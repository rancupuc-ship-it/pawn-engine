import os
import sys
import random
import unittest

from tests.helpers import make_scene, new_project, obj

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PAWN_NO_SOUND", "1")

from engine import native, physics  # noqa: E402
from engine.runtime import Runtime  # noqa: E402


def random_scene(seed):
    r = random.Random(seed)
    objs = []
    for i in range(r.randint(3, 25)):
        kind = r.choice(["block", "block", "plat", "ramp"])
        o = obj(f"S{i}", x=r.randint(-300, 300), y=r.randint(-100, 300), w=r.randint(20, 160), h=r.randint(10, 60), solid=True)
        if kind == "plat":
            o["one_way"] = True
        if kind == "ramp":
            o["slope"] = r.choice(["up-right", "up-left"])
        if r.random() < 0.2:
            o["cgroup"], o["cmask"] = r.randint(1, 3), r.randint(1, 7)
        objs.append(o)
    for i in range(r.randint(1, 30)):
        o = obj(f"B{i}", x=r.randint(-300, 300), y=r.randint(-300, 100), w=r.randint(8, 30), h=r.randint(8, 30), body=True)
        o["vx"] = r.choice([0, 0, r.randint(-400, 400)])
        o["bounce"] = r.choice([0, 0, 0.5, 0.9])
        o["friction"] = r.choice([0, 5, 12])
        if r.random() < 0.2:
            o["cgroup"], o["cmask"] = r.randint(1, 3), r.randint(1, 7)
        objs.append(o)
    return make_scene(*objs)


def snapshot(rt):
    return [(o.name, round(o.x, 6), round(o.y, 6), round(o.vx, 6), round(o.vy, 6), o.on_ground) for o in rt.scene.all() if o.body]


@unittest.skipUnless(native.available(), "Rust core not built")
class NativeMatchesPython(unittest.TestCase):
    def run_frames(self, seed, use_native, frames=90):
        proj = new_project()
        rt = Runtime(random_scene(seed), proj)
        rt.start()
        saved = physics._core
        physics._core = native.core if use_native else None
        try:
            for f in range(frames):
                rt.update(1 / 60 if f % 17 else 1 / 20)   # include a few long frames
        finally:
            physics._core = saved
        return snapshot(rt)

    def test_random_scenes_match(self):
        for seed in range(40):
            a, b = self.run_frames(seed, True), self.run_frames(seed, False)
            self.assertEqual(a, b, f"seed {seed} differs")

    def test_tilemap_and_empty(self):
        self.assertEqual(native.core.step([], [], [], [], 1 / 60), [])


class Interpreter(unittest.TestCase):
    def run_script(self, src, frames=12):
        proj = new_project()
        (proj.scripts_dir / "t.pawn").write_text(src, encoding="utf-8")
        rt = Runtime(make_scene(obj("A", script="t.pawn")), proj)
        rt.start()
        for _ in range(frames):
            rt.update(0.1)
        return rt

    def test_plain_handler_runs_without_task(self):
        rt = self.run_script("n = 0\n\nwhen true\n    n += 1\n    self.x = n\n")
        self.assertEqual(rt.find("A").pawn_get("x"), 12)

    def test_function_that_waits_still_works(self):
        rt = self.run_script("def nap()\n    wait 0.25 seconds\n\non start\n    nap()\n    self.x = 99\n", frames=2)
        self.assertEqual(rt.find("A").pawn_get("x"), 0)
        for _ in range(6):
            rt.update(0.1)
        self.assertEqual(rt.find("A").pawn_get("x"), 99)

    def test_every_and_state_go(self):
        rt = self.run_script("n = 0\n\nevery 0.1 seconds\n    n += 1\n    self.y = n\n", frames=10)
        self.assertGreaterEqual(rt.find("A").pawn_get("y"), 8)

    def test_errors_keep_their_line(self):
        from pawnlang import PawnError
        with self.assertRaises(PawnError) as c:
            self.run_script("when true\n    self.x = 1 / 0\n", frames=2)
        self.assertEqual(c.exception.line, 2)

    def test_comparisons_and_math(self):
        rt = self.run_script("when true\n    if 1 < 2 and \"a\" < \"b\" and 3 >= 3 and 2 <= 1 == false\n        self.x = 5 * 2 - 3 + 0.5\n", frames=2)
        self.assertEqual(rt.find("A").pawn_get("x"), 7.5)


