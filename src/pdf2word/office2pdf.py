"""Office → PDF：双引擎调度。

引擎策略：
    auto（默认）  本机装了 Office/WPS → 走 COM（0.5~2.8 s/文件，零体积代价）
                 否则 → 走内置 LibreOffice（自包含，首次 8~15 s，可用预热进程加速）
    com           强制本机 Office/WPS
    libreoffice   强制内置 LibreOffice（用于兼容性对照）

进程清理（实测必须做，见 experiments/office_com/README.md）：
    Office 的 Quit 不保证进程退出。任务结束后枚举「本次新增且无窗口标题」的
    Office 进程并结束它们；有窗口标题的通常是用户自己打开的文档，一律不动。
"""

import os
import subprocess
import sys

from .minicom import (VT_BOOL, VT_BSTR, VT_I4, ComError, com_session, create,
                      progid_exists)

#: 扩展名 → 应用类型
KIND_BY_EXT = {
    ".docx": "word", ".doc": "word", ".rtf": "word",
    ".xlsx": "excel", ".xls": "excel", ".csv": "excel",
    ".pptx": "ppt", ".ppt": "ppt",
}

#: 应用类型 → 依次尝试的 ProgID（先 MS Office，再 WPS）
PROGIDS = {
    "word": ("Word.Application", "KWPS.Application"),
    "excel": ("Excel.Application", "KET.Application"),
    "ppt": ("PowerPoint.Application", "KWPP.Application"),
}

#: 各 Office 组件的进程名（用于残留清理）
OFFICE_PROCS = {
    "winword.exe", "excel.exe", "powerpnt.exe",
    "wps.exe", "et.exe", "wpp.exe",
}

#: Office 导出为 PDF 的格式常量
WORD_PDF = 17       # wdFormatPDF
EXCEL_PDF = 0       # xlTypePDF
PPT_PDF = 32        # ppSaveAsPDF


# ---------------------------------------------------------------- 引擎检测

def detect_com_engine():
    """返回 {kind: progid}，只包含本机可用的组件。"""
    found = {}
    for kind, candidates in PROGIDS.items():
        for pid in candidates:
            if progid_exists(pid):
                found[kind] = pid
                break
    return found


