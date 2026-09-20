"""演示数据生成与启动引导."""
import random
from datetime import date, datetime, timedelta

from .extensions import db
from .models import CalibrationRecord, Device, DeviceRange, Exceedance, Measurement, Station

DEMO_STATIONS = [
    {
        "code": "SZ-AQ-001", "name": "市民中心站", "area": "福田区",
        "address": "福田区福中三路市民中心广场", "station_type": "ambient",
        "status": "active", "longitude": 114.0579, "latitude": 22.5410,
        "installed_at": date(2019, 5, 12), "remark": "城市环境评价点",
    },
    {
        "code": "SZ-AQ-002", "name": "华侨城站", "area": "南山区",
        "address": "南山区华侨城生态广场", "station_type": "ambient",
        "status": "active", "longitude": 113.9711, "latitude": 22.5356,
        "installed_at": date(2020, 3, 1), "remark": "城市环境评价点",
    },
    {
        "code": "SZ-AQ-003", "name": "罗湖口岸站", "area": "罗湖区",
        "address": "罗湖区火车站东广场", "station_type": "traffic",
        "status": "active", "longitude": 114.1276, "latitude": 22.5329,
        "installed_at": date(2018, 11, 20), "remark": "道路交通监测点, 早晚高峰浓度偏高",
    },
    {
        "code": "SZ-AQ-004", "name": "宝安中心站", "area": "宝安区",
        "address": "宝安区中心区宝安大道", "station_type": "ambient",
        "status": "active", "longitude": 113.8830, "latitude": 22.5551,
        "installed_at": date(2021, 6, 18), "remark": None,
    },
    {
        "code": "SZ-AQ-005", "name": "龙岗工业园站", "area": "龙岗区",
        "address": "龙岗区宝龙工业区龙岗大道", "station_type": "industrial",
        "status": "active", "longitude": 114.2465, "latitude": 22.7204,
        "installed_at": date(2019, 9, 8), "remark": "周边为工业排放源, 需重点关注 SO₂",
    },
    {
        "code": "SZ-AQ-006", "name": "梧桐山背景站", "area": "罗湖区",
        "address": "罗湖区梧桐山风景区", "station_type": "background",
        "status": "active", "longitude": 114.1837, "latitude": 22.5862,
        "installed_at": date(2017, 4, 2), "remark": "区域背景点, 用于对照评价",
    },
    {
        "code": "SZ-AQ-007", "name": "大鹏生态站", "area": "大鹏新区",
        "address": "大鹏新区葵涌街道", "station_type": "rural",
        "status": "maintenance", "longitude": 114.4798, "latitude": 22.5964,
        "installed_at": date(2022, 8, 15), "remark": "设备检修中, 计划本周恢复",
    },
    {
        "code": "SZ-AQ-008", "name": "前海自贸区站", "area": "南山区",
        "address": "南山区前海湾保税港区", "station_type": "ambient",
        "status": "offline", "longitude": 113.8980, "latitude": 22.5253,
        "installed_at": date(2023, 1, 10), "remark": "站点搬迁停用",
    },
]

POLLUTANT_BASE = {"PM25": 45.0, "PM10": 80.0, "SO2": 30.0, "NO2": 45.0, "CO": 1.5, "O3": 120.0}
HOURLY_FACTOR = {"PM25": 1.0, "PM10": 1.05, "SO2": 0.8, "NO2": 1.1, "CO": 0.9, "O3": 1.3}
STATION_FACTOR = {
    "ambient": 1.0, "traffic": 1.2, "industrial": 1.35, "background": 0.55, "rural": 0.75,
}
HOURLY_POINTS = (2, 8, 14, 20)
RECORDERS = ("李静", "王敏", "陈志强", "赵宇", "孙倩")

# 各因子演示量程上限 (与常规环境监测设备规格一致)
DEVICE_RANGE_MAX = {"PM25": 1000.0, "PM10": 2000.0, "SO2": 1000.0, "NO2": 1000.0,
                    "CO": 50.0, "O3": 1000.0}
DEVICE_RANGE_MIN = {code: 0.0 for code in DEVICE_RANGE_MAX}


def _value(pollutant, period, station_type, rng):
    base = POLLUTANT_BASE[pollutant] * STATION_FACTOR.get(station_type, 1.0)
    if period == "hourly":
        base *= HOURLY_FACTOR[pollutant]
    value = base * rng.uniform(0.72, 1.22)
    if rng.random() < 0.12:  # 少量明显超标样本, 便于演示超标标注
        value *= rng.uniform(1.8, 2.6)
    return round(value, 2 if pollutant == "CO" else 1)


