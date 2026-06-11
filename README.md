# 智能停车场管理系统

> Smart Parking Lot Management System — 边缘AI + 物联网 + 云服务

基于 **Raspberry Pi 5 (YOLOv8n + PaddleOCR)** 边缘识别、**ESP32-S3** 通信、**STM32** 硬件控制的完整智能停车场解决方案。

---

## 系统架构

```
                          +-------------------+
                          |   云端 Flask API   |
                          |   port 5000        |
                          +-------+-----------+
                                  | HTTP / WebSocket
                 +----------------+----------------+
                 |                |                |
          +------v-----+  +------v-----+  +------v-----+
          |  Pi 5 (AI) |  | ESP32-S3   |  | K210 (备) |
          | YOLOv8n+OCR|  | WiFi/UART桥 |  |  兼容保留   |
          +------+------+  +------+-----+  +------------+
                 |                 |
              GPIO               UART
                 |                 |
          +------v------+  +------v------+
          | 闸机 / LED   |  | STM32F103  |
          +-------------+  | HC-SR04x8   |
                           | 舵机/LED     |
                           +-------------+
```

**数据流：** 摄像头 → YOLO 车辆检测 → PaddleOCR 车牌识别 → 云端匹配 → 分配车位 → 开闸放行 → 传感器监测 → 计费离场

---

## 技术栈

| 层级 | 技术 |
|------|------|
| **后端框架** | Flask 3 + SQLAlchemy + SQLite |
| **认证鉴权** | JWT HS256 (access + refresh token) |
| **实时通信** | flask-socketio (WebSocket) |
| **边缘AI** | YOLOv8n (车辆检测) + PaddleOCR (车牌识别) + HyperLPR3 |
| **云端OCR** | 腾讯云 LicensePlateOCR (兜底) |
| **AI推荐** | scikit-learn MLP + 协同过滤 |
| **前端** | Vue 3 + Element Plus + ECharts |
| **硬件通信** | PySerial, UART CRC-16, STM32 AA55帧协议 |
| **部署** | Python 3.13 + Docker 可选 |

---

## 目录结构

```
car/
├── code/                        # 后端应用
│   ├── app.py                   # Flask 入口 + 虚拟仿真引擎
│   ├── extensions.py            # JWT / CRC16 / 计费 / 审计
│   ├── models.py                # 8 张数据表 (ORM)
│   ├── database_init.py         # 种子数据
│   ├── routes/                  # API 蓝图
│   │   ├── auth_routes.py       # JWT 登录/注册/刷新/登出
│   │   ├── admin_routes.py      # 管理面板(用户/审批/计费/硬件)
│   │   ├── user_routes.py       # 用户端(预约/支付/充电/记录)
│   │   ├── hardware_routes.py   # 硬件接口(识别/传感器/心跳/协议)
│   │   └── ai_parking_engine.py # ML推荐引擎
│   ├── edge/                    # 边缘计算模块
│   │   ├── yolo_detector.py     # YOLOv8n 车辆检测器
│   │   ├── ocr_engine.py        # PaddleOCR 车牌识别引擎
│   │   ├── plate_recognizer.py  # 识别管线(检测+OCR+稳定性)
│   │   ├── stm32_comm.py        # STM32 AA55帧协议
│   │   ├── esp32_bridge.py      # ESP32 WiFi桥接
│   │   ├── k210_compat.py       # K210 兼容适配器
│   │   ├── main_bridge.py       # 串口桥接(HyperLPR3)
│   │   ├── camera_module.py     # 摄像头串口采集
│   │   ├── time_module.py       # ESP32时钟同步
│   │   └── webcam_simulator.py  # PC摄像头模拟器
│   ├── templates/               # 前端 HTML 模板
│   └── static/
├── hardware/                    # 硬件代码
│   ├── README.md                # 硬件架构与接线
│   ├── pi5/                     # 树莓派5 边缘节点
│   │   ├── main.py              # 主程序(检测+识别+控制)
│   │   ├── config.py            # 部署配置
│   │   └── install.sh           # Pi5 环境安装
│   └── stm32/                   # STM32 下位机固件
│       ├── main.c               # 超声波+舵机+LED+UART
│       └── protocol.h           # 通信协议定义
├── tools/                       # 工具脚本
│   ├── plate_generator.py       # 车牌生成器
│   └── image_converter/         # 图片转C数组
├── docs/                        # 项目文档
│   ├── generate_doc.py          # Word文档生成器
│   └── generate_doc_v2.py
├── setup.py                     # 一键配环境
├── requirements.txt             # Python依赖清单
├── .gitignore
└── README.md                    # 本文件
```

---

## 快速开始

### 1. 环境要求

- Python 3.13+
- (可选) CUDA GPU / Pi5 用于边缘AI
- (可选) ESP32-S3 / STM32 / K210 硬件

### 2. 一键安装

```bash
# 克隆项目
git clone <repo-url>
cd car

# 一键配置环境
python setup.py
```

