"""Tests for v0.3: sprite animation, vx/friction/bounce, audio mixer, UI objects and events, themes, audio builtins."""
import unittest

from helpers import Game, make_scene, obj, new_project
from engine.animation import parse_anims, format_anims
from engine.mixer import Mixer
from engine.theme import merged, resolve, DEFAULT_THEME
from engine.gameobject import GameObject
from engine.runtime import Runtime


class Animation(unittest.TestCase):
    def test_parse_and_format_round_trip(self):
        a = parse_anims("run = 0-3 @ 10 loop\nidle = 4\njump = 5,6,7 @ 8 once  # comment")
        self.assertEqual(a["run"]["frames"], [0, 1, 2, 3])
        self.assertTrue(a["run"]["loop"] and not a["jump"]["loop"])
        self.assertEqual(parse_anims(format_anims(a)), a)

    def test_bad_line_is_friendly(self):
        with self.assertRaises(ValueError) as c:
            parse_anims("run = zero to three")
        self.assertIn("Line 1", str(c.exception))

    def test_clip_steps_through_frames_and_once_stops(self):
        anims = {"run": {"frames": [0, 1, 2], "fps": 10.0, "loop": True}, "hit": {"frames": [3, 4], "fps": 10.0, "loop": False}}
        g = Game('on start\n    self.play_anim("run")\n', sheet_cols=5, sheet_rows=1, anims=anims)
        seen = set()
        for _ in range(40):
            g.run(1)
            seen.add(g.find("P").frame)
        self.assertEqual(seen, {0, 1, 2})
        self.assertIsNone(g.error)
        g2 = Game('on start\n    self.play_anim("hit")\n', sheet_cols=5, sheet_rows=1, anims=anims)
        g2.run(60)
        self.assertEqual(g2.find("P").frame, 4)

    def test_unknown_clip_suggests(self):
        anims = {"run": {"frames": [0, 1], "fps": 8.0, "loop": True}}
        g = Game('on start\n    self.play_anim("rn")\n', sheet_cols=2, sheet_rows=1, anims=anims)
        self.assertIsNotNone(g.error)
        self.assertIn("run", str(g.error) + " " + str(g.error.hint))

    def test_autoplay(self):
        anims = {"run": {"frames": [1, 2], "fps": 10.0, "loop": True}}
        g = Game("on start\n    print(1)\n", sheet_cols=3, sheet_rows=1, anims=anims, anim="run")
        g.run(20)
        self.assertIn(g.find("P").frame, (1, 2))


class Physics(unittest.TestCase):
    def floor(self):
        return [obj("Floor", x=0, y=200, w=2000, h=40, solid=True)]

    def test_friction_stops_a_slide(self):
        g = Game("on start\n    self.vx = 300\n", extra=self.floor(), body=True, friction=8, y=150)
        g.run(180)
        self.assertLess(abs(g.find("P").vx), 1)

    def test_no_friction_keeps_sliding(self):
        g = Game("on start\n    self.vx = 300\n", extra=self.floor(), body=True, friction=0, y=150)
        g.run(120)
        self.assertGreater(g.find("P").vx, 250)

    def test_bounce_rebounds_up(self):
        g = Game("on start\n    self.vy = 0\n", extra=self.floor(), body=True, bounce=0.8, y=0)
        peaks, last = 0, None
        for _ in range(400):
            g.run(1)
            y = g.find("P").y
            if last is not None and last > y + 0.01 and g.find("P").y < 170:
                peaks += 1
            last = y
        self.assertGreater(peaks, 5)

    def test_wall_bounce_flips_vx(self):
        wall = obj("Wall", x=120, y=0, w=20, h=400, solid=True)
        g = Game("on start\n    self.vx = 400\n", extra=[wall], body=True, bounce=1, x=0)
        g.run(90)
        self.assertLess(g.find("P").vx, 0)


