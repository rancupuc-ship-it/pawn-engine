"""The functions every script can call (print, random, find, spawn, ...)."""
import math

from pawnlang import PawnError, PairList, fmt, type_name
from pawnlang.values import is_num
from .signals import Signal
from . import effects, gamepad, joints, queries, savedata

MAX_RANGE = 100000


def build_shared(rt):
    """Returns the dict of builtins for one Runtime."""

    def need_num(*vals):
        for v in vals:
            if not is_num(v):
                raise PawnError(f"I expected a number but got {fmt(v)}.")

    def p_print(*a):
        rt.console(" ".join(x if isinstance(x, str) else fmt(x) for x in a), "print")

    def clamp(v, lo, hi):
        need_num(v, lo, hi)
        return max(lo, min(hi, v))

    def xy(v, what="angle_to"):
        if hasattr(v, "pawn_get"):
            return float(v.pawn_get("x")), float(v.pawn_get("y"))
        if isinstance(v, dict) and "x" in v and "y" in v:
            need_num(v["x"], v["y"])
            return float(v["x"]), float(v["y"])
        raise PawnError(f"{what}() needs two objects, or two points like  {{x = 0, y = 0}}.")

    def angle_to(a, b, c=None, d=None):
        """Angle in degrees from one point to another (0 = right, 90 = down, -90 = up)."""
        if c is not None:
            need_num(a, b, c, d)
            return math.degrees(math.atan2(d - b, c - a))
        (x1, y1), (x2, y2) = xy(a), xy(b)
        return math.degrees(math.atan2(y2 - y1, x2 - x1))

    def p_shuffle(lst):
        if not isinstance(lst, list):
            raise PawnError("shuffle() needs a list.")
        out = list(lst)
        rt.rng.shuffle(out)
        return out

    def wrap(v, lo, hi):
        need_num(v, lo, hi)
        if hi == lo:
            return lo
        return lo + (v - lo) % (hi - lo)

    def approach(cur, target, step):
        need_num(cur, target, step)
        step = abs(step)
        return min(target, cur + step) if cur < target else max(target, cur - step)

    def smoothstep(a, b, t):
        need_num(a, b, t)
        k = 0.0 if a == b else max(0.0, min(1.0, (t - a) / (b - a)))
        return k * k * (3 - 2 * k)

    def map_range(v, a1, b1, a2, b2):
        need_num(v, a1, b1, a2, b2)
        return a2 if a1 == b1 else a2 + (v - a1) / (b1 - a1) * (b2 - a2)

    def snap(v, step):
        need_num(v, step)
        return v if step == 0 else round(v / step) * step

    def p_len(v):
        if isinstance(v, (list, str, dict)):
            return len(v)
        raise PawnError("len() only works on lists, tables and text.")

    def p_float(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            raise PawnError(f"I can't turn {fmt(v)} into a number.")

    def p_int(v):
        return int(p_float(v))

    def sign(v):
        need_num(v)
        return (v > 0) - (v < 0)

    def p_round(v, n=0):
        need_num(v, n)
        return round(v, int(n)) if n else int(round(v))

    def p_range(a, b=None, step=1):
        need_num(a, step)
        if b is None:
            a, b = 0, a
        need_num(b)
        if step == 0:
            raise PawnError("range() can't step by zero.")
        if abs((b - a) / step) > MAX_RANGE:
            raise PawnError(f"range() can make at most {MAX_RANGE} numbers.")
        out, v = [], a
        while (v < b) if step > 0 else (v > b):
            out.append(v)
            v += step
        return out

    def need_table(v, what):
        if not isinstance(v, (dict, list)):
            raise PawnError(f"{what}() needs a table or a list.")
        return v

    def p_pairs(t):
        need_table(t, "pairs")
        items = t.items() if isinstance(t, dict) else enumerate(t)
        return PairList([k, v] for k, v in items)

    def p_keys(t):
        need_table(t, "keys")
        return list(t.keys()) if isinstance(t, dict) else list(range(len(t)))

    def p_values(t):
        need_table(t, "values")
        return list(t.values()) if isinstance(t, dict) else list(t)

    def p_sorted(lst):
        if not isinstance(lst, list):
            raise PawnError("sorted() needs a list.")
        try:
            return sorted(lst)
        except TypeError:
            raise PawnError("A list can only be sorted when it holds all numbers or all text.")

    def p_sum(lst):
        if not isinstance(lst, list) or not all(is_num(x) for x in lst):
            raise PawnError("sum() needs a list of numbers.")
        return sum(lst)

    def audio(name):
        a = rt.audio
        return getattr(a, name, None) if a is not None else None

    def call_audio(name, *args):
        fn = audio(name)
        if fn:
            fn(*args)

    def p_play(name, vol=1):
        need_num(vol)
        if rt.play_sound:
            rt.play_sound(str(name))
        else:
            call_audio("play_sound", str(name), max(0.0, min(1.0, float(vol))))

    def p_play_music(name, loop=True, vol=1):
        need_num(vol)
        call_audio("play_music", str(name), bool(loop), max(0.0, min(1.0, float(vol))))

    def p_volume(kind, v=None):
        if v is None:
            kind, v = "master", kind
        need_num(v)
        if kind not in ("master", "music", "sound"):
            raise PawnError("volume() can set:  master, music or sound.", hint='like: volume("music", 0.5)')
        call_audio("set_volume", kind, max(0.0, min(1.0, float(v))))

    def p_get_volume(kind="master"):
        fn = audio("get_volume")
        if kind not in ("master", "music", "sound"):
            raise PawnError("get_volume() can read:  master, music or sound.")
        return fn(kind) if fn else 1.0

    def p_fade_music(vol=0, seconds=1, stop=False):
        need_num(vol, seconds)
        call_audio("fade_music", max(0.0, min(1.0, float(vol))), float(seconds), bool(stop))

    def p_music_playing():
        fn = audio("music_playing")
        return bool(fn()) if fn else False

    def p_breakpoint(note=""):
        inst = rt.ctx.inst
        where = (inst.file if inst is not None and getattr(inst, "file", None) else "a script")
        rt.break_msg = f"Paused by breakpoint() in {where}" + (f": {fmt(note)}" if note != "" else "")

    def p_darkness(v=None):
        if v is None:
            return rt.scene.darkness
        need_num(v)
        rt.scene.darkness = max(0.0, min(1.0, float(v)))

    def p_ambient(c=None):
        if c is None:
            return rt.scene.ambient
        if not isinstance(c, str):
            raise PawnError('ambient() needs a color like "#101030".')
        rt.scene.ambient = c

    def p_shake(amount=8, seconds=0.3):
        need_num(amount, seconds)
        rt.shake(amount, seconds)

    def p_load_game(slot="slot1"):
        d = savedata.load(rt.project, slot)
        if d is None:
            return False
        rt.game.d.update(d)
        return True

    def p_seed(n):
        rt.rng.seed(n)

    def p_event(name):
        name = str(name)
        sig = rt.events.get(name)
        if sig is None:
            sig = rt.events[name] = Signal(rt, name)
        return sig

    def pad_name(name):
        name = str(name).lower()
        if name not in gamepad.BUTTONS:
            raise PawnError(f"'{name}' isn't a pad button.", hint="try: " + ", ".join(gamepad.BUTTONS))
        return name

    def pad(name, index=1):
        name = pad_name(name)
        st = rt.pad_state(index)
        return st is not None and name in st["buttons"]

    def pad_pressed(name, index=1):
        name = pad_name(name)
        st = rt.pad_state(index)
        if st is None or name not in st["buttons"]:
            return False
        before = rt.pads_prev[index - 1] if index <= len(rt.pads_prev) else None
        return before is None or name not in before["buttons"]

    def pad_axis(name, index=1):
        name = str(name).lower()
        if name not in gamepad.AXES:
            raise PawnError(f"'{name}' isn't a pad stick or trigger.", hint="try: " + ", ".join(gamepad.AXES))
        st = rt.pad_state(index)
        return 0.0 if st is None else st["axes"].get(name, 0.0)

    def pad_rumble(left=1.0, right=None, index=1):
        if rt.rumble_fn is not None:
            st = rt.pad_state(index)
            if st is not None:
                rt.rumble_fn(st.get("index", index - 1), float(left), float(left if right is None else right))

    ray, ray_dir, can_see = queries.pawn_raycast(rt)
    cooldowns = {}

    def can_use(name, seconds):
        """True (and starts the wait) when `name` is ready; false while it is still cooling down."""
        need_num(seconds)
        key = (id(rt.ctx.inst), str(name))
        if rt.time >= cooldowns.get(key, -1e18):
            cooldowns[key] = rt.time + seconds
            return True
        return False

    def wait_left(name):
        return max(0.0, cooldowns.get((id(rt.ctx.inst), str(name)), 0.0) - rt.time)

    return {
        "print": p_print,
        "rope": lambda a, b, length=None, show=True: joints.make(rt, "rope", a, b, length, None, show),
        "spring": lambda a, b, length=None, strength=None, show=True: joints.make(rt, "spring", a, b, length, strength, show),
        "weld": lambda a, b, show=False: joints.make(rt, "weld", a, b, None, None, show),
        "effect": lambda name, a=1.0, b=None: effects.set_effect(rt.effects, name, a, b),
        "clear_effects": lambda: rt.effects.clear(),
        "pad": pad, "pad_pressed": pad_pressed, "pad_axis": pad_axis, "pad_rumble": pad_rumble,
        "pad_connected": lambda index=1: rt.pad_state(index) is not None, "pad_count": lambda: len(rt.pads),
        "spawn_point": rt.spawn_point, "respawn": rt.respawn,
        "raycast": ray, "raycast_dir": ray_dir, "can_see": can_see,
        "find_path": lambda a, b, cell=32, size=0: queries.find_path(rt, a, b, cell, size),
        "can_use": can_use, "wait_left": wait_left,
        "key": lambda name: str(name).lower() in rt.down,
        "pressed": lambda name: str(name).lower() in rt.pressed,
        "game": rt.game, "mouse": rt.mouse, "camera": rt.camera,
        "dt": 1 / 60, "pi": math.pi,
        "seconds": lambda: rt.time,
        "find": rt.find, "all": rt.all_named, "tagged": lambda t: rt.all_named("#" + str(t)),
        "spawn": rt.spawn,
        "distance": rt.distance,
        "random": lambda a=0, b=1: rt.rng.uniform(a, b),
        "random_int": lambda a, b: rt.rng.randint(int(a), int(b)),
        "choose": lambda lst: rt.rng.choice(lst) if lst else None,
        "seed": p_seed,
        "round": p_round,
        "floor": lambda v: math.floor(v), "ceil": lambda v: math.ceil(v),
        "abs": lambda v: abs(v), "min": min, "max": max, "clamp": clamp, "sign": sign,
        "sqrt": lambda v: math.sqrt(v), "sin": math.sin, "cos": math.cos,
        "lerp": lambda a, b, t: a + (b - a) * t,
        "angle_to": angle_to, "shuffle": p_shuffle, "wrap": wrap, "approach": approach, "smoothstep": smoothstep,
        "map_range": map_range, "snap": snap, "chance": lambda p=0.5: rt.rng.random() < p,
        "atan2": lambda y, x: math.degrees(math.atan2(y, x)), "radians": math.radians, "degrees": math.degrees,
        "tan": math.tan,
        "len": p_len, "str": lambda v: fmt(v), "int": p_int, "number": p_float,
        "type": type_name,
        "range": p_range, "pairs": p_pairs, "keys": p_keys, "values": p_values,
        "sorted": p_sorted, "sum": p_sum,
        "signal": lambda: Signal(rt), "event": p_event,
        "require": rt.require,
        "play": p_play, "play_music": p_play_music,
        "stop_music": lambda: call_audio("stop_music"),
        "volume": p_volume, "get_volume": p_get_volume,
        "fade_music": p_fade_music, "music_playing": p_music_playing,
        "pause_music": lambda: call_audio("pause_music"), "resume_music": lambda: call_audio("resume_music"),
        "mute": lambda on=True: call_audio("mute", bool(on)),
        "restart": rt.request_restart,
        "load_scene": rt.request_scene,
        "shake": p_shake,
        "breakpoint": p_breakpoint, "darkness": p_darkness, "ambient": p_ambient,
        "save_game": lambda slot="slot1": savedata.save(rt.project, slot, rt.game.d),
        "load_game": p_load_game, "has_save": lambda slot="slot1": savedata.exists(rt.project, slot),
        "delete_save": lambda slot="slot1": savedata.delete(rt.project, slot),
        "saves": lambda: savedata.slots(rt.project),
        "scene_name": lambda: rt.scene_name,
        "typing": lambda: rt.ui.focus is not None,
        "over_ui": rt.ui.over_ui,
    }
