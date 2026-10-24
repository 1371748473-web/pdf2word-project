"""PDF 转图片页：格式 × 分辨率 × 两种输出模式（独立多张 / 拼接长图）。"""

import os

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
)

from .page_base import BasePage, form_grid


class ImagePage(BasePage):
    FILE_EXTS = ("pdf",)
    RUN_TEXT = "开始转换"
    BUSY_TEXT = "转换中"
    EMPTY_TITLE = "拖拽 PDF 到此处"
    EMPTY_HINT = "可输出多张独立图片，或拼接成一张长图"

    def __init__(self, parent=None):
        self._out_dir = None
        self._cur = (0, 0)
        super().__init__(parent)

    def _ready_summary(self):
        return "选择格式与分辨率后开始。长图模式会自动分卷，避免超大图片。"

    def _build_options(self, layout):
        g = form_grid()

        g.addWidget(QLabel("图片格式"), 0, 0)
        self.cmb_fmt = QComboBox()
        for label, val in (("PNG（无损）", "png"), ("JPG（体积小）", "jpg"),
                           ("WebP", "webp"), ("BMP", "bmp"), ("TIFF", "tiff")):
            self.cmb_fmt.addItem(label, val)
        g.addWidget(self.cmb_fmt, 0, 1)

        g.addWidget(QLabel("分辨率"), 0, 2)
        self.cmb_dpi = QComboBox()
        self.cmb_dpi.setEditable(True)
        for v, label in (("120", "120 DPI · 网页用"), ("150", "150 DPI · 推荐"),
                         ("200", "200 DPI · 清晰"), ("300", "300 DPI · 印刷用")):
            self.cmb_dpi.addItem(label, v)
        self.cmb_dpi.setCurrentIndex(1)
        g.addWidget(self.cmb_dpi, 0, 3)

        g.addWidget(QLabel("输出模式"), 1, 0)
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItem("每页一张独立图片", "separate")
        self.cmb_mode.addItem("拼接为一张长图", "long")
        g.addWidget(self.cmb_mode, 1, 1)

        g.addWidget(QLabel("JPG 质量"), 1, 2)
        self.spin_quality = QSpinBox()
        self.spin_quality.setRange(60, 100)
        self.spin_quality.setValue(90)
        self.spin_quality.setSuffix(" %")
        g.addWidget(self.spin_quality, 1, 3)

        g.addWidget(QLabel("长图单卷上限"), 2, 0)
        self.spin_maxh = QSpinBox()
        self.spin_maxh.setRange(2000, 60000)
        self.spin_maxh.setSingleStep(1000)
        self.spin_maxh.setValue(20000)
        self.spin_maxh.setSuffix(" px")
        g.addWidget(self.spin_maxh, 2, 1)

        g.addWidget(QLabel("页间距"), 2, 2)
        self.spin_gap = QSpinBox()
        self.spin_gap.setRange(0, 200)
        self.spin_gap.setValue(0)
        self.spin_gap.setSuffix(" px")
        g.addWidget(self.spin_gap, 2, 3)
        layout.addLayout(g)

        # 输出目录整行
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel("输出目录")
        lbl.setMinimumWidth(56)
        row.addWidget(lbl)
        self.lbl_out = QLabel("源文件所在目录下新建「文件名_images」文件夹")
        self.lbl_out.setObjectName("hint")
        row.addWidget(self.lbl_out, 1)
        btn = QPushButton("更改…")
        btn.setObjectName("link")
        btn.clicked.connect(self._pick_out_dir)
        row.addWidget(btn)
        layout.addLayout(row)

        self.cmb_fmt.currentIndexChanged.connect(self._sync)
        self.cmb_mode.currentIndexChanged.connect(self._sync)
        self._sync()

    def _sync(self):
        fmt = self.cmb_fmt.currentData()
        is_long = self.cmb_mode.currentData() == "long"
        self.spin_quality.setEnabled(fmt == "jpg")
        self.spin_maxh.setEnabled(is_long)
        self.spin_gap.setEnabled(is_long)

    def _pick_out_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录", self._out_dir or "")
        if d:
            self._out_dir = os.path.normpath(d)
            self.lbl_out.setText(self._out_dir)

    def _progress_extra(self):
        i, n = self._cur
        return f"第 {i}/{n} 个文件" if n else ""

    def _make_task(self, subset=None):
        files = list(subset) if subset else self.list.paths()
        if not files:
            raise ValueError("请先添加 PDF 文件")
        try:
            dpi = int(float(self.cmb_dpi.currentData() or self.cmb_dpi.currentText().split()[0]))
        except (ValueError, IndexError):
            raise ValueError("分辨率请输入数字") from None
        if not 50 <= dpi <= 600:
            raise ValueError("分辨率建议在 50~600 DPI 之间")

        fmt = self.cmb_fmt.currentData()
        mode = self.cmb_mode.currentData()
        quality = self.spin_quality.value()
        max_h = self.spin_maxh.value()
        gap = self.spin_gap.value()
        outdir = self._out_dir
        total = len(files)

        def job(task):
            from ..pdf2img import pdf_to_images

            total_files = 0
            failed = 0
            for i, pdf in enumerate(files):
                if task.should_stop():
                    task.log("已取消")
                    break
                self._cur = (i + 1, total)
                name = os.path.basename(pdf)
                task.log("")
                task.log(f"━━ [{i + 1}/{total}] {name} ━━")
                target = outdir or os.path.join(
                    os.path.dirname(pdf), os.path.splitext(name)[0] + "_images"
                )
                task.log(f"输出目录: {target}")

                def sub(pct, i=i):
                    task.progress((i + pct / 100) / total * 100)

                try:
                    produced = pdf_to_images(
                        pdf, target, fmt=fmt, dpi=dpi, mode=mode,
                        jpeg_quality=quality, gap=gap, max_height=max_h,
                        log=task.log, progress=sub, should_stop=task.should_stop,
                    )
                    total_files += len(produced)
                except Exception as e:  # noqa: BLE001 - 单文件失败继续
                    failed += 1
                    self.note_failed(pdf, e)
                    task.log(f"[失败] {e}")

            if total_files == 0 and failed == 0:
                return "未生成任何图片"
            msg = f"已生成 {total_files} 个图片文件"
            if failed:
                msg += f"，{failed} 个文件未完成"
            return msg

        return job
