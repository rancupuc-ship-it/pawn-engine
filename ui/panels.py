"""Side panels: Hierarchy tree, Project files, Console."""
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QListWidget, QListWidgetItem, QMenu,
                               QPlainTextEdit, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from .theme import C, icon, tile_icon

KIND_COLOR = {"rect": C["teal"], "circle": C["gold"], "sprite": C["blue"], "text": C["text"],
              "camera": C["gold2"], "empty": C["muted"], "button": C["purple"], "bar": C["purple"],
              "slider": C["purple"], "checkbox": C["purple"], "input": C["purple"], "polygon": C["teal"],
              "tilemap": C["blue"], "particles": C["gold"], "light": C["gold2"],
              "model": C["blue"], "folder": C["gold"], "zone": C["teal"], "spawn": C["green"], "beam": C["red"], "prompt": C["blue"]}


class HierarchyTree(QTreeWidget):
    """Explorer-style tree: an icon per object type, an eye (active) and a lock (can't pick) on every row,
    a search filter, and it remembers which groups you opened."""
    about_to_reorder = Signal()
    reordered = Signal()
    picked = Signal(object)      # object id or None
    renamed = Signal(str, str)   # id, new name
    menu_requested = Signal(object, object)  # id or None, global pos
    flag_toggled = Signal(str, str)          # id, "active" or "locked"

    def __init__(self):
        super().__init__()
        self.setColumnCount(3)
        self.setHeaderHidden(True)
        self.header().setStretchLastSection(False)
        self.header().setSectionResizeMode(0, QHeaderView.Stretch)
        for c in (1, 2):
            self.header().setSectionResizeMode(c, QHeaderView.Fixed)
            self.setColumnWidth(c, 26)
        self.setIndentation(16)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditKeyPressed | QAbstractItemView.SelectedClicked)
        self.setIconSize(QSize(16, 16))
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx)
        self.itemSelectionChanged.connect(self._sel)
        self.itemChanged.connect(self._changed)
        self.itemExpanded.connect(lambda it: self._remember(it, True))
        self.itemCollapsed.connect(lambda it: self._remember(it, False))
        self._building = False
        self._closed = set()      # ids of groups the user collapsed
        self._filter = ""

    def _remember(self, it, opened):
        if self._building:
            return
        oid = it.data(0, Qt.UserRole)
        (self._closed.discard if opened else self._closed.add)(oid)

    def _ctx(self, pos):
        it = self.itemAt(pos)
        self.menu_requested.emit(it.data(0, Qt.UserRole) if it else None, self.viewport().mapToGlobal(pos))

    def _sel(self):
        if self._building:
            return
        its = self.selectedItems()
        self.picked.emit(its[0].data(0, Qt.UserRole) if its else None)

    def _changed(self, item, col):
        if not self._building and col == 0:
            self.renamed.emit(item.data(0, Qt.UserRole), item.text(0))

    def dropEvent(self, e):
        self.about_to_reorder.emit()
        super().dropEvent(e)
        self.reordered.emit()

    def set_filter(self, text):
        self._filter = text.strip().lower()
        self._apply_filter()

    def _apply_filter(self):
        def visit(it):
            hit = not self._filter or self._filter in it.text(0).lower()
            kid = False
            for i in range(it.childCount()):
                kid = visit(it.child(i)) or kid
            it.setHidden(not (hit or kid))
            if self._filter and kid:
                it.setExpanded(True)
            return hit or kid
        for i in range(self.topLevelItemCount()):
            visit(self.topLevelItem(i))

    def _flag_icons(self, it, o):
        it.setIcon(1, icon("eye" if o.active else "eye_off", C["muted"] if o.active else C["red"], 14))
        it.setIcon(2, icon("lock" if o.locked else "unlock", C["gold"] if o.locked else C["faint"], 14))
        it.setToolTip(1, "Visible and running (click to hide)" if o.active else "Hidden (click to show)")
        it.setToolTip(2, "Locked: can't be picked in the scene (click to unlock)" if o.locked else "Click to lock")

    def rebuild(self, scene, selected_id=None):
        self._building = True
        self.clear()

        def add(o, parent_item):
            it = QTreeWidgetItem(parent_item if parent_item is not None else self)
            it.setText(0, o.name)
            it.setData(0, Qt.UserRole, o.id)
            it.setIcon(0, icon(o.kind, KIND_COLOR.get(o.kind, C["text"]), 16))
            it.setFlags(it.flags() | Qt.ItemIsEditable | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled)
            it.setToolTip(0, f"{o.name}  ·  {KIND_LABEL_TIP.get(o.kind, o.kind)}")
            self._flag_icons(it, o)
            if not o.active:
                it.setForeground(0, QColor(C["muted"]))
                f = it.font(0)
                f.setItalic(True)
                it.setFont(0, f)
            for c in o.children:
                add(c, it)
            it.setExpanded(o.id not in self._closed)
            if o.id == selected_id:
                self.setCurrentItem(it)

        for r in scene.roots:
            add(r, None)
        self._building = False
        if self._filter:
            self._apply_filter()

    def select_id(self, oid):
        self._building = True
        self.clearSelection()
        if oid:
            it = self._find(oid)
            if it:
                self.setCurrentItem(it)
        self._building = False

    def _find(self, oid):
        stack = [self.topLevelItem(i) for i in range(self.topLevelItemCount())]
        while stack:
            it = stack.pop()
            if it.data(0, Qt.UserRole) == oid:
                return it
            stack.extend(it.child(i) for i in range(it.childCount()))
        return None

    def mousePressEvent(self, e):
        pos = e.position().toPoint()
        it = self.itemAt(pos)
        if not it:
            self.clearSelection()
        elif e.button() == Qt.LeftButton and self.columnAt(pos.x()) in (1, 2):
            self.flag_toggled.emit(it.data(0, Qt.UserRole), "active" if self.columnAt(pos.x()) == 1 else "locked")
            return
        super().mousePressEvent(e)


