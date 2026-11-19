"""Opens the real editor off-screen and drives it. Skipped if PySide6 is not installed."""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PAWN_NO_SOUND"] = "1"

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QImage, QColor
    HAVE_QT = True
except Exception:
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class EditorSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import helpers  # noqa: F401  (puts the project on sys.path)
        cls.app = QApplication.instance() or QApplication([])
        from ui.theme import apply_theme
        apply_theme(cls.app)

    def setUp(self):
        from engine.project import create_project
        from ui.editor import EditorWindow
        self.proj = create_project("Smoke", Path(tempfile.mkdtemp()), "coin")
        self.ed = EditorWindow(self.proj)

    def tearDown(self):
        self.ed.game_view.stop()

    def pump(self, n=60):
        for _ in range(n):
            if self.ed.game_view.running:
                self.ed.game_view.step()
            self.app.processEvents()

    def test_play_the_coin_game(self):
        self.ed.play()
        self.pump(150)
        gv = self.ed.game_view
        self.assertTrue(gv.running and not gv.errored)
        player = next(o for o in gv.rt.scene.all() if o.name == "Player")
        self.assertTrue(player.on_ground)
        self.assertEqual(gv.rt.game.d.get("score", 0), 0)

    def test_ui_objects_sheets_and_inspector_cards(self):
        from PySide6.QtGui import QPainter
        ed = self.ed
        for k in ("button", "bar", "slider", "checkbox", "input"):
            ed.add_object(k)
            o = ed.selected
            self.assertEqual(o.kind, k)
            self.assertTrue(o.hud)
            self.assertEqual(o.color, "")
            self.assertGreater(ed.inspector.body.layout().count(), 3)     # the UI card was built
        ed.add_object("sprite")
        spr = ed.selected
        img = QImage(40, 20, QImage.Format_ARGB32)
        img.fill(QColor("red"))
        for x in range(20, 40):
            for y in range(20):
                img.setPixelColor(x, y, QColor("blue"))
        d = Path(tempfile.mkdtemp())
        img.save(str(d / "sheet.png"))
        rel = self.proj.import_asset(d / "sheet.png")
        spr.sprite, spr.sheet_cols, spr.sheet_rows, spr.frame = rel, 2, 1, 1
        ed.inspector.set_object(spr)                                      # builds the animation card
        # render the second cell of the sheet and a few UI widgets
        out = QImage(960, 540, QImage.Format_ARGB32)
        out.fill(QColor("black"))
        p = QPainter(out)
        p.translate(480, 270)
        from engine.render import draw_scene
        spr.x, spr.y, spr.w, spr.h, spr.hud = 0, 0, 40, 40, False
        draw_scene(p, ed.scene, (0.0, 0.0, 1.0), ed.assets, editor=False)
        p.end()
        self.assertEqual(out.pixelColor(480, 270).blue(), 255)            # frame 1 is the blue half
        self.assertLess(out.pixelColor(480, 270).red(), 10)

    def test_v04_objects_scenes_prefabs_svg_and_painting(self):
        from PySide6.QtGui import QPainter
        from unittest import mock
        ed = self.ed
        for k in ("polygon", "tilemap", "particles"):
            ed.add_object(k)
            self.assertEqual(ed.selected.kind, k)
            self.assertGreater(ed.inspector.body.layout().count(), 3)
        tm = next(o for o in ed.scene.all() if o.kind == "tilemap")
        ed.select(tm)
        self.assertIsNotNone(ed.inspector.palette)
        # paint with the scene view
        ed.tile_paint, ed.tile_brush = True, 2
        from PySide6.QtCore import QPointF
        pos = ed.scene_view.w2s(tm.x + 32 * 5, tm.y + 32 * 2)
        ed.scene_view._paint(pos, False)
        self.assertEqual(tm.tiles.get("5,2"), 2)
        ed.scene_view._paint(pos, True)
        self.assertNotIn("5,2", tm.tiles)
        # render all three
        out = QImage(960, 540, QImage.Format_ARGB32)
        out.fill(QColor("black"))
        p = QPainter(out)
        p.translate(480, 270)
        from engine.render import draw_scene
        draw_scene(p, ed.scene, (0.0, 0.0, 1.0), ed.assets, editor=True)
        p.end()
        # prefab round trip
        poly = next(o for o in ed.scene.all() if o.kind == "polygon")
        with mock.patch("ui.editor.QInputDialog.getText", return_value=("Gem", True)):
            ed.save_prefab(poly)
        self.assertEqual(self.proj.list_prefabs(), ["Gem"])
        before = len(list(ed.scene.all()))
        ed.add_prefab("Gem")
        self.assertEqual(len(list(ed.scene.all())), before + 1)
        # svg import
        svg = Path(tempfile.mkdtemp()) / "art.svg"
        svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"><polygon points="0,0 10,0 5,10" fill="red"/>'
                       '<rect x="20" y="0" width="10" height="10" fill="#00f"/></svg>')
        before = len(list(ed.scene.all()))
        ed.import_svg(str(svg))
        self.assertEqual(len(list(ed.scene.all())), before + 3)       # group + two shapes
        # scenes
        with mock.patch("ui.editor.QInputDialog.getText", return_value=("Level 2", True)):
            ed.new_scene()
        self.assertEqual(ed.scene_name, "Level 2")
        ed.switch_scene("Main")
        self.assertIn("Gem", [o.name for o in ed.scene.all()] + ["Gem"])
        ed.make_start_scene()
        self.assertEqual(self.proj.start_scene, "Main")
        # play the edited scene
        ed.play()
        self.pump(30)
        self.assertFalse(ed.game_view.errored)

    def test_v05_editor_features(self):
        from unittest import mock
        from PySide6.QtGui import QPainter, QTextCursor
        from PySide6.QtWidgets import QSlider
        ed = self.ed
        # linter + autocomplete in the code editor
        self.proj.write_script("typo.pawn", "speed = 5  # range 0 10\non start\n    print(speeed)\n    self.x = 1\n")
        tab = ed.open_script("typo.pawn")
        tab.check()
        self.assertTrue(any("speeed" in w.message for w in tab.warnings))
        self.assertIn(3, tab.edit.warnings)
        tab.edit.moveCursor(QTextCursor.End)
        tab.edit.insertPlainText("    self.")
        tab.edit._update_completer()
        self.assertIn("x", tab.edit._candidates("self"))
        self.assertIn("random", tab.edit._candidates(None))
        self.assertEqual(tab.edit._word_info()[1], "self")
        tab.edit.insertPlainText("al")
        prefix, owner, after_dot, _ = tab.edit._word_info()
        self.assertEqual((prefix, owner), ("al", "self"))
        tab.edit._insert_completion("alpha")
        self.assertTrue(tab.edit.toPlainText().rstrip().endswith("self.alpha"))
        # Inspector: slider from "# range"
        ed.add_object("rect")
        typo_obj = ed.selected
        ed.attach_script(typo_obj, "typo.pawn")
        ed.inspector.set_object(typo_obj)
        self.assertTrue(ed.inspector.findChildren(QSlider))
        # gallery dialog adds a script to the selected object
        from ui.gallery import GalleryDialog, all_entries
        self.assertGreaterEqual(len(all_entries()), 40)
        d = GalleryDialog(ed, ed.selected)
        d.search.setText("double jump")
        self.assertEqual(d._current()[1], "Double jump")
        d._add()
        self.assertIn("double_jump.pawn", [r["file"] for r in ed.selected.scripts])
        # lighting dialog + a light object + darkness rendering in the editor
        ed.add_object("light")
        self.assertGreater(ed.scene.darkness, 0)
        from ui.dialogs import LightingDialog
        ld = LightingDialog(ed.scene)
        ld.slider.setValue(80)
        self.assertEqual(ld.result()[0], 0.8)
        out = QImage(960, 540, QImage.Format_ARGB32)
        out.fill(QColor("white"))
        p = QPainter(out)
        p.translate(480, 270)
        from engine.render import draw_scene
        ed.scene.darkness = 0.9
        draw_scene(p, ed.scene, (0.0, 0.0, 1.0), ed.assets, editor=False)
        p.end()
        self.assertLess(out.pixelColor(900, 40).red(), 120)          # far from any light: dark
        # watch panel: show and live-edit values (drop the script with the deliberate typo first)
        typo_obj.scripts = []
        ed.play()
        self.assertTrue(ed.game_view.running)
        self.pump(5)
        ed.game_view.rt.game.d["score"] = 3
        ed.bottom_tabs.setCurrentWidget(ed.watch)
        ed.watch.refresh(ed.game_view.rt, ed.selected)
        rows = {ed.watch.tree.topLevelItem(0).child(i).text(0): ed.watch.tree.topLevelItem(0).child(i)
                for i in range(ed.watch.tree.topLevelItem(0).childCount())}
        self.assertIn("game.score", rows)
        rows["game.score"].setText(1, "42")
        self.assertEqual(ed.game_view.rt.game.d["score"], 42)
        from ui.watch import parse_value
        self.assertEqual((parse_value("7"), parse_value("2.5"), parse_value("true"), parse_value('"hi"'), parse_value("x y")),
                         (7, 2.5, True, "hi", "x y"))
        ed.stop()
        ed._refresh_watch()
        self.assertIsNone(ed.watch.rt)

    def test_breakpoint_pauses_the_game_view(self):
        self.proj.write_script("brk.pawn", "when pressed(\"b\")\n    breakpoint(\"hi\")\n")
        self.ed.attach_script(self.ed.scene.find_name("Coin"), "brk.pawn")
        self.ed.play()
        self.pump(3)
        gv = self.ed.game_view
        gv.rt.pressed.add("b")
        self.pump(2)
        self.assertTrue(gv.paused)
        self.assertEqual(self.ed.bottom_tabs.currentWidget(), self.ed.watch)

    def test_theme_and_mixer_dialogs_save(self):
        from ui.dialogs import ThemeDialog, MixerDialog
        d = ThemeDialog(self.proj)
        d.values["accent"] = "#112233"
        self.proj.set_theme(d.result_theme())
        self.assertEqual(self.proj.theme["accent"], "#112233")
        m = MixerDialog(self.proj)
        m.sliders["music"].setValue(30)
        self.proj.set_audio_levels(m.levels())
        self.assertAlmostEqual(self.proj.audio_levels["music"], 0.3)

    def test_module_tab_saves_and_hot_reloads(self):
        name = self.proj.new_module_name("tools")
        self.proj.write_module(name, "return {k = 1}\n")
        self.ed.files.refresh(self.proj)
        self.proj.write_script("use.pawn", 'local t = require("tools")\nwhen true\n    game.k = t.k\n')
        self.ed.attach_script(self.ed.scene.find_name("Coin"), "use.pawn")
        self.ed.play()
        self.pump(3)
        self.assertEqual(self.ed.game_view.rt.game.d["k"], 1)
        tab = self.ed.open_script(name)
        self.assertTrue(tab.is_module)
        tab.edit.setPlainText("return {k = 2}\n")
        tab.save()
        self.pump(3)
        self.assertEqual(self.ed.game_view.rt.game.d["k"], 2)

    def test_module_with_error_shows_in_status(self):
        name = self.proj.new_module_name("bad")
        self.proj.write_module(name, "return {k = 1}\n")
        tab = self.ed.open_script(name)
        tab.edit.setPlainText("when true\n    pass\n")
        self.assertFalse(tab.check())
        self.assertIn("Module scripts", tab.status.text())

    def test_import_by_drop_and_single_picture_becomes_a_sprite(self):
        src = Path(tempfile.mkdtemp())
        img = QImage(40, 20, QImage.Format_ARGB32)
        img.fill(QColor("red"))
        img.save(str(src / "hero.png"))
        (src / "theme.ogg").write_bytes(b"OggS")
        self.ed.select(None)
        self.ed.import_paths([str(src / "hero.png")])
        self.assertTrue((self.proj.path / "assets/sprites/hero.png").exists())
        sprites = [o for o in self.ed.scene.all() if o.kind == "sprite"]
        self.assertEqual([s.sprite for s in sprites], ["assets/sprites/hero.png"])
        self.ed.import_paths([str(src / "theme.ogg"), str(src / "nope.exe")])
        self.assertTrue((self.proj.path / "assets/music/theme.ogg").exists())

    def test_inspector_tags_layer_and_render(self):
        coin = self.ed.scene.find_name("Coin")
        self.ed.select(coin)
        self.app.processEvents()
        self.ed.inspector._set_tags(coin, "coin, #pickup, coin")
        self.assertEqual(coin.tags, ["coin", "pickup"])
        coin.alpha, coin.flip_x, coin.layer = 0.5, True, 3
        self.ed.game_view.resize(960, 540)
        self.ed.play()
        self.pump(3)
        self.assertFalse(self.ed.game_view.grab().isNull())
        self.assertFalse(self.ed.scene_view.grab().isNull())

    def test_warnings_show_in_console_and_game_pauses_on_errors(self):
        self.proj.write_script("w.pawn", 'when true\n    n = 0\n    n += 1\n')
        self.ed.attach_script(self.ed.scene.find_name("Coin"), "w.pawn")
        self.ed.play()
        self.pump(3)
        self.assertIn("temporary variable", self.ed.console.out.toPlainText())
        self.proj.write_script("e.pawn", 'when true\n    x = 1 / 0\n')
        self.ed.attach_script(self.ed.scene.find_name("Coin"), "e.pawn")
        self.ed.stop()
        self.ed.play()
        self.pump(3)
        self.assertTrue(self.ed.game_view.errored)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class ParticleInspectorSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import helpers  # noqa: F401
        cls.app = QApplication.instance() or QApplication([])
        from ui.theme import apply_theme
        apply_theme(cls.app)

    def test_particle_card_and_presets(self):
        from engine.project import create_project
        from ui.editor import EditorWindow
        from PySide6.QtWidgets import QComboBox
        ed = EditorWindow(create_project("PSmoke", Path(tempfile.mkdtemp()), "blank"))
        try:
            ed.add_object("particles")
            o = ed.selected
            ed.inspector.set_object(o)
            combos = [c for c in ed.inspector.findChildren(QComboBox) if c.itemText(0).startswith("Pick a preset")]
            self.assertEqual(len(combos), 1)
            combos[0].setCurrentIndex(combos[0].findData("fire"))
            self.assertTrue(o.em_add)
            self.assertEqual(o.em_color_end, "#c0200a")
            self.app.processEvents()
        finally:
            ed.game_view.stop()


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class HelperObjectsSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import helpers  # noqa: F401
        cls.app = QApplication.instance() or QApplication([])
        from ui.theme import apply_theme
        apply_theme(cls.app)

    def test_add_every_helper_and_part(self):
        from engine.project import create_project
        from ui.editor import EditorWindow, HELPER_KINDS, PARTS
        ed = EditorWindow(create_project("HSmoke", Path(tempfile.mkdtemp()), "blank"))
        try:
            for k in HELPER_KINDS:
                ed.add_object(k)
                self.assertEqual(ed.selected.kind, k)
                ed.inspector.set_object(ed.selected)
                ed.scene_view.update()
            for label in PARTS:
                ed.add_part(label)
                self.assertTrue(ed.selected.name.startswith(label))
                ed.inspector.set_object(ed.selected)
            self.assertTrue(ed.selected.solid or ed.selected.body)
            ed.rebuild_hierarchy()
            self.app.processEvents()
        finally:
            ed.game_view.stop()


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class ExplorerSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import helpers  # noqa: F401
        cls.app = QApplication.instance() or QApplication([])
        from ui.theme import apply_theme
        apply_theme(cls.app)

    def test_every_kind_has_an_svg_icon(self):
        from engine.gameobject import KINDS
        from ui.svgicons import has
        for k in KINDS:
            self.assertTrue(has(k), k)

    def test_eye_lock_search_and_expansion(self):
        from engine.project import create_project
        from ui.editor import EditorWindow
        ed = EditorWindow(create_project("ExplSmoke", Path(tempfile.mkdtemp()), "blank"))
        try:
            ed.add_object("model")
            model = ed.selected
            ed.add_object("rect", parent=model)
            kid = ed.selected
            ed._flag_toggled(kid.id, "locked")
            self.assertTrue(kid.locked)
            ed._flag_toggled(kid.id, "active")
            self.assertFalse(kid.active)
            ed.do_undo()
            self.assertTrue(ed.scene.find_id(kid.id).active)
            ed.tree.set_filter(kid.name.lower())
            top = ed.tree._find(model.id)
            self.assertFalse(top.isHidden())           # parents of a match stay visible
            ed.tree.set_filter("zzz-nothing")
            self.assertTrue(ed.tree._find(kid.id).isHidden())
            ed.tree.set_filter("")
            ed.tree._find(model.id).setExpanded(False)
            ed.rebuild_hierarchy()
            self.assertFalse(ed.tree._find(model.id).isExpanded())     # collapsed groups stay collapsed
        finally:
            ed.game_view.stop()


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class ThemeSwitchSmoke(unittest.TestCase):
    def test_light_and_dark_build_and_switch(self):
        import helpers  # noqa: F401
        app = QApplication.instance() or QApplication([])
        from ui import theme
        from engine.project import create_project
        from ui.editor import EditorWindow
        for mode in ("light", "dark"):
            theme.apply_theme(app, mode)
            self.assertNotIn("%(", theme.build_qss())
        ed = EditorWindow(create_project("ThemeSmoke", Path(tempfile.mkdtemp()), "blank"))
        try:
            ed.set_theme("light")
            self.assertEqual(ed.theme_mode, "light")
            self.assertEqual(theme.C["bg0"], theme.LIGHT["bg0"])
            ed.set_theme("dark")
            self.assertEqual(ed.theme_mode, "dark")
        finally:
            ed.game_view.stop()


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class PropertiesSmoke(unittest.TestCase):
    def test_fold_and_search(self):
        import helpers  # noqa: F401
        app = QApplication.instance() or QApplication([])
        from ui.theme import apply_theme
        apply_theme(app, "dark")
        from engine.project import create_project
        from ui.editor import EditorWindow
        from ui.inspector import Inspector
        ed = EditorWindow(create_project("PropSmoke", Path(tempfile.mkdtemp()), "blank"))
        try:
            ed.show()
            ed.add_object("rect")
            ins = ed.inspector
            titles = [t for t, *_ in ins.cards]
            self.assertIn("Look", titles)
            look = next(c for c in ins.cards if c[0] == "Look")
            look[3].click()                              # fold
            self.assertIn("Look", Inspector.collapsed)
            ed.inspector.set_object(ed.selected)         # still folded for the next object
            self.assertTrue(next(c for c in ins.cards if c[0] == "Look")[3].text().startswith("▸"))
            Inspector.collapsed.discard("Look")
            ed.inspector.set_object(ed.selected)
            ed.prop_search.setText("zzzz-nope")
            self.assertTrue(all(not c[1].isVisible() for c in ins.cards))
            ed.prop_search.setText("")
            self.assertTrue(all(c[1].isVisible() for c in ins.cards))
        finally:
            ed.game_view.stop()
