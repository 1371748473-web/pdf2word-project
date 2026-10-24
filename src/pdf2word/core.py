"""转换编排核心：类型判定 → 分支处理 → 输出。CLI 与 GUI 共用。"""

import os
import time


def convert_pdf(
    pdf_path,
    out_path=None,
    dpi=200,
    mode="auto",
    extract_image_text=True,
    log=print,
    progress=None,
):
    """转换单个 PDF，返回输出 docx 路径。

    mode: auto=自动判定 / text=强制直转 / scan=强制重建
    """
    import pymupdf

    from . import rebuild
    from .classify import classify_doc

    t0 = time.time()
    out_path = out_path or os.path.splitext(pdf_path)[0] + ".docx"
    doc = pymupdf.open(pdf_path)
    n = doc.page_count
    log(f"输入: {os.path.basename(pdf_path)}（{n} 页）")

    doc_type, page_types = classify_doc(doc)
    log("页面类型: {} → 文档判定: {}".format(" ".join(page_types), doc_type))

    use_direct = (doc_type == "text" and mode == "auto") or mode == "text"

    try:
        if use_direct:
            log("走文字页直转通道（pdf2docx，保排版）...")
            from pdf2docx import Converter

            cv = Converter(pdf_path)
            cv.convert(out_path, start=0, end=None)
            cv.close()
            if progress:
                progress(n, n)
            if extract_image_text:
                from . import imagetext

                # 先扫描文档中是否真的存在内嵌图片：无图则完全不加载 OCR 模型，
                # 可省掉约 9 秒的模型初始化开销（大多数纯文字 PDF 受益）。
                n_img = imagetext.count_docx_images(out_path)
                if n_img == 0:
                    log("文档中无内嵌图片，跳过图内文字检测（不加载 OCR 模型）")
                else:
                    log(f"检测输出文档中的图片文字（共 {n_img} 处图片）...")
                    engine = rebuild.get_ocr_engine()
                    hits = imagetext.enrich_direct_docx(out_path, engine, log)
                    if not hits:
                        log("未发现含文字的图片")
        else:
            log(f"走重建通道（版面分析 + OCR，DPI={dpi}）...")
            engine = rebuild.get_ocr_engine() if extract_image_text else None
            pages_blocks = []
            for i, page in enumerate(doc):
                ptype = page_types[i] if mode == "auto" else "scan"
                tag = "OCR重建" if ptype == "scan" else "文本层"
                log(f"  [{i + 1}/{n}] 第 {i + 1} 页 → {tag}")
                if ptype == "scan":
                    blocks = rebuild.scan_page_blocks(
                        page, dpi=dpi, extract_image_text=extract_image_text, log=log
                    )
                else:
                    blocks = rebuild.extract_text_blocks(
                        page, engine=engine, extract_image_text=extract_image_text
                    )
                pages_blocks.append(blocks)
                if progress:
                    progress(i + 1, n)
            rebuild.build_docx(out_path, pages_blocks)
    finally:
        doc.close()

    log(f"完成: {out_path}（用时 {time.time() - t0:.1f}s）")
    return out_path
