/**
 * STM32 智能停车场下位机固件
 * 功能: 超声波车位检测 + 舵机闸机 + LED指示灯 + UART通信
 *
 * 硬件配置 (以 STM32F103C8T6 为例):
 *   - PA0: 超声波 Trig (车位1)
 *   - PA1: 超声波 Echo (车位1)
 *   - PA6: 超声波 Trig (车位2)
 *   - PA7: 超声波 Echo (车位2)
 *   - PB0: 舵机 PWM (闸机)
 *   - PB12: LED 绿灯
 *   - PB13: LED 红灯
 *   - PB14: LED 黄灯
 *   - USART1: 与 ESP32 通信 (PA9-TX, PA10-RX)
 *   - 更多车位通过移位寄存器扩展
 */

#include "stm32f1xx_hal.h"
#include <string.h>
#include <stdio.h>

/* ---- 常量定义 ---- */
#define MAX_SLOTS         8       // 最大管理车位数
#define TRIG_PULSE_US     10      // 超声波触发脉冲 10us
#define DISTANCE_THRESHOLD 50.0f  // 距离阈值 (cm)，小于此值认为有车
#define SONIC_INTERVAL_MS 200     // 超声波轮询间隔 (ms)
#define SERVO_OPEN_ANGLE  900     // 闸机打开角度 (0.5ms-2.5ms 对应 0-1800)
#define SERVO_CLOSE_ANGLE 500     // 闸机关闭角度
#define UART_RX_BUF_SIZE  64      // UART 接收缓冲区

/* ---- 舵机占空比参数 (TIM2, 50Hz) ---- */
#define SERVO_TIM_PERIOD  19999   // 72MHz / (71+1) / 20000 = 50Hz
#define ANGLE_TO_PULSE(a) ((a) * 2000 / 1800 + 500)

/* ---- 数据结构 ---- */
typedef struct {
    GPIO_TypeDef *trig_port;
    uint16_t      trig_pin;
    GPIO_TypeDef *echo_port;
    uint16_t      echo_pin;
    float         distance_cm;
    uint8_t       occupied;       // 0=空闲, 1=占用
    uint32_t      last_measure_ms;
} SonicSensor;

typedef struct {
    uint8_t   angle;              // 当前角度 0-180
    uint8_t   state;              // 0=关闭, 1=打开中, 2=打开, 3=关闭中
    uint32_t  open_timestamp;     // 打开时刻
} GateServo;

typedef enum {
    LED_OFF = 0,
    LED_GREEN,
    LED_RED,
    LED_YELLOW,
    LED_BLINK_GREEN,
    LED_BLINK_RED
} LedMode;

typedef struct {
    uint8_t   mode;
    uint32_t  blink_last_toggle;
    uint16_t  blink_interval_ms;
} LedStatus;

/* ---- 全局变量 ---- */
static SonicSensor sensors[MAX_SLOTS];
static GateServo   gate;
static LedStatus   led_status;
static UART_HandleTypeDef huart1;
static TIM_HandleTypeDef  htim2, htim3;
static char        uart_rx_buf[UART_RX_BUF_SIZE];
static uint8_t     uart_rx_idx;
static uint32_t    sys_tick_count;

/* ---- 函数声明 ---- */
static void SystemClock_Config(void);
static void GPIO_Init(void);
static void TIM2_Init(void);       // 舵机 PWM
static void TIM3_Init(void);       // 超声波定时器
static void USART1_Init(void);
static void Sonic_Init(void);
static float Sonic_Measure(SonicSensor *s);
static void Gate_SetAngle(uint16_t pulse);
static void Gate_Open(void);
static void Gate_Close(void);
static void Led_SetMode(LedMode mode);
static void Led_Process(void);
static void UART_ProcessCommand(const char *cmd);
static void UART_SendStatus(void);
static void delay_us(uint32_t us);

/* ---- 超声波传感器初始化 ---- */
static void Sonic_Init(void) {
    const struct { GPIO_TypeDef *port; uint16_t trig; uint16_t echo; } pins[MAX_SLOTS] = {
        {GPIOA, GPIO_PIN_0, GPIO_PIN_1},   // 车位1
        {GPIOA, GPIO_PIN_6, GPIO_PIN_7},   // 车位2
        {GPIOB, GPIO_PIN_6, GPIO_PIN_7},   // 车位3
        {GPIOB, GPIO_PIN_8, GPIO_PIN_9},   // 车位4
    };
    for (int i = 0; i < MAX_SLOTS; i++) {
        sensors[i].trig_port     = pins[i].port;
        sensors[i].trig_pin      = pins[i].trig;
        sensors[i].echo_port     = pins[i].port;
        sensors[i].echo_pin      = pins[i].echo;
        sensors[i].distance_cm   = 300.0f;
        sensors[i].occupied      = 0;
        sensors[i].last_measure_ms = 0;
    }
}

