"""Painting of a scene with QPainter. Shared by the editor's Scene view and the Game view."""
import math
import random

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen, QPixmap, QFontDatabase, QPolygonF, QRadialGradient

from .scene import sort_for_drawing
from .gameobject import UI_KINDS
from .theme import DEFAULT_THEME, resolve, corner
from .animation import cell_count
from . import joints, particles, tilemap

_colors = {}


def qcolor(s):
    c = _colors.get(s)
    if c is None:
        c = QColor(s)
        if not c.isValid():
            c = QColor("#888888")
        _colors[s] = c
    return c


class Assets:
    """Loads and caches pixmaps from a project folder."""

    def __init__(self, project_dir):
        self.dir = project_dir
        self._cache = {}
        self._fonts = {}
        self.theme = dict(DEFAULT_THEME)

    def font_family(self, rel):
        """Family name of a .ttf/.otf inside the project (loaded once), or '' for the default font."""
        if not rel:
            return ""
        path = self.dir / rel
        try:
            mt = path.stat().st_mtime
        except OSError:
            return ""
        hit = self._fonts.get(rel)
        if hit and hit[0] == mt:
            return hit[1]
        fid = QFontDatabase.addApplicationFont(str(path))
        fam = QFontDatabase.applicationFontFamilies(fid)
        name = fam[0] if fam else ""
        self._fonts[rel] = (mt, name)
        return name

    def make_font(self, rel, px, bold=False):
        f = QFont()
        fam = self.font_family(rel or self.theme.get("font", ""))
        if fam:
            f.setFamily(fam)
        f.setPixelSize(max(6, int(px)))
        f.setBold(bold and not fam)
        return f

    def pixmap(self, rel):
        if not rel:
            return None
        path = self.dir / rel
        try:
            mt = path.stat().st_mtime
        except OSError:
            return None
        hit = self._cache.get(rel)
        if hit and hit[0] == mt:
            return hit[1]
        pm = QPixmap(str(path))
        if pm.isNull():
            return None
        self._cache[rel] = (mt, pm)
        return pm


def _plain_font(px):
    f = QFont()
    f.setPixelSize(max(6, int(px)))
    f.setBold(True)
    return f


