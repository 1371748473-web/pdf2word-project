# PDF2WordTool v1.2 项目总结 · 验证报告

验证时间：2026-08-14 ｜ 验证范围：项目总结（pdf2word-project-summary.html）中所有可静态核查的声明
范围说明：**不验证「无 GPU 的干净机器实机验证」**（项目总结第七节待办第 1 项，用户已明确要求跳过）；GPU 性能计时（4-5×、18-28s/页）同样需 GPU 硬件，标记为「未验证」。

图例：✅ 通过 ｜ ⚠️ 部分/推测 ｜ ❌ 不符

---

## 一、技术栈与版本号

| 组件 | 总结声明 | 实测（venv / spec） | 结论 |
|---|---|---|---|
| Python | 3.12 | 3.12.13（.venv 与 .venv-cpu） | ✅ |
| PySide6 (Qt 6) | PySide6 | 6.11.1 | ✅ |
| PaddleOCR | 3.7 / PP-OCRv6 | paddleocr 3.7.0 | ✅ |
| PaddleX PP-DocLayoutV3 | PP-DocLayoutV3 | paddlex 3.7.2；layout.py 调用 `create_model("PP-DocLayoutV3")` | ✅ |
| SLANet_plus | SLANet_plus | table.py 调用 `create_model("SLANet_plus")` | ✅ |
| paddlepaddle-gpu | 3.3.0 (CUDA 12.6) | paddlepaddle-gpu 3.3.0；gpu_installer 固定 cu126 版本 | ✅ |
| PyMuPDF | PyMuPDF | 1.28.2 | ✅ |
| pdf2docx | pdf2docx | 0.5.13 | ✅ |
| PyInstaller | 6.22 | 6.22.0 | ✅ |
| Inno Setup | 6.7 | 安装包已编译产出（含简体中文语言包）；本机 ISCC 二进制未在搜索路径中找到，**6.7 版本号未独立确认** | ⚠️ |

---

## 二、核心功能（代码层面）

| 功能 | 关键证据 | 结论 |
|---|---|---|
| 文字页保排版直转（pdf2docx） | core.py `use_direct` 分支 → `Converter(pdf_path).convert()` | ✅ |
| 扫描页 OCR 重建（版面→OCR→段落） | rebuild.scan_page_blocks → layout + OCR + group_lines | ✅ |
| 表格结构还原（SLANet_plus + OCR 回填） | table.reconstruct_table，输出 Word 原生表格 | ✅ |
| 图内文字提取（灰色斜体标注） | imagetext.enrich_direct_docx / rebuild 中 `style="gray"` 灰色斜体段落 | ✅ |
| GPU 自动加速 + 无 GPU 回退 CPU | envsetup._detect_gpu 设 `PDF2WORD_DEVICE`；activate_gpu_device 用 `paddle.device.is_compiled_with_cuda()` 二次确认 | ✅ |
| GPU 支持在线管理（工具菜单 下载/检查/卸载） | gui.py `menu_tools` 含「下载 GPU 加速支持…」「检查 GPU 状态」「卸载 GPU 支持…」 | ✅ |

---

## 三、本轮修复项（14 条逐项核对）

| # | 声明 | 代码/产物证据 | 结论 |
|---|---|---|---|
| 1 | 修复 GPU 检测（nvidia-smi 不在 PATH 误判） | envsetup._find_nvidia_smi 遍历 System32/NVSMI 路径；activate_gpu_device 二次确认 | ✅ |
| 2 | 修复安装路径 editable 与 CUDNN 版本匹配 | envsetup._relocate_models（非 ASCII 路径搬运）；_register_nvidia_dll_dirs（注册 CUDA DLL）；gpu_installer.KNOWN_VERSIONS 锁定 cu126 版本 | ✅ |
| 3 | 批量 OCR 推理，减少 GPU 调用开销 | rebuild.ocr_lines_arr_batch（一次性 predict 多图，失败回退逐张） | ✅ |
| 4 | 低 DPI 版面分析，加速区域检测 | rebuild.scan_page_blocks `layout_dpi = min(dpi, 150)` 后缩放回原 DPI | ✅ |
| 5 | 裁剪 CUDA/Qt/传递依赖，体积减少约 688 MB | gpu spec 仅收 cublas/cuda_runtime/cudnn/cusolver，排除 cufft/curand/cusparse；剥离 Qt6* 非必需模块 + pandas/tkinter | ✅（见注 A） |
| 6 | 新增 gpu_installer.py 在线下载模块（国内镜像） | gpu_installer.py：清华/阿里云 PyPI + PaddlePaddle 官网 CDN，断点重试、取消、CPU DLL 备份回滚 | ✅ |
| 7 | GUI 新增工具菜单：下载/检查/卸载 GPU 支持 | gui.py 三项 QAction 已接入 | ✅ |
| 8 | 创建 CPU 打包虚拟环境 .venv-cpu | .venv-cpu 存在，Python 3.12.13，paddlepaddle 3.3.1（CPU） | ✅ |
| 9 | GPU 完整版清理旧产物后重新打包 | dist/PDF转Word 时间戳 08-14 15:19（本轮） | ✅ |
| 10 | 精简版打包（独立 spec 与输出目录） | pdf2word-lite.spec + dist/PDF转Word-Lite（排除全部 nvidia 包） | ✅ |
| 11 | 安装并配置 Inno Setup 6.7（含简体中文语言包） | 两 .iss 均引用 ChineseSimplified.isl；安装包已产出 | ⚠️（版本号见上） |
| 12 | 编译双版本安装包并验证产物完整性 | 见第五节体积核对 | ✅ |
| 13 | 更新 PROJECT_DOC.md 技术文档 | 文件存在，08-14 16:14，含 v1.2 / PP-DocLayoutV3 / SLANet / nvidia-smi / gpu_installer 等章节 | ✅ |
| 14 | 更新 使用说明.txt 用户文档 | 文件存在，08-14 16:14 | ✅ |

