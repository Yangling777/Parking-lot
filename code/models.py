from datetime import datetime
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    plate_number = db.Column(db.String(20))
    role = db.Column(db.String(10), default='user')
    register_time = db.Column(db.DateTime, default=datetime.now)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class ParkingSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slot_number = db.Column(db.String(20), unique=True, nullable=False)
    status = db.Column(db.Integer, default=0)
    has_charging = db.Column(db.Boolean, default=False)
    last_updated = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

class ParkingRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    plate_number = db.Column(db.String(20), nullable=False)
    slot_number = db.Column(db.String(20))
    entry_time = db.Column(db.DateTime, default=datetime.now)
    exit_time = db.Column(db.DateTime, nullable=True)
    fee = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='正在停车')

# 🌟 新增：充电记录表
class ChargingRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    plate_number = db.Column(db.String(20), nullable=False)
    slot_number = db.Column(db.String(20))
    start_time = db.Column(db.DateTime, default=datetime.now)
    end_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='正在充电') # '正在充电' 或 '已完成'

class ModificationRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    username = db.Column(db.String(100))
    mod_type = db.Column(db.String(20))
    old_value = db.Column(db.String(255))
    new_value = db.Column(db.String(255))
    reason = db.Column(db.String(255))
    status = db.Column(db.String(20), default='待审核')
    created_at = db.Column(db.DateTime, default=datetime.now)


class ParkingPriceRule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rule_name = db.Column(db.String(50), nullable=False)
    day_start_hour = db.Column(db.Integer, default=8)
    day_end_hour = db.Column(db.Integer, default=20)
    day_rate_per_hour = db.Column(db.Float, default=5.0)
    night_rate_per_hour = db.Column(db.Float, default=3.0)
    free_minutes = db.Column(db.Integer, default=30)
    day_cap = db.Column(db.Float, default=50.0)
    night_cap = db.Column(db.Float, default=20.0)
    green_plate_discount = db.Column(db.Float, default=0.8)
    is_active = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    username = db.Column(db.String(50))
    action = db.Column(db.String(50), nullable=False)
    target = db.Column(db.String(100))
    detail = db.Column(db.String(500))
    ip_address = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)


class HardwareDevice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), unique=True, nullable=False)
    device_type = db.Column(db.String(30))
    location = db.Column(db.String(100))
    ip_address = db.Column(db.String(50))
    status = db.Column(db.String(20), default='offline')
    last_heartbeat = db.Column(db.DateTime)
    firmware_version = db.Column(db.String(20))
    registered_at = db.Column(db.DateTime, default=datetime.now)