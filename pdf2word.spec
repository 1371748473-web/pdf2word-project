# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)

datas = [
    (os.path.join(SPECPATH, "app_icon.ico"), "."),
    # v1.4：QSS 用的箭头图标（QComboBox 设了 border 后必须自带 down-arrow）
    (os.path.join(SPECPATH, "src", "pdf2word", "ui", "assets"), "pdf2word/ui/assets"),
]
binaries = []
hiddenimports = []

# 说明：曾尝试改用 collect_submodules + collect_data_files + collect_dynamic_libs
# 以剔除重复的 .py 源码，结果导致 paddle 出现循环导入/半初始化
# （AttributeError: partially initialized module 'paddle' has no attribute 'tensor'）。
# 遂保持 collect_all —— v1.2 扫描页崩溃的真正根因并非重复源码，
# 而是 spec 排除了 paddlex 顶层依赖的 huggingface_hub 与 pandas。
for pkg in ["paddle", "paddlex", "paddleocr", "pdf2docx", "pymupdf"]:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# nvidia CUDA 运行时包（paddlepaddle-gpu 依赖）：DLL 在各子包的 bin/ 目录
#
# 只收集推理真正必需的三个包（实测：仅这三个即可跑通 GPU 版版面分析 + OCR）：
#   cublas       609 MB —— 矩阵运算，CNN 推理核心
#   cudnn        811 MB —— 卷积 / 池化等算子
#   cuda_runtime   6 MB —— CUDA Runtime API
#
# 不收集（并说明原因，避免后人误加回来）：
#   cusolver 213 MB —— 线性方程求解，OCR 推理用不到
#   cusparse 275 MB —— 只被 cusolver 依赖
#   nvjitlink 84 MB —— 只被 cusparse 依赖
#   cufft     265 MB —— FFT，本工具不涉及
#   curand     63 MB —— 随机数，本工具不涉及
#
# 【v1.2 扫描页必崩的真根因】v1.2 收集了 cusolver 却排除了 cusparse，
# 而 cusolver64_11.dll 的导入表里硬依赖 cusparse64_12.dll。paddle/__init__.py
# 会 glob 加载 nvidia/*/bin/*.dll，于是加载 cusolver 时报
#   OSError: [WinError 126] 找不到指定的模块 ... cusolver64_11.dll
# 该错误发生在 paddle 初始化末尾，早期被 paddle.tensor 报错掩盖，所以一直没暴露。
for pkg in [
    "nvidia.cublas",
    "nvidia.cuda_runtime",
    "nvidia.cudnn",
]:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

# paddlex 在创建 OCR pipeline 时会用 importlib.metadata 核对 ocr-core extra
# 的依赖是否安装；打包环境缺少这些 dist-info 元数据会抛 DependencyError。
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
        # 以下为传递依赖，源码未直接使用
        # 注意：pandas 不能排除。paddlex/inference/common/result/mixin.py 等
        # 多处在顶层 import pandas，缺失会让 paddlex 导入中途失败。
        # （matplotlib / torch 均为函数内延迟 import，可安全排除）
        # 注意：huggingface_hub 不能排除。paddlex/inference/utils/official_models.py
        # 顶层 import 了它，缺失会导致 paddlex 导入中途失败，进而引发
        # "PDX has already been initialized" 这种误导性报错（约 8 MB，代价很小）
        "hf_xet",
        "tkinter", "_tkinter",
        "Crypto",
    ],
    noarchive=False,
)

# ---- 过滤不需要的二进制文件，减小打包体积 ----
_strip_binaries = [
    # PySide6: 仅保留 QtWidgets/QtGui/QtCore/QtNetwork，裁剪 QML/PDF 等模块
    "Qt6Quick", "Qt6Qml", "Qt6QmlModels", "Qt6QmlMeta", "Qt6Pdf",
    "Qt6VirtualKeyboard", "Qt6DataVisualization",
    "Qt6Charts", "Qt6Multimedia", "Qt6WebEngine", "Qt6WebChannel",
    "Qt6Positioning", "Qt6Sensors", "Qt6SerialPort", "Qt6Bluetooth",
    "Qt6Designer", "Qt6Help", "Qt6Location", "Qt6Nfc", "Qt6RemoteObjects",
    "Qt6Scxml", "Qt6SpatialAudio", "Qt6Sql", "Qt6Test", "Qt6UiTools",
    # 软件渲染器（有显卡时不需要；若目标机器无显卡需保留）
    "opengl32sw",
    # paddle: C++ 头文件仅编译时需要，运行时无用
    # 注意：必须用正斜杠。_should_strip() 会把待判路径的 "\\" 统一替换成 "/"，
    # 若这里写成 os.sep（Windows 下为 "\\"）将永远匹配不上（v1.2 的历史 bug）。
    "paddle/include",
    # 注意：paddle/distributed 不能裁剪。虽然它是分布式训练组件，
    # 但 paddle/__init__.py 的初始化链会导入它；删掉 distributed/__init__.py
    # 会导致 `import paddle` 中途失败（表现为
    # "partially initialized module 'paddle' has no attribute 'tensor'"）。
    # 代价仅约 11 MB，保留。
    # OpenCV 视频编解码（ffmpeg）：本工具只做图像读取/缩放/裁剪，不涉及视频
    "opencv_videoio_ffmpeg",
    # 注释：cusolver 已整体不打包（见上方 nvidia 收集说明），故此条不再生效。
    # 若将来重新收集 cusolver，可安全裁剪 cusolverMg（cusolver64_11 不依赖它，省 81 MB）
    "cusolverMg",
    # 时区数据：本工具无时区相关逻辑
    "tzdata",
]

def _should_strip(dest):
    """判断该二进制目标路径是否应被裁剪。"""
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

# 控制台版：同一套运行时，便于命令行转换与打包自检
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
    name="PDFToolbox",
)
