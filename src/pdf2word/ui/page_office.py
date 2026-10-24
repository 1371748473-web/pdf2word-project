"""Office 转 PDF 页。

引擎策略（auto）：本机 Office/WPS > 内置 docx 引擎 > LibreOffice。
- 内置 docx 引擎（dxpdf，约 12 MB）只处理 .docx，无需任何外部程序
- xlsx / pptx 需要 Office/WPS 或 LibreOffice，缺失时在页面内给出下载引导
"""

import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from .dialog_guide import EngineGuideDialog
from .page_base import BasePage, form_grid


class OfficePage(BasePage):
    FILE_EXTS = ("docx", "xlsx", "pptx")
    RUN_TEXT = "开始转换"
    BUSY_TEXT = "转换中"
    EMPTY_TITLE = "拖拽 Word / Excel / PPT 到此处"
    EMPTY_HINT = "支持 docx、xlsx、pptx"

    def __init__(self, parent=None):
        self._out_dir = None
        self._cur = (0, 0)
        self._info = {}
        super().__init__(parent)

    def _ready_summary(self):
        return ("Word 文档可直接转换；Excel / PPT 需要本机装有 Office/WPS，"
                "或安装一次免费的 LibreOffice。")

    def _build_options(self, layout):
        g = form_grid()
        g.addWidget(QLabel("转换引擎"), 0, 0)
        self.cmb_engine = QComboBox()
        self.cmb_engine.addItem("自动选择（推荐）", "auto")
        self.cmb_engine.addItem("仅本机 Office / WPS", "com")
        self.cmb_engine.addItem("仅内置 docx 引擎", "dxpdf")
        self.cmb_engine.addItem("仅 LibreOffice", "libreoffice")
        g.addWidget(self.cmb_engine, 0, 1)
        layout.addLayout(g)

        self.lbl_engine = QLabel("正在检测可用引擎…")
        self.lbl_engine.setObjectName("hint")
        self.lbl_engine.setWordWrap(True)
        layout.addWidget(self.lbl_engine)

        # 缺引擎时的引导行：只在需要时出现，不打断操作
        self.guide_row = QWidget()
        gh = QHBoxLayout(self.guide_row)
        gh.setContentsMargins(0, 0, 0, 0)
        gh.setSpacing(8)
        self.lbl_guide = QLabel()
        self.lbl_guide.setObjectName("hint")
        self.lbl_guide.setWordWrap(True)
        gh.addWidget(self.lbl_guide, 1)
        self.btn_download = QPushButton("下载 LibreOffice")
        self.btn_download.setObjectName("link")
        self.btn_download.setCursor(Qt.PointingHandCursor)
        self.btn_download.clicked.connect(self.open_download)
        gh.addWidget(self.btn_download)
        self.guide_row.setVisible(False)
        layout.addWidget(self.guide_row)

        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel("输出位置")
        lbl.setMinimumWidth(56)
        row.addWidget(lbl)
        self.lbl_out = QLabel("与源文件同目录（同名 .pdf）")
        self.lbl_out.setObjectName("hint")
        row.addWidget(self.lbl_out, 1)
        btn = QPushButton("更改…")
        btn.setObjectName("link")
        btn.clicked.connect(self._pick_out_dir)
        row.addWidget(btn)
        layout.addLayout(row)

    # ---- 引擎检测 ----
    def showEvent(self, e):
        super().showEvent(e)
        if not self._info:
            self.refresh_engines()

    def refresh_engines(self):
        from ..office2pdf import LO_SIZE_MB, describe_engines, detect_engines

        try:
            info = detect_engines()
        except Exception as e:  # noqa: BLE001 - 检测失败不影响其他功能
            self.lbl_engine.setText(f"引擎检测失败：{e}")
            return
        self._info = info
        self.lbl_engine.setText("可用引擎：" + describe_engines(info))

        com = info.get("com") or {}
        has_lo = bool(info.get("lo"))
        lacking = []
        if "excel" not in com and not has_lo:
            lacking.append("Excel")
        if "ppt" not in com and not has_lo:
            lacking.append("PPT")

        if lacking:
            self.lbl_guide.setText(
                f"未检测到可转换 {'/'.join(lacking)} 的引擎。"
                f"安装 Office/WPS，或下载免费 LibreOffice（约 {LO_SIZE_MB} MB）。"
            )
            self.guide_row.setVisible(True)
        else:
            self.guide_row.setVisible(False)

    def open_download(self):
        from ..office2pdf import primary_download_url

        QDesktopServices.openUrl(QUrl(primary_download_url()))

    def _pick_out_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录", self._out_dir or "")
        if d:
            self._out_dir = os.path.normpath(d)
            self.lbl_out.setText(self._out_dir)

    def _progress_extra(self):
        i, n = self._cur
        return f"第 {i}/{n} 个文件" if n else ""

    # ---- 任务 ----
    def _make_task(self, subset=None):
        from ..office2pdf import (KIND_BY_EXT, LO_SIZE_MB, WINGET_CMD,
                                  detect_engines, missing_kind_names,
                                  primary_download_url)

        files = list(subset) if subset else self.list.paths()
        if not files:
            raise ValueError("请先添加 Office 文件")
        engine = self.cmb_engine.currentData()
        outdir = self._out_dir
        total = len(files)

        # 预检查：先算清有没有引擎，缺就直接引导，不要等任务跑一半才失败
        info = detect_engines()
        com = info.get("com") or {}
        has_lo = bool(info.get("lo"))
        has_dx = bool(info.get("dxpdf"))
        kinds = set()
        for f in files:
            k = KIND_BY_EXT.get(os.path.splitext(f)[1].lower())
            if k:
                kinds.add(k)

        if engine == "auto":
            lacking = [
                k for k in kinds
                if not (k in com or (k == "word" and has_dx) or has_lo)
            ]
        elif engine == "com":
            lacking = [k for k in kinds if k not in com]
        elif engine == "dxpdf":
            lacking = [k for k in kinds if k != "word" or not has_dx]
        else:
            lacking = list(kinds) if not has_lo else []

        if lacking:
            dlg = EngineGuideDialog(
                self, missing_kind_names(lacking), LO_SIZE_MB,
                primary_download_url(), WINGET_CMD,
            )
            dlg.exec()
            self.refresh_engines()
            return None

        def job(task):
            from ..office2pdf import convert_many

            self._cur = (1, total)
            ok, fail, used, skipped, failed_files = convert_many(
                files, out_dir=outdir, engine=engine,
                log=task.log, progress=task.progress, should_stop=task.should_stop,
            )
            for path, why in failed_files:
                self.note_failed(path, why)
            self._cur = (total, total)
            task.progress(100)
            name = {
                "com": "本机 Office",
                "dxpdf": "内置 docx 引擎",
                "libreoffice": "LibreOffice",
                "none": "无",
            }
            used_text = " + ".join(name.get(x, x) for x in used.split("+"))
            msg = f"成功 {ok} 个，失败 {fail} 个（引擎：{used_text}）"
            if skipped:
                msg += f"，跳过 {len(skipped)} 个不支持的文件"
            return msg

        return job
