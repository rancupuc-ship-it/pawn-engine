"""Inspector: edit the selected object's settings and its scripts."""
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QPlainTextEdit, QSizePolicy, QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFormLayout, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QScrollArea, QSlider, QVBoxLayout, QWidget)

from engine.gameobject import ANCHORS
from .theme import C, icon

ANCHOR_NAMES = [k for k in ANCHORS if k != "none"]

KIND_NAMES = {"rect": "Rectangle", "circle": "Circle", "sprite": "Picture", "text": "Text",
              "camera": "Camera", "empty": "Empty object", "button": "Button", "bar": "Progress bar",
              "slider": "Slider", "checkbox": "Checkbox", "input": "Text box", "polygon": "Polygon", "tilemap": "Tile map",
              "particles": "Particles", "light": "Light",
              "model": "Model", "folder": "Folder", "zone": "Zone", "spawn": "Spawn point", "beam": "Beam", "prompt": "Prompt"}
UI_KINDS = ("button", "bar", "slider", "checkbox", "input")
SWATCHES = ["#f2b84b", "#4fd1b5", "#6aa7ff", "#ef6b6b", "#6bd38a", "#c792ea", "#ffffff", "#3a4256"]


def _spin(value, lo=-99999, hi=99999, step=1.0, dec=1, width=None):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(dec)
    s.setSingleStep(step)
    s.setKeyboardTracking(True)
    s.setValue(float(value))
    s.setMinimumWidth(44)
    s.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
    if width:
        s.setFixedWidth(width)
    return s


def wrap_label(text, width=290):
    """Muted word-wrapped label with a reliable height (Qt under-measures wrapped labels inside scroll areas)."""
    l = QLabel(text)
    l.setProperty("muted", True)
    l.setWordWrap(True)
    h = l.fontMetrics().boundingRect(0, 0, width, 2000, Qt.TextWordWrap, text).height()
    l.setMinimumHeight(h + 4)
    return l


