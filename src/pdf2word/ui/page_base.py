"""工具页基类：卡片分区布局 + 主按钮状态机 + 进度反馈 + 折叠日志。

五个模块（对应 UI 方案 1.1）：
    文件上传卡片 → 参数配置卡片 → 操作行（主按钮 + 进度）→ 日志卡片
（顶部导航区由 MainWindow 的 QTabWidget 承担。）

子类只需：
    FILE_EXTS / RUN_TEXT / EMPTY_TITLE 等类属性
    _build_options(card_layout)   参数区控件
    _make_task()                  返回 job(task) 或抛 ValueError 提示用户
"""

import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .common import TaskThread
from .dialog_failure import ACTION_LOG, ACTION_RETRY, FailureDialog
from .widgets import FileList, LogPanel, make_card


class BasePage(QWidget):
    FILE_EXTS = ()
    RUN_TEXT = "开始处理"
    BUSY_TEXT = "处理中"
    EMPTY_TITLE = "拖拽文件到此处"
    EMPTY_HINT = "或点击下方「添加文件」"
    #: 失败后是否允许「只重试失败的文件」（合并是整体操作，设为 False）
    CAN_RETRY_SUBSET = True
    #: 任务开始多久后弹进度窗。低于该时长的任务不弹，避免窗口闪一下
    PROGRESS_DIALOG_DELAY_MS = 1000

    #: 页面向主窗口请求（Toast / 状态栏）
    toast_requested = Signal(str, bool)
    busy_changed = Signal(bool, str)
    progress_changed = Signal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.task = None
        self._failed = []  # [(路径或名称, 原因)]，由 note_failed() 在任务中累积
        self._prog_dlg = None  # 长任务的进度弹窗（1 秒后才出现）
        self._run_count = 0
        self._spin_frames = ["◐", "◓", "◑", "◒"]
        self._spin_i = 0
        self._spin_timer = QTimer(self)
        self._spin_timer.timeout.connect(self._tick_spin)
        self._build()

    # ---------------------------------------------------------------- 布局
    def _build(self):
        c = theme.now_palette()
        self._c = c
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 4, 0, 0)
        root.setSpacing(12)

        # ---- 1. 文件上传卡片 ----
        card_files = make_card("添加文件", c)
        vf = card_files.body
        vf.setSpacing(10)

        self.list = FileList(self.FILE_EXTS, self.EMPTY_TITLE, self.EMPTY_HINT,
                             show_pages=bool(self.FILE_EXTS) and self.FILE_EXTS[0] in
                             ("pdf", "docx", "xlsx", "pptx"))
        self.list.setMinimumHeight(150)
        self.list.files_changed.connect(self._on_files_changed)
        vf.addWidget(self.list)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.btn_add = QPushButton("添加文件")
        self.btn_add.clicked.connect(self.on_add)
        bar.addWidget(self.btn_add)

        self.list_bar = bar  # 子类可在此插入调序等列表操作按钮

        self.btn_clear = QPushButton("清空")
        self.btn_clear.setObjectName("link")
        self.btn_clear.clicked.connect(self.list.clear_all)
        bar.addWidget(self.btn_clear)
        bar.addStretch(1)

        self.lbl_count = QLabel("共 0 个文件")
        self.lbl_count.setObjectName("hint")
        bar.addWidget(self.lbl_count)
        vf.addLayout(bar)
        root.addWidget(card_files, 3)

        # ---- 2. 参数配置卡片 ----
        self.card_opts = make_card("参数设置", c)
        self.opt_layout = self.card_opts.body
        self.opt_layout.setSpacing(10)
        self._build_options(self.opt_layout)
        root.addWidget(self.card_opts)

        # ---- 3. 操作行 ----
        act = QHBoxLayout()
        act.setSpacing(12)
        self.btn_run = QPushButton(self.RUN_TEXT)
        self.btn_run.setObjectName("primary")
        self.btn_run.setCursor(Qt.PointingHandCursor)
        self.btn_run.setFixedHeight(44)
        self.btn_run.setMinimumWidth(160)
        self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self.on_run)
        act.addWidget(self.btn_run)

        prog_col = QVBoxLayout()
        prog_col.setSpacing(4)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        prog_col.addWidget(self.progress)
        self.lbl_progress = QLabel("等待开始")
        self.lbl_progress.setObjectName("hint")
        prog_col.addWidget(self.lbl_progress)
        act.addLayout(prog_col, 1)
        root.addLayout(act)

        # ---- 4. 日志卡片（默认折叠，高度随展开状态变化）----
        self.card_log = make_card("处理日志", c)
        self.log_panel = LogPanel(self._ready_summary(), self)
        self.card_log.body.addWidget(self.log_panel)
        self.log_panel.expanded_changed.connect(self._on_log_toggle)
        root.addWidget(self.card_log)
        self._on_log_toggle(False)

    def _on_log_toggle(self, expanded):
        self.card_log.setMaximumHeight(460 if expanded else 104)

    def _ready_summary(self):
        return "就绪。添加文件后点击「%s」。" % self.RUN_TEXT

    def _build_options(self, layout):
        """子类填充参数区。"""

    # ---------------------------------------------------------------- 交互
    def on_add(self):
        from PySide6.QtWidgets import QFileDialog

        pattern = " ".join(f"*.{e}" for e in self.FILE_EXTS)
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择文件", "", f"支持的文件 ({pattern})"
        )
        if files:
            import os

            self.list.add_paths([os.path.normpath(f) for f in files])

    def _on_files_changed(self, paths):
        n = len(paths)
        self.lbl_count.setText(f"共 {n} 个文件" if n else "共 0 个文件")
        if self.task and self.task.isRunning():
            return
        self.btn_run.setEnabled(n > 0)
        if n == 0:
            self.lbl_progress.setText("等待开始")
            self.progress.setValue(0)

    def on_run(self):
        if self.task and self.task.isRunning():
            self.task.ask_stop()
            self.btn_run.setText("正在停止…")
            self.btn_run.setEnabled(False)
            return
        self._start()

    def note_failed(self, path, reason):
        """任务中记录一个失败文件（供失败弹窗与「只重试这些」使用）。"""
        self._failed.append((path, str(reason)))

    def _start(self, subset=None):
        """subset 非空时只处理这些文件（用于失败重试）。"""
        paths = list(subset) if subset else self.list.paths()
        if not paths:
            self.toast_requested.emit("请先添加文件", False)
            return
        self._failed = []
        try:
            job = self._make_task(list(subset) if subset else None)
        except ValueError as e:
            self.toast_requested.emit(str(e), False)
            return
        if job is None:
            return
        self.task = TaskThread(job, self)
        self.task.sig_log.connect(self.log_panel.log)
        self.task.sig_percent.connect(self._on_percent)
        self.task.sig_done.connect(self._on_done)
        self.log_panel.expand()
        self.log_panel.log("")
        self.log_panel.log(f"━━ {time.strftime('%H:%M:%S')} 开始 {self.RUN_TEXT} ━━")
        self.btn_run.setEnabled(True)
        self.btn_run.setText(f"◐  {self.BUSY_TEXT}…")
        self._spin_i = 0
        self._spin_timer.start(160)
        self.progress.setValue(0)
        self.busy_changed.emit(True, f"{self.BUSY_TEXT}…")
        self.progress_changed.emit(0, "")
        self.task.start()

        # 延迟弹进度窗：1 秒内跑完的任务不会看到任何弹窗
        self._prog_dlg = None
        self._run_count = len(paths)
        QTimer.singleShot(self.PROGRESS_DIALOG_DELAY_MS, self._maybe_show_progress)

    # ---- 长任务进度弹窗 ----
    def _dialog_subject(self):
        n = self._run_count or len(self.list.paths())
        return f"共 {n} 个文件，正在处理…" if n else "正在处理…"

    def _maybe_show_progress(self):
        """延迟回调：任务还在跑才弹窗。"""
        if self._prog_dlg is not None:
            return
        if not (self.task and self.task.isRunning()):
            return  # 1 秒内已完成，不弹
        from .dialog_progress import ProgressDialog

        dlg = ProgressDialog(self, f"正在{self.BUSY_TEXT}", self._dialog_subject())
        dlg.cancel_requested.connect(self._cancel_from_dialog)
        dlg.set_progress(self.progress.value(), self._progress_extra())
        dlg.show()
        dlg.raise_()
        self._prog_dlg = dlg

    def _cancel_from_dialog(self):
        if self.task and self.task.isRunning():
            self.task.ask_stop()
            self.btn_run.setText("正在停止…")
            self.btn_run.setEnabled(False)
            self.lbl_progress.setText("正在停止，等待当前文件结束…")

    def _tick_spin(self):
        self._spin_i = (self._spin_i + 1) % len(self._spin_frames)
        self.btn_run.setText(f"{self._spin_frames[self._spin_i]}  {self.BUSY_TEXT}…")

    def _on_percent(self, pct):
        self.progress.setValue(pct)
        extra = self._progress_extra()
        self.lbl_progress.setText(f"进度 {pct}%" + (f" · {extra}" if extra else ""))
        self.progress_changed.emit(pct, extra)
        if self._prog_dlg is not None:
            self._prog_dlg.set_progress(pct, extra)

    def _progress_extra(self):
        """子类可返回「第 1/2 个文件」这类附加信息。"""
        return ""

    def _on_done(self, ok, msg):
        self._spin_timer.stop()
        if self._prog_dlg is not None:
            self._prog_dlg.finish()
            self._prog_dlg = None
        self.btn_run.setText(self.RUN_TEXT)
        self.btn_run.setEnabled(bool(self.list.paths()))
        self.busy_changed.emit(False, "就绪")
        failed = list(self._failed)

        if failed or not ok:
            # 有失败才弹窗（全部成功只走 Toast，避免打断）
            self.lbl_progress.setText(
                f"{len(failed)} 个未完成，可单独重试" if failed else "已中断"
            )
            self.log_panel.set_summary("! " + (msg or "处理未完成"))
            self.progress_changed.emit(100 if ok else -1, "")
            self._report_failure(failed, msg)
        else:
            self.progress.setValue(100)
            self.lbl_progress.setText("已完成")
            self.log_panel.set_summary("✓ " + (msg or "全部完成"))
            self.log_panel.log(msg or "全部完成")
            self.toast_requested.emit(msg or "处理完成", True)
            self.progress_changed.emit(100, "")

    def _report_failure(self, failed, msg):
        """弹失败报告；选「只重试」时只重跑失败的那几个文件。"""
        can_retry = bool(failed) and self.CAN_RETRY_SUBSET
        dlg = FailureDialog(self, failed, msg or "", can_retry=can_retry)
        dlg.exec()
        if dlg.action == ACTION_RETRY:
            subset = [p for p, _ in failed]
            self.log_panel.log(f"── 重试 {len(subset)} 个未完成的文件 ──")
            self._start(subset)
        elif dlg.action == ACTION_LOG:
            self.log_panel.expand()

    def is_busy(self):
        return bool(self.task and self.task.isRunning())

    def request_stop(self):
        if self.task and self.task.isRunning():
            self.task.ask_stop()
            return True
        return False


def form_grid():
    """两列表单布局（对应 UI 方案 1.3）。"""
    from PySide6.QtWidgets import QGridLayout

    g = QGridLayout()
    g.setHorizontalSpacing(18)
    g.setVerticalSpacing(10)
    g.setColumnStretch(1, 1)
    g.setColumnStretch(3, 1)
    return g
