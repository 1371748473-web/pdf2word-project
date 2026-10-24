"""可复用的交互控件：拖拽文件列表、Toast、折叠日志、状态胶囊、卡片。

设计要点：
    - FileList 自带空状态引导（虚线框 + 图标 + 文案）、拖拽悬停高亮、
      行内删除按钮、右键菜单、页数/大小元信息（后台线程读取，不卡 UI）
    - 所有控件只依赖 PySide6；业务模块（pymupdf 等）在后台线程里延迟导入
"""

import os
import time

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import theme


def human_size(n):
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n / 1024 / 1024:.1f} MB"


class Card(QFrame):
    """卡片容器：标题用 QLabel（QGroupBox::title 的字号在 QSS 下不可控）+ 内容布局 body。"""

    def __init__(self, title, c=None, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 14)
        lay.setSpacing(10)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("cardTitle")
        lay.addWidget(self.title_label)
        self.body = lay
        if c:
            theme.elevated(self, c, blur=16, dy=2, alpha=22)


def make_card(title, c=None):
    """创建带轻投影的卡片容器，内容加到 card.body。"""
    return Card(title, c)


# ---------------------------------------------------------------- 元信息

class _MetaWorker(QThread):
    """后台读取 PDF 页数（首次会导入 pymupdf，约 0.6 s，不阻塞界面）。"""

    sig_meta = Signal(str, int)  # path, page_count（读取失败为 -1）

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue = []
        self._stop = False

    def enqueue(self, path):
        if path in self._queue:
            return
        self._queue.append(path)
        if not self.isRunning():
            self.start()

    def stop(self):
        self._stop = True

    def run(self):
        import pymupdf

        while not self._stop:
            if not self._queue:
                self.msleep(60)
                if not self._queue:
                    return
                continue
            path = self._queue.pop(0)
            pages = -1
            try:
                doc = pymupdf.open(path)
                pages = doc.page_count
                doc.close()
            except Exception:
                pages = -1
            self.sig_meta.emit(path, pages)


class FileRow(QWidget):
    """文件列表的一行：图标 + 名称 + 元信息 + hover 出现的删除按钮。"""

    remove_requested = Signal(str)

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path
        self.setObjectName("fileRow")
        h = QHBoxLayout(self)
        h.setContentsMargins(8, 4, 6, 4)
        h.setSpacing(9)

        self.lbl_icon = QLabel()
        self.lbl_icon.setFixedSize(18, 18)
        h.addWidget(self.lbl_icon)

        col = QVBoxLayout()
        col.setSpacing(1)
        self.lbl_name = QLabel(os.path.basename(path))
        self.lbl_name.setObjectName("fileName")
        self.lbl_meta = QLabel(self._size_text())
        self.lbl_meta.setObjectName("fileMeta")
        col.addWidget(self.lbl_name)
        col.addWidget(self.lbl_meta)
        h.addLayout(col, 1)

        self.btn_remove = QPushButton("✕")
        self.btn_remove.setObjectName("rowRemove")
        self.btn_remove.setFixedSize(24, 24)
        self.btn_remove.setCursor(Qt.PointingHandCursor)
        self.btn_remove.setToolTip("从列表移除")
        self.btn_remove.clicked.connect(lambda: self.remove_requested.emit(self.path))
        self.btn_remove.setVisible(False)  # hover 时才显示
        h.addWidget(self.btn_remove)

        self._pages = None
        self._paint_icon()

    # ---- 内部 ----
    def _size_text(self):
        try:
            return human_size(os.path.getsize(self.path))
        except OSError:
            return "—"

    def _paint_icon(self):
        """画一个 18x18 的文档小图标（避免额外图片资源）。"""
        pm = self.lbl_icon.pixmap()
        from PySide6.QtGui import QPixmap

        pm = QPixmap(18, 18)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        col = QColor(self._icon_color())
        p.setPen(QPen(col, 1.4))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(3.5, 1.5, 11, 15), 2.5, 2.5)
        p.drawLine(6, 6, 12, 6)
        p.drawLine(6, 9, 12, 9)
        p.drawLine(6, 12, 10, 12)
        p.end()
        self.lbl_icon.setPixmap(pm)

    def _icon_color(self):
        # 跟随当前字体色（暗色主题下自动变浅），避免硬编码
        return self.palette().color(self.foregroundRole()).name()

    def set_pages(self, pages):
        self._pages = pages
        if pages and pages > 0:
            self.lbl_meta.setText(f"{pages} 页 · {self._size_text()}")
        elif pages == 0:
            self.lbl_meta.setText(f"空文档 · {self._size_text()}")

    def repaint_icon(self):
        """主题切换后重绘图标（颜色跟随前景色）。"""
        self._paint_icon()

    # ---- hover ----
    def enterEvent(self, e):
        self.btn_remove.setVisible(True)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.btn_remove.setVisible(False)
        super().leaveEvent(e)


