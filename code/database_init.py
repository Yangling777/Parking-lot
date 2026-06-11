from models import User, ParkingSlot, ParkingPriceRule
from extensions import db, spot_recommender
import pandas as pd


def init_database(app):
    with app.app_context():
        db.create_all()

        # 定义 6 大角色预设数据
        users_data = [
            # 1. 最普通用户
            {'username': '张三', 'phone': '13800138000', 'plate': '京A88888', 'role': 'user', 'pwd': '123456'},
            # 2. 安保 (只看大盘、记录，无高级操作)
            {'username': '安保', 'phone': 'anbao', 'plate': '', 'role': 'security', 'pwd': 'anbao'},
            # 3. 开发管理员 (最高权限)
            {'username': 'admin', 'phone': 'admin', 'plate': '', 'role': 'admin', 'pwd': 'admin'},
            # 4. 测试用户 (免除防刷限制)
            {'username': '测试车主', 'phone': 'test', 'plate': '京B66666,京C12345', 'role': 'test_user',
             'pwd': '123456'},
            # 5. 模拟终端 (只进模拟器)
            {'username': '模拟', 'phone': 'test2', 'plate': '', 'role': 'simulator', 'pwd': '123456'},
            # 6. 物业总管 (除了底层车流引擎，其他全看)
            {'username': 'wuye', 'phone': 'wuye', 'plate': '', 'role': 'manager', 'pwd': 'wuye'},
        ]

        # 循环注入账户
        for u_data in users_data:
            if not User.query.filter_by(phone=u_data['phone']).first():
                u = User(username=u_data['username'], phone=u_data['phone'], plate_number=u_data['plate'],
                         role=u_data['role'])
                u.set_password(u_data['pwd'])
                db.session.add(u)

        db.session.commit()

        # 初始车位注入
        if ParkingSlot.query.count() == 0:
            for i in range(1, 103):
                db.session.add(ParkingSlot(slot_number=f'A-{i:03d}', has_charging=(3 <= i <= 22)))
        else:
            slots = ParkingSlot.query.all()
            for s in slots:
                s.has_charging = (3 <= int(s.slot_number.split('-')[1]) <= 22)
        db.session.commit()

        if ParkingPriceRule.query.count() == 0:
            db.session.add(ParkingPriceRule(
                rule_name='默认计费规则', day_start_hour=8, day_end_hour=20,
                day_rate_per_hour=5.0, night_rate_per_hour=3.0,
                free_minutes=30, day_cap=50.0, night_cap=20.0,
                green_plate_discount=0.8, is_active=True
            ))
            db.session.commit()

        print("[AI引擎] 正在加载协同过滤推荐模型历史偏好...")
        dummy_history = pd.DataFrame(
            {'user_id': [1, 1, 2, 3, 3], 'spot_id': [5, 6, 25, 88, 90], 'rating': [5, 4, 5, 4, 5]})
        spot_recommender.fit_history(dummy_history)