"""Tests for everything new in v0.2: fixes, local, tables, modules, wait, signals, states, tween, tags."""
import tempfile
import time
import unittest
from pathlib import Path

from helpers import Game, make_scene, obj, new_project
from pawnlang import parse, PawnError


def frames_until(g, cond, limit=600):
    for i in range(limit):
        if cond():
            return i
        g.run(1)
    return None


class BugFixes(unittest.TestCase):
    def test_export_rejects_dotdot_and_existing_folder(self):
        from engine.export import export_game
        proj = new_project()
        base = Path(tempfile.mkdtemp())
        dest = base / "a" / "b"
        dest.mkdir(parents=True)
        (base / "a" / "keep.txt").write_text("precious")
        out, launcher, real = export_game(proj, dest, "..")
        self.assertTrue((base / "a" / "keep.txt").exists())
        self.assertEqual(out.parent, dest.resolve() if out.parent == dest.resolve() else dest)
        # second export to the same name needs permission to overwrite
        with self.assertRaises(FileExistsError):
            export_game(proj, dest, "My Game")
            export_game(proj, dest, "My Game")
        export_game(proj, dest, "My Game", overwrite=True)

    def test_inspector_override_reaches_derived_values(self):
        g = Game('speed = 5\ndouble = speed * 2\non start\n    print(double, speed)\n', values={"speed": 100})
        self.assertEqual(g.out, ["200 100"])

    def test_size_is_real(self):
        g = Game('on start\n    self.size = 40\n    print(self.size)\n', kind="text")
        self.assertEqual(g.out, ["40"])

    def test_builtin_errors_are_friendly(self):
        for src in ('abs("a")', 'sqrt(-1)', 'min(1, "a")', 'floor("x")', 'round("x")'):
            g = Game(f"on start\n    print({src})\n")
            self.assertIsNotNone(g.error, src)
            self.assertNotIn("operand", g.error.pretty(), src)
            self.assertNotIn("instances of", g.error.pretty(), src)

    def test_touching_is_fast_with_many_objects(self):
        proj = new_project()
        proj.write_script("c.pawn", 'when touching("P")\n    pass\n')
        coins = [obj(f"Coin ({i})" if i else "Coin", "c.pawn", x=1000 + i, y=1000) for i in range(400)]
        g = Game("pass\n", extra=coins, proj=proj)
        g.run(1)
        t = time.perf_counter()
        g.run(10)
        per_frame = (time.perf_counter() - t) / 10
        self.assertLess(per_frame, 0.03)

    def test_frame_budget_stops_runaway_work(self):
        g = Game('on start\n    i = 0\n    while i < 99999\n        i += 1\n')
        t = time.perf_counter()
        g.run(1)
        self.assertLess(time.perf_counter() - t, 1.0)

    def test_huge_text_is_refused(self):
        g = Game('on start\n    x = "ab" * 100000000\n')
        self.assertIn("million", g.error.pretty())

    def test_no_tunneling_after_a_lag_spike(self):
        ground = obj("Ground", y=100, w=400, h=20, solid=True)
        g = Game("pass\n", extra=[ground], body=True, y=40)
        g.find("P").vy = 1400
        g.run(1, dt=0.05)
        g.run(30)
        p = g.find("P")
        self.assertLess(p.y, 100)
        self.assertTrue(p.on_ground)

    def test_malformed_recent_file_does_not_crash(self):
        from engine import recent
        import json
        d = Path(tempfile.mkdtemp())
        recent.config_dir = lambda: d
        (d / "recent.json").write_text(json.dumps([{"nope": 1}, "x", {"path": str(d)}]))
        self.assertEqual(recent.load_recent(), [])

    def test_script_writes_are_atomic(self):
        proj = new_project()
        proj.write_script("x.pawn", "pass\n")
        self.assertFalse(any(p.suffix == ".tmp" for p in proj.scripts_dir.iterdir()))


