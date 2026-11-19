"""What scripts see: 'self', other objects, the game table, the mouse and the camera."""
from pawnlang import PawnError, fmt, suggest
from . import animation, particles, tilemap
from .gameobject import particles_clean

NUMERIC_SET = {"width": "w", "w": "w", "height": "h", "h": "h", "angle": "angle", "vy": "vy", "vx": "vx",
               "friction": "friction", "bounce": "bounce"}
COLOR_SET = ("color", "back_color", "hover_color", "press_color", "text_color")
# names scripts use for the particle settings
PARTICLE_PROPS = {"rate": "em_rate", "lifetime": "em_life", "speed": "em_speed", "spread": "em_spread",
                  "direction": "em_dir", "gravity": "em_gravity", "particle_size": "em_size", "end_color": "em_color_end",
                  "end_alpha": "em_alpha_end", "end_size": "em_size_end", "spin": "em_spin", "drag": "em_drag",
                  "wind": "em_wind", "shape": "em_shape", "glow": "em_add", "follow": "em_local",
                  "shape_size": "em_radius", "inherit": "em_inherit", "max_particles": "em_max"}
PARTICLE_TEXT = ("em_color_end", "em_shape")
PARTICLE_FLAGS = ("em_add", "em_local")


GETTERS = ("x", "y", "width", "height", "angle", "color", "text", "size", "visible", "name", "vx", "vy",
           "on_ground", "sprite", "layer", "flip_x", "alpha", "tags", "frame", "anim", "playing", "friction", "bounce",
           "font", "value", "checked", "enabled", "anchor", "hovered", "pressed", "focused", "back_color",
           "hover_color", "press_color", "text_color", "solid", "trigger", "one_way", "cgroup", "cmask", "emitting", "tile_size", "slope", "parallax", "intensity", "flicker", "radius") + tuple(PARTICLE_PROPS)
METHODS = ("move", "jump", "push", "destroy", "touching", "distance_to", "hide", "show", "tag", "untag", "has_tag",
           "play_anim", "stop_anim", "burst", "set_tile", "get_tile", "tile_at", "clear_tiles", "fill_tiles", "preset")
SETTABLE = ("x, y, width, height, angle, color, text, size, visible, sprite, layer, flip_x, alpha, vx, vy, frame, "
            "friction, bounce, font, value, checked, enabled, anchor, back_color, hover_color, press_color, text_color, "
            "solid, trigger, one_way, cgroup, cmask, emitting, parallax, intensity, flicker, radius, "
            + ", ".join(PARTICLE_PROPS))


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _font_path(value):
    """'pixel.ttf' -> 'assets/fonts/pixel.ttf'; full paths and empty text stay as they are."""
    if value and "/" not in value and value.lower().endswith((".ttf", ".otf")):
        return "assets/fonts/" + value
    return value


class GameNS:
    """The shared 'game' table. Unset values start at 0."""

    def __init__(self):
        self.d = {}

    def pawn_get(self, name):
        return self.d.get(name, 0)

    def pawn_set(self, name, value):
        self.d[name] = value


class MouseNS:
    def __init__(self, rt):
        self.rt = rt

    def pawn_get(self, name):
        if name == "x":
            return self.rt.mx
        if name == "y":
            return self.rt.my
        if name == "down":
            return self.rt.mouse_down
        if name == "clicked":
            return self.rt.mouse_clicked
        raise PawnError(f"The mouse doesn't have '{name}'.", hint="try: x, y, down, clicked")

    def pawn_set(self, name, value):
        raise PawnError("You can't change the mouse.")


