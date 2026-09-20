"""设备校准记录.

一条校准记录覆盖 [started_at, finished_at](未结束时 finished_at 为空);
落在该时间窗内的监测数据会被标记为无效, 不参与达标率统计。
"""
from ..domain.constants import CALIBRATION_RESULT_LABELS, label_of
from ..extensions import db
from .base import TimestampMixin, iso


class CalibrationRecord(TimestampMixin, db.Model):
    __tablename__ = "calibration_records"

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(
        db.Integer, db.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at = db.Column(db.DateTime, nullable=False, index=True)
    finished_at = db.Column(db.DateTime, index=True)
    result = db.Column(db.String(16))
    calibrator = db.Column(db.String(64))
    organization = db.Column(db.String(120))
    note = db.Column(db.Text)

    device = db.relationship("Device", back_populates="calibrations")

    def to_dict(self):
        return {
            "id": self.id,
            "device_id": self.device_id,
            "device_code": self.device.code if self.device else None,
            "device_name": self.device.name if self.device else None,
            "station_id": self.device.station_id if self.device else None,
            "station_name": self.device.station.name if self.device and self.device.station else None,
            "started_at": iso(self.started_at),
            "finished_at": iso(self.finished_at),
            "active": self.finished_at is None,
            "result": self.result,
            "result_label": label_of(CALIBRATION_RESULT_LABELS, self.result) if self.result else None,
            "calibrator": self.calibrator,
            "organization": self.organization,
            "note": self.note,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }

    def __repr__(self):
        return "<CalibrationRecord device=%s %s>" % (self.device_id, self.started_at)
