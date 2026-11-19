"""Gravity, sideways speed, friction, bounce and collisions (solid blocks, one-way platforms, slopes, groups).

Falling is sub-stepped so fast or laggy frames can't tunnel through floors.
"""
import math

from . import tilemap
from .native import core as _core

GRAVITY = 1800.0
MAX_FALL = 1500.0
SUBSTEP = 1 / 120
MAX_SUBSTEPS = 12
BOUNCE_MIN_SPEED = 80.0     # impacts that would rebound slower than half of this just stop
ONE_WAY_GRACE = 6.0         # a body this far into a one-way platform still lands on it
SLOPE_SNAP = 14.0           # how far below a ramp surface a walking body is still lifted onto it


def overlap(ax, ay, aw, ah, bx, by, bw, bh):
    return abs(ax - bx) * 2 < aw + bw - 0.01 and abs(ay - by) * 2 < ah + bh - 0.01


def _rebound(speed, bounce):
    """Velocity after hitting something: reflected and scaled by bounce, or zero for weak hits."""
    if bounce > 0 and abs(speed) * bounce >= BOUNCE_MIN_SPEED / 2:
        return -speed * bounce
    return 0.0


def slope_surface(s, sx, sy, sw, sh, x):
    """Height (y) of a ramp's top surface at world x, or None when x is outside the ramp."""
    left, right = sx - sw / 2, sx + sw / 2
    if x < left or x > right:
        return None
    bottom = sy + sh / 2
    t = (x - left) / sw if s.slope == "up-right" else (right - x) / sw
    return bottom - t * sh


def step_py(live, bodies, prev, dt):
    """The reference version, in plain Python. Also used when the Rust core isn't available."""
    blocks, platforms, ramps = [], [], []
    for o in live:
        if not o.solid or o.trigger:
            continue
        sx, sy = o.world_pos()
        if o.kind == "tilemap":
            for cx, cy, w, h in tilemap.solid_rects(o):
                blocks.append((o, sx + cx, sy + cy, w, h))
            continue
        entry = (o, sx, sy, o.w, o.h)
        if o.slope:
            ramps.append(entry)
        elif o.one_way:
            platforms.append(entry)
        else:
            blocks.append(entry)
    n = max(1, min(MAX_SUBSTEPS, math.ceil(dt / SUBSTEP)))
    sub = dt / n
    for b in bodies:
        if b.dead:
            continue
        px, py = prev[id(b)]
        x, y = b.world_pos()
        x += b.vx * dt                     # sideways speed (set by push() or vx)
        hit_side = False
        # sideways: scripts move objects directly, so push back out of anything solid
        for s, sx, sy, sw, sh in blocks:
            if s is b or not b.collides_with(s):
                continue
            if overlap(x, py, b.w, b.h, sx, sy, sw, sh):
                if x > px:
                    x = sx - sw / 2 - b.w / 2
                    hit_side = True
                elif x < px:
                    x = sx + sw / 2 + b.w / 2
                    hit_side = True
        # the tall end of a ramp is a wall for bodies that are below the surface
        for s, sx, sy, sw, sh in ramps:
            if s is b or not b.collides_with(s):
                continue
            high_right = s.slope == "up-right"
            edge = sx + sw / 2 if high_right else sx - sw / 2
            if not overlap(x, py, b.w, b.h, sx, sy, sw, sh):
                continue
            surf = slope_surface(s, sx, sy, sw, sh, edge)
            feet = py + b.h / 2
            if surf is not None and feet > surf + SLOPE_SNAP:
                if high_right and x < px and x < edge + b.w / 2 and px >= edge:
                    x, hit_side = edge + b.w / 2, True
                elif not high_right and x > px and x > edge - b.w / 2 and px <= edge:
                    x, hit_side = edge - b.w / 2, True
        if hit_side:
            b.vx = _rebound(b.vx, b.bounce)
        # friction slows sideways speed while standing on something
        if b.on_ground and b.friction > 0 and b.vx:
            b.vx -= b.vx * min(1.0, b.friction * dt)
            if abs(b.vx) < 1.0:
                b.vx = 0.0
        # falling and jumping, in small slices
        grounded = False
        for _ in range(n):
            b.vy = min(b.vy + GRAVITY * sub, MAX_FALL)
            feet_before = y + b.h / 2
            ny = y + b.vy * sub
            grounded = False
            for s, sx, sy, sw, sh in blocks:
                if s is b or not b.collides_with(s):
                    continue
                if overlap(x, ny, b.w, b.h, sx, sy, sw, sh):
                    if b.vy > 0:
                        ny = sy - sh / 2 - b.h / 2
                        b.vy = _rebound(b.vy, b.bounce)
                        grounded = b.vy == 0.0
                    else:
                        ny = sy + sh / 2 + b.h / 2
                        b.vy = _rebound(b.vy, b.bounce)
            if b.vy >= 0:
                for s, sx, sy, sw, sh in platforms:
                    if s is b or not b.collides_with(s):
                        continue
                    top = sy - sh / 2
                    if (overlap(x, ny, b.w, b.h, sx, sy, sw, sh) and feet_before <= top + ONE_WAY_GRACE
                            and ny + b.h / 2 > top):
                        ny = top - b.h / 2
                        b.vy = _rebound(b.vy, b.bounce)
                        grounded = grounded or b.vy == 0.0
                for s, sx, sy, sw, sh in ramps:
                    if s is b or not b.collides_with(s):
                        continue
                    surf = slope_surface(s, sx, sy, sw, sh, x)
                    if surf is None:
                        continue
                    feet = ny + b.h / 2
                    if feet >= surf and feet_before <= surf + SLOPE_SNAP:
                        ny = surf - b.h / 2
                        b.vy = _rebound(b.vy, b.bounce)
                        grounded = grounded or b.vy == 0.0
            y = ny
        b.on_ground = grounded
        b.set_world_pos(x, y)


