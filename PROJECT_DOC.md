# PDF 工具箱 — 项目技术文档

> 本文档面向计算机专业开发者，目标是让任何新人可以立即接手本项目。
> 最后更新：2026-10-22（v1.4 新增 PDF 合并 / PDF 转图片 / Office 转 PDF）

---

## 一、项目概述

### 1.1 产品定位

**PDF 工具箱** 是一款 Windows 桌面工具，v1.4 起由单一「PDF 转 Word」扩展为四个功能：

| 功能 | 入口 | 说明 |
|------|------|------|
| PDF 转 Word | 主界面 | 文字页保排版直转，扫描页 OCR 重建（原有能力） |
| PDF 合并 | 工具菜单 | 多文件合并，可调顺序、可指定页面范围、可保留书签 |
| PDF 转图片 | 工具菜单 | PNG/JPG/WebP/BMP/TIFF，多张独立或单张长图（超限自动分卷） |
| Office 转 PDF | 工具菜单 | docx/xlsx/pptx，双引擎：本机 Office（COM）优先，内置 LibreOffice 兜底 |

PDF 转 Word 的核心能力：
- **文字页**：通过 `pdf2docx` 直接转换，保留原始排版与字体样式。
- **扫描页**：渲染为图像 → 版面分析（PP-DocLayoutV3）→ OCR（PaddleOCR v6）→ 段落重组 → 写入 Word。
- **图内文字**：对图片区域额外运行文字检测，提取图内文字并以灰色斜体标注在 Word 中。
- **表格**：SLANet_plus 模型识别表格结构，OCR 回填单元格文字，输出 Word 原生表格。
- **GPU 加速**：自动检测 NVIDIA GPU，使用 CUDA 推理，无 GPU 时自动回退 CPU。
- **双版本发布**：GPU 完整版（含 CUDA 运行时）和精简版（CPU 推理，可在线升级 GPU 支持）。

### 1.2 技术栈

| 层级 | 技术 |
|------|------|
| 语言 | Python 3.12 |
| GUI | PySide6（Qt 6） |
| PDF 解析 | PyMuPDF (fitz) |
| 文字页转换 | pdf2docx |
| OCR 引擎 | PaddleOCR 3.7+（PP-OCRv6） |
| 版面分析 | PaddleX PP-DocLayoutV3 |
| 表格识别 | PaddleX SLANet_plus |
| 深度学习框架 | paddlepaddle-gpu 3.3.0（CUDA 12.6） |
| 打包 | PyInstaller 6.22 |
| 安装包 | Inno Setup 6.7（ISCC） |
| 操作系统 | Windows 10/11 x64 |

### 1.3 性能指标

| 场景 | CPU | GPU (RTX 3060) |
|------|-----|----------------|
| 扫描页单页转换 | ~100s | ~18-28s |
| 安装包体积（GPU 完整版） | — | ~1020 MB |
| 安装包体积（精简版） | ~291 MB | — |
| 首次启动（模型加载） | ~15s | ~20s |

---

## 二、项目结构

```
E:\PDF2WordTool\
├── app_entry.py              # PyInstaller 打包入口
├── app_icon.ico              # 应用图标
├── pdf2word.iss              # Inno Setup 安装脚本（GPU 完整版）
├── pdf2word.spec             # PyInstaller 打包配置（GPU 完整版）
├── pdf2word-lite.iss         # Inno Setup 安装脚本（精简版）
├── pdf2word-lite.spec        # PyInstaller 打包配置（精简版，不含 CUDA）
├── pyproject.toml            # 项目元数据与依赖
├── run.bat                   # 开发环境快速启动脚本
├── 使用说明.txt              # 用户说明
│
├── src/
│   └── pdf2word/             # 核心包
│       ├── __init__.py       # 包初始化
│       ├── __main__.py       # python -m pdf2word 入口
│       ├── cli.py            # 命令行参数解析
│       ├── core.py           # 转换主流程编排
│       ├── classify.py       # 页面类型分类（文字/扫描）
│       ├── rebuild.py        # 扫描页重建（OCR + 版面分析 + docx 组装）
│       ├── layout.py         # 版面分析模块（PP-DocLayoutV3）
│       ├── table.py          # 表格识别模块（SLANet_plus）
│       ├── imagetext.py      # 图内文字检测
│       ├── envsetup.py       # 环境初始化（GPU 检测、DLL 注册、模型路径）
│       ├── gpu_installer.py  # GPU 加速支持在线下载与安装
│       ├── gui.py            # 主窗口（PDF 转 Word + 工具菜单）
│       ├── merge.py          # v1.4：PDF 合并
│       ├── pdf2img.py        # v1.4：PDF 转图片
│       ├── office2pdf.py     # v1.4：Office 转 PDF（双引擎调度 + 残留进程清理）
│       ├── minicom.py        # v1.4：ctypes COM 封装（零依赖，不含 pywin32）
│       └── ui/               # v1.4：三个工具弹窗
│           ├── common.py     #   共用控件（FileDropList / TaskThread / ToolDialog）
│           ├── dialog_merge.py
│           ├── dialog_image.py
│           └── dialog_office.py
│
├── scripts/                  # 可复用构建工具（一次性实验脚本已移至 experiments/）
│   ├── make_icon.py          # 图标生成辅助脚本
│   ├── make_samples.py       # 测试样本生成
│   ├── download_gpu_support.py  # GPU 支持下载命令行脚本
│   ├── make_gpu_pack.py      # GPU 支持包打包脚本
│   ├── pyi_rth_paddle.py     # PyInstaller runtime hook（spec 引用，勿移动）
│   └── setup_cpu_venv.ps1    # CPU 虚拟环境创建脚本
│
├── tests/
│   └── samples/              # 测试 PDF 样本
│       ├── sample_mixed.pdf
│       ├── sample_scan.pdf
│       ├── sample_text.pdf
│       └── sample_text_noimg.pdf
│
├── experiments/              # 一次性实验归档（不参与打包，见其 README）
│   ├── README.md             # 归档总览与索引
│   ├── onednn/               # CPU oneDNN 加速可行性实验（结论：不可用）
│   ├── benchmarks/           # v1.3 性能基准/懒加载验证脚本与产物
│   ├── cpu_lite/             # 精简版扫描页运行日志
│   ├── outputs/              # v1.0~v1.3 历史转换结果 docx（回归对照）
│   └── packaging/            # v1.2 构建/安装日志、随包说明文本
│
├── model_cache/              # PaddleX 模型缓存（通过 junction 指向实际位置）
│   └── models/official_models/
│       ├── PP-DocLayoutV3/
│       ├── PP-OCRv6_medium_det/
│       ├── PP-OCRv6_medium_rec/
│       └── SLANet_plus/
│
├── paddlex_cache/            # PaddleX 推理缓存
├── .venv/                    # GPU 开发虚拟环境（paddlepaddle-gpu）
├── .venv-cpu/               # CPU 打包虚拟环境（paddlepaddle）
├── dist/
│   ├── PDF转Word/           # GPU 完整版 PyInstaller 输出
│   │   ├── PDF转Word.exe    # GUI 主程序
│   │   ├── pdf2word-cli.exe # 命令行版本
│   │   └── _internal/       # 运行时依赖（含 nvidia CUDA DLL）
│   └── PDF转Word-Lite/      # 精简版 PyInstaller 输出（不含 CUDA）
│       ├── PDF转Word.exe
│       ├── pdf2word-cli.exe
│       └── _internal/       # 运行时依赖（无 nvidia 目录）
│
└── installer_out/            # Inno Setup 安装包输出
    ├── PDF转Word-Setup-1.3.exe       # GPU 完整版安装包（v1.3）
    └── PDF转Word-Lite-Setup-1.3.exe  # 精简版安装包（v1.3）
```

---

## 三、核心架构

### 3.1 转换流程

```
PDF 输入
  │
  ▼
┌─────────────────────────────────────────┐
│ core.py: convert_pdf()                  │
│  逐页遍历 → classify.py 判定页面类型     │
│  ┌──────────────┬──────────────────┐    │
│  │ 文字页        │ 扫描页            │    │
│  │ pdf2docx直转  │ rebuild.py 重建   │    │
│  └──────────────┴──────────────────┘    │
│  收集所有页的 blocks → build_docx()     │
└─────────────────────────────────────────┘
  │
  ▼
Word (.docx) 输出
```