class MixerTests(unittest.TestCase):
    def test_effective_levels_and_mute(self):
        m = Mixer({"master": 0.5, "music": 0.5})
        self.assertAlmostEqual(m.effective("music"), 0.25)
        self.assertAlmostEqual(m.effective("sound"), 0.5)
        m.muted = True
        self.assertEqual(m.effective("music"), 0.0)

    def test_set_clamps(self):
        m = Mixer()
        m.set("music", 5)
        self.assertEqual(m.level["music"], 1.0)
        with self.assertRaises(KeyError):
            m.set("bass", 1)

    def test_fade_out_then_stop(self):
        m = Mixer()
        m.fade_music(0, 1.0, stop=True)
        res = None
        for _ in range(70):
            res = m.update(1 / 60) or res
        self.assertEqual(res, "stop")
        self.assertEqual(m.level["music"], 0.0)
        self.assertFalse(m.fading())

    def test_instant_fade(self):
        m = Mixer()
        self.assertEqual(m.fade_music(0.2, 0, stop=True), "stop")
        self.assertEqual(m.level["music"], 0.2)


class FakeAudio:
    def __init__(self):
        self.calls = []
        self.mixer = Mixer()

    def __getattr__(self, name):
        def f(*a):
            self.calls.append((name,) + a)
        return f

    def play_sound(self, name, vol):
        self.calls.append(("play_sound", name, vol))

    def play_music(self, name, loop, vol):
        self.calls.append(("play_music", name, loop, vol))

    def set_volume(self, k, v):
        self.calls.append(("set_volume", k, v))

    def get_volume(self, k):
        return 0.25

    def music_playing(self):
        return True


def run_with_audio(src):
    proj = new_project()
    proj.write_script("a.pawn", src)
    audio = FakeAudio()
    out = []
    rt = Runtime(make_scene(obj("P", "a.pawn")), proj, console=lambda m, l="print": out.append(m), audio=audio)
    rt.start()
    rt.update(1 / 60)
    return audio, out


class AudioBuiltins(unittest.TestCase):
    def test_play_with_volume(self):
        a, _ = run_with_audio('on start\n    play("coin", 0.5)\n')
        self.assertIn(("play_sound", "coin", 0.5), a.calls)

    def test_music_and_volume(self):
        a, out = run_with_audio('on start\n    play_music("theme", true, 0.7)\n    volume("music", 0.4)\n'
                                '    volume(2)\n    print(get_volume("music"), music_playing())\n')
        self.assertIn(("play_music", "theme", True, 0.7), a.calls)
        self.assertIn(("set_volume", "music", 0.4), a.calls)
        self.assertIn(("set_volume", "master", 1.0), a.calls)
        self.assertEqual(out, ["0.25 true"])

    def test_fade_pause_mute(self):
        a, _ = run_with_audio('on start\n    fade_music(0, 2, true)\n    pause_music()\n    resume_music()\n    mute()\n')
        names = [c[0] for c in a.calls]
        for n in ("fade_music", "pause_music", "resume_music", "mute"):
            self.assertIn(n, names)

    def test_bad_bus_is_friendly(self):
        proj = new_project()
        proj.write_script("a.pawn", 'on start\n    volume("bass", 1)\n')
        rt = Runtime(make_scene(obj("P", "a.pawn")), proj, console=lambda *a: None, audio=FakeAudio())
        with self.assertRaises(Exception) as c:
            rt.start()
        self.assertIn("master", str(c.exception))

    def test_no_audio_device_never_crashes(self):
        g = Game('on start\n    play("coin")\n    play_music("x")\n    volume("music", 0.2)\n    print(music_playing())\n')
        self.assertIsNone(g.error)
        self.assertEqual(g.out, ["false"])


