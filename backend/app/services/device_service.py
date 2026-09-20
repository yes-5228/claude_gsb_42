"""监测设备档案、量程与校准管理业务逻辑.

有效性规则集中在本模块:
* 校准时间窗 (started_at <= measured_at <= finished_at, 未结束窗口只有下界) 内
  由该设备采集的数据标记为无效 (invalid_reason='calibration');
* 设备超过校准周期仍未再次校准 (last_calibration_at + interval < now) 时,
  新录入的数据标记为无效 (invalid_reason='calibration_overdue');
* 无效数据原样保留, 但不参与达标率统计。
"""
from datetime import datetime, timedelta

from sqlalchemy import func, or_

from ..domain.constants import DEVICE_STATUS_LABELS
from ..errors import ConflictError, NotFoundError, ValidationError
from ..extensions import db
from ..models import CalibrationRecord, Device, DeviceRange, Measurement, Station
from ..models.base import iso
from ..domain.standards import POLLUTANT_CODES

DEVICE_STATUS_CHOICES = tuple(DEVICE_STATUS_LABELS.keys())
CALIBRATION_RESULT_CHOICES = ("pass", "fail")


def _split(value):
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


# ---------------------------------------------------------------------------
# 校准窗口与设备状态
# ---------------------------------------------------------------------------
def is_in_calibration(device, measured_at):
    """该设备在 measured_at 时刻是否处于校准时间窗内."""
    records = CalibrationRecord.query.filter(
        CalibrationRecord.device_id == device.id,
        CalibrationRecord.started_at <= measured_at,
        or_(
            CalibrationRecord.finished_at.is_(None),
            CalibrationRecord.finished_at >= measured_at,
        ),
    ).all()
    return bool(records)


def active_calibration(device, at=None):
    """当前仍在进行中的校准记录 (可能因为结束时间晚于 now 也算占用)."""
    moment = at or datetime.now()
    return (
        CalibrationRecord.query.filter(
            CalibrationRecord.device_id == device.id,
            CalibrationRecord.started_at <= moment,
            or_(
                CalibrationRecord.finished_at.is_(None),
                CalibrationRecord.finished_at >= moment,
            ),
        )
        .order_by(CalibrationRecord.started_at.desc())
        .first()
    )


def is_overdue(device, at=None):
    """超过校准周期且未再校准."""
    if device.status == "retired":
        return False
    moment = at or datetime.now()
    if not device.last_calibration_at:
        return False
    next_due = device.last_calibration_at + timedelta(days=device.calibration_interval_days)
    return next_due < moment


def compute_status(device, at=None):
    """根据校准记录动态计算设备状态 (retired 为人工停用, 优先级最高)."""
    moment = at or datetime.now()
    if device.status == "retired":
        return "retired"
    record = active_calibration(device, moment)
    if record is not None:
        return "calibrating"
    if is_overdue(device, moment):
        return "overdue"
    return "available"


def availability(device, measured_at, data_created_at=None):
    """录入时判定: 返回 (是否可用, 无效原因或 None, 占用中的校准记录).

    校准超期按监测时刻判断: 若 measured_at 已过到期日, 且在 measured_at
    之后没有新的合格校准覆盖, 则该时刻数据视为超期无效。

    ``data_created_at`` 为数据实际写入时刻 (默认当前)。为避免"事后补登一条
    进行中校准"误伤补登之前已入库的历史数据, 只有校准记录登记早于数据写入时,
    该时间窗才使数据无效。
    """
    if device.status == "retired":
        return False, None, None
    created_at = data_created_at or datetime.now()
    record = (
        CalibrationRecord.query.filter(
            CalibrationRecord.device_id == device.id,
            CalibrationRecord.started_at <= measured_at,
            CalibrationRecord.created_at <= created_at,
            or_(
                CalibrationRecord.finished_at.is_(None),
                CalibrationRecord.finished_at >= measured_at,
            ),
        )
        .order_by(CalibrationRecord.started_at.desc())
        .first()
    )
    if record is not None:
        return False, "calibration", record
    if device.last_calibration_at and measured_at >= device.last_calibration_at:
        due_at = device.last_calibration_at + timedelta(days=device.calibration_interval_days)
        if measured_at >= due_at:
            later_calibration = CalibrationRecord.query.filter(
                CalibrationRecord.device_id == device.id,
                CalibrationRecord.started_at > measured_at,
            ).first()
            if later_calibration is None:
                return False, "calibration_overdue", None
    return True, None, None