class FileList(QListWidget):
    """可拖拽的文件列表，带空状态、拖拽高亮与右键菜单。"""

    files_changed = Signal(list)

    def __init__(self, extensions, empty_title="拖拽文件到此处",
                 empty_hint="或点击下方「添加文件」", show_pages=True, parent=None):
        super().__init__(parent)
        self.setObjectName("dropList")
        self.extensions = tuple("." + e.lower().lstrip(".") for e in extensions)
        self.empty_title = empty_title
        self.empty_hint = empty_hint
        self.show_pages = show_pages
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.setProperty("hasFiles", False)
        self.setProperty("dragActive", False)
        self._rows = {}
        self._meta = None
        self._on_open_request = None

    # ---- 空状态绘制 ----
    def paintEvent(self, e):
        super().paintEvent(e)
        if self.count() == 0:
            self._paint_empty()

    def _paint_empty(self):
        c = theme.now_palette()
        p = QPainter(self.viewport())
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.viewport().rect()
        cx = rect.center().x()
        cy = rect.center().y() - 26

        # 图标：一个加号 + 文档轮廓
        col = QColor(c["text_faint"])
        p.setPen(QPen(col, 1.6))
        p.drawRoundedRect(QRectF(cx - 13, cy - 15, 26, 32), 4, 4)
        p.drawLine(cx - 6, cy + 1, cx + 6, cy + 1)
        p.drawLine(cx, cy - 5, cx, cy + 7)

        f = QFont(self.font())
        f.setPointSizeF(10)
        p.setFont(f)
        p.setPen(QColor(c["text_sub"]))
        p.drawText(QRectF(rect.left(), cy + 26, rect.width(), 22),
                   Qt.AlignHCenter | Qt.AlignTop, self.empty_title)

        f2 = QFont(self.font())
        f2.setPointSizeF(9)
        p.setFont(f2)
        p.setPen(QColor(c["text_faint"]))
        p.drawText(QRectF(rect.left(), cy + 48, rect.width(), 20),
                   Qt.AlignHCenter | Qt.AlignTop, self.empty_hint)
        p.end()

    # ---- 拖拽 ----
    def _has_acceptable(self, mime):
        if not mime.hasUrls():
            return False
        for url in mime.urls():
            p = url.toLocalFile()
            if p and os.path.isfile(p) and p.lower().endswith(self.extensions):
                return True
        return False

    def dragEnterEvent(self, e):
        if self._has_acceptable(e.mimeData()):
            self._set_prop("dragActive", True)
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragLeaveEvent(self, e):
        self._set_prop("dragActive", False)
        super().dragLeaveEvent(e)

    def dragMoveEvent(self, e):
        if self._has_acceptable(e.mimeData()):
            e.acceptProposedAction()

    def dropEvent(self, e):
        self._set_prop("dragActive", False)
        paths = []
        for url in e.mimeData().urls():
            p = url.toLocalFile()
            if p and os.path.isfile(p) and p.lower().endswith(self.extensions):
                paths.append(os.path.normpath(p))
        if paths:
            self.add_paths(paths)
            e.acceptProposedAction()

    # ---- 数据 ----
    def _set_prop(self, name, value):
        self.setProperty(name, value)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def add_paths(self, paths):
        existing = set(self.paths())
        added = 0
        for p in paths:
            if p in existing:
                continue
            item = QListWidgetItem()
            item.setData(Qt.UserRole, p)
            item.setToolTip(p)
            item.setSizeHint(QSize(0, 48))  # 显式高度，否则首行可能只渲染出标题
            self.addItem(item)
            row = FileRow(p)
            row.setMinimumHeight(44)
            row.remove_requested.connect(self.remove_path)
            self.setItemWidget(item, row)
            self._rows[p] = (item, row)
            existing.add(p)
            added += 1
            if self.show_pages:
                self._ensure_meta().enqueue(p)
        if added:
            self._refresh_state()
            self.files_changed.emit(self.paths())

    def remove_path(self, path):
        entry = self._rows.pop(path, None)
        if not entry:
            return
        item, _ = entry
        row = self.row(item)
        if row >= 0:
            self.takeItem(row)
        self._refresh_state()
        self.files_changed.emit(self.paths())

    def remove_selected(self):
        for item in list(self.selectedItems()):
            p = item.data(Qt.UserRole)
            self._rows.pop(p, None)
            self.takeItem(self.row(item))
        self._refresh_state()
        self.files_changed.emit(self.paths())

    def clear_all(self):
        self.clear()
        self._rows.clear()
        self._refresh_state()
        self.files_changed.emit([])

    def paths(self):
        out = []
        for i in range(self.count()):
            item = self.item(i)
            p = item.data(Qt.UserRole)
            if p:
                out.append(p)
        return out

    def move_selected(self, delta):
        rows = sorted(self.row(i) for i in self.selectedItems())
        if not rows:
            return
        if delta < 0 and rows[0] == 0:
            return
        if delta > 0 and rows[-1] == self.count() - 1:
            return
        for r in (rows if delta < 0 else reversed(rows)):
            item = self.takeItem(r)
            self.insertItem(r + delta, item)
            entry = self._rows.get(item.data(Qt.UserRole))
            if entry:
                self.setItemWidget(item, entry[1])
            item.setSelected(True)
        self.files_changed.emit(self.paths())

    def set_display_text(self, path, text, tooltip=None):
        """修改某一行的主标题（合并页用它显示页面范围）。"""
        entry = self._rows.get(path)
        if not entry:
            return
        row = entry[1]
        row.lbl_name.setText(text)
        row.lbl_name.setToolTip(tooltip or "")

    def _refresh_state(self):
        self._set_prop("hasFiles", self.count() > 0)

    def _ensure_meta(self):
        if self._meta is None:
            self._meta = _MetaWorker(self)
            self._meta.sig_meta.connect(self._on_meta)
        return self._meta

    def _on_meta(self, path, pages):
        entry = self._rows.get(path)
        if entry:
            entry[1].set_pages(pages)

    # ---- 右键菜单 ----
    def set_open_handler(self, fn):
        """fn(path) -> None，用于「打开文件」菜单项。"""
        self._on_open_request = fn

    def _context_menu(self, pos: QPoint):
        item = self.itemAt(pos)
        menu = QMenu(self)
        if item:
            path = item.data(Qt.UserRole)
            act_open = menu.addAction("打开文件")
            act_dir = menu.addAction("打开所在目录")
            menu.addSeparator()
            act_remove = menu.addAction("从列表移除")
            act = menu.exec(self.viewport().mapToGlobal(pos))
            if act == act_open and self._on_open_request:
                self._on_open_request(path)
            elif act == act_open:
                try:
                    os.startfile(path)
                except OSError:
                    pass
            elif act == act_dir:
                try:
                    os.startfile(os.path.dirname(path))
                except OSError:
                    pass
            elif act == act_remove:
                self.remove_path(path)
        else:
            act = menu.addAction("清空列表")
            if menu.exec(self.viewport().mapToGlobal(pos)) == act:
                self.clear_all()


