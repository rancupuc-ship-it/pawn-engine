"""Friendly errors and 'Did you mean...?' hints."""
import difflib


class PawnError(Exception):
    """A friendly error that points at a line of a script."""

    def __init__(self, msg, line=None, hint=None, file=None):
        super().__init__(msg)
        self.msg, self.line, self.hint, self.file = msg, line, hint, file

    def pretty(self):
        where = ""
        if self.file:
            where = self.file
        if self.line:
            where = (where + ", line " if where else "Line ") + str(self.line)
        text = (where + ": " if where else "") + self.msg
        if self.hint:
            text += "  (" + self.hint + ")"
        return text


def suggest(name, candidates):
    m = difflib.get_close_matches(name, [c for c in candidates if isinstance(c, str)], n=1, cutoff=0.6)
    return f"Did you mean '{m[0]}'?" if m else None
