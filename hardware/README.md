# 硬件部署架构

```
                         云端 Flask 后端
                              |
                         HTTP/WebSocket
                              |
    +-------------------------+-------------------------+
    |                         |                         |
    v                         v                         v
  Pi5 (边缘AI)            ESP32-S3 (通信)          K210 (兼容)
  YOLOv8n+OCR             WiFi+协议转换           旧方案保留
    |                         |
    | GPIO                    | UART
    v                         v
  闸机/LED              STM32F103 (下位机)
                        HC-SR04 x8 + 舵机 x2
```

## 目录结构

```
hardware/
├── README.md            # 本文档
├── pi5/                 # 树莓派5 边缘节点
│   ├── main.py          # 主程序 (YOLO+OCR+上报)
│   ├── config.py        # 配置文件
│   └── install.sh       # 环境安装脚本
└── stm32/               # STM32 下位机固件
    ├── main.c           # 主固件 (传感器+舵机+LED+UART)
    └── protocol.h       # 通信协议定义
```

## Pi5 接线图

| GPIO  | 设备      | 说明           |
|-------|-----------|----------------|
| GPIO17| LED 绿灯  | 允许通行       |
| GPIO27| LED 红灯  | 禁止通行/车位满 |
| GPIO22| 继电器    | 闸机抬杆       |
| CSI   | Pi Camera | 图像采集       |
| UART  | ESP32     | /dev/ttyAMA0  |

## STM32 接线图

| 引脚  | 设备           | 说明              |
|-------|----------------|-------------------|
| PA0   | HC-SR04 Trig 1 | 车位1超声波触发   |
| PA1   | HC-SR04 Echo 1 | 车位1超声波回波   |
| PA6   | HC-SR04 Trig 2 | 车位2超声波触发   |
| PA7   | HC-SR04 Echo 2 | 车位2超声波回波   |
| PB6   | HC-SR04 Trig 3 | 车位3 (以此类推)  |
| PB7   | HC-SR04 Echo 3 | ...               |
| PB0   | 舵机 PWM       | 闸机抬杆控制      |
| PB12  | LED 绿灯       | 空闲指示          |
| PB13  | LED 红灯       | 占用指示          |
| PB14  | LED 黄灯       | 故障/维护         |
| PA9   | USART1 TX      | → ESP32 RX        |
| PA10  | USART1 RX      | ← ESP32 TX        |

## 数据流

```
1. 入场:
   车辆驶入 → Pi5 摄像头检测 → YOLO 裁剪 → OCR 识别车牌
   → HTTP POST /api/hardware/edge/upload
   → 后端返回 {action:"open_in", gate_command:"OPEN"}
   → Pi5 GPIO 开闸 → ESP32 UART转发 → STM32 舵机开闸

2. 车位检测:
   STM32 轮询 HC-SR04 → 距离 < 50cm = 有车
   → UART 上报 "SENSOR|001|25.5|1"
   → ESP32 WiFi 转发 → HTTP POST /api/hardware/stm32/sensor
   → 后端更新车位状态 → 返回 LED 指令

3. 出场:
   摄像头识别车牌 → 后端查找在停记录 → 计费
   → 返回 {action:"open_out", fee:15.00}
   → 开闸放行
```

## 启动命令

```bash
# Pi5
cd hardware/pi5
python3 main.py

# STM32
# 使用 STM32CubeIDE 或 Keil 编译烧录 main.c
```
