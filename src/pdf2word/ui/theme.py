"""统一视觉主题（亮 / 暗两套），供全应用套用。

设计目标（v1.5）：
    - 模块化卡片：浅色卡片 + 轻阴影，替代细线分割
    - 明确的视觉层级：模块标题 14px/600 · 表单标签 13px/400 · 辅助说明 12px
    - 扁平 + 轻质感：8px 圆角、1px 细边框、无凹凸
    - 主操作渐变 + 投影；次级操作为描边或文字按钮

用法：
    from .ui.theme import apply_theme, detect_dark, palette
    apply_theme(app, dark=detect_dark())

约定（objectName）：
    card       卡片容器（配 elevated() 加阴影）
    primary    主行动按钮
    danger     危险操作
    ghost      文字/图标按钮
    hint       辅助说明文字
    pill       状态胶囊
    emptyHint  列表空状态
"""

import os
import sys

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QGraphicsDropShadowEffect


def _asset_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    cands = [os.path.join(here, "assets")]
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            cands.append(os.path.join(meipass, "pdf2word", "ui", "assets"))
        exe_dir = os.path.dirname(sys.executable)
        cands.append(os.path.join(exe_dir, "_internal", "pdf2word", "ui", "assets"))
    for c in cands:
        if os.path.isdir(c):
            return c
    return cands[0]


_ASSETS = _asset_dir().replace("\\", "/")


def _url(name):
    return f'url("{_ASSETS}/{name}")'


# ---------------------------------------------------------------- 配色

LIGHT = {
    "bg": "#f3f4f7",
    "card": "#ffffff",
    "card_alt": "#fafbfd",
    "hover": "#eef1f6",
    "pressed": "#e5e9f1",
    "border": "#e6e8ee",
    "border_strong": "#d5dae4",
    "text": "#1d2230",
    "text_sub": "#5f6673",
    "text_faint": "#98a1b0",
    "accent": "#2f6bff",
    "accent_hover": "#4a7dff",
    "accent_press": "#2456d6",
    "accent_soft": "#e9efff",
    "accent_text": "#1d4ed8",
    "danger": "#e5484d",
    "danger_soft": "#fdecec",
    "ok": "#12946a",
    "ok_soft": "#e6f6f0",
    "warn": "#b7791f",
    "log_bg": "#fafbfd",
    "scroll": "#cdd3de",
    "scroll_hover": "#b6bdcb",
    "shadow": "#1d2230",
    "tab_track": "#eceef3",
    "disabled_bg": "#b9c8ea",
}

DARK = {
    "bg": "#15181f",
    "card": "#1e222b",
    "card_alt": "#232833",
    "hover": "#2a3040",
    "pressed": "#333a4b",
    "border": "#2b3140",
    "border_strong": "#3a4254",
    "text": "#e8ecf4",
    "text_sub": "#a2acbd",
    "text_faint": "#6d7789",
    "accent": "#4d84ff",
    "accent_hover": "#6a99ff",
    "accent_press": "#3a6fe0",
    "accent_soft": "#243252",
    "accent_text": "#a9c2ff",
    "danger": "#f16b6f",
    "danger_soft": "#3a2326",
    "ok": "#3ecf9a",
    "ok_soft": "#1e3a32",
    "warn": "#e0b050",
    "log_bg": "#181b23",
    "scroll": "#3a4254",
    "scroll_hover": "#4b5568",
    "shadow": "#000000",
    "tab_track": "#1b1f28",
    "disabled_bg": "#33405e",
}


def palette(dark=False):
    return DARK if dark else LIGHT


def detect_dark():
    """读取 Windows 应用主题设置（AppsUseLightTheme=0 即深色）。"""
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as k:
            v, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
            return int(v) == 0
    except Exception:
        return False


# ---------------------------------------------------------------- QSS

