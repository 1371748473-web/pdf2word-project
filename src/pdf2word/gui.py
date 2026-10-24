"""主窗口：品牌区 + Tab 功能导航 + 底部状态栏 + Toast。

交互结构（v1.5）：
    顶部：应用图标 / 标题 / 副标题 / 「⋯」次级菜单（设置、GPU、关于）
    中部：Tab 标签栏（PDF 转 Word · PDF 合并 · PDF 转图片 · Office 转 PDF）
    底部：状态栏（任务状态 + 进度百分比 + 推理设备胶囊）
    浮层：右上角 Toast 结果提示
"""

import os
import sys
import traceback

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .envsetup import ensure_env
from .ui import theme
from .ui.page_image import ImagePage
from .ui.page_merge import MergePage
from .ui.page_office import OfficePage
from .ui.page_word import WordPage
from .ui.widgets import StatusBar, Toast

APP_TITLE = "PDF 工具箱"
APP_VERSION = "1.5"


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def icon_path():
    p = os.path.join(app_dir(), "app_icon.ico")
    return p if os.path.isfile(p) else None


class DeviceProbe(QThread):
    """后台探测推理设备（nvidia-smi 约 0.4 s），避免阻塞窗口显示。"""

    sig_device = Signal(str)

    def run(self):
        from .envsetup import ensure_device

        try:
            dev = ensure_device()
        except Exception:
            dev = "cpu"
        self.sig_device.emit(dev)


