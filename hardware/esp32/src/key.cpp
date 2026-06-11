#include "key.h"

// 按键初始化
void key_init(void) {
    pinMode(KEY1_PIN, INPUT_PULLUP);
}

// 标准按键扫描函数
// mode: 0=单次触发, 1=连按
// 返回值: 0(没按), KEY1_PRES, KEY2_PRES
uint8_t key_scan(uint8_t mode) {
    static uint8_t key_up = 1; 
    
    if (mode) key_up = 1; 
    
    // 读取两个按键的状态 (低电平有效)
    bool k1_pressed = (digitalRead(KEY1_PIN) == LOW);
    bool k2_pressed = (xl9555_get_pin(KEY2) == 0);

    if (key_up && (k1_pressed || k2_pressed)) {
        delay(10); // 10ms 软件消抖
        key_up = 0; 
        
        if (k1_pressed) return KEY1_PRES;
        if (k2_pressed) return KEY2_PRES;
    } else if (!k1_pressed && !k2_pressed) {
        key_up = 1; // 恢复标志位
    }
    
    return 0; 
}