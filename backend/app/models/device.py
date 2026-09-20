"""监测设备档案与分因子量程."""
from ..domain.constants import DEVICE_STATUS_LABELS, label_of
from ..extensions import db
from .base import TimestampMixin, iso, iso_date


class Device(TimestampMixin, db.Model):
    __tablename__ = "devices"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    model = db.Column(db.String(80))
    manufacturer = db.Column(db.String(120))
    station_id = db.Column(
        db.Integer, db.ForeignKey("stations.id", ondelete="SET NULL"), index=True
    )
    install_location = db.Column(db.String(200))
    installed_at = db.Column(db.Date)
    status = db.Column(db.String(16), nullable=False, default="available", index=True)
    calibration_interval_days = db.Column(db.Integer, nullable=False, default=365)
    last_calibration_at = db.Column(db.DateTime)
    remark = db.Column(db.Text)

    station = db.relationship("Station", backref=db.backref("devices", passive_deletes=True))
    ranges = db.relationship(
        "DeviceRange",
        back_populates="device",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    calibrations = db.relationship(
        "CalibrationRecord",
        back_populates="device",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="desc(CalibrationRecord.started_at)",
    )
    measurements = db.relationship(
        "Measurement",
        back_populates="device",
        passive_deletes=True,
    )

    def range_map(self):
        return {item.pollutant: item for item in self.ranges}

    def to_dict(self, include_ranges=False, include_calibrations=False):
        payload = {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "model": self.model,
            "manufacturer": self.manufacturer,
            "station_id": self.station_id,
            "station_name": self.station.name if self.station else None,
            "station_code": self.station.code if self.station else None,
            "area": self.station.area if self.station else None,
            "install_location": self.install_location,
            "installed_at": iso_date(self.installed_at),
            "status": self.status,
            "status_label": label_of(DEVICE_STATUS_LABELS, self.status),
            "calibration_interval_days": self.calibration_interval_days,
            "last_calibration_at": iso(self.last_calibration_at),
            "remark": self.remark,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }
        if include_ranges:
            payload["ranges"] = [item.to_dict() for item in sorted(self.ranges, key=lambda r: r.pollutant)]
        if include_calibrations:
            payload["calibrations"] = [item.to_dict() for item in self.calibrations]
        return payload

    def to_option(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "station_id": self.station_id,
            "station_name": self.station.name if self.station else None,
            "station_code": self.station.code if self.station else None,
            "status": self.status,
            "status_label": label_of(DEVICE_STATUS_LABELS, self.status),
        }

    def __repr__(self):
        return "<Device %s %s>" % (self.code, self.name)


class DeviceRange(db.Model):
    """单个监测因子的设备量程 (留空 min/max 表示该侧不限)."""

    __tablename__ = "device_ranges"
    __table_args__ = (
        db.UniqueConstraint("device_id", "pollutant", name="uq_device_pollutant_range"),
    )

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(
        db.Integer, db.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pollutant = db.Column(db.String(16), nullable=False)
    min_value = db.Column(db.Float)
    max_value = db.Column(db.Float)
    unit = db.Column(db.String(16))

    device = db.relationship("Device", back_populates="ranges")

    def to_dict(self):
        return {
            "id": self.id,
            "device_id": self.device_id,
            "pollutant": self.pollutant,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "unit": self.unit,
        }

    def __repr__(self):
        return "<DeviceRange %s %s>" % (self.device_id, self.pollutant)
