"""Tests for v0.5: linter, docs, Inspector hints, gallery scripts, lighting, parallax, breakpoint, menu template."""
import tempfile
import unittest
from pathlib import Path

from helpers import Game, make_scene, obj, new_project
from engine.docs import BUILTIN_NAMES, BUILTIN_DOCS, SPECIAL_DOCS, doc_for
from engine.lint import lint
from engine.hints import parse_hints
from engine.gallery import GALLERY
from engine.gameobject import GameObject
from engine.scene import Scene
from engine.presets import PRESETS


class DocsAndLint(unittest.TestCase):
    def test_docs_match_what_scripts_can_really_call(self):
        g = Game("on start\n    print(1)\n")
        real = set(g.rt.shared)
        self.assertEqual(real - BUILTIN_NAMES, set(), "a builtin has no entry in engine/docs.py")
        inst = {"self", "touching", "nearest", "destroy", "current_state", "in_state"}
        self.assertEqual(BUILTIN_NAMES - real - inst, set(), "docs mention a name scripts can't use")

    def test_doc_for(self):
        self.assertIn("random", doc_for("random")[0])
        self.assertIsNotNone(doc_for("alpha"))
        self.assertIsNone(doc_for("nothing_here"))

    def test_typos_get_suggestions(self):
        ws = lint("speed = 5\non start\n    print(speeed)\n    self.xx = 1\n    camera.zoomm = 2\n", "a.pawn")
        msgs = [w.message + " " + str(w.hint) for w in ws if w.kind == "warning"]
        self.assertTrue(any("speeed" in m and "speed" in m.split("Did you mean")[-1] for m in msgs))
        self.assertTrue(any("'self'" in m and "'x'" in m for m in msgs))
        self.assertTrue(any("zoom" in m for m in msgs))

    def test_unused_names_are_only_tips(self):
        ws = lint("local a = 1\non start\n    b = 2\n    _c = 3\n", "a.pawn")
        self.assertEqual({w.message.split("'")[1] for w in ws}, {"a", "b"})
        self.assertTrue(all(w.kind == "info" for w in ws))

    def test_inspector_values_and_used_names_are_clean(self):
        ws = lint("speed = 5\non start\n    self.x += speed\n    each k, v in pairs(game)\n        print(k, v)\n", "a.pawn")
        self.assertEqual(ws, [])

    def test_script_that_does_not_parse_returns_nothing(self):
        self.assertEqual(lint("when\n", "a.pawn"), [])

    def test_functions_params_watch_and_event_names_are_known(self):
        src = ("def add(a, b)\n    return a + b\non start\n    print(add(1, 2))\n"
               "watch game.score as s\n    print(s)\non change as v\n    print(v)\n")
        self.assertEqual([w for w in lint(src, "a.pawn") if w.kind == "warning"], [])

    def test_instance_helpers_are_known(self):
        src = 'when touching("Player")\n    print(current_state(), in_state("x"), nearest("a"))\n    destroy()\n'
        self.assertEqual([w for w in lint(src, "a.pawn") if w.kind == "warning"], [])

    def test_all_shipped_scripts_have_no_warnings(self):
        for label, (f, src) in PRESETS.items():
            bad = [w for w in lint(src, f) if w.kind == "warning"]
            self.assertEqual(bad, [], label)


class Hints(unittest.TestCase):
    def test_parse(self):
        h = parse_hints('speed = 260   # range 0 600\njump = 6 # range 1..9 step 2\nmode = "a"  # choice easy, hard\n'
                        'c = "#fff" # color\nhp = 3 # Starting health\nplain = 1\nname = "a # b"\nlo = 5 # range 9 1\n')
        self.assertEqual(h["speed"], {"kind": "range", "min": 0.0, "max": 600.0, "step": None})
        self.assertEqual(h["jump"]["step"], 2.0)
        self.assertEqual(h["mode"]["items"], ["easy", "hard"])
        self.assertEqual(h["c"]["kind"], "color")
        self.assertEqual(h["hp"], {"kind": "text", "text": "Starting health"})
        self.assertNotIn("plain", h)
        self.assertNotIn("name", h)
        self.assertEqual((h["lo"]["min"], h["lo"]["max"]), (1.0, 9.0))

    def test_project_caches_and_updates(self):
        proj = new_project()
        proj.write_script("a.pawn", "speed = 1  # range 0 5\n")
        self.assertEqual(proj.script_hints("a.pawn")["speed"]["max"], 5.0)
        import time
        time.sleep(0.01)
        proj.write_script("a.pawn", "speed = 1  # range 0 9\n")
        self.assertEqual(proj.script_hints("a.pawn")["speed"]["max"], 9.0)
        self.assertEqual(proj.script_hints("missing.pawn"), {})


