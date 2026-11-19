"""Standalone player window used by exported games."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow, QMessageBox

from engine.paths import resource
from engine.project import Project
from engine.render import Assets
from pawnlang import PawnError
from .gameview import GameView


def _themed(assets, project):
    assets.theme = project.theme
    return assets


class PlayerWindow(QMainWindow):
    def __init__(self, project_dir):
        super().__init__()
        self.project = Project(project_dir)
        opts = self.project.window
        self.setWindowTitle(opts["title"])
        own_icon = self.project.assets_dir / "icon.png"
        self.setWindowIcon(QIcon(str(own_icon if own_icon.is_file() else resource("assets/icon.png"))))
        self.resize(opts["width"], opts["height"])
        self.setMinimumSize(min(opts["min_width"], opts["width"]), min(opts["min_height"], opts["height"]))
        if not opts["resizable"]:
            self.setFixedSize(opts["width"], opts["height"])
        self._start_full = opts["fullscreen"]
        self.view = GameView(self.project, _themed(Assets(self.project.path), self.project), self._log, fullscreen_mode=True)
        self.setCentralWidget(self.view)
        self.view.error_raised.connect(self._error)
        QShortcut(QKeySequence("F11"), self, activated=self._toggle_fullscreen)
        QShortcut(QKeySequence("Escape"), self, activated=self._escape)
        self._start()

    def showEvent(self, e):
        super().showEvent(e)
        if self._start_full:
            self._start_full = False
            self.showFullScreen()

    def _start(self):
        try:
            self.view.start(self.project.load_scene(), self.project.start_scene)
        except PawnError as e:
            QMessageBox.critical(self, "This game can't start", e.pretty())
            self.close()

    def _log(self, msg, level="print"):
        print(msg)

    def _error(self, e):
        self.view.stop()
        QMessageBox.critical(self, "Something went wrong in the game", e.pretty())
        self.close()

    def _toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def _escape(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.close()