### 3.2 块（Block）格式

所有页面内容统一表示为 block 元组，供 `build_docx()` 渲染：

```python
("para", text, pt, bold[, style])     # 文本段落，style 可选 "gray"
("image", data_bytes, ext[, ratio])   # 图片，ratio 为图宽占页宽比例
("table", grid)                       # 表格，grid=[[{"text":str,"colspan":int},...],...]
```

### 3.3 页面分类（classify.py）

通过 PyMuPDF 提取文本，按字符密度判定：
- 字符密度 > 阈值 → 文字页（text）
- 否则 → 扫描页（scan）

### 3.4 扫描页重建（rebuild.py）

```
扫描页
  │
  ▼
render_page() → PIL Image (numpy array)
  │
  ▼
layout.detect_regions() → 版面区域列表
  │
  ├─ 模型不可用 → 退化为整页 OCR
  │
  ▼
区域分类（text / table / image / skip）
  │
  ├─ text  → OCR + 段落聚合 → ("para", ...)
  ├─ table → SLANet_plus 结构识别 + OCR 回填 → ("table", grid)
  ├─ image → 保存 PNG → ("image", data, "png", ratio)
  │         └─ imagetext.detect_image_text() → ("para", MARK+text, ..., "gray")
  └─ 未覆盖区域兜底 OCR
  │
  ▼
blocks 列表 → build_docx() → Word 文档
```

### 3.5 GPU 推理架构（envsetup.py）

```
启动
  │
  ▼
ensure_env()
  ├─ _detect_gpu()          # 检查 nvidia-smi（兼容不在 PATH 中的情况）
  │   └─ 设置 PDF2WORD_DEVICE 环境变量
  ├─ 模型目录定位
  └─ paddlex 依赖补丁
  │
  ▼
用户触发转换
  │
  ▼
activate_gpu_device()       # 惰性调用，首次模型加载前执行
  ├─ _register_nvidia_dll_dirs()   # os.add_dll_directory() 注册 DLL 搜索路径
  │   └─ 支持从 _internal/nvidia/ 子目录加载（精简版安装 GPU 支持后）
  ├─ import paddle
  └─ paddle.set_device("gpu")
  │
  ▼
模型加载（OCR / 版面 / 表格）
```

**设计要点**：
- `_detect_gpu()` 通过 `_find_nvidia_smi()` 在 PATH 和常见安装路径中查找 nvidia-smi，不导入 paddle，避免打包环境循环导入。
- `activate_gpu_device()` 延迟到模型加载前调用，确保 DLL 路径已注册。
- 精简版安装 GPU 支持后，CUDA DLL 位于 `_internal/nvidia/` 子目录，`_register_nvidia_dll_dirs()` 会自动扫描并注册。
- 无 GPU 时所有模型自动使用 CPU，无需任何配置。

### 3.6 精简版 GPU 在线升级架构（gpu_installer.py）

```
用户点击「工具 → 下载 GPU 加速支持」
  │
  ▼
GpuInstaller.install()
  ├─ 检查 NVIDIA GPU（nvidia-smi）
  ├─ 检查是否已安装（nvidia 目录 + 关键 DLL）
  │
  ├─ 下载 nvidia CUDA 包（从清华/阿里云 PyPI 镜像）
  │   ├─ nvidia-cublas-cu12 → cublas/
  │   ├─ nvidia-cuda-runtime-cu12 → cuda_runtime/
  │   ├─ nvidia-cudnn-cu12 → cudnn/
  │   ├─ nvidia-cusolver-cu12 → cusolver/
  │   └─ nvidia-nvjitlink-cu12 → nvjitlink/
  │   └─ 从 wheel 中提取 .dll 到 _internal/nvidia/
  │
  ├─ 下载 paddlepaddle-gpu（从 PaddlePaddle 官网 CDN）
  │   └─ 提取 paddle/libs/*.dll，备份 CPU 版（.cpu 后缀）
  │
  └─ 验证安装 → 提示重启程序
```

**卸载流程**：删除 nvidia 目录，恢复 .cpu 备份的 DLL。

---

## 四、源码文件详解

### 4.1 envsetup.py — 环境初始化

**职责**：GPU 检测、DLL 注册、模型目录定位、paddlex 依赖补丁。

**关键函数**：

| 函数 | 说明 |
|------|------|
| `_find_nvidia_smi()` | 在 PATH 和常见安装路径中查找 nvidia-smi 可执行文件 |
| `_detect_gpu()` | 通过 nvidia-smi 检测 GPU，设置 `PDF2WORD_DEVICE` 环境变量 |
| `_register_nvidia_dll_dirs()` | 遍历 nvidia.* 子包的 bin/ 目录，调用 `os.add_dll_directory()` |
| `activate_gpu_device()` | 注册 DLL 路径 → 导入 paddle → `paddle.set_device("gpu")` |
| `ensure_env()` | 入口函数，调用 `_detect_gpu()` + 模型目录定位 + paddlex 补丁 |

**环境变量**：
- `PDF2WORD_DEVICE`：`"gpu"` 或 `"cpu"`，由 `_detect_gpu()` 设置
- `PDF2WORD_MODEL_DIR`：模型目录，打包时指向 `_internal/models/`

### 4.2 core.py — 转换主流程

**职责**：编排整个 PDF 转换流程。

**关键函数**：

| 函数 | 说明 |
|------|------|
| `convert_pdf()` | 主入口：打开 PDF → 逐页分类 → 收集 blocks → 输出 docx |
| `_convert_text_page()` | 文字页：pdf2docx 直转 |
| `_convert_scan_page()` | 扫描页：调用 rebuild.scan_page_blocks() |

### 4.3 rebuild.py — 扫描页重建

**职责**：OCR 引擎管理、版面分析调度、段落聚合、docx 组装。

**关键函数**：

| 函数 | 说明 |
|------|------|
| `get_ocr_engine()` | 惰性创建 PaddleOCR 单例，调用 `activate_gpu_device()` |
| `ocr_lines_arr()` | 对 numpy 图像执行 OCR，返回行级结果 |
| `group_lines()` | 按阅读顺序排序并聚合为段落 |
| `scan_page_blocks()` | 扫描页完整重建流程 |
| `extract_text_blocks()` | 文字页内容提取（利用 PDF 文本层，保真度更高） |
| `build_docx()` | 将 blocks 列表渲染为 Word 文档 |

### 4.4 layout.py — 版面分析

**职责**：PP-DocLayoutV3 模型管理，区域检测与分类。

**关键函数**：

| 函数 | 说明 |
|------|------|
| `get_layout_model()` | 惰性加载版面模型 |
| `detect_regions()` | 检测页面区域，返回 `[{label, score, x0, y0, x1, y1}]` |
| `label_kind()` | 将区域标签归类为 text / table / image / skip |
| `sort_reading_order()` | 按阅读顺序排序区域 |

### 4.5 table.py — 表格识别

**职责**：SLANet_plus 模型管理，表格结构重建。

**关键函数**：

| 函数 | 说明 |
|------|------|
| `get_table_model()` | 惰性加载表格模型 |
| `reconstruct_table()` | 对裁剪的表格图像做结构识别 + OCR 回填 |

### 4.6 imagetext.py — 图内文字检测

**职责**：检测图片区域内的文字，用于辅助标注。

**关键常量**：
- `MARK`：图内文字标注前缀（如 `"[图内文字: ...]"`）

### 4.7 classify.py — 页面分类

**职责**：判断 PDF 页面是文字页还是扫描页。

**策略**：提取页面文本，按字符密度与阈值比较。

### 4.8 gui.py — 图形界面

**职责**：PySide6 GUI，提供文件选择、转换、进度显示、GPU 支持管理。

**功能**：
- 文件拖拽添加（支持从资源管理器拖入 PDF）
- 转换模式选择（auto / text / scan）
- DPI 设置、输出目录选择
- 进度条与日志输出
- 设备信息显示（GPU/CPU）
- **工具菜单**：
  - 「下载 GPU 加速支持」— 在线下载 CUDA 库和 paddlepaddle-gpu（精简版专用）
  - 「检查 GPU 状态」— 显示显卡型号、支持包安装状态、当前推理设备
  - 「卸载 GPU 支持」— 删除 CUDA 库，恢复 CPU 版 paddle DLL

