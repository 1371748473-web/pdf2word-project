"""页面类型判定：逐页判断 text / scan。"""

MIN_TEXT_CHARS = 20      # 文本层字符数阈值
IMAGE_COVERAGE = 0.80    # 大图覆盖率阈值


def page_image_coverage(page):
    """计算页面被位图覆盖的面积比例。"""
    rect = page.rect
    page_area = max(rect.width * rect.height, 1.0)
    area = 0.0
    for info in page.get_image_info():
        b = info.get("bbox")
        if b:
            area += max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    return min(area / page_area, 1.0)


def classify_page(page):
    """单页判定：文本层充足为 text，否则按 scan 处理（含低质量混合页兜底）。"""
    text = page.get_text("text").strip()
    if len(text) >= MIN_TEXT_CHARS:
        return "text"
    return "scan"


def classify_doc(doc):
    """整份文档判定，返回 (doc_type, [page_types])。"""
    types = [classify_page(p) for p in doc]
    if all(t == "text" for t in types):
        return "text", types
    if all(t == "scan" for t in types):
        return "scan", types
    return "mixed", types