def build_qss(c):
    return f"""
/* ================= 基础 ================= */
QWidget {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Segoe UI";
    font-size: 13px;
    color: {c['text']};
}}
QMainWindow, QDialog {{ background: {c['bg']}; }}
QToolTip {{
    background: {c['text']};
    color: {c['card']};
    border: none; border-radius: 6px; padding: 5px 8px;
}}

/* ================= 品牌区 ================= */
QWidget#brandBar, QWidget#statusBar, QWidget#tabBarWrap {{ background: transparent; }}
QLabel#appTitle {{ font-size: 18px; font-weight: 600; color: {c['text']}; }}
QLabel#appSubtitle {{ font-size: 12px; color: {c['text_faint']}; }}

/* ================= 卡片 ================= */
QFrame#card {{
    background: {c['card']};
    border: 1px solid {c['border']};
    border-radius: 12px;
}}
QLabel#cardTitle {{
    font-size: 14px;
    font-weight: 600;
    color: {c['text']};
    padding: 0;
}}

/* ================= Tab 标签栏 ================= */
QTabWidget::pane {{
    border: none;
    background: transparent;
    top: -1px;
}}
QTabWidget::tab-bar {{ left: 0; }}
QTabBar {{ qproperty-drawBase: 0; }}
QTabBar::tab {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 9px;
    padding: 8px 18px;
    margin-right: 6px;
    color: {c['text_sub']};
    font-size: 13px;
    min-height: 20px;
}}
QTabBar::tab:hover {{
    background: {c['hover']};
    color: {c['text']};
}}
QTabBar::tab:selected {{
    background: {c['accent_soft']};
    color: {c['accent_text']};
    font-weight: 600;
}}

/* ================= 按钮 ================= */
QPushButton {{
    background: {c['card']};
    color: {c['text']};
    border: 1px solid {c['border_strong']};
    border-radius: 8px;
    padding: 7px 14px;
    min-height: 18px;
}}
QPushButton:hover {{ background: {c['hover']}; border-color: {c['border_strong']}; }}
QPushButton:pressed {{ background: {c['pressed']}; }}
QPushButton:disabled {{ color: {c['text_faint']}; background: {c['card_alt']}; border-color: {c['border']}; }}

QPushButton#primary {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {c['accent_hover']}, stop:1 {c['accent']});
    color: #ffffff;
    border: 1px solid {c['accent']};
    border-radius: 10px;
    padding: 10px 26px;
    font-size: 14px;
    font-weight: 600;
}}
QPushButton#primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #6a99ff, stop:1 {c['accent_hover']});
}}
QPushButton#primary:pressed {{
    background: {c['accent_press']};
    padding-top: 11px; padding-bottom: 9px;
}}
QPushButton#primary:disabled {{
    background: {c['disabled_bg']};
    border-color: {c['disabled_bg']};
    color: {c['card']};
}}

QPushButton#ghost {{
    background: transparent;
    border: 1px solid transparent;
    color: {c['text_sub']};
    padding: 6px 10px;
    border-radius: 8px;
}}
QPushButton#ghost:hover {{ background: {c['hover']}; color: {c['text']}; }}

QPushButton#link {{
    background: transparent; border: none;
    color: {c['text_sub']}; padding: 2px 4px; border-radius: 6px;
    font-size: 12px;
}}
QPushButton#link:hover {{ color: {c['accent']}; background: {c['hover']}; }}

/* ================= 输入控件 ================= */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {c['card_alt']};
    border: 1px solid {c['border_strong']};
    border-radius: 8px;
    padding: 6px 10px;
    min-height: 18px;
    color: {c['text']};
    selection-background-color: {c['accent']};
    selection-color: #ffffff;
}}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover {{ border-color: {c['text_faint']}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {c['accent']};
    background: {c['card']};
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{
    background: {c['card_alt']}; color: {c['text_faint']};
}}
QLineEdit[readOnly="true"] {{ color: {c['text_sub']}; }}

QComboBox::drop-down {{
    subcontrol-origin: padding; subcontrol-position: center right;
    border: none; width: 22px;
}}
QComboBox::down-arrow {{ image: {_url("chevron-down.png")}; width: 12px; height: 12px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border; subcontrol-position: top right;
    width: 18px; height: 12px; margin: 3px 3px 0 0;
    background: transparent; border: none;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border; subcontrol-position: bottom right;
    width: 18px; height: 12px; margin: 0 3px 3px 0;
    background: transparent; border: none;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: {_url("caret-up.png")}; width: 10px; height: 10px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: {_url("caret-down.png")}; width: 10px; height: 10px;
}}
QComboBox QAbstractItemView {{
    background: {c['card']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    padding: 4px; outline: none;
    selection-background-color: {c['accent_soft']};
    selection-color: {c['accent_text']};
}}
QComboBox QAbstractItemView::item {{ padding: 6px 8px; border-radius: 6px; min-height: 20px; }}

/* ================= 文件列表（可拖拽）================= */
QListWidget#dropList {{
    background: {c['card_alt']};
    border: 1.5px dashed {c['border_strong']};
    border-radius: 10px;
    padding: 6px;
    outline: none;
}}
QListWidget#dropList[dragActive="true"] {{
    border: 1.5px dashed {c['accent']};
    background: {c['accent_soft']};
}}
QListWidget#dropList[hasFiles="true"] {{
    border: 1px solid {c['border']};
    background: {c['card']};
}}
QListWidget#dropList::item {{ border-radius: 8px; color: {c['text']}; }}
QListWidget#dropList::item:hover {{ background: {c['hover']}; }}
QListWidget#dropList::item:selected {{ background: {c['accent_soft']}; }}

/* 列表项内部（自定义 widget）*/
QWidget#fileRow {{ background: transparent; }}
QLabel#fileName {{ font-size: 13px; color: {c['text']}; }}
QLabel#fileMeta {{ font-size: 11.5px; color: {c['text_faint']}; }}
QPushButton#rowRemove {{
    background: transparent; border: none;
    color: {c['text_faint']};
    border-radius: 6px; padding: 2px 6px; font-size: 13px;
}}
QPushButton#rowRemove:hover {{ background: {c['danger_soft']}; color: {c['danger']}; }}
QLabel#emptyTitle {{ font-size: 13px; color: {c['text_sub']}; }}
QLabel#emptyHint {{ font-size: 12px; color: {c['text_faint']}; }}

/* ================= 日志 ================= */
QPlainTextEdit {{
    background: {c['log_bg']};
    border: 1px solid {c['border']};
    border-radius: 10px;
    padding: 8px;
    font-family: "Cascadia Mono", "Consolas", "Courier New";
    font-size: 12px;
    color: {c['text_sub']};
    selection-background-color: {c['accent_soft']};
}}

/* ================= 进度条 ================= */
QProgressBar {{
    background: {c['border_strong']};
    border: none; border-radius: 5px;
    height: 10px; max-height: 10px;
    text-align: center; color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {c['accent']}, stop:1 {c['accent_hover']});
    border-radius: 5px;
}}

/* ================= 复选 ================= */
QCheckBox {{ spacing: 8px; color: {c['text']}; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border-radius: 4px;
    border: 1px solid {c['border_strong']};
    background: {c['card']};
}}
QCheckBox::indicator:hover {{ border-color: {c['accent']}; }}
QCheckBox::indicator:checked {{
    background: {c['accent']};
    border: 1px solid {c['accent']};
    image: {_url("check-white.png")};
}}
QCheckBox::indicator:disabled {{
    background: {c['card_alt']};
    border-color: {c['border']};
}}

/* ================= 胶囊 / 文本 ================= */
QLabel#pill {{
    background: {c['hover']};
    color: {c['text_sub']};
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 12px;
}}
QLabel#pillOk {{ background: {c['ok_soft']}; color: {c['ok']}; border-radius: 10px; padding: 3px 10px; font-size: 12px; }}
QLabel#pillWarn {{ background: {c['accent_soft']}; color: {c['accent_text']}; border-radius: 10px; padding: 3px 10px; font-size: 12px; }}
QLabel#hint {{ color: {c['text_faint']}; font-size: 12px; }}
QLabel#sectionLabel {{ color: {c['text_sub']}; font-size: 13px; }}
QLabel#statusText {{ color: {c['text_sub']}; font-size: 12px; }}
QFrame#divider {{ background: {c['border']}; max-height: 1px; border: none; }}

/* ================= 菜单 ================= */
QMenuBar {{ background: transparent; }}
QMenuBar::item {{ background: transparent; padding: 6px 11px; border-radius: 7px; color: {c['text_sub']}; }}
QMenuBar::item:selected {{ background: {c['hover']}; color: {c['text']}; }}
QMenu {{
    background: {c['card']};
    border: 1px solid {c['border']};
    border-radius: 10px; padding: 6px;
}}
QMenu::item {{ padding: 7px 26px 7px 14px; border-radius: 7px; color: {c['text']}; }}
QMenu::item:selected {{ background: {c['accent_soft']}; color: {c['accent_text']}; }}
QMenu::separator {{ height: 1px; background: {c['border']}; margin: 5px 8px; }}

/* ================= 滚动条 ================= */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px 4px 0; }}
QScrollBar::handle:vertical {{ background: {c['scroll']}; border-radius: 5px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {c['scroll_hover']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0 4px 2px 4px; }}
QScrollBar::handle:horizontal {{ background: {c['scroll']}; border-radius: 5px; min-width: 28px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ================= Toast ================= */
QFrame#toast {{
    background: {c['card']};
    border: 1px solid {c['border']};
    border-radius: 10px;
}}
QLabel#toastIconOk {{ color: {c['ok']}; font-size: 15px; font-weight: 700; }}
QLabel#toastIconErr {{ color: {c['danger']}; font-size: 15px; font-weight: 700; }}
QLabel#toastText {{ font-size: 13px; color: {c['text']}; }}
"""


def apply_theme(app, dark=False):
    """套用主题。必须在创建任何窗口之前调用。"""
    c = palette(dark)
    app.setStyle("Fusion")
    f = QFont()
    if sys.platform == "win32":
        f.setFamily("Microsoft YaHei UI")
    f.setPointSize(9)
    app.setFont(f)
    app.setStyleSheet(build_qss(c))
    app.setProperty("darkMode", bool(dark))
    return c


def current_palette(app):
    return palette(bool(app.property("darkMode")))


def is_dark():
    """当前是否为深色模式。

    注意：darkMode 是设在 QApplication 上的动态属性，控件用 self.window().property()
    取不到（QObject.property 不向上查找），必须走 QApplication.instance()。
    """
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    return bool(app.property("darkMode")) if app else False


def now_palette():
    return palette(is_dark())


def elevated(widget, c, blur=18, dy=2, alpha=26):
    """给卡片加轻投影（QSS 不支持 box-shadow）。"""
    eff = QGraphicsDropShadowEffect(widget)
    col = QColor(c["shadow"])
    col.setAlpha(alpha)
    eff.setColor(col)
    eff.setBlurRadius(blur)
    eff.setOffset(0, dy)
    widget.setGraphicsEffect(eff)
    return eff
