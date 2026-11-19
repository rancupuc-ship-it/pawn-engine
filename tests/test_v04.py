"""Tests for v0.4: scenes, save/load, prefabs, physics upgrades, triggers, tile maps, particles, shake, polygons, SVG."""
import json
import tempfile
import unittest
from pathlib import Path

from helpers import Game, make_scene, obj, new_project
from engine.gameobject import GameObject
from engine import tilemap, particles
from engine.svg import parse_svg, normalise
from engine.runtime import Runtime


class Scenes(unittest.TestCase):
    def two_scenes(self):
        proj = new_project()
        proj.save_scene(make_scene(obj("Two", "two.pawn")), "Level 2")
        return proj

    def test_scene_api(self):
        proj = self.two_scenes()
        self.assertEqual(proj.list_scenes(), ["Level 2", "Main"])
        self.assertEqual(proj.start_scene, "Main")
        proj.set_start_scene("Level 2")
        self.assertEqual(proj.start_scene, "Level 2")
        proj.delete_scene("Level 2")
        self.assertEqual(proj.start_scene, "Main")
        with self.assertRaises(ValueError):
            proj.delete_scene("Main")
        with self.assertRaises(ValueError):
            proj.scene_path("../evil")
        self.assertEqual(proj.new_scene_name("Main"), "Main 2")

    def test_load_scene_switches_at_end_of_frame_and_keeps_game_data(self):
        proj = self.two_scenes()
        proj.write_script("two.pawn", 'on start\n    print("two", scene_name(), game.hp)\n')
        g = Game('on start\n    game.hp = 7\n    load_scene("Level 2")\n    print("still scene one")\n', proj=proj)
        g.run(3)
        self.assertEqual(g.out, ["still scene one", "two Level 2 7"])
        self.assertIsNone(g.find("P"))
        self.assertEqual(g.rt.scene_name, "Level 2")

    def test_old_scripts_stop_and_game_script_survives(self):
        proj = self.two_scenes()
        proj.write_script("two.pawn", "on start\n    print(1)\n")
        proj.write_script("game.pawn", "every 0.05 seconds\n    game.ticks += 1\n")
        g = Game('on start\n    wait 0.1 seconds\n    load_scene("Level 2")\nevery 0.01 seconds\n    game.old += 1\n', proj=proj)
        g.run(30)
        old = g.rt.game.d.get("old", 0)
        ticks = g.rt.game.d.get("ticks", 0)
        g.run(60)
        self.assertEqual(g.rt.game.d.get("old", 0), old)      # the first scene's scripts are gone
        self.assertGreater(g.rt.game.d.get("ticks", 0), ticks)  # the global script keeps running

    def test_unknown_scene_suggests(self):
        proj = self.two_scenes()
        g = Game('on start\n    load_scene("Levl 2")\n', proj=proj)
        self.assertIsNotNone(g.error)
        self.assertIn("Level 2", str(g.error.hint))

    def test_ui_state_reset_after_switch(self):
        proj = self.two_scenes()
        btn = obj("B", "b.pawn", kind="button", x=0, y=0, w=100, h=40, hud=False)
        proj.write_script("b.pawn", 'on click\n    load_scene("Level 2")\n')
        proj.write_script("two.pawn", "on start\n    print(1)\n")
        g = Game("on start\n    print('x')\n", proj=proj, extra=[btn])
        g.rt.mx, g.rt.my, g.rt.mouse_down = 0, 0, True
        g.run(2)
        g.rt.mouse_down = False
        g.run(3)
        self.assertEqual(g.rt.scene_name, "Level 2")
        self.assertIsNone(g.rt.ui.hover)


class SaveLoad(unittest.TestCase):
    def test_round_trip_and_slots(self):
        g = Game('on start\n    game.hp = 7\n    game.name = "Ann"\n    game.items = ["a", "b"]\n    game.stats = {k = 1}\n'
                 '    save_game("one")\n    game.hp = 0\n    print(load_game("one"), game.hp, game.name, game.items, game.stats.k)\n'
                 '    print(has_save("one"), has_save("two"), saves())\n    delete_save("one")\n    print(has_save("one"))\n')
        self.assertEqual(g.out, ["true 7 Ann [a, b] 1", "true false [one]", "false"])

    def test_missing_save_returns_false(self):
        g = Game('on start\n    print(load_game("nope"))\n')
        self.assertEqual(g.out, ["false"])

    def test_private_names_and_bad_values(self):
        g = Game('on start\n    game._secret = 1\n    game.who = self\n    save_game("x")\n')
        self.assertIsNotNone(g.error)
        self.assertIn("save", str(g.error))
        g = Game('on start\n    game._secret = 1\n    game.a = 2\n    save_game("x")\n    game._secret = 5\n    game.a = 0\n'
                  '    load_game("x")\n    print(game.a, game._secret)\n')
        self.assertEqual(g.out, ["2 5"])

    def test_bad_slot_name_is_friendly_and_damaged_file_is_ignored(self):
        g = Game('on start\n    save_game("../x")\n')
        self.assertIsNotNone(g.error)
        proj = new_project()
        (proj.path / "saves").mkdir()
        (proj.path / "saves" / "bad.json").write_text("{not json")
        g = Game('on start\n    print(load_game("bad"))\n', proj=proj)
        self.assertEqual(g.out, ["false"])