class PawnHelpers(Interpreter):
    def value(self, expr):
        rt = self.run_script(f"on start\n    self.x = {expr}\n", frames=1)
        return rt.find("A").pawn_get("x")

    def test_old_scripts_may_still_use_new_builtin_names_as_variables(self):
        rt = self.run_script("snap = 5\nwrap = 2\n\non start\n    self.x = snap * wrap\n", frames=1)
        self.assertEqual(rt.find("A").pawn_get("x"), 10)

    def test_coalesce(self):
        rt = self.run_script("local t = {a = 5}\non start\n    self.x = t.a ?? 9\n    self.y = t.b ?? 9\n", frames=1)
        a = rt.find("A")
        self.assertEqual((a.pawn_get("x"), a.pawn_get("y")), (5, 9))
        self.assertEqual(self.value("none ?? none ?? 7"), 7)
        self.assertEqual(self.value("0 ?? 7"), 0)          # only none counts, not zero

    def test_math_helpers(self):
        self.assertEqual(self.value("wrap(370, 0, 360)"), 10)
        self.assertEqual(self.value("wrap(-10, 0, 360)"), 350)
        self.assertEqual(self.value("approach(0, 10, 3)"), 3)
        self.assertEqual(self.value("approach(9, 10, 3)"), 10)
        self.assertEqual(self.value("approach(5, 0, 2)"), 3)
        self.assertEqual(self.value("map_range(5, 0, 10, 100, 200)"), 150)
        self.assertEqual(self.value("snap(17, 8)"), 16)
        self.assertEqual(self.value("smoothstep(0, 10, 5)"), 0.5)
        self.assertEqual(self.value("smoothstep(0, 10, 99)"), 1)
        self.assertAlmostEqual(self.value("atan2(1, 1)"), 45)
        self.assertAlmostEqual(self.value("degrees(radians(30))"), 30)

    def test_angle_to(self):
        self.assertAlmostEqual(self.value("angle_to(0, 0, 10, 0)"), 0)
        self.assertAlmostEqual(self.value("angle_to(0, 0, 0, -10)"), -90)
        self.assertAlmostEqual(self.value("angle_to({x = 0, y = 0}, {x = 0, y = 5})"), 90)

    def test_shuffle_and_chance(self):
        self.assertEqual(self.value("len(shuffle([1, 2, 3, 4]))"), 4)
        self.assertEqual(self.value("sum(shuffle([1, 2, 3, 4]))"), 10)
        rt = self.run_script("on start\n    self.x = 0\n    self.y = 0\n    if chance(1)\n        self.x = 1\n    if chance(0)\n        self.y = 1\n", frames=1)
        a = rt.find("A")
        self.assertEqual((a.pawn_get("x"), a.pawn_get("y")), (1, 0))


