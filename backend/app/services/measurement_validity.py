"""监测数据有效性判定: 校准期间录入的数据保留但标记为无效.

- 有效校准窗口 = 状态非 cancelled 的校准时间区间 (已取消的校准不影响数据)
- 有效性在录入时即时判定; 校准记录增删改后按站点/因子重算历史数据
- 数据转为无效时删除超标记录 (原始判定快照保留); 恢复有效时按现有规则重建
"""
from ..extensions import db
from ..models import CalibrationRecord, Device, Measurement

INVALID_REASON_CALIBRATION = "calibration"
INVALID_REASON_CALIBRATING = "设备校准期间数据"

NON_INVALIDATING_STATUS = ("cancelled",)


def effective_calibration_windows(device_id):
    """Return [(started_at, ended_at, calibration_id), ...] that invalidate readings."""
    records = CalibrationRecord.query.filter(
        CalibrationRecord.device_id == device_id,
        ~CalibrationRecord.status.in_(NON_INVALIDATING_STATUS),
    ).all()
    return [(item.started_at, item.ended_at, item.id) for item in records]


def find_validity_window(windows, measured_at):
    for started_at, ended_at, _id in windows:
        if started_at <= measured_at <= ended_at:
            return started_at, ended_at, _id
    return None


def evaluate_validity(device, measured_at, windows=None):
    """Decide whether a new reading for ``device`` is valid at ``measured_at``."""
    if device is None:
        return True, None, None
    if device.status == "scrapped":
        return False, INVALID_REASON_CALIBRATION, "设备已报废, 数据标记无效"
    windows = windows if windows is not None else effective_calibration_windows(device.id)
    if find_validity_window(windows, measured_at) is not None:
        return False, INVALID_REASON_CALIBRATION, INVALID_REASON_CALIBRATING
    return True, None, None


def revalidate_measurements(station_id=None, pollutant=None, measured_from=None,
                            measured_to=None):
    """Recompute is_valid for stored measurements after calibration/device changes.

    Historical rows without a device are back-filled via the same device
    resolution used at entry time.
    """
    from .device_service import find_entry_device
    from .measurement_service import sync_exceedance_for_record

    query = Measurement.query
    if station_id is not None:
        query = query.filter(Measurement.station_id == station_id)
    if pollutant is not None:
        query = query.filter(Measurement.pollutant == pollutant)
    if measured_from is not None:
        query = query.filter(Measurement.measured_at >= measured_from)
    if measured_to is not None:
        query = query.filter(Measurement.measured_at <= measured_to)

    windows_cache = {}
    changes = 0
    for record in query.all():
        device = db.session.get(Device, record.device_id) if record.device_id else None
        if device is None:
            device = find_entry_device(record.station_id, record.pollutant, record.measured_at)
            if device is not None:
                record.device_id = device.id
        # 历史重判只看校准窗口: 设备报废不溯及既往的有效数据
        windows = (
            windows_cache.setdefault(device.id, effective_calibration_windows(device.id))
            if device is not None else []
        )
        valid = find_validity_window(windows, record.measured_at) is None
        reason_code = None if valid else INVALID_REASON_CALIBRATION
        if record.is_valid == valid and (valid or record.invalid_reason == reason_code):
            continue
        record.is_valid = valid
        record.invalid_reason = None if valid else reason_code
        if not valid:
            if record.exceedance is not None:
                db.session.delete(record.exceedance)
        else:
            sync_exceedance_for_record(record)
        changes += 1
    return changes
