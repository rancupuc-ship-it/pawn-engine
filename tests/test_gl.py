"""GPU renderer tests. They need an OpenGL 3.3 context, so they are skipped on machines without one
(the offscreen test platform has none). Run them with a real or virtual display, e.g.  xvfb-run python -m unittest tests.test_gl
"""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("PAWN_NO_SOUND", "1")

from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from engine import glrender  # noqa: E402
from engine.project import create_project  # noqa: E402
from engine.render import Assets, draw_scene, qcolor  # noqa: E402
from engine.runtime import Runtime  # noqa: E402

_app = QApplication.instance() or QApplication([])
_gpu = glrender.make_renderer()

W, H = 480, 270
CAM = {"name": "Main Camera", "kind": "camera", "x": 0, "y": 0, "w": W, "h": H}


def project():
    proj = create_project("G", Path(tempfile.mkdtemp()), "blank")
    img = QImage(16, 16, QImage.Format_ARGB32)
    img.fill(QColor("#3a7"))
    (proj.assets_dir / "sprites").mkdir(parents=True, exist_ok=True)
    img.save(str(proj.assets_dir / "sprites" / "tile.png"))
    return proj


def cpu_image(rt, assets):
    img = QImage(W, H, QImage.Format_ARGB32_Premultiplied)
    img.fill(QColor(qcolor(rt.scene.bg)))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.translate(W / 2, H / 2)
    p.translate(-rt.cam[0], -rt.cam[1])
    draw_scene(p, rt.scene, rt.camv(), assets, editor=False)
    p.end()
    return img


def differing(a, b, step=2, limit=90):
    bad = 0
    for y in range(0, H, step):
        for x in range(0, W, step):
            c, d = QColor(a.pixel(x, y)), QColor(b.pixel(x, y))
            if abs(c.red() - d.red()) + abs(c.green() - d.green()) + abs(c.blue() - d.blue()) > limit:
                bad += 1
    return bad


def run(objs, **scene_extra):
    proj = project()
    rt = Runtime({"bg": "#101020", "objects": [CAM, *objs], **scene_extra}, proj)
    rt.start()
    rt.update(1 / 60)
    return rt, Assets(proj.path)