class WorldQueries(unittest.TestCase):
    def world(self, extra=(), script=None):
        proj = new_project()
        if script:
            (proj.scripts_dir / "t.pawn").write_text(script, encoding="utf-8")
        wall = obj("Wall", x=0, y=0, w=20, h=200, solid=True)
        rt = Runtime(make_scene(wall, obj("A", x=-100, y=0, w=10, h=10, script="t.pawn" if script else None),
                                obj("B", x=100, y=0, w=10, h=10), *extra), proj)
        rt.start()
        rt.update(1 / 60)
        return rt

    def test_raycast_hits_the_wall(self):
        rt = self.world()
        a, b = rt.find("A"), rt.find("B")
        from engine import queries
        r = queries.raycast(rt, -100, 0, 100, 0)
        self.assertTrue(r["hit"])
        self.assertAlmostEqual(r["x"], -10)
        self.assertAlmostEqual(r["distance"], 90)
        self.assertEqual(r["object"].obj.name, "Wall")
        self.assertFalse(queries.raycast(rt, -100, 150, 100, 150)["hit"])     # over the top
        ray, ray_dir, can_see = queries.pawn_raycast(rt)
        self.assertFalse(can_see(a, b))
        self.assertTrue(can_see(a, {"x": -100, "y": 150}))
        self.assertTrue(ray_dir(a, 0, 500)["hit"])
        self.assertFalse(ray_dir(a, 180, 500)["hit"])

    def test_path_goes_around_the_wall(self):
        from engine import queries
        rt = self.world()
        a, b = rt.find("A"), rt.find("B")
        path = queries.find_path(rt, a, b, 20)
        self.assertGreater(len(path), 2)
        self.assertEqual((path[0]["x"], path[0]["y"]), (-100, 0))
        self.assertEqual((path[-1]["x"], path[-1]["y"]), (100, 0))
        # some point of the route goes past the top or bottom of the 200-tall wall
        self.assertTrue(any(abs(p["y"]) > 100 for p in path))

    def test_no_way_gives_empty_list(self):
        from engine import queries
        boxed = [obj("Box", x=100, y=0, w=60, h=60, solid=True)]          # B stands inside a solid box
        rt = self.world(boxed)
        self.assertEqual(queries.find_path(rt, rt.find("A"), {"x": 100, "y": 0}, 10), [])

    def test_rust_and_python_find_equal_length_routes(self):
        from engine import queries
        blocked = bytearray(20 * 10)
        for y in range(1, 9):
            blocked[y * 20 + 10] = 1
        py = queries._astar_py(blocked, 20, 10, 2, 5, 17, 5)
        self.assertEqual(py[0], (2, 5))
        self.assertEqual(py[-1], (17, 5))
        if native.available():
            flat = native.core.astar(bytes(blocked), 20, 10, 2, 5, 17, 5)
            rs = list(zip(flat[0::2], flat[1::2]))
            self.assertEqual(len(rs), len(py))

    def test_scripts_can_use_them(self):
        rt = self.world(script="on start\n    local r = raycast(self, find(\"B\"))\n    local p = find_path(self, find(\"B\"), 20)\n    self.y = r.distance\n    self.x = len(p)\n")
        a = rt.find("A")
        self.assertGreater(a.pawn_get("x"), 2)
        self.assertAlmostEqual(a.pawn_get("y"), 90)

    def test_bad_arguments(self):
        from pawnlang import PawnError
        from engine import queries
        rt = self.world()
        with self.assertRaises(PawnError):
            queries.find_path(rt, 5, 6)
        with self.assertRaises(PawnError):
            queries.find_path(rt, rt.find("A"), rt.find("B"), 1)

    def test_can_use_cooldown(self):
        rt = self.run_cool()

    def run_cool(self):
        proj = new_project()
        (proj.scripts_dir / "t.pawn").write_text("n = 0\n\nwhen can_use(\"x\", 0.5)\n    n += 1\n    self.x = n\n", encoding="utf-8")
        rt = Runtime(make_scene(obj("A", script="t.pawn")), proj)
        rt.start()
        for _ in range(30):                  # 3 seconds at 0.1 per frame
            rt.update(0.1)
        n = rt.find("A").pawn_get("x")
        self.assertTrue(5 <= n <= 7, n)
        return rt


class Joints(unittest.TestCase):
    def build(self, kind, extra=""):
        proj = new_project()
        (proj.scripts_dir / "t.pawn").write_text(
            f"on start\n    j = {kind}(find(\"Anchor\"), find(\"Weight\"){extra})\n", encoding="utf-8")
        anchor = obj("Anchor", x=0, y=0, w=10, h=10, script="t.pawn")
        weight = obj("Weight", x=100, y=0, w=10, h=10, body=True)
        rt = Runtime(make_scene(anchor, weight), proj)
        rt.start()
        return rt

    def simulate(self, rt, frames=240):
        for _ in range(frames):
            rt.update(1 / 60)
        a, w = rt.find("Anchor").obj, rt.find("Weight").obj
        return a, w, ((w.x - a.x) ** 2 + (w.y - a.y) ** 2) ** 0.5

    def test_rope_holds_the_weight_at_its_length(self):
        a, w, d = self.simulate(self.build("rope"))
        self.assertLessEqual(d, 101.5)
        self.assertGreater(d, 98)          # it hangs taut, not falling away

    def test_rope_lets_it_swing_closer(self):
        a, w, d = self.simulate(self.build("rope", ", 300"), 120)
        self.assertGreater(abs(w.y), 50)   # fell a long way because the rope is long

    def test_spring_bounces_near_its_length(self):
        rt = self.build("spring", ", 80, 40")
        a, w, d = self.simulate(rt, 600)
        self.assertLess(abs(d - 80), 60)   # settles somewhere near (gravity stretches it)

    def test_weld_follows_the_anchor(self):
        rt = self.build("weld")
        a = rt.find("Anchor").obj
        a.x = 50
        for _ in range(3):
            rt.update(1 / 60)
        w = rt.find("Weight").obj
        self.assertAlmostEqual(w.x - a.x, 100, delta=0.5)

    def test_remove_and_dead_objects_stop_the_joint(self):
        rt = self.build("rope")
        rt.update(1 / 60)
        self.assertEqual(len(rt.joints), 1)
        rt.joints[0].dead = True
        rt.update(1 / 60)
        self.assertEqual(rt.joints, [])

    def test_bad_arguments(self):
        from pawnlang import PawnError
        from engine import joints
        rt = self.build("rope")
        a = rt.find("Anchor")
        with self.assertRaises(PawnError):
            joints.make(rt, "rope", a, 5)
        with self.assertRaises(PawnError):
            joints.make(rt, "rope", a, a)
        with self.assertRaises(PawnError):
            joints.make(rt, "rope", a, rt.find("Weight"), -5)