class ObjProxy:
    """What scripts see as 'self' or as another object."""

    def __init__(self, obj, rt):
        self.obj, self.rt = obj, rt

    def __eq__(self, other):
        return isinstance(other, ObjProxy) and other.obj is self.obj

    def __hash__(self):
        return id(self.obj)

    def __repr__(self):
        return f"<{self.obj.name}>"

    def pawn_get(self, name):
        o, rt = self.obj, self.rt
        if name == "x":
            return o.world_pos(rt.camv())[0]
        if name == "y":
            return o.world_pos(rt.camv())[1]
        if name in ("width", "w"):
            return o.w
        if name in ("height", "h"):
            return o.h
        if name == "angle":
            return o.angle
        if name == "color":
            return o.color
        if name == "text":
            return o.text
        if name == "size":
            return o.text_size
        if name == "visible":
            return o.active
        if name == "name":
            return o.name
        if name == "vy":
            return o.vy
        if name == "on_ground":
            return o.on_ground
        if name == "sprite":
            return o.sprite
        if name == "layer":
            return o.layer
        if name == "flip_x":
            return o.flip_x
        if name == "alpha":
            return o.alpha
        if name == "tags":
            return list(o.tags)
        if name == "vx":
            return o.vx
        if name in ("friction", "bounce", "solid", "trigger", "one_way", "cgroup", "cmask"):
            return getattr(o, name)
        if name == "frame":
            return o.frame
        if name == "anim":
            return o.anim_name
        if name == "playing":
            return bool(o.anim_name) and not o.anim_done
        if name == "font":
            return o.font
        if name == "value":
            return o.value
        if name == "checked":
            return o.checked
        if name == "enabled":
            return o.enabled
        if name == "anchor":
            return o.anchor
        if name == "hovered":
            return o.hovered
        if name == "pressed":
            return o.pressing
        if name == "focused":
            return o.focused
        if name in COLOR_SET:
            return getattr(o, name)
        if name in ("parallax", "intensity", "flicker"):
            return getattr(o, name)
        if name == "radius":
            return o.w / 2 if o.kind == "light" else o.radius
        if name in PARTICLE_PROPS:
            if o.kind != "particles":
                self._need("particle emitter", name)
            return getattr(o, PARTICLE_PROPS[name])
        if name == "preset":
            return self._preset
        if name == "emitting":
            return o.em_on
        if name == "tile_size":
            return o.tile_size
        if name == "slope":
            return o.slope or "none"
        if name == "burst":
            return lambda n=20: particles.spawn(o, rt.rng, max(0, min(500, int(n)))) if o.kind == "particles" else self._need("particles", "burst")
        if name in ("set_tile", "get_tile", "tile_at", "clear_tiles", "fill_tiles"):
            if o.kind != "tilemap":
                self._need("tile map", name)
            return getattr(self, "_" + name)
        if name == "play_anim":
            return lambda clip, restart=False: animation.play(o, str(clip), bool(restart))
        if name == "stop_anim":
            return lambda: animation.stop(o)
        if name == "push":
            return self._push
        if name == "move":
            return lambda dx, dy=0: self._move(dx, dy)
        if name == "jump":
            return self._jump
        if name == "destroy":
            return lambda: rt.destroy(o)
        if name == "touching":
            return lambda target: rt.touching(o, target)
        if name == "distance_to":
            return lambda other: rt.distance(self, other)
        if name == "hide":
            return lambda: self._set_active(False)
        if name == "show":
            return lambda: self._set_active(True)
        if name == "tag":
            return self._tag
        if name == "untag":
            return self._untag
        if name == "has_tag":
            return lambda t: str(t) in o.tags
        raise PawnError(f"'{o.name}' doesn't have anything called '{name}'.",
                        hint=suggest(name, list(GETTERS) + list(METHODS)) or "try: x, y, width, height, color, text")

    def pawn_set(self, name, value):
        o, rt = self.obj, self.rt
        num = _num(value)
        if name in ("x", "y"):
            if not num:
                raise PawnError(f"'{name}' must be a number.")
            wx, wy = o.world_pos(rt.camv())
            if name == "x":
                wx = float(value)
            else:
                wy = float(value)
            o.set_world_pos(wx, wy, rt.camv())
        elif name in NUMERIC_SET:
            if not num:
                raise PawnError(f"'{name}' must be a number.")
            setattr(o, NUMERIC_SET[name], float(value))
        elif name == "size":
            if not num:
                raise PawnError("'size' must be a number.")
            o.text_size = max(1, int(value))
        elif name == "layer":
            if not num:
                raise PawnError("'layer' must be a number.")
            o.layer = int(value)
        elif name == "alpha":
            if not num:
                raise PawnError("'alpha' must be a number from 0 (invisible) to 1 (solid).")
            o.alpha = max(0.0, min(1.0, float(value)))
        elif name == "flip_x":
            o.flip_x = bool(value)
        elif name in COLOR_SET:
            setattr(o, name, str(value))
        elif name == "sprite":
            o.sprite = str(value)
        elif name == "frame":
            if not num:
                raise PawnError("'frame' must be a number.")
            animation.stop(o)
            o.frame = int(value) % animation.cell_count(o)
        elif name == "font":
            o.font = _font_path(str(value))
        elif name == "value":
            if not num:
                raise PawnError("'value' must be a number from 0 to 1.")
            o.value = max(0.0, min(1.0, float(value)))
        elif name == "checked":
            o.checked = bool(value)
        elif name in ("parallax", "intensity", "flicker"):
            if not num:
                raise PawnError(f"'{name}' must be a number.")
            v = float(value)
            setattr(o, name, v if name == "parallax" else max(0.0, min(2.0 if name == "intensity" else 1.0, v)))
        elif name == "radius":
            if not num:
                raise PawnError("'radius' must be a number.")
            if o.kind == "light":
                o.w = o.h = max(2.0, float(value) * 2)
            else:
                o.radius = int(value)
        elif name in PARTICLE_PROPS:
            if o.kind != "particles":
                self._need("particle emitter", name)
            field = PARTICLE_PROPS[name]
            if field in PARTICLE_FLAGS:
                value = bool(value)
            elif field in PARTICLE_TEXT:
                if not isinstance(value, str):
                    raise PawnError(f"'{name}' must be text.", hint="for example:  " + ("\"#ff0000\"" if field == "em_color_end" else "\"circle\""))
                if field == "em_shape" and value not in ("point", "circle", "box", "line"):
                    raise PawnError(f"'{value}' isn't a particle shape.", hint="try: point, circle, box or line")
            elif not num:
                raise PawnError(f"'{name}' must be a number.")
            setattr(o, field, value)
            particles_clean(o)
        elif name == "emitting":
            o.em_on = bool(value)
        elif name in ("solid", "trigger", "one_way"):
            setattr(o, name, bool(value))
        elif name == "cgroup":
            if not num or not 1 <= int(value) <= 8:
                raise PawnError("'cgroup' must be a number from 1 to 8.")
            o.cgroup = int(value)
        elif name == "cmask":
            if not num or not 0 <= int(value) <= 255:
                raise PawnError("'cmask' must be a number from 0 to 255 (a bit for each group 1-8).")
            o.cmask = int(value)
        elif name == "enabled":
            o.enabled = bool(value)
        elif name == "anchor":
            from .gameobject import ANCHORS
            if value not in ANCHORS:
                raise PawnError(f"'{value}' isn't an anchor.", hint="try: " + ", ".join(ANCHORS))
            o.anchor = value
        elif name == "text":
            o.text = value if isinstance(value, str) else fmt(value)
        elif name == "visible":
            self._set_active(bool(value))
        else:
            raise PawnError(f"You can't change '{name}' on '{o.name}'.", hint="you can change: " + SETTABLE)

    def _preset(self, name):
        o = self.obj
        if o.kind != "particles":
            self._need("particle emitter", "preset")
        if not particles.apply_preset(o, str(name)):
            raise PawnError(f"There is no particle preset called '{name}'.", hint="try: " + ", ".join(particles.PRESETS))

    def _need(self, kind, what):
        raise PawnError(f"'{self.obj.name}' isn't a {kind}, so it can't {what}().",
                        hint=f"add a {kind} object from Object > Add")

    def _set_tile(self, col, row, n=0):
        if not (_num(col) and _num(row) and _num(n)):
            raise PawnError("set_tile() needs numbers, like  map.set_tile(3, 2, 5)   (use -1 to erase)")
        tilemap.set_tile(self.obj, int(col), int(row), int(n))

    def _get_tile(self, col, row):
        if not (_num(col) and _num(row)):
            raise PawnError("get_tile() needs numbers, like  map.get_tile(3, 2)")
        return tilemap.get(self.obj, int(col), int(row))

    def _tile_at(self, x, y):
        if not (_num(x) and _num(y)):
            raise PawnError("tile_at() needs a world position, like  map.tile_at(player.x, player.y + 20)")
        c, r = tilemap.cell_at(self.obj, float(x), float(y))
        return tilemap.get(self.obj, c, r)

    def _clear_tiles(self):
        tilemap.clear(self.obj)

    def _fill_tiles(self, text, legend):
        if not isinstance(text, str) or not isinstance(legend, dict):
            raise PawnError("fill_tiles() needs text and a table, like  map.fill_tiles(\"#..#\", {\"#\": 1})")
        tilemap.from_text(self.obj, text, legend)

    def _set_active(self, on):
        self.obj.active = on
        self.rt.invalidate()

    def _tag(self, *names):
        for t in names:
            t = str(t)
            if t not in self.obj.tags:
                self.obj.tags.append(t)
        self.rt.invalidate()

    def _untag(self, *names):
        for t in names:
            if str(t) in self.obj.tags:
                self.obj.tags.remove(str(t))
        self.rt.invalidate()

    def _push(self, dx, dy=0):
        if not (_num(dx) and _num(dy)):
            raise PawnError("push() needs numbers, like  self.push(200, -400)")
        self.obj.vx += float(dx)
        self.obj.vy += float(dy)
        self.obj.on_ground = False if dy else self.obj.on_ground

    def _move(self, dx, dy):
        x, y = self.obj.world_pos(self.rt.camv())
        self.obj.set_world_pos(x + dx, y + dy, self.rt.camv())

    def _jump(self, power):
        if self.obj.on_ground:
            self.obj.vy = -abs(power)
            self.obj.on_ground = False


class CameraProxy:
    def __init__(self, rt):
        self.rt = rt

    def _obj(self):
        c = self.rt.cam_obj
        if c is None:
            raise PawnError("This scene has no camera. Add one from Object > Add > Camera.")
        return c

    def pawn_get(self, name):
        c = self._obj()
        if name in ("x", "y"):
            return c.world_pos()[0 if name == "x" else 1]
        if name == "zoom":
            return c.zoom
        if name == "shake":
            return self.rt.shake
        raise PawnError(f"The camera doesn't have '{name}'.", hint="try: x, y, zoom, shake")

    def pawn_set(self, name, value):
        c = self._obj()
        if name in ("x", "y", "zoom") and not _num(value):
            raise PawnError(f"The camera's '{name}' must be a number.")
        if name in ("x", "y"):
            wx, wy = c.world_pos()
            c.set_world_pos(float(value) if name == "x" else wx, float(value) if name == "y" else wy)
        elif name == "zoom":
            c.zoom = max(0.1, float(value))
        else:
            raise PawnError(f"You can't change '{name}' on the camera.", hint="you can change: x, y, zoom")
