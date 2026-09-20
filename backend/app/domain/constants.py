"""Enumerations shared by the API layer and the frontend."""

PERIOD_LABELS = {"hourly": "小时均值", "daily": "日均值"}

DATA_SOURCE_LABELS = {"manual": "手工录入", "device": "设备上传", "import": "历史导入"}

STATION_TYPE_LABELS = {
    "ambient": "环境空气",
    "traffic": "道路交通",
    "background": "区域背景",
    "industrial": "工业园区",
    "rural": "农村站点",
}

STATION_STATUS_LABELS = {"active": "运行中", "maintenance": "维护中", "offline": "停用"}

EXCEEDANCE_LEVEL_LABELS = {"light": "轻度超标", "moderate": "中度超标", "severe": "重度超标"}

EXCEEDANCE_STATUS_LABELS = {"pending": "待标注", "confirmed": "已确认", "ignored": "已忽略"}

# 设备运行状态: 校准期间由校准记录动态判定为“不可用”, 不改变设备档案状态
DEVICE_STATUS_LABELS = {"in_service": "在用", "standby": "备用", "scrapped": "已报废"}

CALIBRATION_STATUS_LABELS = {"scheduled": "计划中", "in_progress": "校准中", "completed": "已完成", "cancelled": "已取消"}

CALIBRATION_RESULT_LABELS = {"passed": "合格", "conditional": "限用", "failed": "不合格"}

INVALID_REASON_CALIBRATING = "设备校准期间数据"
INVALID_REASON_CALIBRATION = "calibration"


def as_options(label_map):
    return [{"value": key, "label": label} for key, label in label_map.items()]


def options_payload():
    return {
        "station_type": as_options(STATION_TYPE_LABELS),
        "station_status": as_options(STATION_STATUS_LABELS),
        "period": as_options(PERIOD_LABELS),
        "data_source": as_options(DATA_SOURCE_LABELS),
        "exceedance_level": as_options(EXCEEDANCE_LEVEL_LABELS),
        "exceedance_status": as_options(EXCEEDANCE_STATUS_LABELS),
        "device_status": as_options(DEVICE_STATUS_LABELS),
        "calibration_status": as_options(CALIBRATION_STATUS_LABELS),
        "calibration_result": as_options(CALIBRATION_RESULT_LABELS),
    }


def label_of(label_map, key):
    return label_map.get(key, key)
