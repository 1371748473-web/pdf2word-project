# -*- coding: utf-8 -*-
"""PyInstaller 运行时钩子：修复冻结环境下 paddle 子模块未绑定回父包的问题。

背景
----
paddle/__init__.py 第 62 行调用 monkey_patch_variable()。该函数内部有一个
"是否已打过补丁" 的标志位，标志位为真时走 else 分支：

        import paddle.tensor
        for method_name in paddle.tensor.tensor_method_func:   # ← 983 行
            ...

关键在于 `import paddle.tensor` 这一句：CPython 的
importlib._bootstrap._find_and_load_unlocked() 中有这样一段（俗称
"crazy side-effects"）：

        if parent:
            if parent not in sys.modules:
                _call_with_frames_removed(import_, parent)
            if name in sys.modules:
                return sys.modules[name]        # ← 提前返回
            ...
        ...
        setattr(parent_module, child, module)   # ← 绑定父包属性

也就是说：**当 paddle.tensor 已经在 sys.modules 里时，会提前返回，
不会执行 setattr**，paddle 模块对象上就没有 tensor 这个属性。

源码目录下运行时，paddle.tensor 通常是第一次被导入，于是正常绑定；
而 PyInstaller 把所有模块塞进 PYZ 后，paddle 各子模块的加载顺序发生变化，
paddle.tensor 可能在 paddle/__init__ 之前/期间就已经被载入 sys.modules，
于是命中提前返回分支，最终抛出：

    AttributeError: partially initialized module 'paddle'
                    has no attribute 'tensor' (most likely due to a circular import)

本钩子在每次 `import paddle.*` 之后，若发现子模块没有绑定到父包上，
就手动补一次 setattr，从而修复该问题。

诊断：设置环境变量 PDF2WORD_DEBUG=1 时，补绑动作会打印到 stderr。
"""

import builtins
import os
import sys

_orig_import = builtins.__import__
_DEBUG = os.environ.get("PDF2WORD_DEBUG") == "1"

_logged = set()


def _log(msg):
    if not _DEBUG:
        return
    if msg in _logged:
        return
    _logged.add(msg)
    try:
        sys.stderr.write("[pyi_rth_paddle] %s\n" % msg)
        sys.stderr.flush()
    except Exception:
        pass


def _ensure_bound(full_name):
    """把 sys.modules 中已存在的 paddle 子模块逐级绑定到各自的父包上。"""
    parts = full_name.split(".")
    for i in range(1, len(parts)):
        parent_name = ".".join(parts[:i])
        child = parts[i]
        child_name = ".".join(parts[: i + 1])
        parent = sys.modules.get(parent_name)
        sub = sys.modules.get(child_name)
        if parent is None or sub is None:
            continue
        if hasattr(parent, child):
            continue
        try:
            setattr(parent, child, sub)
            _log("补绑 %s -> %s" % (parent_name, child))
        except Exception:
            pass


def _patched_import(name, globals=None, locals=None, fromlist=(), level=0):
    # 只有 paddle 相关导入需要额外处理；其余直接放行，开销仅一次 startswith
    need = type(name) is str and not level and name.startswith("paddle")
    if need:
        try:
            _ensure_bound(name)
        except Exception:
            pass

    mod = _orig_import(name, globals, locals, fromlist, level)

    if need:
        try:
            if name == "paddle":
                # paddle 本体导入完成后，兜底把已存在的直接子模块全部绑定
                prefix = "paddle."
                for k in list(sys.modules.keys()):
                    if k.startswith(prefix) and "." not in k[len(prefix):]:
                        _ensure_bound(k)
            else:
                _ensure_bound(name)
        except Exception:
            pass
    return mod


builtins.__import__ = _patched_import
