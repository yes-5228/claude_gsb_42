"""监测设备档案、量程与校准管理测试."""
from datetime import datetime, timedelta

import pytest

from app.extensions import db
from app.models import CalibrationRecord, Device, DeviceRange, Measurement
from app.services import device_service


@pytest.fixture
def device_payload(station):
    def _make(**overrides):
        payload = {
            "code": "AQMS-100",
            "name": "多因子分析仪",
            "model": "TH-2000",
            "manufacturer": "先河环保",
            "station_id": station.id,
            "install_location": "主站房屋顶",
            "installed_at": "2024-01-10",
            "status": "available",
            "calibration_interval_days": 180,
            "ranges": [
                {"pollutant": "PM25", "min_value": 0, "max_value": 1000, "unit": "μg/m³"},
                {"pollutant": "SO2", "min_value": 0, "max_value": 500},
            ],
        }
        payload.update(overrides)
        return payload

    return _make


def _create_device(client, payload):
    return client.post("/api/devices/", json=payload)


# --------------------------------------------------------------------------
# 档案管理
# --------------------------------------------------------------------------
def test_create_device_with_ranges(client, device_payload):
    response = _create_device(client, device_payload())
    assert response.status_code == 201
    body = response.get_json()
    assert body["code"] == "AQMS-100"
    assert body["station_name"] == "测试监测点"
    assert len(body["ranges"]) == 2
    assert body["status"] == "available"
    assert body["status_label"] == "可用"


def test_duplicate_device_code_conflicts(client, device_payload):
    assert _create_device(client, device_payload()).status_code == 201
    response = _create_device(client, device_payload(name="另一台设备"))
    assert response.status_code == 409


def test_device_range_min_over_max_rejected(client, device_payload):
    payload = device_payload(ranges=[
        {"pollutant": "PM25", "min_value": 900, "max_value": 10},
    ])
    response = _create_device(client, payload)
    assert response.status_code == 422
    assert "量程" in response.get_json()["error"]["message"]


def test_device_range_unknown_pollutant_rejected(client, device_payload):
    payload = device_payload(ranges=[{"pollutant": "XX", "min_value": 0, "max_value": 1}])
    response = _create_device(client, payload)
    assert response.status_code == 422


def test_update_and_delete_device(client, device_payload):
    created = _create_device(client, device_payload()).get_json()
    response = client.put("/api/devices/%d" % created["id"], json={
        "name": "改名后的分析仪", "calibration_interval_days": 365,
        "ranges": [{"pollutant": "NO2", "min_value": 0, "max_value": 800}],
    })
    assert response.status_code == 200
    body = response.get_json()
    assert body["name"] == "改名后的分析仪"
    assert body["calibration_interval_days"] == 365
    assert [item["pollutant"] for item in body["ranges"]] == ["NO2"]

    deleted = client.delete("/api/devices/%d" % created["id"])
    assert deleted.status_code == 200
    assert Device.query.count() == 0
    assert DeviceRange.query.count() == 0


def test_device_options_filtered_by_station(client, device_payload, second_station):
    _create_device(client, device_payload())
    body = client.get("/api/devices/options?station_id=%d" % second_station.id).get_json()
    assert body["items"] == []
    body_all = client.get("/api/devices/options").get_json()
    assert len(body_all["items"]) == 1


def test_device_list_status_filter_is_dynamic(client, device_payload):
    _create_device(client, device_payload())
    body = client.get("/api/devices/?status=available").get_json()
    assert body["total"] == 1
    assert client.get("/api/devices/?status=calibrating").get_json()["total"] == 0


def test_device_list_paginates_after_dynamic_status_filter(client, station, second_station, device_payload):
    for index in range(5):
        payload = device_payload(
            code="AQMS-%03d" % (200 + index),
            station_id=station.id if index % 2 == 0 else second_station.id,
        )
        assert _create_device(client, payload).status_code == 201
    page1 = client.get("/api/devices/?status=available&page=1&page_size=2").get_json()
    page2 = client.get("/api/devices/?status=available&page=2&page_size=2").get_json()
    page3 = client.get("/api/devices/?status=available&page=3&page_size=2").get_json()
    assert page1["total"] == 5
    ids = [item["id"] for item in page1["items"] + page2["items"] + page3["items"]]
    assert len(ids) == len(set(ids)) == 5