/* ---- 超声波测距 (单次) ---- */
static float Sonic_Measure(SonicSensor *s) {
    uint32_t start_tick, end_tick;

    // 发送 10us 触发脉冲
    HAL_GPIO_WritePin(s->trig_port, s->trig_pin, GPIO_PIN_SET);
    delay_us(TRIG_PULSE_US);
    HAL_GPIO_WritePin(s->trig_port, s->trig_pin, GPIO_PIN_RESET);

    // 等待 Echo 上升沿，超时 25ms
    uint32_t timeout = 25000;
    while (HAL_GPIO_ReadPin(s->echo_port, s->echo_pin) == GPIO_PIN_RESET) {
        if (--timeout == 0) return 300.0f;
    }
    start_tick = HAL_GetTick();
    __disable_irq();
    TIM3->CNT = 0;
    __enable_irq();

    // 等待 Echo 下降沿
    timeout = 25000;
    while (HAL_GPIO_ReadPin(s->echo_port, s->echo_pin) == GPIO_PIN_SET) {
        if (--timeout == 0) return 300.0f;
    }
    __disable_irq();
    end_tick = TIM3->CNT;
    __enable_irq();

    // 计算距离: distance = (高电平时间 * 声速) / 2
    float pulse_us = (float)end_tick;   // TIM3 预分频后 1us 计数
    return pulse_us * 0.0343f / 2.0f;  // cm
}

/* ---- 用户速延迟 (微秒级) ---- */
static void delay_us(uint32_t us) {
    uint32_t start = HAL_GetTick() * 1000;
    while (1) {
        uint32_t now = HAL_GetTick() * 1000;
        if (now - start >= us) break;
    }
}

/* ---- 舵机控制 ---- */
static void Gate_SetAngle(uint16_t pulse) {
    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, pulse);
}

static void Gate_Open(void) {
    Gate_SetAngle(ANGLE_TO_PULSE(SERVO_OPEN_ANGLE));
    gate.state = 1;
    gate.open_timestamp = HAL_GetTick();
    Led_SetMode(LED_GREEN);
}

static void Gate_Close(void) {
    Gate_SetAngle(ANGLE_TO_PULSE(SERVO_CLOSE_ANGLE));
    gate.state = 0;
    gate.open_timestamp = 0;
    Led_SetMode(LED_OFF);
}

/* ---- LED 控制 ---- */
static void Led_SetMode(LedMode mode) {
    led_status.mode = mode;
    led_status.blink_last_toggle = HAL_GetTick();
    led_status.blink_interval_ms = 500;
}

static void Led_Process(void) {
    uint32_t now = HAL_GetTick();
    switch (led_status.mode) {
        case LED_GREEN:
            HAL_GPIO_WritePin(GPIOB, GPIO_PIN_12, GPIO_PIN_SET);
            HAL_GPIO_WritePin(GPIOB, GPIO_PIN_13, GPIO_PIN_RESET);
            HAL_GPIO_WritePin(GPIOB, GPIO_PIN_14, GPIO_PIN_RESET);
            break;
        case LED_RED:
            HAL_GPIO_WritePin(GPIOB, GPIO_PIN_12, GPIO_PIN_RESET);
            HAL_GPIO_WritePin(GPIOB, GPIO_PIN_13, GPIO_PIN_SET);
            HAL_GPIO_WritePin(GPIOB, GPIO_PIN_14, GPIO_PIN_RESET);
            break;
        case LED_YELLOW:
            HAL_GPIO_WritePin(GPIOB, GPIO_PIN_12, GPIO_PIN_RESET);
            HAL_GPIO_WritePin(GPIOB, GPIO_PIN_13, GPIO_PIN_RESET);
            HAL_GPIO_WritePin(GPIOB, GPIO_PIN_14, GPIO_PIN_SET);
            break;
        case LED_BLINK_GREEN:
            if (now - led_status.blink_last_toggle > led_status.blink_interval_ms) {
                HAL_GPIO_TogglePin(GPIOB, GPIO_PIN_12);
                HAL_GPIO_WritePin(GPIOB, GPIO_PIN_13, GPIO_PIN_RESET);
                led_status.blink_last_toggle = now;
            }
            break;
        case LED_BLINK_RED:
            if (now - led_status.blink_last_toggle > led_status.blink_interval_ms) {
                HAL_GPIO_TogglePin(GPIOB, GPIO_PIN_13);
                HAL_GPIO_WritePin(GPIOB, GPIO_PIN_12, GPIO_PIN_RESET);
                led_status.blink_last_toggle = now;
            }
            break;
        default: // LED_OFF
            HAL_GPIO_WritePin(GPIOB, GPIO_PIN_12, GPIO_PIN_RESET);
            HAL_GPIO_WritePin(GPIOB, GPIO_PIN_13, GPIO_PIN_RESET);
            HAL_GPIO_WritePin(GPIOB, GPIO_PIN_14, GPIO_PIN_RESET);
            break;
    }
}

