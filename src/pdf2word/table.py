"""表格重建：SLANet_plus 表格结构识别 + OCR 文字回填单元格。

输出网格格式（供 rebuild.build_docx 渲染为 Word 表格）：
    [ [ {"text": str, "colspan": int}, ... ], ... ]
"""

import re

_table_model = None
_table_failed = False

_TD_RE = re.compile(r"<td([^>]*)>")
_COLSPAN_RE = re.compile(r'colspan\s*=\s*"?(\d+)')
_ROWSPAN_RE = re.compile(r'rowspan\s*=\s*"?(\d+)')


def get_table_model():
    """惰性加载 SLANet_plus（进程内单例，失败时返回 None）。"""
    global _table_model, _table_failed
    if _table_model is None and not _table_failed:
        try:
            from .envsetup import activate_gpu_device, patch_paddlex_deps
            from paddlex import create_model

            # paddlex 已正常导入，此时打补丁不会触发重复初始化
            patch_paddlex_deps()
            activate_gpu_device()
            _table_model = create_model("SLANet_plus")
        except Exception:
            _table_failed = True
    return _table_model


def _quad_to_box(q):
    xs = [float(q[i]) for i in (0, 2, 4, 6)]
    ys = [float(q[i]) for i in (1, 3, 5, 7)]
    return [min(xs), min(ys), max(xs), max(ys)]


def _parse_structure(tokens):
    """结构 token 序列 → 行网格。返回 (rows, cell_of_td)。

    rows: [[{"text":"", "colspan":1, "rowspan":1}, ...], ...]
    cell_of_td: td 序号 → (row_idx, cell_idx)
    """
    rows, cur = [], None
    cell_of_td = {}
    td_index = 0
    for tok in tokens:
        t = tok.strip() if isinstance(tok, str) else str(tok)
        if t == "<tr>":
            cur = []
            rows.append(cur)
        elif t == "</tr>":
            cur = None
        elif "</td>" in t:
            cell = {"text": "", "colspan": 1, "rowspan": 1}
            m = _TD_RE.match(t)
            if m:
                attrs = m.group(1) or ""
                mc = _COLSPAN_RE.search(attrs)
                mr = _ROWSPAN_RE.search(attrs)
                if mc:
                    cell["colspan"] = max(1, int(mc.group(1)))
                if mr:
                    cell["rowspan"] = max(1, int(mr.group(1)))
            if cur is None:  # 结构异常时兜底建行
                cur = []
                rows.append(cur)
            cell_of_td[td_index] = (len(rows) - 1, len(cur))
            cur.append(cell)
            td_index += 1
    return rows, cell_of_td


def _heuristic_grid(lines):
    """TSR 不可用时的兜底：按 OCR 行框聚类出行列。"""
    if len(lines) < 4:
        return None
    width = max(L["x1"] for L in lines) - min(L["x0"] for L in lines)
    # 行聚类：中心 y 接近的归一行
    rows = []
    for L in sorted(lines, key=lambda x: x["cy"]):
        for row in rows:
            if any(abs(L["cy"] - M["cy"]) <= 0.6 * max(L["h"], M["h"]) for M in row):
                row.append(L)
                break
        else:
            rows.append([L])
    rows.sort(key=lambda r: min(m["y0"] for m in r))
    # 列聚类：x0 接近的归一列
    tol = max(8.0, width * 0.02)
    col_heads = []
    for x in sorted(L["x0"] for L in lines):
        if col_heads and x - col_heads[-1] <= tol:
            continue
        col_heads.append(x)
    if len(col_heads) < 2 or len(rows) < 2:
        return None

    def col_of(L):
        best, bd = 0, abs(L["x0"] - col_heads[0])
        for i, cx in enumerate(col_heads[1:], 1):
            d = abs(L["x0"] - cx)
            if d < bd:
                best, bd = i, d
        return best

    grid = []
    for row in rows:
        cells = [""] * len(col_heads)
        for L in sorted(row, key=lambda x: (col_of(x), x["x0"])):
            c = col_of(L)
            cells[c] = (cells[c] + " " + L["text"]).strip()
        if any(cells):
            grid.append([{"text": c, "colspan": 1} for c in cells])
    return grid if len(grid) >= 2 else None


def reconstruct_table(crop_pil, ocr_lines, log=None):
    """表格区域图 + 该区 OCR 行 → 网格；失败返回 None。"""
    import numpy as np

    log = log or (lambda s: None)
    lines = [L for L in ocr_lines if L["text"].strip()]
    if len(lines) < 4:
        return None

    model = get_table_model()
    if model is None:
        log("    表格结构模型不可用，使用聚类兜底")
        return _heuristic_grid(lines)

    try:
        res = list(model.predict(np.asarray(crop_pil)))
        d = dict(res[0]) if not isinstance(res[0], dict) else res[0]
        structure = d["structure"]
        cell_quads = np.asarray(d["bbox"], dtype=float)
        if cell_quads.ndim != 2 or cell_quads.shape[0] == 0:
            raise ValueError("TSR 无单元格输出")
        cell_boxes = [_quad_to_box(q) for q in cell_quads]
    except Exception as e:
        log(f"    表格结构识别失败（{e}），使用聚类兜底")
        return _heuristic_grid(lines)

    try:
        from paddlex.inference.pipelines.table_recognition.table_recognition_post_processing import (
            match_table_and_ocr,
        )

        ocr_boxes = [[L["x0"], L["y0"], L["x1"], L["y1"]] for L in lines]
        matched = match_table_and_ocr(cell_boxes, ocr_boxes, cell_sort_by_y_projection=True)
    except Exception:
        # 简化版匹配：文本行中心落在哪个单元格
        matched = {}
        for i, L in enumerate(lines):
            cx, cy = (L["x0"] + L["x1"]) / 2, (L["y0"] + L["y1"]) / 2
            best, bd = None, None
            for j, (l, t, r, b) in enumerate(cell_boxes):
                if l <= cx <= r and t <= cy <= b:
                    best = j
                    break
                dd = max(l - cx, 0) + max(cx - r, 0) + max(t - cy, 0) + max(cy - b, 0)
                if bd is None or dd < bd:
                    best, bd = j, dd
            if best is not None:
                matched.setdefault(best, []).append(i)

    rows, cell_of_td = _parse_structure(structure)
    if not rows:
        return _heuristic_grid(lines)

    for td_idx, ocr_idxs in matched.items():
        pos = cell_of_td.get(td_idx)
        if pos is None:
            continue
        ri, ci = pos
        cell_lines = sorted((lines[i] for i in ocr_idxs), key=lambda L: (L["y0"], L["x0"]))
        text = " ".join(L["text"].strip() for L in cell_lines if L["text"].strip())
        rows[ri][ci]["text"] = text

    # 过滤完全空的表（整表无任何文字）
    if not any(c["text"] for row in rows for c in row):
        return None
    return rows