### 3. 启动后端

```bash
# 方式一: 直接启动
python code/app.py

# 方式二: 启用 WebSocket
ENABLE_SOCKETIO=1 python code/app.py

# 方式三: 生产模式
gunicorn -w 4 -b 0.0.0.0:5000 "code.app:create_app()"
```

访问地址:
- 用户端: http://localhost:5000
- 管理端: http://localhost:5000/admin
- 模拟器: http://localhost:5000/simulator

### 4. 启动边缘节点 (Pi5)

```bash
cd hardware/pi5
python3 main.py
```

### 5. 测试账号

| 角色 | 手机号 | 密码 | 说明 |
|------|--------|------|------|
| 普通用户 | 13800138000 | 123456 | 车牌: 京A88888 |
| 管理员 | admin | admin | 最高权限 |
| 安保 | anbao | anbao | 只读大盘 |
| 测试用户 | test | 123456 | 免防刷限制 |
| 物业 | wuye | wuye | 管理权限 |

---

## API 概览 (57个接口)

### 认证 `/api/auth/`
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | JWT登录 → access + refresh token |
| POST | `/api/auth/register` | 注册(待审批) |
| POST | `/api/auth/refresh` | 刷新令牌(旧token黑名单) |
| POST | `/api/auth/logout` | 登出(加入黑名单) |

### 用户 `/api/user/`
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/user/info` | 个人信息 |
| GET | `/api/user/recommend` | AI推荐车位 |
| POST | `/api/user/reserve` | 预约车位 |
| POST | `/api/user/pay` | 支付停车费 |
| POST | `/api/user/start_charge` | 开始充电 |

### 管理 `/api/admin/`
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/dashboard` | 仪表盘数据 |
| POST | `/api/admin/user/approve` | 审批用户 |
| GET/POST | `/api/admin/price_rules` | 计费规则CRUD |
| GET | `/api/admin/audit_logs` | 审计日志 |
| GET | `/api/admin/hardware/topology` | 硬件拓扑图 |

### 硬件 `/api/hardware/`
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/hardware/edge/upload` | Pi5/K210 上传识别结果 |
| POST | `/api/hardware/heartbeat` | 设备心跳 |
| POST | `/api/hardware/stm32/sensor` | STM32 传感器上报 |
| POST | `/api/hardware/stm32/command` | 闸机/LED/舵机指令 |
| POST | `/api/hardware/esp32/bridge` | ESP32 协议桥接 |

---

## 计费规则

| 时段 | 费率 | 封顶 |
|------|------|------|
| 白天 8:00-20:00 | ¥5/小时 | ¥50/天 |
| 夜间 20:00-8:00 | ¥3/小时 | ¥20/夜 |
| 免费 | 入场后30分钟内 | — |
| 新能源绿牌 | 享8折 | — |

> 计费规则可通过管理面板 `/api/admin/price_rules` 实时修改，无需重启。

---

## 硬件接线

详见 [hardware/README.md](hardware/README.md)

| 设备 | 连接方式 | 功能 |
|------|----------|------|
| Pi5 CSI Camera | GPIO CSI | 车辆抓拍 |
| Pi5 继电器 | GPIO22 | 闸机抬杆 |
| Pi5 LED | GPIO17/27 | 通行指示 |
| STM32 HC-SR04 | GPIO | 车位超声波测距 |
| STM32 舵机 | PB0 PWM | 闸机控制 |
| ESP32 ↔ STM32 | UART 115200 | 协议转换 |
| ESP32 ↔ 云端 | WiFi | HTTP通信 |

---

## JWT 认证使用

```bash
# 登录获取token
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"phone":"13800138000","password":"123456"}'

# 返回
{
  "code": 200,
  "data": {
    "access_token": "eyJhbG...",
    "refresh_token": "eyJhbG...",
    "expires_in": 7200,
    "user": { "id": 1, "username": "张三", "role": "user" }
  }
}

# 使用token访问受保护接口
curl http://localhost:5000/api/user/info \
  -H "Authorization: Bearer eyJhbG..."
```

---

## 开发指南

```bash
# 安装开发依赖
pip install pytest pytest-cov

# 运行测试
pytest tests/

# 启动调试模式 (热重载)
python code/app.py
```

### 添加新硬件节点类型

1. 在 `edge/` 下创建模块文件 (参考 `k210_compat.py`)
2. 在 `hardware_routes.py` 添加对应路由
3. 在 `models.py` 的 `HardwareDevice.device_type` 注册新类型

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `JWT_SECRET` | 内置默认值 | JWT 签名密钥 |
| `SECRET_KEY` | 内置默认值 | Flask Session 密钥 |
| `ENABLE_SOCKETIO` | 0 | 启用 WebSocket 推送 |
| `TENCENT_SECRET_ID` | — | 腾讯云OCR SecretId |
| `TENCENT_SECRET_KEY` | — | 腾讯云OCR SecretKey |

---

## License

MIT
