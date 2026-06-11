/**
 ****************************************************************************************************
 * @file        xl9555.cpp
 * @author      正点原子团队(ALIENTEK)
 * @version     V1.0
 * @date        2023-12-01
 * @brief       xl9555 驱动代码
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

#include "xl9555.h"
#include "driver/i2c.h"  // 使用ESP32底层I2C驱动

#define I2C_MASTER_NUM      I2C_NUM_1       // 使用I2C1
#define I2C_MASTER_TIMEOUT_MS  1000

static bool i2c_initialized = false;

/**
 * @brief 初始化底层I2C
 */
static void xl9555_i2c_init(void)
{
    if (i2c_initialized) {
        return;
    }

    i2c_config_t conf = {};
    conf.mode = I2C_MODE_MASTER;
    conf.sda_io_num = IIC_SDA;
    conf.scl_io_num = IIC_SCL;
    conf.sda_pullup_en = GPIO_PULLUP_ENABLE;
    conf.scl_pullup_en = GPIO_PULLUP_ENABLE;
    conf.master.clk_speed = 400000;
    conf.clk_flags = 0;

    i2c_param_config(I2C_MASTER_NUM, &conf);
    i2c_driver_install(I2C_MASTER_NUM, conf.mode, 0, 0, 0);

    i2c_initialized = true;
}

/**
* @brief       初始化IO扩展芯片
* @param       无
* @retval      无
*/
void xl9555_init(void)
{
    pinMode(IIC_INT_PIN, INPUT_PULLUP);

    // 使用底层I2C驱动，不会与esp_camera冲突
    xl9555_i2c_init();

    // 清除中断标志
    xl9555_read_port(0);
    xl9555_read_port(1);
}

/**
 * @brief      向XL9555相关寄存器写数据
 * @param      reg    : 寄存器地址
 * @param      data   : 写入到寄存器的数据
 * @retval     无
 */
void xl9555_write_reg(uint8_t reg, uint8_t data)
{
    xl9555_i2c_init();  // 确保I2C已初始化

    i2c_cmd_handle_t cmd = i2c_cmd_link_create();
    i2c_master_start(cmd);
    i2c_master_write_byte(cmd, (EXIO_ADDR << 1) | I2C_MASTER_WRITE, true);
    i2c_master_write_byte(cmd, reg, true);
    i2c_master_write_byte(cmd, data, true);
    i2c_master_stop(cmd);
    i2c_master_cmd_begin(I2C_MASTER_NUM, cmd, pdMS_TO_TICKS(I2C_MASTER_TIMEOUT_MS));
    i2c_cmd_link_delete(cmd);
}

/**
 * @brief       向XL9555相关寄存器读取数据
 * @param       reg    : 寄存器地址
 * @retval      寄存器的值 / 0xFF:未接收到数据
 */
uint8_t xl9555_read_reg(uint8_t reg)
{
    xl9555_i2c_init();  // 确保I2C已初始化

    uint8_t data = 0xFF;
    i2c_cmd_handle_t cmd = i2c_cmd_link_create();

    // 写寄存器地址
    i2c_master_start(cmd);
    i2c_master_write_byte(cmd, (EXIO_ADDR << 1) | I2C_MASTER_WRITE, true);
    i2c_master_write_byte(cmd, reg, true);

    // 读数据
    i2c_master_start(cmd);
    i2c_master_write_byte(cmd, (EXIO_ADDR << 1) | I2C_MASTER_READ, true);
    i2c_master_read_byte(cmd, &data, I2C_MASTER_NACK);
    i2c_master_stop(cmd);

    i2c_master_cmd_begin(I2C_MASTER_NUM, cmd, pdMS_TO_TICKS(I2C_MASTER_TIMEOUT_MS));
    i2c_cmd_link_delete(cmd);

    return data;
}

/**
 * @brief       设置XL9555的P0或P1端口的输出状态
 * @param       portx : P0 / P1
 * @param       data  : IO的状态(对应8个IO)
 * @retval      无
 */
void xl9555_write_port(uint8_t portx, uint8_t data)
{
    xl9555_write_reg(portx ? XL9555_OUTPUT_PORT1_REG : XL9555_OUTPUT_PORT0_REG, data);
}