class UITests(unittest.TestCase):
    def click(self, g, x, y, frames=3):
        rt = g.rt
        rt.mx, rt.my = x, y
        rt.mouse_down = True
        g.run(frames)
        rt.mouse_down = False
        g.run(frames)

    def test_button_click_event(self):
        btn = obj("Btn", "b.pawn", kind="button", x=100, y=50, w=100, h=40, hud=False)
        proj = new_project()
        proj.write_script("b.pawn", 'count = 0\non click\n    count += 1\n    print("clicked", count)\n')
        proj.write_script("a.pawn", "on start\n    print(1)\n")
        g = Game("on start\n    print('x')\n", proj=proj, extra=[btn])
        self.click(g, 100, 50)
        self.click(g, 100, 50)
        self.assertIn("clicked 1", g.out)
        self.assertIn("clicked 2", g.out)

    def test_click_outside_does_nothing_and_release_off_cancels(self):
        btn = obj("Btn", "b.pawn", kind="button", x=100, y=50, w=100, h=40, hud=False)
        proj = new_project()
        proj.write_script("b.pawn", 'on click\n    print("c")\non press\n    print("p")\non release\n    print("r")\n')
        g = Game("on start\n    print('x')\n", proj=proj, extra=[btn])
        self.click(g, 400, 400)
        self.assertEqual([m for m in g.out if m in "cpr"], [])
        g.rt.mx, g.rt.my, g.rt.mouse_down = 100, 50, True
        g.run(2)
        g.rt.mx = 400
        g.rt.mouse_down = False
        g.run(2)
        self.assertEqual([m for m in g.out if m in "cpr"], ["p", "r"])

    def test_hover_and_leave(self):
        btn = obj("Btn", "b.pawn", kind="button", x=100, y=50, w=100, h=40, hud=False)
        proj = new_project()
        proj.write_script("b.pawn", 'on hover\n    print("in")\non leave\n    print("out")\n')
        g = Game("on start\n    print('x')\n", proj=proj, extra=[btn])
        g.rt.mx, g.rt.my = 100, 50
        g.run(2)
        g.rt.mx = 600
        g.run(2)
        self.assertEqual([m for m in g.out if m in ("in", "out")], ["in", "out"])

    def test_slider_drag_sets_value_and_fires_change(self):
        sl = obj("S", "s.pawn", kind="slider", x=0, y=100, w=200, h=20, hud=False, value=0.0)
        proj = new_project()
        proj.write_script("s.pawn", 'on change as v\n    print("v", round(v * 100))\n')
        g = Game("on start\n    print('x')\n", proj=proj, extra=[sl])
        g.rt.mx, g.rt.my, g.rt.mouse_down = 50, 100, True       # 75% along a 200 wide slider centered at 0
        g.run(2)
        g.rt.mouse_down = False
        g.run(1)
        self.assertAlmostEqual(g.find("S").value, 0.75, places=2)
        self.assertIn("v 75", g.out)

    def test_checkbox_toggles(self):
        cb = obj("C", "c.pawn", kind="checkbox", x=0, y=100, w=100, h=30, hud=False)
        proj = new_project()
        proj.write_script("c.pawn", 'on change as v\n    print("now", v)\n')
        g = Game("on start\n    print('x')\n", proj=proj, extra=[cb])
        self.click(g, 0, 100)
        self.click(g, 0, 100)
        self.assertEqual([m for m in g.out if m.startswith("now")], ["now true", "now false"])

    def test_text_input_typing(self):
        ti = obj("T", "t.pawn", kind="input", x=0, y=100, w=200, h=40, hud=False, text="")
        proj = new_project()
        proj.write_script("t.pawn", 'on submit as t\n    print("got", t)\n')
        g = Game("on start\n    print('x')\n", proj=proj, extra=[ti])
        self.click(g, 0, 100)
        self.assertTrue(g.rt.ui.focus is g.find("T"))
        g.rt.typed.extend("hix\b\n")
        g.run(1)
        self.assertEqual(g.find("T").text, "hi")
        self.assertIn("got hi", g.out)
        self.click(g, 400, 400)
        self.assertIsNone(g.rt.ui.focus)

    def test_disabled_ignores_mouse(self):
        btn = obj("Btn", "b.pawn", kind="button", x=100, y=50, w=100, h=40, hud=False, enabled=False)
        proj = new_project()
        proj.write_script("b.pawn", 'on click\n    print("c")\n')
        g = Game("on start\n    print('x')\n", proj=proj, extra=[btn])
        self.click(g, 100, 50)
        self.assertNotIn("c", g.out)

    def test_bad_event_name_is_friendly(self):
        g = Game("on clck\n    print(1)\n")
        self.assertIsNotNone(g.error)
        self.assertIn("click", str(g.error))

    def test_script_can_read_and_set_ui_fields(self):
        sl = obj("S", kind="bar", x=0, y=100, w=200, h=20, hud=False, value=0.2)
        g = Game('on start\n    b = find("S")\n    b.value = b.value + 0.5\n    print(b.value)\n', extra=[sl])
        self.assertEqual(g.out, ["0.7"])

    def test_anchored_hud_follows_camera_and_zoom(self):
        o = GameObject("H", "button")
        o.hud, o.anchor, o.x, o.y = True, "top-left", 50, 30
        self.assertEqual(o.world_pos((0.0, 0.0, 1.0)), (-430.0, -240.0))
        self.assertEqual(o.world_pos((100.0, 0.0, 2.0)), (-90.0, -105.0))

    def test_hud_click_with_camera_moved(self):
        btn = obj("Btn", "b.pawn", kind="button", x=0, y=0, w=100, h=40, hud=True, anchor="center")
        proj = new_project()
        proj.write_script("b.pawn", 'on click\n    print("hud")\n')
        g = Game("on start\n    print('x')\n", proj=proj, extra=[btn])
        g.find("Main Camera").x = 500        # the camera moved, a HUD button stays under the screen centre
        g.run(2)
        self.click(g, 500, 0)
        self.assertIn("hud", g.out)


