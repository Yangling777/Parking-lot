#ifndef __KEY_H
#define __KEY_H

#include "Arduino.h"
#include "xl9555.h"  // 必须引入扩展芯片库

/* 引脚定义 */
#define KEY1_PIN      0   /* 板载 KEY1(BOOT) 连接到 GPIO0 */

/* 宏定义按键被按下的返回值 */
#define KEY1_PRES     1   /* KEY1 被按下 */
#define KEY2_PRES     2   /* KEY2 (XL9555) 被按下 */

/* 函数声明 */
void key_init(void);              
uint8_t key_scan(uint8_t mode);   

#endif