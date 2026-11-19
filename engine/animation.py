"""Sprite-sheet animation: named clips that step through the pictures of a sheet."""
import re

from pawnlang import PawnError, suggest


def parse_anims(text):
    """Read the Inspector's animation text. One clip per line:   run = 0-3 @ 10 loop    idle = 4 @ 1

    Returns {"run": {"frames": [0, 1, 2, 3], "fps": 10.0, "loop": True}, ...}. Raises ValueError with a friendly
    message pointing at the bad line.
    """
    out = {}
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        m = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([0-9,\-\s]+?)\s*(?:@\s*([0-9.]+))?\s*(loop|once)?", line)
        if not m:
            raise ValueError(f"Line {n}: write a clip like   run = 0-3 @ 10 loop")
        name, spec, fps, mode = m.groups()
        frames = []
        for part in spec.replace(" ", "").split(","):
            if not part:
                continue
            r = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
            if not r:
                raise ValueError(f"Line {n}: '{part}' isn't a frame number or a range like 0-3")
            a, b = int(r.group(1)), int(r.group(2) if r.group(2) is not None else r.group(1))
            frames.extend(range(a, b + 1) if a <= b else range(a, b - 1, -1))
        if not frames:
            raise ValueError(f"Line {n}: '{name}' needs at least one frame number")
        out[name] = {"frames": frames, "fps": float(fps) if fps else 8.0, "loop": mode != "once"}
    return out


def _spec(frames):
    """[0, 1, 2, 3, 7] -> '0-3,7'"""
    parts, i = [], 0
    while i < len(frames):
        j = i
        while j + 1 < len(frames) and frames[j + 1] == frames[j] + 1:
            j += 1
        parts.append(str(frames[i]) if i == j else f"{frames[i]}-{frames[j]}")
        i = j + 1
    return ",".join(parts)


def format_anims(anims):
    lines = []
    for name, a in anims.items():
        fps = a.get("fps", 8)
        fps = int(fps) if float(fps).is_integer() else fps
        lines.append(f"{name} = {_spec(a['frames'])} @ {fps} {'loop' if a.get('loop', True) else 'once'}")
    return "\n".join(lines)


def cell_count(o):
    return max(1, o.sheet_cols) * max(1, o.sheet_rows)


def play(o, name, restart=False, line=None):
    if name not in o.anims:
        raise PawnError(f"'{o.name}' has no animation called '{name}'.", line,
                        suggest(name, list(o.anims)) or
                        ("it has: " + ", ".join(o.anims) if o.anims else
                         "add animations in the Inspector (Picture > Animations)"))
    if o.anim_name == name and not o.anim_done and not restart:
        return
    o.anim_name, o.anim_t, o.anim_done = name, 0.0, False
    _show(o)


def stop(o):
    o.anim_name, o.anim_done = "", False


def _show(o):
    a = o.anims.get(o.anim_name)
    if not a or not a["frames"]:
        return
    frames = a["frames"]
    idx = int(o.anim_t * max(0.01, float(a.get("fps", 8))))
    if a.get("loop", True):
        idx %= len(frames)
    elif idx >= len(frames):
        idx = len(frames) - 1
        o.anim_done = True
    o.frame = frames[idx] % cell_count(o)


def advance(o, dt):
    if not o.anim_name or o.anim_done:
        return
    o.anim_t += dt
    _show(o)


def autoplay(o):
    """Start the clip chosen as 'plays by itself' (called when the game starts or an object is spawned)."""
    if o.anim and o.anim in o.anims:
        play(o, o.anim, restart=True)
