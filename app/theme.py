# -*- coding: utf-8 -*-
"""淺色／深色主題，跟隨系統自動切換。"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

LIGHT = {
    "bg":          "#F6F6F7",
    "panel":       "#FFFFFF",
    "card":        "#FFFFFF",
    "border":      "#E4E4E7",
    "text":        "#18181B",
    "muted":       "#71717A",
    "accent":      "#18181B",
    "accent_text": "#FFFFFF",
    "hover":       "#F4F4F5",
    "field":       "#FAFAFA",
    "shadow":      QColor(0, 0, 0, 28),
    "danger":      "#DC2626",
    "overlay":     "rgba(255,255,255,0.92)",
}

DARK = {
    "bg":          "#0E0E11",
    "panel":       "#17171B",
    "card":        "#1C1C21",
    "border":      "#2A2A31",
    "text":        "#F4F4F5",
    "muted":       "#8B8B94",
    "accent":      "#F4F4F5",
    "accent_text": "#18181B",
    "hover":       "#26262C",
    "field":       "#212127",
    "shadow":      QColor(0, 0, 0, 130),
    "danger":      "#F87171",
    "overlay":     "rgba(28,28,33,0.92)",
}


def is_dark(app) -> bool:
    """先問 Qt 的系統色彩配置，問不到就用視窗底色亮度判斷。"""
    try:
        hints = app.styleHints()
        scheme = hints.colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
    except Exception:
        pass
    c = app.palette().window().color()
    return (c.red() * 299 + c.green() * 587 + c.blue() * 114) / 1000 < 128


def palette(app) -> dict:
    return DARK if is_dark(app) else LIGHT


def stylesheet(p: dict) -> str:
    return f"""
QWidget {{
    color: {p['text']};
    font-family: "Segoe UI", "Microsoft JhengHei UI", "PingFang TC", sans-serif;
    font-size: 13px;
}}
#Root {{ background: {p['bg']}; }}

/* ---- 卡片容器 ---- */
#Panel, #Card, #Sheet {{
    background: {p['panel']};
    border: 1px solid {p['border']};
    border-radius: 16px;
}}
#Card {{ background: {p['card']}; border-radius: 14px; }}

/* ---- 分頁按鈕 ---- */
#SegmentBar {{
    background: {p['field']};
    border: 1px solid {p['border']};
    border-radius: 11px;
}}
#SegmentBtn {{
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 7px 0;
    color: {p['muted']};
    font-weight: 600;
}}
#SegmentBtn:hover {{ color: {p['text']}; }}
#SegmentBtn:checked {{
    background: {p['panel']};
    color: {p['text']};
}}

/* ---- 下拉選單 ---- */
QComboBox {{
    background: {p['field']};
    border: 1px solid {p['border']};
    border-radius: 10px;
    padding: 8px 12px;
    min-height: 20px;
}}
QComboBox:hover {{ border-color: {p['muted']}; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{
    background: {p['panel']};
    border: 1px solid {p['border']};
    border-radius: 10px;
    padding: 4px;
    outline: none;
    selection-background-color: {p['hover']};
    selection-color: {p['text']};
}}

/* ---- 文字輸入 ---- */
QPlainTextEdit, QLineEdit {{
    background: {p['field']};
    border: 1px solid {p['border']};
    border-radius: 12px;
    padding: 10px 12px;
    selection-background-color: {p['muted']};
}}
QPlainTextEdit:focus, QLineEdit:focus {{ border-color: {p['muted']}; }}

/* ---- 參數小按鈕 ---- */
#Pill {{
    background: {p['field']};
    border: 1px solid {p['border']};
    border-radius: 13px;
    padding: 5px 11px;
    color: {p['text']};
    font-size: 12px;
}}
#Pill:hover {{ background: {p['hover']}; border-color: {p['muted']}; }}
#Pill::menu-indicator {{ image: none; }}

/* ---- 主要按鈕 ---- */
#Primary {{
    background: {p['accent']};
    color: {p['accent_text']};
    border: none;
    border-radius: 12px;
    padding: 12px 20px;
    font-size: 14px;
    font-weight: 600;
}}
#Primary:hover {{ background: {p['muted']}; }}
#Primary:disabled {{ background: {p['border']}; color: {p['muted']}; }}

#Ghost {{
    background: transparent;
    border: 1px solid {p['border']};
    border-radius: 10px;
    padding: 8px 14px;
}}
#Ghost:hover {{ background: {p['hover']}; }}

/* ---- 拖曳區 ---- */
#DropZone {{
    background: {p['field']};
    border: 1px dashed {p['border']};
    border-radius: 12px;
}}
#DropZone[dragging="true"] {{
    border-color: {p['text']};
    background: {p['hover']};
}}

/* ---- 文字色階 ---- */
#Muted {{ color: {p['muted']}; }}
#Title {{ font-size: 15px; font-weight: 600; }}
#Cost {{ color: {p['muted']}; font-size: 12px; }}

/* ---- 卡片浮動按鈕 ---- */
#CardBtn {{
    background: {p['overlay']};
    border: 1px solid {p['border']};
    border-radius: 12px;
    color: {p['text']};
    font-size: 13px;
}}
#CardBtn:hover {{ background: {p['hover']}; }}
#CardBtnDanger:hover {{ color: {p['danger']}; }}

/* ---- 捲軸 ---- */
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget, QScrollArea > QWidget > QWidget {{ background: transparent; }}
QAbstractScrollArea::viewport {{ background: transparent; }}
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {p['border']}; border-radius: 5px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {p['muted']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QToolTip {{
    background: {p['panel']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 8px;
    padding: 5px 8px;
}}
"""