class EffectsApi(unittest.TestCase):
    def test_set_validate_and_remove(self):
        from pawnlang import PawnError
        from engine import effects
        fx = {}
        effects.set_effect(fx, "blur", 5)
        effects.set_effect(fx, "tint", "#ff0000", 0.5)
        effects.set_effect(fx, "vignette", 99)
        self.assertEqual(fx["blur"], 5.0)
        self.assertEqual(fx["tint"], ("#ff0000", 0.5))
        self.assertEqual(fx["vignette"], 1.0)
        effects.set_effect(fx, "blur", 0)
        self.assertNotIn("blur", fx)
        for args in (("blurr", 1), ("blur", "lots"), ("tint", 5), ("tint", "#fff", "x")):
            with self.assertRaises(PawnError):
                effects.set_effect(fx, *args)

    def test_scripts_use_effect(self):
        proj = new_project()
        (proj.scripts_dir / "t.pawn").write_text("on start\n    effect(\"grayscale\", 0.5)\n    effect(\"tint\", \"#00ff00\")\n", encoding="utf-8")
        rt = Runtime(make_scene(obj("A", script="t.pawn")), proj)
        rt.start()
        self.assertEqual(rt.effects["grayscale"], 0.5)
        self.assertEqual(rt.effects["tint"], ("#00ff00", 0.4))

    def test_cpu_fallback_runs(self):
        from PySide6.QtGui import QColor, QImage
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from engine import effects
        img = QImage(96, 54, QImage.Format_ARGB32_Premultiplied)
        img.fill(QColor("#ff0000"))
        out = effects.apply_cpu(img, {"grayscale": 1.0, "vignette": 1.0, "scanlines": 0.5, "pixelate": 8.0, "blur": 4.0,
                                      "invert": 1.0, "tint": ("#0000ff", 0.5)})
        self.assertEqual((out.width(), out.height()), (96, 54))
        c = QColor(out.pixel(48, 27))
        self.assertGreater(c.blue(), c.red())


class GamepadApi(Interpreter):
    def test_buttons_axes_and_edges(self):
        proj = new_project()
        (proj.scripts_dir / "t.pawn").write_text(
            "n = 0\n\nwhen pad_pressed(\"a\")\n    n += 1\n    self.x = n\n\nwhen pad(\"b\")\n    self.y = pad_axis(\"left_x\") * 100\n"
            "\nwhen pad_connected(2)\n    self.alpha = 0.5\n", encoding="utf-8")
        rt = Runtime(make_scene(obj("A", script="t.pawn")), proj)
        rt.start()
        from engine import gamepad
        st = gamepad.empty_state()
        st["buttons"] = {"a", "b"}
        st["axes"]["left_x"] = 0.5
        for _ in range(5):                           # held for five frames: pressed fires once
            rt.set_pads([st])
            rt.update(1 / 60)
        a = rt.find("A")
        self.assertEqual(a.pawn_get("x"), 1)
        self.assertEqual(a.pawn_get("y"), 50)
        self.assertEqual(a.pawn_get("alpha"), 1)     # pad 2 is not connected
        rt.set_pads([])
        rt.update(1 / 60)
        rt.set_pads([st])
        rt.update(1 / 60)
        self.assertEqual(a.pawn_get("x"), 2)         # released then pressed again

    def test_bad_names_and_numbers(self):
        from pawnlang import PawnError
        proj = new_project()
        (proj.scripts_dir / "t.pawn").write_text("on start\n    print(pad(\"z\"))\n", encoding="utf-8")
        rt = Runtime(make_scene(obj("A", script="t.pawn")), proj)
        with self.assertRaises(PawnError):
            rt.start()
        with self.assertRaises(PawnError):
            rt.pad_state(0)

    def test_drift_is_ignored_and_range_stays_full(self):
        from engine import gamepad
        self.assertEqual(gamepad.clean_axis(0.1), 0.0)
        self.assertEqual(gamepad.clean_axis(-0.1), 0.0)
        self.assertEqual(gamepad.clean_axis(1.0), 1.0)
        self.assertEqual(gamepad.clean_axis(-1.0), -1.0)
        self.assertGreater(gamepad.clean_axis(0.5), 0.3)

    def test_other_systems_have_no_pads_and_nothing_breaks(self):
        from engine import gamepad
        self.assertEqual(gamepad.XInput().poll() if sys.platform != "win32" else [], [])


