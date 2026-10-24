"""运行环境初始化：模型目录定位与 paddlex 依赖自检补丁。

GUI 与 CLI 入口在执行任何转换前都必须先调用 ensure_env()。

v1.4 起区分「快启动」与「设备探测」：
  - ensure_env(fast=True)  只做零成本初始化（环境变量、模型目录），不调用 nvidia-smi
  - ensure_device()        幂等地执行 GPU 探测（约 0.37 s），改为后台线程或首次转换前触发
原因：nvidia-smi 探测占原热启动 1.05 s 中的 0.37 s（35%），而设备真值最终由
activate_gpu_device() 用 paddle 二次确认，启动期探测只影响界面上的设备标签。
"""

import os
import shutil
import sys
import threading


def patch_paddlex_deps():
    """打包环境下跳过 paddlex 基于包元数据的依赖自检。

    paddlex 的 require_extra/is_dep_available 通过 importlib.metadata 逐个核对
    ocr extra 的依赖（einops/tokenizers/scikit-learn 等）是否安装。PyInstaller
    打包后部分 dist-info 元数据不完整，导致 OCR pipeline 创建时抛 DependencyError。
    打包产物已包含全部实际运行代码与模型，直接让这些检查通过即可。
    """
    # 关键：绝不能在 paddlex 尚未导入时调用本函数。
    # `from paddlex.utils import deps` 会触发 paddlex/__init__ 执行 _initialize()；
    # 打包环境中该导入可能在中途失败（模块对象被 Python 丢弃），但 repo_manager
    # 已完成初始化，于是后续再次 import paddlex 时会抛
    # "PDX has already been initialized. Reinitialization is not supported."
    # （v1.2 打包产物扫描页必崩的根因）。因此必须等 paddlex 被正常导入后再打补丁。
    if "paddlex" not in sys.modules:
        return False
    try:
        from paddlex.utils import deps

        deps.is_extra_available = lambda extra: True
        deps.require_extra = lambda extra, *, obj_name=None, alt=None: None
        deps.require_deps = lambda *deps_, **kwargs: None
        deps.is_dep_available = lambda dep, *a, **k: True
        return True
    except Exception:
        if os.environ.get("PDF2WORD_DEBUG"):
            import traceback

            traceback.print_exc()
        return False  # 未安装 paddlex 或版本结构不同时无需处理


def _is_ascii_path(p):
    try:
        p.encode("ascii")
        return True
    except (UnicodeEncodeError, UnicodeDecodeError):
        return False


def _relocate_models(bundled):
    """程序目录含非 ASCII 字符时，把自带模型复制到纯 ASCII 目录并返回。

    Paddle 的 C++ 推理库在 Windows 上用窄字符打开模型文件，路径含中文
    （如程序目录名「PDF转Word」）时读取为空，create_predictor 报
    "attempting to parse an empty input"。
    """
    candidates = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(os.path.join(local, "PDF2WordTool", "models"))
    programdata = os.environ.get("PROGRAMDATA") or r"C:\ProgramData"
    candidates.append(os.path.join(programdata, "PDF2WordTool", "models"))

    src = os.path.join(bundled, "official_models")
    # 以内置模型目录清单作为标记内容，清单变化（新增模型）时强制重新复制
    try:
        manifest = "\n".join(sorted(os.listdir(src))) if os.path.isdir(src) else ""
    except Exception:
        manifest = ""
    for cand in candidates:
        if not _is_ascii_path(cand):
            continue
        dst = os.path.join(cand, "official_models")
        marker = os.path.join(cand, ".copy_complete")
        stale = True
        if os.path.isfile(marker):
            try:
                with open(marker, "r", encoding="utf-8") as f:
                    stale = f.read() != manifest
            except Exception:
                stale = True
        if os.path.isdir(src) and stale:
            if os.path.isdir(dst):
                try:
                    shutil.rmtree(dst)  # 清理旧版/未完成的复制
                except Exception:
                    continue
            try:
                shutil.copytree(src, dst)
                with open(marker, "w", encoding="utf-8") as f:
                    f.write(manifest)
            except Exception:
                continue
        if os.path.isdir(os.path.join(cand, "official_models")):
            return cand
    return bundled  # 全部失败则退回原目录（可能仍会报错，但便于定位）


def _find_nvidia_smi():
    """查找 nvidia-smi 可执行文件，兼容不在 PATH 中的情况。"""
    smi = shutil.which("nvidia-smi")
    if smi:
        return smi
    for p in (
        r"C:\Windows\System32\nvidia-smi.exe",
        r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
        r"C:\Program Files\NVIDIA Corporation\nvidia-smi\nvidia-smi.exe",
    ):
        if os.path.isfile(p):
            return p
    return None