class Locals(unittest.TestCase):
    def test_local_in_handler_and_tip_for_plain_assignment(self):
        g = Game('when true\n    n = 0\n    n += 1\n    print(n)\n').run(2)
        tips = [m for m in g.out if "temporary variable" in m]
        self.assertEqual(len(tips), 1)
        g = Game('when true\n    local n = 0\n    n += 1\n    print(n)\n').run(2)
        self.assertFalse([m for m in g.out if "temporary" in m])

    def test_top_level_local_is_private_and_persists(self):
        g = Game('local hits = 0\nwhen true\n    hits += 1\n')
        g.run(5)
        self.assertEqual(g.rt.instances[0].fields["hits"], 5)
        self.assertNotIn("hits", g.rt.instances[0].prog.exposed)

    def test_type_annotation_is_accepted(self):
        g = Game('on start\n    local hp: number = 3\n    print(hp)\n')
        self.assertEqual(g.out, ["3"])


class Tables(unittest.TestCase):
    def test_table_literals_and_access(self):
        g = Game('''on start
    t = {hp = 3, name = "orc", [5] = "five"}
    t.hp += 1
    t["mp"] = 7
    print(t.hp, t.name, t[5], t.mp, t.missing, t.has("hp"), t.length)
''')
        self.assertEqual(g.out, ["4 orc five 7 none true 4"])

    def test_pairs_keys_values(self):
        g = Game('''on start
    t = {a = 1, b = 2}
    s = 0
    each k, v in pairs(t)
        s += v
        print(k)
    print(s, keys(t).length, values(t).length)
    each i, x in ["p", "q"]
        print(i, x)
''')
        self.assertEqual(g.out, ["a", "b", "3 2 2", "0 p", "1 q"])

    def test_list_methods(self):
        g = Game('''on start
    l = [3, 1, 2]
    l.sort()
    l.insert(0, 9)
    print(l, l.pop(), l.index_of(1), l.slice(1, 3), [1, 2].join("-"))
    print(range(3), sorted([2, 1]), sum([1, 2, 3]))
''')
        self.assertEqual(g.out, ["[9, 1, 2] 3 1 [1, 2] 1-2", "[0, 1, 2] [1, 2] 6"])

    def test_power_and_floor_div(self):
        g = Game('on start\n    print(2 ^ 3, 2 ^ 3 ^ 2, -2 ^ 2, 7 // 2, 2 ^ -1)\n')
        self.assertEqual(g.out, ["8 512 -4 3 0.5"])

    def test_text_methods(self):
        g = Game('on start\n    print("a-b".split("-").length, " hi ".trim().upper(), "abc".contains("b"))\n')
        self.assertEqual(g.out, ["2 HI true"])

    def test_type_builtin(self):
        g = Game('on start\n    print(type(1), type("a"), type([]), type({}), type(none), type(true))\n')
        self.assertEqual(g.out, ["number text list table none bool"])

    def test_seedable_random(self):
        g = Game('on start\n    seed(7)\n    a = random_int(1, 1000)\n    seed(7)\n    print(a == random_int(1, 1000))\n')
        self.assertEqual(g.out, ["true"])