def find_soffice():
    """定位可用的 soffice.exe，找不到返回 None。

    查找顺序：
        1. 环境变量 PDF2WORD_LO（调试用，可指向任意绿色目录）
        2. 打包内置：<程序目录>/_internal/libreoffice/program/soffice.exe
        3. 系统安装：C:\\Program Files\\LibreOffice\\program\\soffice.exe
    注意：**不探测** experiments/ 下的实验目录 —— 那里是从 MSI 还原的半成品，
    实测无法启动（services 注册残留冲突），若被识别为"已就绪"会误导用户。
    """
    env = os.environ.get("PDF2WORD_LO")
    if env and os.path.isfile(env):
        return env

    cands = []
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
        cands += [
            os.path.join(base, "_internal", "libreoffice", "program", "soffice.exe"),
            os.path.join(base, "libreoffice", "program", "soffice.exe"),
        ]
    cands += [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    for p in cands:
        if os.path.isfile(p):
            return p
    return None


def detect_engines():
    """返回 {"com": {kind: progid}, "lo": soffice路径或None, "dxpdf": bool}。"""
    return {
        "com": detect_com_engine(),
        "lo": find_soffice(),
        "dxpdf": dxpdf_available(),
    }


def describe_engines(info=None):
    """生成给界面显示的一行中文描述。"""
    info = info or detect_engines()
    com = info["com"]
    names = {"word": "Word", "excel": "Excel", "ppt": "PowerPoint"}
    parts = []
    if com:
        parts.append("本机 " + "/".join(names[k] for k in ("word", "excel", "ppt") if k in com))
    else:
        parts.append("未检测到 Office/WPS")
    if info.get("dxpdf"):
        parts.append("内置 docx 引擎")
    if info.get("lo"):
        parts.append("LibreOffice")
    return "｜".join(parts)


def missing_kind_names(kinds):
    names = {"word": "Word 文档", "excel": "Excel 表格", "ppt": "PPT 演示"}
    return "、".join(names.get(k, k) for k in kinds)


# ---------------------------------------------------------------- 下载源

#: 推荐下载的 LibreOffice 版本（与镜像目录一致）
LO_VERSION = "26.8.1"
#: 安装包体积（MB），用于引导文案
LO_SIZE_MB = 358
#: 下载源：国内镜像优先，官方主站兜底。
#: 清华 TUNA 实测直链可用且文件大小与官方一致（374,870,016 字节）。
LO_MIRRORS = (
    ("清华镜像",
     f"https://mirrors.tuna.tsinghua.edu.cn/libreoffice/libreoffice/stable/"
     f"{LO_VERSION}/win/x86_64/LibreOffice_{LO_VERSION}_Win_x86-64.msi"),
    ("官方主站",
     f"https://download.documentfoundation.org/libreoffice/stable/"
     f"{LO_VERSION}/win/x86_64/LibreOffice_{LO_VERSION}_Win_x86-64.msi"),
)
#: 备选：winget 一行命令（Windows 10 1809+ 自带）
WINGET_CMD = "winget install TheDocumentFoundation.LibreOffice"


def primary_download_url():
    return LO_MIRRORS[0][1]


# ---------------------------------------------------------------- dxpdf 引擎

#: 内置 docx 引擎支持的扩展名（dxpdf 只做 docx）
DXPDF_EXTS = {".docx"}


def dxpdf_available():
    """内置 docx 引擎是否可用。

    用 find_spec 而不是真正 import：dxpdf 会加载 Skia（约 100 ms），
    启动期与引擎探测都不该付这个成本。
    """
    try:
        import importlib.util

        return importlib.util.find_spec("dxpdf") is not None
    except Exception:
        return False


# ---------------------------------------------------------------- 公共工具

def out_path_for(src, out_dir):
    """计算目标 PDF 路径。"""
    name = os.path.splitext(os.path.basename(src))[0] + ".pdf"
    if out_dir:
        return os.path.join(os.path.abspath(out_dir), name)
    return os.path.splitext(os.path.abspath(src))[0] + ".pdf"


def _proc_snapshot():
    """返回 {pid: (进程名小写, 是否有可见带标题窗口)}，毫秒级。

    注意：**不能用 tasklist /V** —— 它需要逐进程取窗口标题，本机实测 20 s 以上
    （v1.4 首次联调就是被它拖到 46 s）。这里用 Toolhelp32 + EnumWindows 原生枚举。
    """
    import ctypes
    from ctypes import wintypes

    TH32CS_SNAPPROCESS = 0x2

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == -1:
        return {}

    visible = _pids_with_window()
    out = {}
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = k32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            pid = int(entry.th32ProcessID)
            out[pid] = (entry.szExeFile.lower(), pid in visible)
            ok = k32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        k32.CloseHandle(snap)
    return out


def _pids_with_window():
    """收集「有可见且带标题的顶层窗口」的进程 PID，用于区分用户文档与自动化实例。"""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    pids = set()

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _cb(hwnd, _lparam):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            if user32.GetWindowTextLengthW(hwnd) <= 0:
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            pids.add(int(pid.value))
        except Exception:
            pass
        return True

    try:
        user32.EnumWindows(_cb, 0)
    except Exception:
        pass
    return pids


def cleanup_orphans(before_pids, log=print):
    """结束本次新增且无可见窗口的 Office 进程（有窗口的多为用户文档，不动）。"""
    after = _proc_snapshot()
    killed = 0
    for pid, (name, has_window) in after.items():
        if pid in before_pids or name not in OFFICE_PROCS:
            continue
        if has_window:
            continue  # 有窗口 → 用户正在用，跳过
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                           capture_output=True, timeout=10)
            killed += 1
        except Exception:
            pass
    if killed:
        log(f"[清理] 结束 {killed} 个残留的 Office 后台进程")
    return killed


# ---------------------------------------------------------------- COM 引擎

def _convert_group_com(kind, progid, files, out_dir, log, progress, should_stop,
                       done_counter, total):
    """用同一个 Application 实例批量转换同类型文件。"""
    app = None
    try:
        log(f"启动 {progid} ...")
        app = create(progid)
        try:
            app.set("DisplayAlerts", VT_I4, 0)
        except ComError:
            pass
        try:
            # 禁止宏：msoAutomationSecurityForceDisable = 3
            app.set("AutomationSecurity", VT_I4, 3)
        except ComError:
            pass
        if kind != "ppt":
            # PowerPoint 不支持隐藏窗口，设了会抛错
            try:
                app.set("Visible", VT_BOOL, False)
            except ComError:
                pass

        for src in files:
            if should_stop and should_stop():
                log("已取消，停止后续文件")
                break
            dst = out_path_for(src, out_dir)
            name = os.path.basename(src)
            log(f"  {name} → {os.path.basename(dst)}")
            try:
                if kind == "word":
                    docs = app.get("Documents")
                    doc = docs.call("Open", (VT_BSTR, os.path.abspath(src)),
                                    (VT_BOOL, False), (VT_BOOL, True),
                                    (VT_BOOL, False))
                    try:
                        doc.call("SaveAs2", (VT_BSTR, dst), (VT_I4, WORD_PDF))
                    finally:
                        doc.call("Close", (VT_I4, 0))
                elif kind == "excel":
                    books = app.get("Workbooks")
                    wb = books.call("Open", (VT_BSTR, os.path.abspath(src)),
                                    (VT_I4, 0), (VT_BOOL, True))
                    try:
                        wb.call("ExportAsFixedFormat", (VT_I4, EXCEL_PDF),
                                (VT_BSTR, dst))
                    finally:
                        wb.call("Close", (VT_BOOL, False))
                else:  # ppt
                    pres_list = app.get("Presentations")
                    pres = pres_list.call("Open", (VT_BSTR, os.path.abspath(src)),
                                          (VT_BOOL, True), (VT_BOOL, False),
                                          (VT_BOOL, False))
                    try:
                        pres.call("SaveAs", (VT_BSTR, dst), (VT_I4, PPT_PDF))
                    finally:
                        pres.call("Close")
                ok = os.path.isfile(dst) and os.path.getsize(dst) > 0
                if not ok:
                    raise RuntimeError("导出后未生成有效 PDF")
                log(f"      完成 {os.path.getsize(dst) / 1024:.0f} KB")
            except Exception as e:  # noqa: BLE001 - 单文件失败继续下一个
                log(f"      [失败] {e}")
            done_counter[0] += 1
            if progress:
                progress(done_counter[0] / max(total, 1) * 100)
    finally:
        if app is not None:
            try:
                app.call("Quit")
            except Exception:
                pass
            app.release()


