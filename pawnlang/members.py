"""Built-in methods and properties of lists, text and tables (dictionaries)."""
from .errors import PawnError, suggest
from .values import fmt, is_num, kind

LIST_MEMBERS = ("length", "add", "push", "remove", "contains", "first", "last", "pop", "insert", "sort",
                "reverse", "index_of", "slice", "join", "clear", "copy")
TEXT_MEMBERS = ("length", "upper", "lower", "trim", "contains", "starts_with", "ends_with", "replace",
                "split", "index_of", "slice")
TABLE_MEMBERS = ("length", "has", "remove", "keys", "values", "get", "clear", "copy")


def _need_int(v, what="a whole number"):
    if not is_num(v) or v != int(v):
        raise PawnError(f"I expected {what} but got {fmt(v)}.")
    return int(v)


def _sort(lst):
    try:
        lst.sort()
    except TypeError:
        raise PawnError("A list can only be sorted when it holds all numbers or all text.")
    return lst


def _pop(lst, i=None):
    if not lst:
        return None
    if i is None:
        return lst.pop()
    i = _need_int(i)
    if not -len(lst) <= i < len(lst):
        raise PawnError(f"That list has {len(lst)} items, so position {i} doesn't exist.", hint="positions start at 0")
    return lst.pop(i)


def _insert(lst, i, x):
    i = _need_int(i)
    if not 0 <= i <= len(lst):
        raise PawnError(f"You can only insert at positions 0 to {len(lst)} in this list.")
    lst.insert(i, x)


def _slice(lst, a=0, b=None):
    return lst[_need_int(a):None if b is None else _need_int(b)]


def _join(lst, sep=""):
    return str(sep).join(x if isinstance(x, str) else fmt(x) for x in lst)


def list_member(obj, name):
    m = {
        "length": lambda: len(obj),
        "add": lambda x: obj.append(x),
        "push": lambda x: obj.append(x),
        "remove": lambda x: obj.remove(x) if x in obj else None,
        "contains": lambda x: x in obj,
        "pop": lambda i=None: _pop(obj, i),
        "insert": lambda i, x: _insert(obj, i, x),
        "sort": lambda: _sort(obj),
        "reverse": lambda: (obj.reverse(), obj)[1],
        "index_of": lambda x: obj.index(x) if x in obj else -1,
        "slice": lambda a=0, b=None: _slice(obj, a, b),
        "join": lambda sep="": _join(obj, sep),
        "clear": lambda: obj.clear(),
        "copy": lambda: list(obj),
    }
    if name == "length":
        return len(obj)
    if name == "first":
        return obj[0] if obj else None
    if name == "last":
        return obj[-1] if obj else None
    return m.get(name)


def text_member(obj, name):
    m = {
        "upper": lambda: obj.upper(),
        "lower": lambda: obj.lower(),
        "trim": lambda: obj.strip(),
        "contains": lambda x: str(x) in obj,
        "starts_with": lambda x: obj.startswith(str(x)),
        "ends_with": lambda x: obj.endswith(str(x)),
        "replace": lambda a, b: obj.replace(str(a), str(b)),
        "split": lambda sep=" ": obj.split(str(sep)),
        "index_of": lambda x: obj.find(str(x)),
        "slice": lambda a=0, b=None: _text_slice(obj, a, b),
    }
    if name == "length":
        return len(obj)
    return m.get(name)


def _text_slice(text, a, b):
    ok = lambda v: v is None or (isinstance(v, (int, float)) and not isinstance(v, bool))
    if not (ok(a) and ok(b)):
        raise PawnError("slice() needs numbers, like  text.slice(0, 3)")
    return text[int(a or 0):None if b is None else int(b)]


def table_member(obj, name):
    m = {
        "has": lambda k: k in obj,
        "remove": lambda k: obj.pop(k, None),
        "keys": lambda: list(obj.keys()),
        "values": lambda: list(obj.values()),
        "get": lambda k, default=None: obj.get(k, default),
        "clear": lambda: obj.clear(),
        "copy": lambda: dict(obj),
    }
    if name == "length":
        return len(obj)
    return m.get(name)


def get_member(obj, name, line):
    """Read obj.name for lists, text and tables. Tables return 'none' for missing entries."""
    if isinstance(obj, list):
        v = list_member(obj, name)
        if v is not None or name in ("first", "last"):
            return v
        raise PawnError(f"Lists don't have '{name}'.", line,
                        suggest(name, LIST_MEMBERS) or "try: add, remove, contains, length")
    if isinstance(obj, str):
        v = text_member(obj, name)
        if v is not None:
            return v
        raise PawnError(f"Text doesn't have '{name}'.", line,
                        suggest(name, TEXT_MEMBERS) or "try: length, upper, lower, contains")
    if isinstance(obj, dict):
        if name in obj:
            return obj[name]
        return table_member(obj, name)      # a method, or none for a missing entry
    raise PawnError(f"{kind(obj).capitalize()} doesn't have anything called '{name}'.", line)
