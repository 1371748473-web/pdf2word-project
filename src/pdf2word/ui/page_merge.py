"""PDF 合并页：顺序可调、可逐文件指定页面范围、可保留书签。"""

import os
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
)

from .page_base import BasePage


def _default_out_name():
    return "合并结果_" + datetime.now().strftime("%Y%m%d_%H%M") + ".pdf"


class MergePage(BasePage):
    FILE_EXTS = ("pdf",)
    RUN_TEXT = "开始合并"
    BUSY_TEXT = "合并中"
    EMPTY_TITLE = "拖拽多个 PDF 到此处"
    EMPTY_HINT = "按列表顺序合并，可用下方按钮调整先后"
    CAN_RETRY_SUBSET = False  # 合并是整体操作，失败后重跑整批

    def __init__(self, parent=None):
        self._out = None
        self._total_pages = 0
        super().__init__(parent)

    def _ready_summary(self):
        return "按列表顺序合并。双击某个文件可单独指定页面范围（如 1-5,8）。"

    def _build_options(self, layout):
        # 顺序调整按钮插到文件卡片底部
        btn_up = QPushButton("上移")
        btn_up.setObjectName("ghost")
        btn_up.clicked.connect(lambda: self.list.move_selected(-1))
        btn_down = QPushButton("下移")
        btn_down.setObjectName("ghost")
        btn_down.clicked.connect(lambda: self.list.move_selected(1))
        self.list_bar.insertWidget(2, btn_up)
        self.list_bar.insertWidget(3, btn_down)
        self.list.itemDoubleClicked.connect(self._edit_range)

        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel("输出文件")
        lbl.setMinimumWidth(56)
        row.addWidget(lbl)
        self.txt_out = QLineEdit()
        self.txt_out.setReadOnly(True)
        self.txt_out.setPlaceholderText("默认：第一个文件所在目录 / 合并结果_时间戳.pdf")
        row.addWidget(self.txt_out, 1)
        btn = QPushButton("更改…")
        btn.setObjectName("link")
        btn.clicked.connect(self._pick_out)
        row.addWidget(btn)
        layout.addLayout(row)

        self.chk_bookmark = QCheckBox("保留源文件书签（以文件名分组）")
        self.chk_bookmark.setChecked(True)
        layout.addWidget(self.chk_bookmark)

        hint = QLabel("提示：双击列表中的文件可设置该文件的页面范围，例如 1-5,8")
        hint.setObjectName("hint")
        layout.addWidget(hint)

    # ---- 交互 ----
    def _pick_out(self):
        start = self._out or (os.path.dirname(self.list.paths()[0]) if self.list.paths() else "")
        default = os.path.join(start, _default_out_name())
        f, _ = QFileDialog.getSaveFileName(self, "保存为", default, "PDF 文件 (*.pdf)")
        if f:
            if not f.lower().endswith(".pdf"):
                f += ".pdf"
            self._out = os.path.normpath(f)
            self.txt_out.setText(self._out)

    def _edit_range(self, item):
        path = item.data(Qt.UserRole)
        rng = item.data(Qt.UserRole + 1) or ""
        text, ok = QInputDialog.getText(
            self, "页面范围",
            f"{os.path.basename(path)}\n\n输入页面范围（留空 = 全部，例：1-5,8）：",
            text=rng,
        )
        if not ok:
            return
        rng = text.strip()
        item.setData(Qt.UserRole + 1, rng)
        base = os.path.basename(path)
        self.list.set_display_text(
            path, f"{base}    [{rng}]" if rng else base,
            tooltip=f"页面范围：{rng}" if rng else None,
        )

    def _progress_extra(self):
        n = len(self.list.paths())
        return f"共 {n} 个文件"

    def _make_task(self, subset=None):
        files = list(subset) if subset else self.list.paths()
        if not files:
            raise ValueError("请先添加 PDF 文件")
        ranges = [
            self.list.item(i).data(Qt.UserRole + 1) or ""
            for i in range(self.list.count())
        ]
        out = self._out or os.path.join(os.path.dirname(files[0]), _default_out_name())
        out_dir = os.path.dirname(os.path.abspath(out))
        if out_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)
        keep_bm = self.chk_bookmark.isChecked()

        def job(task):
            from ..merge import merge_pdfs

            task.log(f"合并 {len(files)} 个文件 → {out}")
            final_out, pages, failed = merge_pdfs(
                files, out, ranges=ranges, keep_bookmarks=keep_bm,
                log=task.log, progress=task.progress, should_stop=task.should_stop,
            )
            if failed:
                return f"合并完成（{pages} 页，跳过 {len(failed)} 个文件）"
            return f"已合并 {len(files)} 个文件，共 {pages} 页"

        return job
