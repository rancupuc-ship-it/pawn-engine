"""Code editor for .pawn scripts: line numbers, colors, auto-indent, live syntax check."""
import re

from PySide6.QtCore import QStringListModel, Qt, QRect, QSize, QTimer, Signal
from PySide6.QtGui import (QColor, QFont, QPainter, QSyntaxHighlighter, QTextCharFormat, QTextFormat,
                           QTextCursor)
from PySide6.QtWidgets import QCompleter, QHBoxLayout, QLabel, QPlainTextEdit, QTextEdit, QVBoxLayout, QWidget

from pawnlang import parse, PawnError
from pawnlang.parser import KEYWORDS
from engine.docs import BUILTIN_DOCS, MEMBERS, OBJECT_DOCS, SPECIAL_DOCS, doc_for
from engine.lint import lint
from .theme import C, mono_font

BLOCK_STARTS = {"if", "elif", "else", "while", "repeat", "each", "def", "when", "every", "after", "on",
                "watch", "state"}
BUILTINS = sorted(set(BUILTIN_DOCS) | {"touching", "nearest", "destroy", "current_state", "in_state"})
SPECIAL = ["self", "game", "camera", "mouse", "dt", "pi"]


def _fmt(color, bold=False, italic=False):
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Bold)
    f.setFontItalic(italic)
    return f


class PawnHighlighter(QSyntaxHighlighter):
    def __init__(self, doc):
        super().__init__(doc)
        self.rules = [
            (re.compile(r"\b(" + "|".join(sorted(KEYWORDS)) + r")\b"), _fmt("#c792ea", bold=True)),
            (re.compile(r"\b(" + "|".join(BUILTINS) + r")\b(?=\()"), _fmt(C["teal"])),
            (re.compile(r"\b(" + "|".join(SPECIAL) + r")\b"), _fmt(C["gold2"])),
            (re.compile(r"\b\d+(\.\d+)?\b"), _fmt("#f78c6c")),
            (re.compile(r'"[^"\n]*"|\'[^\'\n]*\''), _fmt("#a5d6a7")),
            (re.compile(r"#[^\n]*"), _fmt("#6b7385", italic=True)),
        ]

    def highlightBlock(self, text):
        for rx, fmt in self.rules:
            for m in rx.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)


class _Gutter(QWidget):
    def __init__(self, ed):
        super().__init__(ed)
        self.ed = ed

    def sizeHint(self):
        return QSize(self.ed.gutter_width(), 0)

    def paintEvent(self, e):
        self.ed.paint_gutter(e)


