#include "esp_camera.h"
#include <mbedtls/base64.h> 
#include <Wire.h> 
#include "src/xl9555.h"  
#include "src/spilcd.h"  
#include "src/camera.h"  
#include "qr_code.h" 
#include "src/remote.h"

// ================== 1. 硬件引脚定义 ==================
// --- 主道闸系统 ---
#define TRIG_PIN  3       
#define ECHO_PIN  14  
#define SERVO_PIN 10     
#define BOOT_PIN  0      

#define OV_FLASH  BEEP       
#define OV_PWR    OV_PWDN    

// --- 🌟 双车位终极避坑引脚 ---
#define P1_TRIG_PIN 48  // 已测试成功
#define P1_ECHO_PIN 9   // 已测试成功
#define P2_TRIG_PIN 45  // P4排针上的 IO45 (安全输出脚)
#define P2_ECHO_PIN 46  // 已测试成功
#define PARK_THRESHOLD 5.0  // 车位判定阈值：5.0cm

// ================== 2. 全局状态变量 ==================
int system_state = 0;             
unsigned long state_timer = 0;    
unsigned long last_photo_time = 0;
int stable_count = 0;

int current_servo_angle = 180; 

// --- 双车位状态管理 ---
unsigned long last_park_check = 0;
bool p1_occupied = false;
bool p2_occupied = false;
int p1_occ_count = 0, p1_emp_count = 0;
int p2_occ_count = 0, p2_emp_count = 0;

// ================== 3. 核心功能函数 ==================

// 获取超声波测距
float get_dist(int trig, int echo) {
    digitalWrite(trig, LOW); delayMicroseconds(2);
    digitalWrite(trig, HIGH); delayMicroseconds(10);
    digitalWrite(trig, LOW);
    
    float d = pulseIn(echo, HIGH, 25000);
    if (d == 0) return 999.0; 
    return d * 0.034 / 2;
}

// 调速舵机
void set_servo_angle(int target_angle, int speed_delay = 15) {
    target_angle = constrain(target_angle, 0, 180);
    if (speed_delay == 0) {
        int duty = map(target_angle, 0, 180, 205, 1024);
        ledcWrite(SERVO_PIN, duty); 
        current_servo_angle = target_angle;
        return;
    }
    if (current_servo_angle < target_angle) {
        for (int a = current_servo_angle; a <= target_angle; a++) {
            ledcWrite(SERVO_PIN, map(a, 0, 180, 205, 1024));
            delay(speed_delay);
        }
    } else {
        for (int a = current_servo_angle; a >= target_angle; a--) {
            ledcWrite(SERVO_PIN, map(a, 0, 180, 205, 1024));
            delay(speed_delay);
        }
    }
    current_servo_angle = target_angle;
}

#define QR_WIDTH  120
#define QR_HEIGHT 120
void lcd_draw_qrcode(uint16_t x, uint16_t y, const unsigned char *bmp) {
    uint16_t line_buf[QR_WIDTH]; 
    for (int r = 0; r < QR_HEIGHT; r++) {
        for (int c = 0; c < QR_WIDTH; c++) {
            int bit_idx = r * QR_WIDTH + c;
            int byte_idx = bit_idx / 8;
            int bit_offset = 7 - (bit_idx % 8); 
            bool is_black = (bmp[byte_idx] & (1 << bit_offset)) != 0;
            line_buf[c] = is_black ? BLACK : WHITE; 
        }
        lcd_show_pic(x, y + r, QR_WIDTH, 1, (uint8_t*)line_buf);
    }
}

void set_flash_light(bool on) {
    xl9555_pin_set(OV_FLASH, on ? IO_SET_HIGH : IO_SET_LOW); 
    xl9555_pin_set(OV_PWR, IO_SET_LOW); 
}

void ui_radar_mode() {
    system_state = 0; 
    set_flash_light(false);
    lcd_clear(WHITE);
    
    lcd_show_string(50, 80, 200, 16, LCD_FONT_16, (char*)"RADAR CRUISE", BLUE);
    lcd_show_string(60, 160, 200, 16, LCD_FONT_16, (char*)"Standby...", BLACK);
    
    set_servo_angle(180); 
}

