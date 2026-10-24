"""生成应用图标 app_icon.ico（蓝底文档+箭头）。"""

import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "app_icon.ico")

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# 圆角蓝色背景
d.rounded_rectangle([8, 8, S - 8, S - 8], radius=52, fill=(37, 99, 235, 255))

# 白色文档形状
d.rounded_rectangle([62, 42, 168, 190], radius=14, fill=(255, 255, 255, 255))
# 文档折角
d.polygon([(138, 42), (168, 72), (138, 72)], fill=(191, 219, 254, 255))
# 文档内文字线
for y in (96, 118, 140):
    d.rounded_rectangle([78, y, 152, y + 10], radius=5, fill=(147, 197, 253, 255))

# 右侧箭头（转换含义）
d.polygon([(186, 100), (186, 146), (218, 123)], fill=(253, 224, 71, 255))
d.rectangle([170, 112, 190, 134], fill=(253, 224, 71, 255))

# 底部 W 标记
try:
    font = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 56)
except Exception:
    font = ImageFont.load_default()
d.text((92, 196), "W", font=font, fill=(255, 255, 255, 255))

img.save(OUT, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icon saved:", OUT)
