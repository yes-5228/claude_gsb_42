"""校准期无效数据在查询统计中的剔除规则测试."""
from datetime import datetime

import pytest

from app.services import device_service


@pytest.fixture
def calibrated_device(station):
    device = device_service.create_device(
        {
            "code": "DEV-PM25-CAL",
            "name": "PM2.5 分析仪",
            "station_id": station.id,
            "pollutant": "PM25",
            "measure_min": 0.0,
            "measure_max": 1000.0,
            "unit": "μg/m³",
            "location": "机柜",
            "calibration_interval_days": 180,
            "status": "in_service",
        }
    )
    device_service.create_calibration(
        device,
        {
            "started_at": datetime(2026, 9, 1, 0, 0),
            "ended_at": datetime(2026, 9, 2, 0, 0),
            "status": "in_progress",
        },
    )
    return device


def _enter(client, station_id, measured_at, value):
    return client.post(
        "/api/measurements/entries",
        json={
            "station_id": station_id,
            "measured_at": measured_at,
            "period": "daily",
            "entries": [{"pollutant": "PM25", "value": value}],
        },
    )


def test_list_default_shows_invalid_rows_with_flag(client, station, calibrated_device):
    _enter(client, station.id, "2026-09-01 10:00", 200.0)  # 校准期
    _enter(client, station.id, "2026-09-03 10:00", 60.0)   # 有效

    rows = client.get("/api/measurements").get_json()
    assert rows["total"] == 2
    by_time = {item["measured_at"][:10]: item for item in rows["items"]}
    assert by_time["2026-09-01"]["is_valid"] is False
    assert by_time["2026-09-03"]["is_valid"] is True


def test_validity_filter(client, station, calibrated_device):
    _enter(client, station.id, "2026-09-01 10:00", 200.0)
    _enter(client, station.id, "2026-09-03 10:00", 60.0)

    only_valid = client.get("/api/query/measurements?is_valid=valid").get_json()
    assert only_valid["total"] == 1
    only_invalid = client.get("/api/query/measurements?is_valid=invalid").get_json()
    assert only_invalid["total"] == 1
    assert only_invalid["items"][0]["invalid_reason"] == "calibration"


def test_summary_compliance_rate_excludes_invalid(client, station, calibrated_device):
    # 校准期内一条严重超标数据 (200), 期外一条达标 (60)
    _enter(client, station.id, "2026-09-01 10:00", 200.0)
    _enter(client, station.id, "2026-09-03 10:00", 60.0)

    summary = client.get("/api/query/measurements").get_json()["summary"]
    assert summary["total"] == 2
    assert summary["invalid_count"] == 1
    assert summary["valid_count"] == 1
    assert summary["valid_exceeded_count"] == 0
    assert summary["compliance_rate"] == 1.0


def test_statistics_exclude_invalid_by_default(client, station, calibrated_device):
    _enter(client, station.id, "2026-09-01 10:00", 200.0)
    _enter(client, station.id, "2026-09-03 10:00", 60.0)

    stats = client.get("/api/query/statistics?group_by=pollutant&metric=count").get_json()
    item = stats["items"][0]
    assert item["key"] == "PM25"
    assert item["count"] == 1
    assert item["invalid_count"] == 0
    assert item["compliance_rate"] == 1.0

    included = client.get(
        "/api/query/statistics?group_by=pollutant&metric=count&include_invalid=true"
    ).get_json()
    row = included["items"][0]
    assert row["count"] == 2
    assert row["invalid_count"] == 1
    # 达标率分母剔除校准期无效数据, 与默认口径保持一致
    assert row["valid_count"] == 1
    assert row["compliance_rate"] == 1.0


def test_export_carries_validity_columns(client, station, calibrated_device):
    _enter(client, station.id, "2026-09-01 10:00", 200.0)
    response = client.get("/api/query/export")
    text = response.get_data(as_text=True)
    header = text.splitlines()[0]
    assert "数据有效性" in header
    assert "无效" in text and "设备校准期间数据" in text
    # 默认查询导出: 导出不受统计口径限制, 无效数据保留可见
    assert len(text.strip().splitlines()) == 2
