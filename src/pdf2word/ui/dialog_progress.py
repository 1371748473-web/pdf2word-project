"""长任务进度弹窗。

策略：任务开始后**延迟 1 秒**才出现（PROGRESS_DIALOG_DELAY_MS）。
    - 1 秒内完成的任务：弹窗从不出现，不会闪一下窗口
    - 超过 1 秒：弹出，带进度、当前文件、已用时间、取消按钮
    - 任务结束自动关闭

为什么用非模态：用户可以关掉它继续看页面日志，任务不受影响；
真正要中断时点「取消转换」。
"""

import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)


class ProgressDialog(QDialog):
    cancel_requested = Signal()

    def __init__(self, parent, title="正在处理", subject=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(False)
        self.setMinimumWidth(440)
        # 不固定高度：内容较多时固定高度会把进度条压成 0 像素
        self.setMinimumHeight(210)
        # 关掉窗口不销毁，只是隐藏；任务继续
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._t0 = time.time()
        self._finished = False
        self._build(title, subject)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(200)

    # ---- 布局 ----
    def _build(self, title, subject):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 16)
        root.setSpacing(10)

        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("cardTitle")
        root.addWidget(self.lbl_title)

        self.lbl_subject = QLabel(subject or "请稍候，正在处理…")
        self.lbl_subject.setObjectName("hint")
        self.lbl_subject.setWordWrap(True)
        root.addWidget(self.lbl_subject)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        root.addWidget(self.bar)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.lbl_status = QLabel("进度 0%")
        self.lbl_status.setObjectName("hint")
        row.addWidget(self.lbl_status, 1)
        self.lbl_time = QLabel("已用 0.0 秒")
        self.lbl_time.setObjectName("hint")
        row.addWidget(self.lbl_time)
        root.addLayout(row)

        tip = QLabel("关闭此窗口不会停止任务，进度仍显示在页面上。")
        tip.setObjectName("hint")
        root.addWidget(tip)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btn_cancel = QPushButton("取消转换")
        self.btn_cancel.clicked.connect(self._on_cancel)
        btns.addWidget(self.btn_cancel)
        root.addLayout(btns)

    # ---- 外部更新 ----
    def set_progress(self, pct, extra=""):
        self.bar.setValue(max(0, min(100, int(pct))))
        text = f"进度 {int(pct)}%"
        if extra:
            text += f" · {extra}"
        self.lbl_status.setText(text)

    def set_status(self, text):
        self.lbl_status.setText(text)

    def set_subject(self, text):
        self.lbl_subject.setText(text)

    def _tick(self):
        if self._finished:
            return
        self.lbl_time.setText(f"已用 {time.time() - self._t0:.1f} 秒")

    def _on_cancel(self):
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setText("正在停止…")
        self.lbl_status.setText("正在停止，等待当前文件结束…")
        self.cancel_requested.emit()

    def finish(self):
        """任务结束时调用：停止计时并关闭。"""
        self._finished = True
        self._timer.stop()
        self.close()

    def closeEvent(self, e):
        # 用户点 X 只是隐藏，不触发取消
        self._timer.stop()
        super().closeEvent(e)