class GpuWorker(QThread):
    """后台线程：下载并安装 GPU 加速支持。"""

    sig_log = Signal(str)
    sig_percent = Signal(int)
    sig_done = Signal(bool)

    def __init__(self):
        super().__init__()
        self._installer = None

    def ask_stop(self):
        if self._installer:
            self._installer.cancel()

    def run(self):
        from .gpu_installer import GpuInstaller

        self._installer = GpuInstaller(
            progress=lambda msg, pct=0: (
                self.sig_log.emit(msg),
                self.sig_percent.emit(pct) if pct else None,
            )
        )
        try:
            ok = self._installer.install()
        except Exception as e:  # noqa: BLE001
            self.sig_log.emit(f"[错误] {e}")
            ok = False
        self.sig_done.emit(ok)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(980, 800)
        ip = icon_path()
        if ip:
            self.setWindowIcon(QIcon(ip))

        self.gpu_worker = None
        self.device_probe = None
        self._c = theme.current_palette(QApplication.instance())
        self._build_ui()

    # ---------------------------------------------------------------- 布局
    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 12, 20, 8)
        root.setSpacing(10)

        self._build_brand(root)
        self._build_tabs(root)
        self._build_status(root)

        self.setCentralWidget(central)
        self._build_menu()
        self.toast = Toast(self)

    def _build_brand(self, root):
        bar = QWidget()
        bar.setObjectName("brandBar")
        h = QHBoxLayout(bar)
        h.setContentsMargins(2, 2, 2, 0)
        h.setSpacing(12)

        ip = icon_path()
        if ip:
            lbl_icon = QLabel()
            lbl_icon.setPixmap(QIcon(ip).pixmap(32, 32))
            lbl_icon.setFixedSize(32, 32)
            h.addWidget(lbl_icon)

        col = QVBoxLayout()
        col.setSpacing(0)
        lbl_title = QLabel(APP_TITLE)
        lbl_title.setObjectName("appTitle")
        lbl_sub = QLabel("转换 · 合并 · 转图片 · Office 转 PDF　一站式处理")
        lbl_sub.setObjectName("appSubtitle")
        col.addWidget(lbl_title)
        col.addWidget(lbl_sub)
        h.addLayout(col)
        h.addStretch(1)

        self.btn_more = QPushButton("⋯")
        self.btn_more.setObjectName("ghost")
        self.btn_more.setCursor(Qt.PointingHandCursor)
        self.btn_more.setFixedSize(32, 32)
        self.btn_more.setToolTip("设置与更多功能")
        self.btn_more.clicked.connect(self._show_more_menu)
        h.addWidget(self.btn_more)

        root.addWidget(bar)

    def _build_tabs(self, root):
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabBar().setDrawBase(False)

        # 懒加载：只构建当前页，其余 Tab 先放占位控件，首次切换时才创建。
        # 4 个页面全部预建会让 Qt 首次 polish 的耗时翻倍（实测 0.65 s → 1.5 s）。
        self._factories = (WordPage, MergePage, ImagePage, OfficePage)
        self._titles = ("PDF 转 Word", "PDF 合并", "PDF 转图片", "Office 转 PDF")
        self._page_names = ("word", "merge", "image", "office")
        self._pages = [None] * len(self._factories)

        for title in self._titles:
            self.tabs.addTab(QWidget(), title)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self.tabs, 1)

        self.page_word = self.page(0)

    def page(self, idx):
        """取第 idx 页，必要时先构建。"""
        page = self._pages[idx]
        if page is not None:
            return page
        page = self._factories[idx]()
        page.toast_requested.connect(self.on_toast)
        page.busy_changed.connect(self._on_busy)
        page.progress_changed.connect(self._on_progress)

        holder = self.tabs.widget(idx)
        self.tabs.blockSignals(True)
        self.tabs.removeTab(idx)
        self.tabs.insertTab(idx, page, self._titles[idx])
        self.tabs.setCurrentIndex(idx)
        self.tabs.blockSignals(False)
        if holder is not None:
            holder.deleteLater()

        self._pages[idx] = page
        setattr(self, "page_" + self._page_names[idx], page)
        return page

    def created_pages(self):
        return [p for p in self._pages if p is not None]

    def _build_status(self, root):
        self.status = StatusBar()
        self.status.set_device("", pending=True)
        root.addWidget(self.status)

    def _build_menu(self):
        self.menu_more = QMenu(self)

        self.act_dark = QAction("深色模式", self, checkable=True)
        self.act_dark.setChecked(bool(QApplication.instance().property("darkMode")))
        self.act_dark.triggered.connect(self.toggle_dark)
        self.menu_more.addAction(self.act_dark)

        self.menu_more.addSeparator()

        self.act_download_gpu = QAction("下载 GPU 加速支持…", self)
        self.act_download_gpu.triggered.connect(self.on_download_gpu)
        self.menu_more.addAction(self.act_download_gpu)

        self.act_check_gpu = QAction("检查 GPU 状态", self)
        self.act_check_gpu.triggered.connect(self.on_check_gpu)
        self.menu_more.addAction(self.act_check_gpu)

        self.act_uninstall_gpu = QAction("卸载 GPU 支持…", self)
        self.act_uninstall_gpu.triggered.connect(self.on_uninstall_gpu)
        self.menu_more.addAction(self.act_uninstall_gpu)

        self.menu_more.addSeparator()
        self.act_about = QAction("关于", self)
        self.act_about.triggered.connect(self.on_about)
        self.menu_more.addAction(self.act_about)

    def _show_more_menu(self):
        b = self.btn_more
        self.menu_more.exec(b.mapToGlobal(b.rect().bottomLeft()))

    # ---------------------------------------------------------------- 反馈
    def on_toast(self, text, ok):
        self.toast.show_message(text, ok)

    def _on_busy(self, busy, text):
        if busy:
            self.status.set_busy(text)
        else:
            self.status.set_idle()
            self.status.set_progress(0, "")

    def _on_progress(self, pct, extra):
        if pct is None or pct < 0:
            return
        self.status.set_progress(pct, extra)

    def _on_tab_changed(self, idx):
        if idx < 0:
            return
        page = self.page(idx)
        if page is None:
            return
        if page.is_busy():
            self.status.set_busy(page.BUSY_TEXT + "…")
        else:
            self.status.set_idle()
        self.status.set_progress(0, "")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "toast") and self.toast.isVisible():
            self.toast._place()

    # ---------------------------------------------------------------- 设备
    def probe_device_async(self):
        self.device_probe = DeviceProbe(self)
        self.device_probe.sig_device.connect(self.on_device_ready)
        self.device_probe.start()

    def on_device_ready(self, dev):
        self.status.set_device(dev)
        self.page_word.log_panel.log(f"推理设备: {'GPU (CUDA)' if dev == 'gpu' else 'CPU'}")

    # ---------------------------------------------------------------- 主题
    def toggle_dark(self, checked):
        app = QApplication.instance()
        theme.apply_theme(app, dark=bool(checked))
        self._c = theme.palette(bool(checked))
        self._restyle()

    def _restyle(self):
        from .ui.widgets import Card, FileRow

        c = self._c
        for card in self.findChildren(Card):
            card.setGraphicsEffect(None)
            theme.elevated(card, c, blur=16, dy=2, alpha=22)
        for w in self.findChildren(QWidget):
            w.style().unpolish(w)
            w.style().polish(w)
        for row in self.findChildren(FileRow):
            row.repaint_icon()
        for page in self.created_pages():
            page.list.viewport().update()

    # ---------------------------------------------------------------- 菜单动作
    def on_about(self):
        QMessageBox.information(
            self, "关于",
            f"{APP_TITLE}  v{APP_VERSION}\n\n"
            "PDF 转 Word · PDF 合并 · PDF 转图片 · Office 转 PDF\n\n"
            "文字版 PDF 精准转换；扫描件自动识别文字并还原排版。",
        )

    def on_download_gpu(self):
        if self.gpu_worker and self.gpu_worker.isRunning():
            self.gpu_worker.ask_stop()
            self.act_download_gpu.setText("正在取消…")
            self.act_download_gpu.setEnabled(False)
            return

        from .gpu_installer import check_nvidia_gpu, is_gpu_support_installed

        if is_gpu_support_installed():
            r = QMessageBox.question(
                self, APP_TITLE, "GPU 加速支持已安装，是否重新下载并覆盖安装？",
                QMessageBox.Yes | QMessageBox.No,
            )
            if r != QMessageBox.Yes:
                return

        gpu = check_nvidia_gpu()
        info = "将下载以下组件（约 1.5 GB）：\n\n"
        info += "  • NVIDIA CUDA 运行时库\n  • PaddlePaddle GPU 推理引擎\n\n"
        if gpu:
            info += f"检测到 GPU：{gpu}\n安装后扫描页识别速度预计提升 4-5 倍。\n\n"
        else:
            info += "[警告] 未检测到 NVIDIA GPU，安装后仍将使用 CPU。\n\n"
        info += "支持断点重试，网络中断后可重新点击下载。\n\n是否开始下载？"

        if QMessageBox.question(self, APP_TITLE, info,
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return

        self.gpu_worker = GpuWorker()
        self.gpu_worker.sig_log.connect(lambda s: self.page_word.log_panel.log(s))
        self.gpu_worker.sig_done.connect(self.on_gpu_done)
        self.act_download_gpu.setText("取消下载")
        self.status.set_busy("下载 GPU 加速支持…")
        self.gpu_worker.start()

    def on_gpu_done(self, ok):
        self.act_download_gpu.setText("下载 GPU 加速支持…")
        self.act_download_gpu.setEnabled(True)
        self.status.set_idle()
        if ok:
            self.status.set_device("gpu")
            QMessageBox.information(
                self, APP_TITLE, "GPU 加速支持安装成功！\n\n请重新启动程序以启用 GPU 加速。"
            )
        else:
            QMessageBox.warning(
                self, APP_TITLE,
                "GPU 支持安装未完成，请查看「PDF 转 Word」页的详细日志。",
            )

    def on_check_gpu(self):
        from .gpu_installer import check_nvidia_gpu, is_gpu_support_installed

        gpu = check_nvidia_gpu()
        installed = is_gpu_support_installed()
        device = os.environ.get("PDF2WORD_DEVICE", "cpu")

        info = "GPU 状态检查\n\n"
        info += f"  NVIDIA 显卡：{gpu or '未检测到'}\n"
        info += f"  GPU 支持包：{'已安装' if installed else '未安装'}\n"
        info += f"  当前推理设备：{'GPU (CUDA)' if device == 'gpu' else 'CPU'}\n"
        if not gpu:
            info += "\n[提示] 未检测到 NVIDIA 显卡，无法使用 GPU 加速。"
        elif not installed:
            info += "\n[提示] GPU 支持包未安装，可通过「⋯ → 下载 GPU 加速支持」安装。"
        elif device == "cpu":
            info += "\n[提示] GPU 支持已安装但当前使用 CPU，请重启程序。"
        else:
            info += "\n[OK] GPU 加速已启用。"
        QMessageBox.information(self, APP_TITLE, info)

    def on_uninstall_gpu(self):
        from .gpu_installer import GpuInstaller, is_gpu_support_installed

        if not is_gpu_support_installed():
            QMessageBox.information(self, APP_TITLE, "GPU 支持包未安装，无需卸载。")
            return
        if QMessageBox.question(
            self, APP_TITLE,
            "确定卸载 GPU 加速支持？\n\n卸载后程序将恢复为 CPU 模式，扫描页识别会变慢。",
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        installer = GpuInstaller(progress=lambda msg, pct=0: self.page_word.log_panel.log(msg))
        try:
            installer.uninstall()
            QMessageBox.information(self, APP_TITLE,
                                    "GPU 支持已卸载。\n请重新启动程序以恢复 CPU 模式。")
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, APP_TITLE, f"卸载失败：{e}")

    # ---------------------------------------------------------------- 关闭
    def closeEvent(self, e):
        running = [p for p in self.created_pages() if p.is_busy()]
        if running:
            r = QMessageBox.question(
                self, APP_TITLE, "仍有任务在进行，确定退出吗？",
                QMessageBox.Yes | QMessageBox.No,
            )
            if r != QMessageBox.Yes:
                e.ignore()
                return
            for p in running:
                p.request_stop()
                if p.task:
                    p.task.wait(3000)
        if self.gpu_worker and self.gpu_worker.isRunning():
            self.gpu_worker.ask_stop()
            self.gpu_worker.wait(3000)
        if self.device_probe and self.device_probe.isRunning():
            self.device_probe.wait(1500)
        e.accept()


def main():
    # fast=True：只做零成本初始化，GPU 探测改到窗口显示后的后台线程
    ensure_env(fast=True)
    app = QApplication(sys.argv)
    theme.apply_theme(app, dark=theme.detect_dark())
    win = MainWindow()
    win.show()
    win.probe_device_async()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