class Inspector(QScrollArea):
    def __init__(self, ed):
        super().__init__()
        self.ed = ed
        self.obj = None
        self.setWidgetResizable(True)
        self.body = QWidget()
        self.lay = QVBoxLayout(self.body)
        self.lay.setContentsMargins(12, 12, 12, 16)
        self.lay.setSpacing(12)
        self.setWidget(self.body)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setMinimumWidth(340)
        self.spins = {}
        self.cards = []

    # ---- building ---------------------------------------------------------------
    def _clear(self):
        while self.lay.count():
            it = self.lay.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        self.spins = {}
        self.palette = None
        self.cards = []

    collapsed = set()      # titles of cards the user folded; shared by every object

    @staticmethod
    def _set_items_visible(layout, visible, skip=1):
        for i in range(skip, layout.count()):
            it = layout.itemAt(i)
            if it.widget():
                it.widget().setVisible(visible)
            elif it.layout():
                Inspector._set_items_visible(it.layout(), visible, 0)

    def _fold(self, f, v, h, title):
        closed = title not in self.collapsed
        (self.collapsed.add if closed else self.collapsed.discard)(title)
        h.setText(("▸  " if closed else "▾  ") + title)
        self._set_items_visible(v, not closed)
        if not closed:
            self._filter_cards()
        self._fit()

    def _fit(self):
        """Keep cards at their natural height and scroll, instead of squashing them when the panel is short."""
        self.body.setMinimumHeight(0)
        total, n = 0, 0
        for i in range(self.lay.count()):
            w = self.lay.itemAt(i).widget()
            if w is not None and not w.isHidden():
                total += w.sizeHint().height()
                n += 1
        m = self.lay.contentsMargins()
        self.body.setMinimumHeight(total + max(0, n - 1) * self.lay.spacing() + m.top() + m.bottom())

    def _apply_folds(self):
        for title, f, v, h in self.cards:
            if title in self.collapsed:
                self._set_items_visible(v, False)

    def set_search(self, text):
        self._query = text.strip().lower()
        self._filter_cards()
        self._fit()

    _query = ""

    def _filter_cards(self):
        """Property search: show only the rows (and cards) that match what was typed."""
        q = self._query
        for title, f, v, h in self.cards:
            forms = [v.itemAt(i).layout() for i in range(v.count()) if v.itemAt(i).layout() is not None]
            if not q:
                f.setVisible(True)
                for form in forms:
                    for r in range(form.rowCount()):
                        form.setRowVisible(r, True)
                if title in self.collapsed:
                    self._set_items_visible(v, False)
                continue
            card_hit = q in title.lower()
            any_row = False
            for form in forms:
                for r in range(form.rowCount()):
                    lab = form.itemAt(r, QFormLayout.LabelRole)
                    text = lab.widget().text().lower() if lab is not None and hasattr(lab.widget(), "text") else ""
                    show = card_hit or q in text
                    form.setRowVisible(r, show)
                    any_row = any_row or show
            loose = any(q in w.text().lower() for w in f.findChildren(QCheckBox) + f.findChildren(QPushButton) if w is not h)
            f.setVisible(card_hit or any_row or loose)
            if f.isVisible():
                self._set_items_visible(v, True)

    def _card(self, title, hint=None):
        f = QFrame()
        f.setProperty("card", True)
        f.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)     # never squash a card: the panel scrolls instead
        v = QVBoxLayout(f)
        v.setContentsMargins(12, 10, 12, 12)
        v.setSpacing(8)
        h = QPushButton(("▾  " if title not in self.collapsed else "▸  ") + title)
        h.setProperty("flat", True)
        h.setProperty("cardhead", True)
        h.setCursor(Qt.PointingHandCursor)
        h.setToolTip("Click to fold or unfold")
        h.setStyleSheet("QPushButton { text-align: left; font-size: 14px; font-weight: 700; padding: 2px 0; color: %s; }"
                        "QPushButton:hover { background: transparent; color: %s; }" % (C["text"], C["gold2"]))
        h.clicked.connect(lambda _=False, f=f, v=v, h=h, t=title: self._fold(f, v, h, t))
        v.addWidget(h)
        self.cards.append((title, f, v, h))
        if hint:
            v.addWidget(wrap_label(hint))
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignLeft)
        v.addLayout(form)
        self.lay.addWidget(f)
        return f, form, v

    def set_object(self, obj):
        self.obj = obj
        self._clear()
        if obj is None:
            f = wrap_label("Nothing selected. Click an object in the Scene or in the Hierarchy to edit it here.")
            f.setAlignment(Qt.AlignCenter)
            f.setMinimumHeight(120)
            self.lay.addWidget(f)
            self.lay.addStretch(1)
            return
        self._build_header(obj)
        self._build_transform(obj)
        self._build_scripts(obj)
        self._build_look(obj)
        if obj.kind == "sprite":
            self._build_animation(obj)
        if obj.kind in UI_KINDS:
            self._build_ui(obj)
        if obj.kind == "polygon":
            self._build_polygon(obj)
        if obj.kind == "tilemap":
            self._build_tilemap(obj)
        if obj.kind == "particles":
            self._build_particles(obj)
        if obj.kind == "light":
            self._build_light(obj)
        if obj.kind == "beam":
            self._build_beam(obj)
        if obj.kind == "prompt":
            self._build_prompt(obj)
        if obj.kind == "zone":
            self._build_zone(obj)
        if obj.kind == "spawn":
            self._build_info(obj, "Spawn point", "Where things appear. In code:  respawn(self)  puts an object here; spawn_point() gives this object.")
        if obj.kind in ("model", "folder"):
            self._build_info(obj, "Group", "Put other objects inside by dragging them onto this one in the Hierarchy. Moving it moves them all.")
        if obj.kind in ("rect", "circle", "sprite", "polygon", "tilemap"):
            self._build_physics(obj)
        self.lay.addStretch(1)
        self._apply_folds()
        if self._query:
            self._filter_cards()
        self._fit()

    def _build_header(self, o):
        f, form, v = self._card(KIND_NAMES.get(o.kind, "Object"))
        name = QLineEdit(o.name)
        name.setPlaceholderText("Name")
        name.editingFinished.connect(lambda: self._rename(name))
        v.insertWidget(1, name)
        act = QCheckBox("Active")
        act.setToolTip("Untick to hide this object and pause its scripts")
        act.setChecked(o.active)
        act.toggled.connect(lambda c: self._set(o, "active", c, structural=True))
        v.insertWidget(2, act)
        tags = QLineEdit(", ".join(o.tags))
        tags.setPlaceholderText("Tags, like: enemy, coin")
        tags.setToolTip("Labels for finding objects in scripts: all(\"#enemy\"), tagged(\"enemy\"), touching(\"#enemy\")")
        tags.editingFinished.connect(lambda: self._set_tags(o, tags.text()))
        v.insertWidget(3, tags)

    def _set_tags(self, o, text):
        new = []
        for t in text.replace(";", ",").split(","):
            t = t.strip().lstrip("#")
            if t and t not in new:
                new.append(t)
        if new != o.tags:
            self._set(o, "tags", new)

    def _rename(self, edit):
        o = self.obj
        t = edit.text().strip()
        if o and t and t != o.name:
            self.ed.checkpoint(f"{o.id}:name")
            o.name = t
            self.ed.touch(o, structural=True)

    def _set(self, o, field, value, structural=False):
        self.ed.checkpoint(f"{o.id}:{field}")
        setattr(o, field, value)
        self.ed.touch(o, structural=structural)

    def _num_field(self, o, field, spin):
        def cb(v):
            self.ed.checkpoint(f"{o.id}:{field}")
            setattr(o, field, v)
            self.ed.touch(o)
        spin.valueChanged.connect(cb)
        self.spins[field] = spin

    def _build_transform(self, o):
        hint = "Measured from the camera's center, so it stays on screen." if (o.hud and o.parent is None) else None
        f, form, v = self._card("Position and size", hint)
        row = QHBoxLayout()
        row.setSpacing(6)
        for field, lab in (("x", "X"), ("y", "Y")):
            s = _spin(getattr(o, field))
            self._num_field(o, field, s)
            row.addWidget(QLabel(lab))
            row.addWidget(s, 1)
        form.addRow("Position", row)
        if o.kind not in ("camera", "empty", "tilemap", "particles", "light"):
            row = QHBoxLayout()
            row.setSpacing(6)
            for field, lab in (("w", "W"), ("h", "H")):
                s = _spin(getattr(o, field), 1, 99999)
                self._num_field(o, field, s)
                row.addWidget(QLabel(lab))
                row.addWidget(s, 1)
            form.addRow("Size", row)
            s = _spin(o.angle, -360, 360, 5, 1)
            self._num_field(o, "angle", s)
            form.addRow("Rotation", s)

    def sync_transform(self):
        o = self.obj
        if not o:
            return
        for field, s in self.spins.items():
            if abs(s.value() - getattr(o, field)) > 1e-6:
                s.blockSignals(True)
                s.setValue(float(getattr(o, field)))
                s.blockSignals(False)

    def _build_look(self, o):
        if o.kind in ("empty", "model", "folder", "spawn", "prompt"):
            return
        f, form, v = self._card("Look")
        o_ = o
        if o.kind in ("rect", "circle", "text", "polygon", "particles", "tilemap", "light", "zone", "beam") or o.kind in UI_KINDS:
            sw = QHBoxLayout()
            sw.setSpacing(5)
            for col in SWATCHES:
                b = QPushButton()
                b.setFixedSize(22, 22)
                b.setCursor(Qt.PointingHandCursor)
                b.setToolTip(col)
                b.setStyleSheet(f"QPushButton {{ background: {col}; border: 2px solid "
                                f"{C['gold'] if o.color.lower() == col else C['border']}; border-radius: 11px; padding: 0; }}")
                b.clicked.connect(lambda _=False, c=col: self._pick_color(o_, c))
                sw.addWidget(b)
            custom = QPushButton("…")
            custom.setFixedSize(26, 22)
            custom.setProperty("flat", True)
            custom.setToolTip("Pick any color")
            custom.clicked.connect(lambda: self._custom_color(o_))
            sw.addWidget(custom)
            sw.addStretch(1)
            form.addRow("Color", sw)
        if o.kind in ("rect", "circle", "sprite", "text", "polygon", "tilemap", "particles") or o.kind in UI_KINDS:
            layer = _spin(o.layer, -100, 100, 1, 0)
            layer.setToolTip("Higher layers are drawn on top of lower ones")
            layer.valueChanged.connect(lambda x: self._set(o_, "layer", int(x)))
            form.addRow("Layer", layer)
            alpha = _spin(o.alpha, 0, 1, 0.1, 2)
            alpha.setToolTip("1 is solid, 0 is invisible")
            alpha.valueChanged.connect(lambda x: self._set(o_, "alpha", float(x)))
            form.addRow("Opacity", alpha)
        if o.kind == "sprite":
            flip = QCheckBox("Flip left-right")
            flip.setChecked(o.flip_x)
            flip.toggled.connect(lambda c: self._set(o_, "flip_x", c))
            v.addWidget(flip)
            combo = QComboBox()
            combo.addItem("(none yet)", "")
            for rel, kind in self.ed.project.list_assets("image"):
                combo.addItem(rel.split("/")[-1], rel)
            idx = combo.findData(o.sprite)
            combo.setCurrentIndex(max(0, idx))
            combo.currentIndexChanged.connect(lambda i: self._set(o_, "sprite", combo.itemData(i)))
            form.addRow("Picture", combo)
            v.addWidget(wrap_label("Add pictures by dragging them into the Project panel, or use “Import picture or sound”."))
        if o.kind == "text":
            t = QLineEdit(o.text)
            t.textChanged.connect(lambda s: self._set(o_, "text", s))
            form.addRow("Text", t)
            s = _spin(o.text_size, 6, 400, 1, 0)
            self._num_field(o, "text_size", s)
            form.addRow("Text size", s)
            form.addRow("Font", self._font_combo(o_))
            al = QComboBox()
            al.addItem("Center", "center")
            al.addItem("Left", "left")
            al.setCurrentIndex(0 if o.align == "center" else 1)
            al.currentIndexChanged.connect(lambda i: self._set(o_, "align", al.itemData(i)))
            form.addRow("Align", al)
        if o.kind == "camera":
            combo = QComboBox()
            combo.addItem("(nothing)", "")
            for ob in self.ed.scene.all():
                if ob is not o and ob.kind != "camera":
                    combo.addItem(ob.name, ob.name)
            idx = combo.findData(o.follow)
            if idx < 0 and o.follow:
                combo.addItem(o.follow, o.follow)
                idx = combo.count() - 1
            combo.setCurrentIndex(max(0, idx))
            combo.currentIndexChanged.connect(lambda i: self._set(o_, "follow", combo.itemData(i)))
            form.addRow("Follow", combo)
            z = _spin(o.zoom, 0.1, 10, 0.1, 2)
            self._num_field(o, "zoom", z)
            form.addRow("Zoom", z)
        if o.kind in ("rect", "circle", "sprite", "polygon", "tilemap", "text") and o.parent is None and not o.hud:
            par = _spin(o.parallax, -2, 2, 0.1, 2)
            par.setToolTip("1 moves with the world, 0.5 moves half as fast (far away), 0 stays on the screen")
            par.valueChanged.connect(lambda x: self._set(o, "parallax", float(x)))
            form.addRow("Parallax", par)
        if (o.kind in ("rect", "circle", "sprite", "text") or o.kind in UI_KINDS) and o.parent is None:
            hud = QCheckBox("Stay on screen (HUD)")
            hud.setToolTip("Keeps it fixed on screen, for scores and menus")
            hud.setChecked(o.hud)
            hud.toggled.connect(lambda c: self._toggle_hud(o_, c))
            v.addWidget(hud)

    def _font_combo(self, o):
        combo = QComboBox()
        combo.addItem("(project default)", "")
        for rel, kind in self.ed.project.list_assets("font"):
            combo.addItem(rel.split("/")[-1], rel)
        idx = combo.findData(o.font)
        combo.setCurrentIndex(max(0, idx))
        combo.currentIndexChanged.connect(lambda i: self._set(o, "font", combo.itemData(i)))
        combo.setToolTip("Import a .ttf or .otf font into the Project panel to see it here")
        return combo

    # ---- sprite sheets and animations ---------------------------------------------------
    def _build_animation(self, o):
        from engine import animation
        f, form, v = self._card("Sprite sheet and animations",
                                "Cut one picture into a grid of frames, then name animations like  run = 0-3 @ 10 loop")
        cols = _spin(o.sheet_cols, 1, 256, 1, 0)
        rows = _spin(o.sheet_rows, 1, 256, 1, 0)
        cols.valueChanged.connect(lambda x: self._set(o, "sheet_cols", int(x)))
        rows.valueChanged.connect(lambda x: self._set(o, "sheet_rows", int(x)))
        row = QHBoxLayout()
        row.addWidget(QLabel("Columns"))
        row.addWidget(cols, 1)
        row.addWidget(QLabel("Rows"))
        row.addWidget(rows, 1)
        form.addRow("Grid", row)
        fr = _spin(o.frame, 0, 9999, 1, 0)
        fr.valueChanged.connect(lambda x: self._set(o, "frame", int(x)))
        form.addRow("Frame", fr)
        txt = QPlainTextEdit(animation.format_anims(o.anims))
        txt.setPlaceholderText("idle = 0\nrun = 1-4 @ 10 loop\njump = 5-7 @ 8 once")
        txt.setFixedHeight(90)
        txt.setStyleSheet("font-family: monospace;")
        v.addWidget(txt)
        msg = wrap_label("")
        v.addWidget(msg)

        def commit():
            try:
                anims = animation.parse_anims(txt.toPlainText())
            except Exception as e:  # PawnError carries a friendly message
                msg.setText(str(e))
                return
            msg.setText("")
            if anims != o.anims:
                self._set(o, "anims", anims)
                self.ed.mark_dirty()
        txt.textChanged.connect(commit)
        auto = QComboBox()
        auto.addItem("(none)", "")
        for name in o.anims:
            auto.addItem(name, name)
        idx = auto.findData(o.anim)
        auto.setCurrentIndex(max(0, idx))
        auto.currentIndexChanged.connect(lambda i: self._set(o, "anim", auto.itemData(i)))
        auto.setToolTip("Plays by itself when the game starts. In code:  self.play_anim(\"run\")")
        form.addRow("Autoplay", auto)

    # ---- UI objects ---------------------------------------------------------------------
    def _build_ui(self, o):
        f, form, v = self._card("UI", "Anchored UI stays on the screen edge you pick. React in a script with  on click:")
        if o.parent is None:
            a = QComboBox()
            for name in ANCHOR_NAMES:
                a.addItem(name, name)
            a.setCurrentIndex(max(0, a.findData(o.anchor if o.anchor in ANCHOR_NAMES else "center")))
            a.currentIndexChanged.connect(lambda i: self._set(o, "anchor", a.itemData(i)))
            form.addRow("Anchor", a)
        if o.kind in ("bar", "slider"):
            val = _spin(o.value, 0, 1, 0.05, 2)
            val.valueChanged.connect(lambda x: self._set(o, "value", float(x)))
            form.addRow("Value", val)
        if o.kind == "checkbox":
            c = QCheckBox("Checked")
            c.setChecked(o.checked)
            c.toggled.connect(lambda x: self._set(o, "checked", bool(x)))
            v.addWidget(c)
        if o.kind in ("button", "checkbox", "input", "bar", "slider"):
            t = QLineEdit(o.text)
            t.setPlaceholderText("Text" if o.kind != "input" else "Starting text")
            t.textChanged.connect(lambda s: self._set(o, "text", s))
            form.addRow("Text", t)
            s = _spin(o.text_size, 6, 400, 1, 0)
            self._num_field(o, "text_size", s)
            form.addRow("Text size", s)
            form.addRow("Font", self._font_combo(o))
        r = _spin(o.radius, -1, 200, 1, 0)
        r.setToolTip("-1 uses the project's UI theme")
        r.valueChanged.connect(lambda x: self._set(o, "radius", int(x)))
        form.addRow("Roundness", r)
        en = QCheckBox("Enabled")
        en.setToolTip("Untick to grey it out and ignore the mouse")
        en.setChecked(o.enabled)
        en.toggled.connect(lambda c: self._set(o, "enabled", bool(c)))
        v.addWidget(en)
        v.addWidget(wrap_label("Colors come from Project > UI theme. Set a color above to override it for this one."))

    # ---- polygon, tile map, particles ---------------------------------------------------------
    def _build_polygon(self, o):
        from .editor import SHAPES, shape_points
        f, form, v = self._card("Polygon", "A flat shape with any number of corners. Resize it like any object. "
                                           "Collision uses its box. Project > Import SVG drawing turns vector art into polygons.")
        combo = QComboBox()
        combo.addItem("Pick a shape…", "")
        for name in SHAPES:
            combo.addItem(name.capitalize(), name)
        combo.currentIndexChanged.connect(lambda i: combo.itemData(i) and self._set(o, "points", shape_points(combo.itemData(i))))
        form.addRow("Shape", combo)
        txt = QPlainTextEdit("\n".join(f"{p[0]:g}, {p[1]:g}" for p in o.points))
        txt.setPlaceholderText("One corner per line, from -0.5 to 0.5:\n0, -0.5\n0.5, 0.5\n-0.5, 0.5")
        txt.setFixedHeight(110)
        txt.setStyleSheet("font-family: monospace;")
        v.addWidget(txt)
        msg = wrap_label("")
        v.addWidget(msg)

        def commit():
            pts = []
            for n, line in enumerate(txt.toPlainText().splitlines(), 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    a, b = [float(t) for t in line.replace(";", ",").split(",")]
                except ValueError:
                    msg.setText(f"Line {n}: write a corner like   0.25, -0.5")
                    return
                pts.append([a, b])
            msg.setText("" if len(pts) >= 3 else "A polygon needs at least 3 corners.")
            if len(pts) >= 3 and pts != o.points:
                self._set(o, "points", pts)
        txt.textChanged.connect(commit)

    def _build_info(self, o, title, text):
        f, form, v = self._card(title, text)

    def _build_beam(self, o):
        f, form, v = self._card("Beam", "A line from this object to another one. Type the other object's name. In code:  self.text = \"Player\"")
        target = QLineEdit(o.text)
        target.setPlaceholderText("Name of the other object")
        target.editingFinished.connect(lambda: self._set(o, "text", target.text()))
        form.addRow("Goes to", target)
        width = _spin(o.h, 1, 100, 1, 0)
        width.valueChanged.connect(lambda x: self._set(o, "h", float(x)))
        form.addRow("Thickness", width)

    def _build_prompt(self, o):
        f, form, v = self._card("Prompt", "Shows  [E] text  when an object tagged #player is close. Press E (or pad X) to run  on prompt  in this object's script.")
        txt = QLineEdit(o.text)
        txt.setPlaceholderText("What pressing E does, like Open")
        txt.editingFinished.connect(lambda: self._set(o, "text", txt.text()))
        form.addRow("Action", txt)
        size = _spin(o.w, 20, 2000, 10, 0)
        size.valueChanged.connect(lambda x: (self._set(o, "w", float(x)), setattr(o, "h", float(x))))
        form.addRow("Range", size)

    def _build_zone(self, o):
        f, form, v = self._card("Zone", "An invisible area. Give it a script with  on touch  and  on untouch  to know when things enter or leave. "
                                        "Tick Trigger below so things walk through it.")
        tr = QCheckBox("Things can walk through (trigger)")
        tr.setChecked(o.trigger)
        tr.toggled.connect(lambda c: self._set(o, "trigger", bool(c)))
        v.addWidget(tr)

    def _build_light(self, o):
        f, form, v = self._card("Light", "Cuts a soft hole in the scene's darkness (Project > Scene lighting…). "
                                         "Scripts can move it, change  radius  and  intensity.")
        size = _spin(o.w, 10, 5000, 10, 0)
        size.valueChanged.connect(lambda x: (self._set(o, "w", float(x)), setattr(o, "h", float(x))))
        form.addRow("Size", size)
        it = _spin(o.intensity, 0, 2, 0.1, 2)
        it.valueChanged.connect(lambda x: self._set(o, "intensity", float(x)))
        form.addRow("Strength", it)
        fl = _spin(o.flicker, 0, 1, 0.1, 2)
        fl.setToolTip("0 steady, 1 wobbles a lot (like a candle)")
        fl.valueChanged.connect(lambda x: self._set(o, "flicker", float(x)))
        form.addRow("Flicker", fl)

    def _build_particles(self, o):
        from engine import particles
        f, form, v = self._card("Particles", "Little dots or pictures that fly out of this object. In code:  emitter.burst(30)  or  emitter.preset(\"fire\")")
        on = QCheckBox("Keeps emitting")
        on.setChecked(o.em_on)
        on.toggled.connect(lambda c: self._set(o, "em_on", bool(c)))
        v.addWidget(on)
        preset = QComboBox()
        preset.addItem("Pick a preset…", "")
        for name in particles.PRESETS:
            preset.addItem(name.capitalize(), name)
        preset.setToolTip("Sets all the particle settings at once. You can change them after.")

        def pick(i):
            name = preset.itemData(i)
            if name:
                self.ed.checkpoint(force=True)
                particles.apply_preset(o, name)
                self.ed.mark_dirty()
                self.ed.scene_view.update()
                self.set_object(o)
        preset.currentIndexChanged.connect(pick)
        form.addRow("Preset", preset)
        for field, label, lo, hi, step, dec, tip in (
                ("em_rate", "Per second", 0, 5000, 5, 0, "How many appear each second"),
                ("em_life", "Lifetime", 0.05, 60, 0.1, 2, "Seconds each one lives"),
                ("em_speed", "Speed", 0, 5000, 10, 0, "Start speed"),
                ("em_spread", "Spread", 0, 360, 10, 0, "Angle they fan out over (360 = all directions)"),
                ("em_dir", "Direction", -360, 360, 15, 0, "Centre direction in degrees (-90 = up, 0 = right)"),
                ("em_size", "Size", 0.5, 500, 1, 1, "Start size"),
                ("em_size_end", "End size", 0, 5, 0.1, 2, "Size at the end of life, as a fraction of the start (0 = shrinks away, 2 = doubles)"),
                ("em_size_var", "Size random", 0, 1, 0.1, 2, "How different the sizes are (0 = all the same)"),
                ("em_speed_var", "Speed random", 0, 1, 0.1, 2, "How different the speeds are"),
                ("em_life_var", "Life random", 0, 1, 0.1, 2, "How different the lifetimes are"),
                ("em_alpha_end", "End opacity", 0, 1, 0.1, 2, "How solid they are at the end (0 = fade out completely)"),
                ("em_gravity", "Gravity", -5000, 5000, 50, 0, "Pulls them down (negative lifts them up)"),
                ("em_wind", "Wind", -5000, 5000, 10, 0, "Sideways push (negative = left)"),
                ("em_drag", "Drag", 0, 20, 0.1, 2, "Slows them down (0 = never)"),
                ("em_spin", "Spin", -3600, 3600, 15, 0, "Turning speed in degrees per second (pictures only)"),
                ("em_spin_var", "Spin random", 0, 3600, 15, 0, "Random extra spin"),
                ("em_inherit", "Inherit speed", 0, 1, 0.1, 2, "How much of this object's own speed they start with"),
                ("em_radius", "Circle size", 0, 2000, 1, 0, "Size of the circle shape"),
                ("em_max", "Most alive", 1, 20000, 100, 0, "Most particles alive at once")):
            sp = _spin(getattr(o, field), lo, hi, step, dec)
            sp.setToolTip(tip)
            sp.valueChanged.connect(lambda x, fld=field: self._set(o, fld, float(x) if fld != "em_max" else int(x)))
            form.addRow(label, sp)
        shape = QComboBox()
        for name in ("point", "circle", "box", "line"):
            shape.addItem(name.capitalize(), name)
        shape.setCurrentIndex(max(0, shape.findData(o.em_shape)))
        shape.setToolTip("Where they start: one point, inside a circle, inside the box, or along the width")
        shape.currentIndexChanged.connect(lambda i: self._set(o, "em_shape", shape.itemData(i)))
        form.addRow("Starts from", shape)
        endc = QPushButton(o.em_color_end or "same as start")
        endc.setToolTip("Particles fade toward this color over their life")

        def pick_end():
            c = QColorDialog.getColor(QColor(o.em_color_end or o.color), self, "End color")
            if c.isValid():
                self._set(o, "em_color_end", c.name())
                endc.setText(c.name())
        endc.clicked.connect(pick_end)
        clear = QPushButton("Same")
        clear.setToolTip("Keep the start color all life")
        clear.clicked.connect(lambda: (self._set(o, "em_color_end", ""), endc.setText("same as start")))
        row = QHBoxLayout()
        row.addWidget(endc, 1)
        row.addWidget(clear)
        form.addRow("End color", row)
        for field, label, tip in (("em_add", "Glow (colors add up)", "Bright, fiery look. Good for fire, magic and sparks"),
                                  ("em_local", "Move with the emitter", "Particles stay attached instead of being left behind")):
            cb = QCheckBox(label)
            cb.setChecked(bool(getattr(o, field)))
            cb.setToolTip(tip)
            cb.toggled.connect(lambda c, fld=field: self._set(o, fld, bool(c)))
            v.addWidget(cb)
        v.addWidget(wrap_label("Pictures instead of dots: pick a Picture for this emitter in the Sprite card, and set its sheet columns and rows to use random frames."))

    def _build_tilemap(self, o):
        from engine import tilemap
        f, form, v = self._card("Tile map", "A grid of square tiles. Pick a tile sheet picture, set how it is cut up, then paint in the Scene.")
        ts = _spin(o.tile_size, 4, 512, 4, 0)
        ts.valueChanged.connect(lambda x: self._set_tile_size(o, int(x)))
        form.addRow("Tile size", ts)
        combo = QComboBox()
        combo.addItem("(plain colored tiles)", "")
        for rel, kind in self.ed.project.list_assets("image"):
            combo.addItem(rel.split("/")[-1], rel)
        combo.setCurrentIndex(max(0, combo.findData(o.sprite)))
        combo.currentIndexChanged.connect(lambda i: (self._set(o, "sprite", combo.itemData(i)), self.set_object(o)))
        form.addRow("Tile sheet", combo)
        cols = _spin(o.sheet_cols, 1, 256, 1, 0)
        rows = _spin(o.sheet_rows, 1, 256, 1, 0)
        cols.valueChanged.connect(lambda x: (self._set(o, "sheet_cols", int(x)), self._palette_refresh(o)))
        rows.valueChanged.connect(lambda x: (self._set(o, "sheet_rows", int(x)), self._palette_refresh(o)))
        row = QHBoxLayout()
        row.addWidget(QLabel("Columns"))
        row.addWidget(cols, 1)
        row.addWidget(QLabel("Rows"))
        row.addWidget(rows, 1)
        form.addRow("Sheet grid", row)
        solid = QCheckBox("Tiles are solid")
        solid.setChecked(o.solid)
        solid.toggled.connect(lambda c: self._set(o, "solid", bool(c)))
        v.addWidget(solid)
        paint = QCheckBox("Paint in the Scene   (click = paint, Ctrl+click = erase)")
        paint.setChecked(self.ed.tile_paint)
        paint.toggled.connect(self._toggle_paint)
        v.addWidget(paint)
        self.palette = QListWidget()
        self.palette.setViewMode(QListWidget.IconMode)
        self.palette.setIconSize(QSize(40, 40))
        self.palette.setResizeMode(QListWidget.Adjust)
        self.palette.setMovement(QListWidget.Static)
        self.palette.setFixedHeight(130)
        self.palette.setSpacing(3)
        v.addWidget(self.palette)
        self._palette_refresh(o)
        self.palette.currentRowChanged.connect(lambda r: setattr(self.ed, "tile_brush", max(0, r)))
        clear = QPushButton("Clear all tiles")
        clear.setProperty("flat", True)
        clear.clicked.connect(lambda: (self.ed.checkpoint(force=True), tilemap.clear(o), self.ed.touch(o)))
        v.addWidget(clear)
        v.addWidget(wrap_label("Scripts: map.set_tile(col, row, n)   map.get_tile(col, row)   map.tile_at(x, y)   "
                               "map.fill_tiles(text, legend)"))

    def _toggle_paint(self, on):
        self.ed.tile_paint = bool(on)
        self.ed.scene_view.update()

    def _set_tile_size(self, o, n):
        self._set(o, "tile_size", n)
        o.w = o.h = n
        o.tile_ver += 1
        self.sync_transform()

    def _palette_refresh(self, o):
        pal = getattr(self, "palette", None)
        if pal is None:
            return
        from PySide6.QtGui import QIcon, QPixmap
        pal.blockSignals(True)
        pal.clear()
        cols, rows = max(1, o.sheet_cols), max(1, o.sheet_rows)
        pm = QPixmap(str(self.ed.project.path / o.sprite)) if o.sprite else QPixmap()
        for i in range(min(cols * rows, 400)):
            if not pm.isNull():
                cw, ch = pm.width() / cols, pm.height() / rows
                ic = QIcon(pm.copy(int((i % cols) * cw), int((i // cols) * ch), int(cw), int(ch)).scaled(
                    40, 40, Qt.KeepAspectRatio, Qt.FastTransformation))
                it = QListWidgetItem(ic, "")
            else:
                it = QListWidgetItem(str(i))
            it.setToolTip(f"Tile {i}")
            it.setSizeHint(QSize(46, 46))
            pal.addItem(it)
        pal.setCurrentRow(min(self.ed.tile_brush, max(0, pal.count() - 1)))
        pal.blockSignals(False)

    def _toggle_hud(self, o, on):
        self.ed.checkpoint(f"{o.id}:hud")
        cam = self.ed.scene.camera()
        cp = cam.world_pos() if cam else (0, 0)
        wx, wy = o.world_pos(cp)
        o.hud = on
        o.set_world_pos(wx, wy, cp)
        self.ed.touch(o)
        self.set_object(o)

    def _pick_color(self, o, col):
        self.ed.checkpoint(f"{o.id}:color")
        o.color = col
        self.ed.touch(o)
        self.set_object(o)

    def _custom_color(self, o):
        c = QColorDialog.getColor(QColor(o.color), self, "Pick a color")
        if c.isValid():
            self._pick_color(o, c.name())

    def _build_physics(self, o):
        f, form, v = self._card("Physics", "Gravity makes it fall and jump. Solid makes it a floor or wall.")
        b = QCheckBox("Affected by gravity")
        b.setToolTip("It falls, lands on solid things, and can jump")
        b.setChecked(o.body)
        b.toggled.connect(lambda c: self._set(o, "body", c))
        s = QCheckBox("Solid")
        s.setToolTip("Other objects can stand on it and can't walk through it")
        s.setChecked(o.solid)
        s.toggled.connect(lambda c: self._set(o, "solid", c))
        if o.kind != "tilemap":
            v.addWidget(b)
        v.addWidget(s)
        if o.kind != "tilemap":
            ow = QCheckBox("One-way platform")
            ow.setToolTip("Solid from above only: jump up through it, land on top")
            ow.setChecked(o.one_way)
            ow.toggled.connect(lambda c: self._set(o, "one_way", bool(c)))
            tr = QCheckBox("Trigger (not solid, just detects touches)")
            tr.setToolTip("Use  on touch  and  on untouch  in a script on this object")
            tr.setChecked(o.trigger)
            tr.toggled.connect(lambda c: self._set(o, "trigger", bool(c)))
            v.addWidget(ow)
            v.addWidget(tr)
            sl = QComboBox()
            for label, val in (("No slope", ""), ("Ramp rising to the right", "up-right"), ("Ramp rising to the left", "up-left")):
                sl.addItem(label, val)
            sl.setCurrentIndex(max(0, sl.findData(o.slope)))
            sl.currentIndexChanged.connect(lambda i: self._set(o, "slope", sl.itemData(i)))
            form.addRow("Slope", sl)
        grp = _spin(o.cgroup, 1, 8, 1, 0)
        grp.setToolTip("Which of 8 collision groups this object is in")
        grp.valueChanged.connect(lambda x: self._set(o, "cgroup", int(x)))
        form.addRow("Group", grp)
        mrow = QHBoxLayout()
        mrow.setSpacing(2)
        for bit in range(8):
            cb = QCheckBox(str(bit + 1))
            cb.setChecked(bool((o.cmask >> bit) & 1))
            cb.setToolTip(f"Collide with group {bit + 1}")
            cb.toggled.connect(lambda on_, b_=bit: self._set(o, "cmask", (o.cmask | (1 << b_)) if on_ else (o.cmask & ~(1 << b_))))
            mrow.addWidget(cb)
        form.addRow("Hits", mrow)
        if o.kind == "tilemap":
            return
        fr = _spin(o.friction, 0, 100, 0.5, 1)
        fr.setToolTip("How quickly sideways sliding slows down on the ground. 0 slides forever.")
        fr.valueChanged.connect(lambda x: self._set(o, "friction", float(x)))
        form.addRow("Friction", fr)
        bo = _spin(o.bounce, 0, 1, 0.1, 2)
        bo.setToolTip("0 stops dead, 1 bounces back as fast as it hit")
        bo.valueChanged.connect(lambda x: self._set(o, "bounce", float(x)))
        form.addRow("Bounce", bo)

    # ---- scripts ---------------------------------------------------------------------
    def _build_scripts(self, o):
        f, form, v = self._card("Scripts", "Scripts give this object behavior. Variables at the top of a script show up here.")
        for idx, ref in enumerate(o.scripts):
            v.addWidget(self._script_card(o, idx, ref))
        add = QPushButton("＋  Add script")
        add.setProperty("primary", True)
        add.clicked.connect(lambda: self.ed.show_add_script_menu(o, add))
        v.addWidget(add)

    def _script_card(self, o, idx, ref):
        f = QFrame()
        f.setStyleSheet(f"QFrame {{ background: {C['bg1']}; border: 1px solid {C['border']}; border-radius: 8px; }}"
                        f"QLabel {{ border: none; background: transparent; }}")
        v = QVBoxLayout(f)
        v.setContentsMargins(10, 8, 10, 10)
        v.setSpacing(6)
        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icon("script", C["purple"], 16).pixmap(16, 16))
        name = QLabel(ref["file"])
        name.setStyleSheet(f"color: {C['text']}; font-weight: 700; border: none;")
        edit = QPushButton("Edit code")
        edit.setProperty("flat", True)
        edit.clicked.connect(lambda: self.ed.open_script(ref["file"]))
        rm = QPushButton("✕")
        rm.setProperty("flat", True)
        rm.setToolTip("Remove from this object")
        rm.clicked.connect(lambda: self.ed.remove_script(o, idx))
        head.addWidget(ic)
        head.addWidget(name, 1)
        head.addWidget(edit)
        head.addWidget(rm)
        v.addLayout(head)
        exposed = self.ed.project.script_exposed(ref["file"])
        self._hints = self.ed.project.script_hints(ref["file"])
        if exposed:
            form = QFormLayout()
            form.setContentsMargins(0, 0, 0, 0)
            form.setVerticalSpacing(6)
            for vname, default in exposed.items():
                cur = ref.setdefault("values", {}).get(vname, default)
                label = QLabel(vname.replace("_", " ").capitalize())
                label.setStyleSheet(f"color: {C['muted']}; border: none;")
                form.addRow(label, self._var_widget(o, ref, vname, default, cur))
            v.addLayout(form)
        return f

    def _var_widget(self, o, ref, name, default, cur):
        def store(val):
            self.ed.checkpoint(f"{o.id}:{ref['file']}:{name}")
            ref.setdefault("values", {})[name] = val
            self.ed.touch(o, light=True)
            self.ed.live_value(o, ref["file"], name, val)

        hint = getattr(self, "_hints", {}).get(name, {})
        kind = hint.get("kind")
        if kind == "range" and isinstance(default, (int, float)) and not isinstance(default, bool):
            return self._range_widget(hint, default, cur, store)
        if kind == "choice" and isinstance(default, str):
            w = QComboBox()
            for it in hint["items"]:
                w.addItem(it, it)
            if cur not in hint["items"]:
                w.addItem(str(cur), str(cur))
            w.setCurrentIndex(max(0, w.findData(cur)))
            w.currentIndexChanged.connect(lambda i: store(w.itemData(i)))
            return w
        if kind == "color" and isinstance(default, str):
            return self._color_var(str(cur), store)

        if isinstance(default, bool):
            w = QCheckBox()
            w.setChecked(bool(cur))
            w.toggled.connect(store)
        elif isinstance(default, (int, float)):
            is_int = isinstance(default, int)
            w = _spin(cur, -999999, 999999, 1 if is_int else 0.1, 0 if is_int else 2)
            w.valueChanged.connect(lambda x: store(int(x) if is_int else float(x)))
        else:
            w = QLineEdit(str(cur))
            w.textChanged.connect(store)
        if kind == "text":
            w.setToolTip(hint["text"])
        return w

    def _range_widget(self, hint, default, cur, store):
        """A slider and a number box that stay in step."""
        is_int = isinstance(default, int) and (hint["step"] is None or float(hint["step"]).is_integer())
        lo, hi = hint["min"], hint["max"]
        step = hint["step"] or (1 if is_int else (hi - lo) / 100.0)
        steps = max(1, int(round((hi - lo) / step)))
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, steps)
        spin = _spin(cur, min(lo, cur), max(hi, cur), step, 0 if is_int else 2)
        spin.setFixedWidth(74)
        slider.setValue(int(round((min(max(cur, lo), hi) - lo) / step)))

        def from_slider(i):
            v = lo + i * step
            v = int(round(v)) if is_int else round(v, 4)
            spin.blockSignals(True)
            spin.setValue(v)
            spin.blockSignals(False)
            store(v)

        def from_spin(x):
            v = int(x) if is_int else float(x)
            slider.blockSignals(True)
            slider.setValue(int(round((min(max(v, lo), hi) - lo) / step)))
            slider.blockSignals(False)
            store(v)
        slider.valueChanged.connect(from_slider)
        spin.valueChanged.connect(from_spin)
        row.addWidget(slider, 1)
        row.addWidget(spin)
        return box

    def _color_var(self, cur, store):
        b = QPushButton(cur)

        def paint(c):
            fg = "#000" if QColor(c).lightness() > 128 else "#fff"
            b.setText(c)
            b.setStyleSheet(f"QPushButton {{ background: {c}; color: {fg}; padding: 4px 8px; }}")

        def pick():
            c = QColorDialog.getColor(QColor(b.text()), self, "Pick a color")
            if c.isValid():
                paint(c.name())
                store(c.name())
        b.clicked.connect(pick)
        paint(cur)
        return b