class HelperObjects(unittest.TestCase):
    def make(self, objs, script=None):
        proj = new_project()
        if script:
            (proj.scripts_dir / "t.pawn").write_text(script, encoding="utf-8")
        rt = Runtime(make_scene(*objs), proj)
        rt.start()
        rt.update(1 / 60)
        return rt

    def test_zone_reports_touch_and_untouch(self):
        zone = obj("Z", kind="zone", x=0, y=0, w=100, h=100, trigger=True,
                   script="t.pawn")
        walker = obj("W", x=0, y=0, w=10, h=10, tags=["player"])
        rt = self.make([zone, walker], "n = 0\n\non touch as who\n    n += 1\n    self.x = n\n\non untouch as who\n    self.y = 7\n")
        z = rt.find("Z")
        self.assertEqual(z.pawn_get("x"), 1)
        rt.find("W").obj.x = 500
        rt.update(1 / 60)
        self.assertEqual(z.pawn_get("y"), 7)

    def test_prompt_shows_and_fires_on_e(self):
        prompt = obj("P", kind="prompt", x=0, y=0, w=100, h=100, text="Open", script="t.pawn")
        hero = obj("Hero", x=20, y=0, w=10, h=10, tags=["player"])
        rt = self.make([prompt, hero], "n = 0\n\non prompt as who\n    n += 1\n    self.x = n\n")
        p = rt.find("P")
        self.assertTrue(p.obj.focused)
        self.assertEqual(p.pawn_get("x"), 0)
        rt.pressed.add("e")
        rt.update(1 / 60)
        self.assertEqual(p.pawn_get("x"), 1)
        rt.find("Hero").obj.x = 900
        rt.pressed.add("e")
        rt.update(1 / 60)
        self.assertFalse(p.obj.focused)
        self.assertEqual(p.pawn_get("x"), 1)           # too far away: nothing happens

    def test_spawn_point_and_respawn(self):
        from pawnlang import PawnError
        spawn = obj("Start", kind="spawn", x=300, y=-40, w=40, h=40)
        hero = obj("Hero", x=0, y=0, w=10, h=10, body=True)
        rt = self.make([spawn, hero])
        hero_p = rt.find("Hero")
        hero_p.obj.vy = 500
        rt.respawn(hero_p)
        self.assertEqual((hero_p.obj.x, hero_p.obj.y, hero_p.obj.vy), (300, -40, 0))
        self.assertEqual(rt.spawn_point().obj.name, "Start")
        self.assertIsNone(rt.spawn_point("Nope"))
        rt.find("Start").obj.dead = True
        rt._live_cache = None
        with self.assertRaises(PawnError):
            rt.respawn(hero_p)

    def test_beam_lines_follow_the_target(self):
        from engine import joints
        beam = obj("B", kind="beam", x=0, y=0, w=10, h=6, text="End", color="#ff0000")
        end = obj("End", x=100, y=50, w=10, h=10)
        rt = self.make([beam, end])
        lines = joints.lines(rt.scene)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0][:5], (0, 0, 100, 50, 6))
        rt.find("End").obj.x = 200
        self.assertEqual(joints.lines(rt.scene)[0][2], 200)
        rt.find("B").obj.text = "Missing"
        self.assertEqual(joints.lines(rt.scene), [])

    def test_new_kinds_survive_save_and_load(self):
        from engine.scene import Scene
        scene = Scene.from_dict(make_scene(obj("M", kind="model"), obj("F", kind="folder"), obj("Z", kind="zone"),
                                           obj("S", kind="spawn"), obj("B", kind="beam"), obj("P", kind="prompt")))
        again = Scene.from_dict(scene.to_dict())
        self.assertEqual([o.kind for o in again.all()][1:], ["model", "folder", "zone", "spawn", "beam", "prompt"])


