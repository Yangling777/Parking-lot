from flask import Blueprint, jsonify, request, render_template
import random
import re
from datetime import datetime

from models import User, ParkingSlot, ParkingRecord, ChargingRecord, ModificationRequest, ParkingPriceRule, AuditLog, HardwareDevice
from extensions import db, sim_config, calculate_parking_fee, calculate_parking_fee_simple, add_log, audit_log, get_active_price_rule
from routes.auth_routes import jwt_required, admin_required

admin_bp = Blueprint('admin', __name__)


def is_green_plate(plate):
    if not plate:
        return False
    clean_plate = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', plate)
    return len(clean_plate) == 8


@admin_bp.route('/admin')
def admin_page():
    return render_template('admin.html')


@admin_bp.route('/api/admin/user/approve', methods=['POST'])
def approve_user():
    user = User.query.get(request.json['id'])
    if user and user.role == 'pending_user':
        user.role = 'user'
        db.session.commit()
        audit_log(user.id, user.username, 'APPROVE_USER', '', '管理员审批通过注册', request.remote_addr)
        return jsonify({"code": 200, "msg": "注册审批已通过"})
    return jsonify({"code": 400, "msg": "操作失败，可能已被处理"})


@admin_bp.route('/api/admin/mod_requests', methods=['GET'])
def get_mod_requests():
    reqs = ModificationRequest.query.order_by(ModificationRequest.id.desc()).all()
    res = [{"id": r.id, "username": r.username, "mod_type": "车牌" if r.mod_type == 'plate' else "手机号",
            "old_value": r.old_value, "new_value": r.new_value, "reason": r.reason, "status": r.status,
            "created_at": r.created_at.strftime('%Y-%m-%d %H:%M')} for r in reqs]
    return jsonify({"code": 200, "data": res})


@admin_bp.route('/api/admin/handle_mod_request', methods=['POST'])
def handle_mod_request():
    req_id = request.json.get('req_id')
    action = request.json.get('action')
    mod_req = ModificationRequest.query.get(req_id)

    if not mod_req or mod_req.status != '待审核':
        return jsonify({"code": 400, "msg": "请求不存在或已被处理"})

    if action == 'approve':
        user = User.query.get(mod_req.user_id)
        if user:
            if mod_req.mod_type == 'plate':
                user.plate_number = mod_req.new_value
            elif mod_req.mod_type == 'phone':
                user.phone = mod_req.new_value
        mod_req.status = '已同意'
        audit_log(mod_req.user_id, mod_req.username, 'MOD_APPROVE',
                  f"{mod_req.mod_type}:{mod_req.old_value}→{mod_req.new_value}", '通过', request.remote_addr)
    else:
        mod_req.status = '已拒绝'
        audit_log(mod_req.user_id, mod_req.username, 'MOD_REJECT',
                  f"{mod_req.mod_type}:{mod_req.old_value}→{mod_req.new_value}", '拒绝', request.remote_addr)

    db.session.commit()
    return jsonify({"code": 200, "msg": "处理成功，已下发通知给用户"})


@admin_bp.route('/api/admin/dashboard', methods=['GET'])
def get_dashboard():
    slots = ParkingSlot.query.all()
    slot_list = [{"id": s.id, "slot_number": s.slot_number, "status": s.status,
                  "has_charging": s.has_charging} for s in slots]
    today = datetime.now().date()
    today_records = ParkingRecord.query.filter(
        ParkingRecord.entry_time >= datetime(today.year, today.month, today.day),
        ParkingRecord.status.in_(['已支付', '人工已结清', '一键清空(已放行)'])
    ).all()
    today_revenue = sum(r.fee or 0 for r in today_records)

    predict_trend = [random.randint(40, 50), random.randint(50, 70), random.randint(75, 95),
                     random.randint(60, 80), random.randint(40, 50), random.randint(20, 35),
                     random.randint(10, 20)]

    return jsonify({
        "code": 200,
        "data": {
            "total": len(slots),
            "free": sum(1 for s in slots if s.status == 0),
            "occupied": sum(1 for s in slots if s.status == 1),
            "reserved": sum(1 for s in slots if s.status == 2),
            "slots": slot_list,
            "predict_trend": predict_trend,
            "today_revenue": round(today_revenue, 2),
            "occupancy_rate": round(sum(1 for s in slots if s.status == 1) / max(len(slots), 1) * 100, 1)
        }
    })


@admin_bp.route('/api/admin/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify({"code": 200, "data": [
        {"id": u.id, "username": u.username, "phone": u.phone, "plate": u.plate_number,
         "role": u.role, "register_time": u.register_time.strftime('%Y-%m-%d %H:%M') if u.register_time else ''}
        for u in users]})


