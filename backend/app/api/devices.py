"""监测设备档案与校准管理 API."""
from flask import Blueprint, request

from ..domain.constants import (
    CALIBRATION_RESULT_LABELS,
    CALIBRATION_STATUS_LABELS,
    DEVICE_STATUS_LABELS,
)
from ..domain.standards import POLLUTANT_CODES, POLLUTANTS
from ..services import device_service
from ..utils.pagination import paginate_query
from ..utils.validation import Validator, parse_datetime
from .helpers import json_payload

bp = Blueprint("devices", __name__)


# --------------------------------------------------------------------------
# 设备档案
# --------------------------------------------------------------------------
def _validate_device(data, partial=False):
    validator = Validator(data)
    validator.text("code", "设备编码", required=not partial, max_length=32)
    validator.text("name", "设备名称", required=not partial, max_length=120)
    validator.number("station_id", "所属监测点", required=not partial, minimum=1)
    validator.choice(
        "pollutant", "监测因子",
        choices=POLLUTANT_CODES, required=not partial,
    )
    validator.text("manufacturer", "生产厂家", required=False, max_length=120)
    validator.text("model", "设备型号", required=False, max_length=64)
    validator.text("serial_no", "出厂编号", required=False, max_length=64)
    validator.number("measure_min", "量程下限")
    validator.number("measure_max", "量程上限")
    validator.text("unit", "计量单位", required=False, max_length=16)
    validator.text("location", "安装位置", required=False, max_length=200)
    validator.number("calibration_interval_days", "校准周期(天)",
                     required=False, minimum=1, maximum=3650, default=365)
    validator.choice(
        "status", "设备状态",
        choices=tuple(DEVICE_STATUS_LABELS.keys()),
        required=False, default="in_service",
    )
    validator.date_field("installed_at", "安装日期")
    validator.text("remark", "备注", required=False, max_length=1000)
    cleaned = validator.raise_if_invalid("设备档案信息不合法")

    if "station_id" in cleaned and cleaned["station_id"] is not None:
        cleaned["station_id"] = int(cleaned["station_id"])
    if "calibration_interval_days" in cleaned and cleaned["calibration_interval_days"] is not None:
        cleaned["calibration_interval_days"] = int(cleaned["calibration_interval_days"])
    if cleaned.get("pollutant"):
        cleaned["pollutant"] = cleaned["pollutant"].upper()
        cleaned.setdefault("unit", POLLUTANTS[cleaned["pollutant"]]["unit"])

    if partial:
        cleaned = {key: value for key, value in cleaned.items() if key in data}
    return cleaned


def _validate_calibration(data, partial=False):
    validator = Validator(data)
    validator.datetime_field("started_at", "校准开始时间", required=not partial)
    validator.datetime_field("ended_at", "校准结束时间", required=not partial)
    validator.choice(
        "status", "校准状态",
        choices=tuple(CALIBRATION_STATUS_LABELS.keys()),
        required=False, default="scheduled",
    )
    validator.choice(
        "result", "校准结果",
        choices=tuple(CALIBRATION_RESULT_LABELS.keys()), required=False,
    )
    validator.text("agency", "校准机构", required=False, max_length=120)
    validator.text("operator", "校准人员", required=False, max_length=64)
    validator.text("certificate_no", "证书编号", required=False, max_length=64)
    validator.text("note", "校准说明", required=False, max_length=1000)
    cleaned = validator.raise_if_invalid("校准记录信息不合法")

    if partial:
        cleaned = {key: value for key, value in cleaned.items() if key in data}

    if not partial and cleaned.get("status") == "completed" and not cleaned.get("result"):
        from ..errors import ValidationError

        raise ValidationError("校准完成时必须登记校准结果", fields={"result": "required"})
    return cleaned


@bp.get("/", strict_slashes=False)
def list_devices():
    query = device_service.device_query(request.args)
    result = paginate_query(
        query, lambda device: device.to_dict(include_status=True)
    )
    result["summary"] = device_service.device_summary(request.args)
    return result


