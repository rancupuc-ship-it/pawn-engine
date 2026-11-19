"""Main menu: create a project or open an old one."""
import time
from pathlib import Path

from PySide6.QtCore import Qt, QSize, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMenu, QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from engine.paths import resource
from engine.project import (TEMPLATES, VERSION, Project, create_project, default_projects_dir, load_recent,
                            remove_recent)
from .theme import C


def ago(ts):
    s = max(0, time.time() - ts)
    if s < 90:
        return "just now"
    if s < 3600:
        return f"{int(s // 60)} minutes ago"
    if s < 86400:
        h = int(s // 3600)
        return f"{h} hour{'s' if h != 1 else ''} ago"
    d = int(s // 86400)
    if d < 30:
        return f"{d} day{'s' if d != 1 else ''} ago"
    return time.strftime("%b %d, %Y", time.localtime(ts))


class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New project")
        self.setMinimumWidth(560)
        v = QVBoxLayout(self)
        v.setContentsMargins(26, 24, 26, 22)
        v.setSpacing(12)
        h = QLabel("Create a new project")
        h.setProperty("h1", True)
        h.setStyleSheet("font-size: 22px; font-weight: 700;")
        v.addWidget(h)

        v.addWidget(self._label("Name of your game"))
        self.name = QLineEdit("My Game")
        self.name.selectAll()
        v.addWidget(self.name)

        v.addWidget(self._label("Where to keep it"))
        row = QHBoxLayout()
        self.loc = QLineEdit(str(default_projects_dir()))
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        row.addWidget(self.loc, 1)
        row.addWidget(browse)
        v.addLayout(row)

        v.addWidget(self._label("Start from"))
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.templates = {}
        for i, (key, (title, desc)) in enumerate(TEMPLATES.items()):
            b = QPushButton()
            b.setCheckable(True)
            b.setMinimumHeight(104)
            bl = QVBoxLayout(b)
            bl.setContentsMargins(14, 12, 14, 12)
            t1 = QLabel(title)
            t1.setStyleSheet("font-size: 15px; font-weight: 700; background: transparent;")
            t2 = QLabel(desc)
            t2.setWordWrap(True)
            t2.setStyleSheet(f"color: {C['muted']}; background: transparent;")
            for lab in (t1, t2):
                lab.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            bl.addWidget(t1)
            bl.addWidget(t2)
            bl.addStretch(1)
            b.setStyleSheet(f"""QPushButton {{ text-align: left; padding: 14px; border-radius: 10px; background: {C['bg2']};
                                border: 2px solid {C['border']}; }}
                                QPushButton:hover {{ border-color: #4a5166; }}
                                QPushButton:checked {{ border-color: {C['gold']}; background: #2f2a1c; }}""")
            self.group.addButton(b, i)
            self.templates[i] = key
            cards.addWidget(b, 1)
            if i == 0:
                b.setChecked(True)
        v.addLayout(cards)

        self.error = QLabel()
        self.error.setStyleSheet(f"color: {C['red']};")
        self.error.setWordWrap(True)
        v.addWidget(self.error)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        self.create_btn = QPushButton("Create project")
        self.create_btn.setProperty("primary", True)
        self.create_btn.setDefault(True)
        self.create_btn.clicked.connect(self._create)
        row.addWidget(cancel)
        row.addWidget(self.create_btn)
        v.addLayout(row)
        self.project_path = None

    @staticmethod
    def _label(t):
        l = QLabel(t)
        l.setStyleSheet(f"color: {C['muted']}; font-weight: 600; margin-top: 4px;")
        return l

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Choose a folder", self.loc.text())
        if d:
            self.loc.setText(d)

    def _create(self):
        name = self.name.text().strip()
        if not name:
            self.error.setText("Give your game a name first.")
            return
        try:
            proj = create_project(name, Path(self.loc.text()), self.templates[self.group.checkedId()])
        except FileExistsError as e:
            self.error.setText(str(e) + " Pick another name or location.")
            return
        except OSError as e:
            self.error.setText(f"I couldn't create the project there: {e}")
            return
        self.project_path = proj.path
        self.accept()


class LauncherWindow(QWidget):
    open_project = Signal(object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pawn Engine")
        self.resize(980, 620)
        self.setMinimumSize(820, 520)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._left())
        root.addWidget(self._right(), 1)
        self.refresh()

    def _left(self):
        left = QFrame()
        left.setFixedWidth(340)
        left.setStyleSheet(f"QFrame {{ background: {C['bg0']}; }}")
        v = QVBoxLayout(left)
        v.setContentsMargins(36, 44, 36, 28)
        v.setSpacing(10)
        logo = QLabel()
        pm = QPixmap(str(resource("assets/icon.png")))
        logo.setPixmap(pm.scaled(116, 116, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        v.addWidget(logo)
        v.addSpacing(8)
        t = QLabel("Pawn Engine")
        t.setStyleSheet("font-size: 30px; font-weight: 800;")
        v.addWidget(t)
        s = QLabel("Make 2D games with a tiny,\nfriendly language.")
        s.setStyleSheet(f"color: {C['muted']}; font-size: 14px;")
        v.addWidget(s)
        v.addSpacing(26)
        new = QPushButton("＋   New project")
        new.setProperty("primary", True)
        new.setProperty("big", True)
        new.clicked.connect(self.new_project)
        opn = QPushButton("Open project…")
        opn.setProperty("big", True)
        opn.clicked.connect(self.open_dialog)
        v.addWidget(new)
        v.addWidget(opn)
        v.addStretch(1)
        tip = QLabel("Start small like a pawn,\npromote to a queen.")
        tip.setStyleSheet(f"color: {C['gold']}; font-style: italic;")
        v.addWidget(tip)
        ver = QLabel(f"Version {VERSION}")
        ver.setStyleSheet(f"color: {C['muted']}; font-size: 11px;")
        v.addWidget(ver)
        return left

    def _right(self):
        right = QFrame()
        right.setStyleSheet(f"QFrame {{ background: {C['bg1']}; }}")
        v = QVBoxLayout(right)
        v.setContentsMargins(34, 36, 34, 28)
        v.setSpacing(12)
        h = QLabel("Your projects")
        h.setStyleSheet("font-size: 20px; font-weight: 700;")
        v.addWidget(h)
        self.stack = QStackedWidget()
        self.list = QListWidget()
        self.list.setProperty("cards", True)
        self.list.setSpacing(2)
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.itemActivated.connect(self._activate)
        self.list.itemDoubleClicked.connect(self._activate)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._ctx)
        empty = QWidget()
        ev = QVBoxLayout(empty)
        ev.addStretch(1)
        e1 = QLabel("No projects yet")
        e1.setAlignment(Qt.AlignCenter)
        e1.setStyleSheet("font-size: 18px; font-weight: 700;")
        e2 = QLabel("Create your first game. It only takes a minute —\nthe Coin collector starter is already playable.")
        e2.setAlignment(Qt.AlignCenter)
        e2.setStyleSheet(f"color: {C['muted']};")
        btn = QPushButton("＋  Create your first project")
        btn.setProperty("primary", True)
        btn.setProperty("big", True)
        btn.clicked.connect(self.new_project)
        ev.addWidget(e1)
        ev.addWidget(e2)
        ev.addSpacing(10)
        ev.addWidget(btn, alignment=Qt.AlignHCenter)
        ev.addStretch(1)
        self.stack.addWidget(self.list)
        self.stack.addWidget(empty)
        v.addWidget(self.stack, 1)
        hint = QLabel("Double-click a project to open it. Right-click for more options.")
        hint.setStyleSheet(f"color: {C['muted']};")
        v.addWidget(hint)
        return right

    def refresh(self):
        self.list.clear()
        items = load_recent()
        for it in items:
            li = QListWidgetItem()
            li.setData(Qt.UserRole, it["path"])
            li.setSizeHint(QSize(100, 78))
            self.list.addItem(li)
            self.list.setItemWidget(li, self._card(it))
        self.stack.setCurrentIndex(0 if items else 1)

    def _card(self, it):
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        w.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        h = QHBoxLayout(w)
        h.setContentsMargins(14, 8, 16, 8)
        h.setSpacing(14)
        badge = QLabel(it["name"][:1].upper() or "P")
        badge.setFixedSize(46, 46)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(f"background: {C['gold']}; color: #1a1406; border-radius: 12px; font-size: 21px; font-weight: 800;")
        col = QVBoxLayout()
        col.setSpacing(2)
        n = QLabel(it["name"])
        n.setStyleSheet("font-size: 15px; font-weight: 700; background: transparent;")
        p = QLabel(it["path"])
        p.setStyleSheet(f"color: {C['muted']}; font-size: 11px; background: transparent;")
        col.addStretch(1)
        col.addWidget(n)
        col.addWidget(p)
        col.addStretch(1)
        when = QLabel("Opened " + ago(it.get("opened", 0)))
        when.setStyleSheet(f"color: {C['muted']}; font-size: 12px; background: transparent;")
        h.addWidget(badge)
        h.addLayout(col, 1)
        h.addWidget(when)
        return w

    # ---- actions ------------------------------------------------------------------
    def new_project(self):
        d = NewProjectDialog(self)
        if d.exec() == QDialog.Accepted and d.project_path:
            self.open_project.emit(d.project_path)

    def open_dialog(self):
        d = QFileDialog.getExistingDirectory(self, "Open a Pawn project folder", str(default_projects_dir()
                                             if default_projects_dir().exists() else Path.home()))
        if not d:
            return
        if not (Path(d) / "project.pawnproj").exists():
            QMessageBox.information(self, "Not a Pawn project",
                                    "That folder doesn't contain a Pawn project.\n"
                                    "Pick the folder that has a file called project.pawnproj inside it.")
            return
        self.open_project.emit(Path(d))

    def _activate(self, item):
        self.open_project.emit(Path(item.data(Qt.UserRole)))

    def _ctx(self, pos):
        it = self.list.itemAt(pos)
        if not it:
            return
        path = it.data(Qt.UserRole)
        m = QMenu(self)
        m.addAction("Open", lambda: self.open_project.emit(Path(path)))
        m.addAction("Show in folder", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(path)))
        m.addSeparator()
        m.addAction("Remove from list", lambda: (remove_recent(path), self.refresh()))
        m.exec(self.list.viewport().mapToGlobal(pos))
