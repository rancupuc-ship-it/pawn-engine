"""Small project-wide settings dialogs: the UI theme and the audio mixer."""
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QSlider, QSpinBox, QVBoxLayout)
from PySide6.QtCore import Qt

from engine.theme import DEFAULT_THEME, THEME_LABELS
from .theme import C


class ThemeDialog(QDialog):
    """Colors, roundness and font shared by every button, bar, slider and text box."""

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.setWindowTitle("UI theme")
        self.project = project
        self.values = project.theme
        v = QVBoxLayout(self)
        v.addWidget(QLabel("These apply to every UI object unless you set a color on that one object."))
        form = QFormLayout()
        self.btns = {}
        for key, label in THEME_LABELS.items():
            b = QPushButton()
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self._pick(k))
            self.btns[key] = b
            form.addRow(label, b)
        self.radius = QSpinBox()
        self.radius.setRange(0, 200)
        self.radius.setValue(int(self.values["radius"]))
        form.addRow("Roundness", self.radius)
        self.font = QComboBox()
        self.font.addItem("(default font)", "")
        for rel, _ in project.list_assets("font"):
            self.font.addItem(rel.split("/")[-1], rel)
        self.font.setCurrentIndex(max(0, self.font.findData(self.values["font"])))
        form.addRow("Font", self.font)
        v.addLayout(form)
        row = QHBoxLayout()
        reset = QPushButton("Back to defaults")
        reset.clicked.connect(self._reset)
        row.addWidget(reset)
        row.addStretch(1)
        v.addLayout(row)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self._paint()

    def _paint(self):
        for k, b in self.btns.items():
            col = self.values[k]
            fg = "#000" if QColor(col).lightness() > 128 else "#fff"
            b.setText(col)
            b.setStyleSheet(f"QPushButton {{ background: {col}; color: {fg}; border: 1px solid {C['border']}; padding: 6px 12px; }}")

    def _pick(self, key):
        c = QColorDialog.getColor(QColor(self.values[key]), self, THEME_LABELS[key])
        if c.isValid():
            self.values[key] = c.name()
            self._paint()

    def _reset(self):
        self.values = dict(DEFAULT_THEME)
        self.radius.setValue(int(self.values["radius"]))
        self.font.setCurrentIndex(0)
        self._paint()

    def result_theme(self):
        out = dict(self.values)
        out["radius"] = self.radius.value()
        out["font"] = self.font.currentData() or ""
        return out


class MixerDialog(QDialog):
    """Starting volumes for master, music and sound effects. Scripts can change them with volume()."""

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Audio mixer")
        self.setMinimumWidth(360)
        lv = project.audio_levels
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Starting volumes. In a script:  volume(\"music\", 0.5)"))
        self.sliders = {}
        form = QFormLayout()
        for key, label in (("master", "Master"), ("music", "Music"), ("sound", "Sound effects")):
            s = QSlider(Qt.Horizontal)
            s.setRange(0, 100)
            s.setValue(int(round(float(lv.get(key, 1.0)) * 100)))
            num = QLabel(f"{s.value()}%")
            s.valueChanged.connect(lambda x, n=num: n.setText(f"{x}%"))
            row = QHBoxLayout()
            row.addWidget(s, 1)
            row.addWidget(num)
            form.addRow(label, row)
            self.sliders[key] = s
        v.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def levels(self):
        return {k: s.value() / 100.0 for k, s in self.sliders.items()}


class LightingDialog(QDialog):
    """How dark the scene is and what color the darkness has. Light objects cut through it."""

    def __init__(self, scene, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scene lighting")
        self.setMinimumWidth(360)
        self.ambient = scene.ambient
        v = QVBoxLayout(self)
        v.addWidget(QLabel("0% is normal daylight. Add Light objects (Add > Light) to see through the darkness.\n"
                           "In a script:  darkness(0.7)   ambient(\"#101030\")"))
        form = QFormLayout()
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(int(round(scene.darkness * 100)))
        num = QLabel(f"{self.slider.value()}%")
        self.slider.valueChanged.connect(lambda x: num.setText(f"{x}%"))
        row = QHBoxLayout()
        row.addWidget(self.slider, 1)
        row.addWidget(num)
        form.addRow("Darkness", row)
        self.btn = QPushButton()
        self.btn.clicked.connect(self._pick)
        form.addRow("Color", self.btn)
        v.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self._paint()

    def _paint(self):
        fg = "#000" if QColor(self.ambient).lightness() > 128 else "#fff"
        self.btn.setText(self.ambient)
        self.btn.setStyleSheet(f"QPushButton {{ background: {self.ambient}; color: {fg}; padding: 6px 12px; }}")

    def _pick(self):
        c = QColorDialog.getColor(QColor(self.ambient), self, "Darkness color")
        if c.isValid():
            self.ambient = c.name()
            self._paint()

    def result(self):
        return self.slider.value() / 100.0, self.ambient


class WindowDialog(QDialog):
    """How the exported game's window looks: title, size, resizable, fullscreen. Put assets/icon.png in the project for your own icon."""

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Game window")
        self.setMinimumWidth(380)
        o = project.window
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Used by exported games and Play in the standalone player.\nOwn icon: put icon.png in assets."))
        form = QFormLayout()
        self.title = QLineEdit(o["title"])
        self.w = QSpinBox(); self.w.setRange(320, 7680); self.w.setValue(o["width"])
        self.h = QSpinBox(); self.h.setRange(240, 4320); self.h.setValue(o["height"])
        self.resizable = QCheckBox("Player can resize the window"); self.resizable.setChecked(o["resizable"])
        self.full = QCheckBox("Start in fullscreen (F11 toggles)"); self.full.setChecked(o["fullscreen"])
        form.addRow("Title", self.title)
        form.addRow("Width", self.w)
        form.addRow("Height", self.h)
        form.addRow("", self.resizable)
        form.addRow("", self.full)
        v.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def options(self):
        return {"title": self.title.text(), "width": self.w.value(), "height": self.h.value(),
                "resizable": self.resizable.isChecked(), "fullscreen": self.full.isChecked()}