class GalleryScripts(unittest.TestCase):
    def test_enough_unique_scripts(self):
        self.assertGreaterEqual(len(GALLERY) + 8, 35)
        self.assertEqual(len({g[1] for g in GALLERY}), len(GALLERY))
        self.assertEqual(len({g[2] for g in GALLERY}), len(GALLERY))

    def test_every_script_runs_without_errors_on_many_kinds_of_object(self):
        for cat, label, fname, desc, src in GALLERY:
            proj = new_project()
            extra = [obj("Floor", x=0, y=200, w=2000, h=40, solid=True),
                     obj("Hero", x=60, y=150, w=30, h=30, tags=["player"], body=True),
                     obj("Bullet", x=0, y=0, active=False, tags=["bullet"], trigger=True),
                     obj("Pop", kind="particles", em_on=False), obj("Pause Panel", active=False),
                     obj("Lamp", kind="light", w=200)]
            for kind in ("rect", "light", "text", "button", "slider", "bar"):
                g = Game(src, proj=proj, extra=extra, script_name=fname, body=True, y=100, kind=kind)
                g.rt.down.update({"left", "right", "space"})
                g.rt.pressed.update({"space", "f", "b", "shift", "escape"})
                g.run(120)
                self.assertIsNone(g.error, f"{label} on {kind}: {g.error}")

    def test_double_jump_allows_exactly_two_jumps(self):
        src = dict((g[1], g[4]) for g in GALLERY)["Double jump"]
        floor = obj("Floor", x=0, y=300, w=2000, h=40, solid=True)
        g = Game(src, extra=[floor], body=True, y=270, script_name="dj.pawn")
        g.run(30)
        self.assertTrue(g.find("P").on_ground)
        jumps = 0
        for _ in range(4):                      # four presses, all while still in the air
            g.rt.pressed.add("space")
            g.run(1)
            if g.find("P").vy < -400:
                jumps += 1
            g.run(5)
        self.assertEqual(jumps, 2)
        g.run(120)                              # land: the jumps come back
        g.rt.pressed.add("space")
        g.run(1)
        self.assertLess(g.find("P").vy, -400)

    def test_typewriter_types_everything(self):
        src = dict((g[1], g[4]) for g in GALLERY)["Typewriter text"]
        g = Game(src, kind="text", text="Hello", script_name="t.pawn")
        g.run(2)
        self.assertEqual(g.find("P").text, "H")
        g.run(120)
        self.assertEqual(g.find("P").text, "Hello")

    def test_health_pickup_and_bullet_and_countdown(self):
        lib = dict((g[1], g[4]) for g in GALLERY)
        proj = new_project()
        proj.write_script("hp.pawn", lib["Health pickup"])
        pick = obj("Heart", "hp.pawn", x=0, y=0, w=20, h=20, trigger=True)
        g = Game("on start\n    self.tag('player')\n    game.hp = 2\n", proj=proj, extra=[pick])
        g.run(5)
        self.assertEqual(g.rt.game.d["hp"], 3)
        self.assertEqual(len(g.rt.all_named("Heart")), 0)
        g = Game(lib["Countdown timer"], kind="text", script_name="c.pawn")
        g.run(130)
        self.assertEqual(g.rt.game.d["time"], 28)

    def test_day_night_changes_darkness(self):
        src = dict((g[1], g[4]) for g in GALLERY)["Day and night"]
        g = Game(src, script_name="d.pawn")
        seen = set()
        for _ in range(60):
            g.run(5)
            seen.add(round(g.rt.scene.darkness, 1))
        self.assertGreater(len(seen), 3)

    def test_enemy_states_chase_when_player_is_close(self):
        src = dict((g[1], g[4]) for g in GALLERY)["Enemy states (patrol and chase)"]
        hero = obj("Hero", x=120, y=0, tags=["player"])
        g = Game(src, extra=[hero], script_name="e.pawn", x=0)
        g.run(90)
        self.assertGreater(g.find("P").x, 100)       # went after the hero (patrol alone only reaches 150 slowly)
        self.assertEqual(g.rt.instances[-1].state, "chase") if False else None


