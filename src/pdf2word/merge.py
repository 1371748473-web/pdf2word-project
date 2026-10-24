"""PDF 合并：多文件合成一个，支持逐文件页面范围与书签汇总。

无 Qt 依赖，GUI 与 CLI 共用。
"""

import os
import time


def parse_range(text, page_count):
    """把 "1-5,8" 解析为 [(0,4),(7,7)]（PyMuPDF 的 0-based 闭区间）。

    text 为空或 None 时返回整册区间；非法片段会被忽略。
    """
    if not text or not str(text).strip():
        return [(0, page_count - 1)]
    out = []
    for frag in str(text).replace("，", ",").split(","):
        frag = frag.strip()
        if not frag:
            continue
        try:
            if "-" in frag:
                a, b = frag.split("-", 1)
                start, end = int(a), int(b)
            else:
                start = end = int(frag)
        except ValueError:
            continue
        start = max(1, min(start, page_count))
        end = max(1, min(end, page_count))
        if start > end:
            start, end = end, start
        out.append((start - 1, end - 1))
    return out or [(0, page_count - 1)]


def _bookmark_entries(doc, offsets, title_prefix=None):
    """把单个文档的书签转换成合并后的 TOC 条目。

    offsets: 该文档在合并结果中的页偏移（0-based）。
    返回 [[level, title, page], ...]（page 为 1-based）。
    """
    entries = []
    try:
        toc = doc.get_toc(simple=True)
    except Exception:
        return entries
    for level, title, page in toc:
        t = f"{title_prefix} / {title}" if level == 1 and title_prefix else title
        lv = level + 1 if title_prefix else level
        entries.append([lv, t, max(0, page - 1) + offsets + 1])
    return entries


def merge_pdfs(
    inputs,
    out_path,
    ranges=None,
    keep_bookmarks=True,
    log=print,
    progress=None,
    should_stop=None,
):
    """合并 PDF 列表，返回 (输出路径, 总页数, 失败文件列表)。

    inputs:   源文件路径列表，顺序即合并顺序
    ranges:   与 inputs 等长，每项为 "1-5,8" 或 None
    keep_bookmarks: 是否保留源书签（以文件名作为一级父书签）
    """
    import pymupdf

    if not inputs:
        raise ValueError("没有输入文件")

    t0 = time.time()
    dst = pymupdf.open()
    toc = []
    total_pages = 0
    failed = []
    current_offset = 0
    n = len(inputs)

    for idx, src_path in enumerate(inputs):
        if should_stop and should_stop():
            log("已取消，停止合并")
            break
        name = os.path.basename(src_path)
        log(f"  [{idx + 1}/{n}] {name}")
        try:
            if not os.path.isfile(src_path):
                raise FileNotFoundError("文件不存在")
            src = pymupdf.open(src_path)
            try:
                if src.needs_pass:
                    raise RuntimeError("文件已加密，需要密码，已跳过")
                pages_before = dst.page_count
                spans = parse_range(
                    ranges[idx] if ranges and idx < len(ranges) else None,
                    src.page_count,
                )
                added = 0
                for a, b in spans:
                    dst.insert_pdf(src, from_page=a, to_page=b)
                    added += b - a + 1
                if added == 0:
                    raise RuntimeError("指定范围内没有页面")
                total_pages += added
                if keep_bookmarks and len(inputs) > 1:
                    toc.extend(_bookmark_entries(src, pages_before, name))
                current_offset += added
                log(f"       +{added} 页")
            finally:
                src.close()
        except Exception as e:  # noqa: BLE001 - 单文件失败不中断整批
            failed.append((name, str(e)))
            log(f"       [跳过] {e}")
        if progress:
            progress((idx + 1) / n * 100)

    if dst.page_count == 0:
        dst.close()
        raise RuntimeError("没有任何页面被合并，请检查输入文件")

    if toc:
        try:
            dst.set_toc(toc)
        except Exception as e:  # noqa: BLE001 - 书签失败不影响正文
            log(f"[警告] 书签写入失败：{e}")

    out_dir = os.path.dirname(os.path.abspath(out_path))
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    dst.save(out_path, garbage=3, deflate=True)
    dst.close()

    size_mb = os.path.getsize(out_path) / 1024 / 1024
    log(f"输出: {out_path}")
    log(f"共 {total_pages} 页，{size_mb:.1f} MB，用时 {time.time() - t0:.2f}s")
    if failed:
        log(f"[提示] {len(failed)} 个文件被跳过：" + "、".join(f[0] for f in failed))
    return out_path, total_pages, failed
