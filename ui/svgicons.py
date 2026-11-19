"""One SVG icon per object type, for the Hierarchy and the Add menus. 24x24, drawn with a single color."""
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

S = 'fill="none" stroke="COL" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"'
F = 'fill="COL" stroke="none"'

SVG = {
    "rect": f'<rect x="4" y="6" width="16" height="12" rx="2.5" {S}/>',
    "circle": f'<circle cx="12" cy="12" r="7.5" {S}/>',
    "sprite": f'<rect x="3.5" y="4.5" width="17" height="15" rx="2.5" {S}/><path d="M4 17l5-5 4 4 3-3 4 4" {S}/><circle cx="9" cy="9" r="1.6" {F}/>',
    "text": f'<path d="M5 7V5h14v2M12 5v14M9 19h6" {S}/>',
    "camera": f'<rect x="3" y="7" width="12" height="10" rx="2.5" {S}/><path d="M15 11l6-3v8l-6-3z" {S}/>',
    "empty": f'<path d="M12 4v16M4 12h16" {S}/><circle cx="12" cy="12" r="2" {F}/>',
    "polygon": f'<path d="M12 3.5l8 6-3 10H7l-3-10z" {S}/>',
    "tilemap": f'<rect x="4" y="4" width="7" height="7" rx="1" {S}/><rect x="13" y="4" width="7" height="7" rx="1" {S}/><rect x="4" y="13" width="7" height="7" rx="1" {S}/><rect x="13" y="13" width="7" height="7" rx="1" {F}/>',
    "particles": f'<circle cx="12" cy="18" r="1.8" {F}/><circle cx="7.5" cy="13" r="1.4" {F}/><circle cx="16.5" cy="12" r="1.6" {F}/><circle cx="11" cy="7.5" r="1.2" {F}/><circle cx="17" cy="5.5" r="0.9" {F}/>',
    "light": f'<path d="M9 17h6M10 20h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z" {S}/>',
    "button": f'<rect x="3" y="8" width="18" height="8" rx="4" {S}/><path d="M9 12h6" {S}/>',
    "bar": f'<rect x="3" y="9" width="18" height="6" rx="3" {S}/><rect x="5" y="11" width="8" height="2" rx="1" {F}/>',
    "slider": f'<path d="M4 12h16" {S}/><circle cx="14" cy="12" r="3.2" {F}/>',
    "checkbox": f'<rect x="4.5" y="4.5" width="15" height="15" rx="3" {S}/><path d="M8 12.5l3 3 5-6" {S}/>',
    "input": f'<rect x="3" y="7.5" width="18" height="9" rx="2.5" {S}/><path d="M8 10.5v3" {S}/>',
    "model": f'<path d="M12 3.5l8 4.2v8.6L12 20.5l-8-4.2V7.7z" {S}/><path d="M4 7.7l8 4.3 8-4.3M12 12v8.5" {S}/>',
    "folder": f'<path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z" {S}/>',
    "zone": f'<rect x="4" y="4" width="16" height="16" rx="2" {S} stroke-dasharray="3 3"/><circle cx="12" cy="12" r="1.8" {F}/>',
    "spawn": f'<ellipse cx="12" cy="18" rx="7" ry="2.6" {S}/><path d="M12 18V5" {S}/><path d="M12 5.5l6 2.3-6 2.3z" {F}/>',
    "beam": f'<circle cx="5.5" cy="12" r="2.3" {S}/><circle cx="18.5" cy="12" r="2.3" {S}/><path d="M8 12h8" {S} stroke-dasharray="1.5 2.5"/>',
    "prompt": f'<rect x="4" y="5" width="16" height="11" rx="3" {S}/><path d="M9 16l-2 4 5-4" {S}/><path d="M9.5 10.5h5" {S}/>',
    "eye": f'<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" {S}/><circle cx="12" cy="12" r="3" {S}/>',
    "eye_off": f'<path d="M3 3l18 18M10.6 6a9 9 0 0 1 1.4-.1c6 0 9.5 6.1 9.5 6.1a16 16 0 0 1-3 3.6M6.4 7.4A16 16 0 0 0 2.5 12S6 18.5 12 18.5a9 9 0 0 0 4-1" {S}/>',
    "lock": f'<rect x="5" y="11" width="14" height="9" rx="2.5" {S}/><path d="M8.5 11V8a3.5 3.5 0 0 1 7 0v3" {S}/>',
    "unlock": f'<rect x="5" y="11" width="14" height="9" rx="2.5" {S}/><path d="M8.5 11V8a3.5 3.5 0 0 1 6.8-1.2" {S}/>',
    "search": f'<circle cx="10.5" cy="10.5" r="6" {S}/><path d="M15 15l5 5" {S}/>',
    "scene": f'<path d="M4 18l4-9 4 6 3-4 5 7z" {S}/><circle cx="16.5" cy="7" r="2" {S}/>',
}

_cache = {}


def has(kind):
    return kind in SVG


def svg_text(kind, color):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">{SVG[kind].replace("COL", color)}</svg>'


def svg_icon(kind, color="#e8eaf0", size=16):
    key = (kind, color, size)
    if key not in _cache:
        r = QSvgRenderer(QByteArray(svg_text(kind, color).encode()))
        pm = QPixmap(size * 2, size * 2)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        r.render(p)
        p.end()
        pm.setDevicePixelRatio(2)
        _cache[key] = QIcon(pm)
    return _cache[key]
