# -*- mode: python ; coding: utf-8 -*-
"""精简版（Lite）打包配置 —— 不含 CUDA 运行时，使用 CPU 推理。

构建前提：
  1. 需要单独的 CPU 虚拟环境（安装 paddlepaddle 而非 paddlepaddle-gpu）
     运行 scripts/setup_cpu_venv.ps1 创建 .venv-cpu
  2. 在 CPU venv 下执行：
     pyinstaller pdf2word-lite.spec --noconfirm

GPU 加速支持通过安装后下载 gpu_support.zip 来添加，无需重新打包。

体积对比（预估）：
  GPU 完整版: ~3.4 GB（含 CUDA 库 2.3 GB）
  精简版:     ~1.0 GB（纯 CPU，无 CUDA）
  + GPU 包:  ~1.5 GB（安装时按需下载）
"""
import os
from PyInstaller.utils.hooks import collect_all, copy_metadata

datas = [
    (os.path.join(SPECPATH, "app_icon.ico"), "."),
    # v1.4：QSS 用的箭头图标（QComboBox 设了 border 后必须自带 down-arrow）
    (os.path.join(SPECPATH, "src", "pdf2word", "ui", "assets"), "pdf2word/ui/assets"),
]
binaries = []
hiddenimports = []

# 保持 collect_all（原因同 pdf2word.spec：改用拆分收集器会导致 paddle 循环导入）
for pkg in ["paddle", "paddlex", "paddleocr", "pdf2docx", "pymupdf"]:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# ---- 精简版：不收集任何 nvidia CUDA 包 ----
# GPU 支持通过安装后下载 gpu_support.zip 添加

# paddlex 元数据（同 GPU 版）
for dist in [
    "imagesize",
    "opencv-contrib-python",
    "pyclipper",
    "pypdfium2",
    "python-bidi",
    "shapely",
]:
    try:
        datas += copy_metadata(dist)
    except Exception:
        pass

hiddenimports += [
    "pdf2word",
    "pdf2word.cli",
    "pdf2word.gui",
    "pdf2word.core",
    "pdf2word.rebuild",
    "pdf2word.classify",
    "pdf2word.layout",
    "pdf2word.table",
    "pdf2word.imagetext",
    "pdf2word.envsetup",
    "pdf2word.gpu_installer",
    "pdf2word.merge",
    "pdf2word.pdf2img",
    "pdf2word.office2pdf",
    "pdf2word.minicom",
    "pdf2word.ui",
    "pdf2word.ui.common",
    "pdf2word.ui.theme",
    "pdf2word.ui.widgets",
    "pdf2word.ui.page_base",
    "pdf2word.ui.page_word",
    "pdf2word.ui.page_merge",
    "pdf2word.ui.page_image",
    "pdf2word.ui.page_office",
    "dxpdf",
    "pdf2word.ui.dialog_guide",
]

a = Analysis(
    [os.path.join(SPECPATH, "app_entry.py")],
    pathex=[os.path.join(SPECPATH, "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    # 修复冻结环境下 paddle 子模块未绑定回父包导致的
    # "partially initialized module 'paddle' has no attribute 'tensor'"
    runtime_hooks=[os.path.join(SPECPATH, "scripts", "pyi_rth_paddle.py")],
    excludes=[
        "torch", "tensorflow", "matplotlib",
        # 注意：pandas 不能排除（paddlex 顶层 import 它），详见 pdf2word.spec
        # 注意：huggingface_hub 不能排除（paddlex 顶层 import 它），详见 pdf2word.spec
        "hf_xet",
        "tkinter", "_tkinter",
        "Crypto",
        # 精简版：排除所有 CUDA 包
        "nvidia", "nvidia.cublas", "nvidia.cuda_runtime",
        "nvidia.cudnn", "nvidia.cufft", "nvidia.curand",
        "nvidia.cusolver", "nvidia.cusparse", "nvidia.nvjitlink",
    ],
    noarchive=False,
)

# ---- 过滤不需要的二进制文件 ----
_strip_binaries = [
    "Qt6Quick", "Qt6Qml", "Qt6QmlModels", "Qt6QmlMeta", "Qt6Pdf",
    "Qt6VirtualKeyboard", "Qt6DataVisualization",
    "Qt6Charts", "Qt6Multimedia", "Qt6WebEngine", "Qt6WebChannel",
    "Qt6Positioning", "Qt6Sensors", "Qt6SerialPort", "Qt6Bluetooth",
    "Qt6Designer", "Qt6Help", "Qt6Location", "Qt6Nfc", "Qt6RemoteObjects",
    "Qt6Scxml", "Qt6SpatialAudio", "Qt6Sql", "Qt6Test", "Qt6UiTools",
    "opengl32sw",
    # 注意：必须用正斜杠，原因同 pdf2word.spec（_should_strip 已统一路径分隔符）
    "paddle/include",
    # 注意：paddle/distributed 不能裁剪（paddle 初始化链会导入它），详见 pdf2word.spec
    # OpenCV 视频编解码（ffmpeg）：本工具不涉及视频
    "opencv_videoio_ffmpeg",
    # 时区数据：本工具无时区相关逻辑
    "tzdata",
]

def _should_strip(dest):
    d = dest.replace("\\", "/").lower()
    for s in _strip_binaries:
        if s.lower() in d:
            return True
    return False

a.binaries = [b for b in a.binaries if not _should_strip(b[1])]
a.datas = [d for d in a.datas if not _should_strip(d[1])]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PDF工具箱",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=os.path.join(SPECPATH, "app_icon.ico"),
)

exe_cli = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="pdf2word-cli",
    debug=False,
    strip=False,
    upx=False,
    console=True,
    icon=os.path.join(SPECPATH, "app_icon.ico"),
)

coll = COLLECT(
    exe,
    exe_cli,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PDFToolbox-Lite",
)
