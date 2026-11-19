"""Shared helpers for the headless (no Qt) test suite."""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.project import create_project  # noqa: E402
from engine.runtime import Runtime  # noqa: E402
from pawnlang import PawnError  # noqa: E402


def new_project(template="blank"):
    return create_project("T", Path(tempfile.mkdtemp()), template)


def make_scene(*objs):
    cam = {"name": "Main Camera", "kind": "camera", "x": 0, "y": 0, "w": 60, "h": 40}
    return {"bg": "#000000", "objects": [cam, *objs]}


def obj(name, script=None, values=None, **kw):
    o = {"name": name, "kind": "rect", "x": 0, "y": 0, "w": 10, "h": 10}
    o.update(kw)
    if script:
        o["scripts"] = [{"file": script, "values": values or {}}]
    return o


class Game:
    """Runs one script on one object and collects print output."""

    def __init__(self, source, values=None, extra=(), proj=None, script_name="a.pawn", **objkw):
        self.proj = proj or new_project()
        self.out = []
        self.proj.write_script(script_name, source)
        scene = make_scene(obj("P", script_name, values, **objkw), *extra)
        self.rt = Runtime(scene, self.proj, console=lambda m, l="print": self.out.append(m))
        self.error = None
        try:
            self.rt.start()
        except PawnError as e:
            self.error = e

    def run(self, frames=1, dt=1 / 60):
        try:
            for _ in range(frames):
                self.rt.update(dt)
        except PawnError as e:
            self.error = e
        return self

    def find(self, name):
        for o in self.rt.scene.all():
            if o.name == name:
                return o
        return None
