"""缺少转换引擎时的引导弹窗。

只在用户真的遇到「没有引擎」时才出现（例如拖入 xlsx 但本机无 Office/WPS/LibreOffice），
不在启动时打扰。下载源默认走国内镜像。
"""

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from . import theme

ACTION_CLOSE = "close"


class EngineGuideDialog(QDialog):
    def __init__(self, parent, missing_text, size_mb, url, winget):
        super().__init__(parent)
        self.setWindowTitle("需要转换引擎")
        self.setModal(True)
        self.setMinimumWidth(520)
        self._url = url
        self._winget = winget
        self._build(missing_text, size_mb)
        self.adjustSize()

    def _build(self, missing_text, size_mb):
        c = theme.now_palette()
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 16)
        root.setSpacing(12)

        head = QHBoxLayout()
        head.setSpacing(10)
        badge = QLabel("!")
        badge.setFixedSize(22, 22)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background:{c['accent_soft']}; color:{c['accent_text']};"
            f"border-radius:11px; font-weight:700;"
        )
        head.addWidget(badge, 0, Qt.AlignTop)
        title = QLabel(f"转换 {missing_text} 需要一个办公套件")
        title.setObjectName("cardTitle")
        head.addWidget(title, 1)
        root.addLayout(head)

        body = QLabel(
            "PDF 工具本身不负责排版渲染，需要借助以下任一程序来生成 PDF：\n"
            "　• Microsoft Office 或 WPS（如果已安装，重启本程序即可识别）\n"
            f"　• LibreOffice（免费开源，安装包约 {size_mb} MB）"
        )
        body.setObjectName("hint")
        body.setWordWrap(True)
        root.addWidget(body)

        tip = QLabel("下载后双击安装即可，装完回到这里点「开始转换」。")
        tip.setObjectName("hint")
        tip.setWordWrap(True)
        root.addWidget(tip)

        btns = QHBoxLayout()
        btns.setSpacing(8)
        btn_copy = QPushButton("复制 winget 命令")
        btn_copy.setObjectName("link")
        btn_copy.clicked.connect(self._copy_winget)
        btns.addWidget(btn_copy)
        btns.addStretch(1)

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.reject)
        btns.addWidget(btn_close)

        btn_dl = QPushButton("打开下载页（国内镜像）")
        btn_dl.setObjectName("primary")
        btn_dl.setFixedHeight(36)
        btn_dl.clicked.connect(self._open_download)
        btns.addWidget(btn_dl)
        btn_dl.setDefault(True)
        root.addLayout(btns)

    def _open_download(self):
        QDesktopServices.openUrl(QUrl(self._url))
        self.accept()

    def _copy_winget(self):
        QApplication.clipboard().setText(self._winget)
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.information(
            self, "已复制",
            f"已复制到剪贴板：\n\n{self._winget}\n\n"
            "在 PowerShell 中粘贴执行即可安装（Windows 10 1809+ 自带 winget）。",
        )