KIND_LABEL_TIP = {"rect": "Rectangle", "circle": "Circle", "sprite": "Picture", "text": "Text", "empty": "Empty object",
                  "camera": "Camera", "button": "Button", "bar": "Progress bar", "slider": "Slider", "checkbox": "Checkbox",
                  "input": "Text box", "polygon": "Polygon", "tilemap": "Tile map", "particles": "Particles", "light": "Light",
                  "model": "Model", "folder": "Folder", "zone": "Zone", "spawn": "Spawn point", "beam": "Beam", "prompt": "Prompt"}


class ProjectPanel(QWidget):
    open_script = Signal(str)
    attach_script = Signal(str)
    use_sprite = Signal(str)
    add_prefab = Signal(str)
    new_script = Signal()
    new_module = Signal()
    import_asset = Signal()
    delete_file = Signal(str)
    files_dropped = Signal(list)

    def __init__(self):
        super().__init__()
        self.project = None
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setIconSize(QSize(56, 56))
        self.list.setGridSize(QSize(112, 98))
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        self.list.setWordWrap(True)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._ctx)
        self.list.itemDoubleClicked.connect(self._dbl)
        top = QHBoxLayout()
        top.setContentsMargins(10, 6, 10, 0)
        hint = QLabel("Your scripts, pictures and sounds. Double-click a script to edit it. "
                      "Drag pictures and sounds in here to import them.")
        hint.setProperty("muted", True)
        b1 = QPushButton("＋ New script")
        b1m = QPushButton("＋ New module")
        b1m.setToolTip("A module script holds shared code. Other scripts load it with require(\"name\")")
        b2 = QPushButton("Import picture, sound or font…")
        for b in (b1, b1m, b2):
            b.setProperty("flat", True)
        b1.clicked.connect(self.new_script)
        b1m.clicked.connect(self.new_module)
        b2.clicked.connect(self.import_asset)
        top.addWidget(hint)
        top.addStretch(1)
        top.addWidget(b1)
        top.addWidget(b1m)
        top.addWidget(b2)
        self.setAcceptDrops(True)
        self.list.setAcceptDrops(False)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(top)
        lay.addWidget(self.list, 1)

    def refresh(self, project):
        self.project = project
        self.list.clear()
        for s in project.list_scripts():
            it = QListWidgetItem(tile_icon("script", C["purple"]), s[:-5] if s.endswith(".pawn") else s)
            it.setData(Qt.UserRole, ("script", s))
            it.setToolTip(s + "  •  double-click to edit")
            self.list.addItem(it)
        for m in project.list_modules():
            it = QListWidgetItem(tile_icon("script", C["gold2"]), (m[:-8] if m.endswith(".pawnmod") else m) + " (module)")
            it.setData(Qt.UserRole, ("module", m))
            it.setToolTip(m + "  •  module script  •  double-click to edit  •  use it with require(\"" + m[:-8] + "\")")
            self.list.addItem(it)
        for pf in project.list_prefabs():
            it = QListWidgetItem(tile_icon("empty", C["teal"]), pf + " (prefab)")
            it.setData(Qt.UserRole, ("prefab", pf))
            it.setToolTip("prefab  •  double-click to add to the scene  •  in a script:  spawn(\"" + pf + "\")")
            self.list.addItem(it)
        for rel, kind in project.list_assets():
            name = rel.split("/")[-1]
            if kind == "image":
                pm = QPixmap(str(project.path / rel))
                ic = QIcon(pm.scaled(112, 112, Qt.KeepAspectRatio, Qt.SmoothTransformation)) if not pm.isNull() \
                    else tile_icon("sprite", C["blue"])
            elif kind == "font":
                ic = tile_icon("text", C["purple"])
            else:
                ic = tile_icon("sound", C["green"])
            it = QListWidgetItem(ic, name)
            it.setData(Qt.UserRole, (kind, rel))
            self.list.addItem(it)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.files_dropped.emit(paths)
            e.acceptProposedAction()

    def _dbl(self, it):
        kind, val = it.data(Qt.UserRole)
        if kind in ("script", "module"):
            self.open_script.emit(val)
        elif kind == "image":
            self.use_sprite.emit(val)
        elif kind == "prefab":
            self.add_prefab.emit(val)

    def _ctx(self, pos):
        it = self.list.itemAt(pos)
        if not it:
            return
        kind, val = it.data(Qt.UserRole)
        m = QMenu(self)
        if kind == "script":
            m.addAction("Edit script", lambda: self.open_script.emit(val))
            m.addAction("Attach to selected object", lambda: self.attach_script.emit(val))
        elif kind == "module":
            m.addAction("Edit module", lambda: self.open_script.emit(val))
        elif kind == "image":
            m.addAction("Use as picture on selected object", lambda: self.use_sprite.emit(val))
        elif kind == "prefab":
            m.addAction("Add to the scene", lambda: self.add_prefab.emit(val))
        m.addSeparator()
        if kind == "prefab":
            val = val + ".prefab.json"
        prefix = {"script": "scripts/", "module": "modules/", "prefab": "prefabs/"}.get(kind, "")
        m.addAction("Delete file…", lambda: self.delete_file.emit(prefix + val))
        m.exec(self.list.viewport().mapToGlobal(pos))