/**
 * @brief       读取XL9555的P0或P1端口的状态
 * @param       portx : P0 / P1
 * @retval      IO的状态(对应8个IO)
 */
uint8_t xl9555_read_port(uint8_t portx)
{
    return xl9555_read_reg(portx ? XL9555_INPUT_PORT1_REG : XL9555_INPUT_PORT0_REG);
}

/**
 * @brief       设置XL9555某个IO的模式(输出或输入)
 * @param       port_pin  : 要设置的IO编号,P0~7或P1~7
 * @param       mode      : IO_SET_OUTPUT / IO_SET_INPUT
 * @retval      无
 */
void xl9555_io_config(uint16_t port_pin, io_mode_t mode)
{
    uint8_t config_reg = 0;
    uint8_t config_value = 0;

    config_reg  = xl9555_read_reg(port_pin > XL_PORT0_ALL_PIN ? XL9555_CONFIG_PORT1_REG : XL9555_CONFIG_PORT0_REG);   /* 先读取设置Pin所在的寄存器情况 */

    if (mode == IO_SET_OUTPUT)    /* 根据 mode参数 设置输入输出情况，不能影响其他IO */
    {
        config_value = config_reg & (~(port_pin >> (port_pin > XL_PORT0_ALL_PIN ? 8 : 0)));   /* 得到某个IO设置为输出功能后的PORT值但不影响未设置的其他IO的状态 */
    }
    else
    {
        config_value = config_reg | (port_pin >> (port_pin > XL_PORT0_ALL_PIN ? 8 : 0));      /* 得到某个IO设置为输入功能的PORT值但不影响未设置的其他IO的状态 */
    }

    xl9555_write_reg(port_pin > XL_PORT0_ALL_PIN ? XL9555_CONFIG_PORT1_REG : XL9555_CONFIG_PORT0_REG, config_value);    /* 向配置寄存器设置IO输入输出状态 */
}

/**
 * @brief       设置XL9555配置为输出功能的IO的输出状态(高电平或低电平)
 * @param       port_pin  : 已经设置好输出功能的IO编号
 * @param       state      : IO_SET_LOW / IO_SET_HIGH
 * @retval      无
 */
void xl9555_pin_set(uint16_t port_pin, io_state_t state)
{
    uint8_t pin_reg = 0;
    uint8_t pin_value = 0;

    pin_reg = xl9555_read_reg(port_pin > XL_PORT0_ALL_PIN ? XL9555_OUTPUT_PORT1_REG : XL9555_OUTPUT_PORT0_REG);     /* 先读取设置Pin所在的寄存器情况 */

    if (state == IO_SET_HIGH)    /* 根据 state参数 设置IO的高低电平 */
    {
        pin_value = pin_reg | (port_pin >> (port_pin > XL_PORT0_ALL_PIN ? 8 : 0));          /* 得到某个IO设置为高电平后的PORT值但不影响未设置的其他IO的状态 */
    }
    else
    {
        pin_value = pin_reg & (~(port_pin >> (port_pin > XL_PORT0_ALL_PIN ? 8 : 0)));       /* 得到某个IO设置为低电平后的PORT值但不影响未设置的其他IO的状态 */
    }

    xl9555_write_reg(port_pin > XL_PORT0_ALL_PIN ? XL9555_OUTPUT_PORT1_REG : XL9555_OUTPUT_PORT0_REG, pin_value);   /* 向输出寄存器设置IO高低电平状态 */
}

/**
 * @brief       获取XL9555配置为输入功能的IO的状态(高电平或低电平)
 * @param       port_pin  : 已经设置好输入功能的IO编号
 * @retval      0低电平 / 1高电平
 */
uint8_t xl9555_get_pin(uint16_t port_pin)
{
    uint8_t pin_state = 0;
    uint8_t port_value = 0;

    port_value = xl9555_read_reg(port_pin > XL_PORT0_ALL_PIN ? XL9555_INPUT_PORT1_REG : XL9555_INPUT_PORT0_REG);  /* 读取pin所在port的状态：1没有按下，0按下 */
    pin_state = port_pin >> (port_pin > XL_PORT0_ALL_PIN ? 8 : 0);    /* 假如是PORT1的PIN需要先右移8位 */
    pin_state = pin_state & port_value;                               /* 得到需要查询位的状态 */

    return pin_state ? 1 : 0;
}
