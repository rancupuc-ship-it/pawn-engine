import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.helpers import new_project

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PAWN_NO_SOUND", "1")


class WindowOptions(unittest.TestCase):
    def test_defaults_use_project_name(self):
        p = new_project()
        w = p.window
        self.assertEqual((w["width"], w["height"]), (1152, 648))
        self.assertEqual(w["title"], p.name)
        self.assertTrue(w["resizable"])
        self.assertFalse(w["fullscreen"])

    def test_save_and_reload(self):
        from engine.project import Project
        p = new_project()
        p.set_window({"title": "Cool", "width": 800, "height": 600, "resizable": False, "fullscreen": True})
        q = Project(p.path)
        self.assertEqual(q.window["title"], "Cool")
        self.assertEqual((q.window["width"], q.window["height"]), (800, 600))
        self.assertFalse(q.window["resizable"])
        self.assertTrue(q.window["fullscreen"])

    def test_junk_is_cleaned(self):
        p = new_project()
        p.meta["window"] = {"title": 5, "width": "abc", "height": 10 ** 9, "resizable": "no", "fullscreen": "yes"}
        w = p.window
        self.assertEqual(w["title"], p.name)
        self.assertEqual(w["width"], 1152)
        self.assertEqual(w["height"], 4320)
        self.assertTrue(w["resizable"])
        self.assertFalse(w["fullscreen"])
        p.meta["window"] = "junk"
        self.assertEqual(p.window["width"], 1152)

    def test_version(self):
        from engine.project import VERSION
        self.assertEqual(VERSION, "1.2")

    def test_build_script_excludes(self):
        bat = (Path(__file__).resolve().parent.parent / "tools" / "build_app.py").read_text()
        for m in ("QtWebEngineCore", "QtQml", "QtCharts", "PIL"):
            self.assertIn(m, bat)
        self.assertNotIn("PySide6.QtNetwork", bat)  # QtMultimedia needs it


class WindowUI(unittest.TestCase):
    def test_player_applies_options(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from ui.player import PlayerWindow
        p = new_project("coin")
        p.set_window({"title": "Hi", "width": 700, "height": 500, "resizable": False, "fullscreen": False})
        w = PlayerWindow(str(p.path))
        self.assertEqual(w.windowTitle(), "Hi")
        self.assertEqual((w.width(), w.height()), (700, 500))
        self.assertEqual(w.minimumSize(), w.maximumSize())
        w.view.stop()
        w.close()

    def test_dialog_roundtrip(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from ui.dialogs import WindowDialog
        p = new_project()
        d = WindowDialog(p)
        d.title.setText("X")
        d.w.setValue(900)
        d.resizable.setChecked(False)
        o = d.options()
        self.assertEqual((o["title"], o["width"], o["resizable"]), ("X", 900, False))


if __name__ == "__main__":
    unittest.main()