@admin_bp.route('/api/admin/user/update', methods=['POST'])
def update_user():
    data = request.json
    if data.get('id'):
        user = User.query.get(data['id'])
        user.username, user.phone, user.plate_number, user.role = (
            data.get('username'), data.get('phone'), data.get('plate'), data.get('role')
        )
        if data.get('password'):
            user.set_password(data['password'])
    else:
        user = User(username=data['username'], phone=data['phone'], plate_number=data['plate'], role=data['role'])
        user.set_password(data.get('password', '123456'))
        db.session.add(user)
    db.session.commit()
    audit_log(data.get('id'), data.get('username', ''), 'USER_UPDATE', str(data.get('id', 'new')), '管理员更新用户信息',
              request.remote_addr)
    return jsonify({"code": 200, "msg": "操作成功"})


@admin_bp.route('/api/admin/user/delete', methods=['POST'])
def delete_user():
    user = User.query.get(request.json['id'])
    if user:
        audit_log(user.id, user.username, 'USER_DELETE', str(user.id), '管理员删除用户', request.remote_addr)
        db.session.delete(user)
        db.session.commit()
    return jsonify({"code": 200, "msg": "删除成功"})


@admin_bp.route('/api/admin/records', methods=['GET'])
def get_records():
    records = ParkingRecord.query.order_by(ParkingRecord.id.desc()).limit(100).all()
    return jsonify({"code": 200, "data": [
        {"id": r.id, "plate": r.plate_number, "slot": r.slot_number,
         "entry": r.entry_time.strftime('%Y-%m-%d %H:%M:%S') if r.entry_time else "",
         "exit": r.exit_time.strftime('%Y-%m-%d %H:%M:%S') if r.exit_time else "",
         "fee": r.fee, "status": r.status} for r in records]})


@admin_bp.route('/api/admin/charging_records', methods=['GET'])
def get_charging_records():
    records = ChargingRecord.query.order_by(ChargingRecord.id.desc()).limit(50).all()
    res = []
    for r in records:
        duration_str = "充电中..."
        if r.end_time:
            seconds = (r.end_time - r.start_time).total_seconds()
            duration_str = f"{int(seconds // 60)}分 {int(seconds % 60)}秒"
        res.append({"id": r.id, "plate": r.plate_number, "slot": r.slot_number,
                    "start": r.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "end": r.end_time.strftime('%Y-%m-%d %H:%M:%S') if r.end_time else "",
                    "duration": duration_str, "status": r.status})
    return jsonify({"code": 200, "data": res})


@admin_bp.route('/api/admin/audit_logs', methods=['GET'])
def get_audit_logs():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    query = AuditLog.query.order_by(AuditLog.id.desc())
    total = query.count()
    logs = query.offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({
        "code": 200,
        "data": {
            "total": total, "page": page, "per_page": per_page,
            "items": [{"id": l.id, "username": l.username, "action": l.action,
                       "target": l.target, "detail": l.detail,
                       "ip_address": l.ip_address,
                       "time": l.created_at.strftime('%Y-%m-%d %H:%M:%S') if l.created_at else ''}
                      for l in logs]
        }
    })


@admin_bp.route('/api/admin/unplated_entry', methods=['POST'])
def unplated_entry():
    slot_number = request.json.get('slot')
    slot = ParkingSlot.query.filter_by(slot_number=slot_number).first()
    if not slot or slot.status != 0:
        return jsonify({"code": 400, "msg": "该车位不可用"})

    slot_num = int(slot.slot_number.split('-')[1])
    if 3 <= slot_num <= 22:
        return jsonify({"code": 400, "msg": "拦截：A区为绿牌充电专属，无牌车请分配至 B~E 物理区！"})

    plate = f"无牌车-{random.randint(1000, 9999)}"
    slot.status = 1
    db.session.add(ParkingRecord(plate_number=plate, slot_number=slot.slot_number, status='正在停车'))
    db.session.commit()
    audit_log(None, '管理员', 'UNPLATED_ENTRY', plate, f"车位 {slot_number}", request.remote_addr)
    return jsonify({"code": 200, "msg": f"已抬杆放行，系统自动分配临时编号：{plate}"})


@admin_bp.route('/api/admin/pre_exit', methods=['POST'])
def pre_exit():
    slot_number = request.json.get('slot')
    record = ParkingRecord.query.filter_by(slot_number=slot_number, status='正在停车').first()
    if not record:
        return jsonify({"code": 400, "msg": "未找到在停车辆"})

    plate = record.plate_number
    green = is_green_plate(plate) if plate else False
    fee = calculate_parking_fee(record.entry_time, datetime.now(), is_green=green)
    return jsonify({
        "code": 200,
        "data": {
            "record_id": record.id, "plate": record.plate_number,
            "entry_time": record.entry_time.strftime('%Y-%m-%d %H:%M:%S'), "fee": fee
        }
    })