/* ---- UART 命令处理 ---- */
static void UART_ProcessCommand(const char *cmd) {
    char response[64];
    char prefix[8];
    int val1 = 0, val2 = 0;
    sscanf(cmd, "%7[^:]:%d,%d", prefix, &val1, &val2);

    if (strncmp(prefix, "GATE", 4) == 0) {
        if (val1 == 1) {
            Gate_Open();
            sprintf(response, "OK GATE_OPEN\r\n");
        } else {
            Gate_Close();
            sprintf(response, "OK GATE_CLOSE\r\n");
        }
    }
    else if (strncmp(prefix, "LED", 3) == 0) {
        Led_SetMode((LedMode)val1);
        sprintf(response, "OK LED:%d\r\n", val1);
    }
    else if (strncmp(prefix, "PING", 4) == 0) {
        sprintf(response, "PONG %lu\r\n", HAL_GetTick());
    }
    else if (strncmp(prefix, "TIME", 4) == 0) {
        sprintf(response, "OK TIME\r\n");
    }
    else {
        sprintf(response, "ERR UNKNOWN\r\n");
    }

    HAL_UART_Transmit(&huart1, (uint8_t *)response, strlen(response), 100);
}

/* ---- 传感器状态上报 ---- */
static void UART_SendStatus(void) {
    char msg[128];
    for (int i = 0; i < MAX_SLOTS; i++) {
        int len = sprintf(msg, "SENSOR|%03d|%.1f|%d\r\n",
                          i + 1, sensors[i].distance_cm, sensors[i].occupied);
        HAL_UART_Transmit(&huart1, (uint8_t *)msg, len, 100);
    }
}

/* ---- UART 接收回调 ---- */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart) {
    if (huart->Instance == USART1) {
        char ch = uart_rx_buf[uart_rx_idx];
        if (ch == '\n' || ch == '\r') {
            if (uart_rx_idx > 0) {
                uart_rx_buf[uart_rx_idx] = '\0';
                UART_ProcessCommand(uart_rx_buf);
                uart_rx_idx = 0;
            }
        } else {
            uart_rx_idx++;
            if (uart_rx_idx >= UART_RX_BUF_SIZE) uart_rx_idx = 0;
        }
        HAL_UART_Receive_IT(&huart1, (uint8_t *)&uart_rx_buf[uart_rx_idx], 1);
    }
}

/* ---- 硬件初始化 ---- */
static void GPIO_Init(void) {
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    GPIO_InitTypeDef g = {0};

    // 超声波 Trig (输出)
    g.Pin = GPIO_PIN_0 | GPIO_PIN_6;
    g.Mode = GPIO_MODE_OUTPUT_PP;
    g.Pull = GPIO_NOPULL;
    g.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOA, &g);

    g.Pin = GPIO_PIN_6 | GPIO_PIN_8;
    HAL_GPIO_Init(GPIOB, &g);

    // 超声波 Echo (输入)
    g.Pin = GPIO_PIN_1 | GPIO_PIN_7;
    g.Mode = GPIO_MODE_INPUT;
    HAL_GPIO_Init(GPIOA, &g);

    g.Pin = GPIO_PIN_7 | GPIO_PIN_9;
    HAL_GPIO_Init(GPIOB, &g);

    // LED 输出
    g.Pin = GPIO_PIN_12 | GPIO_PIN_13 | GPIO_PIN_14;
    g.Mode = GPIO_MODE_OUTPUT_PP;
    HAL_GPIO_Init(GPIOB, &g);
}