class ParticlesTwo(unittest.TestCase):
    def emitter(self, **kw):
        proj = new_project()
        o = obj("E", kind="particles", em_rate=0, **kw)
        rt = Runtime(make_scene(o), proj)
        rt.start()
        rt.update(1 / 60)
        return rt, rt.find("E")

    def test_old_settings_still_work(self):
        from engine import particles
        rt, e = self.emitter()
        import random
        particles.spawn(e.obj, random.Random(1), 10)
        self.assertEqual(len(e.obj.parts), 10)
        self.assertTrue(all(len(p) == 10 for p in e.obj.parts))

    def test_presets_apply_and_unknown_raises(self):
        from pawnlang import PawnError
        rt, e = self.emitter()
        e.pawn_get("preset")("fire")
        self.assertTrue(e.obj.em_add)
        self.assertEqual(e.obj.em_color_end, "#c0200a")
        with self.assertRaises(PawnError):
            e.pawn_get("preset")("lava")

    def test_scripts_set_properties_and_junk_is_rejected(self):
        from pawnlang import PawnError
        rt, e = self.emitter()
        e.pawn_set("rate", 40)
        e.pawn_set("glow", True)
        e.pawn_set("end_color", "#ff0000")
        e.pawn_set("shape", "circle")
        o = e.obj
        self.assertEqual((o.em_rate, o.em_add, o.em_color_end, o.em_shape), (40.0, True, "#ff0000", "circle"))
        e.pawn_set("rate", 10 ** 9)
        self.assertEqual(o.em_rate, 5000.0)
        for name, bad in (("rate", "fast"), ("shape", "triangle"), ("end_color", 5)):
            with self.assertRaises(PawnError):
                e.pawn_set(name, bad)

    def test_junk_in_a_saved_file_is_cleaned(self):
        from engine.gameobject import GameObject
        o = GameObject.from_dict({"kind": "particles", "em_rate": "lots", "em_size": float("nan"), "em_shape": 7,
                                  "em_max": -4, "em_color_end": 3, "em_add": "yes"})
        self.assertEqual(o.em_rate, 30.0)
        self.assertEqual(o.em_size, 8.0)
        self.assertEqual(o.em_shape, "point")
        self.assertEqual(o.em_max, 1)
        self.assertEqual(o.em_color_end, "")
        self.assertIs(o.em_add, True)

    def test_motion_drag_wind_spin_and_local_space(self):
        import random
        from engine import particles
        rt, e = self.emitter(em_speed=0, em_wind=100, em_spin=90, em_life=5, em_life_var=0, sprite="x.png")
        o = e.obj
        particles.spawn(o, random.Random(2), 1)
        for _ in range(60):
            particles.update(o, 1 / 60, random.Random(3))
        x, y, vx, vy, age, life, rot, spin, size, seed = o.parts[0]
        self.assertGreater(vx, 90)
        self.assertEqual(spin, 90)
        self.assertGreater(abs(rot), 80)
        # local space: particles are stored relative to the emitter
        o.em_local = True
        o.x = 500
        particles.spawn(o, random.Random(4), 1)
        self.assertLess(abs(o.parts[-1][0]), 1)

    def test_shapes_start_in_the_right_place(self):
        import random
        from engine import particles
        rt, e = self.emitter(em_shape="line", w=200, h=10)
        o = e.obj
        particles.spawn(o, random.Random(5), 50)
        self.assertTrue(all(abs(p[1]) < 1e-9 for p in o.parts))
        self.assertGreater(max(p[0] for p in o.parts) - min(p[0] for p in o.parts), 100)

    @unittest.skipUnless(native.available(), "Rust core not built")
    def test_rust_packer_matches_python(self):
        import random
        from engine import particles
        rt, e = self.emitter(em_color_end="#ff0000", em_add=True, em_size_end=2.0, sprite="a.png")
        o = e.obj
        particles.spawn(o, random.Random(6), 200)
        for _ in range(20):
            particles.update(o, 1 / 30, random.Random(7))
        lk = particles.look(o, 0.7, (0.1, 0.2, 0.5, 0.6), (4, 2))
        a = particles.pack_py(o.parts, lk, 5.0, 6.0)
        b = particles.pack(o.parts, lk, 5.0, 6.0)
        self.assertEqual(len(a), len(b))
        self.assertTrue(all(abs(x - y) < 1e-4 for x, y in zip(a, b)))


if __name__ == "__main__":
    unittest.main()
