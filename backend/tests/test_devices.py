"""监测设备档案与校准管理测试."""
from datetime import datetime

import pytest

from app.extensions import db
from app.models import CalibrationRecord, Device, Exceedance, Measurement
from app.services import device_service


@pytest.fixture
def device(station):
    return device_service.create_device(
        {
            "code": "DEV-PM25-01",
            "name": "PM2.5 分析仪",
            "station_id": station.id,
            "pollutant": "PM25",
            "manufacturer": "聚光科技",
            "model": "AQMS-503",
            "measure_min": 0.0,
            "measure_max": 1000.0,
            "unit": "μg/m³",
            "location": "站房顶部 1 号位",
            "calibration_interval_days": 180,
            "status": "in_service",
            "installed_at": None,
            "remark": None,
        }
    )


def _calibration(device, start, end, status="scheduled", **extra):
    return device_service.create_calibration(
        device,
        {
            "started_at": start,
            "ended_at": end,
            "status": status,
            "agency": "市计量院",
            "operator": "王敏",
            **extra,
        },
    )


# --------------------------------------------------------------------------
# 设备档案 CRUD
# --------------------------------------------------------------------------
def test_create_device_and_list(client, station):
    response = client.post(
        "/api/devices",
        json={
            "code": "DEV-SO2-01",
            "name": "SO₂ 分析仪",
            "station_id": station.id,
            "pollutant": "SO2",
            "measure_min": 0,
            "measure_max": 500,
            "calibration_interval_days": 365,
            "location": "机柜 A 列",
        },
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["pollutant_label"] == "SO₂"
    assert body["runtime"]["available"] is True

    listing = client.get("/api/devices?station_id=%d" % station.id).get_json()
    assert listing["total"] == 1
    assert listing["items"][0]["code"] == "DEV-SO2-01"
    assert listing["summary"]["total"] == 1


def test_duplicate_device_code_conflict(client, device):
    response = client.post(
        "/api/devices",
        json={
            "code": "DEV-PM25-01",
            "name": "另一台设备",
            "station_id": device.station_id,
            "pollutant": "PM25",
        },
    )
    assert response.status_code == 409


def test_device_range_validation(client, station):
    response = client.post(
        "/api/devices",
        json={
            "code": "BAD-RANGE",
            "name": "量程错误设备",
            "station_id": station.id,
            "pollutant": "CO",
            "measure_min": 100,
            "measure_max": 10,
        },
    )
    assert response.status_code == 422
    assert response.get_json()["error"]["fields"]["measure_min"] == "range_invalid"


def test_update_and_delete_device_keeps_measurements(client, station, entry_payload, device):
    # 先录入一条数据, 再删除设备: 数据保留, device_id 置空, 仍为有效
    client.post(
        "/api/measurements/entries",
        json=entry_payload(station.id, entries=[{"pollutant": "PM25", "value": 40.0}]),
    )
    record = Measurement.query.filter_by(pollutant="PM25").one()
    assert record.device_id == device.id

    response = client.delete("/api/devices/%d" % device.id)
    assert response.status_code == 200
    db.session.expire_all()
    record = Measurement.query.filter_by(pollutant="PM25").one()
    assert record.device_id is None
    assert record.is_valid is True
    assert Device.query.count() == 0
    assert CalibrationRecord.query.count() == 0


# --------------------------------------------------------------------------
# 校准记录
# --------------------------------------------------------------------------
def test_create_calibration_and_runtime_unavailable(client, device):
    start = datetime(2026, 9, 10, 9, 0)
    end = datetime(2026, 9, 10, 18, 0)
    response = client.post(
        "/api/devices/%d/calibrations" % device.id,
        json={"started_at": start.isoformat(), "ended_at": end.isoformat()},
    )
    assert response.status_code == 201

    detail = client.get("/api/devices/%d" % device.id).get_json()
    assert detail["calibrations"][0]["status"] == "scheduled"

    # 校准中的设备动态不可用
    _calibration(device, datetime(2030, 1, 1, 0, 0), datetime(2030, 1, 2, 0, 0),
                 status="in_progress")
    runtime = device_service.get_device(device.id).runtime_status(datetime(2030, 1, 1, 12, 0))
    assert runtime["available"] is False
    assert runtime["state"] == "calibrating"


def test_overlapping_calibration_rejected(device):
    _calibration(device, datetime(2026, 9, 10, 9, 0), datetime(2026, 9, 10, 18, 0))
    with pytest.raises(Exception):
        _calibration(device, datetime(2026, 9, 10, 15, 0), datetime(2026, 9, 10, 20, 0))


def test_calibration_status_transition_is_validated(client, device):
    record = _calibration(device, datetime(2026, 9, 1, 9, 0), datetime(2026, 9, 1, 12, 0))
    # completed 不能直接从 scheduled 跳转
    response = client.put(
        "/api/devices/calibrations/%d" % record.id,
        json={"status": "completed", "result": "passed"},
    )
    assert response.status_code == 422


def test_completed_calibration_requires_result(client, device):
    response = client.post(
        "/api/devices/%d/calibrations" % device.id,
        json={
            "started_at": datetime(2026, 9, 1, 9, 0).isoformat(),
            "ended_at": datetime(2026, 9, 1, 12, 0).isoformat(),
            "status": "completed",
        },
    )
    assert response.status_code == 422
    assert "result" in response.get_json()["error"]["fields"]


def test_delete_calibration_restores_measurement_validity(client, station, device, entry_payload):
    start = datetime(2026, 9, 1, 0, 0)
    end = datetime(2026, 9, 2, 0, 0)
    record = _calibration(device, start, end)

    client.post(
        "/api/measurements/entries",
        json=entry_payload(
            station.id,
            measured_at="2026-09-01 10:00",
            entries=[{"pollutant": "PM25", "value": 40.0}],
        ),
    )
    row = Measurement.query.one()
    assert row.is_valid is False

    response = client.delete("/api/devices/calibrations/%d" % record.id)
    assert response.status_code == 200
    db.session.expire_all()
    assert Measurement.query.one().is_valid is True


def test_cancel_calibration_does_not_invalidate_existing_rows(device, station, entry_payload, client):
    record = _calibration(device, datetime(2026, 9, 1, 0, 0), datetime(2026, 9, 2, 0, 0))
    client.post(
        "/api/measurements/entries",
        json=entry_payload(
            station.id, measured_at="2026-09-01 10:00",
            entries=[{"pollutant": "PM25", "value": 40.0}],
        ),
    )
    assert Measurement.query.one().is_valid is False

    client.put(
        "/api/devices/calibrations/%d" % record.id, json={"status": "cancelled"}
    )
    db.session.expire_all()
    assert Measurement.query.one().is_valid is True


def test_moving_calibration_window_restores_old_range(device, station, entry_payload, client):
    # 校准窗口登记在 9-01 -> 数据无效; 改为 9-10 后, 9-01 数据应恢复有效
    record = _calibration(
        device,
        datetime(2026, 9, 1, 0, 0),
        datetime(2026, 9, 2, 0, 0),
        status="in_progress",
    )
    client.post(
        "/api/measurements/entries",
        json=entry_payload(
            station.id, measured_at="2026-09-01 10:00",
            period="daily", entries=[{"pollutant": "PM25", "value": 200.0}],
        ),
    )
    assert Measurement.query.one().is_valid is False

    client.put(
        "/api/devices/calibrations/%d" % record.id,
        json={
            "started_at": datetime(2026, 9, 10, 0, 0).isoformat(),
            "ended_at": datetime(2026, 9, 11, 0, 0).isoformat(),
        },
    )
    db.session.expire_all()
    row = Measurement.query.one()
    assert row.is_valid is True
    assert Exceedance.query.count() == 1  # 恢复有效且超标, 重新生成超标单


# --------------------------------------------------------------------------
# 录入联动: 校准期数据无效 + 可用性接口
# --------------------------------------------------------------------------
def test_entry_during_calibration_is_retained_but_invalid(
    client, station, device, entry_payload
):
    _calibration(
        device,
        datetime(2026, 9, 1, 0, 0),
        datetime(2026, 9, 2, 0, 0),
        status="in_progress",
    )
    response = client.post(
        "/api/measurements/entries",
        json=entry_payload(
            station.id,
            measured_at="2026-09-01 10:00",
            period="daily",
            entries=[
                {"pollutant": "PM25", "value": 60.0},   # 校准期
                {"pollutant": "SO2", "value": 900.0},   # 无设备, 正常超标
            ],
        ),
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["summary"]["invalid_count"] == 1
    assert body["summary"]["exceeded_count"] == 1
    assert body["invalid_items"][0]["pollutant"] == "PM25"

    pm25 = Measurement.query.filter_by(pollutant="PM25").one()
    assert pm25.is_valid is False
    assert pm25.invalid_reason == "calibration"
    # 原始超标判定快照保留
    assert pm25.limit_value == 75.0
    # 无效数据不产生超标记录
    assert Exceedance.query.filter_by(pollutant="PM25").count() == 0
    assert Exceedance.query.filter_by(pollutant="SO2").count() == 1


def test_entry_result_marks_invalid_evaluations(client, station, device, entry_payload):
    _calibration(
        device,
        datetime(2026, 9, 1, 0, 0),
        datetime(2026, 9, 2, 0, 0),
        status="in_progress",
    )
    body = client.post(
        "/api/measurements/entries",
        json=entry_payload(
            station.id,
            measured_at="2026-09-01 10:00",
            entries=[{"pollutant": "PM25", "value": 200.0}],
        ),
    ).get_json()
    evaluation = body["evaluations"][0]
    assert evaluation["is_valid"] is False
    assert evaluation["invalid_message"] == "设备校准期间数据"
    assert evaluation["device_code"] == "DEV-PM25-01"


def test_retroactive_calibration_marks_existing_data_invalid(
    client, station, device, entry_payload
):
    # 先录入有效且超标数据, 后补录校准记录: 历史数据重判为无效, 超标记录撤销
    client.post(
        "/api/measurements/entries",
        json=entry_payload(
            station.id,
            measured_at="2026-09-01 10:00",
            period="daily",
            entries=[{"pollutant": "PM25", "value": 200.0}],
        ),
    )
    assert Exceedance.query.count() == 1

    _calibration(
        device,
        datetime(2026, 9, 1, 0, 0),
        datetime(2026, 9, 2, 0, 0),
        status="completed",
        result="passed",
    )
    row = Measurement.query.one()
    assert row.is_valid is False
    assert Exceedance.query.count() == 0


def test_availability_endpoint_reports_unavailable_device(client, station, device):
    _calibration(
        device,
        datetime(2026, 9, 1, 8, 0),
        datetime(2026, 9, 1, 20, 0),
        status="in_progress",
    )
    response = client.get(
        "/api/devices/availability?station_id=%d&measured_at=2026-09-01%%2010:00" % station.id
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["all_available"] is False
    pm25 = body["devices"]["PM25"]
    assert pm25["available"] is False
    assert pm25["measure_min"] == 0.0
    assert pm25["calibration"]["status"] == "in_progress"
    assert body["unavailable"][0]["pollutant"] == "PM25"

    outside = client.get(
        "/api/devices/availability?station_id=%d&measured_at=2026-09-02%%2010:00" % station.id
    ).get_json()
    assert outside["devices"]["PM25"]["available"] is True


def test_entry_context_contains_devices(client, station, device):
    body = client.get("/api/measurements/entry-context").get_json()
    assert body["devices"][0]["code"] == "DEV-PM25-01"


def test_scrapped_device_makes_readings_invalid(client, station, device, entry_payload):
    client.put("/api/devices/%d" % device.id, json={"status": "scrapped"})
    body = client.post(
        "/api/measurements/entries",
        json=entry_payload(
            station.id, measured_at="2026-09-01 10:00",
            entries=[{"pollutant": "PM25", "value": 40.0}],
        ),
    ).get_json()
    assert body["summary"]["invalid_count"] == 1
    assert Measurement.query.one().is_valid is False