**关键类**：

| 类 | 说明 |
|------|------|
| `DropList` | 支持拖拽的文件列表控件 |
| `Worker` | 转换后台线程，发射日志/进度/完成信号 |
| `GpuWorker` | GPU 支持下载后台线程，调用 GpuInstaller |
| `MainWindow` | 主窗口，管理 UI 和所有交互逻辑 |

### 4.9 gpu_installer.py — GPU 加速支持下载

**职责**：从国内 PyPI 镜像和 PaddlePaddle 官网下载 GPU 运行时库，安装到程序目录。

**关键函数/类**：

| 函数/类 | 说明 |
|------|------|
| `check_nvidia_gpu()` | 检查 NVIDIA GPU，返回名称或 None |
| `is_gpu_support_installed()` | 检查 GPU 支持是否已安装（nvidia 目录 + 关键 DLL） |
| `get_install_dir()` | 获取程序安装目录（打包环境为 _internal/） |
| `GpuInstaller` | GPU 支持下载安装器，支持进度回调、取消、重试 |
| `GpuInstaller.install()` | 完整安装流程：下载 CUDA 包 + paddlepaddle-gpu |
| `GpuInstaller.uninstall()` | 卸载 GPU 支持，恢复 CPU 版 DLL |

**下载源**：
- nvidia CUDA 包：清华源 → 阿里云 → 官方源（按优先级自动切换）
- paddlepaddle-gpu：PaddlePaddle 官网 CDN（`paddlepaddle.org.cn`）

### 4.10 cli.py — 命令行入口

**用法**：
```bash
pdf2word input.pdf -o output.docx
pdf2word input.pdf --mode scan --dpi 300
pdf2word --gui        # 启动图形界面
```

### 4.11 app_entry.py — PyInstaller 入口

**职责**：PyInstaller 打包后的入口点。无参数启动 GUI，有参数走命令行。

### 4.12 merge.py — PDF 合并（v1.4）

| 函数 | 说明 |
|------|------|
| `parse_range(text, page_count)` | "1-5,8" → `[(0,4),(7,7)]`，越界钳制、倒序自动交换、非法片段忽略 |
| `merge_pdfs(inputs, out_path, ranges, keep_bookmarks, log, progress, should_stop)` | 主流程，返回 `(输出路径, 页数, 失败列表)` |

要点：
- 用 `Document.insert_pdf()` 拼接，纯 C 层，100 页约 0.3 s。
- 单个文件失败（加密/损坏）只记入 `failed`，不中断整批。
- 书签：以源文件名为一级父书签，子书签页码按合并偏移量重算后 `set_toc()`。

### 4.13 pdf2img.py — PDF 转图片（v1.4）

| 函数 | 说明 |
|------|------|
| `pdf_to_images(...)` | 主入口，`mode="separate"` 每页一张 / `mode="long"` 长图 |
| `_render_long(...)` | 先按页面尺寸估算高度分组，再逐页渲染粘贴（流式，不分卷时也不整册驻留） |
| `_save_pixmap(...)` | png/jpg 走 PyMuPDF 原生编码；webp/bmp/tiff 走 PIL（PyMuPDF 不支持这三种） |

**关键结论（实测，勿再踩）**：
- PyMuPDF 渲染受 GIL 约束，**多线程是负优化**：30 页 @150dpi，PNG 单线程 68 ms/页，4 线程 103 ms/页（慢 52%）；JPG 单线程 103 ms/页，4 线程 148 ms/页（慢 44%）。故采用单线程流式。
- 长图必须分卷：30 页 @150dpi 拼成 1240×52650 px ≈ 196 MB 内存，默认 20000 px 上限。

### 4.14 office2pdf.py + minicom.py — Office 转 PDF（v1.4 起，v1.5 加三引擎）

**三引擎调度（v1.5）**：
```
auto → 逐类型选择，优先级 本机 Office(COM) > 内置 docx 引擎(dxpdf) > LibreOffice
        ├─ word(docx)  : COM → dxpdf → LO
        ├─ excel(xlsx) : COM → LO
        └─ ppt(pptx)   : COM → LO

dxpdf：12 MB（wheel）/ 27 MB（解压后单文件 dxpdf.pyd，自带 Skia），MIT 许可
       —— 纯本地排版引擎，转 docx 不需要任何办公软件，实测 1.5~1.9 s/文件，中文正常
       —— 只支持 docx，xlsx/pptx 仍需要 Office/WPS 或 LibreOffice
```

| 文件 | 关键点 |
|------|--------|
| `minicom.py` | ctypes + IDispatch 手写封装，约 180 行，**不依赖 pywin32/comtypes** |
| `office2pdf.py` | 引擎检测与逐类型调度、`-env:UserInstallation` 隔离 LO profile、残留进程清理、下载源常量 |
| `ui/dialog_guide.py` | `EngineGuideDialog`：缺引擎时的引导弹窗（国内镜像下载 / winget 命令） |

**为什么不用 PyMuPDF Pro 代替**（调研结论）：`pymupdf-office` 只有 6.2 MB 且支持全格式，
但是**商业授权**（无 key 只能读前 3 页），且官方文档说明它走 Office→HTML→PDF，
**原文分页与版式不保留**。故排除。

**下载源**：`LO_MIRRORS` 首选清华 TUNA（实测 HTTP 200，`Content-Length` 与官方
374,870,016 字节完全一致），备用官方主站；另提供 `winget install
TheDocumentFoundation.LibreOffice` 一键命令。

**导出调用**：
- Word：`Documents.Open(绝对路径, False, True, False)` → `SaveAs2(输出, 17)`
- Excel：`Workbooks.Open(绝对路径, 0, True)` → `ExportAsFixedFormat(0, 输出)`
- PowerPoint：`Presentations.Open(绝对路径, True, False, False)` → `SaveAs(输出, 32)`

**进程清理**：任务前用 Toolhelp32 记 PID 快照，任务后只结束「新增且无可见窗口」的 Office 进程。
绝不用 `taskkill /IM WINWORD.EXE`——会杀掉用户正在编辑的文档。

### 4.15 ui/ — 页面、控件与主题（v1.5 重构）

v1.5 把「单页 + 弹窗」改为**顶部 Tab 平铺 4 个功能页**，界面结构如下：

```
MainWindow
├── 品牌区（图标 / 标题 / 副标题 / 「⋯」次级菜单）
├── QTabWidget（PDF 转 Word · PDF 合并 · PDF 转图片 · Office 转 PDF）
│   └── BasePage 子类（每页统一：文件卡片 → 参数卡片 → 操作行 → 日志卡片）
├── StatusBar（任务状态 + 百分比 + 推理设备胶囊）
└── Toast（右上角浮层结果提示）
```

| 文件 | 职责 |
|------|------|
| `ui/page_base.py` | `BasePage`：卡片分区布局、主按钮状态机（禁用/处理中/停止）、进度反馈、折叠日志；`form_grid()` 两列表单 |
| `ui/page_word.py` | PDF 转 Word（DPI / 模式 / 复选框 / 输出位置） |
| `ui/page_merge.py` | PDF 合并（调序、双击设页面范围、书签） |
| `ui/page_image.py` | PDF 转图片（5 格式 × 独立/长图） |
| `ui/page_office.py` | Office 转 PDF（双引擎） |
| `ui/widgets.py` | `Card`、`FileList`、`FileRow`、`Toast`、`LogPanel`、`StatusBar` |
| `ui/common.py` | `TaskThread`（后台任务 + 日志/进度/取消） |
| `ui/dialog_failure.py` | `FailureDialog`：失败报告弹窗（列出失败文件 + 原因，支持「只重试失败的 N 个」） |
| `ui/theme.py` | 亮/暗双主题 QSS、`apply_theme()`、`detect_dark()`、`elevated()` |

**关键实现点**：
- **Tab 懒加载**：只构建当前页，其余先放占位控件；`MainWindow.page(idx)` 首次访问时创建并替换。
  实测：4 页全预建会让首屏多花 ~0.9 s；懒加载后单页构建仅 17~23 ms，切页 43~76 ms。
