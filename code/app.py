import os
import threading
import time
import random
import re
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify

from extensions import db, sim_config, calculate_parking_fee, calculate_parking_fee_simple, \
    add_log, system_logs, decode_jwt_token
from models import ParkingSlot, ParkingRecord, User
from tools.plate_generator import generate_realistic_plate
from database_init import init_database


def create_app():
    app = Flask(__name__)
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'smart_parking.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'smart-parking-secret-key-2026')

    db.init_app(app)

    from routes.admin_routes import admin_bp
    from routes.user_routes import user_bp
    from routes.hardware_routes import hardware_bp
    from routes.auth_routes import auth_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(hardware_bp)

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/api/system/logs')
    def get_system_logs():
        return jsonify({"code": 200, "data": system_logs})

    @app.route('/api/system/status')
    def get_system_status():
        total = ParkingSlot.query.count()
        occupied = ParkingSlot.query.filter_by(status=1).count()
        reserved = ParkingSlot.query.filter_by(status=2).count()
        free = total - occupied - reserved
        return jsonify({
            "code": 200,
            "data": {
                "total_slots": total, "occupied": occupied,
                "free": free, "reserved": reserved,
                "occupancy_rate": round(occupied / total * 100, 1) if total > 0 else 0,
                "simulation_running": sim_config["is_running"]
            }
        })

    @app.before_request
    def check_rate_limit():
        from extensions import token_blacklist
        if request.endpoint in ('auth.login', 'auth.register'):
            client_ip = request.remote_addr
            if not hasattr(app, '_rate_counter'):
                app._rate_counter = {}
            now = time.time()
            window = 60
            max_req = 10
            key = f"{client_ip}:{request.endpoint}"
            app._rate_counter = {k: [t for t in v if now - t < window] for k, v in app._rate_counter.items()}
            attempts = app._rate_counter.get(key, [])
            if len(attempts) >= max_req:
                return jsonify({"code": 429, "msg": "请求过于频繁，请稍后再试"}), 429
            attempts.append(now)
            app._rate_counter[key] = attempts

    return app


def broadcast_socket_event(app, event_name, data):
    try:
        socketio = getattr(app, 'socketio_instance', None)
        if socketio:
            socketio.emit(event_name, data)
    except Exception:
        pass


def simulate_virtual_parking_spaces(app):
    with app.app_context():
        add_log("虚拟车位动态引擎已启动", "info")
        while True:
            if not sim_config["is_running"]:
                time.sleep(1)
                continue
            time.sleep(random.randint(sim_config["min_interval"], sim_config["max_interval"]))

            slot = ParkingSlot.query.filter_by(slot_number=f"A-{random.randint(3, 102):03d}").first()
            if not slot:
                continue

            if random.random() < sim_config["entry_probability"] and slot.status == 0:
                slot.status = 1
                mock_plate = generate_realistic_plate()
                slot_num = int(slot.slot_number.split('-')[1])
                clean_plate = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', mock_plate)

                if 3 <= slot_num <= 22:
                    if len(clean_plate) == 7:
                        mock_plate = mock_plate[:3] + "D" + mock_plate[3:]
                else:
                    if len(clean_plate) == 8:
                        mock_plate = mock_plate[:3] + mock_plate[4:]

                backdate_minutes = random.randint(10, 720)
                fake_entry = datetime.now() - timedelta(minutes=backdate_minutes)
                db.session.add(ParkingRecord(
                    plate_number=mock_plate, slot_number=slot.slot_number,
                    status='正在停车', entry_time=fake_entry
                ))
                db.session.commit()
                add_log(f"车辆入场: {mock_plate} → {slot.slot_number}", "info")
                broadcast_socket_event(app, 'entry_alert', {
                    "plate": mock_plate, "slot": slot.slot_number, "time": datetime.now().strftime('%H:%M:%S')
                })

            elif slot.status == 1:
                slot.status = 0
                record = ParkingRecord.query.filter_by(slot_number=slot.slot_number, status='正在停车').first()
                if record:
                    record.exit_time = datetime.now()
                    record.fee = calculate_parking_fee_simple(record.entry_time, record.exit_time)
                    record.status = '已支付'
                    db.session.commit()
                    add_log(f"车辆出场: {record.plate_number} 费用 ¥{record.fee}", "info")
                    broadcast_socket_event(app, 'exit_alert', {
                        "plate": record.plate_number, "slot": slot.slot_number,
                        "fee": record.fee, "time": datetime.now().strftime('%H:%M:%S')
                    })

            db.session.commit()

            total = ParkingSlot.query.count()
            occupied = ParkingSlot.query.filter_by(status=1).count()
            free = total - occupied - ParkingSlot.query.filter_by(status=2).count()
            broadcast_socket_event(app, 'dashboard_stats', {
                "total": total, "free": free, "occupied": occupied,
                "time": datetime.now().strftime('%H:%M:%S')
            })


if __name__ == '__main__':
    app = create_app()
    init_database(app)

    socketio_enabled = os.environ.get('ENABLE_SOCKETIO', '0') == '1'
    if socketio_enabled:
        try:
            from flask_socketio import SocketIO
            socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
            app.socketio_instance = socketio
            add_log("WebSocket 实时推送已启用", "info")

            @socketio.on('connect')
            def on_connect():
                pass

            @socketio.on('disconnect')
            def on_disconnect():
                pass

            print("WebSocket 实时推送已就绪")
        except ImportError:
            add_log("flask-socketio 未安装，WebSocket 功能不可用", "warn")
            print("pip install flask-socketio")
    else:
        add_log("WebSocket 未启用 (设置 ENABLE_SOCKETIO=1 以启用)", "info")

    threading.Thread(target=simulate_virtual_parking_spaces, args=(app,), daemon=True).start()

    if socketio_enabled and 'socketio' in dir():
        socketio.run(app, debug=True, host='0.0.0.0', port=5000, use_reloader=False)
    else:
        app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
