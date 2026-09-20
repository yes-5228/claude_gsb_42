"""监测设备档案 (量程 / 安装位置 / 校准周期)."""
from ..domain.constants import DEVICE_STATUS_LABELS, label_of
from ..extensions import db
from .base import TimestampMixin, iso, iso_date


class Device(TimestampMixin, db.Model):
    __tablename__ = "devices"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    station_id = db.Column(
        db.Integer, db.ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pollutant = db.Column(db.String(16), nullable=False, index=True)
    manufacturer = db.Column(db.String(120))
    model = db.Column(db.String(64))
    serial_no = db.Column(db.String(64))
    measure_min = db.Column(db.Float)
    measure_max = db.Column(db.Float)
    unit = db.Column(db.String(16))
    location = db.Column(db.String(200))
    calibration_interval_days = db.Column(db.Integer, nullable=False, default=365)
    status = db.Column(db.String(16), nullable=False, default="in_service", index=True)
    installed_at = db.Column(db.Date)
    remark = db.Column(db.Text)

    station = db.relationship("Station", back_populates="devices")
    calibrations = db.relationship(
        "CalibrationRecord",
        back_populates="device",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CalibrationRecord.started_at.desc()",
    )
    measurements = db.relationship("Measurement", back_populates="device")

    def pollutant_label(self):
        from ..domain.standards import get_pollutant

        meta = get_pollutant(self.pollutant)
        return meta["label"] if meta else self.pollutant

    def to_dict(self, include_status=False, include_calibrations=False, station=None):
        payload = {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "station_id": self.station_id,
            "station_name": station.name if station else (self.station.name if self.station else None),
            "station_code": station.code if station else (self.station.code if self.station else None),
            "pollutant": self.pollutant,
            "pollutant_label": self.pollutant_label(),
            "manufacturer": self.manufacturer,
            "model": self.model,
            "serial_no": self.serial_no,
            "measure_min": self.measure_min,
            "measure_max": self.measure_max,
            "unit": self.unit,
            "location": self.location,
            "calibration_interval_days": self.calibration_interval_days,
            "status": self.status,
            "status_label": label_of(DEVICE_STATUS_LABELS, self.status),
            "installed_at": iso_date(self.installed_at),
            "remark": self.remark,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }
        if include_status:
            payload["runtime"] = self.runtime_status()
        if include_calibrations:
            payload["calibrations"] = [item.to_dict() for item in self.calibrations]
        return payload

    def to_option(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "station_id": self.station_id,
            "pollutant": self.pollutant,
            "pollutant_label": self.pollutant_label(),
        }

    def active_calibration(self, at=None):
        """Return the in-progress calibration window covering ``at`` (default now)."""
        from datetime import datetime

        at = at or datetime.now()
        for item in self.calibrations:
            if item.status == "in_progress" and item.started_at <= at and item.ended_at >= at:
                return item
        return None

    def is_available(self, at=None):
        if self.status == "scrapped":
            return False
        return self.active_calibration(at) is None

    def next_due_date(self):
        """Next calibration due date: interval after the latest completed calibration."""
        from datetime import timedelta

        if not self.calibration_interval_days:
            return None
        latest = None
        for item in self.calibrations:
            if item.status == "completed" and (latest is None or item.ended_at > latest):
                latest = item.ended_at
        if latest is None:
            if self.installed_at is None:
                return None
            base = self.installed_at
            return base + timedelta(days=self.calibration_interval_days)
        return latest.date() + timedelta(days=self.calibration_interval_days)

    def runtime_status(self, at=None):
        """Dynamic availability used by list views and the entry form."""
        calibration = self.active_calibration(at)
        if self.status == "scrapped":
            return {
                "available": False,
                "state": "scrapped",
                "state_label": "已报废",
                "calibration": None,
            }
        if calibration is not None:
            return {
                "available": False,
                "state": "calibrating",
                "state_label": "校准中·不可用",
                "calibration": calibration.to_dict(),
            }
        if self.status == "standby":
            return {"available": True, "state": "standby", "state_label": "备用", "calibration": None}
        return {"available": True, "state": "in_service", "state_label": "可用", "calibration": None}

    def __repr__(self):
        return "<Device %s %s>" % (self.code, self.pollutant)
