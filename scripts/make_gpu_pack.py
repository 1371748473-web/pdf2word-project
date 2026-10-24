#!/usr/bin/env python3
"""从 GPU 版构建产物中提取 GPU 支持文件，打包为 gpu_support.zip。

用法（在项目根目录，GPU venv 下执行）：
  python scripts/make_gpu_pack.py

输出：
  installer_out/gpu_support.zip  （约 1.4–1.5 GB）

该 zip 包含：
  1. nvidia/          — CUDA 运行时 DLL（cublas, cudnn, cuda_runtime, cusolver, nvjitlink）
  2. paddle/libs/     — GPU 版 paddle DLL（phi.dll 等，替换 CPU 版）

精简版安装后，用户可通过 download_gpu_support.py 下载此 zip 并解压到安装目录，
即可启用 GPU 加速，无需重新安装整个程序。
"""
import os
import sys
import zipfile
import shutil

# 项目根目录
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist", "PDF转Word", "_internal")
OUTPUT = os.path.join(ROOT, "installer_out", "gpu_support.zip")


def collect_nvidia_dlls():
    """收集 nvidia/*/bin/*.dll 文件。"""
    nvidia_dir = os.path.join(DIST, "nvidia")
    if not os.path.isdir(nvidia_dir):
        print("[警告] dist/PDF转Word/_internal/nvidia 目录不存在")
        print("       请先完成 GPU 版打包：pyinstaller pdf2word.spec --noconfirm")
        return []
    files = []
    for sub in sorted(os.listdir(nvidia_dir)):
        bin_dir = os.path.join(nvidia_dir, sub, "bin")
        if not os.path.isdir(bin_dir):
            continue
        for f in os.listdir(bin_dir):
            if f.lower().endswith(".dll"):
                src = os.path.join(bin_dir, f)
                dst = os.path.join("nvidia", sub, "bin", f)
                files.append((src, dst))
    return files


def collect_gpu_paddle_dlls():
    """收集 paddle/libs/ 下的 GPU 版 DLL（phi.dll 等）。

    这些 DLL 与 CPU 版不同：GPU 版的 phi.dll 链接了 CUDA，
    解压时会覆盖精简版的 CPU phi.dll。
    """
    paddle_libs = os.path.join(DIST, "paddle", "libs")
    if not os.path.isdir(paddle_libs):
        print("[警告] dist/PDF转Word/_internal/paddle/libs 目录不存在")
        return []
    files = []
    for f in os.listdir(paddle_libs):
        if f.lower().endswith(".dll"):
            src = os.path.join(paddle_libs, f)
            dst = os.path.join("paddle", "libs", f)
            files.append((src, dst))
    return files


def main():
    if not os.path.isdir(DIST):
        print(f"[错误] 找不到 GPU 版构建产物：{DIST}")
        print("       请先执行：pyinstaller pdf2word.spec --noconfirm")
        sys.exit(1)

    nvidia_files = collect_nvidia_dlls()
    paddle_files = collect_gpu_paddle_dlls()

    if not nvidia_files:
        print("[错误] 未找到 nvidia CUDA DLL，请确认 GPU 版打包已完成")
        sys.exit(1)

    total_files = nvidia_files + paddle_files
    total_size = sum(os.path.getsize(s) for s, _ in total_files)
    print(f"收集到 {len(total_files)} 个文件，总计 {total_size / 1e9:.2f} GB")
    print(f"  - nvidia CUDA DLL: {len(nvidia_files)} 个")
    print(f"  - paddle GPU DLL:  {len(paddle_files)} 个")

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)

    print(f"\n正在压缩到 {OUTPUT} ...")
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for src, dst in total_files:
            zf.write(src, dst)
            print(f"  + {dst}", end="\r")

    zip_size = os.path.getsize(OUTPUT)
    print(f"\n\n完成！gpu_support.zip = {zip_size / 1e9:.2f} GB")
    print(f"路径: {OUTPUT}")
    print(f"\n下一步：将此文件上传到云存储或 GitHub Releases，")
    print(f"然后在 download_gpu_support.py 中设置下载 URL。")


if __name__ == "__main__":
    main()
