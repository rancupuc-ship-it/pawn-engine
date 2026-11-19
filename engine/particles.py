"""Particle emitters: dots or pictures that fly out of an object, change color and size, and fade.

A particle is a list: [x, y, vx, vy, age, life, rotation, spin, start_size, seed].
"""
import math
from array import array

from .native import core as _core

MAX_PARTICLES = 1500          # default for em_max; the setting can raise it

PRESETS = {
    "fire": dict(em_rate=90, em_life=0.9, em_speed=70, em_spread=40, em_dir=-90, em_size=14, em_gravity=-160,
                 em_color_end="#c0200a", em_alpha_end=0.0, em_size_end=0.1, em_size_var=0.3, em_add=True,
                 em_drag=0.5, em_wind=0, em_spin=0, em_shape="circle", em_radius=6),
    "smoke": dict(em_rate=25, em_life=2.5, em_speed=35, em_spread=30, em_dir=-90, em_size=18, em_gravity=-30,
                  em_color_end="#444444", em_alpha_end=0.0, em_size_end=2.5, em_size_var=0.3, em_add=False,
                  em_drag=0.4, em_wind=15, em_spin=0, em_shape="circle", em_radius=5),
    "sparks": dict(em_rate=60, em_life=0.7, em_speed=260, em_spread=70, em_dir=-90, em_size=4, em_gravity=700,
                   em_color_end="#ff4400", em_alpha_end=0.0, em_size_end=0.3, em_size_var=0.3, em_add=True,
                   em_drag=0.3, em_wind=0, em_spin=0, em_shape="point", em_radius=0),
    "rain": dict(em_rate=300, em_life=1.2, em_speed=500, em_spread=4, em_dir=100, em_size=3, em_gravity=900,
                 em_color_end="", em_alpha_end=0.6, em_size_end=1.0, em_size_var=0.3, em_add=False,
                 em_drag=0, em_wind=-40, em_spin=0, em_shape="line", em_radius=0),
    "snow": dict(em_rate=60, em_life=6, em_speed=30, em_spread=30, em_dir=90, em_size=6, em_gravity=25,
                 em_color_end="", em_alpha_end=0.3, em_size_end=1.0, em_size_var=0.6, em_add=False,
                 em_drag=0.2, em_wind=18, em_spin=40, em_shape="line", em_radius=0),
    "magic": dict(em_rate=45, em_life=1.4, em_speed=60, em_spread=360, em_dir=-90, em_size=8, em_gravity=-40,
                  em_color_end="#aa44ff", em_alpha_end=0.0, em_size_end=0.2, em_size_var=0.5, em_add=True,
                  em_drag=0.8, em_wind=0, em_spin=90, em_shape="circle", em_radius=14),
    "explosion": dict(em_rate=0, em_life=0.8, em_speed=380, em_spread=360, em_dir=-90, em_size=12, em_gravity=200,
                      em_color_end="#aa2200", em_alpha_end=0.0, em_size_end=0.2, em_size_var=0.5, em_add=True,
                      em_drag=2.2, em_wind=0, em_spin=0, em_shape="point", em_radius=0),
    "dust": dict(em_rate=20, em_life=1.8, em_speed=25, em_spread=360, em_dir=-90, em_size=10, em_gravity=-5,
                 em_color_end="", em_alpha_end=0.0, em_size_end=1.8, em_size_var=0.4, em_add=False,
                 em_drag=1.2, em_wind=10, em_spin=20, em_shape="circle", em_radius=10),
}
PRESET_COLORS = {"fire": "#ffb030", "smoke": "#999999", "sparks": "#ffe070", "rain": "#8ec8ff", "snow": "#ffffff",
                 "magic": "#66e0ff", "explosion": "#ffd060", "dust": "#c9b79c"}


def apply_preset(o, name):
    """Set all the particle settings of an emitter from a named preset. Returns False for an unknown name."""
    if name not in PRESETS:
        return False
    for k, v in PRESETS[name].items():
        setattr(o, k, v)
    o.color = PRESET_COLORS[name]
    o.em_on = PRESETS[name]["em_rate"] > 0
    return True


def rgba(s):
    """'#rrggbb' or '#rrggbbaa' (or short forms) as four numbers from 0 to 1. Anything else is white."""
    try:
        t = str(s).lstrip("#")
        if len(t) in (3, 4):
            t = "".join(c * 2 for c in t)
        if len(t) == 6:
            t += "ff"
        if len(t) != 8:
            return (1.0, 1.0, 1.0, 1.0)
        r, g, b, a = (int(t[i:i + 2], 16) / 255.0 for i in (0, 2, 4, 6))
        return (r, g, b, a)
    except ValueError:
        return (1.0, 1.0, 1.0, 1.0)