@admin_bp.route('/api/admin/manual_entry', methods=['POST'])
def manual_entry():
    slot = ParkingSlot.query.filter_by(slot_number=request.json.get('slot')).first()
    if not slot or slot.status != 0:
        return jsonify({"code": 400, "msg": "不可用"})
    plate = request.json.get('plate', '')
    slot_num = int(slot.slot_number.split('-')[1])
    if 3 <= slot_num <= 22 and not is_green_plate(plate):
        return jsonify({"code": 400, "msg": "A区为新能源专属充电区，违规车辆禁止驶入！(须8位绿牌)"})
    slot.status = 1
    db.session.add(ParkingRecord(plate_number=plate, slot_number=slot.slot_number, status='正在停车'))
    db.session.commit()
    audit_log(None, '管理员', 'MANUAL_ENTRY', plate, f"车位 {slot.slot_number}", request.remote_addr)
    return jsonify({"code": 200, "msg": "已放行"})


@admin_bp.route('/api/admin/manual_exit', methods=['POST'])
def manual_exit():
    record = ParkingRecord.query.get(request.json.get('record_id'))
    if record:
        slot = ParkingSlot.query.filter_by(slot_number=record.slot_number).first()
        if slot:
            slot.status = 0
        record.exit_time = datetime.now()
        green = is_green_plate(record.plate_number) if record.plate_number else False
        record.fee = calculate_parking_fee(record.entry_time, record.exit_time, is_green=green)
        record.status = '人工已结清'
        db.session.commit()
        audit_log(None, '管理员', 'MANUAL_EXIT', record.plate_number, f"费用 ¥{record.fee}", request.remote_addr)
    return jsonify({"code": 200, "msg": "已放行"})


@admin_bp.route('/api/admin/slot_details', methods=['POST'])
def get_slot_details():
    slot_number = request.json.get('slot_number')
    records = ParkingRecord.query.filter_by(slot_number=slot_number).order_by(ParkingRecord.id.desc()).limit(20).all()
    res = []
    for r in records:
        res.append({
            "plate": r.plate_number,
            "entry": r.entry_time.strftime('%H:%M'),
            "exit": r.exit_time.strftime('%H:%M') if r.exit_time else "-",
            "duration": "已完成" if r.exit_time else "停车中",
            "charge_info": "无", "status": r.status
        })
    return jsonify({"code": 200, "data": res})


@admin_bp.route('/api/admin/update_simulation', methods=['POST'])
def update_simulation():
    data = request.json
    sim_config.update({
        "is_running": data.get("is_running", True),
        "min_interval": int(data.get("min_interval", 5)),
        "max_interval": int(data.get("max_interval", 15)),
        "entry_probability": float(data.get("entry_probability", 0.5))
    })
    return jsonify({"code": 200, "msg": "参数已更新"})


@admin_bp.route('/api/admin/clear_all', methods=['POST'])
def clear_all():
    records = ParkingRecord.query.filter(ParkingRecord.status.in_(['正在停车', '待支付'])).all()
    for r in records:
        r.exit_time = datetime.now()
        green = is_green_plate(r.plate_number) if r.plate_number else False
        r.fee = calculate_parking_fee(r.entry_time, r.exit_time, is_green=green)
        r.status = '一键清空(已放行)'
    slots = ParkingSlot.query.filter(ParkingSlot.status != 0).all()
    for s in slots:
        s.status = 0
    db.session.commit()
    add_log("管理员执行一键清空，所有在停车辆已放行", "warn")
    audit_log(None, '管理员', 'CLEAR_ALL', '', '一键清空所有车辆', request.remote_addr)
    return jsonify({"code": 200, "msg": "已强制清空放行"})


@admin_bp.route('/api/admin/price_rules', methods=['GET'])
def get_price_rules():
    rules = ParkingPriceRule.query.order_by(ParkingPriceRule.id.asc()).all()
    if not rules:
        return jsonify({"code": 200, "data": [get_active_price_rule()], "from_db": False})
    return jsonify({"code": 200, "data": [
        {"id": r.id, "rule_name": r.rule_name, "day_start_hour": r.day_start_hour,
         "day_end_hour": r.day_end_hour, "day_rate_per_hour": r.day_rate_per_hour,
         "night_rate_per_hour": r.night_rate_per_hour, "free_minutes": r.free_minutes,
         "day_cap": r.day_cap, "night_cap": r.night_cap,
         "green_plate_discount": r.green_plate_discount, "is_active": r.is_active}
        for r in rules], "from_db": True})