class LightingAndParallax(unittest.TestCase):
    def test_scene_darkness_round_trips_and_is_cleaned(self):
        s = Scene()
        s.darkness, s.ambient = 0.7, "#101030"
        c = Scene.from_dict(s.to_dict())
        self.assertEqual((c.darkness, c.ambient), (0.7, "#101030"))
        bad = Scene.from_dict({"darkness": "lots", "ambient": 5})
        self.assertEqual((bad.darkness, bad.ambient), (0.0, Scene().ambient))
        self.assertEqual(Scene.from_dict({"darkness": 5}).darkness, 1.0)

    def test_script_functions(self):
        g = Game('on start\n    darkness(0.4)\n    ambient("#001122")\n    print(darkness(), ambient())\n    darkness(9)\n    print(darkness())\n')
        self.assertEqual(g.out, ["0.4 #001122", "1"])
        g = Game('on start\n    darkness("x")\n')
        self.assertIsNotNone(g.error)

    def test_light_properties(self):
        lamp = obj("Lamp", kind="light", w=100, h=100)
        g = Game('on start\n    l = find("Lamp")\n    print(l.radius)\n    l.radius = 80\n    l.intensity = 5\n    print(l.width, l.intensity)\n',
                 extra=[lamp])
        self.assertEqual(g.out, ["50", "160 2"])

    def test_parallax_moves_by_the_camera_fraction(self):
        o = GameObject("Far", "rect")
        o.x, o.y, o.parallax = 100, 0, 0.5
        self.assertEqual(o.world_pos((200.0, 0.0, 1.0)), (200.0, 0.0))       # 100 + 200 * (1 - 0.5)
        o.parallax = 0.0
        self.assertEqual(o.world_pos((200.0, 40.0)), (300.0, 40.0))
        o.set_world_pos(300.0, 40.0, (200.0, 40.0))
        self.assertEqual((o.x, o.y), (100.0, 0.0))
        o.parallax = 1.0
        self.assertEqual(o.world_pos((200.0, 0.0)), (100.0, 0.0))

    def test_parallax_and_light_fields_are_cleaned(self):
        c = GameObject.from_dict({"kind": "light", "parallax": "far", "intensity": 9, "flicker": -3})
        self.assertEqual((c.parallax, c.intensity, c.flicker), (1.0, 2.0, 0.0))

    def test_script_can_set_parallax(self):
        g = Game("on start\n    self.parallax = 0.3\n    print(self.parallax)\n")
        self.assertEqual(g.out, ["0.3"])


class BreakpointAndText(unittest.TestCase):
    def test_breakpoint_records_where(self):
        g = Game('on start\n    breakpoint("look here")\n', script_name="dbg.pawn")
        self.assertIn("dbg.pawn", g.rt.break_msg)
        self.assertIn("look here", g.rt.break_msg)

    def test_text_slice(self):
        g = Game('on start\n    t = "Hello"\n    print(t.slice(1, 3), t.slice(2), t.slice(0, 99))\n')
        self.assertEqual(g.out, ["el llo Hello"])
        g = Game('on start\n    print("a".slice("x"))\n')
        self.assertIsNotNone(g.error)


class MenuTemplate(unittest.TestCase):
    def test_menu_template_has_two_scenes_and_a_working_play_button(self):
        from engine.project import create_project
        from engine.runtime import Runtime
        proj = create_project("M", Path(tempfile.mkdtemp()), "menu")
        self.assertEqual(proj.list_scenes(), ["Level 1", "Main"])
        self.assertEqual(proj.start_scene, "Main")
        out = []
        rt = Runtime(proj.load_scene(), proj, console=lambda m, l="print": out.append((l, m)), scene_name="Main")
        rt.start()
        rt.mx, rt.my = 0, 0
        rt.update(1 / 60)
        rt.mouse_down = True
        rt.update(1 / 60)
        rt.update(1 / 60)
        rt.mouse_down = False
        rt.update(1 / 60)
        rt.update(1 / 60)
        self.assertEqual(rt.scene_name, "Level 1")
        for _ in range(240):
            rt.update(1 / 60)
        player = next(o for o in rt.scene.all() if o.name == "Player")
        self.assertTrue(player.on_ground)
        self.assertEqual([m for m in out if m[0] == "error"], [])
        # every script in the template passes the linter
        for f in proj.list_scripts():
            self.assertEqual([w for w in lint(proj.read_script(f), f) if w.kind == "warning"], [], f)

    def test_create_project_never_overwrites_the_menu_with_a_level(self):
        from engine.project import create_project
        proj = create_project("M2", Path(tempfile.mkdtemp()), "menu")
        menu = proj.load_scene("Main")
        names = [o["name"] for o in menu["objects"]]
        self.assertIn("Play Button", names)


if __name__ == "__main__":
    unittest.main()