class CodeEdit(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.setFont(mono_font(11))
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.setStyleSheet(f"QPlainTextEdit {{ background: {C['bg0']}; border: none; border-radius: 0; padding: 4px; }}")
        self.gutter = _Gutter(self)
        self.error_line = None
        self.warnings = {}              # line -> message from the linter
        self.completer = QCompleter(self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setModel(QStringListModel([], self.completer))
        self.completer.activated.connect(self._insert_completion)
        self.completer.popup().setStyleSheet(
            f"QListView {{ background: {C['bg1']}; color: {C['text']}; border: 1px solid {C['border']}; padding: 2px; }}"
            f"QListView::item:selected {{ background: {C['gold']}; color: #1a1406; }}")
        self.blockCountChanged.connect(self._margin)
        self.updateRequest.connect(self._gutter_update)
        self.cursorPositionChanged.connect(self._extra)
        self._margin()
        self._extra()
        self.highlighter = PawnHighlighter(self.document())

    # gutter ----------------------------------------------------------------
    def gutter_width(self):
        digits = max(3, len(str(max(1, self.blockCount()))))
        return 22 + self.fontMetrics().horizontalAdvance("9") * digits

    def _margin(self, _=0):
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _gutter_update(self, rect, dy):
        if dy:
            self.gutter.scroll(0, dy)
        else:
            self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._margin()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cr = self.contentsRect()
        self.gutter.setGeometry(QRect(cr.left(), cr.top(), self.gutter_width(), cr.height()))

    def paint_gutter(self, event):
        p = QPainter(self.gutter)
        p.fillRect(event.rect(), QColor(C["bg1"]))
        block = self.firstVisibleBlock()
        num = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        cur = self.textCursor().blockNumber()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                bad = self.error_line is not None and num + 1 == self.error_line
                p.setPen(QColor(C["red"]) if bad else QColor(C["gold2"]) if num == cur else QColor("#5d6476"))
                p.drawText(0, top, self.gutter.width() - 10, self.fontMetrics().height(), Qt.AlignRight, str(num + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            num += 1

    def _extra(self):
        sels = []
        if not self.isReadOnly():
            s = QTextEdit.ExtraSelection()
            s.format.setBackground(QColor(255, 255, 255, 12))
            s.format.setProperty(QTextFormat.FullWidthSelection, True)
            s.cursor = self.textCursor()
            s.cursor.clearSelection()
            sels.append(s)
        if self.error_line:
            b = self.document().findBlockByNumber(self.error_line - 1)
            if b.isValid():
                s = QTextEdit.ExtraSelection()
                s.format.setBackground(QColor(239, 107, 107, 55))
                s.format.setProperty(QTextFormat.FullWidthSelection, True)
                s.cursor = QTextCursor(b)
                sels.append(s)
        for line in self.warnings:
            b = self.document().findBlockByNumber(line - 1)
            if b.isValid() and line != self.error_line:
                s = QTextEdit.ExtraSelection()
                s.format.setUnderlineStyle(QTextCharFormat.WaveUnderline)
                s.format.setUnderlineColor(QColor(C["gold"]))
                c = QTextCursor(b)
                c.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
                s.cursor = c
                sels.append(s)
        self.setExtraSelections(sels)

    def set_warnings(self, warnings):
        """warnings: list of engine.lint.Warning_. Shown as wavy underlines."""
        self.warnings = {}
        for w in warnings:
            self.warnings.setdefault(w.line, w)
        self._extra()

    # ---- autocomplete -------------------------------------------------------------
    def _word_info(self):
        """(prefix being typed, the object before a dot or None, True when typing right after a dot)."""
        cur = self.textCursor()
        text = cur.block().text()[:cur.positionInBlock()]
        m = re.search(r"([A-Za-z_][A-Za-z0-9_]*)?$", text)
        prefix = m.group(1) or ""
        before = text[:len(text) - len(prefix)]
        owner = None
        dm = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\.$", before)
        if dm:
            owner = dm.group(1)
        return prefix, owner, before.endswith("."), text

    def _candidates(self, owner):
        if owner is not None:
            names = MEMBERS.get(owner)
            if names:
                return sorted(names)
            if owner == "game":
                return sorted(set(re.findall(r"\bgame\.([A-Za-z_][A-Za-z0-9_]*)", self.toPlainText())))
            return []
        words = set(KEYWORDS) | set(BUILTIN_DOCS) | set(SPECIAL_DOCS)
        words |= set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]{2,})\b", self.toPlainText()))
        return sorted(w for w in words if not w[0].isdigit())

    def _update_completer(self):
        prefix, owner, after_dot, line_text = self._word_info()
        in_comment = "#" in re.sub(r"(\"[^\"]*\"|'[^']*')", "", line_text)
        names = self._candidates(owner) if not in_comment else []
        if not names or (len(prefix) < 2 and not after_dot) or (len(prefix) == 0 and not after_dot):
            self.completer.popup().hide()
            return
        if prefix in names and len(names) == 1:
            self.completer.popup().hide()
            return
        self.completer.model().setStringList(names)
        self.completer.setCompletionPrefix(prefix)
        pop = self.completer.popup()
        if self.completer.completionCount() == 0:
            pop.hide()
            return
        pop.setCurrentIndex(self.completer.completionModel().index(0, 0))
        r = self.cursorRect()
        r.setWidth(pop.sizeHintForColumn(0) + pop.verticalScrollBar().sizeHint().width() + 12)
        self.completer.complete(r)

    def _insert_completion(self, text):
        prefix, _, _, _ = self._word_info()
        cur = self.textCursor()
        cur.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, len(prefix))
        cur.insertText(text)
        self.setTextCursor(cur)

    def set_error_line(self, line):
        self.error_line = line
        self._extra()
        self.gutter.update()

    def goto_line(self, line):
        b = self.document().findBlockByNumber(max(0, line - 1))
        if b.isValid():
            c = QTextCursor(b)
            self.setTextCursor(c)
            self.centerCursor()

    # typing helpers -------------------------------------------------------------
    def keyPressEvent(self, e):
        pop = self.completer.popup()
        if pop.isVisible() and e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab, Qt.Key_Backtab, Qt.Key_Escape):
            if e.key() == Qt.Key_Backtab:
                pop.hide()
            else:
                e.ignore()          # the completer takes Enter / Tab (accept) and Escape (close)
                return
        self._key_core(e)
        if e.text() and (e.text().isalnum() or e.text() in "_." ) and not (e.modifiers() & (Qt.ControlModifier | Qt.AltModifier)):
            self._update_completer()
        elif pop.isVisible() and e.key() in (Qt.Key_Backspace, Qt.Key_Delete):
            self._update_completer()
        elif pop.isVisible() and e.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Home, Qt.Key_End):
            pop.hide()

    def _key_core(self, e):
        k = e.key()
        cur = self.textCursor()
        if k in (Qt.Key_Return, Qt.Key_Enter) and not (e.modifiers() & Qt.ShiftModifier):
            line = cur.block().text()
            indent = re.match(r"[ \t]*", line).group(0)
            first = line.strip().split(" ")[0].rstrip(":")
            before = line[:cur.positionInBlock()].strip()
            if before and (first in BLOCK_STARTS or line.rstrip().endswith(":")):
                indent += "    "
            super().keyPressEvent(e)
            self.insertPlainText(indent)
            return
        if k == Qt.Key_Tab and not (e.modifiers() & Qt.ControlModifier):
            if cur.hasSelection():
                self._shift_lines(True)
            else:
                col = cur.positionInBlock()
                self.insertPlainText(" " * (4 - col % 4))
            return
        if k == Qt.Key_Backtab:
            self._shift_lines(False)
            return
        if k == Qt.Key_Backspace and not cur.hasSelection():
            col = cur.positionInBlock()
            text = cur.block().text()
            if col >= 4 and col % 4 == 0 and text[:col].strip() == "":
                for _ in range(4):
                    cur.deletePreviousChar()
                return
        super().keyPressEvent(e)

    def _shift_lines(self, indent):
        cur = self.textCursor()
        start, end = cur.selectionStart(), cur.selectionEnd()
        doc = self.document()
        b1, b2 = doc.findBlock(start), doc.findBlock(end)
        cur.beginEditBlock()
        b = b1
        while True:
            c = QTextCursor(b)
            if indent:
                c.insertText("    ")
            else:
                t = b.text()
                n = len(t) - len(t.lstrip(" "))
                for _ in range(min(4, n)):
                    c.deleteChar()
            if b == b2:
                break
            b = b.next()
        cur.endEditBlock()


