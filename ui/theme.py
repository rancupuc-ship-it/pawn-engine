"""Look and feel: dark charcoal with a gold accent. Also tiny hand-drawn icons."""
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPalette, QPen, QPixmap, QPolygonF

DARK = dict(bg0="#13151a", bg1="#1a1d24", bg2="#222630", bg3="#2b303c", border="#303645",
            text="#e8eaf0", muted="#8a91a3", gold="#f2b84b", gold2="#ffd27a", teal="#4fd1b5",
            red="#ef6b6b", green="#6bd38a", blue="#6aa7ff", purple="#c792ea",
            on_gold="#1a1406", hover="#343a49", hover_b="#414860", sel="#3a3220", sel2="#2f2a1c", scroll="#3a4152",
            scroll_h="#4a5166", faint="#4a5166", off="#5d6476", play="#1f6f5c", play_h="#26856e", play_b="#2a8f77",
            stop="#8a3a3a", stop_b="#b04848", err_bg="#3a2226", err_b="#7a3a42", err_t="#ffb3b3")
LIGHT = dict(bg0="#e9ebf0", bg1="#f6f7fa", bg2="#ffffff", bg3="#e3e6ee", border="#cfd4e0",
             text="#1d2230", muted="#6a7285", gold="#e0a02a", gold2="#a86d00", teal="#16a085",
             red="#d64545", green="#2e9e5b", blue="#2f6fdb", purple="#8e4fc4",
             on_gold="#2a1d00", hover="#d9dde8", hover_b="#b9c0d1", sel="#fbe9bf", sel2="#fff3d6", scroll="#c3c9d8",
             scroll_h="#a7afc2", faint="#9aa2b6", off="#a3aabb", play="#2e9e7e", play_h="#37b08f", play_b="#2a8f77",
             stop="#d64545", stop_b="#b03030", err_bg="#fde8ea", err_b="#e29aa2", err_t="#a12b36")
C = dict(DARK)