# ---------------------------------------------------------------------------
# 档案查询
# ---------------------------------------------------------------------------
def device_query(args):
    query = db.session.query(Device).outerjoin(Station, Device.station_id == Station.id)
    keyword = (args.get("keyword") or "").strip()
    if keyword:
        like = "%" + keyword + "%"
        query = query.filter(
            or_(Device.name.like(like), Device.code.like(like), Device.model.like(like))
        )
    station_ids = []
    for item in _split(args.get("station_id")):
        try:
            station_ids.append(int(item))
        except ValueError:
            raise ValidationError("station_id 参数必须为整数", fields={"station_id": "invalid_integer"})
    if station_ids:
        query = query.filter(Device.station_id.in_(station_ids))
    areas = _split(args.get("area"))
    if areas:
        query = query.filter(Station.area.in_(areas))
    statuses = _split(args.get("status"))
    for status in statuses:
        if status not in DEVICE_STATUS_CHOICES:
            raise ValidationError("未知设备状态: %s" % status, fields={"status": "unknown"})

    sort_field = {
        "code": Device.code,
        "name": Device.name,
        "installed_at": Device.installed_at,
        "created_at": Device.created_at,
    }.get(args.get("sort"), Device.code)
    direction = sort_field.desc() if (args.get("order") or "asc") == "desc" else sort_field.asc()
    query = query.order_by(direction)

    # available / calibrating / overdue 为动态状态, 需在 Python 侧计算过滤
    if statuses:
        now = datetime.now()
        rows = [row for row in query.all() if compute_status(row, now) in statuses]
        return _StaticListQuery(rows)
    return query


class _StaticListQuery:
    """内存中过滤后的列表, 兼容 paginate_query 的 count/all/limit/offset 调用.

    SQL 语义下 limit/offset 与调用顺序无关, 这里延迟到 all() 时一并应用。
    """

    def __init__(self, rows, limit=None, offset=0):
        self._rows = rows
        self._limit = limit
        self._offset = offset

    def count(self):
        return len(self._rows)

    def limit(self, value):
        return _StaticListQuery(self._rows, limit=value, offset=self._offset)

    def offset(self, value):
        return _StaticListQuery(self._rows, limit=self._limit, offset=value)

    def all(self):
        rows = self._rows[self._offset:]
        if self._limit is not None:
            rows = rows[: self._limit]
        return list(rows)


def get_device(device_id):
    device = db.session.get(Device, device_id)
    if device is None:
        raise NotFoundError("监测设备不存在: id=%s" % device_id)
    return device


def option_list(station_id=None):
    query = Device.query
    if station_id:
        query = query.filter(Device.station_id == int(station_id))
    devices = query.order_by(Device.code.asc()).all()
    return [device.to_option() for device in devices]


def device_stats(device_ids):
    if not device_ids:
        return {}
    measurements = dict(
        db.session.query(Measurement.device_id, func.count(Measurement.id))
        .filter(Measurement.device_id.in_(device_ids))
        .group_by(Measurement.device_id)
        .all()
    )
    invalid = dict(
        db.session.query(Measurement.device_id, func.count(Measurement.id))
        .filter(Measurement.device_id.in_(device_ids), Measurement.is_valid.is_(False))
        .group_by(Measurement.device_id)
        .all()
    )
    now = datetime.now()
    result = {}
    for device_id in device_ids:
        status = compute_status(get_device(device_id), now)
        result[device_id] = {
            "measurement_count": int(measurements.get(device_id, 0)),
            "invalid_count": int(invalid.get(device_id, 0)),
            "dynamic_status": status,
        }
    return result


def metadata_summary():
    devices = Device.query.all()
    now = datetime.now()
    by_status = {
        key: {"key": key, "label": label, "count": 0}
        for key, label in DEVICE_STATUS_LABELS.items()
    }
    for device in devices:
        by_status[compute_status(device, now)]["count"] += 1
    open_calibrations = CalibrationRecord.query.filter(CalibrationRecord.finished_at.is_(None)).count()
    return {
        "total": len(devices),
        "by_status": list(by_status.values()),
        "open_calibrations": int(open_calibrations),
    }


