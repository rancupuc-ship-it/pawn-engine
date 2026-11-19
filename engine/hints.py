"""Inspector hints written as comments next to a value:

    speed = 260        # range 0 600            a slider
    jump = 640         # range 100 1200 step 10
    mode = "easy"      # choice easy, normal, hard
    tint = "#ff0000"   # color
    hp = 3             # Starting health        (any other comment becomes the tooltip)
"""
import re

_LINE = re.compile(r"""^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:"[^"\n]*"|'[^'\n]*'|[^#\n"']+?)\s*#\s*(.+?)\s*$""")
_RANGE = re.compile(r"^range\s+(-?\d+(?:\.\d+)?)\s*(?:\.\.|to|,|\s)\s*(-?\d+(?:\.\d+)?)(?:\s+step\s+(\d+(?:\.\d+)?))?$", re.I)


def parse_hints(source):
    """{variable: {"kind": "range"|"choice"|"color"|"text", ...}} for top-level assignments with a comment."""
    out = {}
    for raw in source.splitlines():
        m = _LINE.match(raw)
        if not m:
            continue
        name, note = m.group(1), m.group(2)
        r = _RANGE.match(note)
        if r:
            lo, hi = float(r.group(1)), float(r.group(2))
            if hi < lo:
                lo, hi = hi, lo
            step = float(r.group(3)) if r.group(3) else None
            out[name] = {"kind": "range", "min": lo, "max": hi, "step": step}
        elif note.lower().startswith("choice "):
            items = [c.strip() for c in note[7:].split(",") if c.strip()]
            if items:
                out[name] = {"kind": "choice", "items": items}
        elif note.lower() == "color":
            out[name] = {"kind": "color"}
        else:
            out[name] = {"kind": "text", "text": note}
    return out