# ---------------------------------------------------------------- Toast

class Toast(QFrame):
    """右上角轻提示，自动淡出。"""

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 16, 10)
        lay.setSpacing(10)
        self.lbl_icon = QLabel("✓")
        self.lbl_icon.setObjectName("toastIconOk")
        self.lbl_text = QLabel("")
        self.lbl_text.setObjectName("toastText")
        self.lbl_text.setWordWrap(False)
        lay.addWidget(self.lbl_icon)
        lay.addWidget(self.lbl_text, 1)

        self._eff = QGraphicsOpacityEffect(self)
        self._eff.setOpacity(0.0)
        self.setGraphicsEffect(self._eff)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self.hide()

    def show_message(self, text, ok=True, msec=2800):
        c = theme.now_palette()
        self.lbl_icon.setText("✓" if ok else "!")
        self.lbl_icon.setObjectName("toastIconOk" if ok else "toastIconErr")
        self.lbl_icon.style().unpolish(self.lbl_icon)
        self.lbl_icon.style().polish(self.lbl_icon)
        self.lbl_text.setText(text)
        theme.elevated(self, c, blur=24, dy=4, alpha=48)
        self.adjustSize()
        self._place()
        try:
            self.show()
            self.raise_()
            self._eff.setOpacity(1.0)
        except RuntimeError:
            # 窗口/效果已销毁（例如任务完成瞬间用户关掉了程序），忽略即可
            return
        self._timer.start(msec)

    def _place(self):
        p = self.parentWidget()
        if not p:
            return
        m = 18
        self.move(p.width() - self.width() - m, m)

    def _fade_out(self):
        try:
            self.hide()
        except RuntimeError:
            pass


