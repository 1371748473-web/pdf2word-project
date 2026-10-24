# PDF 工具箱

一个离线运行的 Windows 桌面工具：把 PDF 转成可编辑的 Word 文档，顺带解决合并、转图片和 Office 转 PDF 三件常见的事。文字页直接保真转换，扫描页自动走 OCR 识别重建，全程不联网、不上传文件。

![版本](https://img.shields.io/badge/版本-1.5-blue) ![平台](https://img.shields.io/badge/平台-Windows%2010%2F11%20x64-blue) ![Python](https://img.shields.io/badge/Python-3.10%2B-green)

## 功能

**PDF → Word**　文字页保留字体、字号、段落与表格结构直接转换；扫描页自动识别并重建文档结构，图内文字也会被提取出来。文档分类（文字页 / 扫描页）是自动的，不用手动选。

**PDF 合并**　拖进来就能合，支持调整页面顺序、逐文件设置页码范围（如 `1-5,8`），并自动汇总源文件书签。

**PDF → 图片**　PNG / JPG / WebP / BMP / TIFF 五种格式；可以选择每页一张，也可以合成一张长图（超高自动分卷，默认 20000 px 上限）。

**Office → PDF**　Word / Excel / PowerPoint 转 PDF，配了三套引擎自动调度：

| 优先级 | 引擎 | 说明 |
|---|---|---|
| 1 | 本机 Office / WPS | 检测到就直接用它的导出功能，保真度最高 |
| 2 | 内置 docx 引擎 | 基于 [dxpdf](https://github.com/nerdy-pro/dxpdf)（Rust + Skia）的纯本地排版引擎，Word 文档不需要装任何办公软件 |
| 3 | LibreOffice | 无 Office/WPS 时兜底；全功能版内置，精简版提供国内镜像下载引导 |

## 实测性能

| 指标 | 数据 |
|---|---|
| 程序启动 | 0.52 ~ 0.57 s（含 3.6 GB 的 GPU 版） |
| 4 页扫描件 → Word | GPU **30.4 s** ／ CPU 315.9 s |
| 合并 7 页 PDF | 0.11 s |
| 转图片 | PNG 68 ms/页、JPG 103 ms/页（150 dpi） |
| Office → PDF | 本机 Office 1.07 s、docx 引擎 1.5~1.9 s、LibreOffice 3.5 s |

> 测试环境：RTX 3060 / R7 5800H / 40 GB 内存 / Windows 11。

## 下载安装

提供三个安装包，按需选择：

| 安装包 | 体积 | 适合 |
|---|---|---|
| `PDFToolbox-Lite-Setup` | 175 MB | 没有独显，或只要基础功能（Word 转换不受影响） |
| `PDFToolbox-Setup` | 360 MB | 没有独显，但需要离线转换 Excel/PPT |
| `PDFToolbox-GPU-Setup` | 1.1 GB | 有 NVIDIA 独显，扫描件识别快 10 倍 |

全部内置 LibreOffice 的安装包均为一次性完整安装，卸载干净不留残余。三个版本启动速度相同——CUDA 和 LibreOffice 只在真正需要时才加载。

CPU 版安装后也可以在「⋯ → 下载 GPU 加速支持」在线补齐 CUDA（约 1.5 GB）。

## 使用

主界面四个标签页，功能一目了然：

1. 把文件拖进虚线框（或点击「添加文件」）
2. 按需调参数（都有默认值，通常直接下一步）
3. 点「开始转换」——耗时超过 1 秒的任务会自动弹出进度窗，带计时和取消按钮
4. 完成后右上角弹提示，生成文件与源文件同目录（也可以自定义输出位置）

转换失败时会弹出报告，列出每个文件的具体原因，支持**只重试失败的文件**，已经成功的不重复处理。

也提供命令行：

```bash
pdf2word input.pdf                     # 转成 docx
pdf2word a.pdf b.pdf --merge -o out.pdf
pdf2word input.pdf --to-image -f png
pdf2word report.docx --engine dxpdf    # 强制指定 Office 转换引擎
```

## 从源码构建

### 环境要求

- Windows 10/11 x64
- Python 3.10+
- Git（可选，拉代码用）
- Inno Setup 6（打安装包用，[官网](https://jrsoftware.org/isdl.php) 或 winget）

### 构建 CPU 精简版

```bash
git clone https://github.com/1371748473-web/pdf2word-project.git
cd pdf2word-project

python -m venv .venv-cpu
.venv-cpu\Scripts\pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

# 打包可执行目录
.venv-cpu\Scripts\python -m PyInstaller pdf2word-lite.spec --noconfirm
```

### 构建 GPU 全功能版

```bash
python -m venv .venv
.venv\Scripts\pip install paddlepaddle-gpu -i https://pypi.tuna.tsinghua.edu.cn/simple
.venv\Scripts\pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

.venv\Scripts\python -m PyInstaller pdf2word.spec --noconfirm
```

GPU 版的 CUDA 运行库（cuDNN / cuBLAS）随 PyInstaller 自动收集，无需手动处理。

### 打成安装包

```bash
# ISCC.exe 通常在 %LOCALAPPDATA%\Programs\Inno Setup 6\ 下
ISCC.exe pdf2word-lite.iss    # 产出精简版安装包
ISCC.exe pdf2word.iss         # 产出完整版安装包
```

注意：两个 iss 的 `Source` 均为相对路径 `dist\...`，脚本必须放在仓库根目录执行；
输出文件名由 `OutputBaseFilename` 控制，改版本号只需改 `MyAppVersion` 一处。

## 技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 界面 | PySide6 (Qt 6) | 自绘 QSS 主题（亮/暗双套）、卡片式布局，不依赖 Qt Designer |
| PDF 解析 | PyMuPDF (MuPDF) | 页面渲染、文本层读取、合并、拆图 |
| 直转 | pdf2docx | 文字页 PDF → docx 的保真转换 |
| OCR | PaddleOCR 3.x + PP-DocLayoutV3 | 扫描件文字识别 + 版面分析，GPU 由 `paddlepaddle-gpu` 驱动 |
| 表格重建 | 自研启发式算法 | `table.py`，从 OCR 结果重建表格行列 |
| Office 转 PDF | minicom（自研）+ dxpdf + LibreOffice | minicom 是 **ctypes 手写的 COM 封装**（约 180 行，不依赖 pywin32），直接驱动 Word/Excel/PPT 的 IDispatch 接口 |
| 打包 | PyInstaller + Inno Setup 6 | onedir 模式 + LZMA2/ultra64 压缩安装包 |

### 几个值得一提的实现细节

- **文档自动分类**：逐页统计文本层字符密度，判定「文字页 / 扫描页」，两种页面可以在同一份 PDF 里混用不同通道。
- **COM 进程残留清理**：任务前用 `Toolhelp32` 记录系统进程快照，任务后只结束「新增且无可见窗口」的 Office 进程——绝不会误杀用户正开着的 Word 文档。
- **LibreOffice profile 隔离**：用 `-env:UserInstallation` 把配置指到系统盘独立目录，避免和用户已装的 LibreOffice 互相污染（也绕开了非系统盘路径导致崩溃的问题）。
- **引擎探测不卡启动**：用 `importlib.util.find_spec` 判断 dxpdf 是否存在（不真正 import，省掉加载 Skia 的 100 ms）；Office 探测走注册表查询而非 `CLSIDFromProgID`（20 s → 20 ms）。

## 项目结构

```
├── src/pdf2word/          # 主包
│   ├── core.py            # 转换流水线调度
│   ├── classify.py        # 文字页/扫描页自动分类
│   ├── layout.py          # 版面分析（PP-DocLayout）
│   ├── table.py           # OCR 表格重建
│   ├── rebuild.py         # docx 重建
│   ├── merge.py           # PDF 合并
│   ├── pdf2img.py         # PDF 转图片（含长图分卷）
│   ├── office2pdf.py      # Office → PDF 三引擎调度
│   ├── minicom.py         # ctypes 手写 COM 封装
│   ├── gpu_installer.py   # GPU 加速在线下载
│   ├── cli.py / gui.py    # 命令行 / 图形入口
│   └── ui/                # 界面层（页面、弹窗、主题、控件）
├── tests/                 # 样本文件
├── pdf2word.spec          # PyInstaller（GPU 全功能版）
├── pdf2word-lite.spec     # PyInstaller（CPU 精简版）
└── *.iss                  # Inno Setup 安装包脚本
```

## 常见问题

**转出来的 Word 和原 PDF 不完全一样？**　文字页走结构重建（段落/表格/图片位置还原），不是像素级复制；复杂艺术字、特殊图形会被省略。扫描页受 OCR 精度影响，公式和手写体效果有限。

**没有独显能用吗？**　能。CPU 版所有功能都可用，只是扫描件 OCR 慢（约 80 秒/页）。文字页直转不受影响。

**会偷偷联网吗？**　不会。转换全程本地执行。唯一联网的场景是你主动点「下载 GPU 加速支持」或「下载 LibreOffice」。

## 许可证

本项目尚未指定开源许可证，当前保留所有权利。
