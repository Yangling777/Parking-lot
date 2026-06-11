"""
生成智能停车场管理系统项目设计书 Word 文档
"""
import os
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

def set_cell_shading(cell, color):
    """设置单元格背景色"""
    shading_elm = OxmlElement('w:shd')
    shading_elm.set(qn('w:fill'), color)
    shading_elm.set(qn('w:val'), 'clear')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def set_cell_border(cell, **kwargs):
    """设置单元格边框"""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement('w:tcBorders')
    for edge, val in kwargs.items():
        element = OxmlElement(f'w:{edge}')
        element.set(qn('w:val'), val.get('val', 'single'))
        element.set(qn('w:sz'), val.get('sz', '4'))
        element.set(qn('w:color'), val.get('color', '000000'))
        element.set(qn('w:space'), '0')
        tcBorders.append(element)
    tcPr.append(tcBorders)

def add_styled_table(doc, headers, rows, col_widths=None):
    """添加带样式的表格"""
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = 'Table Grid'

    # 表头
    for i, header in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = header
        for paragraph in cell.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in paragraph.runs:
                run.bold = True
                run.font.size = Pt(10)
                run.font.color.rgb = RGBColor(255, 255, 255)
        set_cell_shading(cell, '2B579A')

    # 数据行
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            cell = table.rows[r + 1].cells[c]
            cell.text = str(val)
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(9)
            if r % 2 == 1:
                set_cell_shading(cell, 'F2F6FC')

    if col_widths:
        for i, width in enumerate(col_widths):
            for row in table.rows:
                row.cells[i].width = Cm(width)

    return table