static void TIM2_Init(void) {
    __HAL_RCC_TIM2_CLK_ENABLE();
    htim2.Instance = TIM2;
    htim2.Init.Prescaler = 71;
    htim2.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim2.Init.Period = SERVO_TIM_PERIOD;
    htim2.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    HAL_TIM_PWM_Init(&htim2);

    TIM_OC_InitTypeDef oc = {0};
    oc.OCMode = TIM_OCMODE_PWM1;
    oc.Pulse = ANGLE_TO_PULSE(SERVO_CLOSE_ANGLE);
    oc.OCPolarity = TIM_OCPOLARITY_HIGH;
    oc.OCFastMode = TIM_OCFAST_DISABLE;
    HAL_TIM_PWM_ConfigChannel(&htim2, &oc, TIM_CHANNEL_1);
    HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_1);
}

static void TIM3_Init(void) {
    __HAL_RCC_TIM3_CLK_ENABLE();
    htim3.Instance = TIM3;
    htim3.Init.Prescaler = 71;          // 72MHz / 72 = 1MHz (1us)
    htim3.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim3.Init.Period = 0xFFFF;
    htim3.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    HAL_TIM_Base_Init(&htim3);
    HAL_TIM_Base_Start(&htim3);
}

static void USART1_Init(void) {
    __HAL_RCC_USART1_CLK_ENABLE();
    huart1.Instance = USART1;
    huart1.Init.BaudRate = 115200;
    huart1.Init.WordLength = UART_WORDLENGTH_8B;
    huart1.Init.StopBits = UART_STOPBITS_1;
    huart1.Init.Parity = UART_PARITY_NONE;
    huart1.Init.Mode = UART_MODE_TX_RX;
    HAL_UART_Init(&huart1);
    HAL_UART_Receive_IT(&huart1, (uint8_t *)&uart_rx_buf[0], 1);
}

static void SystemClock_Config(void) {
    RCC_OscInitTypeDef osc = {0};
    RCC_ClkInitTypeDef clk = {0};
    osc.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    osc.HSEState = RCC_HSE_ON;
    osc.HSEPredivValue = RCC_HSE_PREDIV_DIV1;
    osc.PLL.PLLState = RCC_PLL_ON;
    osc.PLL.PLLSource = RCC_PLLSOURCE_HSE;
    osc.PLL.PLLMUL = RCC_PLL_MUL9;      // 8MHz * 9 = 72MHz
    HAL_RCC_OscConfig(&osc);
    clk.ClockType = RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    clk.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    clk.AHBCLKDivider = RCC_SYSCLK_DIV1;
    clk.APB1CLKDivider = RCC_HCLK_DIV2;
    clk.APB2CLKDivider = RCC_HCLK_DIV1;
    HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_2);
}

/* ---- 主函数 ---- */
int main(void) {
    HAL_Init();
    SystemClock_Config();
    GPIO_Init();
    USART1_Init();
    TIM2_Init();
    TIM3_Init();
    Sonic_Init();

    Gate_Close();
    Led_SetMode(LED_RED);

    uint32_t last_sensor_report = 0;
    uint32_t last_sensor_measure[MAX_SLOTS] = {0};
    uint8_t  current_sensor = 0;

    char boot_msg[] = "STM32 Parking Controller Ready\r\n";
    HAL_UART_Transmit(&huart1, (uint8_t *)boot_msg, strlen(boot_msg), 100);

    while (1) {
        uint32_t now = HAL_GetTick();

        // 轮询超声波传感器
        if (now - last_sensor_measure[current_sensor] > SONIC_INTERVAL_MS) {
            sensors[current_sensor].distance_cm = Sonic_Measure(&sensors[current_sensor]);
            sensors[current_sensor].occupied =
                (sensors[current_sensor].distance_cm < DISTANCE_THRESHOLD) ? 1 : 0;
            sensors[current_sensor].last_measure_ms = now;
            last_sensor_measure[current_sensor] = now;

            current_sensor++;
            if (current_sensor >= MAX_SLOTS) current_sensor = 0;
        }

        // 定期上报传感器状态 (每 2 秒)
        if (now - last_sensor_report > 2000) {
            UART_SendStatus();
            last_sensor_report = now;
        }

        // LED 闪烁处理
        Led_Process();

        // 闸机超时自动关
        if (gate.state == 1 && (now - gate.open_timestamp > 5000)) {
            Gate_Close();
        }

        HAL_Delay(10);
    }
}
