"""PDF 转图片：支持多张独立 / 单张长图两种模式。

性能说明（v1.4 实测，2026-10-22）：
    PyMuPDF 的 get_pixmap() 在渲染期受 GIL 约束，多线程**不会**提速——
    30 页 @150dpi 实测 PNG 单线程 68 ms/页，4 线程反而 103 ms/页（慢 52%）。
    因此本模块采用单线程流式渲染；打包环境下也不引入多进程（freeze_support 与
    子进程重载 exe 的开销大于收益）。

无 Qt 依赖，GUI 与 CLI 共用。
"""

import os
import time

#: 支持的输出格式 → Pillow 格式名
FORMATS = {
    "png": "PNG",
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "webp": "WEBP",
    "bmp": "BMP",
    "tif": "TIFF",
    "tiff": "TIFF",
}

#: JPEG 无损/有损判断（决定是否需要铺白底）
_LOSSY = {"jpg", "jpeg", "bmp"}

#: 长图单卷最大高度（像素）。超过则自动分卷，避免超大图撑爆内存与 JPG 上限。
DEFAULT_MAX_HEIGHT = 20000


def _norm_fmt(fmt):
    f = (fmt or "png").lower().lstrip(".")
    if f == "jpeg":
        f = "jpg"
    if f == "tif":
        f = "tiff"
    if f not in FORMATS:
        raise ValueError(f"不支持的图片格式: {fmt}")
    return f


def _save_pixmap(pix, path, fmt, quality=90):
    """保存渲染结果。

    PyMuPDF 原生编码只支持 png/jpg/pnm/psd/ps（1.28 实测），
    webp/bmp/tiff 需转 PIL 保存——因此只对 png/jpg 走原生快速路径。
    """
    if fmt == "png":
        pix.save(path)
        return
    if fmt == "jpg":
        try:
            pix.save(path, jpg_quality=int(quality))
            return
        except TypeError:
            pass  # 老版本 PyMuPDF 无该参数，落到 PIL

    from PIL import Image

    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    try:
        if fmt == "jpg":
            img.save(path, "JPEG", quality=int(quality), optimize=True)
        elif fmt == "webp":
            img.save(path, "WEBP", quality=int(quality))
        else:
            img.save(path, FORMATS[fmt])
    finally:
        img.close()


def pdf_to_images(
    pdf_path,
    out_dir,
    fmt="png",
    dpi=150,
    mode="separate",
    prefix=None,
    start_index=1,
    jpeg_quality=90,
    gap=0,
    bg="white",
    max_height=DEFAULT_MAX_HEIGHT,
    log=print,
    progress=None,
    should_stop=None,
):
    """把 PDF 转为图片。

    mode: "separate" = 每页一张；"long" = 垂直拼接为长图（超限自动分卷）
    返回生成的图片路径列表。
    """
    import pymupdf

    fmt = _norm_fmt(fmt)
    if mode not in ("separate", "long"):
        raise ValueError(f"未知输出模式: {mode}")
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"文件不存在: {pdf_path}")

    os.makedirs(out_dir, exist_ok=True)
    base = prefix or os.path.splitext(os.path.basename(pdf_path))[0]
    doc = pymupdf.open(pdf_path)
    n = doc.page_count
    written = []
    t0 = time.time()

    try:
        if mode == "separate":
            for i, page in enumerate(doc):
                if should_stop and should_stop():
                    log("已取消")
                    break
                pix = page.get_pixmap(dpi=dpi, alpha=False)
                out = os.path.join(
                    out_dir, f"{base}_{i + start_index:04d}.{fmt}"
                )
                _save_pixmap(pix, out, fmt, jpeg_quality)
                written.append(out)
                log(f"  [{i + 1}/{n}] {os.path.basename(out)}")
                if progress:
                    progress((i + 1) / n * 99)
        else:
            written = _render_long(
                doc, out_dir, base, fmt, dpi, jpeg_quality, gap, bg,
                max_height, log, progress, should_stop,
            )
    finally:
        doc.close()

    if should_stop and should_stop() and written:
        log("已取消，清理本次生成的文件")
        for p in written:
            try:
                os.remove(p)
            except OSError:
                pass
        return []

    total_mb = sum(os.path.getsize(p) for p in written) / 1024 / 1024
    log(f"共生成 {len(written)} 个文件，{total_mb:.1f} MB，"
        f"用时 {time.time() - t0:.2f}s")
    if progress:
        progress(100)
    return written


def _render_long(doc, out_dir, base, fmt, dpi, quality, gap, bg,
                 max_height, log, progress, should_stop):
    """流式拼接长图，按 max_height 自动分卷。

    先按页面尺寸估算高度并分组，再逐页渲染粘贴，避免整册驻留内存。
    """
    from PIL import Image

    n = doc.page_count
    # 1) 估算每页像素尺寸（与 get_pixmap 的取整规则一致）
    sizes = []
    for page in doc:
        r = page.rect
        sizes.append((max(1, round(r.width * dpi / 72)),
                      max(1, round(r.height * dpi / 72))))
    width = max(s[0] for s in sizes)

    # 2) 分组：每卷不超过 max_height
    groups, cur, cur_h = [], [], 0
    for idx, (_, h) in enumerate(sizes):
        extra = h + (gap if cur else 0)
        if cur and cur_h + extra > max_height:
            groups.append(cur)
            cur, cur_h = [idx], h
        else:
            cur.append(idx)
            cur_h += extra
    if cur:
        groups.append(cur)

    multi = len(groups) > 1
    written = []
    for gi, group in enumerate(groups):
        if should_stop and should_stop():
            log("已取消")
            break
        total_h = sum(sizes[i][1] for i in group) + gap * (len(group) - 1)
        canvas = Image.new("RGB", (width, total_h), bg)
        y = 0
        for k, i in enumerate(group):
            if should_stop and should_stop():
                break
            pix = doc[i].get_pixmap(dpi=dpi, alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            if img.width != width:
                # 页面宽度不一致时水平居中
                canvas.paste(img, ((width - img.width) // 2, y))
            else:
                canvas.paste(img, (0, y))
            y += img.height + gap
            done = sum(len(g) for g in groups[:gi]) + k + 1
            if progress:
                progress(done / n * 99)
            log(f"  拼接 [{done}/{n}]")

        suffix = f"_长图_{gi + 1}" if multi else "_长图"
        out = os.path.join(out_dir, f"{base}{suffix}.{fmt}")
        if fmt in ("jpg", "jpeg"):
            canvas.save(out, "JPEG", quality=int(quality), optimize=True)
        elif fmt == "png":
            canvas.save(out, "PNG", optimize=True)
        else:
            canvas.save(out, FORMATS[fmt])
        written.append(out)
        log(f"  输出 {os.path.basename(out)}（{width}x{total_h} px）")
        canvas.close()
    return written