void takeAndSendPhoto() {
    for(int i=0; i<2; i++) { camera_fb_t * t = esp_camera_fb_get(); if(t) esp_camera_fb_return(t); }
    camera_fb_t * fb = esp_camera_fb_get();
    if (!fb || fb->format != PIXFORMAT_JPEG) { if(fb) esp_camera_fb_return(fb); return; }
    size_t out_len;
    mbedtls_base64_encode(NULL, 0, &out_len, fb->buf, fb->len);
    unsigned char * buf = (unsigned char *)malloc(out_len + 1);
    if (buf) {
        mbedtls_base64_encode(buf, out_len, &out_len, fb->buf, fb->len); buf[out_len] = '\0';
        Serial.println("\n[系统] 📸 正在上传抓拍车辆照片...");
        Serial.println("---BEGIN_IMAGE---");
        Serial.println((char*)buf); 
        Serial.println("---END_IMAGE---");
        Serial.println("[系统] ☁️ 照片上传完毕，等待云端识别结果...");
        free(buf);
    }
    esp_camera_fb_return(fb);
}

// ================== 4. 初始化 ==================
void setup() {
    Serial.begin(921600); 
    Serial.setTxBufferSize(8192); 
    delay(1000);

    Serial.println("\n==================================");
    Serial.println("🚀 智能停车场控制终端启动中...");
    Serial.println("🛠️ 模式：双车位启用 | A-001(48,9) | A-002(45,46)");

    xl9555_init();  
    
    xl9555_io_config(OV_FLASH, IO_SET_OUTPUT); 
    xl9555_io_config(OV_PWR, IO_SET_OUTPUT);
    xl9555_pin_set(OV_PWR, IO_SET_LOW); 
    delay(200);

    lcd_init(); 
    lcd_clear(WHITE); 
    
    ledcAttach(SERVO_PIN, 50, 13); 
    set_servo_angle(180, 0); 
    
    pinMode(BOOT_PIN, INPUT_PULLUP); 
    pinMode(TRIG_PIN, OUTPUT); pinMode(ECHO_PIN, INPUT);
    
    // 初始化测试车位引脚
    pinMode(P1_TRIG_PIN, OUTPUT); pinMode(P1_ECHO_PIN, INPUT);
    pinMode(P2_TRIG_PIN, OUTPUT); pinMode(P2_ECHO_PIN, INPUT);
    
    remote_init(); 
    
    lcd_show_string(40, 150, 200, 24, LCD_FONT_24, (char*)"SYSTEM READY", BLACK);
    delay(2000); 
    
    Serial.println("📷 正在初始化摄像头...");
    while (camera_init() != 0) { delay(1000); }
    sensor_t * s = esp_camera_sensor_get();
    if(s) {
        s->set_pixformat(s, PIXFORMAT_JPEG); 
        s->set_framesize(s, FRAMESIZE_QVGA); 
        s->set_quality(s, 15); 
        s->set_vflip(s, 1); 
    }
    
    Serial.println("✅ 系统初始化完成，进入雷达巡航模式\n==================================\n");
    ui_radar_mode();
}

