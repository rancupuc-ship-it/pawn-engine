"""Scene view: the main editing window. Pan, zoom, select, move (with arrows), resize."""
import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from engine import tilemap
from engine.render import draw_scene
from .theme import C

ARROW = 64.0
HANDLE = 5.0


class SceneView(QWidget):
    selected = Signal(object)     # GameObject or None
    transformed = Signal()        # while dragging
    finished = Signal()           # after a drag/nudge

    def __init__(self, ed):
        super().__init__()
        self.ed = ed
        self.cx, self.cy, self.zoom = 0.0, 0.0, 1.0
        self.drag = None
        self.pan = None
        self.hover = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(300, 200)

    # ---- coordinates ------------------------------------------------------------
    def w2s(self, x, y):
        return QPointF((x - self.cx) * self.zoom + self.width() / 2, (y - self.cy) * self.zoom + self.height() / 2)

    def s2w(self, p):
        return (p.x() - self.width() / 2) / self.zoom + self.cx, (p.y() - self.height() / 2) / self.zoom + self.cy

    def cam_pos(self):
        cam = self.ed.scene.camera()
        return cam.world_pos() if cam else (0.0, 0.0)

    def fit_all(self):
        rects = []
        for o in self.ed.scene.all():
            x, y = o.world_pos()
            if o.kind == "camera":
                hw, hh = 480.0 / o.zoom, 270.0 / o.zoom
            elif o.hud or o.w > 1000 or o.kind == "empty":
                continue
            else:
                hw, hh = o.w / 2, o.h / 2
            rects.append((x - hw, y - hh, x + hw, y + hh))
        if not rects:
            self.cx = self.cy = 0.0
            self.zoom = 1.0
        else:
            x0, y0 = min(r[0] for r in rects), min(r[1] for r in rects)
            x1, y1 = max(r[2] for r in rects), max(r[3] for r in rects)
            self.cx, self.cy = (x0 + x1) / 2, (y0 + y1) / 2
            bw, bh = max(x1 - x0, 100), max(y1 - y0, 100)
            self.zoom = max(0.2, min(1.0, self.width() / (bw * 1.12), self.height() / (bh * 1.12)))
        self.update()

    def frame(self, obj=None):
        if obj is not None:
            self.cx, self.cy = obj.world_pos(self.cam_pos())
        else:
            self.cx, self.cy = self.cam_pos()
        self.update()

    # ---- painting ---------------------------------------------------------------------
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor("#15181e"))
        self._grid(p)
        cam = self.cam_pos()
        p.save()
        p.translate(self.width() / 2, self.height() / 2)
        p.scale(self.zoom, self.zoom)
        p.translate(-self.cx, -self.cy)
        draw_scene(p, self.ed.scene, cam, self.ed.assets, editor=True)
        p.restore()
        self._camera_frames(p)
        sel = self.ed.selected
        if sel is not None and not sel.dead:
            self._selection(p, sel, cam)
        self._overlay(p)

    def _grid(self, p):
        step = 50.0
        while step * self.zoom < 14:
            step *= 5
        x0, y0 = self.s2w(QPointF(0, 0))
        x1, y1 = self.s2w(QPointF(self.width(), self.height()))
        minor, major, axis = QColor(255, 255, 255, 10), QColor(255, 255, 255, 22), QColor(242, 184, 75, 70)
        i = math.floor(x0 / step)
        while i * step <= x1:
            wx = i * step
            sx = self.w2s(wx, 0).x()
            p.setPen(QPen(axis if i == 0 else major if i % 5 == 0 else minor, 1))
            p.drawLine(QPointF(sx, 0), QPointF(sx, self.height()))
            i += 1
        j = math.floor(y0 / step)
        while j * step <= y1:
            wy = j * step
            sy = self.w2s(0, wy).y()
            p.setPen(QPen(axis if j == 0 else major if j % 5 == 0 else minor, 1))
            p.drawLine(QPointF(0, sy), QPointF(self.width(), sy))
            j += 1

    def _camera_frames(self, p):
        for o in self.ed.scene.all():
            if o.kind != "camera" or not o.is_active():
                continue
            x, y = o.world_pos()
            vw, vh = 960.0 / o.zoom, 540.0 / o.zoom
            a, b = self.w2s(x - vw / 2, y - vh / 2), self.w2s(x + vw / 2, y + vh / 2)
            p.setPen(QPen(QColor(242, 184, 75, 150), 1.5, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(a, b))
            f = QFont()
            f.setPixelSize(11)
            p.setFont(f)
            p.setPen(QColor(242, 184, 75, 190))
            p.drawText(QPointF(a.x(), a.y() - 6), "Camera view  (what players see)")

    def _box(self, o, cam, pad=0.0):
        """(left, top, right, bottom) of what you click on to select this object."""
        x, y = o.world_pos(cam)
        if o.kind in ("camera", "empty", "particles"):
            hw = hh = (16 if o.kind != "particles" else 20) / self.zoom
            return x - hw, y - hh, x + hw, y + hh
        if o.kind == "tilemap":
            b = tilemap.bounds(o)
            ts = o.tile_size
            if b is None:
                return x - ts / 2, y - ts / 2, x + ts / 2, y + ts / 2
            return x + b[0] * ts - ts / 2, y + b[1] * ts - ts / 2, x + b[2] * ts + ts / 2, y + b[3] * ts + ts / 2
        return x - o.w / 2, y - o.h / 2, x + o.w / 2, y + o.h / 2

    def _selection(self, p, o, cam):
        x, y = o.world_pos(cam)
        left, top, right, bottom = self._box(o, cam)
        r = QRectF(self.w2s(left, top), self.w2s(right, bottom))
        p.setPen(QPen(QColor(C["gold"]), 1.6))
        p.setBrush(Qt.NoBrush)
        p.drawRect(r)
        if o.kind not in ("camera", "empty", "tilemap", "particles"):
            p.setBrush(QColor(C["gold"]))
            p.setPen(QPen(QColor("#1a1406"), 1))
            for hp in self._handles(r).values():
                p.drawRect(QRectF(hp.x() - HANDLE, hp.y() - HANDLE, HANDLE * 2, HANDLE * 2))
        c = self.w2s(x, y)
        for axis, col, vec in (("x", "#ef6b6b", (1, 0)), ("y", "#6bd38a", (0, 1))):
            tip = QPointF(c.x() + vec[0] * ARROW, c.y() + vec[1] * ARROW)
            p.setPen(QPen(QColor(col), 2.4))
            p.drawLine(c, tip)
            p.setBrush(QColor(col))
            p.setPen(Qt.NoPen)
            if axis == "x":
                poly = [tip + QPointF(9, 0), tip + QPointF(-3, -6), tip + QPointF(-3, 6)]
            else:
                poly = [tip + QPointF(0, 9), tip + QPointF(-6, -3), tip + QPointF(6, -3)]
            p.drawPolygon(QPolygonF(poly))
        f = QFont()
        f.setPixelSize(11)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(C["gold2"]))
        p.drawText(QPointF(r.left(), r.top() - 6), o.name)

    def _handles(self, r):
        return {"tl": r.topLeft(), "tr": r.topRight(), "bl": r.bottomLeft(), "br": r.bottomRight()}

    def _overlay(self, p):
        f = QFont()
        f.setPixelSize(11)
        p.setFont(f)
        p.setPen(QColor(C["muted"]))
        p.drawText(14, self.height() - 12,
                   "Drag arrows to move  •  Right-drag to pan  •  Scroll to zoom  •  Hold Shift to snap  •  F to focus")
        p.drawText(self.width() - 70, 20, f"{round(self.zoom * 100)}%")
        if not self.ed.scene.roots:
            p.setPen(QColor(C["muted"]))
            f.setPixelSize(15)
            p.setFont(f)
            p.drawText(self.rect(), Qt.AlignCenter, "Empty scene\nUse  Object ▸ Add  to put something here")

    # ---- picking ---------------------------------------------------------------------------
    def _hit_handle(self, pos):
        o = self.ed.selected
        if o is None:
            return None
        cam = self.cam_pos()
        x, y = o.world_pos(cam)
        c = self.w2s(x, y)
        # arrows
        for axis, vec in (("x", (1, 0)), ("y", (0, 1))):
            tip = QPointF(c.x() + vec[0] * ARROW, c.y() + vec[1] * ARROW)
            if self._seg_dist(pos, c + QPointF(vec[0] * 8, vec[1] * 8), tip) < 8:
                return "move" + axis
        if o.kind not in ("camera", "empty", "tilemap", "particles"):
            r = QRectF(self.w2s(x - o.w / 2, y - o.h / 2), self.w2s(x + o.w / 2, y + o.h / 2))
            for name, hp in self._handles(r).items():
                if abs(pos.x() - hp.x()) <= HANDLE + 3 and abs(pos.y() - hp.y()) <= HANDLE + 3:
                    return "size_" + name
        return None

    @staticmethod
    def _seg_dist(p, a, b):
        ax, ay, bx, by = a.x(), a.y(), b.x(), b.y()
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy or 1
        t = max(0, min(1, ((p.x() - ax) * dx + (p.y() - ay) * dy) / L))
        return math.hypot(p.x() - (ax + t * dx), p.y() - (ay + t * dy))

    def _pick(self, pos):
        wx, wy = self.s2w(pos)
        cam = self.cam_pos()
        best = None
        for o in self.ed.scene.all():
            if not o.is_active() or o.locked:
                continue
            if o.kind == "tilemap" and o.tiles:
                c, r = tilemap.cell_at(o, wx, wy)
                if tilemap.get(o, c, r) >= 0:
                    best = o
                continue
            left, top, right, bottom = self._box(o, cam)
            if o.kind not in ("camera", "empty", "particles"):
                x, y = o.world_pos(cam)
                hw, hh = max(o.w / 2, 7 / self.zoom), max(o.h / 2, 7 / self.zoom)
                left, top, right, bottom = x - hw, y - hh, x + hw, y + hh
            if left <= wx <= right and top <= wy <= bottom:
                best = o  # later in tree = drawn on top
        return best

    # ---- mouse ------------------------------------------------------------------------------
    def mousePressEvent(self, e):
        self.setFocus()
        pos = e.position()
        if e.button() in (Qt.RightButton, Qt.MiddleButton):
            self.pan = (pos, self.cx, self.cy)
            self.setCursor(Qt.ClosedHandCursor)
            return
        if e.button() != Qt.LeftButton:
            return
        o_sel = self.ed.selected
        if self.ed.tile_paint and o_sel is not None and o_sel.kind == "tilemap" and not self._hit_handle(pos):
            self.ed.checkpoint(force=True)
            self.painting = True
            self._paint(pos, bool(e.modifiers() & Qt.ControlModifier))
            return
        handle = self._hit_handle(pos)
        if handle is None:
            hit = self._pick(pos)
            self.selected.emit(hit)
            if hit is None:
                return
            handle = "move"
        o = self.ed.selected
        if o is None:
            return
        cam = self.cam_pos()
        wx, wy = self.s2w(pos)
        self.drag = {"mode": handle, "start": (wx, wy), "pos": o.world_pos(cam),
                     "size": (o.w, o.h), "moved": False, "obj": o}

    painting = False

    def _paint(self, pos, erase):
        o = self.ed.selected
        wx, wy = self.s2w(pos)
        c, r = tilemap.cell_at(o, wx, wy)
        if tilemap.set_tile(o, c, r, -1 if erase else self.ed.tile_brush) is not False:
            self.update()

    def mouseMoveEvent(self, e):
        pos = e.position()
        if self.painting:
            self._paint(pos, bool(e.modifiers() & Qt.ControlModifier))
            return
        if self.pan:
            p0, cx, cy = self.pan
            self.cx = cx - (pos.x() - p0.x()) / self.zoom
            self.cy = cy - (pos.y() - p0.y()) / self.zoom
            self.update()
            return
        d = self.drag
        if d is None:
            h = self._hit_handle(pos)
            self.setCursor({"movex": Qt.SizeHorCursor, "movey": Qt.SizeVerCursor, "size_tl": Qt.SizeFDiagCursor,
                            "size_br": Qt.SizeFDiagCursor, "size_tr": Qt.SizeBDiagCursor,
                            "size_bl": Qt.SizeBDiagCursor}.get(h, Qt.ArrowCursor))
            return
        o = d["obj"]
        wx, wy = self.s2w(pos)
        if not d["moved"]:
            if math.hypot(wx - d["start"][0], wy - d["start"][1]) * self.zoom < 3:
                return
            d["moved"] = True
            self.ed.checkpoint(f"drag:{o.id}", force=True)
        snap = bool(e.modifiers() & Qt.ShiftModifier)
        cam = self.cam_pos()
        mode = d["mode"]
        if mode.startswith("move"):
            nx, ny = d["pos"][0] + (wx - d["start"][0]), d["pos"][1] + (wy - d["start"][1])
            if mode == "movex":
                ny = d["pos"][1]
            elif mode == "movey":
                nx = d["pos"][0]
            if snap:
                nx, ny = round(nx / 10) * 10, round(ny / 10) * 10
            o.set_world_pos(nx, ny, cam)
        else:
            x0, y0 = d["pos"]
            w0, h0 = d["size"]
            left, right, top, bottom = x0 - w0 / 2, x0 + w0 / 2, y0 - h0 / 2, y0 + h0 / 2
            if snap:
                wx, wy = round(wx / 10) * 10, round(wy / 10) * 10
            corner = mode[5:]
            if "l" in corner:
                left = min(wx, right - 4)
            else:
                right = max(wx, left + 4)
            if "t" in corner:
                top = min(wy, bottom - 4)
            else:
                bottom = max(wy, top + 4)
            o.w, o.h = right - left, bottom - top
            o.set_world_pos((left + right) / 2, (top + bottom) / 2, cam)
        self.transformed.emit()
        self.update()

    def mouseReleaseEvent(self, e):
        if self.painting:
            self.painting = False
            self.ed.mark_dirty()
            return
        if self.pan:
            self.pan = None
            self.setCursor(Qt.ArrowCursor)
            return
        if self.drag:
            moved = self.drag["moved"]
            self.drag = None
            if moved:
                self.finished.emit()

    def wheelEvent(self, e):
        before = self.s2w(e.position())
        steps = e.angleDelta().y() / 120.0
        self.zoom = max(0.1, min(6.0, self.zoom * (1.15 ** steps)))
        after = self.s2w(e.position())
        self.cx += before[0] - after[0]
        self.cy += before[1] - after[1]
        self.update()

    def keyPressEvent(self, e):
        k = e.key()
        o = self.ed.selected
        step = 10 if e.modifiers() & Qt.ShiftModifier else 1
        if k == Qt.Key_F:
            self.frame(o)
        elif o is not None and k in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            self.ed.checkpoint(f"nudge:{o.id}")
            dx = {Qt.Key_Left: -step, Qt.Key_Right: step}.get(k, 0)
            dy = {Qt.Key_Up: -step, Qt.Key_Down: step}.get(k, 0)
            x, y = o.world_pos(self.cam_pos())
            o.set_world_pos(x + dx, y + dy, self.cam_pos())
            self.transformed.emit()
            self.finished.emit()
            self.update()
        elif k in (Qt.Key_Delete, Qt.Key_Backspace):
            self.ed.delete_selected()
        else:
            super().keyPressEvent(e)
