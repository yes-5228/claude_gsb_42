"""监测数据录入业务逻辑 (含超标自动判定与设备校准期无效标记)."""
from ..domain import exceedance_rules
from ..domain.standards import get_pollutant
from ..errors import ConflictError, NotFoundError, ValidationError
from ..extensions import db
from ..models import Device, Exceedance, Measurement, Station
from . import device_service


def get_measurement(measurement_id):
    measurement = db.session.get(Measurement, measurement_id)
    if measurement is None:
        raise NotFoundError("监测数据不存在: id=%s" % measurement_id)
    return measurement


def _range_check(device_range, value):
    if device_range is None:
        return None
    if device_range.min_value is not None and value < device_range.min_value:
        return "below"
    if device_range.max_value is not None and value > device_range.max_value:
        return "above"
    return None


def _device_context(device, measured_at):
    """组装录入/预览时需要的设备状态与量程提示."""
    if device is None:
        return None
    usable, reason, record = device_service.availability(device, measured_at)
    range_map = device.range_map()
    return {
        "device_id": device.id,
        "device_code": device.code,
        "device_name": device.name,
        "usable": usable,
        "invalid_reason": reason,
        "calibration": record.to_dict() if record is not None else None,
        "dynamic_status": device_service.compute_status(device, measured_at),
        "ranges": {
            pollutant: {
                "min_value": item.min_value,
                "max_value": item.max_value,
                "unit": item.unit,
            }
            for pollutant, item in range_map.items()
        },
    }


def preview_entries(period, entries, station_id=None, measured_at=None, device_id=None):
    """Dry-run evaluation for the entry form (no database writes)."""
    device = _load_device(device_id, station_id) if device_id else None
    context = _device_context(device, measured_at) if device and measured_at else None
    range_map = device.range_map() if device else {}

    results = []
    for entry in entries:
        pollutant = str(entry.get("pollutant", "")).upper()
        meta = get_pollutant(pollutant)
        if meta is None:
            raise ValidationError("未知监测因子: %s" % entry.get("pollutant"), fields={"pollutant": "unknown"})
        try:
            value = float(entry.get("value"))
        except (TypeError, ValueError):
            raise ValidationError(
                "%s 监测值必须为数字" % meta["label"], fields={pollutant: "invalid_number"}
            )
        evaluation = exceedance_rules.evaluate(pollutant, period, value)
        item = {
            "pollutant": pollutant,
            "pollutant_label": meta["label"],
            "value": value,
            "unit": meta["unit"],
            **evaluation,
        }
        if device is not None:
            item["out_of_range"] = _range_check(range_map.get(pollutant), value)
            item["will_be_invalid"] = bool(context and not context["usable"])
        results.append(item)
    payload = {"period": period, "results": results, "summary": exceedance_rules.summarize(results)}
    if context:
        payload["device_context"] = context
    return payload


def _load_station(station_id):
    station = db.session.get(Station, station_id)
    if station is None:
        raise NotFoundError("监测点不存在: id=%s" % station_id)
    return station


def _load_device(device_id, station_id=None):
    device = db.session.get(Device, device_id)
    if device is None:
        raise NotFoundError("监测设备不存在: id=%s" % device_id)
    if station_id and device.station_id and device.station_id != int(station_id):
        raise ValidationError(
            "设备 %s 未安装在所选监测点, 请重新选择" % device.code,
            fields={"device_id": "station_mismatch"},
        )
    return device


