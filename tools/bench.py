"""Stress tests: prints milliseconds per frame for physics, scripts, particles and drawing.

Run:  python tools/bench.py [--json out.json]
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PAWN_NO_SOUND", "1")

from engine.project import create_project  # noqa: E402
from engine.runtime import Runtime  # noqa: E402
import tempfile  # noqa: E402

CAM = {"name": "Main Camera", "kind": "camera", "x": 0, "y": 0, "w": 1152, "h": 648}


def make(objs, scripts=None):
    proj = create_project("Bench", Path(tempfile.mkdtemp()), "blank")
    for name, src in (scripts or {}).items():
        (proj.scripts_dir / name).write_text(src, encoding="utf-8")
    return Runtime({"bg": "#101020", "objects": [CAM, *objs]}, proj)


def scene_physics(n=300):
    objs = [{"name": f"Floor{i}", "kind": "rect", "x": -500 + i * 60, "y": 250, "w": 60, "h": 20, "solid": True} for i in range(20)]
    objs += [{"name": f"Block{i}", "kind": "rect", "x": -450 + (i % 15) * 60, "y": 100 - (i // 15) * 14, "w": 30, "h": 30, "solid": True}
             for i in range(60)]
    objs += [{"name": f"Body{i}", "kind": "rect", "x": -500 + (i * 37) % 1000, "y": -300 + (i // 20) * 20, "w": 18, "h": 18, "body": True}
             for i in range(n)]
    return make(objs)


def scene_scripts(n=400):
    src = "speed = 50\n\nwhen true\n    self.x += speed * dt\n    if self.x > 500\n        self.x = -500\n    self.alpha = 0.9\n"
    objs = [{"name": f"S{i}", "kind": "rect", "x": (i * 13) % 900 - 450, "y": (i * 7) % 500 - 250, "w": 12, "h": 12,
             "scripts": [{"file": "mover.pawn", "values": {}}]} for i in range(n)]
    return make(objs, {"mover.pawn": src})


def scene_particles(n=6):
    return make([{"name": f"P{i}", "kind": "particles", "x": -400 + i * 150, "y": 0, "w": 10, "h": 10,
                  "em_rate": 600, "em_life": 2.5, "em_speed": 200, "em_gravity": 100} for i in range(n)])


def scene_sprites(n=5000):
    return make([{"name": f"S{i}", "kind": "rect", "x": (i % 100) * 11 - 550, "y": (i // 100) * 11 - 270, "w": 9, "h": 9,
                  "color": "#fa0" if i % 2 else "#0af"} for i in range(n)])


def gpu_ms(rt, frames=20):
    from engine.glrender import shared_renderer
    from engine.render import Assets
    gpu = shared_renderer()
    if gpu is None:
        return None
    assets = Assets(rt.project.path)
    gpu.render(rt.scene, rt, assets, 1152, 648)
    t = time.perf_counter()
    for _ in range(frames):
        gpu.render(rt.scene, rt, assets, 1152, 648)
    return (time.perf_counter() - t) / frames * 1000


def timeit(rt, frames, warm=30):
    rt.start()
    for _ in range(warm):
        rt.update(1 / 60)
    t = time.perf_counter()
    for _ in range(frames):
        rt.update(1 / 60)
    return (time.perf_counter() - t) / frames * 1000


def draw_ms(rt, frames=20):
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from engine.render import Assets, draw_scene
    img = QImage(1152, 648, QImage.Format_ARGB32_Premultiplied)
    assets = Assets(rt.project.path)
    t = time.perf_counter()
    for _ in range(frames):
        img.fill(0)
        p = QPainter(img)
        p.translate(576, 324)
        p.translate(-rt.cam[0], -rt.cam[1])
        draw_scene(p, rt.scene, rt.camv(), assets, editor=False)
        p.end()
    return (time.perf_counter() - t) / frames * 1000


def main():
    results = {}
    for name, build in (("physics 300 bodies / 80 blocks", scene_physics), ("scripts 400 objects", scene_scripts),
                        ("particles 6 x 600/s", scene_particles), ("5000 squares", scene_sprites)):
        rt = build()
        results[name + " update"] = round(timeit(rt, 60), 2)
        try:
            results[name + " draw (CPU)"] = round(draw_ms(rt), 2)
            g = gpu_ms(rt)
            if g is not None:
                results[name + " draw (GPU)"] = round(g, 2)
        except Exception as e:  # keep going so one failure doesn't hide the rest
            results[name + " draw"] = f"error: {e}"
    for k, v in results.items():
        print(f"{k:50s} {v} ms")
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
