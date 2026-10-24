"""极简 COM 自动化封装（ctypes + IDispatch），只为驱动 Office 导出 PDF 而生。

为什么不用 pywin32 / comtypes：
    两者会给安装包增加 20~30 MB，并在 PyInstaller 下引入额外 hiddenimports 与 DLL
    处理问题。本模块约 180 行，覆盖 GetIDsOfNames / Invoke 两个调用，够用且体积 +0。

实测踩过的坑（2026-10-22，详见 experiments/office_com/README.md）：
    1. oleaut32 绝不能用 ctypes.oledll —— 它按 c_long 解析返回值，x64 上会把 BSTR
       指针截断成野指针（表现为 0x80020005 或访问冲突）。必须 WinDLL + restype=c_void_p。
       给 oledll 的实例设置 restype 也**无效**。
    2. GetIDsOfNames 的参数顺序是 (riid, rgszNames, cNames, lcid, rgDispId)，
       cNames 必须为 1，否则报 0x800706F4。
    3. PowerPoint 只认绝对路径，相对路径会被它按自身工作目录解析而报"找不到文件"。
"""

import ctypes
from ctypes import POINTER, byref, c_long, c_longlong, c_ubyte, c_ulong, c_void_p
from ctypes import c_wchar_p, wintypes

ole32 = ctypes.oledll.ole32  # HRESULT 返回值，失败会自动抛 OSError
# 注意：BSTR 相关必须用 WinDLL（见模块文档第 1 条）
_oleaut = ctypes.WinDLL("oleaut32")
_oleaut.SysAllocString.restype = c_void_p
_oleaut.SysAllocString.argtypes = [c_wchar_p]
_oleaut.SysFreeString.restype = None
_oleaut.SysFreeString.argtypes = [c_void_p]

CLSCTX_LOCAL_SERVER = 0x4
DISPATCH_METHOD = 1
DISPATCH_PROPERTYGET = 2
DISPATCH_PROPERTYPUT = 4

VT_I2, VT_I4, VT_BOOL, VT_BSTR, VT_DISPATCH, VT_ERROR = 2, 3, 11, 8, 9, 10
DISP_E_PARAMNOTFOUND = 0x80020004
DISPID_PROPERTYPUT = -3


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", c_ubyte * 8),
    ]


class _U(ctypes.Union):
    _fields_ = [
        ("llVal", c_longlong),
        ("bstrVal", c_void_p),
        ("pdispVal", c_void_p),
        ("_pad", c_ubyte * 16),
    ]


class VARIANT(ctypes.Structure):
    _fields_ = [
        ("vt", wintypes.WORD),
        ("wReserved1", wintypes.WORD),
        ("wReserved2", wintypes.WORD),
        ("wReserved3", wintypes.WORD),
        ("_u", _U),
    ]


class DISPPARAMS(ctypes.Structure):
    _fields_ = [
        ("rgvarg", POINTER(VARIANT)),
        ("rgdispidNamedArgs", POINTER(c_long)),
        ("cArgs", ctypes.c_uint),
        ("cNamedArgs", ctypes.c_uint),
    ]


class EXCEPINFO(ctypes.Structure):
    _fields_ = [
        ("wCode", wintypes.WORD),
        ("wReserved", wintypes.WORD),
        ("bstrSource", c_void_p),
        ("bstrDescription", c_void_p),
        ("bstrHelpFile", c_void_p),
        ("dwHelpContext", c_ulong),
        ("pvReserved", c_void_p),
        ("pfnDeferredFillIn", c_void_p),
        ("scode", c_long),
    ]


class ComError(OSError):
    """COM 调用失败。"""


def _fn(ptr, index, restype, *argtypes):
    """从 COM 接口指针取 vtable[index]，转成可直接调用的函数（首参为 this）。"""
    vtbl = ctypes.cast(ptr, POINTER(c_void_p))[0]
    addr = ctypes.cast(vtbl, POINTER(c_void_p))[index]
    return ctypes.WINFUNCTYPE(restype, c_void_p, *argtypes)(addr)


def _var(vt, value=None):
    v = VARIANT()
    v.vt = vt
    if vt == VT_BSTR:
        v._u.bstrVal = _oleaut.SysAllocString(c_wchar_p(str(value)))
    elif vt == VT_DISPATCH:
        v._u.pdispVal = value
    elif vt == VT_BOOL:
        v._u.llVal = -1 if value else 0
    elif vt in (VT_I2, VT_I4, VT_ERROR):
        v._u.llVal = int(value)
    return v


