"""GPU 加速支持下载与安装模块。

从 PyPI 国内镜像源（清华/阿里云）和 PaddlePaddle 官网下载 GPU 运行时库，
安装到程序目录后即可启用 GPU 加速，无需重新安装整个程序。

特点：
  - 使用国内镜像源，下载速度快、成功率高
  - 支持断点重试（每个文件最多重试 3 次）
  - 支持取消操作
  - 进度回调，方便 GUI 集成
  - 自动备份 CPU 版 paddle DLL，可回滚
"""

import os
import sys
import json
import shutil
import zipfile
import tempfile
import urllib.request
import urllib.error
import re
import subprocess

# ── 镜像源（按优先级排序，国内源优先）──────────────────────
PYPI_MIRRORS = [
    ("清华源", "https://pypi.tuna.tsinghua.edu.cn"),
    ("阿里云", "https://mirrors.aliyun.com/pypi"),
    ("官方源", "https://pypi.org"),
]

# PaddlePaddle GPU 包官方下载地址（国内 CDN）
PADDLE_MIRROR = "https://www.paddlepaddle.org.cn/packages/stable/cu126"

# 需要下载的 nvidia CUDA 包（包名 → 安装子目录名）
NVIDIA_PACKAGES = [
    ("nvidia-cublas-cu12", "cublas"),
    ("nvidia-cuda-runtime-cu12", "cuda_runtime"),
    ("nvidia-cudnn-cu12", "cudnn"),
    ("nvidia-cusolver-cu12", "cusolver"),
    ("nvidia-nvjitlink-cu12", "nvjitlink"),
]

# 固定版本（与开发环境一致，确保兼容性）
KNOWN_VERSIONS = {
    "nvidia-cublas-cu12": "12.6.4.1",
    "nvidia-cuda-runtime-cu12": "12.6.77",
    "nvidia-cudnn-cu12": "9.5.1.17",
    "nvidia-cusolver-cu12": "11.7.1.2",
    "nvidia-nvjitlink-cu12": "12.9.86",
    "paddlepaddle-gpu": "3.3.0",
}