class Prefabs(unittest.TestCase):
    def make(self):
        proj = new_project()
        proj.write_script("c.pawn", 'on start\n    print("hi", self.name)\n')
        proj.save_prefab("Coiny", obj("Coiny", "c.pawn", x=5, y=5, tags=["coin"]))
        return proj

    def test_spawn_from_prefab_runs_scripts_and_places_it(self):
        proj = self.make()
        g = Game('on start\n    c = spawn("Coiny", 40, 50)\n    print(c.x, c.y, c.has_tag("coin"))\n', proj=proj)
        self.assertEqual(g.out, ["hi Coiny", "40 50 true"])

    def test_each_spawn_is_a_new_object_and_scene_objects_win(self):
        proj = self.make()
        g = Game('on start\n    spawn("Coiny")\n    spawn("Coiny")\n    print(len(all("Coiny")))\n', proj=proj)
        self.assertEqual(g.out[-1], "2")
        g = Game('on start\n    spawn("Coiny")\n    print(len(all("Coiny")))\n', proj=proj, extra=[obj("Coiny", x=1, active=False)])
        self.assertEqual(g.out, ["1"])      # copied the scene object (no script), not the prefab

    def test_unknown_name_lists_prefabs(self):
        g = Game('on start\n    spawn("Nope")\n', proj=self.make())
        self.assertIn("Coiny", str(g.error.hint))

    def test_edit_prefab_file_takes_effect(self):
        proj = self.make()
        g = Game('on start\n    print(spawn("Coiny").width)\n', proj=proj)
        self.assertEqual(g.out[-1], "10")
        d = proj.load_prefab("Coiny")
        d["w"] = 77
        proj.save_prefab("Coiny", d)
        g2 = Game('on start\n    print(spawn("Coiny").width)\n', proj=proj)
        self.assertEqual(g2.out[-1], "77")

    def test_bad_names_rejected(self):
        with self.assertRaises(ValueError):
            new_project().prefab_path("../x")