class ComObject:
    """IDispatch 对象包装。"""

    __slots__ = ("ptr", "progid", "_released")

    def __init__(self, ptr, progid=""):
        self.ptr = ptr
        self.progid = progid
        self._released = False

    # ---- 内部 ----
    def _dispid(self, name):
        arr = (c_wchar_p * 1)(c_wchar_p(name))
        dispid = c_long()
        fn = _fn(self.ptr, 5, c_long, POINTER(GUID), POINTER(c_wchar_p),
                 ctypes.c_uint, c_ulong, POINTER(c_long))
        hr = fn(self.ptr, byref(GUID()), arr, 1, 0, byref(dispid))
        if hr < 0:
            raise ComError(
                f"{self.progid}: 找不到成员 '{name}' (0x{hr & 0xFFFFFFFF:08X})"
            )
        return dispid.value

    def _invoke(self, dispid, flags, args, named_put=False):
        n = len(args)
        rgvarg = (VARIANT * max(n, 1))()
        for i, a in enumerate(args):
            rgvarg[n - 1 - i] = a  # IDispatch 参数逆序
        dp = DISPPARAMS()
        dp.rgvarg = ctypes.cast(rgvarg, POINTER(VARIANT))
        dp.cArgs = n
        if named_put:
            named = (c_long * 1)(DISPID_PROPERTYPUT)
            dp.rgdispidNamedArgs = ctypes.cast(named, POINTER(c_long))
            dp.cNamedArgs = 1
        result = VARIANT()
        excep = EXCEPINFO()
        uargerr = ctypes.c_uint()
        fn = _fn(self.ptr, 6, c_long, c_long, POINTER(GUID), c_ulong,
                 wintypes.WORD, POINTER(DISPPARAMS), POINTER(VARIANT),
                 POINTER(EXCEPINFO), POINTER(ctypes.c_uint))
        hr = fn(self.ptr, dispid, byref(GUID()), 0, flags, byref(dp),
                byref(result), byref(excep), byref(uargerr))
        if hr < 0:
            desc = ""
            if excep.bstrDescription:
                desc = ctypes.wstring_at(excep.bstrDescription)
            raise ComError(
                f"{self.progid}: 调用失败 (0x{hr & 0xFFFFFFFF:08X}) {desc}".strip()
            )
        if result.vt == VT_DISPATCH and result._u.pdispVal:
            return ComObject(result._u.pdispVal, self.progid)
        if result.vt == VT_BSTR:
            return ctypes.wstring_at(result._u.bstrVal) if result._u.bstrVal else ""
        if result.vt == VT_BOOL:
            return bool(result._u.llVal)
        if result.vt in (VT_I2, VT_I4):
            return int(result._u.llVal)
        return None

    # ---- 公开 ----
    def call(self, name, *args):
        """调用方法。args 为 (vt, value) 元组。"""
        return self._invoke(
            self._dispid(name),
            DISPATCH_METHOD | DISPATCH_PROPERTYGET,
            [_var(vt, v) for vt, v in args],
        )

    def get(self, name):
        """读取属性。"""
        return self._invoke(self._dispid(name), DISPATCH_PROPERTYGET, [])

    def set(self, name, vt, value):
        """写入属性。"""
        self._invoke(self._dispid(name), DISPATCH_PROPERTYPUT,
                     [_var(vt, value)], named_put=True)

    def release(self):
        if self.ptr and not self._released:
            try:
                _fn(self.ptr, 2, c_ulong)(self.ptr)  # Release
            except Exception:
                pass
            self._released = True
            self.ptr = None

    def __del__(self):
        self.release()


def progid_exists(progid):
    """判断 ProgID 是否已注册（即对应 Office/WPS 组件是否安装）。

    用注册表查 HKCR\\<ProgID>\\CLSID，**不要**用 CLSIDFromProgID：
    后者在未初始化的线程里实测要 20 s（本机 Word/Excel/PPT 三个共 20 s），
    注册表查询同样三个只要 0.002 s。
    """
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, progid + r"\CLSID"):
            return True
    except OSError:
        return False


def create(progid):
    """按 ProgID 创建 COM 对象。调用前需已 CoInitialize（见 com_session）。"""
    clsid = GUID()
    ole32.CLSIDFromProgID(c_wchar_p(progid), byref(clsid))
    iid = GUID(0x00020400, 0x0000, 0x0000,
               (c_ubyte * 8)(0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46))
    pdisp = c_void_p()
    ole32.CoCreateInstance(byref(clsid), None, CLSCTX_LOCAL_SERVER,
                           byref(iid), byref(pdisp))
    if not pdisp:
        raise ComError(f"无法创建 {progid}")
    return ComObject(pdisp, progid)


class com_session:
    """COM 初始化上下文管理器（STA）。用法: with com_session(): ..."""

    def __init__(self):
        self._inited = False

    def __enter__(self):
        try:
            ole32.CoInitializeEx(None, 0x2)  # STA
            self._inited = True
        except OSError:
            pass  # 已初始化（S_FALSE）也继续
        return self

    def __exit__(self, *exc):
        if self._inited:
            try:
                ole32.CoUninitialize()
            except Exception:
                pass
        return False