# --------------------------------------------------------------------------
# 校准管理
# --------------------------------------------------------------------------
def test_start_and_finish_calibration_flow(client, device_payload):
    device_id = _create_device(client, device_payload()).get_json()["id"]
    start = datetime(2026, 9, 10, 9, 0)

    response = client.post("/api/devices/%d/calibrations" % device_id, json={
        "started_at": "2026-09-10 09:00",
        "calibrator": "王敏",
        "organization": "市计量院",
        "note": "年度检定",
    })
    assert response.status_code == 201
    record_id = response.get_json()["id"]

    detail = client.get("/api/devices/%d" % device_id).get_json()
    assert detail["status"] == "calibrating"
    assert detail["status_label"] == "校准中"
    assert len(detail["calibrations"]) == 1

    # 同一时间窗内不能重复登记
    overlap = client.post("/api/devices/%d/calibrations" % device_id, json={
        "started_at": "2026-09-10 12:00",
    })
    assert overlap.status_code == 409

    finish = client.post("/api/devices/calibrations/%d/finish" % record_id, json={
        "finished_at": "2026-09-10 17:00",
        "result": "pass",
        "note": "示值误差合格",
    })
    assert finish.status_code == 200
    body = finish.get_json()
    assert body["device_status"] == "available"
    assert body["calibration"]["result_label"] == "合格"
    device = db.session.get(Device, device_id)
    assert device.last_calibration_at == datetime(2026, 9, 10, 17, 0)


def test_finish_calibration_rejects_early_end(client, device_payload):
    device_id = _create_device(client, device_payload()).get_json()["id"]
    record_id = client.post("/api/devices/%d/calibrations" % device_id, json={
        "started_at": "2026-09-10 09:00",
    }).get_json()["id"]
    response = client.post("/api/devices/calibrations/%d/finish" % record_id, json={
        "finished_at": "2026-09-09 10:00",
    })
    assert response.status_code == 422


def test_overdue_status_when_interval_exceeded(app, device_payload):
    with app.test_client() as client:
        device_id = _create_device(client, device_payload(
            calibration_interval_days=30,
        )).get_json()["id"]
        device = db.session.get(Device, device_id)
        device.last_calibration_at = datetime.now() - timedelta(days=45)
        db.session.commit()
        detail = client.get("/api/devices/%d" % device_id).get_json()
        assert detail["status"] == "overdue"
        assert detail["status_label"] == "校准超期"


