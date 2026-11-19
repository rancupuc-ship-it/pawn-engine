"""Runtime values: scopes, functions, control-flow signals and text formatting."""
from collections import ChainMap


class Return(Exception):
    def __init__(self, value=None):
        self.value = value


class Break(Exception):
    pass


class Continue(Exception):
    pass


class FastChain(ChainMap):
    """ChainMap with quick lookups: the interpreter asks for built-in names on every single name it reads."""

    def __contains__(self, key):
        for m in self.maps:
            if key in m:
                return True
        return False

    def __getitem__(self, key):
        for m in self.maps:
            if key in m:
                return m[key]
        return self.__missing__(key)


class Scope:
    __slots__ = ("vars", "parent", "handler")

    def __init__(self, vars=None, parent=None, handler=False):
        self.vars = {} if vars is None else vars
        self.parent = parent
        self.handler = handler      # True for the temporary scope of a when/every/after block

    def find(self, name):
        s = self
        while s is not None:
            if name in s.vars:
                return s
            s = s.parent
        return None

    def names(self):
        out, s = [], self
        while s is not None:
            out.extend(s.vars.keys())
            s = s.parent
        return out


class PawnFunction:
    def __init__(self, name, params, body, interp):
        self.name, self.params, self.body, self.interp = name, params, body, interp

    def __call__(self, *args):
        return self.interp.call_function(self, list(args))

    def __repr__(self):
        return f"<function {self.name}>"


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def fmt(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "none"
    if isinstance(v, float):
        if v != v:
            return "nan"
        if v in (float("inf"), float("-inf")):
            return "inf" if v > 0 else "-inf"
        if abs(v) < 1e15 and v == int(v):
            return str(int(v))
        return ("%.3f" % v).rstrip("0").rstrip(".")
    if isinstance(v, list):
        return "[" + ", ".join(fmt(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{fmt(k)} = {fmt(x)}" for k, x in v.items()) + "}"
    return str(v)


def kind(v):
    """Plain-English name of a value, for error messages."""
    if isinstance(v, bool):
        return "a yes/no value"
    if is_num(v):
        return "a number"
    if isinstance(v, str):
        return "text"
    if v is None:
        return "'none'"
    if isinstance(v, list):
        return "a list"
    if isinstance(v, dict):
        return "a table"
    if isinstance(v, PawnFunction) or callable(v):
        return "a function"
    return "an object"


def type_name(v):
    """Short machine-style name returned by the type() builtin."""
    if isinstance(v, bool):
        return "bool"
    if is_num(v):
        return "number"
    if isinstance(v, str):
        return "text"
    if v is None:
        return "none"
    if isinstance(v, list):
        return "list"
    if isinstance(v, dict):
        return "table"
    if isinstance(v, PawnFunction) or callable(v):
        return "function"
    return "object"
