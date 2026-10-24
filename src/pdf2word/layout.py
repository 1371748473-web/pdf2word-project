"""版面分析：PP-DocLayoutV3 区域检测（懒加载，失败时优雅降级）。"""

_layout_model = None
_layout_failed = False

# 标签归类规则（PP-DocLayoutV3 输出标签）
_TEXT_KEYS = ("text", "title", "abstract", "content", "footnote", "aside")
_TABLE_KEYS = ("table",)
_IMAGE_KEYS = ("image", "chart", "figure", "seal", "formula", "algorithm", "equation")
_SKIP_KEYS = ("header", "footer", "reference", "number")


def get_layout_model():
    global _layout_model, _layout_failed
    if _layout_model is None and not _layout_failed:
        try:
            from .envsetup import activate_gpu_device, patch_paddlex_deps
            from paddlex import create_model

            # paddlex 已正常导入，此时打补丁不会触发重复初始化
            patch_paddlex_deps()
            activate_gpu_device()
            # 注意：不要在此处开启 oneDNN，PP-DocLayoutV3 在 paddle 3.3 + oneDNN
            # 下加载/推理均报错，详见 experiments/onednn/README.md。
            _layout_model = create_model("PP-DocLayoutV3")
        except Exception:
            _layout_failed = True
    return _layout_model


def detect_regions(np_image, min_score=0.5):
    """返回区域列表 [{'label','score','x0','y0','x1','y1'}]；模型不可用时返回 None。"""
    model = get_layout_model()
    if model is None:
        return None
    try:
        res = list(model.predict(np_image))
    except Exception:
        return None
    if not res:
        return None
    d = dict(res[0]) if not isinstance(res[0], dict) else res[0]
    regions = []
    for b in d.get("boxes", []):
        label = str(b.get("cls_name") or b.get("label") or "")
        try:
            score = float(b.get("score", 0.0))
        except Exception:
            score = 0.0
        coord = b.get("coordinate") or [0, 0, 0, 0]
        if score < min_score or len(coord) < 4:
            continue
        x0, y0, x1, y1 = [float(v) for v in coord[:4]]
        if x1 - x0 < 8 or y1 - y0 < 8:
            continue
        regions.append(
            {"label": label, "score": score, "x0": x0, "y0": y0, "x1": x1, "y1": y1}
        )
    return regions


def label_kind(label):
    """把版面标签归为 text / table / image / skip 四类。"""
    t = str(label).lower()
    if any(k in t for k in _TABLE_KEYS):
        return "table"
    if any(k in t for k in _TEXT_KEYS):
        return "text"
    if any(k in t for k in _IMAGE_KEYS):
        return "image"
    if any(k in t for k in _SKIP_KEYS):
        return "skip"
    return "image"


def sort_reading_order(regions):
    """按阅读顺序排序：先行聚类（纵向），行内按横向。"""
    if not regions:
        return []
    regions = sorted(regions, key=lambda b: (b["y0"], b["x0"]))
    heights = sorted((b["y1"] - b["y0"]) for b in regions)
    med = heights[len(heights) // 2] if heights else 20.0
    rows, cur, cur_y1 = [], [regions[0]], regions[0]["y1"]
    for b in regions[1:]:
        if b["y0"] >= cur_y1 - 0.4 * med:  # 与当前行分离 → 新行
            rows.append(sorted(cur, key=lambda x: x["x0"]))
            cur, cur_y1 = [b], b["y1"]
        else:
            cur.append(b)
            cur_y1 = max(cur_y1, b["y1"])
    rows.append(sorted(cur, key=lambda x: x["x0"]))
    return [b for row in rows for b in row]