def _source_rect(o, pm):
    """Which part of the picture to draw: all of it, or one cell of a sprite sheet."""
    cols, rows = max(1, o.sheet_cols), max(1, o.sheet_rows)
    if cols * rows <= 1:
        return QRectF(pm.rect())
    cw, ch = pm.width() / cols, pm.height() / rows
    n = cell_count(o)
    f = int(o.frame) % n if n else 0
    return QRectF((f % cols) * cw, (f // cols) * ch, cw, ch)


def _draw_ui(p, o, rect, assets):
    th = assets.theme if assets else DEFAULT_THEME
    r = corner(o, th)
    k = o.kind
    dim = 0.5 if not o.enabled else 1.0
    p.setOpacity(p.opacity() * dim)
    text_c = qcolor(resolve(o, "text_color", th))
    font = assets.make_font(o.font, o.text_size, True) if assets else _plain_font(o.text_size)
    p.setPen(Qt.NoPen)
    if k == "button":
        col = resolve(o, "press_color" if o.pressing else "hover_color" if o.hovered else "color", th)
        p.setBrush(qcolor(col))
        p.drawRoundedRect(rect, r, r)
        p.setPen(text_c)
        p.setFont(font)
        p.drawText(rect, int(Qt.AlignCenter), o.text)
    elif k == "bar" or k == "slider":
        p.setBrush(qcolor(resolve(o, "back_color", th)))
        p.drawRoundedRect(rect, r, r)
        v = max(0.0, min(1.0, o.value))
        if v > 0:
            fill = QRectF(rect.left(), rect.top(), max(rect.height(), rect.width() * v) if v > 0.001 else 0, rect.height())
            fill.setWidth(min(fill.width(), rect.width()))
            p.setBrush(qcolor(resolve(o, "color", th)))
            p.drawRoundedRect(fill, r, r)
        if k == "slider":
            kx = rect.left() + rect.width() * v
            kr = rect.height() * 0.8
            p.setBrush(qcolor("#ffffff"))
            p.setPen(QPen(qcolor("#00000066"), 1.5))
            p.drawEllipse(QPointF(kx, rect.center().y()), kr / 2, kr / 2)
        if o.text:
            p.setPen(text_c)
            p.setFont(font)
            p.drawText(rect, int(Qt.AlignCenter), o.text)
    elif k == "checkbox":
        box = QRectF(rect.left(), rect.center().y() - min(rect.height(), 28) / 2, min(rect.height(), 28), min(rect.height(), 28))
        p.setBrush(qcolor(resolve(o, "back_color", th)))
        p.drawRoundedRect(box, min(r, 6), min(r, 6))
        if o.checked:
            p.setPen(QPen(qcolor(resolve(o, "color", th)), max(2.0, box.width() * 0.14), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPolyline([QPointF(box.left() + box.width() * 0.22, box.center().y()),
                            QPointF(box.left() + box.width() * 0.43, box.bottom() - box.height() * 0.25),
                            QPointF(box.right() - box.width() * 0.2, box.top() + box.height() * 0.25)])
        p.setPen(text_c)
        p.setFont(font)
        p.drawText(QRectF(box.right() + 8, rect.top(), rect.width() - box.width() - 8, rect.height()),
                   int(Qt.AlignVCenter | Qt.AlignLeft), o.text)
    elif k == "input":
        p.setBrush(qcolor(resolve(o, "back_color", th)))
        p.setPen(QPen(qcolor(resolve(o, "color", th)), 2) if o.focused else Qt.NoPen)
        p.drawRoundedRect(rect, r, r)
        p.setFont(font)
        inner = rect.adjusted(10, 0, -10, 0)
        shown = o.text + ("|" if o.focused else "")
        p.setPen(text_c)
        p.drawText(inner, int(Qt.AlignVCenter | Qt.AlignLeft), shown)
    p.setOpacity(1.0)


def _draw_polygon(p, o, rect, editor):
    pts = o.points if len(o.points) >= 3 else [[-0.5, 0.5], [0.0, -0.5], [0.5, 0.5]]
    poly = QPolygonF([QPointF(px * o.w, py * o.h) for px, py in pts])
    p.setPen(Qt.NoPen)
    p.setBrush(qcolor(o.color))
    p.drawPolygon(poly)
    if editor and len(o.points) < 3:
        p.setPen(QPen(QColor("#8a91a3"), 1, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawRect(rect)


def _draw_tilemap(p, o, assets, editor):
    ts = float(o.tile_size)
    pm = assets.pixmap(o.sprite) if assets and o.sprite else None
    cols, rows = max(1, o.sheet_cols), max(1, o.sheet_rows)
    view = p.clipBoundingRect()
    cull = view.isValid() and not view.isEmpty()
    n_cells = cols * rows
    for k, n in o.tiles.items():
        c, r = tilemap.split(k)
        cell = QRectF(c * ts - ts / 2, r * ts - ts / 2, ts, ts)
        if cull and not view.intersects(cell):
            continue
        if pm:
            cw, ch = pm.width() / cols, pm.height() / rows
            i = n % n_cells
            p.drawPixmap(cell, pm, QRectF((i % cols) * cw, (i // cols) * ch, cw, ch))
        else:
            p.setPen(Qt.NoPen)
            p.setBrush(qcolor(o.color))
            p.drawRect(cell)
            if n:
                p.setBrush(QColor(0, 0, 0, min(120, 25 * (n % 6))))
                p.drawRect(cell)
    if editor:
        p.setPen(QPen(QColor(255, 255, 255, 60), 1, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(-ts / 2, -ts / 2, ts, ts))


def _draw_particles(p, o, ox, oy, editor, assets=None):
    if editor and not o.parts:
        p.setPen(QPen(QColor("#f2b84b"), 1.5))
        p.setBrush(Qt.NoBrush)
        for i in range(8):
            ang = i * 0.785
            p.drawLine(QPointF(0, 0), QPointF(14 * math.cos(ang), 14 * math.sin(ang)))
        p.drawEllipse(QPointF(0, 0), 4, 4)
        return
    c0 = particles.rgba(o.color)
    c1 = particles.rgba(o.em_color_end) if o.em_color_end else c0
    a_end = o.em_alpha_end * (c1[3] if o.em_color_end else c0[3])
    pm = assets.pixmap(o.sprite) if assets and o.sprite else None
    pm = pm if pm is not None and not pm.isNull() else None
    cols, rows = max(1, o.sheet_cols), max(1, o.sheet_rows)
    p.setPen(Qt.NoPen)
    if o.em_add:
        p.setCompositionMode(QPainter.CompositionMode_Plus)
    col = QColor()
    for px, py, _vx, _vy, age, life, rot, _spin, size0, seed in o.parts:
        k = age / life
        a = c0[3] + (a_end - c0[3]) * k
        col.setRgbF(c0[0] + (c1[0] - c0[0]) * k, c0[1] + (c1[1] - c0[1]) * k, c0[2] + (c1[2] - c0[2]) * k, max(0.0, min(1.0, a)))
        d = max(0.5, size0 * (1.0 + (o.em_size_end - 1.0) * k))
        cx, cy = (px, py) if o.em_local else (px - ox, py - oy)
        if pm:
            i = int(seed * cols * rows) % (cols * rows)
            cw, ch = pm.width() / cols, pm.height() / rows
            p.save()
            p.translate(cx, cy)
            p.rotate(rot)
            p.setOpacity(p.opacity() * col.alphaF())
            p.drawPixmap(QRectF(-d / 2, -d / 2, d, d), pm, QRectF((i % cols) * cw, (i // cols) * ch, cw, ch))
            p.restore()
        else:
            p.setBrush(col)
            p.drawEllipse(QPointF(cx, cy), d / 2, d / 2)
    if o.em_add:
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)


def _draw_marker(p, o, rect, editor):
    """The helper objects: zones, spawn points, models, beams and prompts. Mostly seen only in the editor."""
    k = o.kind
    col = QColor(qcolor(o.color))
    if k == "prompt":
        r = max(8.0, o.w / 2)
        if editor:
            p.setPen(QPen(QColor("#6aa7ff"), 1.5, Qt.DashLine))
            p.setBrush(QColor(106, 167, 255, 30))
            p.drawEllipse(QPointF(0, 0), r, r)
            p.setPen(QPen(QColor("#6aa7ff"), 2))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(-10, -9, 20, 14), 3, 3)
            p.drawLine(-3, 5, -6, 10)
        if o.focused or editor:
            f = QFont()
            f.setPixelSize(13)
            f.setBold(True)
            p.setFont(f)
            label = f"[E]  {o.text or 'Use'}"
            tw = p.fontMetrics().horizontalAdvance(label) + 20
            box = QRectF(-tw / 2, -r - 34 if not editor else -48, tw, 26)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(20, 24, 36, 230))
            p.drawRoundedRect(box, 7, 7)
            p.setPen(QColor("#ffffff"))
            p.drawText(box, Qt.AlignCenter, label)
        return
    if not editor:
        return
    if k == "zone":
        col.setAlpha(45)
        p.setBrush(col)
        p.setPen(QPen(qcolor(o.color), 1.5, Qt.DashLine))
        p.drawRect(rect)
        f = QFont()
        f.setPixelSize(11)
        p.setFont(f)
        p.setPen(QColor(255, 255, 255, 170))
        p.drawText(rect, Qt.AlignCenter, "zone")
    elif k == "spawn":
        p.setPen(QPen(QColor("#6bd38a"), 2))
        p.setBrush(QColor(107, 211, 138, 70))
        p.drawEllipse(QPointF(0, 8), 16, 7)
        p.drawLine(0, 8, 0, -22)
        p.setBrush(QColor("#6bd38a"))
        p.drawPolygon([QPointF(0, -22), QPointF(16, -16), QPointF(0, -10)])
    elif k in ("model", "folder"):
        p.setPen(QPen(QColor("#8a91a3"), 1.5, Qt.DashLine))
        p.setBrush(QColor(138, 145, 163, 25))
        p.drawRect(rect)
        p.setPen(QPen(QColor("#c9ced9"), 1.5))
        p.setBrush(QColor("#8a91a3") if k == "folder" else Qt.NoBrush)
        p.drawRoundedRect(QRectF(-9, -6, 18, 13), 2, 2)
    elif k == "beam":
        p.setPen(QPen(QColor(qcolor(o.color)), 2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(0, 0), 7, 7)
        p.drawLine(7, 0, 16, 0)


def draw_object(p, o, cam, assets, editor=False):
    x, y = o.world_pos(cam)
    p.save()
    p.translate(x, y)
    if o.angle:
        p.rotate(o.angle)
    if o.flip_x:
        p.scale(-1, 1)
    rect = QRectF(-o.w / 2, -o.h / 2, o.w, o.h)
    k = o.kind
    if k == "rect":
        p.setPen(Qt.NoPen)
        p.setBrush(qcolor(o.color))
        p.drawRoundedRect(rect, 6, 6)
    elif k == "circle":
        p.setPen(Qt.NoPen)
        p.setBrush(qcolor(o.color))
        p.drawEllipse(rect)
    elif k == "sprite":
        pm = assets.pixmap(o.sprite) if assets else None
        if pm:
            p.drawPixmap(rect, pm, _source_rect(o, pm))
        else:
            p.setPen(QPen(QColor("#8a91a3"), 1.5, Qt.DashLine))
            p.setBrush(QColor(138, 145, 163, 40))
            p.drawRect(rect)
            f = QFont()
            f.setPixelSize(max(10, int(min(o.w, o.h) * 0.4)))
            p.setFont(f)
            p.drawText(rect, Qt.AlignCenter, "?")
    elif k == "text":
        p.setPen(qcolor(o.color))
        p.setFont(assets.make_font(o.font, o.text_size, True) if assets else _plain_font(o.text_size))
        flags = Qt.AlignVCenter | (Qt.AlignLeft if o.align == "left" else Qt.AlignHCenter)
        p.drawText(rect, int(flags), o.text)
    elif k == "polygon":
        _draw_polygon(p, o, rect, editor)
    elif k == "tilemap":
        _draw_tilemap(p, o, assets, editor)
    elif k == "particles":
        _draw_particles(p, o, x, y, editor, assets)
    elif k == "light" and editor:
        p.setPen(QPen(QColor(o.color), 1.5, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(0, 0), o.w / 2, o.w / 2)
        p.setPen(QPen(QColor(o.color), 2))
        p.drawEllipse(QPointF(0, 0), 7, 7)
        for i in range(8):
            a = i * 0.785
            p.drawLine(QPointF(11 * math.cos(a), 11 * math.sin(a)), QPointF(16 * math.cos(a), 16 * math.sin(a)))
    elif k in UI_KINDS:
        _draw_ui(p, o, rect, assets)
    elif k == "camera" and editor:
        p.setPen(QPen(QColor("#f2b84b"), 2))
        p.setBrush(QColor(242, 184, 75, 60))
        p.drawRoundedRect(QRectF(-18, -11, 30, 22), 3, 3)
        p.drawPolygon([QPointF(12, -4), QPointF(22, -10), QPointF(22, 10), QPointF(12, 4)])
    elif k in ("zone", "spawn", "model", "folder", "beam", "prompt"):
        _draw_marker(p, o, rect, editor)
    elif k == "empty" and editor:
        p.setPen(QPen(QColor("#8a91a3"), 1.5))
        p.drawLine(-10, 0, 10, 0)
        p.drawLine(0, -10, 0, 10)
    p.restore()


def _draw_darkness(p, scene, cam, editor):
    """Cover the view with darkness, then cut soft holes for every light."""
    dk = scene.darkness * (0.45 if editor else 1.0)
    if dk <= 0:
        return
    if p.hasClipping():
        view = p.clipBoundingRect()
    else:
        inv, ok = p.worldTransform().inverted()
        dev = p.device()
        view = inv.mapRect(QRectF(0, 0, dev.width(), dev.height())) if ok else QRectF()
    if not view.isValid() or view.isEmpty():
        return
    scale = max(0.05, p.worldTransform().m11())
    w = max(2, min(3000, int(view.width() * scale) + 1))
    h = max(2, min(3000, int(view.height() * scale) + 1))
    img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    col = QColor(qcolor(scene.ambient))
    col.setAlphaF(dk)
    img.fill(col)
    ip = QPainter(img)
    ip.setRenderHint(QPainter.Antialiasing)
    ip.scale(w / view.width(), h / view.height())
    ip.translate(-view.left(), -view.top())
    ip.setPen(Qt.NoPen)
    lights = [o for o in scene.all() if o.kind == "light" and not o.dead and o.is_active()]
    for o in lights:
        x, y = o.world_pos(cam)
        r = max(1.0, o.w / 2)
        k = max(0.0, min(1.0, o.intensity * (1.0 - o.flicker * random.random() * 0.5)))
        ip.setCompositionMode(QPainter.CompositionMode_DestinationOut)
        g = QRadialGradient(QPointF(x, y), r)
        for stop, a in ((0.0, 1.0), (0.55, 0.75), (1.0, 0.0)):
            c = QColor(0, 0, 0)
            c.setAlphaF(k * a)
            g.setColorAt(stop, c)
        ip.setBrush(QBrush(g))
        ip.drawEllipse(QPointF(x, y), r, r)
    ip.setCompositionMode(QPainter.CompositionMode_SourceOver)
    ip.end()
    p.drawImage(view, img)
    # a gentle colored glow on top of each light
    p.setPen(Qt.NoPen)
    for o in lights:
        if o.color.lower() in ("#ffffff", "#fff"):
            continue
        x, y = o.world_pos(cam)
        r = max(1.0, o.w / 2)
        g = QRadialGradient(QPointF(x, y), r)
        c0, c1 = QColor(qcolor(o.color)), QColor(qcolor(o.color))
        c0.setAlphaF(0.22 * min(1.0, o.intensity))
        c1.setAlphaF(0.0)
        g.setColorAt(0.0, c0)
        g.setColorAt(1.0, c1)
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(x, y), r, r)


def _is_overlay(o):
    """HUD and UI objects are drawn after the darkness so they stay bright."""
    r = o
    while r.parent is not None:
        r = r.parent
    return r.hud or o.kind in UI_KINDS


def spring_points(ax, ay, bx, by, n=10, amp=7.0):
    dx, dy = bx - ax, by - ay
    d = math.hypot(dx, dy) or 1.0
    vx, vy = -dy / d, dx / d
    pts = [(ax, ay)]
    for i in range(1, n):
        t = i / n
        k = amp if i % 2 else -amp
        pts.append((ax + dx * t + vx * k, ay + dy * t + vy * k))
    pts.append((bx, by))
    return pts


def draw_joints(p, scene):
    """Ropes, springs and beams as lines."""
    for ax, ay, bx, by, width, color, style in joints.lines(scene):
        pen = QPen(qcolor(color), width)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        if style == "spring":
            p.drawPolyline([QPointF(x, y) for x, y in spring_points(ax, ay, bx, by)])
        else:
            p.drawLine(QPointF(ax, ay), QPointF(bx, by))


def draw_scene(p, scene, cam, assets, editor=False):
    """Painter must already be in world coordinates."""
    objs = sort_for_drawing(scene)
    dark = scene.darkness > 0
    for overlay in ((False, True) if dark else (None,)):
        if overlay:
            _draw_darkness(p, scene, cam, editor)
        for o in objs:
            if o.dead:
                continue
            if overlay is not None and _is_overlay(o) != overlay:
                continue
            active = o.is_active()
            if not active and not editor:
                continue
            opacity = (1.0 if active else 0.28) * max(0.0, min(1.0, o.alpha))
            if opacity <= 0.0:
                continue
            p.setOpacity(opacity)
            draw_object(p, o, cam, assets, editor)
            p.setOpacity(1.0)
        if overlay is not True:
            draw_joints(p, scene)
