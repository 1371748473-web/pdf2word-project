"""失败报告弹窗：列出未完成的文件与原因，支持「只重试这些」。

设计取舍：
    - 全部成功不弹窗（只走 Toast），避免打断；
    - 有失败时才弹，且默认按钮是「只重试失败的 N 个」——
      这是弹窗相对 Toast 的唯一实质价值：不用重跑已经成功的文件。
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from . import theme

ACTION_RETRY = "retry"
ACTION_LOG = "log"
ACTION_CLOSE = "close"


class FailureDialog(QDialog):
    def __init__(self, parent, failed, summary="", can_retry=True):
        """failed: [(路径或名称, 原因)]"""
        super().__init__(parent)
        self.action = ACTION_CLOSE
        self.failed = list(failed)
        self.setWindowTitle("处理未完成")
        self.setModal(True)
        self.resize(560, 300)
        self.setMinimumWidth(480)
        self._build(summary, can_retry)
        # 列表高度按项数收紧，避免少量失败时出现大片空白
        self.adjustSize()

    def _build(self, summary, can_retry):
        c = theme.now_palette()
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(12)

        n = len(self.failed)
        head = QHBoxLayout()
        head.setSpacing(10)
        badge = QLabel("!")
        badge.setFixedSize(22, 22)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background:{c['danger_soft']}; color:{c['danger']};"
            f"border-radius:11px; font-weight:700;"
        )
        head.addWidget(badge, 0, Qt.AlignTop)
        title = QLabel(f"有 {n} 个文件未能完成" if n else "处理未完成")
        title.setObjectName("cardTitle")
        head.addWidget(title, 1)
        root.addLayout(head)

        if summary:
            sub = QLabel(summary)
            sub.setObjectName("hint")
            sub.setWordWrap(True)
            root.addWidget(sub)

        if n:
            lst = QListWidget()
            lst.setObjectName("dropList")
            lst.setProperty("hasFiles", True)
            lst.setSelectionMode(QListWidget.NoSelection)
            for path, reason in self.failed:
                item = QListWidgetItem(f"{os.path.basename(path)}    —    {reason}")
                item.setToolTip(f"{path}\n{reason}")
                item.setSizeHint(item.sizeHint().expandedTo(
                    item.sizeHint().__class__(0, 34)))
                lst.addItem(item)
            lst.setFixedHeight(min(40 + n * 34, 260))
            root.addWidget(lst, 1)

        hint = QLabel("已成功的文件不会重复处理。" if n and can_retry else "")
        hint.setObjectName("hint")
        hint.setVisible(bool(hint.text()))
        root.addWidget(hint)

        btns = QHBoxLayout()
        btns.setSpacing(8)
        btn_log = QPushButton("查看详细日志")
        btn_log.setObjectName("link")
        btn_log.clicked.connect(self._on_log)
        btns.addWidget(btn_log)
        btns.addStretch(1)

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self._on_close)
        btns.addWidget(btn_close)

        if n and can_retry:
            btn_retry = QPushButton(f"只重试这 {n} 个")
            btn_retry.setObjectName("primary")
            btn_retry.setFixedHeight(36)
            btn_retry.clicked.connect(self._on_retry)
            btns.addWidget(btn_retry)
            btn_retry.setDefault(True)
        root.addLayout(btns)

    def _on_retry(self):
        self.action = ACTION_RETRY
        self.accept()

    def _on_log(self):
        self.action = ACTION_LOG
        self.accept()

    def _on_close(self):
        self.action = ACTION_CLOSE
        self.reject()
