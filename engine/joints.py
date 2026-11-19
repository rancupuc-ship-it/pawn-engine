"""Joints: ropes, springs and welds between two objects. They are solved after physics every frame."""
import math

from pawnlang import PawnError

KINDS = ("rope", "spring", "weld")


class Joint:
    def __init__(self, kind, a, b, length, strength=60.0, visible=True, color="#d9c29a", width=3.0):
        self.kind, self.a, self.b = kind, a, b
        self.length, self.strength = length, strength
        self.visible, self.color, self.width = visible, color, width
        ax, ay = a.world_pos()
        bx, by = b.world_pos()
        self.offset = (bx - ax, by - ay)            # for welds
        self.dead = False

    def alive(self):
        return not self.dead and not self.a.dead and not self.b.dead


def _movable(o):
    return bool(o.body)


def solve(joints, dt):
    keep = []
    for j in joints:
        if not j.alive():
            continue
        keep.append(j)
        a, b = j.a, j.b
        ax, ay = a.world_pos()
        bx, by = b.world_pos()
        if j.kind == "weld":
            ox, oy = j.offset
            if _movable(b) or not _movable(a):
                b.set_world_pos(ax + ox, ay + oy)
                if _movable(b):
                    b.vx, b.vy = a.vx, a.vy
            else:
                a.set_world_pos(bx - ox, by - oy)
                a.vx, a.vy = b.vx, b.vy
            continue
        dx, dy = bx - ax, by - ay
        d = math.hypot(dx, dy)
        if d < 1e-6:
            continue
        nx, ny = dx / d, dy / d
        ma, mb = _movable(a), _movable(b)
        if not ma and not mb:
            continue
        if j.kind == "spring":
            force = j.strength * (d - j.length) * dt        # pulls together when stretched, pushes apart when squeezed
            share_a = 0.5 if (ma and mb) else (1.0 if ma else 0.0)
            share_b = 0.5 if (ma and mb) else (1.0 if mb else 0.0)
            a.vx += nx * force * share_a * 2
            a.vy += ny * force * share_a * 2
            b.vx -= nx * force * share_b * 2
            b.vy -= ny * force * share_b * 2
            damp = max(0.0, 1.0 - 2.0 * dt)
            for o in (a, b):
                if _movable(o):
                    o.vx *= damp
                    o.vy *= damp
        elif d > j.length:                                   # rope: only pulls when taut
            excess = d - j.length
            share_a = 0.5 if (ma and mb) else (1.0 if ma else 0.0)
            share_b = 1.0 - share_a if (ma or mb) else 0.0
            if ma:
                a.set_world_pos(ax + nx * excess * share_a, ay + ny * excess * share_a)
            if mb:
                b.set_world_pos(bx - nx * excess * share_b, by - ny * excess * share_b)
            # cancel the speed that would pull them further apart along the rope
            for o, sgn in ((a, -1.0), (b, 1.0)):             # sgn: direction from the other end toward this one
                if _movable(o):
                    out = o.vx * nx * sgn + o.vy * ny * sgn
                    if out > 0:
                        o.vx -= nx * sgn * out
                        o.vy -= ny * sgn * out
    joints[:] = keep


class JointHandle:
    """What scripts get back from rope(), spring() and weld()."""

    def __init__(self, joint):
        self.j = joint

    def pawn_get(self, name):
        j = self.j
        if name == "remove":
            return lambda: setattr(j, "dead", True)
        if name in ("length", "strength", "visible", "color", "width"):
            return getattr(j, name)
        if name == "kind":
            return j.kind
        if name == "active":
            return j.alive()
        raise PawnError(f"A joint has no '{name}'.", hint="try: remove(), length, strength, visible, color, width, kind, active")

    def pawn_set(self, name, value):
        j = self.j
        if name in ("length", "strength", "width"):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise PawnError(f"'{name}' must be a number.")
            setattr(j, name, max(0.0 if name != "length" else 1.0, float(value)))
        elif name == "visible":
            j.visible = bool(value)
        elif name == "color":
            if not isinstance(value, str):
                raise PawnError("'color' must be text like \"#ff0000\".")
            j.color = value
        else:
            raise PawnError(f"You can't change '{name}' on a joint.", hint="you can change: length, strength, visible, color, width")


def make(rt, kind, a, b, length=None, strength=None, show=True):
    if not (hasattr(a, "obj") and hasattr(b, "obj")):
        raise PawnError(f"{kind}() joins two objects, like  {kind}(find(\"A\"), find(\"B\"))")
    if a.obj is b.obj:
        raise PawnError(f"{kind}() needs two different objects.")
    ax, ay = a.obj.world_pos()
    bx, by = b.obj.world_pos()
    d = math.hypot(bx - ax, by - ay)
    if length is None:
        length = max(1.0, d)
    if isinstance(length, bool) or not isinstance(length, (int, float)) or length <= 0:
        raise PawnError("The length of a joint must be a number above zero.")
    j = Joint(kind, a.obj, b.obj, float(length), 60.0 if strength is None else max(0.0, float(strength)), bool(show))
    rt.joints.append(j)
    return JointHandle(j)


def lines(scene):
    """Every line the renderers must draw: (ax, ay, bx, by, width, color, style) with style 'rope', 'spring' or 'beam'."""
    out = []
    for j in getattr(scene, "joints", ()):
        if j.visible and j.alive() and j.kind != "weld":
            ax, ay = j.a.world_pos()
            bx, by = j.b.world_pos()
            out.append((ax, ay, bx, by, j.width, j.color, j.kind))
    for o in scene.all():
        if o.kind == "beam" and not o.dead and o.is_active() and o.text:
            target = scene.find_name(o.text)
            if target is not None and not target.dead and target is not o:
                ax, ay = o.world_pos()
                bx, by = target.world_pos()
                out.append((ax, ay, bx, by, max(1.0, o.h), o.color, "beam"))
    return out
