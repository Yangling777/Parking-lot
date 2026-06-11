/**
 ****************************************************************************************************
 * @file        remote.h
 * @author      正点原子团队(ALIENTEK)
 * @version     V1.0
 * @date        2023-12-01
 * @brief       REMOTE 驱动代码
 * @license     Copyright (c) 2020-2032, 广州市星翼电子科技有限公司
 ****************************************************************************************************
 * @attention
 *
 * 实验平台:正点原子 ESP32S3 开发板
 * 在线视频:www.yuanzige.com
 * 技术论坛:www.openedv.com
 * 公司网址:www.alientek.com
 * 购买地址:openedv.taobao.com
 *
 * 修改说明
 * V1.0 20231201
 * 第一次发布
 *
 ****************************************************************************************************
 */

#ifndef __REMOTE_H
#define __REMOTE_H

#include "Arduino.h"

/* 引脚定义 */
#define RMT_RX_PIN 2

/* 函数声明 */
void remote_init(void);         /* 红外遥控初始化 */
uint8_t remote_scan(void);      /* 处理红外按键 */

#endif