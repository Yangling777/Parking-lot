/**
 ****************************************************************************************************
 * @file        remote.cpp
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

#include "remote.h"
#include <IRremoteESP8266.h>
#include <IRrecv.h>
#include <IRutils.h>
#include "spilcd.h"

IRrecv irrecv(RMT_RX_PIN);
decode_results results;

/**
 * @brief       红外遥控初始化
 * @param       无
 * @retval      无
 */
void remote_init(void)
{
    irrecv.enableIRIn();
}

/**
 * @brief       处理红外按键
 * @param       无
 * @retval      0:没有任何按键按下
 *              其他:按下的按键键值 
 */
uint8_t remote_scan(void)
{  
    uint8_t rmt_data = 0;         /* 红外遥控按键键值 */
    uint8_t remote_key = 0;       /* 提取控制码 */
    uint32_t raw_data = 0;        /* 原始数据 */

    if (irrecv.decode(&results))  /* 对红外数据进行解码 */
    {
        raw_data = results.value;
        remote_key = (uint8_t)(raw_data >> 8);          /* 提取控制码 */
        
        if ((remote_key != 0xFF) && (remote_key != 0))  /* 证明已经获得有效键值 */
        {
            rmt_data = remote_key;
        }

        irrecv.resume();          /* 接收下一个值 */
        
        return rmt_data;
    }
    
    return 0;
}