@bp.post("/", strict_slashes=False)
def create_device():
    payload = _validate_device(json_payload())
    device = device_service.create_device(payload)
    return device.to_dict(include_status=True), 201


@bp.get("/summary")
def devices_summary():
    return device_service.device_summary(request.args)


@bp.get("/options")
def device_options():
    station_id = request.args.get("station_id")
    return {
        "items": device_service.option_list(station_id=station_id),
        "statuses": [
            {"value": key, "label": label} for key, label in DEVICE_STATUS_LABELS.items()
        ],
        "calibration_statuses": [
            {"value": key, "label": label}
            for key, label in CALIBRATION_STATUS_LABELS.items()
        ],
        "calibration_results": [
            {"value": key, "label": label}
            for key, label in CALIBRATION_RESULT_LABELS.items()
        ],
    }


@bp.get("/availability")
def device_availability():
    """录入界面联动: 指定监测点/时刻各因子设备是否可用、量程与校准窗口."""
    from ..errors import ValidationError

    station_id = request.args.get("station_id")
    if not station_id:
        raise ValidationError("station_id 不能为空", fields={"station_id": "required"})
    measured_at = parse_datetime(request.args.get("measured_at"), "监测时间")
    pollutants = [item.upper() for item in (request.args.get("pollutants") or "").split(",") if item.strip()]
    if pollutants:
        unknown = [item for item in pollutants if item not in POLLUTANT_CODES]
        if unknown:
            raise ValidationError("未知监测因子: %s" % ",".join(unknown), fields={"pollutants": "unknown"})
    return device_service.availability_payload(int(station_id), measured_at, pollutants or None)


@bp.get("/<int:device_id>")
def get_device(device_id):
    device = device_service.get_device(device_id)
    return device.to_dict(include_status=True, include_calibrations=True)


@bp.put("/<int:device_id>")
def update_device(device_id):
    device = device_service.get_device(device_id)
    payload = _validate_device(json_payload(), partial=True)
    return device_service.update_device(device, payload).to_dict(include_status=True)


@bp.delete("/<int:device_id>")
def delete_device(device_id):
    device = device_service.get_device(device_id)
    result = device_service.delete_device(device)
    return {"id": device_id, "deleted": True, **result}


# --------------------------------------------------------------------------
# 校准记录 (嵌套在设备下)
# --------------------------------------------------------------------------
@bp.get("/<int:device_id>/calibrations")
def list_calibrations(device_id):
    device = device_service.get_device(device_id)
    query = device_service.list_calibrations(device, status=request.args.get("status"))
    result = paginate_query(query, lambda record: record.to_dict())
    result["device"] = device.to_dict(include_status=True)
    return result


@bp.post("/<int:device_id>/calibrations")
def create_calibration(device_id):
    device = device_service.get_device(device_id)
    payload = _validate_calibration(json_payload())
    record = device_service.create_calibration(device, payload)
    return record.to_dict(), 201


@bp.get("/calibrations/<int:calibration_id>")
def get_calibration(calibration_id):
    record = device_service.get_calibration_by_id(calibration_id)
    return record.to_dict()


@bp.put("/calibrations/<int:calibration_id>")
def update_calibration(calibration_id):
    record, device = device_service.get_calibration_owner(calibration_id)
    payload = _validate_calibration(json_payload(), partial=True)
    return device_service.update_calibration(device, record, payload).to_dict()


@bp.delete("/calibrations/<int:calibration_id>")
def delete_calibration(calibration_id):
    from ..extensions import db

    record, device = device_service.get_calibration_owner(calibration_id)
    station_id, pollutant = device.station_id, device.pollutant
    db.session.delete(record)
    db.session.flush()
    device_service.revalidate_after_calibration_change(device, station_id, pollutant)
    db.session.commit()
    return {"id": calibration_id, "deleted": True}