def seed_devices(stations, rng):
    """为每个监测点登记一台多因子分析仪, 并安排校准记录."""
    devices = []
    now = datetime.now()
    for index, station in enumerate(stations):
        interval_days = 180
        # 最近一次合格校准, 部分设备刻意安排在较早日期以演示"校准超期"
        overdue = station.code == "SZ-AQ-004"
        days_ago = interval_days + 40 if overdue else rng.choice((30, 75, 120))
        last_done = now - timedelta(days=days_ago, hours=rng.randint(1, 5))
        device = Device(
            code="AQMS-%03d" % (index + 1),
            name="%s多因子分析仪" % station.name,
            model=rng.choice(("TH-2000", "AM-5200", "EQMS-600")),
            manufacturer=rng.choice(("先河环保", "聚光科技", "雪迪龙")),
            station_id=station.id,
            install_location="站点主站房采样平台",
            installed_at=station.installed_at,
            status="available" if station.status != "offline" else "retired",
            calibration_interval_days=interval_days,
            last_calibration_at=last_done,
            remark="六参数气态污染物与颗粒物一体分析仪",
        )
        for code, upper in DEVICE_RANGE_MAX.items():
            device.ranges.append(DeviceRange(
                pollutant=code, min_value=DEVICE_RANGE_MIN[code], max_value=upper,
            ))
        db.session.add(device)
        db.session.flush()

        # 历史校准: 上次校准的完整窗口 (持续大半天)
        db.session.add(CalibrationRecord(
            device_id=device.id,
            started_at=last_done - timedelta(hours=6),
            finished_at=last_done,
            result="pass",
            calibrator=rng.choice(RECORDERS),
            organization="市计量检测院",
            note="周期性例行校准, 示值误差合格",
        ))
        devices.append(device)

    # 市民中心站: 安排一次跨演示数据窗口的"进行中校准",
    # 期间录入的数据会自动标记为无效 (设备校准中)
    calibrating = next((item for item in devices if item.code == "AQMS-001"), devices[0])
    db.session.add(CalibrationRecord(
        device_id=calibrating.id,
        started_at=now - timedelta(days=1, hours=2),
        finished_at=None,
        calibrator="王敏",
        organization="市计量检测院",
        note="年度强制检定, 校准期间数据仅留存不参与考核",
    ))
    db.session.commit()
    return devices


def seed_demo_data(days=5, rng=None, recorder_pool=RECORDERS):
    """Generate demo stations and monitoring records through the normal service path."""
    from .services import measurement_service

    rng = rng or random.Random(20260914)
    created_stations = []
    for item in DEMO_STATIONS:
        station = Station(**item)
        db.session.add(station)
        created_stations.append(station)
    db.session.commit()

    devices = seed_devices(created_stations, rng)
    device_by_station = {device.station_id: device for device in devices}

    today = date.today()
    totals = {"stations": len(created_stations), "measurements": 0, "exceedances": 0,
              "devices": len(devices), "invalid": 0}
    for station in created_stations:
        device = device_by_station.get(station.id)
        device_id = device.id if device and station.status != "offline" else None
        for offset in range(days):
            day = today - timedelta(days=offset)
            daily_entries = [
                {"pollutant": code, "value": _value(code, "daily", station.station_type, rng)}
                for code in POLLUTANT_BASE
            ]
            result = measurement_service.record_entries(
                station_id=station.id,
                measured_at=datetime(day.year, day.month, day.day, 0, 0),
                period="daily",
                entries=daily_entries,
                data_source="device",
                recorder=rng.choice(recorder_pool),
                remark="日均值自动汇总",
                device_id=device_id,
            )
            totals["measurements"] += result["summary"]["created_count"]
            totals["exceedances"] += result["summary"]["exceeded_count"]
            totals["invalid"] += result["summary"]["invalid_count"]

            for hour in HOURLY_POINTS:
                hourly_entries = [
                    {"pollutant": code, "value": _value(code, "hourly", station.station_type, rng)}
                    for code in HOURLY_FACTOR
                ]
                result = measurement_service.record_entries(
                    station_id=station.id,
                    measured_at=datetime(day.year, day.month, day.day, hour, 0),
                    period="hourly",
                    entries=hourly_entries,
                    data_source="manual",
                    recorder=rng.choice(recorder_pool),
                    device_id=device_id,
                )
                totals["measurements"] += result["summary"]["created_count"]
                totals["exceedances"] += result["summary"]["exceeded_count"]
                totals["invalid"] += result["summary"]["invalid_count"]

    # 标注一部分超标记录, 让工作台同时存在待办与已处理记录
    from .services import exceedance_service

    exceedances = Exceedance.query.order_by(Exceedance.id.asc()).all()
    annotated = 0
    for index, record in enumerate(exceedances):
        if index % 3 == 0:
            continue
        if index % 3 == 1:
            exceedance_service.annotate(
                record, status="confirmed", note="数据经复核属实, 已通知运维排查周边排放源",
                annotator=rng.choice(recorder_pool),
            )
        else:
            exceedance_service.annotate(
                record, status="ignored", note="仪器校准期间异常值, 已在原始数据中标记无效",
                annotator=rng.choice(recorder_pool),
            )
        annotated += 1
    totals["annotated"] = annotated
    return totals


def reset_database():
    db.drop_all()
    db.create_all()


def ensure_bootstrap(app):
    """Create tables / seed demo data at startup when enabled by config."""
    auto_init = app.config.get("AUTO_INIT_DB")
    auto_seed = app.config.get("AUTO_SEED")
    if not auto_init and not auto_seed:
        return
    with app.app_context():
        try:
            if auto_init:
                db.create_all()
            if auto_seed and db.session.query(Station.id).first() is None:
                app.logger.info("seeding demo data ...")
                seed_demo_data()
        except Exception as exc:  # pragma: no cover - depends on external database
            app.logger.warning("bootstrap skipped: %s", exc)
