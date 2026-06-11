/**
 * STM32 <> ESP32 UART 通信协议定义
 * 格式: CMD|PAYLOAD\r\n  (ASCII文本协议, 简单可靠)
 *
 * 命令方向:
 *   ESP32 -> STM32: GATE, LED, PING, TIME
 *   STM32 -> ESP32: SENSOR, PONG, ACK, ERR
 */

#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <stdint.h>

/* ---- 命令码 ---- */
#define CMD_GATE_OPEN     "GATE:1"
#define CMD_GATE_CLOSE    "GATE:0"
#define CMD_LED_GREEN     "LED:1"
#define CMD_LED_RED       "LED:2"
#define CMD_LED_YELLOW    "LED:3"
#define CMD_LED_BLINK_G   "LED:11"
#define CMD_LED_BLINK_R   "LED:12"
#define CMD_LED_OFF       "LED:0"
#define CMD_PING          "PING"
#define CMD_TIME_SYNC     "TIME"

/* ---- 传感器上报格式 ---- */
// SENSOR|<slot_id:03d>|<distance_cm:.1f>|<occupied:1>
// 例: "SENSOR|001|25.5|1" 表示1号车位25.5cm, 有车

/* ---- 舵机角度参数 ---- */
#define SERVO_MIN_PULSE   500   // 0度
#define SERVO_MAX_PULSE   2500  // 180度
#define SERVO_OPEN_ANGLE  90    // 闸机打开 90度
#define SERVO_CLOSE_ANGLE 0     // 闸机关闭 0度

/* ---- 超声波参数 ---- */
#define SONIC_TRIG_US     10    // 触发脉冲宽度 (us)
#define SONIC_TIMEOUT_MS  25    // 测量超时 (ms)
#define SONIC_SPEED_CM_US 0.0343f  // 声速 cm/us (20°C)

/* ---- 车位判定 ---- */
#define SLOT_OCCUPIED_CM  50.0f   // 距离 < 50cm 认为有车
#define SLOT_EMPTY_CM     200.0f  // 距离 > 200cm 认为空

/* ---- 上报间隔 ---- */
#define SENSOR_REPORT_MS  2000    // 传感器上报间隔 (ms)
#define HEARTBEAT_MS      10000   // 心跳间隔 (ms)

#endif /* PROTOCOL_H */