def _detect_gpu():
    """检测 NVIDIA GPU 可用性，设置环境变量。不在启动时导入 paddle 以避免打包环境循环导入。"""
    smi = _find_nvidia_smi()
    if not smi:
        # nvidia-smi 不可用不代表没有 GPU，留待 activate_gpu_device() 用 paddle 二次确认
        os.environ["PDF2WORD_DEVICE"] = "cpu"
        return "cpu"
    import subprocess

    try:
        r = subprocess.run(
            [smi, "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode != 0 or not r.stdout.strip():
            os.environ["PDF2WORD_DEVICE"] = "cpu"
            return "cpu"
    except Exception:
        os.environ["PDF2WORD_DEVICE"] = "cpu"
        return "cpu"

    os.environ["PDF2WORD_DEVICE"] = "gpu"
    return "gpu"


_device_lock = threading.Lock()
_device_detected = False


def ensure_device():
    """确保 GPU 可用性已探测一次（幂等，线程安全）。

    返回 "gpu" / "cpu"。首次调用会执行 nvidia-smi 探测（约 0.37 s）；
    之后直接返回缓存值，可安全地在后台线程与主线程同时调用。
    """
    global _device_detected
    if _device_detected:
        return os.environ.get("PDF2WORD_DEVICE", "cpu")
    with _device_lock:
        if not _device_detected:
            try:
                _detect_gpu()
            except Exception:
                os.environ["PDF2WORD_DEVICE"] = "cpu"
            _device_detected = True
    return os.environ.get("PDF2WORD_DEVICE", "cpu")


def detect_device_async(callback=None):
    """后台线程探测设备，完成后回调 callback(device)。用于不阻塞 UI 启动。"""

    def _run():
        try:
            dev = ensure_device()
        except Exception:
            dev = "cpu"
        if callback is not None:
            try:
                callback(dev)
            except Exception:
                pass

    t = threading.Thread(target=_run, name="pdf2word-gpu-probe", daemon=True)
    t.start()
    return t


def _register_nvidia_dll_dirs():
    """注册 nvidia CUDA 包的 bin/ 目录到 DLL 搜索路径。

    支持两种场景：
    1. GPU 版打包：nvidia.* 作为 Python 包被 PyInstaller 收集，可通过 importlib 导入
    2. 精简版 + 下载 GPU 包：nvidia/ 目录存在于 _internal/ 下，但不是 Python 包

    PyInstaller 打包后 nvidia 各子包的 DLL 在 _internal/nvidia/*/bin/ 下，
    不在系统 PATH 或 exe 同级目录中，paddle 加载 CUDA DLL 时会报
    "找不到指定的模块"。通过 os.add_dll_directory() 把这些目录注册上。
    """
    try:
        import importlib

        registered = set()

        # 方式1：通过 Python 包导入查找（GPU 版打包环境）
        for sub in [
            "cublas", "cuda_runtime", "cudnn",
            "cusolver",
        ]:
            try:
                mod = importlib.import_module(f"nvidia.{sub}")
                bin_dir = os.path.join(os.path.dirname(mod.__file__), "bin")
                if os.path.isdir(bin_dir) and bin_dir not in registered:
                    os.add_dll_directory(bin_dir)
                    registered.add(bin_dir)
                nvidia_root = os.path.dirname(os.path.dirname(mod.__file__))
                nvjit_bin = os.path.join(nvidia_root, "nvjitlink", "bin")
                if os.path.isdir(nvjit_bin) and nvjit_bin not in registered:
                    os.add_dll_directory(nvjit_bin)
                    registered.add(nvjit_bin)
            except Exception:
                pass

        # 方式2：直接扫描 _internal/nvidia/ 目录（精简版 + GPU 包下载场景）
        if not registered and getattr(sys, "frozen", False):
            base = os.path.dirname(sys.executable)
            for nvidia_root in (
                os.path.join(base, "_internal", "nvidia"),
                os.path.join(base, "nvidia"),
            ):
                if not os.path.isdir(nvidia_root):
                    continue
                for sub in ["cublas", "cuda_runtime", "cudnn", "cusolver", "nvjitlink"]:
                    bin_dir = os.path.join(nvidia_root, sub, "bin")
                    if os.path.isdir(bin_dir) and bin_dir not in registered:
                        os.add_dll_directory(bin_dir)
                        registered.add(bin_dir)
                if registered:
                    break
    except Exception:
        pass


def activate_gpu_device():
    """延迟激活 GPU 设备（在首次模型加载前由调用方触发）。

    即使 _detect_gpu() 因 nvidia-smi 不在 PATH 而误判为 CPU，
    此处仍会通过 paddle.device 二次确认，避免漏用 GPU。
    """
    try:
        _register_nvidia_dll_dirs()
        import paddle

        if paddle.device.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0:
            paddle.set_device("gpu")
            os.environ["PDF2WORD_DEVICE"] = "gpu"
        else:
            os.environ["PDF2WORD_DEVICE"] = "cpu"
    except Exception:
        os.environ["PDF2WORD_DEVICE"] = "cpu"


def ensure_env(fast=False):
    """运行环境初始化：GPU 检测、模型目录定位、paddlex 依赖补丁。

    fast=True 时跳过 GPU 探测（省 0.37 s），改由 ensure_device() / 后台线程后续执行。
    GUI 启动走 fast=True；CLI 与转换流程走默认值，保证行为与 v1.3 一致。
    """
    # 全局强制关闭 oneDNN（含环境变量与各 create_model 实例）。
    # 当前依赖栈（paddle 3.3 + paddlex）下开启会导致 OCR/版面模型推理崩溃，
    # 结论与复测方式见 experiments/onednn/README.md。
    os.environ.setdefault("FLAGS_use_mkldnn", "0")
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

    # GPU 自动检测（须在模型加载前完成）
    if fast:
        # 不阻塞启动：mkldnn 恒为 0，与设备判定无关（见 _detect_gpu 调用点）
        os.environ["FLAGS_use_mkldnn"] = "0"
    else:
        device = ensure_device()
        if device == "cpu":
            os.environ["FLAGS_use_mkldnn"] = "0"

    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
        mdir = os.path.join(base, "models")
        if os.path.isdir(mdir):
            # paddlex 在 import 时读取该变量决定模型缓存目录
            target = mdir if _is_ascii_path(mdir) else _relocate_models(mdir)
            os.environ.setdefault("PADDLE_PDX_CACHE_HOME", target)
        patch_paddlex_deps()