class PhysicsUpgrades(unittest.TestCase):
    def test_one_way_platform(self):
        plat = obj("Plat", x=0, y=100, w=200, h=20, solid=True, one_way=True)
        floor = obj("Floor", x=0, y=300, w=2000, h=40, solid=True)
        g = Game("on start\n    self.vy = -900\n", extra=[plat, floor], body=True, y=200)
        peak = 1e9
        for _ in range(240):
            g.run(1)
            peak = min(peak, g.find("P").y)
        self.assertLess(peak, 60)                     # went up through the platform
        self.assertAlmostEqual(g.find("P").y, 85, delta=1)   # and landed on top of it
        self.assertTrue(g.find("P").on_ground)

    def test_one_way_does_not_block_sideways_or_from_below(self):
        plat = obj("Plat", x=100, y=0, w=50, h=20, solid=True, one_way=True)
        g = Game("on start\n    self.vx = 300\n", extra=[plat], body=False, x=0)
        g.find("P").body = True
        g.rt.scene.find_name("P").vy = -1500
        g.run(60)
        self.assertGreater(g.find("P").x, 150)

    def test_ramp_is_walkable(self):
        ramp = obj("Ramp", x=0, y=250, w=300, h=100, solid=True, slope="up-right")
        floor = obj("Floor", x=0, y=330, w=2000, h=40, solid=True)
        g = Game("on start\n    self.vx = 150\n", extra=[ramp, floor], body=True, x=-300, y=300)
        seen = []
        for _ in range(200):
            g.run(1)
            p = g.find("P")
            if -100 < p.x < 100:
                seen.append(p.y)
                self.assertTrue(p.on_ground)
        self.assertLess(min(seen), 250)               # climbed well above the flat floor
        self.assertLess(seen[-1], seen[0])

    def test_tall_end_of_ramp_blocks_from_the_wrong_side(self):
        ramp = obj("Ramp", x=0, y=250, w=300, h=100, solid=True, slope="up-right")
        floor = obj("Floor", x=0, y=320, w=2000, h=40, solid=True)
        g = Game("on start\n    self.vx = -200\n", extra=[ramp, floor], body=True, x=400, y=290)
        g.run(180)
        self.assertGreater(g.find("P").x, 150)

    def test_collision_groups(self):
        wall = obj("Wall", x=100, y=0, w=20, h=500, solid=True, cgroup=2)
        g = Game("on start\n    self.vx = 300\n", extra=[wall], body=True, cmask=253, x=0)
        g.run(90)
        self.assertGreater(g.find("P").x, 300)
        g = Game("on start\n    self.vx = 300\n", extra=[wall], body=True, x=0)
        g.run(90)
        self.assertLess(g.find("P").x, 100)
        # both sides must agree
        wall2 = obj("Wall", x=100, y=0, w=20, h=500, solid=True, cgroup=2, cmask=0)
        g = Game("on start\n    self.vx = 300\n", extra=[wall2], body=True, x=0)
        g.run(90)
        self.assertGreater(g.find("P").x, 300)

    def test_script_can_change_physics_fields(self):
        g = Game('on start\n    self.trigger = true\n    self.cgroup = 3\n    self.cmask = 7\n    print(self.trigger, self.cgroup, self.cmask)\n')
        self.assertEqual(g.out, ["true 3 7"])
        g = Game("on start\n    self.cgroup = 9\n")
        self.assertIsNotNone(g.error)

    def test_trigger_is_not_solid(self):
        zone = obj("Zone", x=0, y=100, w=200, h=20, solid=True, trigger=True)
        g = Game("on start\n    print(1)\n", extra=[zone], body=True, y=0)
        g.run(60)
        self.assertGreater(g.find("P").y, 150)


class TouchEvents(unittest.TestCase):
    def test_enter_and_exit(self):
        proj = new_project()
        proj.write_script("z.pawn", 'on touch as who\n    print("in", who.name)\non untouch as who\n    print("out", who.name)\n')
        zone = obj("Zone", "z.pawn", x=100, y=0, w=50, h=50, solid=True, trigger=True)
        g = Game("every 0.01 seconds\n    self.x += 5\n", proj=proj, extra=[zone], x=0)
        g.run(120)
        self.assertEqual(g.out, ["in P", "out P"])

    def test_not_fired_again_while_staying_inside(self):
        proj = new_project()
        proj.write_script("z.pawn", 'on touch as who\n    print("in")\n')
        zone = obj("Zone", "z.pawn", x=0, y=0, w=100, h=100, trigger=True)
        g = Game("on start\n    print('x')\n", proj=proj, extra=[zone])
        g.run(60)
        self.assertEqual(g.out.count("in"), 1)

    def test_pickup_destroys_itself(self):
        proj = new_project()
        proj.write_script("coin.pawn", 'on touch as who\n    if who.has_tag("player")\n        game.score += 1\n        self.destroy()\n')
        coins = [obj("Coin", "coin.pawn", x=0, y=0, w=20, h=20, tags=["coin"]) for _ in range(3)]
        g = Game("on start\n    self.tag('player')\n", proj=proj, extra=coins)
        g.run(5)
        self.assertEqual(g.rt.game.d["score"], 3)
        self.assertEqual(len(g.rt.all_named("Coin")), 0)

    def test_groups_filter_touches(self):
        proj = new_project()
        proj.write_script("z.pawn", 'on touch as who\n    print("in")\n')
        zone = obj("Zone", "z.pawn", x=0, y=0, w=100, h=100, trigger=True, cmask=1)
        g = Game("on start\n    print('x')\n", proj=proj, extra=[zone], cgroup=2)
        g.run(10)
        self.assertNotIn("in", g.out)

    def test_many_watchers_stay_fast(self):
        import time
        proj = new_project()
        proj.write_script("c.pawn", 'on touch as who\n    print("t")\n')
        coins = [obj("Coin", "c.pawn", x=i * 30 - 6000, y=(i % 7) * 40, w=20, h=20, trigger=True) for i in range(400)]
        g = Game("on start\n    print('x')\n", proj=proj, extra=coins)
        t = time.perf_counter()
        g.run(30)
        self.assertLess((time.perf_counter() - t) / 30, 0.02)


