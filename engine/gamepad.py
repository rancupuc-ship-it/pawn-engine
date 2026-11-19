"""Game controllers. On Windows this reads Xbox-style pads (XInput); other systems have no controllers yet.

A pad's state is {"buttons": set of names, "axes": {name: number}}.
"""
import sys
import time

BUTTONS = {"up": 0x0001, "down": 0x0002, "left": 0x0004, "right": 0x0008, "start": 0x0010, "back": 0x0020,
           "ls": 0x0040, "rs": 0x0080, "lb": 0x0100, "rb": 0x0200, "a": 0x1000, "b": 0x2000, "x": 0x4000, "y": 0x8000}
AXES = ("left_x", "left_y", "right_x", "right_y", "lt", "rt")
DEADZONE = 0.18


def clean_axis(v, deadzone=DEADZONE):
    """Ignore tiny stick drift, then stretch what is left back to the full -1..1 range."""
    if abs(v) < deadzone:
        return 0.0
    return max(-1.0, min(1.0, (abs(v) - deadzone) / (1 - deadzone))) * (1 if v > 0 else -1)


def empty_state():
    return {"buttons": set(), "axes": {a: 0.0 for a in AXES}}


class XInput:
    """Talks to xinput1_4.dll with ctypes. Does nothing (and never fails) when it isn't there."""

    def __init__(self):
        self.dll = None
        self.last_try = [0.0] * 4
        self.connected = [False] * 4
        if sys.platform != "win32":
            return
        import ctypes
        self.ctypes = ctypes

        class Pad(ctypes.Structure):
            _fields_ = [("buttons", ctypes.c_ushort), ("lt", ctypes.c_ubyte), ("rt", ctypes.c_ubyte), ("lx", ctypes.c_short),
                        ("ly", ctypes.c_short), ("rx", ctypes.c_short), ("ry", ctypes.c_short)]

        class State(ctypes.Structure):
            _fields_ = [("packet", ctypes.c_uint), ("pad", Pad)]

        class Vib(ctypes.Structure):
            _fields_ = [("left", ctypes.c_ushort), ("right", ctypes.c_ushort)]
        self.State, self.Vib = State, Vib
        for name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
            try:
                self.dll = ctypes.WinDLL(name)
                break
            except OSError:
                continue

    def poll(self):
        """One state per connected pad, in order (pad 1 first). Disconnected pads are only re-checked once a second."""
        if self.dll is None:
            return []
        out = []
        now = time.monotonic()
        for i in range(4):
            if not self.connected[i] and now - self.last_try[i] < 1.0:
                continue
            self.last_try[i] = now
            st = self.State()
            ok = self.dll.XInputGetState(i, self.ctypes.byref(st)) == 0
            self.connected[i] = ok
            if not ok:
                continue
            p = st.pad
            s = empty_state()
            s["buttons"] = {n for n, bit in BUTTONS.items() if p.buttons & bit}
            s["axes"] = {"left_x": clean_axis(p.lx / 32767.0), "left_y": -clean_axis(p.ly / 32767.0),
                         "right_x": clean_axis(p.rx / 32767.0), "right_y": -clean_axis(p.ry / 32767.0),
                         "lt": p.lt / 255.0, "rt": p.rt / 255.0}
            s["index"] = i
            out.append(s)
        return out

    def rumble(self, index, left, right):
        if self.dll is None:
            return
        v = self.Vib(int(max(0.0, min(1.0, left)) * 65535), int(max(0.0, min(1.0, right)) * 65535))
        try:
            self.dll.XInputSetState(index, self.ctypes.byref(v))
        except OSError:
            pass