@unittest.skipIf(_gpu is None, "no OpenGL 3.3 available")
class GpuMatchesCpu(unittest.TestCase):
    def check(self, objs, allowed=0.01, **extra):
        rt, assets = run(objs, **extra)
        gpu = _gpu.render(rt.scene, rt, assets, W, H)
        cpu = cpu_image(rt, assets)
        bad = differing(cpu, gpu)
        self.assertLessEqual(bad, allowed * (W // 2) * (H // 2), f"{bad} sampled pixels differ")
        return rt, gpu

    def test_shapes(self):
        self.check([{"name": "R", "kind": "rect", "x": -100, "y": 0, "w": 80, "h": 40, "color": "#e55"},
                    {"name": "C", "kind": "circle", "x": 0, "y": 0, "w": 60, "h": 60, "color": "#5e5"},
                    {"name": "T", "kind": "rect", "x": 100, "y": 0, "w": 60, "h": 30, "color": "#55e", "angle": 30, "alpha": 0.5}])

    def test_sprites_and_flip(self):
        self.check([{"name": "A", "kind": "sprite", "x": -60, "y": 0, "w": 64, "h": 64, "sprite": "assets/sprites/tile.png"},
                    {"name": "B", "kind": "sprite", "x": 60, "y": 0, "w": 64, "h": 64, "sprite": "assets/sprites/tile.png", "flip_x": True}])

    def test_tilemap_particles_text_and_polygon_keep_their_order(self):
        rt, gpu = self.check([
            {"name": "M", "kind": "tilemap", "x": 0, "y": 60, "tile_size": 32, "color": "#789", "tiles": {"0,0": 0, "1,0": 1, "-1,0": 2}},
            {"name": "Txt", "kind": "text", "x": 0, "y": -40, "w": 160, "h": 40, "text": "Hi", "color": "#fff", "text_size": 24},
            {"name": "Above", "kind": "rect", "x": 0, "y": -40, "w": 20, "h": 20, "color": "#f00", "layer": 3},
            {"name": "P", "kind": "polygon", "x": 120, "y": -40, "w": 60, "h": 60, "color": "#f0f"}])
        # the red square (layer 3) must be on top of the text (layer 0)
        c = QColor(gpu.pixel(W // 2, H // 2 - 40))
        self.assertGreater(c.red(), 200)
        self.assertLess(c.green(), 60)

    def test_particles_two_point_oh(self):
        import random
        from engine import particles
        rt, assets = run([{"name": "P", "kind": "particles", "x": 0, "y": 0, "w": 10, "h": 10, "em_rate": 0, "color": "#ffaa00",
                           "em_color_end": "#ff0000", "em_add": True, "em_size_end": 1.5, "em_size": 12, "em_life": 3}])
        o = [x for x in rt.scene.all() if x.name == "P"][0]
        rng = random.Random(9)
        particles.spawn(o, rng, 120)
        for _ in range(20):
            particles.update(o, 1 / 30, rng)
        gpu = _gpu.render(rt.scene, rt, assets, W, H)
        cpu = cpu_image(rt, assets)
        self.assertLessEqual(differing(cpu, gpu), 0.02 * (W // 2) * (H // 2))
        bg = QColor(qcolor(rt.scene.bg)).rgb()
        lit = sum(1 for y in range(0, H, 3) for x in range(0, W, 3) if gpu.pixel(x, y) != bg)
        self.assertGreater(lit, 100)

    def test_darkness_and_lights(self):
        self.check([{"name": "R", "kind": "rect", "x": -60, "y": 0, "w": 80, "h": 80, "color": "#e55"},
                    {"name": "L", "kind": "light", "x": -60, "y": 0, "w": 200, "h": 200, "color": "#ffcc66", "intensity": 1}],
                   darkness=0.8, ambient="#0a0c30")

    def test_hud_objects_stay_bright_in_the_dark(self):
        rt, gpu = self.check([{"name": "Bar", "kind": "rect", "x": 0, "y": 0, "w": 100, "h": 20, "color": "#ffffff", "hud": True}],
                             darkness=0.9)
        self.assertGreater(QColor(gpu.pixel(W // 2, H // 2)).red(), 200)


@unittest.skipIf(_gpu is None, "no OpenGL 3.3 available")
class ScreenEffects(unittest.TestCase):
    def scene(self):
        return run([{"name": "R", "kind": "rect", "x": 0, "y": 0, "w": 100, "h": 100, "color": "#ff0000"}])

    def test_grayscale_removes_color(self):
        rt, assets = self.scene()
        rt.effects["grayscale"] = 1.0
        c = QColor(_gpu.render(rt.scene, rt, assets, W, H).pixel(W // 2, H // 2))
        self.assertLess(abs(c.red() - c.green()), 4)
        self.assertLess(abs(c.green() - c.blue()), 4)

    def test_tint_and_invert(self):
        rt, assets = self.scene()
        rt.effects["invert"] = 1.0
        c = QColor(_gpu.render(rt.scene, rt, assets, W, H).pixel(W // 2, H // 2))
        self.assertLess(c.red(), 30)
        self.assertGreater(c.green(), 220)
        rt.effects.clear()
        rt.effects["tint"] = ("#0000ff", 1.0)
        c = QColor(_gpu.render(rt.scene, rt, assets, W, H).pixel(W // 2, H // 2))
        self.assertGreater(c.blue(), 240)

    def test_pixelate_and_blur_change_edges(self):
        rt, assets = self.scene()
        plain = _gpu.render(rt.scene, rt, assets, W, H)
        edge = W // 2 + 50
        before = QColor(plain.pixel(edge - 1, H // 2)).red(), QColor(plain.pixel(edge + 1, H // 2)).red()
        self.assertGreater(before[0], 200)
        self.assertLess(before[1], 40)
        rt.effects["blur"] = 12.0
        soft = _gpu.render(rt.scene, rt, assets, W, H)
        mid = QColor(soft.pixel(edge + 1, H // 2)).red()
        self.assertGreater(mid, 40)                 # the edge is smeared out
        rt.effects.clear()
        rt.effects["pixelate"] = 40.0
        blocky = _gpu.render(rt.scene, rt, assets, W, H)
        self.assertEqual(blocky.pixel(10, 10), blocky.pixel(11, 11))

    def test_vignette_darkens_corners_only(self):
        rt, assets = self.scene()
        rt.effects["vignette"] = 1.0
        img = _gpu.render(rt.scene, rt, assets, W, H)
        self.assertGreater(QColor(img.pixel(W // 2, H // 2)).red(), 200)
        self.assertLess(QColor(img.pixel(2, 2)).lightness(), 10)


@unittest.skipIf(_gpu is None, "no OpenGL 3.3 available")
class Batching(unittest.TestCase):
    def test_thousands_of_squares_are_one_draw_call(self):
        objs = [{"name": f"R{i}", "kind": "rect", "x": (i % 50) * 14 - 350, "y": (i // 50) * 14 - 280, "w": 5, "h": 5, "color": "#fa0"}
                for i in range(2000)]
        rt, assets = run(objs)
        _gpu.render(rt.scene, rt, assets, W, H)
        self.assertEqual(_gpu.stats["draw_calls"], 1)
        self.assertGreater(_gpu.stats["instances"], 500)       # only the ones in view are sent (culling)
        self.assertLess(_gpu.stats["instances"], 2000)

    def test_sprites_share_one_atlas_page(self):
        objs = [{"name": f"S{i}", "kind": "sprite", "x": i * 20 - 100, "y": 0, "w": 16, "h": 16, "sprite": "assets/sprites/tile.png"}
                for i in range(10)]
        rt, assets = run(objs)
        _gpu.render(rt.scene, rt, assets, W, H)
        self.assertEqual(_gpu.stats["draw_calls"], 1)

    def test_tilemap_is_uploaded_once(self):
        tiles = {f"{c},{r}": 0 for c in range(20) for r in range(10)}
        rt, assets = run([{"name": "M", "kind": "tilemap", "x": 0, "y": 0, "tile_size": 16, "color": "#789", "tiles": tiles}])
        _gpu.render(rt.scene, rt, assets, W, H)
        self.assertEqual(_gpu.stats["uploaded"], 200)
        _gpu.render(rt.scene, rt, assets, W, H)
        self.assertEqual(_gpu.stats["uploaded"], 0)            # unchanged: nothing re-sent
        m = [o for o in rt.scene.all() if o.name == "M"][0]
        m.tiles["50,50"] = 1
        m.tile_ver += 1
        _gpu.render(rt.scene, rt, assets, W, H)
        self.assertEqual(_gpu.stats["uploaded"], 201)


class Fallback(unittest.TestCase):
    def test_cpu_env_turns_the_gpu_off(self):
        os.environ["PAWN_RENDERER"] = "cpu"
        try:
            self.assertIsNone(glrender.make_renderer())
        finally:
            del os.environ["PAWN_RENDERER"]


if __name__ == "__main__":
    unittest.main()
