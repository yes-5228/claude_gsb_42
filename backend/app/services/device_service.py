"""监测设备档案与校准管理业务逻辑."""
from datetime import datetime, timedelta

from sqlalchemy import func, or_

from ..domain.constants import (
    CALIBRATION_STATUS_LABELS,
    DEVICE_STATUS_LABELS,
)
from ..domain.standards import POLLUTANT_CODES
from ..errors import ConflictError, NotFoundError, ValidationError
from ..extensions import db
from ..models import CalibrationRecord, Device, Station
from ..models.base import iso
from .measurement_validity import revalidate_measurements

# 校准状态允许的流转
_STATUS_TRANSITIONS = {
    "scheduled": {"in_progress", "cancelled"},
    "in_progress": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


def _split(value):
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


# --------------------------------------------------------------------------
# 设备档案
# --------------------------------------------------------------------------
def get_device(device_id):
    device = db.session.get(Device, device_id)
    if device is None:
        raise NotFoundError("监测设备不存在: id=%s" % device_id)
    return device


def device_query(args):
    query = Device.query.join(Station, Device.station_id == Station.id)
    keyword = (args.get("keyword") or "").strip()
    if keyword:
        like = "%" + keyword + "%"
        query = query.filter(
            or_(Device.name.like(like), Device.code.like(like), Device.location.like(like),
                Device.model.like(like), Device.serial_no.like(like))
        )
    station_ids = [int(item) for item in _split(args.get("station_id")) if item.isdigit()]
    if station_ids:
        query = query.filter(Device.station_id.in_(station_ids))
    pollutants = [item.upper() for item in _split(args.get("pollutant"))]
    if pollutants:
        query = query.filter(Device.pollutant.in_(pollutants))
    statuses = _split(args.get("status"))
    if statuses:
        query = query.filter(Device.status.in_(statuses))
    areas = _split(args.get("area"))
    if areas:
        query = query.filter(Station.area.in_(areas))
    sort_field = {
        "code": Device.code,
        "created_at": Device.created_at,
        "calibration_interval_days": Device.calibration_interval_days,
    }.get(args.get("sort"), Device.code)
    direction = sort_field.desc() if (args.get("order") or "asc") == "desc" else sort_field.asc()
    return query.order_by(direction)


def _validate_uniqueness(code, exclude_id=None):
    query = Device.query.filter(func.lower(Device.code) == code.lower())
    if exclude_id is not None:
        query = query.filter(Device.id != exclude_id)
    if query.first():
        raise ConflictError("设备编码 %s 已存在" % code)


def _validate_range(measure_min, measure_max):
    if measure_min is not None and measure_max is not None and measure_min >= measure_max:
        raise ValidationError(
            "量程下限必须小于上限", fields={"measure_min": "range_invalid"}
        )


def create_device(data):
    _validate_uniqueness(data["code"])
    _validate_range(data.get("measure_min"), data.get("measure_max"))
    device = Device(**data)
    db.session.add(device)
    db.session.commit()
    return device


def update_device(device, data):
    code = data.get("code")
    if code:
        _validate_uniqueness(code, exclude_id=device.id)
    if "measure_min" in data or "measure_max" in data:
        _validate_range(
            data.get("measure_min", device.measure_min),
            data.get("measure_max", device.measure_max),
        )
    for field, value in data.items():
        setattr(device, field, value)
    db.session.commit()
    return device


def delete_device(device):
    """删除设备: 监测数据保留 (device_id 置空), 校准记录一并删除."""
    affected_station_id = device.station_id
    affected_pollutant = device.pollutant
    code = device.code
    db.session.delete(device)
    db.session.commit()
    revalidate_measurements(
        station_id=affected_station_id,
        pollutant=affected_pollutant,
    )
    return {"device_code": code}


def option_list(station_id=None):
    query = Device.query
    if station_id:
        query = query.filter(Device.station_id == int(station_id))
    devices = query.order_by(Device.station_id.asc(), Device.code.asc()).all()
    return [device.to_option() for device in devices]


def device_summary(args=None):
    args = args or {}
    base = device_query(args)
    total = base.count()
    by_status = [
        {"key": key, "label": label, "count": Device.query.filter_by(status=key).count()}
        for key, label in DEVICE_STATUS_LABELS.items()
    ]
    now = datetime.now()
    calibrating = (
        db.session.query(func.count(func.distinct(CalibrationRecord.device_id)))
        .filter(
            CalibrationRecord.status == "in_progress",
            CalibrationRecord.started_at <= now,
            CalibrationRecord.ended_at >= now,
        )
        .scalar()
    )
    due_soon = 0
    overdue = 0
    today = now.date()
    horizon = today + timedelta(days=30)
    for device in Device.query.filter(Device.status != "scrapped").all():
        due = device.next_due_date()
        if due is None:
            continue
        if due < today:
            overdue += 1
        elif due <= horizon:
            due_soon += 1
    return {
        "total": total,
        "by_status": by_status,
        "calibrating_count": int(calibrating or 0),
        "due_soon_count": due_soon,
        "overdue_count": overdue,
    }


# --------------------------------------------------------------------------
# 校准记录
# --------------------------------------------------------------------------
def _overlapping(device, started_at, ended_at, exclude_id=None):
    records = CalibrationRecord.query.filter_by(device_id=device.id).all()
    for item in records:
        if exclude_id is not None and item.id == exclude_id:
            continue
        if item.status == "cancelled":
            continue
        if item.started_at <= ended_at and item.ended_at >= started_at:
            return item
    return None


def _validate_calibration_window(device, started_at, ended_at, exclude_id=None):
    if started_at >= ended_at:
        raise ValidationError(
            "校准结束时间必须晚于开始时间", fields={"ended_at": "range_invalid"}
        )
    overlap = _overlapping(device, started_at, ended_at, exclude_id=exclude_id)
    if overlap is not None:
        raise ConflictError(
            "校准时间与记录 #%s (%s ~ %s, %s) 重叠, 请先调整或取消原记录"
            % (
                overlap.id,
                iso(overlap.started_at),
                iso(overlap.ended_at),
                CALIBRATION_STATUS_LABELS.get(overlap.status, overlap.status),
            )
        )


def get_calibration(device, calibration_id):
    record = db.session.get(CalibrationRecord, calibration_id)
    if record is None or record.device_id != device.id:
        raise NotFoundError("校准记录不存在: id=%s" % calibration_id)
    return record


def get_calibration_by_id(calibration_id):
    record = db.session.get(CalibrationRecord, calibration_id)
    if record is None:
        raise NotFoundError("校准记录不存在: id=%s" % calibration_id)
    return record


def get_calibration_owner(calibration_id):
    record = get_calibration_by_id(calibration_id)
    device = db.session.get(Device, record.device_id)
    if device is None:  # pragma: no cover - 外键保护, 理论不可达
        raise NotFoundError("校准记录所属设备不存在")
    return record, device


def revalidate_after_calibration_change(device, station_id, pollutant):
    revalidate_measurements(station_id=station_id, pollutant=pollutant)


def list_calibrations(device, status=None):
    query = CalibrationRecord.query.filter_by(device_id=device.id)
    if status:
        query = query.filter(CalibrationRecord.status.in_(_split(status)))
    return query.order_by(CalibrationRecord.started_at.desc(), CalibrationRecord.id.desc())


def create_calibration(device, data):
    started_at, ended_at = data["started_at"], data["ended_at"]
    status = data.get("status", "scheduled")
    _validate_calibration_window(device, started_at, ended_at)
    record = CalibrationRecord(device_id=device.id, **data)
    if status in ("completed", "in_progress"):
        record.completed_at = datetime.now() if status == "completed" else None
    db.session.add(record)
    db.session.flush()
    _revalidate_for_record(device, record)
    db.session.commit()
    return record


def update_calibration(device, record, data):
    started_at = data.get("started_at", record.started_at)
    ended_at = data.get("ended_at", record.ended_at)
    status = data.get("status", record.status)
    if status not in (record.status, *_STATUS_TRANSITIONS.get(record.status, set())):
        raise ValidationError(
            "校准状态不能从 %s 变更为 %s"
            % (
                CALIBRATION_STATUS_LABELS.get(record.status, record.status),
                CALIBRATION_STATUS_LABELS.get(status, status),
            ),
            fields={"status": "transition_invalid"},
        )
    _validate_calibration_window(device, started_at, ended_at, exclude_id=record.id)

    for field, value in data.items():
        setattr(record, field, value)
    if status == "completed" and not record.completed_at:
        record.completed_at = datetime.now()
    db.session.flush()
    _revalidate_for_record(device, record)
    db.session.commit()
    return record


def _revalidate_for_record(device, record):
    """Recompute measurement validity for all of the device's station/pollutant.

    A full-history rescan (rather than only the new window) correctly handles
    windows that move or shrink on edit: readings previously covered by an
    older window must be restored.
    """
    revalidate_measurements(
        station_id=device.station_id,
        pollutant=device.pollutant,
    )


# --------------------------------------------------------------------------
# 录入联动: 设备可用性与数据有效性
# --------------------------------------------------------------------------
def find_entry_device(station_id, pollutant, measured_at):
    """Pick the device responsible for a pollutant at a station.

    Prefer non-scrapped devices; when multiple remain, prefer the device whose
    active calibration window covers ``measured_at`` (i.e. the unit being
    calibrated), then the most recently installed one.
    """
    devices = (
        Device.query.filter_by(station_id=station_id, pollutant=pollutant)
        .order_by(Device.status.asc(), Device.installed_at.desc(), Device.id.asc())
        .all()
    )
    if not devices:
        return None
    for device in devices:
        if device.status != "scrapped" and device.active_calibration(measured_at) is not None:
            return device
    for device in devices:
        if device.status != "scrapped":
            return device
    return devices[0]


def availability_payload(station_id, measured_at, pollutant_codes=None):
    """Device availability / range info consumed by the entry form."""
    station = db.session.get(Station, station_id)
    if station is None:
        raise NotFoundError("监测点不存在: id=%s" % station_id)
    codes = pollutant_codes or list(POLLUTANT_CODES)
    devices_map = {}
    for code in codes:
        device = find_entry_device(station_id, code, measured_at)
        if device is None:
            devices_map[code] = None
            continue
        runtime = device.runtime_status(measured_at)
        devices_map[code] = {
            "device_id": device.id,
            "device_code": device.code,
            "device_name": device.name,
            "pollutant": device.pollutant,
            "measure_min": device.measure_min,
            "measure_max": device.measure_max,
            "unit": device.unit,
            "location": device.location,
            "available": runtime["available"],
            "state": runtime["state"],
            "state_label": runtime["state_label"],
            "calibration": runtime["calibration"],
        }

    unavailable = [
        {"pollutant": code, **info}
        for code, info in devices_map.items()
        if info and not info["available"]
    ]
    return {
        "station_id": station_id,
        "measured_at": iso(measured_at),
        "devices": devices_map,
        "unavailable": unavailable,
        "all_available": len(unavailable) == 0,
    }
