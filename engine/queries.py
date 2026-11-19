"""Questions a game asks about its world: can I see that? what's in the way? how do I walk there?"""
import math

from . import physics
from .native import core as _core
from pawnlang import PawnError

MAX_CELLS = 250_000          # biggest path grid (cells); a bigger world needs a bigger cell size


def _point(v, what):
    """(x, y, ignored object or None) from an object or a table like {x = 1, y = 2}."""
    if hasattr(v, "pawn_get") and hasattr(v, "obj"):
        return float(v.pawn_get("x")), float(v.pawn_get("y")), v.obj
    if isinstance(v, dict) and isinstance(v.get("x"), (int, float)) and isinstance(v.get("y"), (int, float)):
        return float(v["x"]), float(v["y"]), None
    raise PawnError(f"{what}() needs an object or a point like  {{x = 10, y = 20}}.")


def _solids(rt, ignore=()):
    blocks, _platforms, ramps = physics._gather(rt._live())
    return [e for e in blocks + ramps if e[0] not in ignore]


def hit_box(x1, y1, x2, y2, cx, cy, w, h):
    """Where the segment (x1,y1)-(x2,y2) first enters a box, as a fraction 0..1 of its length, or None."""
    dx, dy = x2 - x1, y2 - y1
    lo, hi = 0.0, 1.0
    for p, d, a, b in ((x1, dx, cx - w / 2, cx + w / 2), (y1, dy, cy - h / 2, cy + h / 2)):
        if abs(d) < 1e-12:
            if p < a or p > b:
                return None
            continue
        t0, t1 = (a - p) / d, (b - p) / d
        if t0 > t1:
            t0, t1 = t1, t0
        lo, hi = max(lo, t0), min(hi, t1)
        if lo > hi:
            return None
    return lo


def raycast(rt, x1, y1, x2, y2, ignore=()):
    """The first solid thing on the line, as a table, or {hit = false}."""
    best, who = None, None
    for o, sx, sy, sw, sh in _solids(rt, ignore):
        t = hit_box(x1, y1, x2, y2, sx, sy, sw, sh)
        if t is not None and (best is None or t < best):
            best, who = t, o
    length = math.hypot(x2 - x1, y2 - y1)
    if best is None:
        return {"hit": False, "x": x2, "y": y2, "distance": length, "object": None}
    from .proxies import ObjProxy
    return {"hit": True, "x": x1 + (x2 - x1) * best, "y": y1 + (y2 - y1) * best, "distance": length * best,
            "object": ObjProxy(who, rt)}


def pawn_raycast(rt):
    def ray(a, b=None, c=None, d=None):
        if c is not None:
            for v in (a, b, c, d):
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    raise PawnError("raycast() needs two objects/points, or four numbers: x1, y1, x2, y2.")
            return raycast(rt, float(a), float(b), float(c), float(d))
        x1, y1, o1 = _point(a, "raycast")
        x2, y2, o2 = _point(b, "raycast")
        return raycast(rt, x1, y1, x2, y2, tuple(o for o in (o1, o2) if o is not None))

    def ray_dir(a, angle, distance):
        x1, y1, o1 = _point(a, "raycast_dir")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in (angle, distance)):
            raise PawnError("raycast_dir(from, angle, distance) needs numbers for the angle and distance.")
        r = math.radians(angle)
        return raycast(rt, x1, y1, x1 + math.cos(r) * distance, y1 + math.sin(r) * distance, (o1,) if o1 else ())

    def can_see(a, b):
        return not ray(a, b)["hit"]

    return ray, ray_dir, can_see


