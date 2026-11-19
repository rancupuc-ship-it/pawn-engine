"""The script gallery window: browse ready-made behaviors, read them, and add one to the selected object."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit,
                               QPushButton, QVBoxLayout)

from engine.gallery import GALLERY, CATEGORY_OF_BUILTIN
from engine.presets import PRESETS
from .codeedit import PawnHighlighter
from .theme import C, mono_font


def all_entries():
    """[(category, label, file, description, source)] including the older starter scripts."""
    out = list(GALLERY)
    known = {e[1] for e in out}
    for label, (fname, text) in PRESETS.items():
        if label not in known:
            first = text.splitlines()[0].lstrip("# ").strip() if text else ""
            out.append((CATEGORY_OF_BUILTIN.get(label, "Utility"), label, fname, first, text))
    return sorted(out, key=lambda e: (e[0], e[1]))


class GalleryDialog(QDialog):
    def __init__(self, editor, target):
        super().__init__(editor)
        self.ed, self.target = editor, target
        self.setWindowTitle("Script gallery")
        self.resize(900, 560)
        self.entries = all_entries()
        v = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search: jump, enemy, menu, light…")
        self.search.textChanged.connect(self._fill)
        v.addWidget(self.search)
        row = QHBoxLayout()
        v.addLayout(row, 1)
        self.list = QListWidget()
        self.list.setMinimumWidth(280)
        self.list.setMaximumWidth(320)
        self.list.currentRowChanged.connect(self._show)
        self.list.itemDoubleClicked.connect(lambda _: self._add())
        row.addWidget(self.list)
        right = QVBoxLayout()
        row.addLayout(right, 1)
        self.title = QLabel()
        self.title.setStyleSheet(f"color: {C['gold2']}; font-size: 15px; font-weight: 700;")
        self.desc = QLabel()
        self.desc.setWordWrap(True)
        self.desc.setProperty("muted", True)
        self.code = QPlainTextEdit()
        self.code.setReadOnly(True)
        self.code.setFont(mono_font(10))
        self.code.setLineWrapMode(QPlainTextEdit.NoWrap)
        PawnHighlighter(self.code.document())
        right.addWidget(self.title)
        right.addWidget(self.desc)
        right.addWidget(self.code, 1)
        buttons = QHBoxLayout()
        self.add_btn = QPushButton("Add to " + (f"“{target.name}”" if target is not None else "the project"))
        self.add_btn.setProperty("primary", True)
        self.add_btn.clicked.connect(self._add)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(close)
        buttons.addWidget(self.add_btn)
        right.addLayout(buttons)
        self._fill()

    def _fill(self):
        q = self.search.text().strip().lower()
        self.list.clear()
        self.shown = []
        last = None
        for e in self.entries:
            if q and q not in (e[1] + " " + e[3] + " " + e[0] + " " + e[4]).lower():
                continue
            if e[0] != last:
                last = e[0]
                h = QListWidgetItem(e[0].upper())
                h.setFlags(Qt.NoItemFlags)
                h.setForeground(Qt.gray)
                self.list.addItem(h)
                self.shown.append(None)
            it = QListWidgetItem("   " + e[1])
            self.list.addItem(it)
            self.shown.append(e)
        for i, e in enumerate(self.shown):
            if e is not None:
                self.list.setCurrentRow(i)
                break
        else:
            self._show(-1)

    def _current(self):
        r = self.list.currentRow()
        return self.shown[r] if 0 <= r < len(self.shown) else None

    def _show(self, _row):
        e = self._current()
        self.add_btn.setEnabled(e is not None)
        if e is None:
            self.title.setText("Nothing found")
            self.desc.setText("")
            self.code.setPlainText("")
            return
        self.title.setText(e[1])
        self.desc.setText(e[3])
        self.code.setPlainText(e[4])

    def _add(self):
        e = self._current()
        if e is None:
            return
        _cat, label, fname, _desc, text = e
        proj = self.ed.project
        if not (proj.scripts_dir / fname).exists():
            proj.write_script(fname, text)
            self.ed.files.refresh(proj)
        if self.target is not None:
            self.ed.attach_script(self.target, fname)
            self.ed.log(f"Added “{label}” to {self.target.name}. It is saved as scripts/{fname} — open it to change anything.", "ok")
        else:
            self.ed.log(f"Added scripts/{fname} to your project.", "ok")
        self.accept()
