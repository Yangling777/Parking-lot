/**
 ****************************************************************************************************
 * @file        camera.c
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

#include "camera.h"
#include "esp_camera.h"
#include "spilcd.h"
#include "xl9555.h"

camera_fb_t *fb = NULL;   /* 定义一个指向camera_fb_t变量的指针(camera_fb_t结构体存放图像缓冲区相关信息) */

/**
 * @brief       摄像头(OV5640 / OV2640)初始化
 * @param       无
 * @retval      0:表示初始化成功 / 1:表示失败 
 */
uint8_t camera_init(void)
{
    camera_config_t camera_config;

    camera_config.ledc_channel = LEDC_CHANNEL_0;  /* 产生XCLK时钟通道 */
    camera_config.ledc_timer = LEDC_TIMER_0;      /* 产生XCLK时钟的定时器  */
    camera_config.xclk_freq_hz = 24000000;        /* 设定外部时钟频率24M */

    camera_config.pin_d7 = OV_D7_PIN;             /* 数据线7 */
    camera_config.pin_d6 = OV_D6_PIN;             /* 数据线6 */
    camera_config.pin_d5 = OV_D5_PIN;             /* 数据线5 */
    camera_config.pin_d4 = OV_D4_PIN;             /* 数据线4 */
    camera_config.pin_d3 = OV_D3_PIN;             /* 数据线3 */
    camera_config.pin_d2 = OV_D2_PIN;             /* 数据线2 */
    camera_config.pin_d1 = OV_D1_PIN;             /* 数据线1 */
    camera_config.pin_d0 = OV_D0_PIN;             /* 数据线0 */

    camera_config.pin_xclk  = OV_XCLK_PIN;        /* 外部时钟脚 */ 
    camera_config.pin_pclk  = OV_PCLK_PIN;        /* 像素时钟脚 */
    camera_config.pin_vsync = OV_VSYNC_PIN;       /* 垂直同步脚  */
    camera_config.pin_href  = OV_HREF_PIN;        /* 水平同步脚 */

    camera_config.pin_sscb_sda = OV_SDA_PIN;      /* SCCB数据线 */
    camera_config.pin_sscb_scl = OV_SCL_PIN;      /* SCCB时钟线 */

    camera_config.pin_pwdn  = OV_PWDN_PIN;        /* 断电引脚 */
    camera_config.pin_reset = OV_RESET_PIN;       /* 复位引脚 */
    
    camera_config.frame_size   = FRAMESIZE_VGA;  /* 图像大小 */  
    camera_config.pixel_format = PIXFORMAT_JPEG;/* 设置图像格式 */
    camera_config.grab_mode    = CAMERA_GRAB_LATEST;      /* 始终获取最新帧 */
    camera_config.fb_location  = CAMERA_FB_IN_PSRAM;      /* 摄像头图像缓冲区存放位置 */

    camera_config.jpeg_quality = 12;              /* 设置JPEG图像画质(0~63,数字越低画质越高) */
    camera_config.fb_count     = 2;               /* 图像缓冲区数量，双缓冲提升帧率 */            

    if (spilcd_dir == 0)      /* 竖屏情况下,只能显示240*240分辨率的图像 */
    {
        camera_config.frame_size   = FRAMESIZE_240X240; 
    }

    if (OV_PWDN_PIN == -1)                        /* 摄像头上电 */  
    {
        xl9555_io_config(OV_PWDN, IO_SET_OUTPUT);   /* PWDN引脚用了XL9555的IO */
        xl9555_pin_set(OV_PWDN, IO_SET_LOW);        /* 上电 */
    } 

    if (OV_RESET_PIN == -1)                       /* 硬件复位 */
    { 
        xl9555_io_config(OV_RESET, IO_SET_OUTPUT);  /* RESET引脚用了XL9555的IO */
        xl9555_pin_set(OV_RESET, IO_SET_LOW);
        delay(20);
        xl9555_pin_set(OV_RESET, IO_SET_HIGH);
        delay(20);
    } 

    esp_err_t err =  esp_camera_init(&camera_config);   /* 摄像头初始化 */
    if (err != ESP_OK) 
    {
        Serial.printf("摄像头初始化失败,错误码:0x%x", err);
        return 1;
    }

    sensor_t * s = esp_camera_sensor_get();             /* 获取摄像头信息 */
    Serial.printf("摄像头ID:%#x  \r\n", s->id.PID);      /* 打印摄像头ID */
    
    s->set_brightness(s, 0);      /* 设置亮度 (-2 ~ 2) */         
    s->set_contrast(s, 0);        /* 设置对比度 (-2 ~ 2) */
    s->set_saturation(s, 0);      /* 设置饱和度 (-2 ~ 2) */
    s->set_hmirror(s, 0);         /* 不设置水平方向翻转 */
    s->set_vflip(s, 1);           /* 设置垂直方向翻转 */

    if (s->id.PID == OV2640_PID)
    {
        s->set_vflip(s, 0);       /* 不设置垂直方向翻转 */
    }

    return 0;
}

/**
 * @brief       LCD显示摄像头捕获数据
 * @param       无
 * @retval      0:成功 / 1:画面获取有问题 
 */
uint8_t camera_capture_show(void)
{
  fb = esp_camera_fb_get();                     /* 捕获一帧图像数据 */
  if (!fb) 
  {
      Serial.printf("无法获得图像数据 \r\n");
      return 1;
  }

  if (spilcd_dir == 1)                          /* 横屏情况下,显示320*240分辨率的图像 */
  {
      lcd_show_pic(0, 0, 320, 240, fb->buf);    /* 画面全屏显示 */
  }
  else                                          /* 竖屏情况下,显示240*240分辨率的图像 */
  {
      lcd_show_pic(0, 39, 240, 240, fb->buf);   /* 画面居中显示 */
  }

  esp_camera_fb_return(fb);                     /* 清除摄像头缓存 */
  fb = NULL;

  return 0;
}


