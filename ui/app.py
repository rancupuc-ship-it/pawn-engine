"""Ties the main menu and editor windows together."""
from PySide6.QtWidgets import QMessageBox

from engine.project import Project
from .editor import EditorWindow
from .launcher import LauncherWindow


class App:
    def __init__(self):
        self.launcher = None
        self.editor = None

    def show_launcher(self):
        self.launcher = LauncherWindow()
        self.launcher.open_project.connect(self.open_project)
        self.launcher.show()
        self._daily_update_check()

    def _daily_update_check(self):
        """Once a day, quietly look for a new version. Only speaks up when there is one."""
        import time
        from PySide6.QtCore import QSettings, QTimer
        st = QSettings("PawnEngine", "PawnEngine")
        last = float(st.value("update_checked", 0) or 0)
        if time.time() - last < 86400:
            return
        st.setValue("update_checked", time.time())
        import threading
        from engine import updates
        box = {}
        t = threading.Thread(target=lambda: box.update(r=updates.check()), daemon=True)
        t.start()

        def done():
            if t.is_alive():
                QTimer.singleShot(300, done)
            elif box.get("r", {}).get("status") == "newer" and self.launcher is not None:
                from PySide6.QtWidgets import QMessageBox
                from PySide6.QtCore import QUrl
                from PySide6.QtGui import QDesktopServices
                r = box["r"]
                if QMessageBox.question(self.launcher, "Update available", f"Pawn Engine {r['latest']} is out. Download it now?") == QMessageBox.Yes:
                    QDesktopServices.openUrl(QUrl(r["url"]))
        QTimer.singleShot(1500, done)

    def open_project(self, path):
        try:
            proj = Project(path)
            editor = EditorWindow(proj)
        except Exception as e:
            QMessageBox.critical(self.launcher, "Couldn't open that project", f"Something is wrong with the project:\n{e}")
            return
        self.editor = editor
        editor.back_to_menu.connect(self._back)
        editor.show()
        if self.launcher is not None:
            self.launcher.close()
            self.launcher = None

    def _back(self):
        self.show_launcher()