- **空状态与拖拽反馈**：`FileList.paintEvent` 在 `count()==0` 时绘制虚线框提示；拖拽进入时通过
  `dragActive` 动态属性把边框染成主题色（QSS `[dragActive="true"]`）。
- **文件行**：`setItemWidget` + `FileRow`（图标 + 名称 + 「N 页 · 体积」+ hover 删除按钮）；
  页数由 `_MetaWorker` 后台线程读取 pymupdf，避免卡 UI。
- **Toast**：`QGraphicsOpacityEffect` + 定位到父窗口右上角。
- **状态栏**：`set_busy()` 用 `◐◓◑◒` 帧动画表达进行中，`set_device()` 区分「GPU 加速已启用 / CPU 运行」胶囊。

**失败重试机制**（`ui/dialog_failure.py`）：
- 原则：**全部成功只弹 Toast**（不打断），有失败才弹窗。
- 弹窗列出每个失败文件与原因，主按钮是「只重试这 N 个」——只把失败项作为 `subset`
  传给 `_make_task(subset)`，已成功的文件不重跑。
- 失败信息由任务函数调用 `BasePage.note_failed(path, reason)` 累积；
  各页面统一签名为 `_make_task(self, subset=None)`。
- `CAN_RETRY_SUBSET` 类属性控制是否允许子集重试（合并页为 `False`，合并是整体操作）。
- 各页面容错：word / image 逐文件 try，单文件失败继续；office 用 `convert_many()`
  返回的 `failed_files`（第 5 个返回值）补齐失败详情。
- `dialog_failure` 必须在 `page_base` **模块顶层**导入（不能写在函数内），
  否则 PyInstaller 静态分析可能漏收该模块。

### 4.16 ui/theme.py — 视觉主题（v1.5 支持亮/暗双主题）

**职责**：全应用统一 QSS + 字体，替代 Qt Fusion 默认观感。

| 内容 | 说明 |
|------|------|
| `LIGHT` / `DARK` | 两套配色字典（`bg / card / border / text / accent / danger / log_bg / shadow` 等） |
| `build_qss(c)` | 约 400 行 QSS：卡片、Tab、主按钮渐变、输入控件、拖拽列表、进度条、复选、菜单、Toast、滚动条 |
| `apply_theme(app, dark)` | 设 Fusion 底座 + 字体 + QSS，约 6 ms；同时把 `darkMode` 记到 app 属性供控件取色 |
| `detect_dark()` | 读 `HKCU\...\Themes\Personalize\AppsUseLightTheme`，跟随系统 |
| `elevated(widget, c)` | 卡片轻投影（QSS 不支持 box-shadow，只能用 `QGraphicsDropShadowEffect`） |
| `assets/` | `chevron-down` / `caret-up` / `caret-down` / `check-white`，8 倍超采样生成 |

**必踩的 Qt 坑**：
1. 给 `QComboBox` 设了 `border` 后，Qt **不再绘制默认箭头**。不补图 → 右侧一片空白；
   用 `subcontrol-position` 但没给 `down-arrow` 图 → 渲染成实心小方块。`QSpinBox` 上下箭头同理。
2. 复选框：QSS 一旦自定义 `::indicator`，Fusion 默认的勾会消失（暗色下更是渲染成黑方块）。
   必须自带选中态勾号图（`check-white.png`）+ 主题色底。
3. 必须**显式给 `QListWidgetItem.setSizeHint()`**，否则 `setItemWidget` 的首行可能只渲染出标题、
   丢失副标题行。
4. `QGroupBox::title` 的字号在 QSS 下不可靠 → 卡片标题改用独立 `QLabel#cardTitle`（`Card` 类）。
5. 打包时必须把 `ui/assets` 挂进两个 spec 的 `datas`，否则箭头/勾号全部丢失。

---

## 五、开发环境搭建

### 5.1 系统要求

- Windows 10/11 x64
- Python 3.12（推荐 3.12.13）
- NVIDIA 显卡驱动（GPU 加速需要，CUDA 12.6 兼容）
- 磁盘空间：开发环境约 15GB（含模型缓存）

### 5.2 创建虚拟环境

**GPU 开发环境**（日常开发使用）：
```bash
cd E:\PDF2WordTool
python -m venv .venv
.venv\Scripts\activate

# 安装依赖
pip install -e .
# 或手动安装：
pip install paddlepaddle-gpu==3.3.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu126/
pip install paddleocr paddlex pdf2docx pymupdf python-docx Pillow PySide6
```

**CPU 打包环境**（精简版打包使用）：
```bash
# 使用脚本自动创建
powershell -ExecutionPolicy Bypass -File scripts\setup_cpu_venv.ps1
```

**重要**：`paddlepaddle-gpu 3.3.0` 不在 PyPI 上，必须从 PaddlePaddle 官方源安装。PyPI 上只有 2.6.x 版本。

### 5.3 模型缓存

PaddleX 首次运行会自动下载模型到 `~/.paddlex/` 目录。本项目通过 NTFS junction 将模型缓存重定向到项目内的 `model_cache/` 目录：

```bash
# 如果模型已下载到其他位置，可以创建 junction
mklink /J E:\PDF2WordTool\model_cache C:\path\to\existing\paddlex_cache
```

模型列表：
- PP-DocLayoutV3（版面分析）
- PP-OCRv6_medium_det（文字检测）
- PP-OCRv6_medium_rec（文字识别）
- SLANet_plus（表格结构识别）

### 5.4 开发运行

```bash
# 命令行模式
python -m pdf2word tests/samples/sample_scan.pdf -o output.docx

# GUI 模式
python -m pdf2word --gui

# 或使用 run.bat
run.bat
```

---

## 六、打包与发布

### 6.1 GPU 完整版打包

使用 GPU 虚拟环境（`.venv`）打包，包含 CUDA 运行时库。

```bash
cd E:\PDF2WordTool
.venv\Scripts\python.exe -m PyInstaller pdf2word.spec --noconfirm
```

**关键配置**（pdf2word.spec）：
- 收集推理必需的 CUDA 库：cublas / cudnn / cusolver / cuda_runtime（裁剪 cufft / curand / cusparse，省约 600MB）
- 手动收集 `nvidia.nvjitlink`（namespace package，collect_all 无法处理）
- 裁剪不需要的 PySide6 模块（QML、PDF、Multimedia 等）
- 排除 torch、tensorflow、matplotlib、pandas、tkinter 减小体积
- 裁剪 paddle 的 include/ 和 distributed/ 目录

**产物体积**：约 3.1 GB（`dist/PDF转Word/`）

### 6.2 精简版打包

使用 CPU 虚拟环境（`.venv-cpu`）打包，不含 CUDA 运行时库。

```bash
cd E:\PDF2WordTool
.venv-cpu\Scripts\python.exe -m PyInstaller pdf2word-lite.spec --noconfirm --workpath build-lite
```

**关键配置**（pdf2word-lite.spec）：
- 不收集任何 nvidia CUDA 包
- 排除所有 nvidia.* 模块
- 其余裁剪策略与 GPU 版一致
- 输出目录为 `PDF转Word-Lite`，避免与 GPU 版冲突

**产物体积**：约 2.3 GB（`dist/PDF转Word-Lite/`）

### 6.3 Inno Setup 安装包

```bash
# 编译 GPU 完整版安装包
"C:\Users\13717\AppData\Local\Programs\Inno Setup 6\ISCC.exe" pdf2word.iss

# 编译精简版安装包
"C:\Users\13717\AppData\Local\Programs\Inno Setup 6\ISCC.exe" pdf2word-lite.iss
```

**注意事项**：
- LZMA2 ultra64 压缩，GPU 版编译耗时约 25 分钟，精简版约 17 分钟
- GPU 版安装包约 1020 MB，精简版约 291 MB
- 两个版本使用不同的 AppId，可以共存安装
- 精简版安装到 `PDF2WordToolLite` 目录，GPU 版安装到 `PDF2WordTool` 目录
- 输出到 `installer_out/` 目录