class ThemeAndSaves(unittest.TestCase):
    def test_theme_merge_ignores_junk(self):
        t = merged({"accent": "#fff", "radius": "huge", "nope": 1})
        self.assertEqual(t["accent"], "#fff")
        self.assertEqual(t["radius"], DEFAULT_THEME["radius"])
        self.assertNotIn("nope", t)

    def test_resolve_prefers_own_color(self):
        o = GameObject("B", "button")
        o.color = ""
        self.assertEqual(resolve(o, "color", DEFAULT_THEME), DEFAULT_THEME["button"])
        o.color = "#123456"
        self.assertEqual(resolve(o, "color", DEFAULT_THEME), "#123456")

    def test_project_theme_and_audio_persist(self):
        proj = new_project()
        proj.set_theme({"accent": "#ff0000"})
        proj.set_audio_levels({"music": 0.3})
        from engine.project import Project
        again = Project(proj.path)
        self.assertEqual(again.theme["accent"], "#ff0000")
        self.assertEqual(again.audio_levels["music"], 0.3)

    def test_object_ui_and_sheet_fields_round_trip(self):
        o = GameObject("S", "slider")
        o.value, o.anchor, o.enabled, o.sheet_cols = 0.4, "bottom", False, 4
        o.anims = {"run": {"frames": [0, 1], "fps": 6.0, "loop": True}}
        c = GameObject.from_dict(o.to_dict())
        self.assertEqual((c.value, c.anchor, c.enabled, c.sheet_cols), (0.4, "bottom", False, 4))
        self.assertEqual(c.anims["run"]["frames"], [0, 1])

    def test_junk_in_old_or_hand_edited_scene_is_sanitized(self):
        c = GameObject.from_dict({"name": "X", "kind": "sprite", "sheet_cols": -5, "anims": "oops"})
        self.assertGreaterEqual(c.sheet_cols, 1)
        self.assertEqual(c.anims, {})

    def test_font_import(self):
        import tempfile
        from pathlib import Path
        proj = new_project()
        f = Path(tempfile.mkdtemp()) / "My Font.ttf"
        f.write_bytes(b"not really a font")
        rel = proj.import_asset(f)
        self.assertEqual(rel, "assets/fonts/My_Font.ttf")
        self.assertEqual(proj.list_assets("font"), [(rel, "font")])


if __name__ == "__main__":
    unittest.main()