void loop() {
    // ================== 🌟 1. 双车位 5cm 防抖检测 ==================
    // 每 1.2 秒检测一次，避免刷屏太快
    if (millis() - last_park_check > 1200) {
        last_park_check = millis();
        float d1 = get_dist(P1_TRIG_PIN, P1_ECHO_PIN);
        delay(50); // 防串扰延时
        float d2 = get_dist(P2_TRIG_PIN, P2_ECHO_PIN);

        // 清晰的底层探测日志
        Serial.printf("🔍 【车位测距】A-001: %.1f cm  |  A-002: %.1f cm\n", d1, d2);

        // --- 车位 1 判定 ---
        if (d1 > 0.1 && d1 <= PARK_THRESHOLD) {
            p1_emp_count = 0;
            if (!p1_occupied) { 
                p1_occ_count++; 
                if(p1_occ_count >= 2) { 
                    p1_occupied = true; 
                    Serial.println("\n🚗 ━━━━━━━━━━━━━━━━━━━━━");
                    Serial.println("🚗 【状态上报】A-001 车位 [被占用]！"); 
                    Serial.println("🚗 ━━━━━━━━━━━━━━━━━━━━━\n");
                } 
            }
        } else {
            p1_occ_count = 0;
            if (p1_occupied) { 
                p1_emp_count++; 
                if(p1_emp_count >= 2) { 
                    p1_occupied = false; 
                    Serial.println("\n🟩 ━━━━━━━━━━━━━━━━━━━━━");
                    Serial.println("🟩 【状态上报】A-001 车位 [已空闲]！"); 
                    Serial.println("🟩 ━━━━━━━━━━━━━━━━━━━━━\n");
                } 
            }
        }

        // --- 车位 2 判定 ---
        if (d2 > 0.1 && d2 <= PARK_THRESHOLD) {
            p2_emp_count = 0;
            if (!p2_occupied) { 
                p2_occ_count++; 
                if(p2_occ_count >= 2) { 
                    p2_occupied = true; 
                    Serial.println("\n🚙 ━━━━━━━━━━━━━━━━━━━━━");
                    Serial.println("🚙 【状态上报】A-002 车位 [被占用]！"); 
                    Serial.println("🚙 ━━━━━━━━━━━━━━━━━━━━━\n");
                } 
            }
        } else {
            p2_occ_count = 0;
            if (p2_occupied) { 
                p2_emp_count++; 
                if(p2_emp_count >= 2) { 
                    p2_occupied = false; 
                    Serial.println("\n🟩 ━━━━━━━━━━━━━━━━━━━━━");
                    Serial.println("🟩 【状态上报】A-002 车位 [已空闲]！"); 
                    Serial.println("🟩 ━━━━━━━━━━━━━━━━━━━━━\n");
                } 
            }
        }
    }

    // ================== 🌟 2. 红外遥控 ==================
    uint8_t rmt_key = remote_scan();
    if (rmt_key) {
        if (rmt_key == 104) { 
            Serial.println("📲 [红外] 触发：显示临时车缴费二维码");
            system_state = 2; state_timer = millis(); 
            lcd_clear(WHITE);
            lcd_show_string(10, 20, 200, 16, LCD_FONT_16, (char*)"FEE:", RED);
            lcd_draw_qrcode(60, 50, lcd_icon); 
            lcd_show_string(40, 190, 200, 24, LCD_FONT_24, (char*)"TEMP VEHICLE", BLACK); 
        }
        else if (rmt_key == 152) { 
            Serial.println("🚧 [红外] 触发：人工紧急抬杆放行！");
            system_state = 4; 
            lcd_clear(WHITE);
            lcd_show_string(40, 100, 200, 24, LCD_FONT_24, (char*)"MANUAL OPEN", GREEN);
            set_servo_angle(90); 
        }
        else if (rmt_key == 176) { 
            Serial.println("🚧 [红外] 触发：强制关杆并恢复雷达");
            ui_radar_mode(); 
        }
    }

    // ================== 🌟 3. 物理按键处理 ==================
    static bool button_pressed = false;
    static unsigned long button_press_time = 0;
    static bool long_press_handled = false;

    if (digitalRead(BOOT_PIN) == LOW) { 
        if (!button_pressed) {
            delay(10); 
            if (digitalRead(BOOT_PIN) == LOW) {
                button_pressed = true; button_press_time = millis(); long_press_handled = false;
            }
        } else {
            if (!long_press_handled && (millis() - button_press_time > 1000)) {
                long_press_handled = true; 
                Serial.println("🚧 [按键] 触发：长按人工抬杆！");
                lcd_clear(WHITE);
                lcd_show_string(40, 100, 200, 24, LCD_FONT_24, (char*)"MANUAL OPEN", GREEN);
                set_servo_angle(90); 
                unsigned long start_wait = millis();
                while(millis() - start_wait < 3000) { yield(); delay(10); }
                ui_radar_mode();
            }
        }
    } else {
        if (button_pressed) {
            button_pressed = false;
            if (!long_press_handled) {
                Serial.println("📲 [按键] 触发：短按显示缴费二维码");
                system_state = 2; state_timer = millis(); 
                lcd_clear(WHITE);
                lcd_show_string(10, 20, 200, 16, LCD_FONT_16, (char*)"FEE:", RED);
                lcd_draw_qrcode(60, 50, lcd_icon); 
                lcd_show_string(40, 190, 200, 24, LCD_FONT_24, (char*)"TEMP VEHICLE", BLACK); 
            }
        }
    }

    // ================== 🌟 4. 上位机下发指令处理 ==================
    if (Serial.available() > 0) {
        String cmd = Serial.readStringUntil('\n'); cmd.trim();
        
        if (cmd.startsWith("ENTER|")) { 
            String plate = cmd.substring(6);
            Serial.println("🟢 [云端] 收到入场许可：车牌号 " + plate + "，正在抬杆！");
            system_state = 3; set_flash_light(false);
            
            lcd_clear(WHITE);
            lcd_show_string(60, 60, 200, 24, LCD_FONT_24, (char*)"WELCOME", GREEN);
            lcd_show_string(50, 120, 200, 32, LCD_FONT_32, (char*)plate.c_str(), BLUE); 
            
            set_servo_angle(90); 
            
            unsigned long wait_entry = millis();
            while(millis() - wait_entry < 3000) { yield(); delay(10); }
            Serial.println("🔴 [云端] 入场完毕，正在落杆");
            ui_radar_mode(); 
        }
        else if (cmd.startsWith("PAY|")) { 
            int bar = cmd.lastIndexOf('|');
            String plate = cmd.substring(4, bar);
            String fee = cmd.substring(bar + 1);
            
            Serial.println("💰 [云端] 收到出场结账指令：车牌号 " + plate + "，需缴费 " + fee + " 元");
            system_state = 3; set_flash_light(false);
            
            lcd_clear(WHITE);
            lcd_show_string(10, 20, 200, 16, LCD_FONT_16, (char*)"FEE:", RED);
            lcd_show_string(70, 20, 200, 16, LCD_FONT_16, (char*)(fee + " RMB").c_str(), BLUE);
            lcd_draw_qrcode(60, 50, lcd_icon); 
            lcd_show_string(50, 190, 200, 24, LCD_FONT_24, (char*)plate.c_str(), BLACK);
            
            // =========================================================================
            // 【修改点 2】出场识别成功后，二维码显示时间从 3000 毫秒增加到 5000 毫秒（5秒）
            // =========================================================================
            unsigned long wait_qr = millis();
            while(millis() - wait_qr < 5000) { yield(); delay(10); } 
            // =========================================================================

            Serial.println("✅ [云端] 缴费成功，正在抬杆放行！");
            lcd_clear(WHITE);
            lcd_show_string(40, 80, 200, 24, LCD_FONT_24, (char*)"PAY SUCCESS", GREEN);
            lcd_show_string(50, 130, 200, 24, LCD_FONT_24, (char*)"GATE OPEN", BLUE);
            
            set_servo_angle(90); 
            
            unsigned long wait_exit_gate = millis();
            while(millis() - wait_exit_gate < 3000) { yield(); delay(10); }
            Serial.println("🔴 [系统] 车辆已离场，正在落杆");
            ui_radar_mode(); 
        }
    }

    // ================== 🌟 5. 主道闸雷达检测 ==================
    if (system_state == 0) { 
        digitalWrite(TRIG_PIN, LOW); delayMicroseconds(2); digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10); digitalWrite(TRIG_PIN, LOW);
        float dist = pulseIn(ECHO_PIN, HIGH, 30000) * 0.034 / 2;
        if (dist > 0.1 && dist < 400.0) { 
            // =========================================================================
            // 【修改点 1】主道闸触发拍照测距阈值从 <= 10.0 厘米 修改为 <= 15.0 厘米
            // =========================================================================
            if (dist <= 15.0) {
                stable_count++;
                if (stable_count >= 2) {
                    stable_count = 0; system_state = 1; state_timer = millis(); 
                    
                    // 同步修改了这里的串口日志提示文字，反映 15cm 的修改
                    Serial.println("🔔 [雷达] 发现车辆驶近主道闸(<=15cm)，触发摄像头拍照！"); 
                    set_flash_light(true); 
                    
                    lcd_clear(WHITE);
                    lcd_show_string(40, 120, 200, 24, LCD_FONT_24, (char*)"SCANNING...", RED);
                }
            } else { stable_count = 0; }
            // =========================================================================
        }
        delay(50); 
    } 
    else if (system_state == 1) { 
        if (millis() - state_timer > 15000) {
            Serial.println("⚠️ [雷达] 车辆滞留过久或已倒车离开，取消拍照");
            ui_radar_mode(); 
        }
        else if (millis() - last_photo_time > 3000) { takeAndSendPhoto(); last_photo_time = millis(); }
    } 
    else if (system_state == 2) { 
        if (millis() - state_timer > 10000) ui_radar_mode();
    }
}