---

## 四、打包产物完整性

| 产物 | 总结声明 | 实测 | 结论 |
|---|---|---|---|
| PDF转Word-Setup-1.2.exe | GPU 完整版 · 1020.3 MB | 1020.3 MB（1,069,847,175 B） | ✅ |
| PDF转Word-Lite-Setup-1.2.exe | 精简版 · 290.6 MB | 290.6 MB（304,768,597 B） | ✅ |
| dist/PDF转Word | 3.12 GB（中间产物） | 3189 MB ≈ 3.12 GB | ✅ |
| dist/PDF转Word-Lite | 2.35 GB（中间产物） | 2419 MB ≈ 2.35 GB | ✅ |
| 双版本可共存 | 不同 AppId + 安装目录 | GPU `...0001`→`PDF2WordTool`；Lite `...0002`→`PDF2WordToolLite` | ✅ |
| 产物命名 | PDF转Word-Setup-1.2 / PDF转Word-Lite-Setup-1.2 | .iss `OutputBaseFilename` 一致 | ✅ |

> 注：总结表格单元格内写的 3121.6 / 2351.2 MB 与目录实际 3189 / 2419 MB 相差约 2%（四舍五入口径），属正常误差，结论为通过。

---

## 五、代码健康度

- 全部源码模块 `py_compile` 通过：**无语法错误**（src/pdf2word/*.py、scripts/*.py、app_entry.py）。
- CODE 实际结构（core/layout/table/imagetext/rebuild/classify/envsetup/gui/cli/gpu_installer）与 PROJECT_DOC.md 描述的模块职责一致。

---

## 六、未验证 / 需留意项

| 项 | 原因 |
|---|---|
| GPU 性能（4-5× 提速、18-28s/页） | 需 NVIDIA 实机计时，用户已排除无 GPU 机器验证，此项同属硬件相关，未跑 |
| 精简版「在线升级 GPU」端到端实机流程 | 属总结第七节待办第 1 项，需干净无 GPU 机器联网实跑；代码逻辑已具备（gpu_installer + 工具菜单），但未端到端验证 |
| 体积减少「约 688 MB」精确值 | 为构建期测量值；spec 注释标注 CUDA 裁剪约 600MB，量级一致，本次未重新对比未优化基线 |
| Inno Setup 精确版本 6.7 | 安装包已成功编译、产物完整，但本机 ISCC 二进制未在搜索路径，版本号未独立确认 |

**轻微异常（不阻断）：**
- ⚠️ `.venv-cpu` 中除 `paddlepaddle==3.3.1` 外，还残留 `paddlepaddle-gpu==2.6.2`。精简版 spec 已 `excludes` 全部 nvidia 包且不收集 paddlepaddle-gpu，因此**不会进入 Lite 产物**，但建议清理该 venv 以免混淆。

---

## 七、结论

项目总结中**除 GPU 性能计时与无 GPU 干净机器实机验证外**，其余所有可静态核查的声明（技术栈版本、六大核心功能代码、本轮 14 项修复、打包产物体积与命名、双版本共存设计、文档更新、代码可编译性）**均与仓库实际状态一致，验证通过**。

后续待办（批量文件夹转换、进度百分比、OCR 多语言、跨页段落合并、深色模式/自动更新）在总结中本就列为未完成项，与代码现状相符，无需修正。