class Modules(unittest.TestCase):
    def setUp(self):
        self.proj = new_project()
        self.proj.write_module("tools.pawnmod", 'count = 0\ndef bump()\n    count += 1\n    return count\nreturn {bump = bump, k = 10}\n')

    def test_require_returns_shared_table(self):
        g = Game('''on start
    a = require("tools")
    b = require("tools")
    a.bump()
    print(b.bump(), a.k, a == b)
''', proj=self.proj)
        self.assertEqual(g.out, ["2 10 true"])

    def test_module_runs_once_across_scripts(self):
        self.proj.write_script("b.pawn", 'on start\n    print(require("tools").bump())\n')
        g = Game('on start\n    print(require("tools").bump())\n', proj=self.proj,
                 extra=[obj("Q", "b.pawn")])
        self.assertEqual(sorted(g.out), ["1", "2"])

    def test_missing_module_and_circular(self):
        g = Game('on start\n    require("nope")\n', proj=self.proj)
        self.assertIn("can't find a module", g.error.pretty())
        self.proj.write_module("a.pawnmod", 'x = require("b")\nreturn {}\n')
        self.proj.write_module("b.pawnmod", 'y = require("a")\nreturn {}\n')
        g = Game('on start\n    require("a")\n', proj=self.proj)
        self.assertIn("circular", g.error.pretty())

    def test_module_must_return_and_cannot_have_handlers(self):
        self.proj.write_module("noret.pawnmod", "x = 1\n")
        g = Game('on start\n    require("noret")\n', proj=self.proj)
        self.assertIn("didn't return", g.error.pretty())
        with self.assertRaises(PawnError):
            parse("when true\n    pass\n", "m.pawnmod", module=True)
        with self.assertRaises(PawnError):
            parse("return 1\n", "s.pawn")

    def test_module_error_names_the_module_file(self):
        self.proj.write_module("bad.pawnmod", 'def f()\n    return 1 / 0\nreturn {f = f}\n')
        g = Game('on start\n    require("bad").f()\n', proj=self.proj)
        self.assertIn("bad.pawnmod", g.error.pretty())

    def test_module_hot_reload_updates_holders(self):
        g = Game('t = none\non start\n    t = require("tools")\nwhen true\n    game.k = t.k\n', proj=self.proj)
        g.run(1)
        self.assertEqual(g.rt.game.d["k"], 10)
        self.proj.write_module("tools.pawnmod", "return {k = 99}\n")
        g.rt.reload_script("tools.pawnmod")
        g.run(1)
        self.assertEqual(g.rt.game.d["k"], 99)

    def test_module_functions_can_wait(self):
        self.proj.write_module("slow.pawnmod", 'def nap()\n    wait 0.1 seconds\n    return 5\nreturn {nap = nap}\n')
        g = Game('on start\n    print(require("slow").nap())\n', proj=self.proj)
        self.assertEqual(g.out, [])
        g.run(10)
        self.assertEqual(g.out, ["5"])


class GameScript(unittest.TestCase):
    def test_game_pawn_runs_once_for_the_whole_game(self):
        proj = new_project()
        proj.write_script("game.pawn", 'on start\n    game.level = 3\nwhen true\n    game.ticks += 1\n')
        g = Game("pass\n", proj=proj)
        g.run(4)
        self.assertEqual(g.rt.game.d["level"], 3)
        self.assertEqual(g.rt.game.d["ticks"], 4)


class Waiting(unittest.TestCase):
    def test_wait_seconds_pauses_and_resumes(self):
        g = Game('on start\n    print("a")\n    wait 0.5 seconds\n    print("b")\n')
        self.assertEqual(g.out, ["a"])
        g.run(20)
        self.assertEqual(g.out, ["a"])
        g.run(15)
        self.assertEqual(g.out, ["a", "b"])

    def test_wait_inside_loops_and_functions(self):
        g = Game('''def beep(n)
    print(n)
    wait 0.1 seconds
on start
    repeat 3 times
        beep("x")
    print("end")
''')
        g.run(60)
        self.assertEqual(g.out, ["x", "x", "x", "end"])

    def test_wait_until_and_wait_frame(self):
        g = Game('on start\n    wait until game.go\n    wait frame\n    print("went")\n')
        g.run(5)
        self.assertEqual(g.out, [])
        g.rt.game.d["go"] = True
        g.run(3)
        self.assertEqual(g.out, ["went"])

    def test_when_does_not_restart_while_waiting(self):
        g = Game('when true\n    game.runs += 1\n    wait 0.5 seconds\n')
        g.run(20)
        self.assertEqual(g.rt.game.d["runs"], 1)
        g.run(30)
        self.assertGreaterEqual(g.rt.game.d["runs"], 2)

    def test_every_can_overlap(self):
        g = Game('every 0.1 seconds\n    game.n += 1\n    wait 1 second\n')
        g.run(30)
        self.assertGreaterEqual(g.rt.game.d["n"], 4)

    def test_destroying_the_object_cancels_its_waits(self):
        g = Game('on start\n    wait 0.2 seconds\n    game.after_death = 1\n    ')
        g.rt.destroy(g.rt.find("P"))
        g.run(30)
        self.assertEqual(g.rt.game.d.get("after_death", 0), 0)

    def test_hot_reload_cancels_waits(self):
        g = Game('on start\n    wait 0.5 seconds\n    game.old = 1\n')
        g.proj.write_script("a.pawn", 'when true\n    pass\n')
        g.rt.reload_script("a.pawn")
        g.run(60)
        self.assertEqual(g.rt.game.d.get("old", 0), 0)

    def test_wait_outside_a_block_is_a_friendly_error(self):
        g = Game('wait 1 second\n')
        self.assertIn("only works inside", g.error.pretty())

    def test_errors_inside_waiting_code_are_reported(self):
        g = Game('on start\n    wait 0.1 seconds\n    x = 1 / 0\n')
        g.run(10)
        self.assertIn("divide by zero", g.error.pretty())