# ---------------------------------------------------------------- 日志

class LogPanel(QWidget):
    """折叠式日志：默认只显示一行摘要，点开才看详细日志。"""

    expanded_changed = Signal(bool)

    def __init__(self, summary="就绪", parent=None):
        super().__init__(parent)
        self._expanded = False
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.lbl_summary = QLabel(summary)
        self.lbl_summary.setObjectName("hint")
        self.lbl_summary.setWordWrap(True)
        head.addWidget(self.lbl_summary, 1)

        self.btn_toggle = QPushButton("详细日志 ▾")
        self.btn_toggle.setObjectName("link")
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_toggle.clicked.connect(self.toggle)
        head.addWidget(self.btn_toggle, 0, Qt.AlignRight)
        root.addLayout(head)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumBlockCount(1200)
        self.text.setMinimumHeight(110)
        self.text.hide()
        root.addWidget(self.text)

    def toggle(self):
        self._expanded = not self._expanded
        self.text.setVisible(self._expanded)
        self.btn_toggle.setText("收起日志 ▴" if self._expanded else "详细日志 ▾")
        self.expanded_changed.emit(self._expanded)

    def expand(self):
        if not self._expanded:
            self.toggle()

    def log(self, s):
        self.text.appendPlainText(str(s))

    def set_summary(self, s):
        self.lbl_summary.setText(str(s))


# ---------------------------------------------------------------- 状态栏

class StatusBar(QWidget):
    """底部状态栏：左侧任务状态，右侧推理设备胶囊（带轻量活动指示）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusBar")
        h = QHBoxLayout(self)
        h.setContentsMargins(2, 2, 2, 0)
        h.setSpacing(10)

        self.lbl_state = QLabel("就绪")
        self.lbl_state.setObjectName("statusText")
        h.addWidget(self.lbl_state, 1)

        self.lbl_pct = QLabel("")
        self.lbl_pct.setObjectName("statusText")
        h.addWidget(self.lbl_pct)

        self.lbl_device = QLabel("设备检测中")
        self.lbl_device.setObjectName("pill")
        h.addWidget(self.lbl_device)

        self._spin_frames = ["◐", "◓", "◑", "◒"]
        self._spin_i = 0
        self._spin_timer = QTimer(self)
        self._spin_timer.timeout.connect(self._spin_tick)
        self._spinning = False

    def _spin_tick(self):
        self._spin_i = (self._spin_i + 1) % len(self._spin_frames)
        base = getattr(self, "_spin_base", "处理中")
        self.lbl_state.setText(f"{self._spin_frames[self._spin_i]}  {base}")

    def set_busy(self, text):
        self._spin_base = text
        self._spinning = True
        self.lbl_state.setText(f"{self._spin_frames[0]}  {text}")
        self._spin_timer.start(160)

    def set_idle(self, text="就绪"):
        self._spin_timer.stop()
        self._spinning = False
        self.lbl_state.setText(text)

    def set_progress(self, pct, extra=""):
        self.lbl_pct.setText(f"{pct}% {extra}".strip() if pct is not None else extra)

    def set_device(self, dev, pending=False):
        if pending:
            self.lbl_device.setObjectName("pill")
            self.lbl_device.setText("◌ 设备检测中")
        elif dev == "gpu":
            self.lbl_device.setObjectName("pillOk")
            self.lbl_device.setText("GPU 加速已启用")
        else:
            self.lbl_device.setObjectName("pillWarn")
            self.lbl_device.setText("CPU 运行")
        self.lbl_device.style().unpolish(self.lbl_device)
        self.lbl_device.style().polish(self.lbl_device)


def now_hms():
    return time.strftime("%H:%M:%S")
