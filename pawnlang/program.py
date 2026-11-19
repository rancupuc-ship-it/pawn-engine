"""A parsed script: top-level statements, event handlers, states and Inspector-exposed variables."""
from .errors import PawnError

KEYWORDS = {"if", "elif", "else", "while", "repeat", "each", "in", "def", "return", "break",
            "continue", "pass", "when", "every", "after", "on", "promote", "and", "or", "not",
            "true", "false", "none", "as", "local", "wait", "watch", "state", "go", "tween"}
HANDLERS = {"when", "every", "after", "onstart", "watch", "onevent"}
UI_EVENTS = ("click", "press", "release", "hover", "leave", "change", "submit", "touch", "untouch", "prompt")
STATE_ITEMS = {"when", "every", "after", "watch", "onenter", "onexit"}
MODULES = {"game"}
TIME_WORDS = {"seconds", "second", "sec", "s"}
EASINGS = ("linear", "in", "out", "inout", "smooth")
_NO = object()


def literal(node):
    k = node[0]
    if k in ("num", "bool"):
        return node[2]
    if k == "str":
        return node[2]
    if k == "un" and node[2] == "-" and node[3][0] == "num":
        return -node[3][2]
    return _NO


class Program:
    def __init__(self, body, source="", module=False, file=None):
        self.body = body
        self.source = source
        self.module = module
        self.file = file
        self.handlers = [n for n in body if n[0] in HANDLERS]
        self.states = [n for n in body if n[0] == "state"]
        self.toplevel = [n for n in body if n[0] not in HANDLERS and n[0] != "state"]
        self.promotes = [n[2] for n in body if n[0] == "promote"]
        self.exposed = {}
        for n in self.toplevel:
            if n[0] == "assign" and n[3] == "=" and n[2][0] == "name":
                v = literal(n[4])
                if v is not _NO and not n[2][2].startswith("_"):
                    self.exposed[n[2][2]] = v
        self._validate()

    def _validate(self):
        if self.module:
            for n in self.body:
                if n[0] in HANDLERS or n[0] == "state":
                    word = {"onstart": "on start", "state": "state"}.get(n[0], n[0])
                    if n[0] == "onevent":
                        word = "on " + n[2]
                    raise PawnError(f"Module scripts only hold functions and values, so '{word}' can't go here.",
                                    n[1], "put it in a normal script instead", self.file)
        else:
            for n in self.toplevel:
                if n[0] == "return":
                    raise PawnError("'return' at the left edge only works in module scripts.", n[1],
                                    "inside a function or a 'when' block it is fine", self.file)
        names = [s[2] for s in self.states]
        for i, nm in enumerate(names):
            if nm in names[:i]:
                raise PawnError(f"There are two states called '{nm}'.", self.states[i][1], None, self.file)