# ---------------------------------------------------------------------------
# 档案写入
# ---------------------------------------------------------------------------
def _validate_ranges(ranges):
    cleaned = []
    seen = set()
    for item in ranges or []:
        if not isinstance(item, dict):
            raise ValidationError("量程配置必须是对象数组", fields={"ranges": "invalid"})
        pollutant = str(item.get("pollutant", "")).upper()
        if pollutant not in POLLUTANT_CODES:
            raise ValidationError("量程中存在未知监测因子: %s" % pollutant,
                                  fields={"ranges": "unknown_pollutant"})
        if pollutant in seen:
            raise ValidationError("因子 %s 的量程重复配置" % pollutant,
                                  fields={"ranges": "duplicated_pollutant"})
        seen.add(pollutant)
        min_value = item.get("min_value")
        max_value = item.get("max_value")
        min_value = float(min_value) if min_value not in (None, "") else None
        max_value = float(max_value) if max_value not in (None, "") else None
        if min_value is not None and min_value < 0:
            raise ValidationError("%s 量程下限不能为负" % pollutant,
                                  fields={"ranges": "min_negative"})
        if min_value is not None and max_value is not None and min_value > max_value:
            raise ValidationError("%s 量程下限不能大于上限" % pollutant,
                                  fields={"ranges": "range_invalid"})
        cleaned.append({
            "pollutant": pollutant,
            "min_value": min_value,
            "max_value": max_value,
            "unit": (str(item["unit"]).strip() if item.get("unit") else None),
        })
    return cleaned


def _assert_code_unique(code, exclude_id=None):
    query = Device.query.filter(func.lower(Device.code) == code.lower())
    if exclude_id:
        query = query.filter(Device.id != exclude_id)
    if query.first():
        raise ConflictError("设备编码 %s 已存在" % code)


def _load_station(station_id):
    if station_id in (None, ""):
        return None
    station = db.session.get(Station, int(station_id))
    if station is None:
        raise NotFoundError("监测点不存在: id=%s" % station_id)
    return station


def create_device(data):
    ranges = _validate_ranges(data.pop("ranges", []))
    code = data["code"]
    _assert_code_unique(code)
    station = _load_station(data.get("station_id"))
    device = Device(
        code=code,
        name=data["name"],
        model=data.get("model"),
        manufacturer=data.get("manufacturer"),
        station_id=station.id if station else None,
        install_location=data.get("install_location"),
        installed_at=data.get("installed_at"),
        status=data.get("status", "available"),
        calibration_interval_days=int(data.get("calibration_interval_days") or 365),
        last_calibration_at=data.get("last_calibration_at"),
        remark=data.get("remark"),
    )
    if device.calibration_interval_days <= 0:
        raise ValidationError("校准周期必须为正整数(天)",
                              fields={"calibration_interval_days": "invalid"})
    for item in ranges:
        device.ranges.append(DeviceRange(**item))
    db.session.add(device)
    db.session.commit()
    return device


def update_device(device, data):
    if "code" in data and data["code"]:
        _assert_code_unique(data["code"], exclude_id=device.id)
        device.code = data["code"]
    for field in ("name", "model", "manufacturer", "install_location",
                  "installed_at", "calibration_interval_days", "last_calibration_at", "remark"):
        if field in data:
            setattr(device, field, data[field])
    if "station_id" in data:
        station = _load_station(data["station_id"])
        device.station_id = station.id if station else None
    if "status" in data and data["status"]:
        if data["status"] not in DEVICE_STATUS_CHOICES:
            raise ValidationError("设备状态取值不合法", fields={"status": "unknown"})
        device.status = data["status"]
    if device.calibration_interval_days <= 0:
        raise ValidationError("校准周期必须为正整数(天)",
                              fields={"calibration_interval_days": "invalid"})
    if "ranges" in data:
        device.ranges = []
        db.session.flush()
        for item in _validate_ranges(data["ranges"]):
            device.ranges.append(DeviceRange(**item))
    db.session.commit()
    return device


def delete_device(device):
    """删除设备档案; 历史监测数据保留但解除设备关联."""
    measurement_count = Measurement.query.filter_by(device_id=device.id).count()
    db.session.delete(device)
    db.session.commit()
    return {"measurements_detached": measurement_count}


# ---------------------------------------------------------------------------
# 校准管理
# ---------------------------------------------------------------------------
def calibration_query(args):
    query = db.session.query(CalibrationRecord).join(
        Device, CalibrationRecord.device_id == Device.id
    ).outerjoin(Station, Device.station_id == Station.id)
    device_ids = []
    for item in _split(args.get("device_id")):
        try:
            device_ids.append(int(item))
        except ValueError:
            raise ValidationError("device_id 参数必须为整数", fields={"device_id": "invalid_integer"})
    if device_ids:
        query = query.filter(CalibrationRecord.device_id.in_(device_ids))
    station_ids = []
    for item in _split(args.get("station_id")):
        try:
            station_ids.append(int(item))
        except ValueError:
            raise ValidationError("station_id 参数必须为整数", fields={"station_id": "invalid_integer"})
    if station_ids:
        query = query.filter(Device.station_id.in_(station_ids))
    active = (args.get("active") or "").strip().lower()
    if active in {"1", "true", "yes"}:
        query = query.filter(CalibrationRecord.finished_at.is_(None))
    elif active in {"0", "false", "no"}:
        query = query.filter(CalibrationRecord.finished_at.isnot(None))
    result = args.get("result")
    if result:
        query = query.filter(CalibrationRecord.result == result)
    return query.order_by(CalibrationRecord.started_at.desc(), CalibrationRecord.id.desc())