QSS = """
* { outline: 0; }
QWidget { background: %(bg1)s; color: %(text)s; font-size: 13px; }
QMainWindow, QDialog { background: %(bg0)s; }
QLabel { background: transparent; }
QLabel[muted="true"] { color: %(muted)s; }
QLabel[h1="true"] { font-size: 26px; font-weight: 700; }
QLabel[h2="true"] { font-size: 15px; font-weight: 700; }
QToolTip { background: %(bg3)s; color: %(text)s; border: 1px solid %(border)s; padding: 4px 6px; }

QMenuBar { background: %(bg0)s; padding: 2px 6px; }
QMenuBar::item { background: transparent; padding: 5px 10px; border-radius: 5px; }
QMenuBar::item:selected { background: %(bg3)s; }
QMenu { background: %(bg2)s; border: 1px solid %(border)s; padding: 5px; border-radius: 8px; }
QMenu::item { padding: 6px 26px 6px 12px; border-radius: 5px; }
QMenu::item:selected { background: %(gold)s; color: %(on_gold)s; }
QMenu::item:disabled { color: %(muted)s; }
QMenu::separator { height: 1px; background: %(border)s; margin: 5px 6px; }

QToolBar { background: %(bg0)s; border: none; border-bottom: 1px solid %(border)s; spacing: 6px; padding: 6px 10px; }
QToolBar QLabel { color: %(muted)s; }

QPushButton { background: %(bg3)s; border: 1px solid %(border)s; border-radius: 8px; padding: 7px 16px; }
QPushButton:hover { background: %(hover)s; border-color: %(hover_b)s; }
QPushButton:pressed { background: %(bg2)s; }
QPushButton:disabled { color: %(off)s; background: %(bg2)s; }
QPushButton[primary="true"] { background: %(gold)s; color: %(on_gold)s; border: 1px solid %(gold)s; font-weight: 700; }
QPushButton[primary="true"]:hover { background: %(gold2)s; }
QPushButton[big="true"] { padding: 11px 18px; font-size: 14px; border-radius: 9px; }
QPushButton[play="true"] { background: %(play)s; border-color: %(play_b)s; padding: 6px 16px; font-weight: 700; }
QPushButton[play="true"]:hover { background: %(play_h)s; }
QPushButton[play="true"][running="true"] { background: %(stop)s; border-color: %(stop_b)s; }
QPushButton[flat="true"] { background: transparent; border: none; padding: 4px 8px; color: %(muted)s; }
QPushButton[flat="true"]:hover { color: %(text)s; background: %(bg3)s; }
QToolButton { background: transparent; border: none; padding: 4px 6px; border-radius: 6px; }
QToolButton:hover { background: %(bg3)s; }

QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: %(bg2)s; border: 1px solid %(border)s; border-radius: 6px; padding: 4px 8px;
    selection-background-color: %(gold)s; selection-color: %(on_gold)s; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: %(gold)s; }
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 0; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: %(bg2)s; border: 1px solid %(border)s; selection-background-color: %(gold)s; selection-color: %(on_gold)s; }
QCheckBox { spacing: 8px; background: transparent; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1px solid %(faint)s; background: %(bg2)s; }
QCheckBox::indicator:checked { background: %(gold)s; border-color: %(gold)s; }

QTreeWidget, QListWidget { background: %(bg1)s; border: none; alternate-background-color: %(bg1)s; }
QTreeView { show-decoration-selected: 1; }
QTreeView::branch { background: transparent; }
QTreeView::branch:selected { background: transparent; }
QTreeWidget::item { padding: 5px 3px; border-radius: 6px; }
QTreeWidget::item:focus { outline: none; border: none; }
QTreeWidget::item:hover, QListWidget::item:hover { background: %(bg2)s; }
QTreeWidget::item:selected, QListWidget::item:selected { background: %(sel)s; color: %(gold2)s; }
QListWidget[cards="true"]::item { background: %(bg2)s; border: 1px solid %(border)s; border-radius: 10px; margin: 4px 2px; }
QListWidget[cards="true"]::item:hover { border-color: %(faint)s; background: %(bg3)s; }
QListWidget[cards="true"]::item:selected { border-color: %(gold)s; background: %(sel2)s; }

QDockWidget { titlebar-close-icon: none; color: %(muted)s; }
QDockWidget::title { background: %(bg0)s; padding: 7px 12px; border-bottom: 1px solid %(border)s; font-weight: 700; }
QTabWidget::pane { border: none; border-top: 1px solid %(border)s; background: %(bg1)s; }
QTabWidget::tab-bar { left: 0px; }
QTabBar { background: %(bg0)s; }
QTabBar::tab { background: transparent; color: %(muted)s; padding: 8px 16px; border-bottom: 2px solid transparent; }
QTabBar::tab:hover { color: %(text)s; }
QTabBar::tab:selected { color: %(gold2)s; border-bottom: 2px solid %(gold)s; }
QTabBar::close-button { subcontrol-position: right; }

QScrollArea { border: none; background: %(bg1)s; }
QScrollBar:vertical { background: transparent; width: 11px; margin: 2px; }
QScrollBar::handle:vertical { background: %(scroll)s; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: %(scroll_h)s; }
QScrollBar:horizontal { background: transparent; height: 11px; margin: 2px; }
QScrollBar::handle:horizontal { background: %(scroll)s; border-radius: 4px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QFrame[card="true"] { background: %(bg2)s; border: 1px solid %(border)s; border-radius: 12px; }
QFrame[card="true"] QLabel { background: transparent; }
QFrame[banner="error"] { background: %(err_bg)s; border: 1px solid %(err_b)s; border-radius: 8px; }
QFrame[banner="error"] QLabel { color: %(err_t)s; }
QStatusBar { background: %(bg0)s; color: %(muted)s; border-top: 1px solid %(border)s; }
QStatusBar::item { border: none; }
QSplitter::handle { background: %(border)s; }
QDialogButtonBox QPushButton { min-width: 80px; }
""" 


def build_qss():
    return QSS % C


def set_mode(mode):
    """Switch the color table between 'dark' and 'light' (in place, so every module sees it)."""
    C.clear()
    C.update(LIGHT if mode == "light" else DARK)
    return "light" if mode == "light" else "dark"


def saved_mode():
    from PySide6.QtCore import QSettings
    m = QSettings("PawnEngine", "PawnEngine").value("theme", "dark")
    return "light" if m == "light" else "dark"