class CodeTab(QWidget):
    """A code editor tab for one script file. Autosaves and tells the editor to hot reload."""
    saved = Signal(str)

    def __init__(self, project, file):
        super().__init__()
        self.project, self.file = project, file
        self.edit = CodeEdit()
        self.status = QLabel()
        self.status.setStyleSheet(f"color: {C['muted']}; padding: 0 4px;")
        top = QWidget()
        top.setStyleSheet(f"background: {C['bg0']};")
        tl = QHBoxLayout(top)
        tl.setContentsMargins(14, 7, 14, 7)
        name = QLabel(file)
        name.setStyleSheet(f"color: {C['gold2']}; font-weight: 700;")
        hint = QLabel("Saves automatically  •  Running games update instantly" +
                      ("  •  Module script: loaded with require(...)" if file.endswith(".pawnmod") else ""))
        hint.setStyleSheet(f"color: {C['muted']};")
        tl.addWidget(name)
        tl.addStretch(1)
        tl.addWidget(hint)
        bottom = QWidget()
        bottom.setStyleSheet(f"background: {C['bg0']};")
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(14, 5, 14, 5)
        bl.addWidget(self.status)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(top)
        lay.addWidget(self.edit, 1)
        lay.addWidget(bottom)
        self.is_module = file.endswith(".pawnmod")
        self.edit.setPlainText(project.read_module(file) if self.is_module else project.read_script(file))
        self.dirty = False
        self._save_t = QTimer(self, singleShot=True, interval=900)
        self._save_t.timeout.connect(self.save)
        self._check_t = QTimer(self, singleShot=True, interval=350)
        self._check_t.timeout.connect(self.check)
        self.edit.textChanged.connect(self._changed)
        self.warnings = []
        self.edit.cursorPositionChanged.connect(self._show_hint)
        self.check()

    def _changed(self):
        self.dirty = True
        self.status.setText("Editing…")
        self.status.setStyleSheet(f"color: {C['muted']};")
        self._save_t.start()
        self._check_t.start()

    def check(self):
        try:
            parse(self.edit.toPlainText(), self.file, module=self.is_module)
        except PawnError as e:
            self.edit.set_error_line(e.line)
            self.status.setText("⚠  " + e.pretty())
            self.status.setStyleSheet(f"color: {C['red']};")
            return False
        self.edit.set_error_line(None)
        try:
            known = ()
            self.warnings = lint(self.edit.toPlainText(), self.file, module=self.is_module, extra_known=known)
        except Exception:               # the linter must never get in the way of writing code
            self.warnings = []
        self.edit.set_warnings([w for w in self.warnings])
        self._show_hint()
        return True

    def _show_hint(self):
        """Status line: the warning on this line, else help for the word under the cursor, else the saved state."""
        cur = self.edit.textCursor()
        line = cur.blockNumber() + 1
        ws = [w for w in self.warnings if w.line == line] if hasattr(self, "warnings") else []
        if ws:
            w = ws[0]
            self.status.setText(("💡  " if w.kind == "info" else "⚠  ") + w.message + ("  " + w.hint if w.hint else ""))
            self.status.setStyleSheet(f"color: {C['gold2']};")
            return
        word = ""
        c2 = QTextCursor(cur)
        c2.select(QTextCursor.WordUnderCursor)
        word = c2.selectedText()
        d = doc_for(word) if word else None
        if d:
            self.status.setText(f"{d[0]}   —   {d[1]}")
            self.status.setStyleSheet(f"color: {C['teal']};")
            return
        n = len(getattr(self, "warnings", []))
        if self.dirty:
            return
        self.status.setText("✓  Saved" + (f"   ({n} tip{'s' if n != 1 else ''} — click the underlined lines)" if n else ""))
        self.status.setStyleSheet(f"color: {C['green']};")

    def save(self):
        if not self.dirty:
            return
        if self.is_module:
            self.project.write_module(self.file, self.edit.toPlainText())
        else:
            self.project.write_script(self.file, self.edit.toPlainText())
        self.dirty = False
        ok = self.check()
        if ok:
            self.status.setText("✓  Saved")
            self.status.setStyleSheet(f"color: {C['green']};")
        self.saved.emit(self.file)

    def show_error(self, line):
        self.edit.set_error_line(line)
        if line:
            self.edit.goto_line(line)