# ---------------------------------------------------------------- LibreOffice 引擎

def _lo_profile_dir():
    """LibreOffice 的用户配置目录。

    必须落在系统盘：实测把 -env:UserInstallation 指向 E 盘（数据盘）时，
    soffice 会以 0xC0000409（STACK_BUFFER_OVERRUN）崩溃，且不产生任何日志；
    同一份文件指向 C 盘则正常转换。若用户把 LOCALAPPDATA 改到了别的盘，
    这里强制回退到系统盘临时目录。
    """
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    p = os.path.join(base, "PDFToolbox", "lo_profile")
    drive = os.path.splitdrive(os.path.abspath(p))[0].upper()
    sys_drive = os.environ.get("SystemDrive", "C:").upper()
    if drive and drive != sys_drive:
        p = os.path.join(os.environ.get("TEMP", sys_drive + "\\Temp"),
                         "PDFToolbox_lo_profile")
    os.makedirs(p, exist_ok=True)
    return p


def _convert_with_lo(soffice, files, out_dir, log, progress, should_stop,
                     done_counter, total):
    profile = _lo_profile_dir()
    profile_url = "file:///" + profile.replace("\\", "/")
    for src in files:
        if should_stop and should_stop():
            log("已取消，停止后续文件")
            break
        dst = out_path_for(src, out_dir)
        log(f"  {os.path.basename(src)} → {os.path.basename(dst)}")
        target_dir = os.path.dirname(dst)
        os.makedirs(target_dir, exist_ok=True)
        cmd = [
            soffice,
            "--headless", "--norestore", "--nolockcheck", "--nodefault",
            f"-env:UserInstallation={profile_url}",
            "--convert-to", "pdf", "--outdir", target_dir,
            os.path.abspath(src),
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=180)
            if not (os.path.isfile(dst) and os.path.getsize(dst) > 0):
                msg = (r.stderr or b"").decode("utf-8", "replace").strip()
                raise RuntimeError(msg or "LibreOffice 未生成 PDF")
            log(f"      完成 {os.path.getsize(dst) / 1024:.0f} KB")
        except subprocess.TimeoutExpired:
            log("      [失败] 转换超时（180 s）")
        except Exception as e:  # noqa: BLE001
            log(f"      [失败] {e}")
        done_counter[0] += 1
        if progress:
            progress(done_counter[0] / max(total, 1) * 100)


# ---------------------------------------------------------------- dxpdf 引擎

def _convert_with_dxpdf(files, out_dir, log, progress, should_stop, done_counter, total):
    """内置 docx 引擎：纯本地排版渲染，不启动任何 Office 进程。

    仅支持 .docx（xlsx/pptx 会由调度层分给 Office/LibreOffice）。
    """
    import dxpdf

    for src in files:
        if should_stop and should_stop():
            log("已取消，停止后续文件")
            break
        dst = out_path_for(src, out_dir)
        log(f"  {os.path.basename(src)} → {os.path.basename(dst)}")
        try:
            dxpdf.convert_file(os.path.abspath(src), dst)
            if not (os.path.isfile(dst) and os.path.getsize(dst) > 0):
                raise RuntimeError("未生成 PDF")
            log(f"      完成 {os.path.getsize(dst) / 1024:.0f} KB")
        except Exception as e:  # noqa: BLE001 - 单文件失败继续
            log(f"      [失败] {e}")
        done_counter[0] += 1
        if progress:
            progress(done_counter[0] / max(total, 1) * 100)


