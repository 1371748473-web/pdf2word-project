#!/usr/bin/env python3
"""命令行版 GPU 加速支持下载器。

功能同 GUI 中的「工具 → 下载 GPU 加速支持」，
从 PyPI 国内镜像源和 PaddlePaddle 官网下载 GPU 运行时库。

用法：
  python download_gpu_support.py           # 下载并安装
  python download_gpu_support.py --check   # 仅检查状态
  python download_gpu_support.py --uninstall  # 卸载 GPU 支持
"""
import sys


def main():
    # 添加 src 到路径（开发环境）
    import os
    src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
    if os.path.isdir(src):
        sys.path.insert(0, src)

    from pdf2word.gpu_installer import (
        GpuInstaller,
        check_nvidia_gpu,
        is_gpu_support_installed,
    )

    if "--check" in sys.argv:
        gpu = check_nvidia_gpu()
        installed = is_gpu_support_installed()
        print(f"NVIDIA 显卡: {gpu or '未检测到'}")
        print(f"GPU 支持包: {'已安装' if installed else '未安装'}")
        return 0

    if "--uninstall" in sys.argv:
        installer = GpuInstaller(progress=lambda msg, pct=0: print(msg))
        installer.uninstall()
        return 0

    # 检查是否已安装
    if is_gpu_support_installed():
        print("GPU 支持已安装，如需重装请先执行: python download_gpu_support.py --uninstall")
        return 0

    # 安装
    def progress(msg, pct=0):
        if pct:
            print(f"\r{msg}", end="", flush=True)
        else:
            print(msg)

    installer = GpuInstaller(progress=progress)
    ok = installer.install()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
