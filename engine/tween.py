"""Tweens: smoothly change a number over time."""
from pawnlang import PawnError


def _out(t):
    return 1 - (1 - t) * (1 - t)


def _inout(t):
    return 2 * t * t if t < 0.5 else 1 - 2 * (1 - t) * (1 - t)


EASE = {
    "linear": lambda t: t,
    "in": lambda t: t * t,
    "out": _out,
    "inout": _inout,
    "smooth": lambda t: t * t * (3 - 2 * t),
}


class Tween:
    def __init__(self, key, getter, setter, start, end, dur, ease, line):
        self.key, self.getter, self.setter = key, getter, setter
        self.start, self.end, self.dur = start, end, dur
        self.ease = EASE.get(ease, EASE["linear"])
        self.line = line
        self.t = 0.0

    def update(self, dt):
        """Moves the value forward. Returns True when the tween has finished."""
        self.t += dt
        k = 1.0 if self.dur <= 0 else min(1.0, self.t / self.dur)
        self.setter(self.start + (self.end - self.start) * self.ease(k))
        return k >= 1.0

    def finish_with_error_line(self, e):
        if e.line is None:
            e.line = self.line
        return e


def run_tweens(tweens, dt, file):
    """Advance a dict of tweens, dropping finished ones."""
    for key in list(tweens):
        tw = tweens.get(key)
        if tw is None:
            continue
        try:
            done = tw.update(dt)
        except PawnError as e:
            del tweens[key]
            if e.file is None:
                e.file = file
            raise tw.finish_with_error_line(e)
        if done:
            tweens.pop(key, None)