class ConsolePanel(QWidget):
    def __init__(self):
        super().__init__()
        self.out = QPlainTextEdit()
        self.out.setReadOnly(True)
        self.out.setMaximumBlockCount(2000)
        self.out.setStyleSheet(f"QPlainTextEdit {{ background: {C['bg0']}; border: none; border-radius: 0; padding: 6px 10px; }}")
        from .theme import mono_font
        self.out.setFont(mono_font(10))
        clear = QPushButton("Clear")
        clear.setProperty("flat", True)
        clear.clicked.connect(self.out.clear)
        top = QHBoxLayout()
        top.setContentsMargins(10, 4, 10, 0)
        hint = QLabel("Messages from your game appear here. Use print(...) in a script.")
        hint.setProperty("muted", True)
        top.addWidget(hint)
        top.addStretch(1)
        top.addWidget(clear)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(top)
        lay.addWidget(self.out, 1)

    def log(self, msg, level="print"):
        colors = {"print": C["text"], "info": C["muted"], "error": C["red"], "ok": C["green"], "warn": C["gold2"]}
        import html
        self.out.appendHtml(f'<span style="color:{colors.get(level, C["text"])}">{html.escape(str(msg))}</span>')
        sb = self.out.verticalScrollBar()
        sb.setValue(sb.maximum())
