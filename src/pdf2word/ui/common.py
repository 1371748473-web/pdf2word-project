"""后台任务线程（各页面共用）。

业务任务一律通过 TaskThread 执行：UI 线程只负责收集参数、显示进度，
避免长任务阻塞窗口。任务函数签名：func(task)，可调用
task.log() / task.progress() / task.should_stop()。
"""

import traceback

from PySide6.QtCore import QThread, Signal


class TaskThread(QThread):
    sig_log = Signal(str)
    sig_percent = Signal(int)
    sig_done = Signal(bool, str)

    def __init__(self, func, parent=None):
        super().__init__(parent)
        self._func = func
        self._stop = False

    # ---- 供任务函数调用 ----
    def log(self, s):
        self.sig_log.emit(str(s))

    def progress(self, pct):
        self.sig_percent.emit(max(0, min(100, int(pct))))

    def should_stop(self):
        return self._stop

    # ---- 外部控制 ----
    def ask_stop(self):
        self._stop = True

    def run(self):
        try:
            msg = self._func(self) or ""
            self.sig_done.emit(True, str(msg))
        except Exception as e:  # noqa: BLE001 - 任务内任何异常都要回传 UI
            self.sig_log.emit(f"[错误] {e}")
            self.sig_log.emit(traceback.format_exc())
            self.sig_done.emit(False, str(e))