class TileMaps(unittest.TestCase):
    def test_set_get_cells_and_round_trip(self):
        o = GameObject("M", "tilemap")
        tilemap.set_tile(o, 2, -1, 5)
        self.assertEqual(tilemap.get(o, 2, -1), 5)
        self.assertEqual(tilemap.get(o, 0, 0), -1)
        c = GameObject.from_dict(json.loads(json.dumps(o.to_dict())))
        self.assertEqual(c.tiles, {"2,-1": 5})
        tilemap.set_tile(o, 2, -1, -1)
        self.assertEqual(o.tiles, {})

    def test_junk_tiles_are_cleaned(self):
        c = GameObject.from_dict({"kind": "tilemap", "tiles": {"1,1": 3, "x": 1, "2,2": "no", "3,3": -4}, "tile_size": "big"})
        self.assertEqual(c.tiles, {"1,1": 3})
        self.assertEqual(c.tile_size, 32)

    def test_rows_merge_into_collision_boxes(self):
        o = GameObject("M", "tilemap")
        for c in (0, 1, 2, 5):
            tilemap.set_tile(o, c, 0, 1)
        rects = sorted(tilemap.solid_rects(o))
        self.assertEqual(len(rects), 2)
        self.assertEqual(rects[0][2], 96)
        tilemap.set_tile(o, 3, 0, 1)
        self.assertEqual(len(tilemap.solid_rects(o)), 2)          # cache rebuilt: 0-3 and 5
        self.assertEqual(sorted(tilemap.solid_rects(o))[0][2], 128)

    def test_cell_at_matches_tile_centres(self):
        o = GameObject("M", "tilemap")
        o.x, o.y = 100, 50
        self.assertEqual(tilemap.cell_at(o, 100, 50), (0, 0))
        self.assertEqual(tilemap.cell_at(o, 100 + 32 * 3 + 10, 50 - 32), (3, -1))
        self.assertEqual(tilemap.cell_at(o, 100 - 17, 50), (-1, 0))

    def test_body_stands_on_solid_tiles(self):
        m = obj("Map", kind="tilemap", x=0, y=200, tile_size=32, solid=True, tiles={f"{c},0": 0 for c in range(-5, 6)})
        g = Game("on start\n    print(1)\n", extra=[m], body=True, y=0)
        g.run(120)
        self.assertAlmostEqual(g.find("P").y, 200 - 16 - 5, delta=1)
        self.assertTrue(g.find("P").on_ground)

    def test_script_api(self):
        m = obj("Map", kind="tilemap", x=0, y=0, tile_size=32)
        g = Game('on start\n    m = find("Map")\n    m.set_tile(1, 1, 4)\n    print(m.get_tile(1, 1), m.get_tile(0, 0))\n'
                 '    print(m.tile_at(32, 32))\n    m.fill_tiles("#.#\\n.#.", {"#": 2})\n'
                 '    print(m.get_tile(0, 0), m.get_tile(1, 0), m.get_tile(1, 1), m.tile_size)\n    m.clear_tiles()\n'
                 '    print(m.get_tile(0, 0))\n', extra=[m])
        self.assertEqual(g.out, ["4 -1", "4", "2 -1 2 32", "-1"])

    def test_wrong_kind_is_friendly(self):
        g = Game('on start\n    self.set_tile(1, 1, 1)\n')
        self.assertIn("tile map", str(g.error))


class ParticlesAndShake(unittest.TestCase):
    def test_emits_ages_and_dies(self):
        o = GameObject("E", "particles")
        o.em_rate, o.em_life = 100, 0.5
        import random
        rng = random.Random(1)
        for _ in range(30):
            particles.update(o, 1 / 60, rng)
        self.assertGreater(len(o.parts), 10)
        o.em_on = False
        for _ in range(60):
            particles.update(o, 1 / 60, rng)
        self.assertEqual(o.parts, [])

    def test_burst_and_cap(self):
        e = obj("Fx", kind="particles", em_on=False, em_life=1.0)
        g = Game('on start\n    fx = find("Fx")\n    fx.burst(25)\n    each i in range(50)\n        fx.burst(500)\n', extra=[e])
        self.assertIsNone(g.error)
        self.assertLessEqual(len(g.find("Fx").parts), particles.MAX_PARTICLES)
        self.assertGreater(len(g.find("Fx").parts), 25)

    def test_gravity_pulls_down(self):
        o = GameObject("E", "particles")
        o.em_on, o.em_speed, o.em_gravity, o.em_spread = False, 0, 1000, 0
        import random
        particles.spawn(o, random.Random(1), 1)
        particles.update(o, 0.3, random.Random(1))
        self.assertGreater(o.parts[0][1], 0)

    def test_emitting_property(self):
        e = obj("Fx", kind="particles")
        g = Game('on start\n    fx = find("Fx")\n    fx.emitting = false\n    print(fx.emitting)\n', extra=[e])
        self.assertEqual(g.out, ["false"])

    def test_shake_moves_camera_then_settles(self):
        g = Game("on start\n    shake(30, 0.5)\n")
        xs = []
        for _ in range(20):
            g.run(1)
            xs.append(g.rt.cam[0])
        self.assertTrue(any(abs(x) > 0.5 for x in xs))
        g.run(60)
        self.assertEqual(g.rt.cam, [0.0, 0.0])

    def test_camera_shake_method(self):
        g = Game("on start\n    camera.shake(5)\n")
        self.assertIsNone(g.error)
        self.assertGreater(g.rt.shake_t, 0)


