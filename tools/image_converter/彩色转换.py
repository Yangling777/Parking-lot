from PIL import Image

def image_to_rgb565_c_array(image_path, output_name="image_data", width=120, height=120):
    """
    图片 → 120x120 RGB565 彩色 C 数组
    不转黑白！保留真实颜色
    输出格式：const uint16_t PROGMEM
    """
    # 1. 打开并缩放图片
    img = Image.open(image_path).convert("RGB")
    img = img.resize((width, height), Image.Resampling.LANCZOS)

    # 2. 转 RGB565 颜色
    rgb565_data = []
    for y in range(height):
        for x in range(width):
            r, g, b = img.getpixel((x, y))

            # RGB565 公式
            r5 = (r >> 3) & 0x1F
            g6 = (g >> 2) & 0x3F
            b5 = (b >> 3) & 0x1F
            rgb565 = (r5 << 11) | (g6 << 5) | b5
            rgb565_data.append(rgb565)

    # 3. 生成 C 文件
    c_content = f"""
// 120x120 彩色 RGB565 图片（无黑白转换）
// 尺寸: {width}x{height}
// 格式: RGB565 | 逐行扫描 | 高位字节在前
#ifndef {output_name.upper()}_H
#define {output_name.upper()}_H

#include <stdint.h>

const uint16_t {output_name}[{width}*{height}] = {{
"""

    # 每行输出10个，好看
    for i in range(0, len(rgb565_data), 10):
        line = ", ".join(f"0x{p:04X}" for p in rgb565_data[i:i+10])
        c_content += "    " + line + ",\n"

    c_content += "};\n\n#endif\n"

    # 保存
    with open(f"{output_name}.h", "w", encoding="utf-8") as f:
        f.write(c_content)

    print("✅ 转换完成！彩色 RGB565")
    print(f"📦 数组：{output_name}.h")
    print(f"📏 大小：{width}x{height}")
    print(f"📝 格式：uint16_t RGB565 彩色")

# ====================== 使用 ======================
if __name__ == "__main__":
    image_to_rgb565_c_array(
        image_path="D:\car\图片转数组\static\pay.jpg",    # 你的图片
        output_name="logo_120x120"# 输出数组名
    )