"""无效数据与达标率统计测试 (校准期数据排除)."""
from datetime import datetime, timedelta

from app.extensions import db
from app.models import Device, Measurement


def _make_device(client, station, **overrides):
    payload = {
        "code": "AQMS-200",
        "name": "测试分析仪",
        "station_id": station.id,
        "status": "available",
        "calibration_interval_days": 365,
        "ranges": [{"pollutant": "PM25", "min_value": 0, "max_value": 1000}],
    }
    payload.update(overrides)
    return client.post("/api/devices/", json=payload).get_json()["id"]


def _entry(client, station, measured_at, value, device_id=None, period="hourly"):
    return client.post("/api/measurements/entries", json={
        "station_id": station.id,
        "measured_at": measured_at,
        "period": period,
        "data_source": "manual",
        "device_id": device_id,
        "entries": [{"pollutant": "PM25", "value": value}],
    })


def test_compliance_rate_excludes_calibration_data(client, station):
    device_id = _make_device(client, station)
    now = datetime.now()
    client.post("/api/devices/%d/calibrations" % device_id, json={
        "started_at": (now - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M"),
    })

    # 校准窗口内: 1 条达标的无效数据 + 1 条超标的无效数据 (日均值限值 75)
    _entry(client, station, (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"),
           30.0, device_id, period="daily")
    _entry(client, station, (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M"),
           500.0, device_id, period="daily")
    # 窗口外有效数据: 3 条达标 + 1 条超标
    _entry(client, station, "2026-01-10 08:00", 30.0, device_id, period="daily")
    _entry(client, station, "2026-01-11 09:00", 31.0, device_id, period="daily")
    _entry(client, station, "2026-01-12 10:00", 32.0, device_id, period="daily")
    _entry(client, station, "2026-01-13 11:00", 200.0, device_id, period="daily")

    summary = client.get("/api/query/measurements").get_json()["summary"]
    assert summary["total"] == 6
    assert summary["invalid_count"] == 2
    assert summary["valid_count"] == 4
    assert summary["valid_exceeded_count"] == 1
    assert summary["compliant_count"] == 3
    # 达标率分母只含 4 条有效数据 => 75%
    assert summary["compliance_rate"] == 0.75


def test_is_valid_filter(client, station):
    device_id = _make_device(client, station)
    now = datetime.now()
    client.post("/api/devices/%d/calibrations" % device_id, json={
        "started_at": (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"),
    })
    _entry(client, station, now.strftime("%Y-%m-%d %H:%M"), 30.0, device_id)
    _entry(client, station, "2026-01-10 09:00", 31.0, device_id)

    only_invalid = client.get("/api/query/measurements?is_valid=false").get_json()
    assert only_invalid["total"] == 1
    assert only_invalid["items"][0]["is_valid"] is False
    assert only_invalid["items"][0]["invalid_reason_label"] == "设备校准中"

    only_valid = client.get("/api/query/measurements?is_valid=true").get_json()
    assert only_valid["total"] == 1
    assert only_valid["items"][0]["is_valid"] is True


def test_grouped_statistics_report_validity(client, station):
    device_id = _make_device(client, station)
    now = datetime.now()
    client.post("/api/devices/%d/calibrations" % device_id, json={
        "started_at": (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"),
    })
    _entry(client, station, now.strftime("%Y-%m-%d %H:%M"), 900.0, device_id, period="daily")
    _entry(client, station, "2026-01-10 09:00", 30.0, device_id, period="daily")

    body = client.get("/api/query/statistics?group_by=pollutant&metric=avg").get_json()
    item = body["items"][0]
    assert item["count"] == 2
    assert item["valid_count"] == 1
    assert item["invalid_count"] == 1
    # 有效数据全部达标 => 100%, 尽管无效数据里有一条超标
    assert item["compliance_rate"] == 1.0
    assert body["totals"]["invalid_count"] == 1


def test_measurement_dict_carries_device_and_validity(client, station):
    device_id = _make_device(client, station)
    _entry(client, station, "2026-01-10 09:00", 31.0, device_id)
    row = client.get("/api/query/measurements").get_json()["items"][0]
    assert row["device_id"] == device_id
    assert row["device_code"] == "AQMS-200"
    assert row["is_valid"] is True
    assert row["invalid_reason"] is None


def test_invalid_data_kept_when_calibration_finishes(client, station):
    device_id = _make_device(client, station)
    record_id = client.post("/api/devices/%d/calibrations" % device_id, json={
        "started_at": "2026-09-10 09:00",
    }).get_json()["id"]
    # 校准进行中录入
    _entry(client, station, "2026-09-10 12:00", 30.0, device_id)
    client.post("/api/devices/calibrations/%d/finish" % record_id, json={
        "finished_at": "2026-09-10 18:00", "result": "pass",
    })
    # 数据仍保留, 且仍标记无效
    record = Measurement.query.one()
    assert record.is_valid is False
    assert record.invalid_reason == "calibration"
    # 校准结束后新录入的数据恢复有效
    _entry(client, station, "2026-09-11 12:00", 31.0, device_id)
    fresh = Measurement.query.filter(
        Measurement.measured_at == datetime(2026, 9, 11, 12, 0)
    ).one()
    assert fresh.is_valid is True