def _gather(live):
    """Sort the solid things into plain blocks, one-way platforms and ramps: lists of (object, x, y, w, h)."""
    blocks, platforms, ramps = [], [], []
    for o in live:
        if not o.solid or o.trigger:
            continue
        sx, sy = o.world_pos()
        if o.kind == "tilemap":
            for cx, cy, w, h in tilemap.solid_rects(o):
                blocks.append((o, sx + cx, sy + cy, w, h))
            continue
        entry = (o, sx, sy, o.w, o.h)
        (ramps if o.slope else platforms if o.one_way else blocks).append(entry)
    return blocks, platforms, ramps


def _pack(entries, ramp=False):
    out = []
    for o, x, y, w, h in entries:
        out += (x, y, w, h, id(o) & 0xFFFFFFFFFFFF, o.cgroup, o.cmask, 1.0 if ramp and o.slope == "up-right" else 0.0)
    return out


def step(live, bodies, prev, dt):
    """Move everything for one frame. Uses the Rust core when it's built, otherwise plain Python (same results)."""
    if _core is None or not bodies:
        return step_py(live, bodies, prev, dt)
    blocks, platforms, ramps = _gather(live)
    flat = []
    todo = []
    for b in bodies:
        if b.dead:
            continue
        px, py = prev[id(b)]
        x, y = b.world_pos()
        flat += (id(b) & 0xFFFFFFFFFFFF, x, y, px, py, b.w, b.h, b.vx, b.vy, b.bounce, b.friction,
                 1.0 if b.on_ground else 0.0, b.cgroup, b.cmask)
        todo.append(b)
    res = _core.step(_pack(blocks), _pack(platforms), _pack(ramps, True), flat, dt)
    for i, b in enumerate(todo):
        x, y, vx, vy, g = res[i * 5:i * 5 + 5]
        b.vx, b.vy, b.on_ground = vx, vy, g > 0.5
        b.set_world_pos(x, y)
