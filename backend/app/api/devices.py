"""监测设备档案与校准管理 API."""
from datetime import datetime

from flask import Blueprint, request

from ..domain.constants import CALIBRATION_RESULT_LABELS, DEVICE_STATUS_LABELS
from ..errors import NotFoundError
from ..extensions import db
from ..models import CalibrationRecord
from ..services import device_service
from ..utils.pagination import paginate_query
from ..utils.validation import Validator, parse_datetime
from .helpers import json_payload

bp = Blueprint("devices", __name__)


def _validate_device(data, partial=False):
    validator = Validator(data)
    validator.text("code", "设备编码", required=not partial, max_length=32)
    validator.text("name", "设备名称", required=not partial, max_length=120)
    validator.text("model", "设备型号", required=False, max_length=80)
    validator.text("manufacturer", "生产厂商", required=False, max_length=120)
    station_id = validator.number("station_id", "安装监测点", required=False, minimum=1)
    validator.text("install_location", "安装位置", required=False, max_length=200)
    validator.date_field("installed_at", "安装日期")
    validator.choice(
        "status", "设备状态",
        choices=tuple(DEVICE_STATUS_LABELS.keys()),
        required=False,
        default="available",
    )
    interval = validator.number(
        "calibration_interval_days", "校准周期(天)", required=False, minimum=1, maximum=3650,
        default=365,
    )
    validator.text("remark", "备注", required=False, max_length=1000)
    last_calibration_raw = data.get("last_calibration_at")
    cleaned = validator.raise_if_invalid("设备信息不合法")

    if partial:
        cleaned = {key: value for key, value in cleaned.items() if key in data}
    if station_id is not None:
        cleaned["station_id"] = int(station_id)
    if interval is not None:
        cleaned["calibration_interval_days"] = int(interval)
    if last_calibration_raw not in (None, ""):
        cleaned["last_calibration_at"] = parse_datetime(last_calibration_raw, "最近校准时间")
    if "ranges" in data:
        cleaned["ranges"] = data.get("ranges") or []
    return cleaned


@bp.get("/", strict_slashes=False)
def list_devices():
    query = device_service.device_query(request.args)
    result = paginate_query(query, lambda device: device.to_dict())
    stats = device_service.device_stats([item["id"] for item in result["items"]])
    for item in result["items"]:
        item["stats"] = stats.get(item["id"], {})
        item["status"] = stats.get(item["id"], {}).get("dynamic_status", item["status"])
        item["status_label"] = DEVICE_STATUS_LABELS.get(item["status"], item["status"])
    return result


@bp.post("/", strict_slashes=False)
def create_device():
    payload = _validate_device(json_payload())
    device = device_service.create_device(payload)
    return device.to_dict(include_ranges=True), 201


@bp.get("/options")
def device_options():
    station_id = request.args.get("station_id")
    items = device_service.option_list(station_id=station_id)
    return {"items": items}


@bp.get("/summary")
def device_summary():
    return device_service.metadata_summary()


@bp.get("/calibrations")
def list_calibrations():
    query = device_service.calibration_query(request.args)
    result = paginate_query(query, lambda record: record.to_dict())
    return result


@bp.get("/<int:device_id>")
def get_device(device_id):
    device = device_service.get_device(device_id)
    payload = device.to_dict(include_ranges=True, include_calibrations=True)
    now = datetime.now()
    payload["status"] = device_service.compute_status(device, now)
    payload["status_label"] = DEVICE_STATUS_LABELS.get(payload["status"], payload["status"])
    payload["stats"] = device_service.device_stats([device.id]).get(device.id, {})
    return payload


@bp.put("/<int:device_id>")
def update_device(device_id):
    device = device_service.get_device(device_id)
    payload = _validate_device(json_payload(), partial=True)
    device = device_service.update_device(device, payload)
    return device.to_dict(include_ranges=True)


@bp.delete("/<int:device_id>")
def delete_device(device_id):
    device = device_service.get_device(device_id)
    removed = device_service.delete_device(device)
    return {"id": device_id, "removed": removed}


# ---- 校准管理 -------------------------------------------------------------
@bp.post("/<int:device_id>/calibrations")
def start_calibration(device_id):
    """登记校准开始, 设备进入不可用状态."""
    device = device_service.get_device(device_id)
    data = json_payload()
    validator = Validator(data)
    started_at = validator.datetime_field("started_at", "校准开始时间", required=True)
    validator.text("calibrator", "校准人员", required=False, max_length=64)
    validator.text("organization", "校准机构", required=False, max_length=120)
    validator.text("note", "校准说明", required=False, max_length=500)
    cleaned = validator.raise_if_invalid("校准信息不合法")
    record = device_service.start_calibration(
        device,
        started_at=started_at,
        calibrator=cleaned.get("calibrator"),
        organization=cleaned.get("organization"),
        note=cleaned.get("note"),
    )
    return record.to_dict(), 201


@bp.post("/calibrations/<int:record_id>/finish")
def finish_calibration(record_id):
    """结束校准, 恢复设备可用并重算窗口内数据有效性."""
    record = db.session.get(CalibrationRecord, record_id)
    if record is None:
        raise NotFoundError("校准记录不存在: id=%s" % record_id)
    data = json_payload()
    validator = Validator(data)
    finished_at = validator.datetime_field("finished_at", "校准结束时间", required=True)
    validator.choice(
        "result", "校准结果",
        choices=tuple(CALIBRATION_RESULT_LABELS.keys()),
        required=False,
    )
    validator.text("calibrator", "校准人员", required=False, max_length=64)
    validator.text("organization", "校准机构", required=False, max_length=120)
    validator.text("note", "校准说明", required=False, max_length=500)
    cleaned = validator.raise_if_invalid("校准信息不合法")
    updated, affected = device_service.finish_calibration(
        record,
        finished_at=finished_at,
        result=cleaned.get("result"),
        calibrator=cleaned.get("calibrator"),
        organization=cleaned.get("organization"),
        note=cleaned.get("note"),
    )
    return {
        "calibration": updated.to_dict(),
        "invalidated_count": affected,
        "device_status": device_service.compute_status(updated.device),
    }
