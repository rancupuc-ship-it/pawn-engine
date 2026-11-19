"""A gentle checker for Pawn scripts: finds typos and unused names that parse fine but won't do what you meant."""
from pawnlang import PawnError, parse, suggest
from pawnlang.parser import KEYWORDS
from .docs import BUILTIN_NAMES, MEMBERS


class Warning_:
    def __init__(self, line, message, hint=None, kind="warning"):
        self.line, self.message, self.hint, self.kind = line, message, hint, kind

    def __repr__(self):
        return f"Line {self.line}: {self.message}"


def _children(node):
    for x in node:
        if isinstance(x, tuple):
            yield x
        elif isinstance(x, list):
            for y in x:
                if isinstance(y, tuple):
                    yield y
                elif isinstance(y, list):
                    for z in y:
                        if isinstance(z, tuple):
                            yield z


def lint(source, filename=None, module=False, extra_known=()):
    """Returns a list of Warning_. A script that doesn't parse returns [] (the parser's own error is shown instead)."""
    try:
        prog = parse(source, filename, module=module)
    except PawnError:
        return []
    defined, uses, member_uses, reads = {}, [], [], set()

    def define(name, line):
        defined.setdefault(name, line)

    def walk(node, target=False):
        if not isinstance(node, tuple) or not node or not isinstance(node[0], str):
            return
        k = node[0]
        if k == "name":
            if not target:
                uses.append((node[2], node[1]))
                reads.add(node[2])
            return
        if k == "assign":
            tgt = node[2]
            if tgt[0] == "name":
                define(tgt[2], node[1])
                if node[3] != "=":
                    uses.append((tgt[2], node[1]))
                    reads.add(tgt[2])
            else:
                walk(tgt)
            walk(node[4])
            return
        if k == "local":
            define(node[2], node[1])
            if node[4] is not None:
                walk(node[4])
            return
        if k == "def":
            define(node[2], node[1])
            for p in node[3]:
                define(p, node[1])
            for st in node[4]:
                walk(st)
            return
        if k == "each":
            define(node[2], node[1])
            if len(node) > 5 and isinstance(node[5], str):
                define(node[5], node[1])
            for ch in _children(node):
                walk(ch)
            return
        if k in ("watch", "onevent", "when"):
            for x in node[2:]:
                if isinstance(x, str) and k != "onevent":
                    define(x, node[1])
            if k == "onevent" and isinstance(node[3], str):
                define(node[3], node[1])
            if k == "watch" and isinstance(node[3], str):
                define(node[3], node[1])
            if k == "when" and len(node) > 3 and isinstance(node[3], str):
                define(node[3], node[1])
        if k == "promote":
            for x in node[2:]:
                if isinstance(x, str):
                    define(x, node[1])
        if k == "attr" and node[2][0] == "name" and node[2][2] in MEMBERS and MEMBERS[node[2][2]] is not None:
            member_uses.append((node[2][2], node[3], node[1]))
        for ch in _children(node):
            walk(ch)

    for n in prog.body:
        walk(n)

    out, seen = [], set()
    known = set(defined) | BUILTIN_NAMES | set(extra_known) | KEYWORDS | {"true", "false", "none"}
    for name, line in sorted(uses, key=lambda u: u[1]):
        if name in known or name in seen:
            continue
        seen.add(name)
        hint = suggest(name, sorted(known - KEYWORDS))
        out.append(Warning_(line, f"I don't know a name called '{name}'.", hint or "did you forget to give it a value first?"))
    mseen = set()
    for owner, member, line in member_uses:
        if member in MEMBERS[owner] or (owner, member) in mseen:
            continue
        mseen.add((owner, member))
        out.append(Warning_(line, f"'{owner}' doesn't have anything called '{member}'.",
                            suggest(member, sorted(MEMBERS[owner]))))
    # names that are set but never read (only private ones: Inspector values are used outside the script)
    for name, line in defined.items():
        if name in reads or name in BUILTIN_NAMES or name in prog.exposed or name.startswith("_"):
            continue
        out.append(Warning_(line, f"'{name}' is given a value but never used.", "remove it, or start it with _ to hide this tip",
                            "info"))
    out.sort(key=lambda w: (w.line, w.kind != "warning"))
    return out