**ChineseSimplified.isl 语言文件**：Inno Setup 6.7 默认不包含简体中文语言文件，需从 GitHub 下载 `ChineseSimplified.isl` 放到 `Languages/` 目录。

### 6.4 静默安装测试

```bash
# GPU 版
installer_out\PDF转Word-Setup-1.2.exe /VERYSILENT /TASKS="" /DIR=E:\test_install

# 精简版
installer_out\PDF转Word-Lite-Setup-1.2.exe /VERYSILENT /TASKS="" /DIR=E:\test_lite

# 测试转换
E:\test_install\pdf2word-cli.exe tests\samples\sample_scan.pdf -o E:\test_install\test_output.docx

# 卸载
E:\test_install\unins000.exe /VERYSILENT
```

---

## 七、版本历史

### v1.0 — 初始版本（MVP）

**功能**：
- 文字页 pdf2docx 直转
- 扫描页整页 OCR + 段落重建
- 图片保留 + 图内文字标注
- tkinter GUI + CLI 双模式

**技术决策**：
- 选择 PaddleOCR 而非 Tesseract：中文识别准确率显著更高
- 选择整页 OCR 而非版面分析：MVP 阶段简化流程
- 使用 PyMuPDF 渲染：速度快，API 简洁

### v1.1 — 版面分析 + 表格识别

**新增功能**：
- PP-DocLayoutV3 版面分析：分区处理文字、表格、图片区域
- SLANet_plus 表格识别：重建 Word 原生表格
- 未覆盖区域兜底 OCR：防止版面模型漏检
- 阅读顺序排序：行聚类 + 行内从左到右

**技术改进**：
- 模型惰性加载（单例模式），避免启动时全量加载
- 块（block）统一格式，解耦识别与渲染
- paddlex 依赖元数据补丁（打包环境需要 imagesize 等 dist-info）

### v1.2 — GPU 加速 + 双版本发布

**新增功能**：
- 自动检测 NVIDIA GPU，CUDA 推理加速
- 无 GPU 时自动回退 CPU，零配置
- GUI 显示当前推理设备
- **GUI 从 tkinter 升级为 PySide6**（Qt 6），支持拖拽、样式更现代
- **双版本发布**：GPU 完整版 + 精简版（CPU 推理）
- **精简版 GPU 在线升级**：程序内「工具」菜单下载 GPU 支持，从国内 PyPI 镜像源下载
- GPU 支持管理：下载、检查状态、卸载

**性能提升**：
- 扫描页单页转换：~100s (CPU) → ~18-28s (GPU)，提速约 4-5x
- 裁剪不必要 CUDA 库（cufft/curand/cusparse），GPU 版体积减少约 600MB
- 裁剪不需要的 PySide6 模块和传递依赖（pandas/tkinter 等）

**技术实现**：
- `envsetup.py` 新增 GPU 检测（兼容 nvidia-smi 不在 PATH）、DLL 注册、惰性激活
- `gpu_installer.py` 新模块：从清华/阿里云镜像下载 CUDA 包，从 PaddlePaddle 官网下载 GPU 引擎
- `gui.py` 重写为 PySide6，新增工具菜单（GPU 支持下载/检查/卸载）
- `paddlepaddle` → `paddlepaddle-gpu 3.3.0`（CUDA 12.6）
- PyInstaller spec 收集推理必需的 nvidia CUDA 运行时包
- 精简版使用独立 CPU 虚拟环境（`.venv-cpu`）打包

**安装包变化**：
- GPU 完整版：约 1020 MB（含 CUDA 运行时）
- 精简版：约 291 MB（纯 CPU，可在线升级 GPU 支持）
- 两个版本使用不同 AppId，可共存安装

### v1.3 — 性能与体积再优化（同时修复扫描页崩溃）

**修复的两个致命打包缺陷**（详见 8.3 / 8.4 / 8.10，均为 v1.2 扫描页必崩的根因）：

1. `AttributeError: partially initialized module 'paddle' has no attribute 'tensor'`
   —— PyInstaller 把模块压进 PYZ 后命中 CPython 导入机制的「子模块缓存提前返回」分支，
   子模块没有绑定回父包。新增运行时钩子 `scripts/pyi_rth_paddle.py` 补齐绑定。
2. `OSError: [WinError 126] cusolver64_11.dll`
   —— `cusolver64_11.dll` 硬依赖 `cusparse64_12.dll`，v1.2 只收前者、排除了后者。
   改为只保留 `cublas / cudnn / cuda_runtime` 三个 CUDA 包。
3. `.venv-cpu` 混装 `paddlepaddle 3.3.1` 与残留 `paddlepaddle-gpu 2.6.2`，
   导致精简版报 `cannot import name 'forward_complete_op_role'`。已清理重装为纯 CPU 版 3.3.0。

**性能优化**：
- 文字页按需加载 OCR：新增 `imagetext.count_docx_images()`（纯 XML 扫描，不加载引擎），
  文档无内嵌图片时完全不导入 paddle。无图样本实测 **14 s → 3 s（约 4.7×）**。
- `envsetup.patch_paddlex_deps()` 改为 paddlex 导入成功后再打补丁，
  消除 "PDX has already been initialized" 二次初始化崩溃。

**体积优化**：
- CUDA 运行时只保留推理必需的 cublas / cudnn / cuda_runtime，
  移除 cusolver(213 MB) / cusparse(275 MB) / nvjitlink(84 MB) / cufft / curand。
