"""设备校准记录 (校准期间设备不可用, 该时段录入的监测数据标记为无效)."""
from ..domain.constants import (
    CALIBRATION_RESULT_LABELS,
    CALIBRATION_STATUS_LABELS,
    label_of,
)
from ..extensions import db
from .base import TimestampMixin, iso


class CalibrationRecord(TimestampMixin, db.Model):
    __tablename__ = "calibration_records"
    __table_args__ = (
        db.Index("ix_calibration_device_time", "device_id", "started_at", "ended_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(
        db.Integer,
        db.ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    started_at = db.Column(db.DateTime, nullable=False, index=True)
    ended_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="scheduled", index=True)
    result = db.Column(db.String(16))
    agency = db.Column(db.String(120))
    operator = db.Column(db.String(64))
    certificate_no = db.Column(db.String(64))
    note = db.Column(db.Text)
    completed_at = db.Column(db.DateTime)

    device = db.relationship("Device", back_populates="calibrations")

    def covers(self, measured_at):
        return self.started_at <= measured_at <= self.ended_at

    def to_dict(self):
        return {
            "id": self.id,
            "device_id": self.device_id,
            "started_at": iso(self.started_at),
            "ended_at": iso(self.ended_at),
            "status": self.status,
            "status_label": label_of(CALIBRATION_STATUS_LABELS, self.status),
            "result": self.result,
            "result_label": label_of(CALIBRATION_RESULT_LABELS, self.result) if self.result else None,
            "agency": self.agency,
            "operator": self.operator,
            "certificate_no": self.certificate_no,
            "note": self.note,
            "completed_at": iso(self.completed_at),
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
            "device_code": self.device.code if self.device else None,
            "device_name": self.device.name if self.device else None,
            "station_id": self.device.station_id if self.device else None,
        }

    def __repr__(self):
        return "<CalibrationRecord device=%s %s~%s %s>" % (
            self.device_id, self.started_at, self.ended_at, self.status
        )