@admin_bp.route('/api/admin/price_rules', methods=['POST'])
def save_price_rule():
    data = request.json
    rule_id = data.get('id')
    if rule_id:
        rule = ParkingPriceRule.query.get(rule_id)
        if not rule:
            return jsonify({"code": 404, "msg": "规则不存在"})
    else:
        rule = ParkingPriceRule()
        db.session.add(rule)

    rule.rule_name = data.get('rule_name', '默认计费规则')
    rule.day_start_hour = int(data.get('day_start_hour', 8))
    rule.day_end_hour = int(data.get('day_end_hour', 20))
    rule.day_rate_per_hour = float(data.get('day_rate_per_hour', 5.0))
    rule.night_rate_per_hour = float(data.get('night_rate_per_hour', 3.0))
    rule.free_minutes = int(data.get('free_minutes', 30))
    rule.day_cap = float(data.get('day_cap', 50.0))
    rule.night_cap = float(data.get('night_cap', 20.0))
    rule.green_plate_discount = float(data.get('green_plate_discount', 0.8))
    rule.is_active = data.get('is_active', True)

    db.session.commit()
    audit_log(None, '管理员', 'PRICE_RULE_UPDATE', rule.rule_name, '更新计费规则', request.remote_addr)
    return jsonify({"code": 200, "msg": "计费规则已保存", "id": rule.id})


@admin_bp.route('/api/admin/price_rules/<int:rule_id>', methods=['DELETE'])
def delete_price_rule(rule_id):
    rule = ParkingPriceRule.query.get(rule_id)
    if rule:
        db.session.delete(rule)
        db.session.commit()
        audit_log(None, '管理员', 'PRICE_RULE_DELETE', rule.rule_name, '删除计费规则', request.remote_addr)
        return jsonify({"code": 200, "msg": "规则已删除"})
    return jsonify({"code": 404, "msg": "规则不存在"})


@admin_bp.route('/api/admin/hardware/topology', methods=['GET'])
def get_hardware_topology():
    devices = HardwareDevice.query.order_by(HardwareDevice.last_heartbeat.desc()).all()
    nodes = []
    for d in devices:
        is_online = False
        if d.last_heartbeat:
            is_online = (datetime.now() - d.last_heartbeat).total_seconds() < 30
        nodes.append({
            "device_id": d.device_id, "device_type": d.device_type,
            "location": d.location or "未知位置", "ip_address": d.ip_address,
            "status": "online" if is_online else "offline",
            "last_heartbeat": d.last_heartbeat.strftime('%H:%M:%S') if d.last_heartbeat else '',
            "firmware_version": d.firmware_version or ''
        })

    edges = []
    pi5_devices = [d for d in devices if d.device_type in ('raspberry_pi_5', 'k210')]
    esp32_devices = [d for d in devices if d.device_type == 'esp32_s3']
    stm32_devices = [d for d in devices if d.device_type == 'stm32']

    for pi5 in pi5_devices:
        edges.append({"from": "cloud", "to": pi5.device_id, "protocol": "HTTP/WS"})
    for esp in esp32_devices:
        edges.append({"from": "cloud", "to": esp.device_id, "protocol": "HTTP"})
        for stm in stm32_devices:
            edges.append({"from": esp.device_id, "to": stm.device_id, "protocol": "UART"})
    for pi5 in pi5_devices:
        for esp in esp32_devices:
            edges.append({"from": pi5.device_id, "to": esp.device_id, "protocol": "UART/GPIO"})

    return jsonify({
        "code": 200,
        "data": {"nodes": nodes, "edges": edges,
                 "summary": {"pi5_count": len(pi5_devices), "esp32_count": len(esp32_devices),
                             "stm32_count": len(stm32_devices)}}
    })


@admin_bp.route('/api/admin/hardware/control', methods=['POST'])
def hardware_control():
    data = request.json
    device_id = data.get('device_id', '')
    command = data.get('command', '')
    params = data.get('params', {})

    valid_commands = ['gate_open', 'gate_close', 'led_green', 'led_red', 'led_yellow',
                      'servo_set', 'restart_device', 'update_firmware', 'sync_time']

    if command not in valid_commands:
        return jsonify({"code": 400, "msg": f"无效指令，可用: {valid_commands}"})

    audit_log(None, '管理员', f'HW_CTRL_{command.upper()}', device_id,
              f"硬件控制: {command} {params}", request.remote_addr)

    return jsonify({
        "code": 200, "msg": f"指令 {command} 已下发到 {device_id}",
        "command": {"device_id": device_id, "command": command, "params": params}
    })
