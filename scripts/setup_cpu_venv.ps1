# setup_cpu_venv.ps1
# 创建用于精简版打包的 CPU 虚拟环境
#
# 用法: powershell -ExecutionPolicy Bypass -File scripts\setup_cpu_venv.ps1
#
# 此脚本会：
#   1. 在 .venv-cpu 目录创建独立的 CPU 虚拟环境
#   2. 安装 paddlepaddle（CPU 版）及所有其他依赖
#   3. 安装打包工具 PyInstaller
#
# 注意：paddlepaddle（CPU）与 paddlepaddle-gpu 不能共存于同一 venv，
#       因此需要独立的 .venv-cpu 环境用于精简版打包。

$ErrorActionPreference = "Stop"
$ROOT = Split-Path $PSScriptRoot -Parent
$VENV = Join-Path $ROOT ".venv-cpu"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  PDF 转 Word 工具 — CPU 虚拟环境创建脚本" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 检查是否已存在
if (Test-Path $VENV) {
    Write-Host "[提示] $VENV 已存在。" -ForegroundColor Yellow
    $overwrite = Read-Host "是否删除并重新创建？(y/N)"
    if ($overwrite.ToLower() -eq "y") {
        Remove-Item $VENV -Recurse -Force
        Write-Host "已删除旧环境。"
    } else {
        Write-Host "已跳过。如需使用现有环境，请手动激活："
        Write-Host "  .venv-cpu\Scripts\activate"
        exit 0
    }
}

# 创建虚拟环境
Write-Host "正在创建 CPU 虚拟环境..." -ForegroundColor Cyan
& python -m venv $VENV
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] 创建虚拟环境失败" -ForegroundColor Red
    exit 1
}

$python = Join-Path $VENV "Scripts\python.exe"
$pip = Join-Path $VENV "Scripts\pip.exe"

# 升级 pip
Write-Host ""
Write-Host "正在升级 pip..." -ForegroundColor Cyan
& $python -m pip install --upgrade pip

# 安装 paddlepaddle（CPU 版）
Write-Host ""
Write-Host "正在安装 paddlepaddle（CPU 版）..." -ForegroundColor Cyan
& $pip install paddlepaddle==3.0.0
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] paddlepaddle 安装失败" -ForegroundColor Red
    Write-Host "  请检查网络连接，或尝试: pip install paddlepaddle"
    exit 1
}

# 安装其他依赖
Write-Host ""
Write-Host "正在安装其他依赖..." -ForegroundColor Cyan
& $pip install paddleocr paddlex pdf2docx pymupdf python-docx pillow pyside6 pefile
if ($LASTEXITCODE -ne 0) {
    Write-Host "[警告] 部分依赖安装失败，请检查错误信息" -ForegroundColor Yellow
}

# 安装 PyInstaller
Write-Host ""
Write-Host "正在安装 PyInstaller..." -ForegroundColor Cyan
& $pip install pyinstaller
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] PyInstaller 安装失败" -ForegroundColor Red
    exit 1
}

# 安装项目本身（editable 模式）
Write-Host ""
Write-Host "正在安装项目（editable 模式）..." -ForegroundColor Cyan
& $pip install -e $ROOT
if ($LASTEXITCODE -ne 0) {
    Write-Host "[警告] 项目安装失败，请手动执行: pip install -e ." -ForegroundColor Yellow
}

# 验证
Write-Host ""
Write-Host "正在验证安装..." -ForegroundColor Cyan
& $python -c "import paddle; print(f'paddle {paddle.__version__}, CUDA: {paddle.device.is_compiled_with_cuda()}')"
& $python -c "import paddleocr; print('paddleocr OK')"
& $python -c "import PySide6; print('PySide6 OK')"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  CPU 虚拟环境创建完成！" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "下一步操作："
Write-Host "  1. 激活 CPU 环境："
Write-Host "     .venv-cpu\Scripts\activate"
Write-Host ""
Write-Host "  2. 打包精简版："
Write-Host "     pyinstaller pdf2word-lite.spec --noconfirm"
Write-Host ""
Write-Host "  3. 生成 GPU 支持包（需在 GPU 环境 .venv 下）："
Write-Host "     .venv\Scripts\python.exe scripts\make_gpu_pack.py"
Write-Host ""
Write-Host "  4. 编译精简版安装程序："
Write-Host "     ISCC.exe pdf2word-lite.iss"
Write-Host ""
Write-Host "体积预估："
Write-Host "  精简版安装包: ~1.0 GB（CPU 推理）"
Write-Host "  GPU 支持包:   ~1.4 GB（安装时按需下载）"
Write-Host "  GPU 完整版:   ~3.4 GB（一次性打包所有）"