def get_install_dir():
    """获取程序安装目录（打包环境为 _internal/，开发环境为 src 上级）。"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
        internal = os.path.join(base, "_internal")
        if os.path.isdir(internal):
            return internal
        return base
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check_nvidia_gpu():
    """检查系统是否有 NVIDIA GPU，返回 GPU 名称或 None。"""
    for smi in [shutil.which("nvidia-smi"),
                r"C:\Windows\System32\nvidia-smi.exe"]:
        if smi and os.path.isfile(smi):
            try:
                r = subprocess.run(
                    [smi, "--query-gpu=name", "--format=csv,noheader"],
                    capture_output=True, text=True, timeout=5
                )
                if r.returncode == 0 and r.stdout.strip():
                    return r.stdout.strip().splitlines()[0]
            except Exception:
                pass
    return None


def is_gpu_support_installed(install_dir=None):
    """检查 GPU 支持是否已安装（nvidia 目录存在且包含关键 DLL）。"""
    install_dir = install_dir or get_install_dir()
    nvidia_dir = os.path.join(install_dir, "nvidia")
    if not os.path.isdir(nvidia_dir):
        return False
    # 检查关键 DLL 是否存在
    checks = [
        ("cudnn", "cudnn64_9.dll"),
        ("cublas", "cublas64_12.dll"),
        ("cuda_runtime", "cudart64_12.dll"),
    ]
    return all(
        os.path.isfile(os.path.join(nvidia_dir, sub, "bin", dll))
        for sub, dll in checks
    )


class GpuInstaller:
    """GPU 加速支持下载安装器。

    用法:
        installer = GpuInstaller(progress_callback)
        success = installer.install()
        if success:
            print("安装成功，请重启程序")

    progress_callback 签名: callback(message: str, percent: int = 0)
    """

    def __init__(self, install_dir=None, progress=None):
        self.install_dir = install_dir or get_install_dir()
        self.progress = progress or (lambda msg, pct=0: None)
        self.temp_dir = tempfile.mkdtemp(prefix="gpu_install_")
        self._cancelled = False

    def cancel(self):
        """取消下载安装（可在 GUI 中调用）。"""
        self._cancelled = True

    # ── 内部方法 ──────────────────────────────────────────

    def _download(self, url, dest, retries=3):
        """下载文件，支持重试。"""
        for attempt in range(retries):
            if self._cancelled:
                return False
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "PDF2WordTool/1.2"}
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    total = int(resp.headers.get("Content-Length", 0))
                    downloaded = 0
                    chunk = 1024 * 1024  # 1 MB
                    with open(dest, "wb") as f:
                        while True:
                            if self._cancelled:
                                return False
                            data = resp.read(chunk)
                            if not data:
                                break
                            f.write(data)
                            downloaded += len(data)
                            if total > 0:
                                pct = downloaded * 100 // total
                                mb_d = downloaded / 1e6
                                mb_t = total / 1e6
                                self.progress(
                                    f"  下载中: {mb_d:.0f}/{mb_t:.0f} MB", pct
                                )
                return True
            except Exception as e:
                if attempt < retries - 1:
                    self.progress(
                        f"  下载失败（第{attempt + 1}次），{5}秒后重试... ({e})"
                    )
                    import time
                    time.sleep(5)
                    continue
                raise
        return False

    def _find_nvidia_wheel(self, package, version, mirror_base):
        """从 PyPI 镜像源查找 Windows x64 wheel 下载地址。"""
        api_url = f"{mirror_base}/pypi/{package}/json"
        try:
            req = urllib.request.Request(
                api_url, headers={"User-Agent": "PDF2WordTool/1.2"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())

            releases = data.get("releases", {})

            # 优先查找指定版本
            for ver in [version, data.get("info", {}).get("version", "")]:
                if not ver:
                    continue
                for f in releases.get(ver, []):
                    fn = f.get("filename", "")
                    # 只下载 Windows x64 wheel
                    if "win_amd64" in fn and fn.endswith(".whl"):
                        return f["url"], fn
        except Exception as e:
            self.progress(f"  查询 {package} 失败: {e}")
        return None, None

    def _find_paddle_gpu_wheel(self, version):
        """从 PaddlePaddle 官网查找 GPU wheel 下载地址。"""
        url = f"{PADDLE_MIRROR}/paddlepaddle-gpu/"
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "PDF2WordTool/1.2"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                html = resp.read().decode("utf-8")

            # 查找所有 win_amd64 wheel 链接
            pattern = r'href="([^"]*paddlepaddle_gpu[^"]*win_amd64\.whl)"'
            matches = re.findall(pattern, html)

            py_tag = f"cp{sys.version_info.major}{sys.version_info.minor}"

            # 优先匹配版本号 + Python 版本
            for m in matches:
                basename = os.path.basename(m)
                if version in basename and py_tag in basename:
                    return m if m.startswith("http") else (
                        f"{PADDLE_MIRROR}/paddlepaddle-gpu/{basename}"
                    )

            # 回退：匹配 Python 版本
            for m in matches:
                basename = os.path.basename(m)
                if py_tag in basename:
                    return m if m.startswith("http") else (
                        f"{PADDLE_MIRROR}/paddlepaddle-gpu/{basename}"
                    )

            # 最后回退：第一个 win_amd64
            if matches:
                m = matches[0]
                basename = os.path.basename(m)
                return m if m.startswith("http") else (
                    f"{PADDLE_MIRROR}/paddlepaddle-gpu/{basename}"
                )
        except Exception as e:
            self.progress(f"  查询 paddlepaddle-gpu 失败: {e}")
        return None

    def _extract_nvidia_wheel(self, wheel_path):
        """从 nvidia wheel 中提取 DLL 到安装目录。"""
        with zipfile.ZipFile(wheel_path, "r") as zf:
            for member in zf.namelist():
                if member.startswith("nvidia/") and member.endswith(".dll"):
                    zf.extract(member, self.install_dir)

    def _extract_paddle_wheel(self, wheel_path):
        """从 paddlepaddle-gpu wheel 中提取 DLL，替换 CPU 版（自动备份）。"""
        paddle_libs = os.path.join(self.install_dir, "paddle", "libs")
        with zipfile.ZipFile(wheel_path, "r") as zf:
            for member in zf.namelist():
                if "paddle/libs/" in member and member.endswith(".dll"):
                    filename = os.path.basename(member)
                    dst = os.path.join(paddle_libs, filename)
                    backup = dst + ".cpu"
                    # 备份 CPU 版（仅首次）
                    if os.path.isfile(dst) and not os.path.isfile(backup):
                        try:
                            os.rename(dst, backup)
                        except Exception:
                            pass
                    # 提取 GPU 版
                    zf.extract(member, self.install_dir)
                    self.progress(f"  替换: {filename}")

    # ── 公开方法 ──────────────────────────────────────────

    def install(self):
        """执行完整的 GPU 支持安装流程。返回 True 表示成功。"""
        try:
            # 1. 检查 GPU
            self.progress("正在检查系统 GPU...")
            gpu = check_nvidia_gpu()
            if gpu:
                self.progress(f"[OK] 检测到 NVIDIA GPU: {gpu}")
            else:
                self.progress("[警告] 未检测到 NVIDIA GPU")
                self.progress("  仍可安装，但程序将使用 CPU 模式")

            # 2. 检查是否已安装
            if is_gpu_support_installed(self.install_dir):
                self.progress("[提示] GPU 支持已安装，无需重复安装")
                return True

            total = len(NVIDIA_PACKAGES) + 1  # +1 for paddlepaddle-gpu
            step = 0

            # 3. 下载并安装 nvidia CUDA 包
            for pkg, subdir in NVIDIA_PACKAGES:
                if self._cancelled:
                    self.progress("已取消安装")
                    return False

                step += 1
                version = KNOWN_VERSIONS.get(pkg, "")
                self.progress(f"\n({step}/{total}) 下载 {pkg}=={version}")

                wheel_url = None
                wheel_name = None
                for mirror_name, mirror_base in PYPI_MIRRORS:
                    self.progress(f"  尝试{mirror_name}...")
                    wheel_url, wheel_name = self._find_nvidia_wheel(
                        pkg, version, mirror_base
                    )
                    if wheel_url:
                        self.progress(f"  找到: {wheel_name}")
                        break

                if not wheel_url:
                    self.progress(f"[错误] 无法找到 {pkg} 的下载地址")
                    self.progress("  请检查网络连接，或手动运行：")
                    self.progress(f"  pip install {pkg}=={version}")
                    return False

                wheel_path = os.path.join(self.temp_dir, wheel_name)
                if not self._download(wheel_url, wheel_path):
                    if self._cancelled:
                        self.progress("已取消")
                        return False
                    self.progress(f"[错误] 下载 {pkg} 失败")
                    return False

                self.progress(f"  解压安装 {pkg}...")
                self._extract_nvidia_wheel(wheel_path)
                self.progress(f"  [OK] {pkg} 安装完成")

                # 清理 wheel 文件释放磁盘空间
                try:
                    os.unlink(wheel_path)
                except Exception:
                    pass

            # 4. 下载并安装 paddlepaddle-gpu
            if self._cancelled:
                self.progress("已取消安装")
                return False

            step += 1
            paddle_ver = KNOWN_VERSIONS.get("paddlepaddle-gpu", "")
            self.progress(f"\n({step}/{total}) 下载 paddlepaddle-gpu=={paddle_ver}")
            self.progress("  从 PaddlePaddle 官网下载（国内 CDN）...")

            paddle_url = self._find_paddle_gpu_wheel(paddle_ver)
            if not paddle_url:
                self.progress("[错误] 无法找到 paddlepaddle-gpu 下载地址")
                self.progress("  请手动安装：")
                self.progress(
                    f"  pip install paddlepaddle-gpu=={paddle_ver}"
                    f" -f {PADDLE_MIRROR}/"
                )
                return False

            paddle_name = os.path.basename(paddle_url)
            self.progress(f"  找到: {paddle_name}")

            wheel_path = os.path.join(self.temp_dir, paddle_name)
            if not self._download(paddle_url, wheel_path):
                if self._cancelled:
                    self.progress("已取消")
                    return False
                self.progress("[错误] 下载 paddlepaddle-gpu 失败")
                return False

            self.progress("  替换 paddle DLL（CPU 版 → GPU 版）...")
            self._extract_paddle_wheel(wheel_path)
            self.progress("  [OK] paddlepaddle-gpu 安装完成")

            try:
                os.unlink(wheel_path)
            except Exception:
                pass

            # 5. 验证安装
            self.progress("\n正在验证安装...")
            if is_gpu_support_installed(self.install_dir):
                self.progress("")
                self.progress("=" * 50)
                self.progress("  GPU 加速支持安装成功！")
                self.progress("  请重新启动程序以启用 GPU 加速。")
                self.progress("=" * 50)
                return True
            else:
                self.progress("[警告] 部分文件可能缺失，请检查上方日志")
                return False

        except Exception as e:
            self.progress(f"\n[错误] 安装失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            try:
                shutil.rmtree(self.temp_dir)
            except Exception:
                pass

    def uninstall(self):
        """卸载 GPU 支持，恢复 CPU 版 paddle DLL。"""
        # 删除 nvidia 目录
        nvidia_dir = os.path.join(self.install_dir, "nvidia")
        if os.path.isdir(nvidia_dir):
            shutil.rmtree(nvidia_dir, ignore_errors=True)
            self.progress("已删除 nvidia CUDA 库")

        # 恢复 CPU 版 paddle DLL
        paddle_libs = os.path.join(self.install_dir, "paddle", "libs")
        if os.path.isdir(paddle_libs):
            for f in os.listdir(paddle_libs):
                if f.endswith(".cpu"):
                    gpu_dll = f[:-4]  # 去掉 .cpu 后缀
                    gpu_path = os.path.join(paddle_libs, gpu_dll)
                    cpu_path = os.path.join(paddle_libs, f)
                    try:
                        if os.path.isfile(gpu_path):
                            os.unlink(gpu_path)
                        os.rename(cpu_path, gpu_path)
                        self.progress(f"  恢复: {gpu_dll}")
                    except Exception as e:
                        self.progress(f"  恢复失败: {gpu_dll} ({e})")

        self.progress("GPU 支持已卸载，请重启程序。")
