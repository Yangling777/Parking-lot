# utils/plate_generator.py
import random


def generate_realistic_plate():
    """
    生成符合中国国家标准的虚拟车牌
    """
    provinces = "京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼"
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    digits = "0123456789"
    alphanumeric = digits + letters

    # 按现实比例设定权重：蓝牌(60%), 绿牌(30%), 黄牌(5%), 白牌(2%), 黑牌(3%)
    p_type = random.choices(['blue', 'green', 'yellow', 'white', 'black'], weights=[0.6, 0.3, 0.05, 0.02, 0.03])[0]

    prov = random.choice(provinces)
    city = random.choice(letters)

    if p_type == 'green':
        # 绿牌（新能源）: 6位，通常以 D/A/B/C/E 开头
        tail = random.choice("DABCE") + "".join(random.choices(digits, k=5))
    elif p_type == 'white':
        # 白牌（公检法学）: 尾部带特殊汉字
        tail = "".join(random.choices(digits, k=4)) + random.choice(["警", "学", "领"])
    elif p_type == 'black':
        # 黑牌（领事馆/港澳牌）
        if random.random() < 0.5:
            prov, city = "使", ""
            tail = "".join(random.choices(digits, k=6))
            return f"{prov}·{tail}"
        else:
            prov, city = "粤", "Z"
            tail = "".join(random.choices(alphanumeric, k=4)) + random.choice(["港", "澳"])
    else:
        # 蓝牌/黄牌: 5位标准字符
        tail = "".join(random.choices(alphanumeric, k=5))

    return f"{prov}{city}·{tail}"