class Events(unittest.TestCase):
    def test_signal_connect_fire_with_args_and_once(self):
        g = Game('''hits = signal()
def on_hit(n)
    game.total += n
on start
    hits.connect(on_hit)
    hits.once(on_hit)
    hits.fire(5)
    hits.fire(1)
''')
        self.assertEqual(g.rt.game.d["total"], 5 + 5 + 1)

    def test_signal_wait(self):
        g = Game('''boom = signal()
on start
    boom.fire.__class__
''') if False else Game('''on start
    local v = event("boom").wait()
    print("got", v)
every 0.1 seconds
    event("boom").fire(7)
''')
        g.run(20)
        self.assertEqual(g.out[0], "got 7")

    def test_watch_runs_when_value_changes(self):
        g = Game('''watch game.score as s
    game.seen = s
''')
        g.run(2)
        self.assertEqual(g.rt.game.d.get("seen", 0), 0)
        g.rt.game.d["score"] = 5
        g.run(1)
        self.assertEqual(g.rt.game.d["seen"], 5)

    def test_state_machine(self):
        g = Game('''state idle
    on enter
        game.log += 1
    after 0.1 seconds
        go run
state run
    on enter
        game.running = 1
    on exit
        game.exited = 1
    when game.stop
        go idle
''')
        g.run(1)
        self.assertEqual(g.rt.instances[0].state, "idle")
        g.run(10)
        self.assertEqual(g.rt.instances[0].state, "run")
        self.assertEqual(g.rt.game.d["running"], 1)
        g.rt.game.d["stop"] = True
        g.run(2)
        self.assertEqual(g.rt.instances[0].state, "idle")
        self.assertEqual(g.rt.game.d["exited"], 1)

    def test_go_to_unknown_state_suggests(self):
        g = Game('state idle\n    after 0.01 seconds\n        go idel\n')
        g.run(3)
        self.assertIn("Did you mean 'idle'", g.error.pretty())


class Tweens(unittest.TestCase):
    def test_tween_moves_value_over_time_with_easing(self):
        g = Game('on start\n    tween self.x to 100 over 1 second ease out\n')
        g.run(30)
        mid = g.find("P").x
        self.assertGreater(mid, 50)
        g.run(40)
        self.assertAlmostEqual(g.find("P").x, 100, delta=0.001)

    def test_wait_tweens(self):
        g = Game('on start\n    tween self.x to 10 over 0.5 seconds\n    wait tweens\n    print("done")\n')
        g.run(20)
        self.assertEqual(g.out, [])
        g.run(20)
        self.assertEqual(g.out, ["done"])

    def test_tween_a_variable_and_alpha(self):
        g = Game('v = 0\non start\n    tween v to 4 over 0.2 seconds\n    tween self.alpha to 0 over 0.2 seconds\n')
        g.run(20)
        self.assertAlmostEqual(g.rt.instances[0].fields["v"], 4)
        self.assertAlmostEqual(g.find("P").alpha, 0)

    def test_tween_needs_numbers(self):
        g = Game('on start\n    tween self.x to "a" over 1 second\n')
        self.assertIn("has to be a number", g.error.pretty())


class TagsAndLayers(unittest.TestCase):
    def test_tags_find_and_touching(self):
        foe = obj("Orc", x=3, tags=["enemy"])
        g = Game('''on start
    self.tag("hero")
    print(all("#enemy").length, tagged("hero").length, touching("#enemy") != none)
''', extra=[foe])
        self.assertEqual(g.out, ["1 1 true"])

    def test_layer_alpha_flip_roundtrip(self):
        g = Game('on start\n    self.layer = 3\n    self.alpha = 2\n    self.flip_x = true\n')
        o = g.find("P")
        self.assertEqual((o.layer, o.alpha, o.flip_x), (3, 1.0, True))
        d = o.to_dict()
        self.assertEqual((d["layer"], d["alpha"], d["flip_x"], d["tags"]), (3, 1.0, True, []))


