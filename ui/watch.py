"""Watch panel: look at (and change) the running game's data while it plays or is paused."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from pawnlang import fmt
from engine.proxies import ObjProxy
from .theme import C

OBJECT_FIELDS = ("x", "y", "vx", "vy", "on_ground", "angle", "alpha", "layer", "visible")


def parse_value(text):
    """What you typed -> a Pawn value: 12, 3.5, true, false, none, or text (quotes are optional)."""
    t = text.strip()
    if t.lower() == "true":
        return True
    if t.lower() == "false":
        return False
    if t.lower() in ("none", "null"):
        return None
    try:
        return int(t)
    except ValueError:
        pass
    try:
        return float(t)
    except ValueError:
        pass
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'":
        return t[1:-1]
    return t


def editable(v):
    return v is None or isinstance(v, (bool, int, float, str))


class WatchPanel(QWidget):
    def __init__(self, ed):
        super().__init__()
        self.ed = ed
        self.rt = None
        self._busy = False
        self._open = {"game": True, "obj": True}
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.note = QLabel("Press ▶ Play to watch your game's data. Double-click a value to change it while the game runs.")
        self.note.setProperty("muted", True)
        self.note.setContentsMargins(12, 6, 12, 6)
        self.note.setWordWrap(True)
        v.addWidget(self.note)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Name", "Value"])
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(False)
        self.tree.setColumnWidth(0, 240)
        self.tree.itemChanged.connect(self._edited)
        self.tree.itemExpanded.connect(lambda it: self._remember(it, True))
        self.tree.itemCollapsed.connect(lambda it: self._remember(it, False))
        v.addWidget(self.tree, 1)

    def _remember(self, it, on):
        key = it.data(0, Qt.UserRole)
        if isinstance(key, tuple) and key[0] == "group":
            self._open[key[1]] = on

    # ---- showing -----------------------------------------------------------------
    def clear(self):
        self.rt = None
        self._busy = True
        self.tree.clear()
        self._busy = False
        self.note.show()

    def _row(self, parent, name, value, target):
        it = QTreeWidgetItem(parent, [name, fmt(value) if not isinstance(value, str) else value])
        it.setData(0, Qt.UserRole, ("var", target))
        if editable(value):
            it.setFlags(it.flags() | Qt.ItemIsEditable)
            if isinstance(value, str):
                it.setText(1, value)
        else:
            it.setForeground(1, self.palette().mid())
        return it

    def refresh(self, rt, selected):
        """Rebuild the rows (cheap: a few dozen). Skipped while a value is being typed."""
        if self.tree.state() == QTreeWidget.EditingState:
            return
        self.rt = rt
        self.note.hide()
        self._busy = True
        scroll = self.tree.verticalScrollBar().value()
        self.tree.clear()
        g = QTreeWidgetItem(self.tree, [f"game   ({len(rt.game.d)})", ""])
        g.setData(0, Qt.UserRole, ("group", "game"))
        for k in sorted(rt.game.d, key=str):
            self._row(g, f"game.{k}", rt.game.d[k], ("game", k))
        g.setExpanded(self._open["game"])
        obj = rt.scene.find_id(selected.id) if selected is not None else None
        if obj is not None and not obj.dead:
            o = QTreeWidgetItem(self.tree, [f"{obj.name}   (selected)", ""])
            o.setData(0, Qt.UserRole, ("group", "obj"))
            px = ObjProxy(obj, rt)
            for f in OBJECT_FIELDS:
                try:
                    self._row(o, f, px.pawn_get(f), ("field", obj, f))
                except Exception:
                    pass
            for inst in rt.instances:
                if inst.obj is obj:
                    for k in sorted(inst.fields):
                        if not k.startswith("__"):
                            self._row(o, f"{inst.file}: {k}", inst.fields[k], ("script", inst, k))
                    if inst.state:
                        self._row(o, f"{inst.file}: state", inst.state, ("readonly",)).setFlags(Qt.ItemIsEnabled)
            o.setExpanded(self._open["obj"])
        self.tree.verticalScrollBar().setValue(scroll)
        self._busy = False

    # ---- editing -------------------------------------------------------------------
    def _edited(self, it, col):
        if self._busy or col != 1 or self.rt is None:
            return
        key = it.data(0, Qt.UserRole)
        if not isinstance(key, tuple) or key[0] != "var":
            return
        target, val = key[1], parse_value(it.text(1))
        try:
            if target[0] == "game":
                self.rt.game.d[target[1]] = val
            elif target[0] == "script":
                target[1].fields[target[2]] = val
            elif target[0] == "field":
                ObjProxy(target[1], self.rt).pawn_set(target[2], val)
            self.ed.statusBar().showMessage("Changed while playing (the script file is not changed)", 3000)
        except Exception as e:      # PawnError and friends: show it, don't crash
            self.ed.statusBar().showMessage(f"Can't set that: {e}", 5000)