- 修复 spec 裁剪规则的历史 bug：`_should_strip()` 会把路径分隔符统一成 `/`，
  而规则里写的是 `"paddle" + os.sep + "include"`（Windows 下是 `\`），
  **v1.2 的裁剪规则从来没生效过**。改为正斜杠后，`paddle/include`、
  `opencv_videoio_ffmpeg`、`tzdata` 才真正被裁掉。
- 恢复被误排除的 `pandas` 与 `huggingface_hub`（paddlex 顶层 import，排除会导致导入中途失败）。

**体积对比**：

| | v1.2 | v1.3 | 变化 |
|---|---|---|---|
| GPU 版（打包目录） | 3189 MB | 2812 MB | −377 MB |
| 精简版（打包目录） | 2337 MB | 762 MB | −1575 MB |
| GPU 版安装包 | 1020 MB | 908 MB | −112 MB（−11%） |
| 精简版安装包 | 291 MB | 166 MB | −125 MB（−43%） |

> 精简版体积降幅特别大，主因不是 spec 改动，而是修好了 `.venv-cpu`：
> 混装环境下 `libpaddle.pyd` 达 1708 MB，清理后为 126 MB。

**实测（本机 RTX 3060 Laptop 6GB，打包产物）**：
- GPU 版：扫描页 27.2 s（冷启动，含模型加载）/ 文字页 6.7 s / 混合页 11.7 s
- 精简版（CPU）：扫描页 56.1 s / 文字页 12.2 s

### v1.4 — 三大新功能 + 启动/体积策略调整

**新增功能**：
- **PDF 合并**：多文件合并，顺序可调，支持逐文件页面范围（`1-5,8`），书签按文件名汇总。实测 7 页 0.11 s。
- **PDF 转图片**：PNG/JPG/WebP/BMP/TIFF × 多张独立 / 单张长图（20000 px 自动分卷）。实测 150 dpi 下 PNG 68 ms/页、JPG 103 ms/页。
- **Office 转 PDF**：docx/xlsx/pptx 双引擎——本机 Office/WPS 走 COM（1~3 s/文件、零体积），否则走内置 LibreOffice。
- **更名「PDF 工具箱」**：主界面保持单页，新功能进「工具」菜单；新 AppId（`...0003` / `...0004`），安装目录 `PDFToolbox` / `PDFToolboxLite`。
- CLI 新增 `merge` / `image` / `office` 子命令，旧参数用法完全兼容。

**性能优化**：
- **启动 −0.4 s**：`ensure_env(fast=True)` 跳过 `nvidia-smi` 探测（实测 494 ms，占原热启动 1.05 s 的 35%），改为窗口显示后的后台线程；设备真值仍由 `activate_gpu_device()` 用 paddle 二次确认。
- 引擎检测从 `CLSIDFromProgID`（20 s）改为注册表查 `HKCR\<ProgID>\CLSID`（0.002 s）。
- Office 进程快照从 `tasklist /V`（22 s）改为 Toolhelp32 + EnumWindows（0.035 s）。
  > 这两项让 Office 转 PDF 的单文件耗时从 46.95 s 降到 5.44 s。

**新增依赖**：无。`minicom.py` 用标准库 ctypes 实现 COM，避免 pywin32（+20~30 MB）。

**界面现代化改造**：
- 新增 `ui/theme.py`（QSS 主题）+ `ui/assets/` 三个箭头图标，浅灰底 + 白色圆角卡片 + 主色 #2f6bff。
- 顶部改为品牌栏（图标 / 标题 / 副标题 / 三个功能按钮 / 「⋯」），**移除 menuBar**，GPU 功能收进「⋯」。
- 弹窗统一为「待处理文件 / 选项 / 日志」三卡片结构。
- 实测成本：`apply_theme` 6 ms；有/无主题的启动差异 < 20 ms；打包版 GUI 出窗 **0.95~1.17 s**。

**版本策略调整**（双包）：
| 包 | 体积 | Office 转 PDF | 说明 |
|----|------|--------------|------|
| 精简版 | ≈170 MB | 需本机 Office/WPS | 不含 LibreOffice |
| 全功能版 | ≈400~560 MB | 内置 LibreOffice | 未装 Office 也能用 |

> LibreOffice 实测：官方 MSI 358 MB，解包 19,427 个文件 / 1.58 GB。裁剪目标 1.0~1.2 GB，
> 逐项裁剪需回归三种格式（见 PLAN-v1.4.md §3.2）。

### v1.5 — 界面重构（信息层级 / 视觉 / 交互 / 细节）

**布局与层级**
- 顶部改为 **Tab 标签栏**平铺 4 个功能页（原来藏在「工具」菜单里），一步直达。
- 每页统一 5 个模块：品牌区 → 文件卡片 → 参数卡片 → 操作行 → 日志卡片；
  卡片用浅色底 + 1px 边框 + 轻投影做物理隔离，替代细线分割。
- 参数区统一为 **两列网格**（`form_grid()`），控件等高、等圆角、基线对齐。
- 编辑区去掉了 `QMainWindow.menuBar()`，次级功能（深色模式 / GPU / 关于）收进「⋯」。

**视觉**
- 建立字号层级：卡片标题 14px/600 · 表单标签 13px · 辅助说明 12px/浅灰。
- 主按钮 44px 高 + 垂直渐变 + 按下位移；禁用态、处理中态（`◐◓◑◒` 帧动画 + 可点击停止）齐备。
- 次级操作降级为 `objectName="link"` 文字按钮，不与主按钮抢注意力。

**交互**
- 文件列表：**空状态**（虚线框 + 图标 + 引导文案）、**拖拽悬停**高亮、
  **行内 hover 删除**、**右键菜单**（打开文件 / 所在目录 / 移除）、
  行内显示「N 页 · 体积」（页数由后台线程读）。
- 进度：进度条 10px 品牌色渐变 + 文案「进度 35% · 第 1/2 个文件 · 文件名」。
- 状态栏：任务状态（带帧动画）+ 推理设备胶囊（GPU 加速已启用 / CPU 运行）。
- 结果反馈：右上角 Toast（成功/失败），失败自动展开日志。

**细节**
- 日志默认折叠成一行摘要，点「详细日志 ▾」展开；文案改为用户能懂的表述。
- 新增**深色模式**（跟随系统 `AppsUseLightTheme`，也可在「⋯」里手动切换）。
- 修掉 v1.4 的 `find_soffice()` 误判：不再把 `experiments/` 下无法启动的半成品认作"已就绪"。

**性能取舍**
- Tab **懒加载**：只建当前页，首次切换时创建。实测 4 页预建会让首屏构造多花约 0.9 s；
  懒加载后单页 17~23 ms、切页 43~76 ms，`MainWindow` 预热后构造 53 ms。
- 首屏剩下的 1.2~1.3 s 是 Qt 首次初始化窗口系统的固定成本（无 QSS 也要 1.29 s），与业务代码无关。

**打包与体积（v1.5 实测，Inno Setup 6）**：
- 精简版 `PDFToolbox-Lite-Setup-1.4.exe` = **167 MB**（源码 726 MB，压缩率 23%）。
- 三档对比：`lzma2/normal` 214 MB/109 s，`lzma2/max` 210 MB/145 s，
  `lzma2/ultra64` **167 MB/214 s**（采用，多花不到 2 分钟换 28% 体积）。
- `PrivilegesRequired=lowest`：免管理员安装，静默安装 3475 文件 / 731 MB，
  安装后热启动 0.53 s、CLI 正常、卸载干净。

---

## 八、已知问题与解决方案

### 8.1 paddlepaddle-gpu 安装源

**问题**：PyPI 上 paddlepaddle-gpu 只有 2.6.x，没有 3.x。

**解决**：从 PaddlePaddle 官方源安装：
```bash
pip install paddlepaddle-gpu==3.3.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu126/
```

### 8.2 PaddleOCR use_gpu 参数

**问题**：PaddleOCR 3.7+ 不再接受 `use_gpu` 参数，传入会抛 `ValueError: Unknown argument: use_gpu`。

**解决**：移除 `use_gpu` 参数，PaddleOCR 自动继承 `paddle.set_device()` 的全局设备设置。

### 8.3 打包后 paddle 报 `has no attribute 'tensor'`（v1.3 已修复）

**问题**：打包产物运行扫描页时崩溃：
```
AttributeError: partially initialized module 'paddle' has no attribute 'tensor'
                (most likely due to a circular import)
```

**原因**：与 PATH 无关，是 CPython 导入机制的「子模块缓存提前返回」分支。
`paddle/__init__.py` 第 62 行 → `monkey_patch_variable()` 的 else 分支执行
`import paddle.tensor`，而 `importlib._bootstrap._find_and_load_unlocked()` 中有：

```python
if parent:
    if parent not in sys.modules:
        _call_with_frames_removed(import_, parent)
    if name in sys.modules:
        return sys.modules[name]      # ← 提前返回，不执行下面的 setattr