def start_calibration(device, started_at, calibrator=None, organization=None, note=None):
    """登记一次校准开始, 设备进入不可用状态 (拒绝重叠的校准窗口)."""
    if device.status == "retired":
        raise ValidationError("已停用的设备不能登记校准", fields={"device": "retired"})
    overlap = CalibrationRecord.query.filter(
        CalibrationRecord.device_id == device.id,
        CalibrationRecord.started_at <= started_at,
        or_(
            CalibrationRecord.finished_at.is_(None),
            CalibrationRecord.finished_at >= started_at,
        ),
    ).first()
    if overlap is not None:
        raise ConflictError(
            "该设备在 %s 已存在校准窗口 (%s ~ %s), 不能重复登记"
            % (iso(started_at), iso(overlap.started_at), iso(overlap.finished_at) or "进行中")
        )
    record = CalibrationRecord(
        device_id=device.id,
        started_at=started_at,
        calibrator=calibrator,
        organization=organization,
        note=note,
    )
    db.session.add(record)
    db.session.commit()
    return record


def finish_calibration(record, finished_at, result=None, calibrator=None,
                       organization=None, note=None):
    """结束校准: 设备恢复可用, 并重算落在窗口内的历史数据有效性."""
    if record.finished_at is not None:
        raise ConflictError("该校准记录已结束, 不能重复操作")
    if finished_at < record.started_at:
        raise ValidationError("校准结束时间不能早于开始时间 %s" % iso(record.started_at),
                              fields={"finished_at": "range_invalid"})
    overlapping_newer = CalibrationRecord.query.filter(
        CalibrationRecord.device_id == record.device_id,
        CalibrationRecord.id != record.id,
        CalibrationRecord.started_at <= finished_at,
        CalibrationRecord.started_at >= record.started_at,
    ).first()
    if overlapping_newer is not None:
        raise ConflictError("结束时间与其他校准窗口冲突, 请检查")

    record.finished_at = finished_at
    if result:
        if result not in CALIBRATION_RESULT_CHOICES:
            raise ValidationError("校准结果取值不合法", fields={"result": "unknown"})
        record.result = result
    if calibrator is not None:
        record.calibrator = calibrator
    if organization is not None:
        record.organization = organization
    if note is not None:
        record.note = note

    device = record.device
    # 合格校准后推进"最近校准时间"; 不合格不推进, 设备继续视为超期/不可信
    if result == "pass":
        current = device.last_calibration_at
        if current is None or finished_at > current:
            device.last_calibration_at = finished_at

    db.session.flush()
    affected = revalidate_device(device)
    db.session.commit()
    return record, affected


def revalidate_device(device):
    """按已结束的校准窗口重算该设备历史数据的有效性标记.

    补登一条**进行中**的校准不应追溯性作废此前已入库的数据, 因此此处只
    覆盖已结束的完整窗口; 进行中窗口仅在录入当时拦截。返回窗口内被置为
    无效的数据条数; 人工标记无效 (invalid_reason='manual') 的记录不动。
    """
    records = (
        Measurement.query.filter_by(device_id=device.id)
        .order_by(Measurement.measured_at.asc())
        .all()
    )
    windows = [
        (row.started_at, row.finished_at)
        for row in CalibrationRecord.query.filter(
            CalibrationRecord.device_id == device.id,
            CalibrationRecord.finished_at.isnot(None),
        )
        .order_by(CalibrationRecord.started_at.asc())
        .all()
    ]
    invalid_count = 0
    for measurement in records:
        if measurement.invalid_reason == "manual":
            continue
        in_window = any(
            start <= measurement.measured_at <= end
            for start, end in windows
        )
        if in_window:
            measurement.is_valid = False
            measurement.invalid_reason = "calibration"
            invalid_count += 1
        else:
            # 窗口外: 按校准超期规则重判
            _, reason, _ = availability(device, measurement.measured_at,
                                        data_created_at=measurement.created_at)
            if reason == "calibration_overdue":
                measurement.is_valid = False
                measurement.invalid_reason = reason
                invalid_count += 1
            else:
                measurement.is_valid = True
                measurement.invalid_reason = None
    return invalid_count
