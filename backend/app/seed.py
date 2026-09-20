"""演示数据生成与启动引导."""
import random
from datetime import date, datetime, timedelta

from .extensions import db
from .models import CalibrationRecord, Device, Exceedance, Station

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

# 每个监测点登记的监测设备 (多参数一体机按因子拆分台账, 便于单独校准)
DEVICE_POLLUTANTS = ("PM25", "PM10", "SO2", "NO2", "CO", "O3")
DEVICE_META = {
    "PM25": ("聚光科技", "AQMS-503", (0.0, 1000.0), 180),
    "PM10": ("聚光科技", "AQMS-504", (0.0, 2000.0), 180),
    "SO2": ("赛默飞", "43i", (0.0, 1000.0), 365),
    "NO2": ("赛默飞", "42i", (0.0, 500.0), 365),
    "CO": ("赛默飞", "48i", (0.0, 50.0), 365),
    "O3": ("赛默飞", "49i", (0.0, 1000.0), 365),
}
POLLUTANT_LOCATION = {
    "PM25": "站房顶部采样总管 1 号位",
    "PM10": "站房顶部采样总管 2 号位",
    "SO2": "站房分析间机柜 A 列",
    "NO2": "站房分析间机柜 A 列",
    "CO": "站房分析间机柜 B 列",
    "O3": "站房分析间机柜 B 列",
}


def _value(pollutant, period, station_type, rng):
    base = POLLUTANT_BASE[pollutant] * STATION_FACTOR.get(station_type, 1.0)
    if period == "hourly":
        base *= HOURLY_FACTOR[pollutant]
    value = base * rng.uniform(0.72, 1.22)
    if rng.random() < 0.12:  # 少量明显超标样本, 便于演示超标标注
        value *= rng.uniform(1.8, 2.6)
    return round(value, 2 if pollutant == "CO" else 1)


def _seed_devices(created_stations, today, rng):
    """登记设备档案与校准记录, 并制造校准窗口以演示无效数据与录入提示."""
    device_count = 0
    calibration_count = 0
    # 校准窗口: 覆盖昨天整日 (当日录入数据将标记无效) + 今天正在进行的校准
    cal_day = today - timedelta(days=1)
    for index, station in enumerate(created_stations):
        if station.status == "offline":
            continue
        for code in DEVICE_POLLUTANTS:
            manufacturer, model_name, (dmin, dmax), interval = DEVICE_META[code]
            device = Device(
                code="%s-%s" % (station.code.replace("SZ-", ""), code),
                name="%s %s 分析仪" % (station.name, dict(PM25="PM2.5", PM10="PM10", SO2="SO₂",
                                                          NO2="NO₂", CO="CO", O3="O₃")[code]),
                station_id=station.id,
                pollutant=code,
                manufacturer=manufacturer,
                model=model_name,
                serial_no="SN%s%03d" % (code, index + 1),
                measure_min=dmin,
                measure_max=dmax,
                unit="mg/m³" if code == "CO" else "μg/m³",
                location=POLLUTANT_LOCATION[code],
                calibration_interval_days=interval,
                status="in_service" if station.status == "active" else "standby",
                installed_at=station.installed_at,
                remark=None,
            )
            db.session.add(device)
            db.session.flush()
            device_count += 1

            # 一条已完成的历史校准 (90 天前, 合格)
            past_start = datetime.combine(today - timedelta(days=90), datetime.min.time()).replace(hour=9)
            db.session.add(
                CalibrationRecord(
                    device_id=device.id,
                    started_at=past_start,
                    ended_at=past_start + timedelta(hours=3),
                    status="completed",
                    result="passed",
                    agency="深圳市计量质量检测研究院",
                    operator=rng.choice(RECORDERS),
                    certificate_no="CAL-2026-%04d" % calibration_count,
                    note="周期校准, 示值误差在允许范围内",
                    completed_at=past_start + timedelta(hours=3),
                )
            )
            calibration_count += 1

            # 市民中心站 PM2.5: 昨天整日校准 -> 该日 PM2.5 数据无效; 今天仍在校准中
            if station.code == "SZ-AQ-001" and code == "PM25":
                db.session.add(
                    CalibrationRecord(
                        device_id=device.id,
                        started_at=datetime.combine(cal_day, datetime.min.time()),
                        ended_at=datetime.combine(today, datetime.min.time()) + timedelta(hours=12),
                        status="in_progress",
                        agency="深圳市计量质量检测研究院",
                        operator=rng.choice(RECORDERS),
                        note="零点 / 跨度校准, 校准期间数据仅留存不参与达标统计",
                    )
                )
                calibration_count += 1
    db.session.commit()
    return {"devices": device_count, "calibrations": calibration_count}


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

    today = date.today()
    device_totals = _seed_devices(created_stations, today, rng)
    totals = {
        "stations": len(created_stations),
        "devices": device_totals["devices"],
        "calibrations": device_totals["calibrations"],
        "measurements": 0,
        "exceedances": 0,
    }
    for station in created_stations:
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
            )
            totals["measurements"] += result["summary"]["created_count"]
            totals["exceedances"] += result["summary"]["exceeded_count"]

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
                )
                totals["measurements"] += result["summary"]["created_count"]
                totals["exceedances"] += result["summary"]["exceeded_count"]

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