...
setattr(parent_module, child, module)  # ← 绑定父包属性
```

源码目录下 `paddle.tensor` 通常是首次导入，会正常绑定；但 PyInstaller 把所有模块
压进 PYZ 后子模块加载顺序改变，`paddle.tensor` 可能已在 `sys.modules` 中，
于是命中提前返回，父包上没有 `tensor` 属性。

**解决**：新增运行时钩子 `scripts/pyi_rth_paddle.py`，在每次 `import paddle.*`
之后检查父包是否已有该属性，缺失则用 `setattr` 补齐。两个 spec 均已挂载：
```python
runtime_hooks=[os.path.join(SPECPATH, "scripts", "pyi_rth_paddle.py")]
```
（设环境变量 `PDF2WORD_DEBUG=1` 可让补绑动作打印到 stderr，便于排查。）

### 8.4 打包后加载 CUDA DLL 报 WinError 126（v1.3 已修复）

**问题**：打包产物运行报
```
OSError: [WinError 126] 找不到指定的模块。
Error loading "...\_internal\nvidia\cusolver\bin\cusolver64_11.dll" or one of its dependencies.
```

**原因**：v1.2 为省体积收集了 `nvidia.cusolver`，却排除了 `nvidia.cusparse`。
但 `cusolver64_11.dll` 的导入表里**硬依赖** `cusparse64_12.dll`（275 MB）：

| DLL | 硬依赖 |
|-----|--------|
| `cusolver64_11.dll` | cublas64_12、cublasLt64_12、**cusparse64_12** |
| `cusparse64_12.dll` | **nvJitLink_120_0** |
| `cusolverMg64_11.dll` | 仅 cublas64_12（无人依赖它，可安全裁剪） |

`paddle/__init__.py` 会 glob 加载 `nvidia/*/bin/*.dll`，于是加载 cusolver 时必然失败。
该错误位于 paddle 初始化末尾，长期被 8.3 的 `tensor` 报错掩盖，所以一直没暴露。

**解决**：不再打包 cusolver / cusparse / nvjitlink，只保留推理真正必需的三个包：
`nvidia.cublas`（矩阵运算）、`nvidia.cudnn`（卷积）、`nvidia.cuda_runtime`。
已实测：仅这三个包，GPU 版版面分析 + OCR 完全正常（扫描页 11~27 s/页）。

> 附带结论：`nvidia.nvjitlink` 不需要再手动收集（它是 namespace package，
> `collect_all()` 无法处理），因为它只被 cusparse 依赖，而 cusparse 已整体移除。

### 8.5 PyInstaller pathex 相对路径问题

**问题**：`pathex=["src"]` 在打包时解析为 CWD/src 而非 spec 文件所在目录/src。

**解决**：使用 SPECPATH 变量：
```python
pathex=[os.path.join(SPECPATH, "src")]
```

### 8.6 CPU 版 paddle 卸载破坏 GPU 版

**问题**：`pip uninstall paddlepaddle` 会删除与 paddlepaddle-gpu 共享的文件。

**解决**：如需重装 GPU 版：
```bash
pip install --force-reinstall paddlepaddle-gpu==3.3.0 --no-deps
```

### 8.7 Inno Setup 编译时间

**问题**：LZMA2 ultra64 压缩大量数据耗时较长（GPU 版约 25 分钟，精简版约 17 分钟）。

**说明**：这是正常的，不要中断。可以在任务管理器观察 ISCC.exe 的 CPU 使用率确认未卡死。

### 8.8 Inno Setup 缺少中文语言文件

**问题**：Inno Setup 6.7 默认安装不包含 `ChineseSimplified.isl`。

**解决**：从 GitHub 下载 `ChineseSimplified.isl` 放到 Inno Setup 安装目录的 `Languages/` 文件夹下。

### 8.9 精简版 GPU 升级后需重启

**问题**：精简版下载 GPU 支持后，当前运行实例仍使用 CPU。

**原因**：paddle DLL 在程序启动时已加载，运行中替换 DLL 不会生效。

**解决**：安装完成后提示用户重启程序。卸载 GPU 支持同理。

### 8.10 CPU 虚拟环境混装两个 paddle 版本

**问题**：精简版打包产物运行报
```
ImportError: cannot import name 'forward_complete_op_role'
             from 'paddle.distributed.passes.pass_utils'
```

**原因**：`.venv-cpu` 里同时安装了 `paddlepaddle 3.3.1` 与残留的
`paddlepaddle-gpu 2.6.2`。两个版本的 wheel 文件叠加在同一个 `paddle/` 目录里，
后装的会覆盖同名文件，于是出现「`pipeline_1f1b.py` 来自 3.3.1、
`pass_utils.py` 来自 2.6.2」这种错配。
判断方法：看 `paddle/distributed/passes/` 下文件的修改时间是否分成两批。

**排查命令**：
```bash
.venv-cpu/Scripts/python.exe -m pip list | grep -i paddle
# 正常应只有 paddlepaddle（CPU 版），不应出现 paddlepaddle-gpu
```

**解决**：卸载干净后重装 CPU 版 paddle，再重新打包：
```bash
.venv-cpu/Scripts/python.exe -m pip uninstall -y paddlepaddle-gpu paddlepaddle
.venv-cpu/Scripts/python.exe -m pip install paddlepaddle==3.3.0 \
    -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
```
> 注意：paddle 有数千个文件，Windows 上卸载较慢（约 10 分钟），不要中断。

---

### 8.11 CPU 版无法用 oneDNN 加速（2026-09-19 实验定案）

**现象**：paddlepaddle 3.3.0（CPU）下，任何方式开启 oneDNN（`enable_mkldnn=True` 或
`FLAGS_use_mkldnn=1`），OCR 检测或版面模型在 `predictor.run()` 抛
`NotImplementedError: ConvertPirAttribute2RuntimeAttribute not support
[pir::ArrayAttribute<pir::DoubleAttribute>]`；设 `FLAGS_enable_pir_in_executor=0`
回退旧执行器也无效（paddlex 自管 predictor 配置）。

**定案**：三处源码强制 `enable_mkldnn=False` 并加注释。完整数据与复现脚本见
`experiments/onednn/README.md`；paddle 升级到 ≥3.4 后可复测。

**How to apply**：任何"CPU 提速"提案不要再往 oneDNN 方向走，优先做
`limit_side_len`、rec 模型档位、多页并行。

### 8.12 COM：oleaut32 不能用 ctypes.oledll（v1.4）

**现象**：调 Word 导出时报 `0x80020005` 或 `access violation reading 0x000000006A45DB34`。

**原因**：`ctypes.oledll.oleaut32` 把返回值按 `c_long`(HRESULT) 解析，x64 上会把
`SysAllocString` 返回的 BSTR 指针截断成野指针。给 oledll 的实例设置
`restype = c_void_p` **也无效**（仍是 c_long 解析）。

**解决**：
```python
oleaut32 = ctypes.WinDLL("oleaut32")
oleaut32.SysAllocString.restype = c_void_p
oleaut32.SysAllocString.argtypes = [c_wchar_p]
```

### 8.13 COM：GetIDsOfNames 参数顺序（v1.4）

**现象**：`0x800706F4`（RPC_X_NULL_REF_POINTER）。

**原因**：把参数写成了 `(riid, cNames, lcid, names, dispid)`。正确顺序是
`(riid, rgszNames, cNames, lcid, rgDispId)`，且 `cNames` 必须为 1。

### 8.14 Office 自动化：相对路径与输出目录（v1.4）

- **PowerPoint / Word 都只认绝对路径**：相对路径会按 Office 自身工作目录解析，
  PowerPoint 直接报"找不到 xxx.pdf"。所有输入输出统一 `os.path.abspath()`。
- **输出目录不存在时只报"命令失败 (0x80020009)"**：`SaveAs2` / `ExportAsFixedFormat`
  不会自建目录。`convert_many()` 入口处统一 `os.makedirs(out_dir, exist_ok=True)`。

### 8.15 两个 Windows API 的性能陷阱（v1.4）

| 用法 | 实测耗时 | 替代方案 | 替代后 |
|------|---------|---------|--------|
| `CLSIDFromProgID` 查 3 个 ProgID（未初始化线程） | **20 s** | 注册表 `HKCR\<ProgID>\CLSID` | 0.002 s |
| `tasklist /V /FO CSV`（437 进程） | **22 s** | Toolhelp32 + EnumWindows | 0.035 s |

这两项曾让 Office 转 PDF 单文件耗时 46.95 s，修复后 5.44 s。

### 8.16 Office 进程残留（v1.4）**现象**：`Application.Quit()` 后 WINWORD.EXE / EXCEL.EXE 仍常驻（每次 160~230 MB）。

**解决**：任务开始前用 Toolhelp32 记录 PID 快照，结束后只结束「新增 且 无可见带标题窗口」
的 Office 进程（有窗口的多为用户正在编辑的文档，一律不动）。
**严禁** `taskkill /IM WINWORD.EXE` —— 实测曾差点误杀用户正在写的开题报告。

### 8.17 E 盘路径导致 MSI 装不上（v1.5）

**现象**：`msiexec /i E:\...\LibreOffice.msi /qn` 返回 83，提权后仍失败，
Windows Installer 弹「无法打开此安装程序包」；日志只有 `MainEngineThread is returning 2`
和 `Note: 1: 1402 ...\Installer\Rollback\Scripts`。文件本身完好（OLE 头 `D0CF11E0` 正常，
`7z` 能完整解出 19427 个文件）。

**解决**：把 MSI 复制到 `%TEMP%`（C 盘）再装，**一次成功**。
→ 结论：**提权上下文无法访问 E 盘**，凡需 UAC 提升的操作，源文件先放系统盘。

### 8.18 非系统盘的 profile 会让 LibreOffice 崩溃（v1.5）

**现象**：`-env:UserInstallation=file:///E:/.../lo_profile` 时 soffice 以
`0xC0000409`（STACK_BUFFER_OVERRUN）退出，无任何日志；同一份程序换成
`file:///C:/Users/.../lo_profile` 则正常转换（首次 7.8 s，热 3.5 s）。

**解决**：`_lo_profile_dir()` 强制把 profile 放在系统盘；若 `LOCALAPPDATA` 不在系统盘，
回退到 `%TEMP%`。**LibreOffice 本体放哪个盘都行**（实测 E 盘内置副本 + C 盘 profile 正常）。

### 8.19 从 MSI 还原绿色版的三个数据陷阱（v1.5，未能跑通）

按 MSI 表还原目录时依次踩到，均已写进 `experiments/office_com/restore_msi_layout.py`：
1. `FileName` 与 `DefaultDir` 都是「**短名|长名**」，长名在 `|` **之后**。
2. 字体文件 MSI 里用 `-`、CAB 内实际用 `_`（`NotoSansHebrew-Bold.ttf`）。
3. 运行库是**多架构**：CAB 内为 `msvcp140.dll_amd64.<GUID>`，且 `System64` 组件的文件
   要放进 `program/` 才能被加载。
4. CAB 内文件名**不带 `lib` 前缀**（`mergedlo.dll` 而非 `libmergedlo.dll`，26.x 的命名）。
5. `program/bootstrap.ini` 里 `InstallMode=<installmode>` 是 MSI 安装时才替换的**占位符**，
   绿色版需手改成 `Portable`。

> 最终仍卡在转换 `rc=81`（初始化正常、依赖齐全），**结论：不要走 MSI 还原这条路，直接装官方包**。

## 九、测试

### 9.1 测试样本

`tests/samples/` 目录下提供三个测试 PDF：
- `sample_text.pdf`：纯文字页
- `sample_scan.pdf`：纯扫描页
- `sample_mixed.pdf`：混合页面

### 9.2 测试流程

```bash
# 1. 虚拟环境测试
.venv\Scripts\activate
python -m pdf2word tests/samples/sample_scan.pdf -o test_output.docx

# 2. GPU 版打包测试
.venv\Scripts\python.exe -m PyInstaller pdf2word.spec --noconfirm
dist\PDF转Word\pdf2word-cli.exe tests/samples/sample_scan.pdf -o test_output.docx

# 3. 精简版打包测试
.venv-cpu\Scripts\python.exe -m PyInstaller pdf2word-lite.spec --noconfirm --workpath build-lite
dist\PDF转Word-Lite\pdf2word-cli.exe tests/samples/sample_scan.pdf -o test_output.docx

# 4. 安装包测试
ISCC.exe pdf2word.iss
installer_out\PDF转Word-Setup-1.2.exe /VERYSILENT /DIR=E:\test
E:\test\pdf2word-cli.exe tests/samples/sample_scan.pdf -o test_output.docx
E:\test\unins000.exe /VERYSILENT
```

### 9.3 GPU 验证

启动 GUI 后查看日志输出的设备信息：
```
推理设备: GPU (CUDA)
```
或
```
推理设备: CPU
```

也可以通过转换一个扫描页 PDF 并观察耗时来判断：GPU 约 18-28s，CPU 约 100s。

精简版可通过「工具 → 检查 GPU 状态」查看 GPU 支持包安装情况。

---

## 十、部署注意事项

### 10.1 目标机器要求

- Windows 10/11 x64
- 磁盘空间：GPU 版安装后约 3GB，精简版安装后约 2.3GB
- GPU 加速需要 NVIDIA 显卡 + 最新驱动（CUDA 12.6 兼容）
- 无 GPU 时自动使用 CPU，无需额外配置

### 10.2 双版本说明

| 版本 | 安装包 | 安装目录 | GPU 支持 | 适用场景 |
|------|--------|---------|---------|---------|
| GPU 完整版 | ~1020 MB | PDF2WordTool | 内置 CUDA | 有 NVIDIA 显卡 |
| 精简版 | ~291 MB | PDF2WordToolLite | 安装后在线下载 | 无显卡或不确定 |

- 两个版本使用不同 AppId，可以共存安装
- 精简版安装后可通过「工具 → 下载 GPU 加速支持」在线升级（约 1.5 GB）
- GPU 支持下载源：清华/阿里云 PyPI 镜像 + PaddlePaddle 官网 CDN

### 10.3 模型文件

安装包已包含所有模型文件（在 `_internal/models/` 目录），无需联网下载。

### 10.4 首次启动

首次启动会初始化模型，可能需要 15-20 秒。后续启动速度相同（模型在每次使用时加载）。

---

## 十一、后续开发建议

### 11.1 可能的改进方向

1. **批量转换**：支持整个文件夹的 PDF 批量转换
2. **进度细化**：显示每页的转换进度百分比
3. **OCR 语言选择**：支持英文、日文等其他语言
4. **排版保真度提升**：浮动文本框还原图内文字位置（需手写 OOXML）
5. **多页合并优化**：跨页段落合并（当前每页独立）
6. **深色模式**：GUI 支持深色主题
7. **自动更新**：检查新版本并提示下载

**CPU 版提速（v1.3 后仍未做，性价比排序）**
（⚠️ oneDNN 已实验证伪，勿再尝试，见 §8.11）

1. OCR 检测限制 `limit_side_len`：200 DPI 渲染常超出必要分辨率，检测耗时大头在此
2. rec 模型提供 mobile 档位开关：精度换速度的用户可选模式
3. 页级并行：`ProcessPoolExecutor` 按页分发，文字页（pdf2docx）与扫描页（重建）互不依赖
4. GPU 版单模型实例下做页间 pipeline：识别与 docx 写盘重叠

**体积再优化**：精简版提供"轻量模型包"可选下载（PP-OCRv6 mobile 档），安装包可再减约一半。

### 11.2 代码组织建议

- 新增功能模块放在 `src/pdf2word/` 目录下
- 新增模块需在 `pdf2word.spec` 和 `pdf2word-lite.spec` 的 `hiddenimports` 中注册
- 模型加载遵循惰性单例模式（参考 layout.py、table.py）
- GPU 相关代码调用 `activate_gpu_device()` 而非直接 `paddle.set_device()`
- **一次性实验**（验证假设的脚本/日志/产物）放 `experiments/<主题>/` 并附 README 说明结论与复现命令，
  不要把中间产物堆在 `tests/` 或项目根目录（v1.3 后已清理过一次，见 `experiments/README.md`）

### 11.3 重新打包流程

```bash
# 1. GPU 完整版
cd E:\PDF2WordTool
.venv\Scripts\python.exe -m PyInstaller pdf2word.spec --noconfirm
"C:\Users\13717\AppData\Local\Programs\Inno Setup 6\ISCC.exe" pdf2word.iss

# 2. 精简版
.venv-cpu\Scripts\python.exe -m PyInstaller pdf2word-lite.spec --noconfirm --workpath build-lite
"C:\Users\13717\AppData\Local\Programs\Inno Setup 6\ISCC.exe" pdf2word-lite.iss

# 3. 验证
dist\PDF转Word\pdf2word-cli.exe tests/samples/sample_scan.pdf -o test.docx
dist\PDF转Word-Lite\pdf2word-cli.exe tests/samples/sample_scan.pdf -o test_lite.docx
```

---

## 十二、关键依赖版本锁定

| 包名 | 版本 | 来源 | 说明 |
|------|------|------|------|
| paddlepaddle-gpu | 3.3.0 | PaddlePaddle 官方源 | CUDA 12.6 |
| paddleocr | 3.7+ | PyPI | PP-OCRv6 |
| paddlex | latest | PyPI | 模型管理 |
| pdf2docx | latest | PyPI | 文字页转换 |
| PyMuPDF | latest | PyPI | PDF 解析与渲染 |
| python-docx | latest | PyPI | Word 文档生成 |
| Pillow | latest | PyPI | 图像处理 |
| PySide6 | latest | PyPI | Qt 6 GUI 框架 |
| PyInstaller | 6.22+ | PyPI | 打包工具 |

---

## 十三、联系方式与资源

- PaddleOCR 文档：https://paddleocr.ai
- PaddleX 文档：https://paddlex.readthedocs.io
- pdf2docx 源码：https://github.com/dothinking/pdf2docx
- PyMuPDF 文档：https://pymupdf.readthedocs.io
- PySide6 文档：https://doc.qt.io/qtforpython/
- Inno Setup 文档：https://jrsoftware.org/ishelp/
- PyInstaller 文档：https://pyinstaller.org

---

*本文档由项目开发过程整理而成，如有疑问请参考源码注释或联系项目维护者。*