# ---- pathfinding ---------------------------------------------------------------------------
def _astar_py(blocked, w, h, sx, sy, gx, gy):
    import heapq
    if not (0 <= sx < w and 0 <= sy < h and 0 <= gx < w and 0 <= gy < h) or blocked[gy * w + gx]:
        return []

    def hf(x, y):
        dx, dy = abs(x - gx), abs(y - gy)
        return max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)
    g = {(sx, sy): 0.0}
    came = {}
    heap = [(hf(sx, sy), sx, sy)]
    while heap:
        _f, x, y = heapq.heappop(heap)
        if (x, y) == (gx, gy):
            out = [(x, y)]
            while (x, y) in came:
                x, y = came[(x, y)]
                out.append((x, y))
            return out[::-1]
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nx, ny = x + dx, y + dy
            if not (0 <= nx < w and 0 <= ny < h) or blocked[ny * w + nx]:
                continue
            if dx and dy and (blocked[y * w + x + dx] or blocked[(y + dy) * w + x]):
                continue
            ng = g[(x, y)] + (math.sqrt(2) if dx and dy else 1.0)
            if ng < g.get((nx, ny), 1e18):
                g[(nx, ny)] = ng
                came[(nx, ny)] = (x, y)
                heapq.heappush(heap, (ng + hf(nx, ny), nx, ny))
    return []


def find_path(rt, a, b, cell=32, size=0):
    """Walk-around route from a to b as a list of {x, y} points ([] when there is no way).

    Solid objects are walls. `cell` is the grid size (smaller = more exact, slower). `size` keeps the route
    that many pixels away from walls, for bigger characters.
    """
    x1, y1, o1 = _point(a, "find_path")
    x2, y2, o2 = _point(b, "find_path")
    if isinstance(cell, bool) or not isinstance(cell, (int, float)) or cell < 4:
        raise PawnError("find_path's cell size must be a number, 4 or more.")
    cell = float(cell)
    pad = float(size) if isinstance(size, (int, float)) and not isinstance(size, bool) else 0.0
    walls = _solids(rt, tuple(o for o in (o1, o2) if o is not None))
    xs = [x1, x2] + [e[1] - e[3] / 2 for e in walls] + [e[1] + e[3] / 2 for e in walls]
    ys = [y1, y2] + [e[2] - e[4] / 2 for e in walls] + [e[2] + e[4] / 2 for e in walls]
    margin = cell * 6
    left, top = min(xs) - margin, min(ys) - margin
    w = int((max(xs) + margin - left) / cell) + 1
    h = int((max(ys) + margin - top) / cell) + 1
    if w * h > MAX_CELLS:
        raise PawnError("find_path: the world is too big for this cell size.", hint="use a bigger cell: find_path(a, b, 64)")
    blocked = bytearray(w * h)
    for _o, cx, cy, cw, ch in walls:
        c0 = max(0, int((cx - cw / 2 - pad - left) / cell))
        c1 = min(w - 1, int((cx + cw / 2 + pad - left - 1e-6) / cell))
        r0 = max(0, int((cy - ch / 2 - pad - top) / cell))
        r1 = min(h - 1, int((cy + ch / 2 + pad - top - 1e-6) / cell))
        for r in range(r0, r1 + 1):
            row = r * w
            blocked[row + c0:row + c1 + 1] = b"\x01" * (c1 - c0 + 1)
    sx, sy = int((x1 - left) / cell), int((y1 - top) / cell)
    gx, gy = int((x2 - left) / cell), int((y2 - top) / cell)
    blocked[sy * w + sx] = 0                  # you can always leave the spot you're standing on
    if _core is not None:
        flat = _core.astar(bytes(blocked), w, h, sx, sy, gx, gy)
        cells = list(zip(flat[0::2], flat[1::2]))
    else:
        cells = _astar_py(blocked, w, h, sx, sy, gx, gy)
    if not cells:
        return []
    pts = [(left + (cx + 0.5) * cell, top + (cy + 0.5) * cell) for cx, cy in cells]
    pts[0] = (x1, y1)
    pts[-1] = (x2, y2)
    # drop points that lie on a straight line between their neighbors
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        (px, py), (cx, cy), (nx, ny) = out[-1], pts[i], pts[i + 1]
        if abs((cx - px) * (ny - cy) - (cy - py) * (nx - cx)) > 1e-6:
            out.append(pts[i])
    out.append(pts[-1])
    return [{"x": x, "y": y} for x, y in out]