def test_device_summary_counts_open_calibrations(client, device_payload):
    device_id = _create_device(client, device_payload()).get_json()["id"]
    client.post("/api/devices/%d/calibrations" % device_id, json={
        "started_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    summary = client.get("/api/devices/summary").get_json()
    assert summary["total"] == 1
    assert summary["open_calibrations"] == 1
    by_status = {item["key"]: item["count"] for item in summary["by_status"]}
    assert by_status["calibrating"] == 1


# --------------------------------------------------------------------------
# 设备可用性与数据有效性
# --------------------------------------------------------------------------
def test_record_during_open_calibration_is_invalid(client, station, entry_payload, device_payload):
    device_id = _create_device(client, device_payload()).get_json()["id"]
    now = datetime.now()
    client.post("/api/devices/%d/calibrations" % device_id, json={
        "started_at": (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"),
    })

    response = client.post("/api/measurements/entries", json=entry_payload(
        station.id,
        measured_at=now.strftime("%Y-%m-%d %H:%M"),
        device_id=device_id,
    ))
    assert response.status_code == 201
    body = response.get_json()
    assert body["device_unavailable"] is True
    assert body["invalid_reason"] == "calibration"
    assert body["summary"]["invalid_count"] == 3
    assert all(item["will_be_invalid"] for item in body["evaluations"])
    # 数据保留
    assert Measurement.query.filter_by(device_id=device_id).count() == 3
    assert all(not m.is_valid for m in Measurement.query.filter_by(device_id=device_id))
    record = Measurement.query.filter_by(pollutant="SO2").one()
    assert record.invalid_reason == "calibration"
    # 超标判定不受有效性影响, 超标记录照常生成
    assert record.is_exceeded is True
    assert record.exceedance is not None


def test_record_outside_calibration_is_valid(client, station, entry_payload, device_payload):
    device_id = _create_device(client, device_payload()).get_json()["id"]
    response = client.post("/api/measurements/entries", json=entry_payload(
        station.id, measured_at="2026-03-01 10:00", device_id=device_id,
    ))
    body = response.get_json()
    assert response.status_code == 201
    assert body["summary"]["invalid_count"] == 0
    assert Measurement.query.filter_by(device_id=device_id, is_valid=True).count() == 3


def test_finish_calibration_revalidates_window_data(client, station, entry_payload, device_payload):
    device_id = _create_device(client, device_payload()).get_json()["id"]
    # 录入校准窗口内、窗口外各一组数据
    client.post("/api/measurements/entries", json=entry_payload(
        station.id, measured_at="2026-09-10 12:00", device_id=device_id,
        entries=[{"pollutant": "PM25", "value": 35.0}],
    ))
    client.post("/api/measurements/entries", json=entry_payload(
        station.id, measured_at="2026-09-12 12:00", device_id=device_id,
        entries=[{"pollutant": "PM25", "value": 36.0}],
    ))

    record_id = client.post("/api/devices/%d/calibrations" % device_id, json={
        "started_at": "2026-09-10 09:00",
    }).get_json()["id"]
    # 补登"进行中"校准不追溯作废此前已录入的数据
    device = db.session.get(Device, device_id)
    device_service.revalidate_device(device)
    db.session.commit()
    windowed = Measurement.query.filter_by(measured_at=datetime(2026, 9, 10, 12, 0)).one()
    outside = Measurement.query.filter_by(measured_at=datetime(2026, 9, 12, 12, 0)).one()
    assert windowed.is_valid is True
    assert outside.is_valid is True

    finish = client.post("/api/devices/calibrations/%d/finish" % record_id, json={
        "finished_at": "2026-09-10 18:00", "result": "pass",
    })
    assert finish.status_code == 200
    # 窗口闭合后重算: 校准当日窗口内数据无效, 窗口外数据保持有效
    db.session.refresh(windowed)
    db.session.refresh(outside)
    assert windowed.is_valid is False
    assert windowed.invalid_reason == "calibration"
    assert outside.is_valid is True


def test_overdue_device_entries_are_invalid(client, station, entry_payload, device_payload):
    device_id = _create_device(client, device_payload(calibration_interval_days=30)).get_json()["id"]
    device = db.session.get(Device, device_id)
    device.last_calibration_at = datetime.now() - timedelta(days=100)
    db.session.commit()

    response = client.post("/api/measurements/entries", json=entry_payload(
        station.id,
        measured_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        device_id=device_id,
        entries=[{"pollutant": "PM25", "value": 40.0}],
    ))
    assert response.status_code == 201
    body = response.get_json()
    assert body["invalid_reason"] == "calibration_overdue"
    assert Measurement.query.one().invalid_reason == "calibration_overdue"


def test_device_must_belong_to_station(client, station, second_station, entry_payload, device_payload):
    device_id = _create_device(client, device_payload()).get_json()["id"]
    response = client.post("/api/measurements/entries", json=entry_payload(
        second_station.id, measured_at="2026-09-01 10:00", device_id=device_id,
    ))
    assert response.status_code == 422
    assert response.get_json()["error"]["fields"]["device_id"] == "station_mismatch"


def test_retired_device_cannot_start_calibration(client, device_payload):
    device_id = _create_device(client, device_payload(status="retired")).get_json()["id"]
    response = client.post("/api/devices/%d/calibrations" % device_id, json={
        "started_at": "2026-09-01 09:00",
    })
    assert response.status_code == 422


def test_device_availability_endpoint(client, device_payload):
    device_id = _create_device(client, device_payload()).get_json()["id"]
    client.post("/api/devices/%d/calibrations" % device_id, json={
        "started_at": "2026-09-10 09:00",
    })
    body = client.get(
        "/api/measurements/device-availability?device_id=%d&measured_at=2026-09-10 12:00"
        % device_id
    ).get_json()
    ctx = body["device_context"]
    assert ctx["usable"] is False
    assert ctx["invalid_reason"] == "calibration"
    assert "PM25" in ctx["ranges"]
    assert ctx["ranges"]["PM25"]["max_value"] == 1000.0


def test_out_of_range_is_warned_but_still_stored(client, station, entry_payload, device_payload):
    device_id = _create_device(client, device_payload()).get_json()["id"]
    response = client.post("/api/measurements/entries", json=entry_payload(
        station.id, measured_at="2026-03-01 10:00", device_id=device_id,
        entries=[{"pollutant": "PM25", "value": 1500.0}],
    ))
    body = response.get_json()
    assert response.status_code == 201
    assert body["out_of_range"][0]["pollutant"] == "PM25"
    assert body["out_of_range"][0]["state"] == "above"
    assert Measurement.query.filter_by(pollutant="PM25").one().value == 1500.0


def test_invalid_exceedance_is_filterable_and_flagged(client, station, entry_payload, device_payload):
    device_id = _create_device(client, device_payload()).get_json()["id"]
    now = datetime.now()
    client.post("/api/devices/%d/calibrations" % device_id, json={
        "started_at": (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"),
    })
    # 校准窗口内一条超标数据 (SO2 小时限值 500)
    client.post("/api/measurements/entries", json=entry_payload(
        station.id, measured_at=now.strftime("%Y-%m-%d %H:%M"), device_id=device_id,
        entries=[{"pollutant": "SO2", "value": 900.0}],
    ))
    invalid_list = client.get("/api/exceedances?is_valid=false").get_json()
    assert invalid_list["total"] == 1
    item = invalid_list["items"][0]
    assert item["is_valid"] is False
    assert item["invalid_reason"] == "calibration"
    valid_list = client.get("/api/exceedances?is_valid=true").get_json()
    assert valid_list["total"] == 0
