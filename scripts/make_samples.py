"""生成三类测试 PDF：扫描版、文字版、混合版。"""

import os
import sys

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "samples")

FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simsun.ttc",
    "C:/Windows/Fonts/simhei.ttf",
]


def load_font(size):
    from PIL import ImageFont

    for f in FONT_CANDIDATES:
        if os.path.isfile(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def make_scan_pdf(path):
    """模拟扫描版：整页是一张图，含标题、正文、一个带文字的框（模拟插图文字）。"""
    from PIL import Image, ImageDraw

    W, H, DPI = 1654, 2339, 200  # A4 @200dpi
    img = Image.new("RGB", (W, H), (250, 249, 245))  # 略带纸色
    d = ImageDraw.Draw(img)
    d.text((140, 160), "扫描文档测试", font=load_font(72), fill=(20, 20, 20))
    body = [
        "这是一份用于测试的扫描版文档。整页内容以图片形式存在，",
        "没有可选择的文本层。转换工具需要通过 OCR 识别出这些文字，",
        "并把它们重建为可编辑的 Word 段落。",
        "",
        "第二段内容：保留排版意味着段落顺序、字号层级要尽量接近原文。",
    ]
    y = 340
    for line in body:
        d.text((140, y), line, font=load_font(36), fill=(30, 30, 30))
        y += 64
    # 一个带文字的框，模拟含文字的插图
    d.rectangle([140, 760, 1500, 1120], outline=(60, 60, 160), width=6)
    d.text((200, 830), "图示区域：这里的文字位于图形内部", font=load_font(40), fill=(60, 60, 160))
    d.text((200, 930), "转换后应当被提取为可编辑文本", font=load_font(40), fill=(60, 60, 160))
    d.text((140, 1220), "页面底部的一段说明文字。", font=load_font(36), fill=(30, 30, 30))
    img.save(path, "PDF", resolution=DPI)
    print("生成:", path)


def make_text_pdf(path):
    """文字型 PDF：含真实文本层与一张带文字的嵌入图片。"""
    import fitz
    from PIL import Image, ImageDraw
    import io

    doc = fitz.open()
    page = doc.new_page()  # A4 595x842pt
    page.insert_text((72, 90), "文字型文档测试", fontname="china-s", fontsize=24)
    page.insert_textbox(
        fitz.Rect(72, 120, 523, 300),
        "这一页拥有真实的文本层，可以直接选择与复制。pdf2docx 直转通道"
        "会保留这里的字体、字号与段落结构。下方插入了一张含有文字的图片，"
        "用于测试图内文字提取功能。",
        fontname="china-s",
        fontsize=13,
    )
    # 带文字的嵌入图片
    img = Image.new("RGB", (900, 300), (240, 246, 255))
    dr = ImageDraw.Draw(img)
    dr.rectangle([10, 10, 890, 290], outline=(40, 90, 180), width=4)
    dr.text((60, 80), "图片内的文字：可编辑提取目标", font=load_font(52), fill=(40, 90, 180))
    dr.text((60, 180), "第二行：转换后应出现在 Word 中", font=load_font(44), fill=(40, 90, 180))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    page.insert_image(fitz.Rect(72, 320, 472, 454), stream=buf.getvalue())
    page.insert_text((72, 500), "图片下方的正文文字，用于验证图文顺序。", fontname="china-s", fontsize=13)
    doc.save(path)
    doc.close()
    print("生成:", path)


def make_mixed_pdf(path):
    """混合文档：第 1 页文字型，第 2 页扫描型。"""
    import fitz
    from PIL import Image, ImageDraw
    import io

    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 90), "混合文档：第一页（文字型）", fontname="china-s", fontsize=20)
    p1.insert_textbox(
        fitz.Rect(72, 130, 523, 260),
        "本页有文本层。第二页是扫描页，没有文本层。工具需要逐页判定并分别处理。",
        fontname="china-s",
        fontsize=13,
    )
    # 第 2 页：整页图片
    W, H, DPI = 1654, 2339, 200
    img = Image.new("RGB", (W, H), (252, 251, 248))
    d = ImageDraw.Draw(img)
    d.text((140, 160), "第二页（扫描页）", font=load_font(64), fill=(20, 20, 20))
    d.text((140, 320), "这一页整体是一张图片，必须依赖 OCR 才能提取文字。", font=load_font(38), fill=(30, 30, 30))
    d.text((140, 420), "两页合并测试文档级分流逻辑。", font=load_font(38), fill=(30, 30, 30))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    p2 = doc.new_page(width=595, height=842)
    p2.insert_image(fitz.Rect(0, 0, 595, 842), stream=buf.getvalue())
    doc.save(path)
    doc.close()
    print("生成:", path)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    make_scan_pdf(os.path.join(OUT_DIR, "sample_scan.pdf"))
    make_text_pdf(os.path.join(OUT_DIR, "sample_text.pdf"))
    make_mixed_pdf(os.path.join(OUT_DIR, "sample_mixed.pdf"))
    print("全部测试样本已生成于:", OUT_DIR)