def apply_theme(app, mode=None):
    mode = set_mode(mode or saved_mode())
    f = QFont()
    f.setFamilies(["Segoe UI", "Inter", "Helvetica Neue", "Arial", "DejaVu Sans"])
    f.setPointSize(10)
    app.setFont(f)
    pal = app.palette()
    pal.setColor(QPalette.Highlight, QColor(C["sel"]))
    pal.setColor(QPalette.HighlightedText, QColor(C["gold2"]))
    app.setPalette(pal)
    app.setStyleSheet(build_qss())
    return mode


def mono_font(size=11):
    f = QFont()
    f.setFamilies(["Cascadia Mono", "Consolas", "JetBrains Mono", "DejaVu Sans Mono", "Courier New"])
    f.setStyleHint(QFont.Monospace)
    f.setPointSize(size)
    return f


def icon(kind, color=None, size=20):
    """Tiny flat icons: SVG for object types, drawn in code for the toolbar, so the app needs no icon files."""
    from .svgicons import has, svg_icon
    if has(kind):
        return svg_icon(kind, QColor(color or C["text"]).name(), size)
    color = QColor(color or C["text"])
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = size * 2
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    m = s * 0.22
    if kind == "play":
        p.drawPolygon(QPolygonF([QPointF(m * 1.3, m), QPointF(m * 1.3, s - m), QPointF(s - m, s / 2)]))
    elif kind == "stop":
        p.drawRoundedRect(QRectF(m, m, s - 2 * m, s - 2 * m), 4, 4)
    elif kind == "pause":
        w = s * 0.16
        p.drawRoundedRect(QRectF(s * 0.28, m, w, s - 2 * m), 2, 2)
        p.drawRoundedRect(QRectF(s * 0.56, m, w, s - 2 * m), 2, 2)
    elif kind == "step":
        p.drawPolygon(QPolygonF([QPointF(m, m), QPointF(m, s - m), QPointF(s * 0.66, s / 2)]))
        p.drawRoundedRect(QRectF(s * 0.7, m, s * 0.13, s - 2 * m), 2, 2)
    elif kind == "plus":
        p.drawRoundedRect(QRectF(s * 0.45, m, s * 0.1, s - 2 * m), 2, 2)
        p.drawRoundedRect(QRectF(m, s * 0.45, s - 2 * m, s * 0.1), 2, 2)
    elif kind == "rect":
        p.drawRoundedRect(QRectF(m, m * 1.2, s - 2 * m, s - 2.4 * m), 5, 5)
    elif kind == "circle":
        p.drawEllipse(QRectF(m, m, s - 2 * m, s - 2 * m))
    elif kind == "sprite":
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(color, 3))
        p.drawRoundedRect(QRectF(m, m, s - 2 * m, s - 2 * m), 5, 5)
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawPolygon(QPolygonF([QPointF(m * 1.4, s - m * 1.4), QPointF(s * 0.45, s * 0.45), QPointF(s * 0.6, s * 0.65),
                                 QPointF(s * 0.72, s * 0.52), QPointF(s - m * 1.4, s - m * 1.4)]))
    elif kind == "text":
        f = QFont()
        f.setPixelSize(int(s * 0.78))
        f.setBold(True)
        p.setFont(f)
        p.setPen(color)
        p.drawText(QRectF(0, 0, s, s), Qt.AlignCenter, "T")
    elif kind == "camera":
        p.drawRoundedRect(QRectF(m * 0.7, s * 0.32, s * 0.6, s * 0.38), 4, 4)
        p.drawPolygon(QPolygonF([QPointF(s * 0.66, s * 0.46), QPointF(s - m * 0.7, s * 0.3),
                                 QPointF(s - m * 0.7, s * 0.72), QPointF(s * 0.66, s * 0.56)]))
    elif kind == "empty":
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(color, 3))
        p.drawLine(QPointF(m, s / 2), QPointF(s - m, s / 2))
        p.drawLine(QPointF(s / 2, m), QPointF(s / 2, s - m))
    elif kind == "light":
        p.drawEllipse(QPointF(s / 2, s * 0.42), s * 0.22, s * 0.22)
        p.drawLine(QPointF(s * 0.4, s * 0.78), QPointF(s * 0.6, s * 0.78))
        p.drawLine(QPointF(s * 0.43, s * 0.9), QPointF(s * 0.57, s * 0.9))
    elif kind == "polygon":
        p.drawPolygon(QPolygonF([QPointF(s * 0.5, m * 0.8), QPointF(s - m * 0.7, s * 0.4), QPointF(s * 0.78, s - m * 0.8),
                                 QPointF(s * 0.22, s - m * 0.8), QPointF(m * 0.7, s * 0.4)]))
    elif kind == "tilemap":
        for i in range(2):
            for j in range(2):
                p.drawRect(QRectF(m + i * (s - 2 * m) / 2, m + j * (s - 2 * m) / 2, (s - 2 * m) / 2, (s - 2 * m) / 2))
    elif kind == "particles":
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        for fx, fy, fr in ((0.5, 0.78, 0.1), (0.32, 0.55, 0.08), (0.66, 0.5, 0.09), (0.45, 0.3, 0.07), (0.7, 0.24, 0.05)):
            p.drawEllipse(QPointF(s * fx, s * fy), s * fr, s * fr)
    elif kind == "button":
        p.drawRoundedRect(QRectF(m * 0.6, s * 0.28, s - 1.2 * m, s * 0.44), 6, 6)
        p.drawLine(QPointF(s * 0.34, s * 0.5), QPointF(s * 0.66, s * 0.5))
    elif kind == "bar":
        p.drawRoundedRect(QRectF(m * 0.6, s * 0.38, s - 1.2 * m, s * 0.24), 5, 5)
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawRoundedRect(QRectF(m * 0.6 + 2, s * 0.38 + 2, (s - 1.2 * m) * 0.55, s * 0.24 - 4), 3, 3)
    elif kind == "slider":
        p.drawLine(QPointF(m * 0.8, s / 2), QPointF(s - m * 0.8, s / 2))
        p.setBrush(color)
        p.drawEllipse(QPointF(s * 0.6, s / 2), s * 0.14, s * 0.14)
    elif kind == "checkbox":
        p.drawRoundedRect(QRectF(m, m, s - 2 * m, s - 2 * m), 4, 4)
        p.drawPolyline(QPolygonF([QPointF(s * 0.28, s * 0.52), QPointF(s * 0.44, s * 0.68), QPointF(s * 0.74, s * 0.32)]))
    elif kind == "input":
        p.drawRoundedRect(QRectF(m * 0.6, s * 0.28, s - 1.2 * m, s * 0.44), 4, 4)
        p.drawLine(QPointF(s * 0.34, s * 0.38), QPointF(s * 0.34, s * 0.62))
    elif kind == "script":
        p.drawRoundedRect(QRectF(s * 0.2, m * 0.8, s * 0.6, s - 1.6 * m), 5, 5)
        p.setPen(QPen(QColor(C["bg1"]), 3))
        for i in range(3):
            y = s * (0.34 + 0.15 * i)
            p.drawLine(QPointF(s * 0.32, y), QPointF(s * 0.68, y))
    elif kind == "sound":
        p.drawPolygon(QPolygonF([QPointF(m, s * 0.38), QPointF(s * 0.38, s * 0.38), QPointF(s * 0.62, m),
                                 QPointF(s * 0.62, s - m), QPointF(s * 0.38, s * 0.62), QPointF(m, s * 0.62)]))
    p.end()
    pm.setDevicePixelRatio(2)
    return QIcon(pm)


def tile_icon(kind, accent, size=56):
    """Bigger rounded tile used in the Project panel."""
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    c = QColor(accent)
    bg = QColor(c)
    bg.setAlpha(46)
    p.setPen(QPen(c, 2))
    p.setBrush(bg)
    s = size * 2
    p.drawRoundedRect(QRectF(4, 4, s - 8, s - 8), 18, 18)
    ic = icon(kind, accent, int(size * 0.55))
    pmi = ic.pixmap(int(size * 0.55), int(size * 0.55))
    p.drawPixmap(int((s - pmi.width()) / 2), int((s - pmi.height()) / 2), pmi)
    p.end()
    pm.setDevicePixelRatio(2)
    return QIcon(pm)
