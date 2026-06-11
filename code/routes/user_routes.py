from flask import Blueprint, jsonify, request, render_template
import re
from models import User, ParkingSlot, ParkingRecord, ChargingRecord, ModificationRequest
from extensions import db, spot_recommender, calculate_parking_fee, audit_log
from routes.auth_routes import jwt_required, optional_jwt
from datetime import datetime, timedelta

user_bp = Blueprint('user', __name__)


def format_plate_str(plate_str):
    if not plate_str: return ""
    clean = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', plate_str).upper()
    if len(clean) >= 2: return clean[:2] + '·' + clean[2:]
    return clean


def is_green_plate(plate):
    if not plate: return False
    clean_plate = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', plate)
    return len(clean_plate) == 8


def get_current_user(data=None, args=None):
    if hasattr(request, 'current_user') and request.current_user:
        return request.current_user
    user_id = None
    if data and 'user_id' in data:
        user_id = data.get('user_id')
    elif args and 'user_id' in args:
        user_id = args.get('user_id')
    if user_id:
        return User.query.get(user_id)
    return None


@user_bp.route('/user')
def user_page(): return render_template('user.html')


@user_bp.route('/simulator')
def simulator_page(): return render_template('simulator.html')


@user_bp.route('/api/user/info', methods=['GET'])
def get_user_info():
    user = get_current_user(args=request.args)
    if not user: return jsonify({"code": 401})
    return jsonify({"code": 200, "data": {"id": user.id, "username": user.username, "phone": user.phone,
                                          "plate_number": user.plate_number, "role": user.role}})


@user_bp.route('/api/user/submit_mod_request', methods=['POST'])
def submit_mod_request():
    user = get_current_user(data=request.json)
    if not user: return jsonify({"code": 401, "msg": "未登录"})
    mod_type = request.json.get('mod_type')
    new_value = request.json.get('new_value')
    reason = request.json.get('reason', '无理由')

    if mod_type == 'plate' and user.role not in ['admin', 'manager', 'test_user']:
        today = datetime.now().date()
        recent = ModificationRequest.query.filter_by(user_id=user.id, mod_type='plate').all()
        for r in recent:
            if r.created_at.date() == today:
                return jsonify({"code": 400, "msg": "普通用户一天只能申请一次车牌变更"})

    if mod_type == 'plate':
        new_plates = [format_plate_str(p) for p in new_value.split(',') if p]
        new_value = ','.join(new_plates)

    old_value = user.plate_number if mod_type == 'plate' else user.phone
    req = ModificationRequest(user_id=user.id, username=user.username, mod_type=mod_type, old_value=old_value,
                              new_value=new_value, reason=reason)
    db.session.add(req)
    db.session.commit()
    return jsonify({"code": 200, "msg": "申请已提交"})


@user_bp.route('/api/user/my_mod_requests', methods=['GET'])
def my_mod_requests():
    user = get_current_user(args=request.args)
    if not user: return jsonify({"code": 401})
    reqs = ModificationRequest.query.filter_by(user_id=user.id).order_by(ModificationRequest.id.desc()).all()
    res = [{"id": r.id, "mod_type": "车牌" if r.mod_type == 'plate' else "手机号", "new_value": r.new_value,
            "status": r.status, "created_at": r.created_at.strftime('%m-%d %H:%M')} for r in reqs]
    return jsonify({"code": 200, "data": res})


@user_bp.route('/api/user/recommend', methods=['GET'])
def get_recommendation():
    user = get_current_user(args=request.args)
    plate = request.args.get('plate', '')
    green = is_green_plate(plate)
    free = ParkingSlot.query.filter_by(status=0).all()
    available = [int(s.slot_number.split('-')[-1]) for s in free if int(s.slot_number.split('-')[-1]) >= 3]
    try:
        rec_ids = spot_recommender.recommend(user_id=user.id if user else 999, available_spots=available,
                                             is_green=green)
        res = [f"A-{i:03d}" for i in rec_ids]
    except:
        res = [f"A-{i:03d}" for i in available[:3]]
    return jsonify({"code": 200, "data": res})


@user_bp.route('/api/user/register', methods=['POST'])
def register():
    data = request.json
    if User.query.filter_by(phone=data['phone']).first():
        return jsonify({"code": 400, "msg": "手机号已被注册"})
    fmt_plate = format_plate_str(data.get('plate', ''))
    new_user = User(username=data['username'], phone=data['phone'], plate_number=fmt_plate, role='pending_user')
    new_user.set_password(data['password'])
    db.session.add(new_user)
    db.session.commit()
    audit_log(new_user.id, new_user.username, 'REGISTER', new_user.phone, '新用户注册', request.remote_addr)
    return jsonify({"code": 200, "msg": "注册资料已提交，请等待管理员审批"})