class Polygons(unittest.TestCase):
    def test_points_round_trip_and_cleaning(self):
        o = GameObject("P", "polygon")
        o.points = [[0, -0.5], [0.5, 0.5], [-0.5, 0.5]]
        c = GameObject.from_dict(json.loads(json.dumps(o.to_dict())))
        self.assertEqual(c.points, o.points)
        bad = GameObject.from_dict({"kind": "polygon", "points": [[0, 0], "x", [1], [1, "a"], [0.5, 0.5]]})
        self.assertEqual(bad.points, [[0.0, 0.0], [0.5, 0.5]])

    def test_svg_shapes(self):
        svg = ('<svg xmlns="http://www.w3.org/2000/svg"><rect x="0" y="0" width="10" height="20" fill="red"/>'
               '<polygon points="0,0 10,0 5,10" style="fill:#0f0"/>'
               '<path d="M 0 0 H 10 V 10 Z" fill="#123456"/><path d="M0 0 C 1 1 2 2 3 3" fill="blue"/></svg>')
        shapes, notes = parse_svg(svg)
        self.assertEqual(len(shapes), 4)
        self.assertEqual(shapes[0]["color"], "#ff0000")
        self.assertEqual(shapes[1]["color"], "#00ff00")
        self.assertEqual(shapes[2]["points"], [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)])
        self.assertEqual(shapes[3]["points"][0], (0.0, 0.0))        # the curve is kept, flattened
        self.assertAlmostEqual(shapes[3]["points"][-1][0], 3.0)
        self.assertEqual(notes, [])

    def test_svg_relative_commands(self):
        shapes, _ = parse_svg('<svg><path d="m 10 10 l 20 0 l 0 20 z" fill="none"/></svg>')
        self.assertEqual(shapes[0]["points"], [(10.0, 10.0), (30.0, 10.0), (30.0, 30.0)])

    def test_curves_arcs_circles_are_flattened(self):
        shapes, _ = parse_svg('<svg><path d="M 0 0 C 0 10 10 10 10 0 S 20 -10 20 0 Z" fill="#111111"/>'
                              '<path d="M 0 0 Q 5 10 10 0 T 20 0 Z"/>'
                              '<path d="M 10 0 A 10 10 0 1 1 -10 0 A 10 10 0 1 1 10 0 Z"/>'
                              '<path d="M0 0a5 5 0 0110 0z"/>'
                              '<circle cx="5" cy="5" r="5"/><ellipse cx="0" cy="0" rx="4" ry="2"/></svg>')
        self.assertEqual(len(shapes), 6)
        self.assertGreater(len(shapes[0]["points"]), 20)
        self.assertGreater(len(shapes[1]["points"]), 20)
        xs = [p[0] for p in shapes[2]["points"]]
        ys = [p[1] for p in shapes[2]["points"]]
        self.assertAlmostEqual(max(xs) - min(xs), 20, delta=0.5)      # a full circle of radius 10
        self.assertAlmostEqual(max(ys) - min(ys), 20, delta=0.5)
        self.assertAlmostEqual(shapes[3]["points"][-1][0], 10.0, delta=0.01)    # compact flags "0110" work
        self.assertEqual(len(shapes[4]["points"]), 36)

    def test_bad_svg_is_friendly(self):
        with self.assertRaises(ValueError):
            parse_svg("<svg><oops")

    def test_normalise(self):
        cx, cy, w, h, pts = normalise([(10, 10), (30, 10), (30, 50)], 2.0)
        self.assertEqual((cx, cy, w, h), (40.0, 60.0, 40.0, 80.0))
        self.assertEqual(pts[0], [-0.5, -0.5])


if __name__ == "__main__":
    unittest.main()
