/**
 ****************************************************************************************************
 * @file        camera.h
 * @author      正点原子团队(ALIENTEK)
 * @version     V1.0
 * @date        2023-12-01
 * @brief       CAMERA 驱动代码
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

#ifndef __CAMERA_H
#define __CAMERA_H

#include "Arduino.h"

/* 引脚定义 */
#define OV_SCL_PIN       38 
#define OV_SDA_PIN       39 
#define OV_D0_PIN        4 
#define OV_D1_PIN        5 
#define OV_D2_PIN        6 
#define OV_D3_PIN        7 
#define OV_D4_PIN        15 
#define OV_D5_PIN        16 
#define OV_D6_PIN        17 
#define OV_D7_PIN        18 
#define OV_VSYNC_PIN     47   
#define OV_HREF_PIN      48 
#define OV_PCLK_PIN      45    
#define OV_XCLK_PIN      -1
#define OV_RESET_PIN     -1
#define OV_PWDN_PIN      -1

/* 在xl9555.h文件已经有定义
#define OV_RESET     
#define OV_PWDN        
*/

/* 函数声明 */
uint8_t camera_init(void);            /* 摄像头初始化 */
uint8_t camera_capture_show(void);    /* LCD显示摄像头捕获数据 */

#endif