class HotReload(unittest.TestCase):
    def test_hot_reload_keeps_runtime_state_of_unchanged_variables(self):
        g = Game('lives = 3\nwhen game.hit\n    lives -= 1\n    game.hit = false\n')
        g.rt.game.d["hit"] = True
        g.run(1)
        self.assertEqual(g.rt.instances[0].fields["lives"], 2)
        g.proj.write_script("a.pawn", 'lives = 3\nwhen game.hit\n    lives -= 1\n    game.hit = false\n# edited\n')
        g.rt.reload_script("a.pawn")
        self.assertEqual(g.rt.instances[0].fields["lives"], 2)
        g.proj.write_script("a.pawn", 'lives = 9\nwhen true\n    pass\n')
        g.rt.reload_script("a.pawn")
        self.assertEqual(g.rt.instances[0].fields["lives"], 9)


class Scenes(unittest.TestCase):
    def test_new_fields_survive_save_and_load(self):
        from engine.scene import Scene
        s = Scene.from_dict(make_scene(obj("A", tags=["x"], layer=2, alpha=0.5, flip_x=True)))
        d = Scene.from_dict(s.to_dict()).find_name("A")
        self.assertEqual((d.tags, d.layer, d.alpha, d.flip_x), (["x"], 2, 0.5, True))
        self.assertEqual(s.to_dict()["format"], 1)

    def test_old_scene_files_still_load(self):
        from engine.scene import Scene
        s = Scene.from_dict({"bg": "#000", "objects": [{"name": "Old", "kind": "rect"}]})
        o = s.find_name("Old")
        self.assertEqual((o.layer, o.alpha, o.tags), (0, 1.0, []))

    def test_asset_import_and_audio_lookup(self):
        proj = new_project()
        src = Path(tempfile.mkdtemp()) / "My Hero!.png"
        src.write_bytes(b"\x89PNG fake")
        rel = proj.import_asset(src)
        self.assertEqual(rel, "assets/sprites/My_Hero_.png")
        self.assertEqual(proj.import_asset(src), rel)          # same file twice: no duplicate
        song = Path(tempfile.mkdtemp()) / "theme.ogg"
        song.write_bytes(b"OggS")
        self.assertEqual(proj.import_asset(song), "assets/music/theme.ogg")
        self.assertEqual(proj.music_path("theme").name, "theme.ogg")
        self.assertIsNone(proj.audio_path("../x"))
        self.assertIsNone(proj.import_asset(Path("x.exe")))

    def test_draw_order_uses_layers(self):
        from engine.scene import sort_for_drawing
        from engine.scene import Scene
        s = Scene.from_dict(make_scene(obj("Top", layer=5), obj("Bottom", layer=-1), obj("Mid")))
        names = [o.name for o in sort_for_drawing(s)]
        self.assertEqual(names[:3], ["Bottom", "Main Camera", "Mid"])
        self.assertEqual(names[-1], "Top")


class Templates(unittest.TestCase):
    def test_coin_template_plays_and_has_new_files(self):
        proj = new_project("coin")
        self.assertIn("game.pawn", proj.list_scripts())
        self.assertIn("utils.pawnmod", proj.list_modules())
        from engine.runtime import Runtime
        rt = Runtime(proj.load_scene(), proj, console=lambda *a: None)
        rt.start()
        for _ in range(120):
            rt.update(1 / 60)
        p = next(o for o in rt.scene.all() if o.name == "Player")
        self.assertTrue(p.on_ground)

    def test_all_presets_parse(self):
        from engine.presets import PRESETS, NEW_SCRIPT, NEW_MODULE
        for label, (fname, text) in PRESETS.items():
            parse(text, fname)
        parse(NEW_SCRIPT, "n.pawn")
        parse(NEW_MODULE.replace("NAME", "x"), "m.pawnmod", module=True)


if __name__ == "__main__":
    unittest.main()