@user_bp.route('/api/user/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(phone=data['phone']).first()
    if user and user.check_password(data['password']):
        if user.role == 'pending_user':
            return jsonify({"code": 403, "msg": "您的注册申请正在审核中"})
        from extensions import create_jwt_token, create_refresh_token
        access_token = create_jwt_token(user.id, user.username, user.role)
        refresh_token = create_refresh_token(user.id)
        audit_log(user.id, user.username, 'LOGIN', '', '用户登录', request.remote_addr)
        return jsonify({"code": 200,
                        "data": {"id": user.id, "username": user.username,
                                 "plate_number": user.plate_number, "role": user.role,
                                 "access_token": access_token, "refresh_token": refresh_token}})
    return jsonify({"code": 401, "msg": "账号或密码错误"})


@user_bp.route('/api/user/change_password', methods=['POST'])
def change_password():
    user = get_current_user(data=request.json)
    if not user.check_password(request.json.get('old_password')): return jsonify({"code": 400, "msg": "原密码验证失败"})
    user.set_password(request.json.get('new_password'))
    db.session.commit()
    return jsonify({"code": 200, "msg": "密码修改成功"})


@user_bp.route('/api/user/update_plates', methods=['POST'])
def update_plates():
    user = get_current_user(data=request.json)
    user.plate_number = request.json.get('plates', '')
    db.session.commit()
    return jsonify({"code": 200, "msg": "更新成功"})


@user_bp.route('/api/user/reserve', methods=['POST'])
def user_reserve():
    user = get_current_user(data=request.json)
    slot_number = request.json.get('slot_number')
    plate = request.json.get('plate', '')
    slot = ParkingSlot.query.filter_by(slot_number=slot_number).first()
    if slot and slot.status == 0:
        slot.status = 2
        db.session.add(
            ParkingRecord(user_id=user.id, plate_number=plate, slot_number=slot.slot_number, status='已预约'))
        db.session.commit()
        if user:
            audit_log(user.id, user.username, 'RESERVE', slot_number, f"预约车位 车牌{plate}", request.remote_addr)
        return jsonify({"code": 200})
    return jsonify({"code": 400})


@user_bp.route('/api/user/cancel_reserve', methods=['POST'])
def cancel_reserve():
    record = ParkingRecord.query.get(request.json.get('record_id'))
    if record:
        record.status = '已取消'
        slot = ParkingSlot.query.filter_by(slot_number=record.slot_number).first()
        if slot: slot.status = 0
        db.session.commit()
    return jsonify({"code": 200})


@user_bp.route('/api/user/my_records', methods=['GET'])
def get_my_records():
    user = get_current_user(args=request.args)
    records = ParkingRecord.query.filter_by(user_id=user.id).order_by(ParkingRecord.id.desc()).all()
    res = [{"id": r.id, "slot": r.slot_number, "plate": r.plate_number, "fee": r.fee, "status": r.status,
            "entry": r.entry_time.strftime('%H:%M'), "exit": r.exit_time.strftime('%H:%M') if r.exit_time else "",
            "has_charging": (3 <= int(r.slot_number.split('-')[1]) <= 22)} for r in records]
    return jsonify({"code": 200, "data": res})


@user_bp.route('/api/user/pay', methods=['POST'])
def pay_order():
    record = ParkingRecord.query.get(request.json['record_id'])
    if record:
        record.status = '已支付'
        db.session.commit()
        user = get_current_user(data=request.json)
        if user:
            audit_log(user.id, user.username, 'PAY', record.plate_number, f"支付 ¥{record.fee}", request.remote_addr)
    return jsonify({"code": 200})


@user_bp.route('/api/user/start_charge', methods=['POST'])
def start_charge():
    user = get_current_user(data=request.json)
    active = ParkingRecord.query.filter_by(user_id=user.id, status='正在停车').first()
    if active: db.session.add(ChargingRecord(user_id=user.id, plate_number=active.plate_number,
                                             slot_number=active.slot_number)); db.session.commit()
    return jsonify({"code": 200})


@user_bp.route('/api/user/stop_charge', methods=['POST'])
def stop_charge():
    user = get_current_user(data=request.json)
    active = ChargingRecord.query.filter_by(user_id=user.id, status='正在充电').first()
    if active: active.end_time, active.status = datetime.now(), '已完成'; db.session.commit()
    return jsonify({"code": 200})


@user_bp.route('/api/user/my_charging_records', methods=['GET'])
def my_charging_records():
    user = get_current_user(args=request.args)
    recs = ChargingRecord.query.filter_by(user_id=user.id).order_by(ChargingRecord.id.desc()).all()
    res = [{"id": r.id, "slot": r.slot_number, "start": r.start_time.strftime('%H:%M'),
            "duration": "充电中" if not r.end_time else "完成", "status": r.status} for r in recs]
    return jsonify({"code": 200, "data": res})


# =========================================================================
# 🌟 以下是专供 simulator 硬件模拟器的物理级接口 (包含出入场、底层时间修改、充电控制)
# =========================================================================

@user_bp.route('/api/simulator/entry', methods=['POST'])
def sim_entry():
    slot_number = request.json.get('slot_number')
    plate = request.json.get('plate')
    slot = ParkingSlot.query.filter_by(slot_number=slot_number).first()
    if not slot or slot.status != 0: return jsonify({"code": 400, "msg": "车位不可用"})
    if 3 <= int(slot.slot_number.split('-')[1]) <= 22 and not is_green_plate(plate):
        return jsonify({"code": 400, "msg": "A区限绿牌"})
    user = User.query.filter(User.plate_number.like(f'%{plate}%')).first()
    db.session.add(ParkingRecord(user_id=user.id if user else None, plate_number=plate, slot_number=slot.slot_number,
                                 status='正在停车'))
    slot.status = 1
    db.session.commit()
    return jsonify({"code": 200, "msg": "已入场"})


@user_bp.route('/api/simulator/sync_time', methods=['POST'])
def sync_time():
    slot_number = request.json.get('slot_number')
    manual_hours = float(request.json.get('manual_hours', 0))
    record = ParkingRecord.query.filter_by(slot_number=slot_number, status='正在停车').first()
    if record:
        record.entry_time = datetime.now() - timedelta(hours=manual_hours)
        db.session.commit()
    return jsonify({"code": 200, "msg": "同步成功"})


@user_bp.route('/api/simulator/exit', methods=['POST'])
def sim_exit():
    slot_number = request.json.get('slot_number')
    record = ParkingRecord.query.filter_by(slot_number=slot_number, status='正在停车').first()
    if not record:
        return jsonify({"code": 400, "msg": "无车"})
    slot = ParkingSlot.query.filter_by(slot_number=slot_number).first()
    if slot:
        slot.status = 0
    record.exit_time = datetime.now()
    green = is_green_plate(record.plate_number) if record.plate_number else False
    record.fee = calculate_parking_fee(record.entry_time, record.exit_time, is_green=green)
    record.status = '待支付' if record.fee > 0 else '已支付'
    db.session.commit()
    audit_log(record.user_id, '', 'SIM_EXIT', record.plate_number, f"费用 ¥{record.fee}", request.remote_addr)
    return jsonify({"code": 200, "data": {"fee": record.fee, "plate": record.plate_number, "record_id": record.id}})


# 🌟 新增：模拟器充电控制全套接口
@user_bp.route('/api/simulator/start_charge', methods=['POST'])
def sim_start_charge():
    slot_number = request.json.get('slot_number')
    active_park = ParkingRecord.query.filter_by(slot_number=slot_number, status='正在停车').first()
    if not active_park: return jsonify({"code": 400, "msg": "车位未停车"})
    db.session.add(
        ChargingRecord(user_id=active_park.user_id, plate_number=active_park.plate_number, slot_number=slot_number))
    db.session.commit()
    return jsonify({"code": 200, "msg": "充电物理插枪成功，开始充电"})


@user_bp.route('/api/simulator/sync_charge_time', methods=['POST'])
def sim_sync_charge():
    slot_number = request.json.get('slot_number')
    manual_hours = float(request.json.get('manual_hours', 0))
    record = ChargingRecord.query.filter_by(slot_number=slot_number, status='正在充电').first()
    if record:
        record.start_time = datetime.now() - timedelta(hours=manual_hours)
        db.session.commit()
        return jsonify({"code": 200, "msg": "底层充电时间已修改"})
    return jsonify({"code": 400, "msg": "未找到充电记录"})


@user_bp.route('/api/simulator/stop_charge', methods=['POST'])
def sim_stop_charge():
    slot_number = request.json.get('slot_number')
    record = ChargingRecord.query.filter_by(slot_number=slot_number, status='正在充电').first()
    if not record: return jsonify({"code": 400, "msg": "无充电记录"})

    record.end_time = datetime.now()
    record.status = '待支付'
    # 物理模拟计费：这里简单设为 1.5元/小时 电费
    hours = (record.end_time - record.start_time).total_seconds() / 3600.0
    fee = round(hours * 1.5, 2)
    db.session.commit()
    return jsonify({"code": 200, "data": {"fee": fee, "plate": record.plate_number, "record_id": record.id}})


@user_bp.route('/api/simulator/pay_charge', methods=['POST'])
def sim_pay_charge():
    record = ChargingRecord.query.get(request.json.get('record_id'))
    if record:
        record.status = '已完成'
        db.session.commit()
        return jsonify({"code": 200, "msg": "充电费支付完成"})
    return jsonify({"code": 400, "msg": "支付失败"})