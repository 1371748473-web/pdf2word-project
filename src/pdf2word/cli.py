"""pdf2word 命令行入口。

用法示例（PDF 转 Word，v1.3 及以前的用法完全保留）：
    pdf2word input.pdf -o output.docx
    pdf2word input.pdf --mode scan --dpi 300
    pdf2word --gui                         # 启动图形界面

v1.4 新增子命令：
    pdf2word merge a.pdf b.pdf -o all.pdf
    pdf2word image in.pdf -o outdir --format png --mode separate --dpi 150
    pdf2word office a.docx b.xlsx -o outdir [--engine auto|com|libreoffice]
"""

import argparse
import os
import sys

#: v1.4 子命令；首参命中即走子命令解析，否则保持旧行为（避免破坏既有脚本）
TOOLS = ("merge", "image", "office")


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

    # 打包环境初始化：模型目录 + paddlex 依赖自检补丁（必须在导入 paddle 前）
    # fast=True：跳过 nvidia-smi 探测（省约 0.37 s），设备在真正转换前再探测，
    # 保证 `--help` 等纯命令行操作不被 GPU 检测拖慢。
    from .envsetup import ensure_env

    ensure_env(fast=True)

    argv = sys.argv[1:]
    if argv and argv[0] in TOOLS:
        sys.exit(_tool_main(argv[0], argv[1:]))

    ap = argparse.ArgumentParser(
        prog="pdf2word",
        description="PDF 转 Word：文字页保排版直转，扫描页版面分析 + OCR 重建，图内文字可编辑提取。",
    )
    ap.add_argument("pdf", nargs="?", help="输入 PDF 文件路径")
    ap.add_argument(
        "-o",
        "--output",
        help="输出 docx 路径或目录（目录时输出同名 .docx；默认与源文件同名同目录）",
    )
    ap.add_argument("--dpi", type=int, default=200, help="扫描页渲染 DPI（默认 200）")
    ap.add_argument(
        "--mode",
        choices=["auto", "text", "scan"],
        default="auto",
        help="auto=自动判定；text=强制 pdf2docx 直转；scan=强制 OCR 重建",
    )
    ap.add_argument(
        "--no-image-text",
        action="store_true",
        help="关闭图内文字提取（默认开启）",
    )
    ap.add_argument("--gui", action="store_true", help="启动图形界面")
    args = ap.parse_args()

    if args.gui or not args.pdf:
        from .gui import main as gui_main

        gui_main()
        return

    if not os.path.isfile(args.pdf):
        print(f"[错误] 文件不存在: {args.pdf}")
        sys.exit(1)

    out_path = args.output
    if out_path and os.path.isdir(out_path):
        out_path = os.path.join(
            out_path, os.path.splitext(os.path.basename(args.pdf))[0] + ".docx"
        )

    from .envsetup import ensure_device

    ensure_device()  # 真正转换前才探测 GPU（幂等）

    from .core import convert_pdf

    convert_pdf(
        args.pdf,
        out_path=out_path,
        dpi=args.dpi,
        mode=args.mode,
        extract_image_text=not args.no_image_text,
    )


def _tool_main(tool, argv):
    """v1.4 子命令分发。返回进程退出码。"""
    ap = argparse.ArgumentParser(
        prog=f"pdf2word {tool}",
        description={
            "merge": "合并多个 PDF 为一个文件",
            "image": "把 PDF 转为图片（多张独立 / 单张长图）",
            "office": "把 Office 文件转为 PDF",
        }[tool],
    )

    if tool == "merge":
        ap.add_argument("pdf", nargs="+", help="按给定顺序合并的 PDF 文件")
        ap.add_argument("-o", "--output", required=True, help="输出 PDF 路径")
        ap.add_argument(
            "--range", dest="ranges", action="append",
            help="为第 N 个文件指定页面范围（可重复，按顺序对应），如 --range 1-5,8",
        )
        ap.add_argument("--no-bookmarks", action="store_true", help="不保留源文件书签")
        args = ap.parse_args(argv)

        from .merge import merge_pdfs

        _, pages, failed = merge_pdfs(
            args.pdf, args.output, ranges=args.ranges,
            keep_bookmarks=not args.no_bookmarks,
        )
        print(f"完成：{pages} 页 → {args.output}")
        return 1 if failed else 0

    if tool == "image":
        ap.add_argument("pdf", help="输入 PDF")
        ap.add_argument("-o", "--outdir", required=True, help="输出目录")
        ap.add_argument("--format", default="png",
                        choices=["png", "jpg", "webp", "bmp", "tiff"])
        ap.add_argument("--mode", default="separate",
                        choices=["separate", "long"],
                        help="separate=每页一张；long=拼接长图")
        ap.add_argument("--dpi", type=int, default=150)
        ap.add_argument("--quality", type=int, default=90, help="JPG/WebP 质量")
        ap.add_argument("--prefix", help="输出文件名前缀")
        ap.add_argument("--gap", type=int, default=0, help="长图页间距（px）")
        ap.add_argument("--max-height", type=int, default=20000,
                        help="长图单卷最大高度（px），超出自动分卷")
        args = ap.parse_args(argv)

        from .pdf2img import pdf_to_images

        files = pdf_to_images(
            args.pdf, args.outdir, fmt=args.format, dpi=args.dpi,
            mode=args.mode, prefix=args.prefix, jpeg_quality=args.quality,
            gap=args.gap, max_height=args.max_height,
        )
        print(f"完成：生成 {len(files)} 个图片 → {args.outdir}")
        return 0 if files else 1

    # office
    ap.add_argument("files", nargs="+", help="docx / xlsx / pptx 文件")
    ap.add_argument("-o", "--outdir", help="输出目录（默认源文件同目录）")
    ap.add_argument("--engine", default="auto",
                    choices=["auto", "com", "dxpdf", "libreoffice"],
                    help="auto=自动（Office>内置docx>LibreOffice）；com=仅本机 Office；"
                         "dxpdf=仅内置 docx 引擎；libreoffice=仅 LibreOffice")
    args = ap.parse_args(argv)

    from .office2pdf import convert_many

    ok, fail, used, skipped, _failed_files = convert_many(
        args.files, out_dir=args.outdir, engine=args.engine
    )
    print(f"完成：成功 {ok} 个，失败 {fail} 个（引擎：{used}）")
    return 1 if fail or skipped else 0


if __name__ == "__main__":
    main()
