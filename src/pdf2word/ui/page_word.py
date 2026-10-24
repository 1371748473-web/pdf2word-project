"""PDF 转 Word 页（原主界面内容）。

参数区按两列网格对齐：DPI | 转换模式 / 两个复选并排 / 输出位置整行。
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
)

from .page_base import BasePage, form_grid


class WordPage(BasePage):
    FILE_EXTS = ("pdf",)
    RUN_TEXT = "开始转换"
    BUSY_TEXT = "转换中"
    EMPTY_TITLE = "拖拽 PDF 到此处"
    EMPTY_HINT = "支持文字版与扫描件，或点击下方「添加文件」"

    def __init__(self, parent=None):
        self._out_dir = None
        self._cur = (0, 0, "")
        super().__init__(parent)

    def _ready_summary(self):
        return ("支持文字版 PDF 精准转换；扫描件会自动识别文字并还原排版。"
                "添加文件后点击「开始转换」。")

    def _build_options(self, layout):
        g = form_grid()

        g.addWidget(QLabel("渲染精度"), 0, 0)
        self.cmb_dpi = QComboBox()
        for v, tip in (("150", "150 DPI · 快"), ("200", "200 DPI · 推荐"),
                       ("300", "300 DPI · 最清晰")):
            self.cmb_dpi.addItem(tip, v)
        self.cmb_dpi.setCurrentIndex(1)
        g.addWidget(self.cmb_dpi, 0, 1)

        g.addWidget(QLabel("转换模式"), 0, 2)
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItem("自动判定（推荐）", "auto")
        self.cmb_mode.addItem("仅文字版直转", "text")
        self.cmb_mode.addItem("仅扫描件识别", "scan")
        g.addWidget(self.cmb_mode, 0, 3)

        self.chk_imgtext = QCheckBox("提取图片中的文字")
        self.chk_imgtext.setChecked(True)
        self.chk_imgtext.setToolTip("把图片内的文字也识别成可编辑段落（灰色斜体标注）")
        self.chk_open = QCheckBox("完成后打开输出目录")
        self.chk_open.setChecked(True)
        g.addWidget(self.chk_imgtext, 1, 0, 1, 2)
        g.addWidget(self.chk_open, 1, 2, 1, 2)
        g.setRowStretch(1, 0)

        layout.addLayout(g)

        # 输出位置：整行，精简显示
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel("输出位置")
        lbl.setMinimumWidth(56)
        row.addWidget(lbl)
        self.lbl_out = QLabel(self._out_text())
        self.lbl_out.setObjectName("hint")
        row.addWidget(self.lbl_out, 1)
        btn_change = QPushButton("更改…")
        btn_change.setObjectName("link")
        btn_change.clicked.connect(self._pick_out_dir)
        row.addWidget(btn_change)
        self.btn_reset_out = QPushButton("恢复默认")
        self.btn_reset_out.setObjectName("link")
        self.btn_reset_out.clicked.connect(self._reset_out_dir)
        self.btn_reset_out.setVisible(False)
        row.addWidget(self.btn_reset_out)
        layout.addLayout(row)

    # ---- 输出位置 ----
    def _out_text(self):
        return f"与源文件同目录（{self._out_dir}）" if self._out_dir else "与源文件同目录"

    def _pick_out_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录", self._out_dir or "")
        if d:
            self._out_dir = os.path.normpath(d)
            self.lbl_out.setText(self._out_text())
            self.btn_reset_out.setVisible(True)

    def _reset_out_dir(self):
        self._out_dir = None
        self.lbl_out.setText(self._out_text())
        self.btn_reset_out.setVisible(False)

    # ---- 任务 ----
    def _progress_extra(self):
        idx, total, name = self._cur
        if total:
            return f"第 {idx}/{total} 个文件 · {name}"
        return ""

    def _make_task(self, subset=None):
        files = list(subset) if subset else self.list.paths()
        if not files:
            raise ValueError("请先添加 PDF 文件")
        dpi = int(self.cmb_dpi.currentData())
        mode = self.cmb_mode.currentData()
        imgtext = self.chk_imgtext.isChecked()
        out_dir = self._out_dir
        open_after = self.chk_open.isChecked()
        total = len(files)

        def job(task):
            from ..core import convert_pdf

            ok_n = 0
            fail = []
            for idx, f in enumerate(files):
                if task.should_stop():
                    task.log("已取消，停止后续文件")
                    break
                self._cur = (idx + 1, total, os.path.basename(f))
                task.log("")
                task.log(f"━━ [{idx + 1}/{total}] {os.path.basename(f)} ━━")
                out = (os.path.join(out_dir, os.path.splitext(os.path.basename(f))[0] + ".docx")
                       if out_dir else os.path.splitext(f)[0] + ".docx")

                def _p(done, tot, idx=idx):
                    task.progress(int((idx + done / max(tot, 1)) / total * 100))

                try:
                    convert_pdf(f, out_path=out, dpi=dpi, mode=mode,
                                extract_image_text=imgtext, log=task.log, progress=_p)
                    ok_n += 1
                except Exception as e:  # noqa: BLE001 - 单文件失败继续
                    fail.append((f, str(e)))
                    self.note_failed(f, e)
                    task.log(f"[失败] {e}")

            if open_after and (out_dir or files):
                try:
                    os.startfile(out_dir or os.path.dirname(files[0]))
                except OSError:
                    pass

            if fail:
                return f"已转换 {ok_n} 个，{len(fail)} 个未能完成"
            return f"已转换 {ok_n} 个文件为 Word"

        return job