# ---------------------------------------------------------------- 对外入口

def convert_many(inputs, out_dir=None, engine="auto", log=print,
                 progress=None, should_stop=None):
    """批量转换，返回 (ok_count, fail_count, used_engine, skipped, failed_files)。

    used_engine: "com" / "libreoffice"
    skipped:     不支持的文件 [(path, 原因)]
    failed_files: 转换失败的 [(path, 原因)]，供「只重试失败项」使用
    """
    inputs = [os.path.abspath(p) for p in inputs]
    total = max(len(inputs), 1)

    # 输出目录必须提前创建：Office 的 SaveAs / ExportAsFixedFormat 不会自建目录，
    # 目录不存在时只报笼统的 "命令失败(0x80020009)"（v1.4 联调时踩到）。
    if out_dir:
        out_dir = os.path.abspath(out_dir)
        os.makedirs(out_dir, exist_ok=True)

    # 1) 按扩展名筛选
    groups, skipped = {}, []
    for p in inputs:
        ext = os.path.splitext(p)[1].lower()
        kind = KIND_BY_EXT.get(ext)
        if not kind:
            skipped.append((p, f"不支持的格式 {ext}"))
            continue
        if not os.path.isfile(p):
            skipped.append((p, "文件不存在"))
            continue
        groups.setdefault(kind, []).append(p)
    for p, why in skipped:
        log(f"[跳过] {os.path.basename(p)}：{why}")

    if not groups:
        raise RuntimeError("没有可转换的文件")

    info = detect_engines()
    com_map = info["com"]
    soffice = info["lo"]
    dx_ok = info.get("dxpdf", False)

    # 逐类型选择引擎：本机 Office（保真最高）> 内置 docx 引擎 > LibreOffice
    plan = {}
    for kind in groups:
        if engine == "com":
            if kind in com_map:
                plan[kind] = "com"
        elif engine == "libreoffice":
            if soffice:
                plan[kind] = "libreoffice"
        elif engine == "dxpdf":
            if kind == "word" and dx_ok:
                plan[kind] = "dxpdf"
        else:  # auto
            if kind in com_map:
                plan[kind] = "com"
            elif kind == "word" and dx_ok:
                plan[kind] = "dxpdf"
            elif soffice:
                plan[kind] = "libreoffice"

    missing = [k for k in groups if k not in plan]
    if missing:
        what = missing_kind_names(missing)
        if engine == "com":
            raise RuntimeError(f"本机缺少对应的 Office 组件：{what}")
        if engine == "libreoffice":
            raise RuntimeError("未找到可用的 LibreOffice")
        if engine == "dxpdf":
            raise RuntimeError("内置 docx 引擎只能处理 .docx 文件")
        raise RuntimeError(
            f"没有可用于转换 {what} 的引擎。\n"
            "安装 Microsoft Office / WPS，或安装 LibreOffice（免费，约 "
            f"{LO_SIZE_MB} MB）后即可转换。"
        )

    used_engines = []
    done_counter = [0]
    need_com = any(v == "com" for v in plan.values())
    before = _proc_snapshot() if need_com else {}

    try:
        if need_com:
            log("使用引擎：本机 Office（COM）")
            # COM 必须在已初始化（STA）的线程里调用；QThread 里同样适用
            with com_session():
                for kind, eng in plan.items():
                    if eng != "com":
                        continue
                    if should_stop and should_stop():
                        break
                    _convert_group_com(kind, com_map[kind], groups[kind], out_dir,
                                       log, progress, should_stop, done_counter, total)
            used_engines.append("com")

        if "dxpdf" in plan.values():
            log("使用引擎：内置 docx 引擎")
            for kind, eng in plan.items():
                if eng == "dxpdf":
                    _convert_with_dxpdf(groups[kind], out_dir, log, progress,
                                        should_stop, done_counter, total)
            used_engines.append("dxpdf")

        if "libreoffice" in plan.values():
            log("使用引擎：LibreOffice")
            lo_files = [f for k, e in plan.items() if e == "libreoffice"
                        for f in groups[k]]
            _convert_with_lo(soffice, lo_files, out_dir, log, progress,
                             should_stop, done_counter, total)
            used_engines.append("libreoffice")
    finally:
        if need_com:
            cleanup_orphans(before, log)

    used = "+".join(used_engines) if used_engines else "none"

    # 2) 统计结果
    ok = fail = 0
    failed_files = []
    for files in groups.values():
        for src in files:
            dst = out_path_for(src, out_dir)
            if os.path.isfile(dst) and os.path.getsize(dst) > 0:
                ok += 1
            else:
                fail += 1
                failed_files.append((src, "未生成 PDF（原因见详细日志）"))
    return ok, fail, used, skipped, failed_files