def record_entries(station_id, measured_at, period, entries, data_source="manual",
                   recorder=None, remark=None, overwrite=False, device_id=None):
    """Persist one measured_at snapshot for a station.

    Duplicate (station, pollutant, period, measured_at) rows are reported back;
    when ``overwrite`` is true the existing row is refreshed instead.

    当选择的设备在监测时刻处于校准窗口/校准超期时, 数据照常保存但标记为无效,
    无效数据不参与达标率统计。
    """
    station = _load_station(station_id)
    if not entries:
        raise ValidationError("至少需要录入一条监测数据", fields={"entries": "empty"})

    device = _load_device(device_id, station_id) if device_id else None
    unusable_reason = None
    calibration_info = None
    range_map = {}
    if device is not None:
        usable, unusable_reason, active_record = device_service.availability(
            device, measured_at, data_created_at=None
        )
        calibration_info = active_record.to_dict() if active_record is not None else None
        range_map = device.range_map()

    existing = {
        row.pollutant: row
        for row in Measurement.query.filter_by(
            station_id=station.id, period=period, measured_at=measured_at
        ).all()
    }

    created, updated, exceeded, duplicates, evaluated = [], [], [], [], []
    invalid_count = 0
    out_of_range = []
    seen = set()
    for entry in entries:
        pollutant = str(entry.get("pollutant", "")).upper()
        meta = get_pollutant(pollutant)
        if meta is None:
            raise ValidationError(
                "未知监测因子: %s" % entry.get("pollutant"), fields={"pollutant": "unknown"}
            )
        if pollutant in seen:
            raise ValidationError(
                "%s 在同一时刻重复提交" % meta["label"], fields={pollutant: "duplicated_in_batch"}
            )
        seen.add(pollutant)

        try:
            value = float(entry.get("value"))
        except (TypeError, ValueError):
            raise ValidationError(
                "%s 监测值必须为数字" % meta["label"], fields={pollutant: "invalid_number"}
            )

        range_state = _range_check(range_map.get(pollutant), value) if device is not None else None
        if range_state:
            out_of_range.append({
                "pollutant": pollutant,
                "pollutant_label": meta["label"],
                "state": range_state,
                "configured_min": range_map[pollutant].min_value,
                "configured_max": range_map[pollutant].max_value,
            })

        evaluation = exceedance_rules.evaluate(pollutant, period, value)
        evaluated_item = {
            "pollutant": pollutant,
            "pollutant_label": meta["label"],
            "value": value,
            "unit": meta["unit"],
            **evaluation,
        }
        if device is not None:
            evaluated_item["out_of_range"] = range_state
            evaluated_item["will_be_invalid"] = unusable_reason is not None
        evaluated.append(evaluated_item)

        record = existing.get(pollutant)
        if record is not None and not overwrite:
            duplicates.append(
                {
                    "pollutant": pollutant,
                    "pollutant_label": meta["label"],
                    "value": value,
                    "existing_id": record.id,
                    "message": "该时刻 %s 数据已存在" % meta["label"],
                }
            )
            continue

        is_new = record is None
        if is_new:
            record = Measurement(station_id=station.id, pollutant=pollutant, period=period,
                                 measured_at=measured_at)
            db.session.add(record)

        record.value = value
        record.unit = meta["unit"]
        record.limit_value = evaluation["limit"]
        record.exceed_ratio = evaluation["ratio"]
        record.is_exceeded = evaluation["exceeded"]
        record.data_source = data_source
        record.recorder = entry.get("recorder") or recorder
        record.remark = entry.get("remark") or remark
        record.device_id = device.id if device else None

        # 人工判定无效 (invalid_reason='manual') 不会被录入流程覆盖;
        # 其余记录按设备校准状态确定有效性
        if record.invalid_reason != "manual":
            if unusable_reason is not None:
                record.is_valid = False
                record.invalid_reason = unusable_reason
            else:
                record.is_valid = True
                record.invalid_reason = None
        if not record.is_valid:
            invalid_count += 1

        _sync_exceedance(record, meta, evaluation)
        db.session.flush()
        (created if is_new else updated).append(record.to_dict(include_station=True))
        if evaluation["exceeded"]:
            exceeded.append(record.exceedance.to_dict() if record.exceedance else None)

    if not created and not updated and duplicates:
        raise ConflictError(
            "所选时刻已存在相同数据, 如需覆盖请勾选\"覆盖已有数据\": %s"
            % ", ".join(item["pollutant_label"] for item in duplicates)
        )

    db.session.commit()
    return {
        "station": station.to_option(),
        "device": device.to_option() if device else None,
        "device_unavailable": unusable_reason is not None,
        "invalid_reason": unusable_reason,
        "calibration": calibration_info,
        "out_of_range": out_of_range,
        "measured_at": measured_at.isoformat(timespec="seconds"),
        "period": period,
        "created": created,
        "updated": updated,
        "exceedances": [item for item in exceeded if item],
        "duplicates": duplicates,
        "evaluations": evaluated,
        "summary": {
            "created_count": len(created),
            "updated_count": len(updated),
            "exceeded_count": len([item for item in evaluated if item["exceeded"]]),
            "duplicate_count": len(duplicates),
            "invalid_count": invalid_count,
        },
    }


def _sync_exceedance(record, meta, evaluation):
    """Create / refresh / drop the exceedance row attached to a measurement."""
    if evaluation["exceeded"]:
        if record.exceedance is None:
            record.exceedance = Exceedance(
                station_id=record.station_id,
                pollutant=record.pollutant,
                period=record.period,
                measured_at=record.measured_at,
                value=record.value,
                limit_value=evaluation["limit"],
                exceed_ratio=evaluation["ratio"],
                level=evaluation["level"],
                status="pending",
            )
        else:
            record.exceedance.value = record.value
            record.exceedance.limit_value = evaluation["limit"]
            record.exceedance.exceed_ratio = evaluation["ratio"]
            record.exceedance.level = evaluation["level"]
            record.exceedance.measured_at = record.measured_at
    elif record.exceedance is not None:
        db.session.delete(record.exceedance)


def delete_measurement(measurement):
    payload = measurement.to_dict()
    db.session.delete(measurement)
    db.session.commit()
    return payload