def spawn(o, rng, n):
    wx, wy = o.world_pos()
    if o.em_local:
        wx = wy = 0.0
    cap = int(o.em_max)
    for _ in range(int(n)):
        if len(o.parts) >= cap:
            break
        ox, oy = _offset(o, rng)
        a = math.radians(o.em_dir + (rng.random() - 0.5) * o.em_spread)
        sp = o.em_speed * (1.0 + (rng.random() * 2 - 1) * o.em_speed_var)
        life = max(0.05, o.em_life * (1.0 + (rng.random() * 2 - 1) * o.em_life_var))
        vx = math.cos(a) * sp + o.vx * o.em_inherit
        vy = math.sin(a) * sp + o.vy * o.em_inherit
        size = max(0.5, o.em_size * (1.0 + (rng.random() * 2 - 1) * o.em_size_var))
        spin = o.em_spin + (rng.random() * 2 - 1) * o.em_spin_var
        o.parts.append([wx + ox, wy + oy, vx, vy, 0.0, life, rng.random() * 360.0 if o.sprite else 0.0, spin, size, rng.random()])


def _offset(o, rng):
    shape = o.em_shape
    if shape == "circle" and o.em_radius > 0:
        r = o.em_radius * math.sqrt(rng.random())
        a = rng.random() * math.tau
        return math.cos(a) * r, math.sin(a) * r
    if shape == "box":
        return (rng.random() - 0.5) * o.w, (rng.random() - 0.5) * o.h
    if shape == "line":
        return (rng.random() - 0.5) * o.w, 0.0
    return 0.0, 0.0


def update(o, dt, rng):
    if o.em_on and o.em_rate > 0:
        o.em_acc += o.em_rate * dt
        n = int(o.em_acc)
        if n:
            o.em_acc -= n
            spawn(o, rng, min(n, 500))
    gy, wind = o.em_gravity, o.em_wind
    keep = max(0.0, 1.0 - o.em_drag * dt) if o.em_drag else 1.0
    alive = []
    for p in o.parts:
        p[4] += dt
        if p[4] >= p[5]:
            continue
        if keep != 1.0:
            p[2] *= keep
            p[3] *= keep
        p[2] += wind * dt
        p[3] += gy * dt
        p[0] += p[2] * dt
        p[1] += p[3] * dt
        p[6] += p[7] * dt
        alive.append(p)
    o.parts = alive


def look(o, opacity=1.0, uv=(0.0, 0.0, 1.0, 1.0), sheet=(1, 1)):
    """Everything the drawing code needs to know about how this emitter's particles look (a flat list of numbers)."""
    c0 = rgba(o.color)
    c1 = rgba(o.em_color_end) if o.em_color_end else c0
    kind = (6.0 if o.em_add else 2.0) if o.sprite else (5.0 if o.em_add else 1.0)
    return [c0[0], c0[1], c0[2], c0[3], c1[0], c1[1], c1[2], o.em_alpha_end * c0[3] if not o.em_color_end else o.em_alpha_end * c1[3],
            o.em_size_end, opacity, kind, uv[0], uv[1], uv[2], uv[3], float(sheet[0]), float(sheet[1])]


def pack_py(parts, lk, ox=0.0, oy=0.0):
    """Instances for the GPU (16 numbers each), in plain Python. Same output as the Rust version."""
    out = array("f")
    r0, g0, b0, a0, r1, g1, b1, a1, size_end, opacity, kind, u0, v0, u1, v1, cols, rows = lk
    cols, rows = max(1, int(cols)), max(1, int(rows))
    cells = cols * rows
    for x, y, _vx, _vy, age, life, rot, _spin, size0, seed in parts:
        t = age / life
        d = max(0.5, size0 * (1.0 + (size_end - 1.0) * t))
        if kind >= 2.0 and kind != 5.0:
            i = int(seed * cells) % cells
            cw, ch = (u1 - u0) / cols, (v1 - v0) / rows
            su, sv = u0 + (i % cols) * cw, v0 + (i // cols) * ch
            uv = (su, sv, su + cw, sv + ch)
        else:
            uv = (0.0, 0.0, 0.0, 0.0)
        out.extend((x + ox, y + oy, d, d, math.radians(rot), 1.0, kind, 0.0,
                    r0 + (r1 - r0) * t, g0 + (g1 - g0) * t, b0 + (b1 - b0) * t, (a0 + (a1 - a0) * t) * opacity,
                    uv[0], uv[1], uv[2], uv[3]))
    return out


def pack(parts, lk, ox=0.0, oy=0.0):
    if _core is not None and parts:
        data = array("f")
        data.frombytes(_core.pack_particles(parts, lk, ox, oy))
        return data
    return pack_py(parts, lk, ox, oy)
