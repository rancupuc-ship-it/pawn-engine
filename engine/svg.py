"""A small SVG reader: turns vector shapes (lines, curves, arcs, circles) into polygons the engine can draw.

Understands <polygon>, <polyline>, <rect>, <circle>, <ellipse> and <path> (M L H V C S Q T A Z, upper and lower case).
Curves and arcs are flattened into short straight pieces, so they look smooth but become polygons.
"""
import math
import re
import xml.etree.ElementTree as ET


def _num(s):
    return [float(x) for x in re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", s)]


CURVE_STEPS = 14


def _bezier(pts, n=CURVE_STEPS):
    """Points along a quadratic or cubic Bezier curve (excluding the start point)."""
    out = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        if len(pts) == 3:
            x = u * u * pts[0][0] + 2 * u * t * pts[1][0] + t * t * pts[2][0]
            y = u * u * pts[0][1] + 2 * u * t * pts[1][1] + t * t * pts[2][1]
        else:
            x = u ** 3 * pts[0][0] + 3 * u * u * t * pts[1][0] + 3 * u * t * t * pts[2][0] + t ** 3 * pts[3][0]
            y = u ** 3 * pts[0][1] + 3 * u * u * t * pts[1][1] + 3 * u * t * t * pts[2][1] + t ** 3 * pts[3][1]
        out.append((x, y))
    return out


def _arc(x1, y1, rx, ry, rot, large, sweep, x2, y2):
    """Points along an SVG elliptical arc (excluding the start point)."""
    if (x1, y1) == (x2, y2):
        return []
    rx, ry = abs(rx), abs(ry)
    if rx == 0 or ry == 0:
        return [(x2, y2)]
    phi = math.radians(rot)
    cp, sp = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p, y1p = cp * dx + sp * dy, -sp * dx + cp * dy
    lam = (x1p ** 2) / (rx ** 2) + (y1p ** 2) / (ry ** 2)
    if lam > 1:
        k = math.sqrt(lam)
        rx, ry = rx * k, ry * k
    num = rx ** 2 * ry ** 2 - rx ** 2 * y1p ** 2 - ry ** 2 * x1p ** 2
    den = rx ** 2 * y1p ** 2 + ry ** 2 * x1p ** 2
    co = math.sqrt(max(0.0, num / den)) if den else 0.0
    if bool(large) == bool(sweep):
        co = -co
    cxp, cyp = co * rx * y1p / ry, -co * ry * x1p / rx
    cx = cp * cxp - sp * cyp + (x1 + x2) / 2
    cy = sp * cxp + cp * cyp + (y1 + y2) / 2

    def ang(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a

    t1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dt = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sweep and dt > 0:
        dt -= 2 * math.pi
    elif sweep and dt < 0:
        dt += 2 * math.pi
    n = max(6, int(abs(dt) / (math.pi / 2) * CURVE_STEPS))
    out = []
    for i in range(1, n + 1):
        t = t1 + dt * i / n
        ex, ey = rx * math.cos(t), ry * math.sin(t)
        out.append((cp * ex - sp * ey + cx, sp * ex + cp * ey + cy))
    out[-1] = (x2, y2)
    return out


def _path_points(d):
    """Returns (list of subpaths, curves_seen). Curves and arcs are flattened into short straight pieces."""
    subs, cur = [], []
    x = y = sx = sy = 0.0
    last_c = last_q = None          # previous control point, for the smooth commands S and T
    for cmd, args in re.findall(r"([MmLlHhVvZzCcSsQqTtAa])([^MmLlHhVvZzCcSsQqTtAa]*)", d):
        c = cmd.upper()
        rel = cmd.islower()
        if c == "Z":
            if cur:
                subs.append(cur)
            cur = []
            x, y = sx, sy
            last_c = last_q = None
            continue
        nums = _num(args) if c != "A" else _arc_nums(args)
        size = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7}[c]
        for i in range(0, len(nums) - size + 1, size):
            v = nums[i:i + size]
            ox, oy = (x, y) if rel else (0.0, 0.0)
            if c in "ML":
                x, y = v[0] + ox, v[1] + oy
                if c == "M" and i == 0:
                    if cur:
                        subs.append(cur)
                    cur = []
                    sx, sy = x, y
                cur.append((x, y))
                last_c = last_q = None
            elif c == "H":
                x = v[0] + (x if rel else 0)
                cur.append((x, y))
                last_c = last_q = None
            elif c == "V":
                y = v[0] + (y if rel else 0)
                cur.append((x, y))
                last_c = last_q = None
            elif c in "CS":
                if c == "C":
                    p1 = (v[0] + ox, v[1] + oy)
                    p2 = (v[2] + ox, v[3] + oy)
                    p3 = (v[4] + ox, v[5] + oy)
                else:
                    p1 = (2 * x - last_c[0], 2 * y - last_c[1]) if last_c else (x, y)
                    p2 = (v[0] + ox, v[1] + oy)
                    p3 = (v[2] + ox, v[3] + oy)
                if not cur:
                    cur.append((x, y))
                cur.extend(_bezier([(x, y), p1, p2, p3]))
                x, y = p3
                last_c, last_q = p2, None
            elif c in "QT":
                if c == "Q":
                    p1 = (v[0] + ox, v[1] + oy)
                    p2 = (v[2] + ox, v[3] + oy)
                else:
                    p1 = (2 * x - last_q[0], 2 * y - last_q[1]) if last_q else (x, y)
                    p2 = (v[0] + ox, v[1] + oy)
                if not cur:
                    cur.append((x, y))
                cur.extend(_bezier([(x, y), p1, p2]))
                x, y = p2
                last_q, last_c = p1, None
            elif c == "A":
                ex, ey = v[5] + ox, v[6] + oy
                if not cur:
                    cur.append((x, y))
                cur.extend(_arc(x, y, v[0], v[1], v[2], v[3], v[4], ex, ey))
                x, y = ex, ey
                last_c = last_q = None
    if cur:
        subs.append(cur)
    return subs, False


_NUM = re.compile(r"[\s,]*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)")
_FLAG = re.compile(r"[\s,]*([01])")


def _arc_nums(args):
    """Numbers of arc commands. The two flags are single digits that may be written without separators."""
    out, rest = [], args
    while True:
        group = []
        for kind in ("n", "n", "n", "f", "f", "n", "n"):
            m = (_NUM if kind == "n" else _FLAG).match(rest)
            if not m:
                return out
            group.append(float(m.group(1)))
            rest = rest[m.end():]
        out.extend(group)


def _fill(el, parent_fill):
    f = el.get("fill")
    if f is None:
        m = re.search(r"fill\s*:\s*([^;]+)", el.get("style", ""))
        f = m.group(1).strip() if m else None
    if f is None:
        f = parent_fill
    return f


def parse_svg(text):
    """Returns ([{"points": [(x, y)...], "color": "#rrggbb"}...], notes). Raises ValueError for unreadable files."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise ValueError(f"That isn't a valid SVG file ({e}).")
    shapes, notes = [], []

    def walk(el, fill):
        tag = el.tag.split("}")[-1]
        fill = _fill(el, fill)
        pts = []
        if tag in ("polygon", "polyline"):
            n = _num(el.get("points", ""))
            pts = [list(zip(n[0::2], n[1::2]))]
        elif tag == "rect":
            x, y = float(el.get("x", 0) or 0), float(el.get("y", 0) or 0)
            w, h = float(el.get("width", 0) or 0), float(el.get("height", 0) or 0)
            pts = [[(x, y), (x + w, y), (x + w, y + h), (x, y + h)]]
        elif tag in ("circle", "ellipse"):
            cx, cy = float(el.get("cx", 0) or 0), float(el.get("cy", 0) or 0)
            rx = float(el.get("r", el.get("rx", 0)) or 0)
            ry = float(el.get("r", el.get("ry", 0)) or 0)
            if rx > 0 and ry > 0:
                pts = [[(cx + rx * math.cos(2 * math.pi * i / 36), cy + ry * math.sin(2 * math.pi * i / 36))
                        for i in range(36)]]
        elif tag == "path":
            pts, _ = _path_points(el.get("d", ""))
        for sub in pts:
            if len(sub) >= 3:
                shapes.append({"points": sub, "color": _to_hex(fill)})
        for ch in el:
            walk(ch, fill)

    walk(root, None)
    return shapes, sorted(set(notes))


NAMED = {"red": "#ff0000", "green": "#008000", "blue": "#0000ff", "white": "#ffffff", "black": "#000000",
         "yellow": "#ffff00", "orange": "#ffa500", "purple": "#800080", "gray": "#808080", "grey": "#808080"}


def _to_hex(c):
    if not c or c == "none":
        return "#4fd1b5"
    c = c.strip().lower()
    if c in NAMED:
        return NAMED[c]
    if re.fullmatch(r"#[0-9a-f]{6}", c):
        return c
    if re.fullmatch(r"#[0-9a-f]{3}", c):
        return "#" + "".join(ch * 2 for ch in c[1:])
    m = re.fullmatch(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", c)
    if m:
        return "#%02x%02x%02x" % tuple(min(255, int(v)) for v in m.groups())
    return "#4fd1b5"


def normalise(points, scale=1.0):
    """Centre a shape on its box. Returns (centre_x, centre_y, width, height, points scaled to -0.5..0.5)."""
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    w, h = max(1e-6, x1 - x0), max(1e-6, y1 - y0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return cx * scale, cy * scale, w * scale, h * scale, [[(x - cx) / w, (y - cy) / h] for x, y in points]
