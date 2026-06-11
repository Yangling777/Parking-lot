from PIL import Image


def image_to_c_array(image_path, output_name="image_data", width=120, height=120):
    """
    将图片转换为 120x120 黑白单色 C 数组
    模式：水平取模，高位在前 (MSB First)
    """
    # 1. 打开图片并缩放到 120x120
    img = Image.open(image_path)
    img = img.resize((width, height), Image.Resampling.LANCZOS)

    # 2. 转为灰度图 → 黑白二值图（阈值 128，纯黑白）
    img_gray = img.convert("L")
    img_binary = img_gray.point(lambda p: 0 if p < 128 else 1, "1")  # 0=黑，1=白

    # 3. 准备 C 数组数据
    byte_data = []
    bytes_per_row = (width + 7) // 8  # 每行需要的字节数

    # 逐行处理（水平取模）
    for y in range(height):
        current_byte = 0
        bit_count = 0

        for x in range(width):
            # 获取像素值（0 黑，1 白）
            pixel = img_binary.getpixel((x, y))

            # 高位在前 MSB First
            current_byte = (current_byte << 1) | pixel
            bit_count += 1

            # 每 8 位打包成一个字节
            if bit_count == 8:
                byte_data.append(current_byte)
                current_byte = 0
                bit_count = 0

        # 一行不足 8 位，补齐剩余位
        if bit_count > 0:
            current_byte <<= (8 - bit_count)
            byte_data.append(current_byte)

    # 4. 生成 C 语言文件内容
    c_content = f"""
// 自动生成：120x120 黑白单色图像数据
// 水平取模 | 高位在前(MSB First)
// 尺寸: {width}x{height}
const unsigned char {output_name}[{len(byte_data)}] = {{
"""

    # 格式化输出（每行 16 个字节）
    for i in range(0, len(byte_data), 16):
        line = ", ".join(f"0x{b:02X}" for b in byte_data[i:i + 16])
        c_content += "    " + line + ",\n"

    c_content += "};\n"

    # 5. 保存到 .h 文件
    output_file = f"{output_name}.h"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(c_content)

    print(f"✅ 转换完成！")
    print(f"📁 输出文件：{output_file}")
    print(f"📏 尺寸：{width}x{height}")
    print(f"📦 数组长度：{len(byte_data)} 字节")
    print(f"⚙️  格式：单色 1bit | 水平取模 | MSB 高位在前")


# ====================== 使用方法 ======================
if __name__ == "__main__":
    # 把你的图片放在同目录下，修改这里的文件名即可
    image_path = "D:\car\图片转数组\static\pay.jpg"  # 你的图片路径
    output_name = "lcd_icon"  # 输出的数组名
    image_to_c_array(image_path, output_name)