def generate_doc():
    doc = Document()

    # ===== 页面设置 =====
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(3.18)
    section.right_margin = Cm(3.18)

    # ===== 样式设置 =====
    style = doc.styles['Normal']
    style.font.name = '宋体'
    style.font.size = Pt(12)
    style.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    style.paragraph_format.line_spacing = 1.5
    style.paragraph_format.space_after = Pt(6)

    # Heading 样式
    for i in range(1, 4):
        h_style = doc.styles[f'Heading {i}']
        h_style.font.name = '黑体'
        h_style.element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
        h_style.font.color.rgb = RGBColor(0x1D, 0x1D, 0x1F)
        if i == 1:
            h_style.font.size = Pt(22)
        elif i == 2:
            h_style.font.size = Pt(16)
        else:
            h_style.font.size = Pt(14)

    # ================================================================
    # 封面
    # ================================================================
    for _ in range(6):
        doc.add_paragraph()

    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title_para.add_run('智能停车场管理系统')
    run.font.name = '黑体'
    run.element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
    run.font.size = Pt(36)
    run.font.color.rgb = RGBColor(0x2B, 0x57, 0x9A)
    run.bold = True

    subtitle_para = doc.add_paragraph()
    subtitle_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle_para.add_run('项 目 设 计 书')
    run.font.name = '黑体'
    run.element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
    run.font.size = Pt(26)
    run.font.color.rgb = RGBColor(0x1D, 0x1D, 0x1F)

    doc.add_paragraph()
    doc.add_paragraph()

    info_lines = [
        ('版本号', 'V1.0'),
        ('编制日期', '2026年6月'),
        ('文档密级', '内部'),
    ]
    for label, value in info_lines:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(f'{label}：{value}')
        run.font.size = Pt(14)
        run.font.name = '宋体'
        run.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')

    doc.add_page_break()

    # ================================================================
    # 目录页（手动）
    # ================================================================
    doc.add_heading('目  录', level=1)
    toc_items = [
        ('一、项目概述', 3),
        ('二、系统总体架构', 4),
        ('三、车牌识别模块', 5),
        ('四、云端识别服务模块', 7),
        ('五、后端服务模块', 8),
        ('六、数据库模块', 9),
        ('七、AI预测与推荐模块', 10),
        ('八、前端模块', 11),
        ('九、硬件通信模块', 12),
        ('十、计费引擎模块', 13),
        ('十一、实时推送模块', 14),
        ('十二、部署与运维模块', 15),
        ('十三、测试方案', 16),
        ('十四、项目里程碑', 17),
    ]
    for item, page in toc_items:
        p = doc.add_paragraph()
        run = p.add_run(f'{item}{"." * (60 - len(item))}{page}')
        run.font.size = Pt(12)

    doc.add_page_break()

    # ================================================================
    # 一、项目概述
    # ================================================================
    doc.add_heading('一、项目概述', level=1)

    doc.add_heading('1.1 项目背景', level=2)
    doc.add_paragraph(
        '随着城市化进程加速，机动车保有量持续增长，传统停车场面临管理效率低下、车位利用率不高、'
        '人工收费易出错等问题。本项目旨在构建一套集车牌识别、智能推荐、实时监控、自动计费于一体的'
        '智能停车场管理系统，实现停车场无人化、智能化运营。'
    )

    doc.add_heading('1.2 项目目标', level=2)
    goals = [
        '实现车辆进出场的自动化车牌识别，识别准确率 > 95%',
        '构建 AI 车位推荐系统，缩短用户平均寻位时间 40% 以上',
        '实现分时段阶梯计费，支持新能源车优惠策略',
        '提供管理端实时大盘与数据报表，辅助运营决策',
        '支持硬件设备（闸机、摄像头、地磁传感器）的统一接入与监控',
    ]
    for g in goals:
        doc.add_paragraph(g, style='List Bullet')

    doc.add_heading('1.3 适用范围', level=2)
    doc.add_paragraph(
        '本系统适用于商业综合体、写字楼、住宅小区、医院等各类停车场景，'
        '支持 100-1000 个车位规模的单体或分布式停车场部署。'
    )

    # ================================================================
    # 二、系统总体架构
    # ================================================================
    doc.add_heading('二、系统总体架构', level=1)

    doc.add_heading('2.1 架构概览', level=2)
    doc.add_paragraph(
        '系统采用"边缘计算 + 云端服务 + Web前端"三层架构。边缘端由 K210 和 ESP32 组成，'
        '负责图像采集与本地识别；云端由 Flask/FastAPI 提供 RESTful API 和 WebSocket 服务；'
        '前端采用 Vue 3 构建 SPA 应用，通过 Nginx 部署。'
    )

    doc.add_heading('2.2 技术栈总览', level=2)
    add_styled_table(doc,
        ['层级', '技术选型', '说明'],
        [
            ['边缘识别', 'K210 (YOLO + OCR) + ESP32 (WiFi)', '车辆检测 + 车牌识别 + 数据上传'],
            ['云端识别', 'PaddleOCR / 腾讯云 OCR', '边缘失败时的兜底识别'],
            ['后端框架', 'Flask / FastAPI + SQLAlchemy', 'RESTful API + WebSocket'],
            ['数据库', 'PostgreSQL + Redis', '持久化存储 + 缓存'],
            ['AI引擎', 'LSTM / Prophet + 协同过滤', '流量预测 + 车位推荐'],
            ['前端', 'Vue 3 + Vite + Element Plus + ECharts', 'SPA 管理端 + 移动端适配'],
            ['实时通信', 'WebSocket (flask-socketio)', '车位状态实时推送'],
            ['部署', 'Docker + Gunicorn + Nginx', '容器化 + 反向代理'],
            ['测试', 'pytest + Playwright', '单元测试 + E2E 测试'],
            ['监控', 'Prometheus + Grafana + Sentry', '指标监控 + 异常追踪'],
        ],
        col_widths=[3, 7, 7]
    )

    doc.add_heading('2.3 系统数据流', level=2)
    doc.add_paragraph(
        '车辆入场：摄像头 → K210(YOLO检测车辆) → 传统CV(车牌定位) → KPU(字符识别) '
        '→ ESP32(WiFi上传) → 云端API → 模糊匹配注册车牌 → 分配车位 → 开闸放行 → 记录入库。'
    )
    doc.add_paragraph(
        '车辆出场：摄像头 → K210/云端OCR识别车牌 → 查找在停记录 → 计费引擎计算费用 '
        '→ 推送支付通知 → 支付确认 → 开闸放行 → 释放车位 → 更新记录。'
    )

    # ================================================================
    # 三、车牌识别模块（边缘端）
    # ================================================================
    doc.add_heading('三、车牌识别模块（边缘端）', level=1)

    doc.add_heading('3.1 硬件选型与分工', level=2)
    add_styled_table(doc,
        ['硬件', '型号', '职责', '说明'],
        [
            ['AI视觉芯片', 'K210 (Kendryte)', '运行YOLO车辆检测 + OCR字符识别', '内置KPU神经网络加速器，0.3TOPS算力'],
            ['通信控制', 'ESP32-S3', 'WiFi数据上传、闸机控制、OLED显示', '双核240MHz，内置WiFi/BLE'],
            ['摄像头', 'OV2640 / OV5640', '图像采集', '200万/500万像素，DVP接口连接K210'],
            ['补光灯', 'LED白光 + 红外', '夜间补光', '光敏电阻自动触发'],
        ],
        col_widths=[2.5, 3.5, 5.5, 5.5]
    )

    doc.add_heading('3.2 识别流水线', level=2)
    doc.add_paragraph('识别采用"先检测、再定位、后识别"的三步流水线架构：')

    steps = [
        ('第一步：车辆检测 (YOLO)',
         '在 K210 上部署 YOLOv2-tiny 或 MobileNet-SSD 目标检测模型。摄像头持续采集画面，'
         '模型实时检测画面中是否出现车辆。当车辆出现在预设的 ROI（感兴趣区域）内且连续 N 帧'
         '（默认3帧）检测到车辆时，判定为有效触发，进入抓拍阶段。该步骤的作用是过滤行人、'
         '非机动车等干扰，确保只在车辆到达最佳拍摄位置时才触发识别。'),
        ('第二步：车牌定位 (传统CV)',
         '对抓拍图像进行预处理（灰度化、高斯滤波），然后基于颜色空间分割提取蓝色/绿色/黄色区域。'
         '对候选区域进行轮廓检测、矩形拟合和长宽比筛选，定位出车牌精确位置。'
         '最后通过透视变换对倾斜车牌进行校正，输出端正的车牌图像。'),
        ('第三步：字符识别 (KPU CNN)',
         '将定位后的车牌图像送入 K210 的 KPU（神经网络处理器）运行轻量级 CNN 分类模型。'
         '模型对车牌上的每个字符逐一分类，输出完整车牌号及置信度。'
         '置信度 ≥ 0.85 判定识别成功，直接上传结果；置信度 < 0.85 判定失败，将原始图像上传至云端进行二次识别。'),
    ]
    for title, desc in steps:
        p = doc.add_paragraph()
        run = p.add_run(title)
        run.bold = True
        run.font.size = Pt(12)
        doc.add_paragraph(desc)

    doc.add_heading('3.3 算法实现要点', level=2)

    doc.add_paragraph('YOLO 车辆检测：', style='List Bullet')
    doc.add_paragraph(
        '使用 YOLOv2-tiny 网络结构（9层卷积），输入分辨率 224×224，输出 7×7×30 张量。'
        '在 K210 上使用 nncase 工具将训练好的模型量化为 INT8 格式以适配 KPU。'
        '检测类别包括：car（小汽车）、truck（卡车）、bus（公交车）。'
    )

    doc.add_paragraph('OCR 字符识别：', style='List Bullet')
    doc.add_paragraph(
        '使用 LeNet-5 改进版 CNN（3层卷积 + 2层全连接），输入 32×32 灰度字符图像，'
        '输出 65 类（31省份简称 + 24字母 + 10数字）。训练数据集使用 CCPD 公开数据集'
        '（约 30 万张真实车牌图片）进行预训练 + 现场场景数据微调。'
    )

    doc.add_heading('3.4 边缘-云端协同策略', level=2)
    add_styled_table(doc,
        ['场景', '处理方式'],
        [
            ['边缘识别置信度 ≥ 0.85', '直接上传结果（plate + confidence），无需云端介入'],
            ['边缘识别置信度 < 0.85', '上传原始 JPEG 图像到云端，触发云端 OCR 兜底'],
            ['边缘检测到车辆但车牌定位失败', '上传原始图像，标记为"定位失败"，云端优先尝试'],
            ['网络断开', '本地缓存识别结果，恢复连接后批量补传'],
            ['云端响应超时 (>8s)', '降级为边缘结果直接判决策（保守策略：拒绝入场，通知安保）'],
        ],
        col_widths=[6, 11]
    )

    # ================================================================
    # 四、云端识别服务模块
    # ================================================================
    doc.add_heading('四、云端识别服务模块', level=1)

    doc.add_heading('4.1 服务定位', level=2)
    doc.add_paragraph(
        '云端识别服务作为边缘识别的兜底方案，当边缘端识别置信度不足或定位失败时被触发。'
        '同时负责将识别结果与数据库中的注册车牌进行模糊匹配，以容忍 OCR 的个别字符误识别。'
    )

    doc.add_heading('4.2 云端 OCR 引擎', level=2)
    doc.add_paragraph(
        '主方案：自建 PaddleOCR 服务。使用 PaddleOCR 的 PP-OCRv4 模型，'
        '基于 14.6M 参数的高精度识别模型，在车牌场景上微调后部署为独立 OCR 微服务。'
    )
    doc.add_paragraph(
        '备用方案：腾讯云 OCR LicensePlateOCR API。当自建服务不可用时自动切换，'
        '确保识别链路高可用。API 密钥通过环境变量注入，定期轮换。'
    )

    doc.add_heading('4.3 模糊匹配机制', level=2)
    doc.add_paragraph(
        '识别结果与数据库中注册车牌列表进行逐一比对，使用 SequenceMatcher（difflib）'
        '计算字符串相似度。相似度阈值 0.70 以上认为匹配成功。匹配成功后返回注册车牌号'
        '（而非 OCR 原始结果），确保数据一致性。'
    )
    doc.add_paragraph(
        '特殊情况处理：同一识别结果匹配到多个注册车牌（相似度均 > 0.70）时，取最高分；'
        '若无匹配（相似度均 < 0.70），判定为未注册车辆，通知安保人工处理。'
    )

    doc.add_heading('4.4 多帧去抖机制', level=2)
    doc.add_paragraph(
        '避免单帧误判，采用滑动窗口去抖：维护最近 5 帧的识别结果队列，'
        '当同一车牌在队列中出现 ≥ 3 次时才确认输出。此机制有效过滤摄像头'
        '画面中的偶然噪声和误识别。'
    )

    # ================================================================
    # 五、后端服务模块
    # ================================================================
    doc.add_heading('五、后端服务模块', level=1)

    doc.add_heading('5.1 框架选型', level=2)
    doc.add_paragraph(
        '推荐使用 FastAPI 作为主框架，理由如下：(1) 原生异步支持，适配 WebSocket 和高并发场景；'
        '(2) 自动生成 OpenAPI 文档 (Swagger UI)，方便前后端联调；'
        '(3) Pydantic 数据校验，类型安全，减少入参校验代码；'
        '(4) 性能优于传统 Flask，接近 Node.js/Go。'
    )
    doc.add_paragraph(
        '若团队更熟悉 Flask，可使用 Flask + flask-restful 保持兼容，'
        '但需额外集成 marshmallow 做入参校验。'
    )

    doc.add_heading('5.2 核心中间件', level=2)
    add_styled_table(doc,
        ['中间件', '技术方案', '功能'],
        [
            ['认证鉴权', 'flask-jwt-extended / fastapi-jwt-auth', 'JWT access_token (15min) + refresh_token (7d)'],
            ['接口限流', 'flask-limiter / slowapi', '登录接口 5次/min，OCR上传 10次/s'],
            ['跨域处理', 'flask-cors / fastapi-cors', '白名单域名配置'],
            ['日志记录', 'structlog + RotatingFileHandler', '结构化日志，按日轮转，保留30天'],
            ['异常处理', '全局 error_handler 装饰器', '统一 JSON 错误响应格式 {code, message, data}'],
            ['入参校验', 'Pydantic / marshmallow', '所有接口入参类型校验 + 业务规则校验'],
        ],
        col_widths=[3, 6, 8]
    )

    doc.add_heading('5.3 分层架构', level=2)
    doc.add_paragraph(
        '路由层 (api/)：接收 HTTP 请求，解析参数，调用服务层，封装 JSON 响应。不包含业务逻辑。'
    )
    doc.add_paragraph(
        '服务层 (services/)：包含全部业务逻辑，如停车入场编排、计费计算、推荐算法调用。'
        '是系统的核心，所有单元测试围绕此层编写。'
    )
    doc.add_paragraph(
        '数据层 (models/)：SQLAlchemy ORM 模型定义，数据库操作封装。'
    )

    doc.add_heading('5.4 API 接口清单', level=2)
    add_styled_table(doc,
        ['模块', '接口', '方法', '说明'],
        [
            ['认证', '/api/auth/login', 'POST', '用户登录，返回 JWT token'],
            ['认证', '/api/auth/register', 'POST', '用户注册（待审批）'],
            ['认证', '/api/auth/refresh', 'POST', '刷新 access_token'],
            ['用户', '/api/user/info', 'GET', '获取个人信息'],
            ['用户', '/api/user/recommend', 'GET', '获取推荐车位'],
            ['用户', '/api/user/reserve', 'POST', '预约车位'],
            ['用户', '/api/user/records', 'GET', '我的停车记录'],
            ['用户', '/api/user/pay', 'POST', '支付停车费'],
            ['管理', '/api/admin/dashboard', 'GET', '管理端仪表盘数据'],
            ['管理', '/api/admin/users', 'GET', '用户列表'],
            ['管理', '/api/admin/approve', 'POST', '审批用户注册'],
            ['管理', '/api/admin/records', 'GET', '全部停车记录'],
            ['硬件', '/api/hardware/upload', 'POST', '边缘端上传识别结果/图像'],
            ['硬件', '/api/hardware/update_slot', 'POST', '地磁传感器上报车位状态'],
            ['硬件', '/api/hardware/heartbeat', 'POST', '设备心跳上报'],
        ],
        col_widths=[1.5, 5, 1.5, 9]
    )

    # ================================================================
    # 六、数据库模块
    # ================================================================
    doc.add_heading('六、数据库模块', level=1)

    doc.add_heading('6.1 数据库选型', level=2)
    add_styled_table(doc,
        ['组件', '选型', '用途'],
        [
            ['主数据库', 'PostgreSQL 16', '用户、车位、停车记录、计费规则等业务数据持久化'],
            ['缓存', 'Redis 7', '车位实时状态缓存、推荐结果缓存（TTL 60s）、JWT 黑名单'],
            ['消息队列', 'Redis Pub/Sub 或 RabbitMQ', 'WebSocket 跨进程广播、异步任务'],
        ],
        col_widths=[3, 4, 10]
    )

    doc.add_heading('6.2 核心数据表设计', level=2)
    add_styled_table(doc,
        ['表名', '核心字段', '说明'],
        [
            ['users', 'id, username, phone, password_hash, plate_number, role, status, created_at', '用户账户'],
            ['parking_slots', 'id, slot_number, zone, status, has_charging, sensor_id', '车位状态'],
            ['parking_records', 'id, user_id, plate_number, slot_number, entry_time, exit_time, fee, status, payment_method', '停车流水'],
            ['charging_records', 'id, user_id, plate_number, slot_number, start_time, end_time, status', '充电记录'],
            ['modification_requests', 'id, user_id, mod_type, old_value, new_value, reason, status', '信息变更审批'],
            ['parking_price_rules', 'id, start_time, end_time, price_per_hour, max_daily, vehicle_type, priority', '计费规则（NEW）'],
            ['audit_logs', 'id, user_id, action, target_type, target_id, detail, ip, created_at', '操作审计（NEW）'],
            ['hardware_devices', 'id, device_id, device_type, location, status, last_heartbeat', '硬件设备注册（NEW）'],
        ],
        col_widths=[3.5, 9.5, 4]
    )

    doc.add_heading('6.3 索引策略', level=2)
    doc.add_paragraph(
        '高频查询字段建立索引：parking_records(plate_number, status)、'
        'parking_records(entry_time DESC)、parking_slots(zone, status)、'
        'users(phone UNIQUE)。索引使用 B-Tree 结构，定期执行 VACUUM ANALYZE 维护统计信息。'
    )

    doc.add_heading('6.4 数据库迁移', level=2)
    doc.add_paragraph(
        '使用 Alembic 管理全部 Schema 变更。每次模型修改后执行：'
        'alembic revision --autogenerate -m "描述" → alembic upgrade head。'
        '禁止在生产环境直接使用 db.create_all()。迁移脚本纳入版本控制。'
    )

    # ================================================================
    # 七、AI预测与推荐模块
    # ================================================================
    doc.add_heading('七、AI预测与推荐模块', level=1)

    doc.add_heading('7.1 停车场流量预测', level=2)

    p = doc.add_paragraph()
    run = p.add_run('算法选型：')
    run.bold = True
    p.add_run(
        '使用 LSTM（长短期记忆网络）进行时序预测。LSTM 相比 MLP 能更好地捕捉停车场'
        '占用率的周期性规律（早高峰、晚高峰、周末模式）。备选方案为 Facebook Prophet，'
        '其优势在于自动处理节假日效应和趋势变化点检测。'
    )

    p = doc.add_paragraph()
    run = p.add_run('特征工程：')
    run.bold = True
    p.add_run(
        '输入特征包括：(1) 过去 24 小时每小时的占用率序列（滑动窗口）；'
        '(2) 星期几的 One-Hot 编码（7维）；(3) 是否节假日（1维）；'
        '(4) 当前时段编码（上午/下午/夜间，3维 one-hot）。'
    )

    p = doc.add_paragraph()
    run = p.add_run('训练与部署：')
    run.bold = True
    p.add_run(
        '每天凌晨 2:00 自动触发增量训练，使用前 30 天的 ParkingRecord 数据构建训练集。'
        '模型训练完成后使用 joblib 持久化到 models/ 目录，服务启动时加载。'
        '预测接口返回未来 7 小时的占用率预测值及其 95% 置信区间。'
    )

    doc.add_heading('7.2 车位智能推荐', level=2)

    p = doc.add_paragraph()
    run = p.add_run('算法选型：')
    run.bold = True
    p.add_run(
        '采用基于用户的协同过滤算法（User-Based Collaborative Filtering）。'
        '通过分析历史停车数据，找到与目标用户偏好相似的用户群体，聚合他们的车位偏好来'
        '为目标用户推荐车位。使用 NearestNeighbors + Cosine Similarity 作为相似度计算引擎。'
    )

    p = doc.add_paragraph()
    run = p.add_run('冷启动策略：')
    run.bold = True
    p.add_run(
        '对于无历史记录的新用户，降级为规则推荐：按"离电梯距离最近"'
        '+ "是否有充电桩（绿牌用户优先）"排序。随着用户停车次数增加，逐步切换到协同过滤模式。'
    )

    p = doc.add_paragraph()
    run = p.add_run('上下文增强：')
    run.bold = True
    p.add_run(
        '在推荐排序中引入天气（雨天优先地下车位）、车辆类型（大型车过滤小型车位）、'
        '预约时段（高峰时段降低远距离车位权重）等上下文特征，提升推荐精准度。'
    )

    # ================================================================
    # 八、前端模块
    # ================================================================
    doc.add_heading('八、前端模块', level=1)

    doc.add_heading('8.1 技术栈', level=2)
    add_styled_table(doc,
        ['技术', '选型', '说明'],
        [
            ['框架', 'Vue 3 (Composition API)', '响应式UI框架'],
            ['构建工具', 'Vite', '极速冷启动 + HMR热更新'],
            ['类型系统', 'TypeScript', '类型安全，减少运行时错误'],
            ['UI组件库', 'Element Plus', '企业级中后台组件库'],
            ['可视化', 'ECharts 5', '仪表盘图表、趋势图、热力图'],
            ['状态管理', 'Pinia', '轻量级状态管理，替代 Vuex'],
            ['路由', 'Vue Router 4', 'SPA 页面路由'],
            ['HTTP', 'Axios + 拦截器', '自动附加 JWT token + 401 拦截'],
            ['实时通信', 'socket.io-client', 'WebSocket 实时推送'],
            ['移动端', 'postcss-px-to-viewport', '移动端视口适配'],
        ],
        col_widths=[2.5, 5, 9.5]
    )

    doc.add_heading('8.2 页面结构', level=2)
    add_styled_table(doc,
        ['页面', '目标用户', '核心功能'],
        [
            ['登录/注册', '所有用户', '手机号+密码登录，JWT token 存储，自动刷新'],
            ['用户首页', '车主', '实时车位地图、推荐车位高亮、一键预约、充电管理'],
            ['停车记录', '车主', '历史停车记录、费用明细、发票申请'],
            ['管理仪表盘', '管理员', '实时KPI卡片、车位占用热力图、今日营收滚动'],
            ['用户管理', '管理员', '用户审批、角色分配、车牌修改审批'],
            ['停车记录管理', '管理员', '全场停车记录查询、异常记录处理、无牌车登记'],
            ['数据报表', '管理员', '日/周/月营收趋势、车位周转率、高峰时段分析'],
            ['实时大屏', '展厅/保安室', '全屏监控、WebSocket实时车位+识别画面流'],
            ['设备监控', '运维', '闸机/摄像头在线状态、识别成功率、帧率监控'],
        ],
        col_widths=[3, 2.5, 11.5]
    )

    doc.add_heading('8.3 前-后端交互', level=2)
    doc.add_paragraph(
        'RESTful API：通过 Axios 发送 HTTP 请求，请求拦截器自动附加 Authorization: Bearer <token>。'
        '响应拦截器捕获 401 错误自动跳转登录页。'
    )
    doc.add_paragraph(
        'WebSocket：通过 socket.io-client 建立长连接，订阅以下事件：slot_update（车位状态变化）、'
        'entry_alert（车辆入场通知）、dashboard_stats（仪表盘实时数据）。前端收到事件后通过 Pinia '
        '更新全局状态，组件自动响应式刷新。'
    )

    # ================================================================
    # 九、硬件通信模块
    # ================================================================
    doc.add_heading('九、硬件通信模块', level=1)

    doc.add_heading('9.1 通信架构', level=2)
    doc.add_paragraph(
        '边缘设备（K210+ESP32）与云端服务之间的通信支持两种模式：'
    )
    doc.add_paragraph(
        '(1) 本地直连模式：ESP32 通过 USB 串口连接本地 PC，PC 上的 Python 桥接程序'
        '（基于 PySerial）接收数据后转发到云端。适用于单点部署或开发调试阶段。'
    )
    doc.add_paragraph(
        '(2) MQTT 远程模式：ESP32 通过 WiFi 直连云端的 MQTT Broker（如 EMQX），'
        '云端服务订阅对应 Topic 接收数据。适用于多设备分布式部署，支持离线消息缓存。'
    )

    doc.add_heading('9.2 应用层协议设计', level=2)
    doc.add_paragraph('通信协议格式：CMD|SEQ|PAYLOAD|CHECKSUM')
    add_styled_table(doc,
        ['指令', '方向', '格式示例', '说明'],
        [
            ['ENTRY', '设备→云端', 'ENTRY|001|冀A·12345|2026-06-07 14:30:00|A3F', '车辆入场上报'],
            ['EXIT', '设备→云端', 'EXIT|002|冀A·12345|2026-06-07 16:45:00|B2E', '车辆出场上报'],
            ['ACK_ENTRY', '云端→设备', 'ACK|ENTRY|001|OK|C1A', '入场确认，开闸'],
            ['ACK_EXIT', '云端→设备', 'ACK|EXIT|002|PAY|15.00|D4B', '出场确认，附费用'],
            ['PING', '设备→云端', 'PING|003|DEVICE_01|E6F', '设备心跳'],
            ['PONG', '云端→设备', 'PONG|003||F1C', '心跳响应'],
            ['SLOT', '设备→云端', 'SLOT|004|A-005|OCCUPIED|A9D', '车位状态上报'],
            ['TIME', '云端→设备', 'TIME||2026-06-07 14:30:00|C4E', '时间同步'],
            ['ERR', '任意→对方', 'ERR|005|TIMEOUT|D1A', '错误上报'],
        ],
        col_widths=[2.5, 2, 8.5, 4]
    )

    doc.add_heading('9.3 容错机制', level=2)
    mechanisms = [
        '消息校验：每条消息末尾附加 CRC-16 校验码，接收方校验不通过则丢弃并请求重发。',
        '超时重传：发送方 3 秒内未收到 ACK 则重发，最多重试 3 次，仍失败则记录错误日志并报警。',
        '断线重连：指数退避重连策略（1s → 2s → 4s → 8s → max 30s），避免重连风暴。',
        '离线缓存：ESP32 本地 Flash 存储未成功发送的记录，网络恢复后按时间顺序批量补传。',
    ]
    for m in mechanisms:
        doc.add_paragraph(m, style='List Bullet')

    # ================================================================
    # 十、计费引擎模块
    # ================================================================
    doc.add_heading('十、计费引擎模块', level=1)

    doc.add_heading('10.1 计费规则', level=2)
    add_styled_table(doc,
        ['规则项', '参数', '说明'],
        [
            ['免费时段', '入场后 30 分钟内免费', '短时临停（接送人、卸货）'],
            ['白天费率', '8:00-20:00，¥5/小时', '不足1小时按1小时计'],
            ['夜间费率', '20:00-次日8:00，¥3/小时', '不足1小时按1小时计'],
            ['白天封顶', '¥50/天', '超过10小时触发'],
            ['夜间封顶', '¥20/夜', '超过7小时触发'],
            ['新能源优惠', '绿牌车辆打 8 折', '鼓励新能源车使用'],
            ['跨天计算', '按自然天分段计算各有封顶', '例如：当晚停到明早，白天段+夜间段分别计费'],
        ],
        col_widths=[3, 5.5, 8.5]
    )

    doc.add_heading('10.2 实现方式', level=2)
    doc.add_paragraph(
        '计费规则存储在 parking_price_rules 表中，支持管理员通过后台界面动态修改，即时生效。'
        'calculate_parking_fee() 函数从规则表中读取最新规则，按入场时间、出场时间逐时段累加计算。'
        '计算逻辑：将停车时长按规则时段切分，各时段分别按费率计算后加总，再应用封顶和折扣策略。'
    )

    # ================================================================
    # 十一、实时推送模块
    # ================================================================
    doc.add_heading('十一、实时推送模块 (WebSocket)', level=1)

    doc.add_heading('11.1 技术方案', level=2)
    doc.add_paragraph(
        '后端使用 flask-socketio（基于 python-socketio），前端使用 socket.io-client。'
        '服务启动时创建 WebSocket 连接池，客户端按需订阅房间（Channel）。'
        '对于多 Worker 部署场景（Gunicorn 多进程），使用 Redis Adapter 实现跨进程消息广播。'
    )

    doc.add_heading('11.2 推送事件定义', level=2)
    add_styled_table(doc,
        ['事件名', '推送内容', '触发时机', '频率'],
        [
            ['slot_update', '{slot_number, zone, status, plate}', '车位状态变化时', '事件驱动'],
            ['entry_alert', '{plate, slot, image_url, timestamp}', '车辆入场识别成功', '事件驱动'],
            ['exit_alert', '{plate, slot, fee, timestamp}', '车辆出场结算完成', '事件驱动'],
            ['dashboard_stats', '{total, free, occupied, revenue_today, revenue_month}', '仪表盘定期刷新', '每5秒'],
            ['recognition_feed', '{image_base64, plate, confidence}', '每次车牌识别完成', '事件驱动'],
            ['system_alert', '{level: info/warn/error, title, message}', '系统异常（满位/设备离线/识别率下降）', '事件驱动'],
        ],
        col_widths=[3, 6, 4.5, 2]
    )

    # ================================================================
    # 十二、部署与运维模块
    # ================================================================
    doc.add_heading('十二、部署与运维模块', level=1)

    doc.add_heading('12.1 容器化部署', level=2)
    doc.add_paragraph(
        '全服务使用 Docker Compose 编排，包括以下服务：'
    )
    services = [
        'web 服务：Python 应用，Gunicorn (4 workers) + Uvicorn worker class，监听 5000 端口',
        'db 服务：PostgreSQL 16，数据卷持久化',
        'redis 服务：Redis 7，用于缓存和 WebSocket 跨进程通信',
        'nginx 服务：Nginx Alpine，反向代理 + 静态文件服务 + HTTPS 终端',
        'ocr 服务：PaddleOCR 独立容器，GPU 加速（可选）',
    ]
    for s in services:
        doc.add_paragraph(s, style='List Bullet')

    doc.add_heading('12.2 HTTPS 配置', level=2)
    doc.add_paragraph(
        'Nginx 配置 Let\'s Encrypt SSL 证书，使用 certbot 自动续签。'
        'HTTP (80端口) 301 重定向到 HTTPS (443端口)。TLS 版本最低要求 1.2。'
    )

    doc.add_heading('12.3 监控体系', level=2)
    add_styled_table(doc,
        ['工具', '用途', '核心指标'],
        [
            ['Prometheus', '指标采集', '请求量(QPS)、响应时间(P50/P99)、错误率、车位占用率'],
            ['Grafana', '可视化面板', '实时仪表盘、历史趋势、告警规则'],
            ['Sentry', '异常追踪', 'Python异常堆栈、前端JS错误、API错误率'],
            ['Uptime Kuma', '可用性监控', 'HTTP/HTTPS服务存活检测、SSL证书到期提醒'],
        ],
        col_widths=[3, 3, 11]
    )

    doc.add_heading('12.4 数据备份', level=2)
    doc.add_paragraph(
        'PostgreSQL 每日凌晨 3:00 自动 pg_dump 完整备份，保留最近 30 天。'
        '备份文件同步至对象存储（阿里云 OSS / AWS S3）。每月 1 日做一次异地冷备。'
    )

    # ================================================================
    # 十三、测试方案
    # ================================================================
    doc.add_heading('十三、测试方案', level=1)

    doc.add_heading('13.1 测试层次', level=2)
    doc.add_paragraph('采用经典测试金字塔模型，自底向上三层覆盖：')

    add_styled_table(doc,
        ['测试层次', '工具', '覆盖目标', '用例数量'],
        [
            ['单元测试', 'pytest + pytest-cov', 'Service层业务逻辑、计费算法、工具函数', '200+ 条，覆盖率 > 80%'],
            ['集成测试', 'pytest + Flask TestClient', 'API接口 + 数据库操作完整链路', '50+ 条核心场景'],
            ['端到端测试', 'Playwright', '完整用户流程（登录→预约→支付）', '10+ 条关键流程'],
        ],
        col_widths=[2.5, 4, 6, 4.5]
    )

    doc.add_heading('13.2 关键测试场景', level=2)
    scenarios = [
        '计费精度：测试 0分钟/29分钟/31分钟/5小时/24小时/跨天/跨天+跨费率的费用计算正确性',
        '并发安全：模拟 10 辆车同时入场，验证车位分配不超卖、数据库无死锁',
        '降级兜底：断开 OCR 服务，验证系统自动切换到备用方案并正确降级',
        '认证安全：无 Token 请求受保护接口，验证返回 401；过期 Token 验证返回 401',
        '边缘-云端协同：模拟边缘识别失败场景，验证云端兜底 → 模糊匹配 → 放行/拒绝全链路',
        '断线恢复：模拟网络中断 5 分钟后恢复，验证离线数据补传完整性',
    ]
    for s in scenarios:
        doc.add_paragraph(s, style='List Bullet')

    # ================================================================
    # 十四、项目里程碑
    # ================================================================
    doc.add_heading('十四、项目里程碑', level=1)

    add_styled_table(doc,
        ['阶段', '周期', '核心交付物', '验收标准'],
        [
            ['Phase 1: 基础架构', '第1-2周', 'JWT认证、项目结构重构、配置管理、日志系统', 'API文档完整、Token认证通过'],
            ['Phase 2: 数据与测试', '第3-4周', 'PostgreSQL迁移、Alembic、Service层测试', '单测覆盖率80%+、API集成测试通过'],
            ['Phase 3: AI引擎', '第5周', '模型持久化、真实数据训练、预测替代假数据', '预测MAE<15%、推荐点击率提升30%'],
            ['Phase 4: 前端', '第6-7周', 'Vue3重构、WebSocket实时推送、数据报表', '页面加载<2s、实时推送延迟<500ms'],
            ['Phase 5: 硬件部署', '第8周', '串口容错、MQTT通信、设备监控API', '断线自动重连、离线缓存补传正常'],
            ['Phase 6: 部署上线', '第9周', 'Docker化、CI/CD、监控面板', '服务可用性>99.5%、异常告警正常'],
        ],
        col_widths=[3, 1.5, 5.5, 7]
    )

    # ================================================================
    # 保存
    # ================================================================
    output_path = os.path.join(os.path.dirname(__file__), '智能停车场管理系统_项目设计书.docx')
    doc.save(output_path)
    print(f'文档已生成: {output_path}')
    return output_path

if __name__ == '__main__':
    generate_doc()
