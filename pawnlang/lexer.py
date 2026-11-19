"""Pawn lexer: turns source text into tokens, with INDENT/DEDENT for blocks."""
import re

from .errors import PawnError  # noqa: F401  (re-exported for older imports)


_TOK = re.compile(r'''
    (?P<num>\d+\.\d+|\d+)
  | (?P<str>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')
  | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<op>==|!=|<=|>=|\?\?|\+=|-=|\*=|/=|//|[-+*/%^<>=()\[\]{},.:])
''', re.X)


def tokenize(src, line_offset=0):
    toks = []
    indents = [0]
    depth = 0
    lines = src.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    last_line = 1
    for number, line in enumerate(lines, 1):
        ln = number + line_offset
        last_line = ln
        if depth == 0:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            ind = 0
            for ch in line:
                if ch == " ":
                    ind += 1
                elif ch == "\t":
                    ind += 4
                else:
                    break
            if ind > indents[-1]:
                indents.append(ind)
                toks.append(("INDENT", None, ln))
            else:
                while ind < indents[-1]:
                    indents.pop()
                    toks.append(("DEDENT", None, ln))
                if ind != indents[-1]:
                    raise PawnError("This line's indentation doesn't match any block above it.", ln,
                                    "use 4 spaces for each level")
        pos, n = 0, len(line)
        while pos < n:
            ch = line[pos]
            if ch in " \t":
                pos += 1
                continue
            if ch == "#":
                break
            m = _TOK.match(line, pos)
            if not m:
                if ch in "\"'":
                    raise PawnError("This text is missing its closing quote.", ln)
                raise PawnError(f"I don't understand the character '{ch}'.", ln)
            pos = m.end()
            kind = m.lastgroup
            val = m.group(kind)
            if kind == "num":
                toks.append(("NUM", float(val) if "." in val else int(val), ln))
            elif kind == "str":
                toks.append(("STR", val[1:-1], ln))
            elif kind == "name":
                toks.append(("NAME", val, ln))
            else:
                if val in ("(", "[", "{"):
                    depth += 1
                elif val in (")", "]", "}"):
                    depth = max(0, depth - 1)
                toks.append(("OP", val, ln))
        if depth == 0:
            toks.append(("NEWLINE", None, ln))
    while len(indents) > 1:
        indents.pop()
        toks.append(("DEDENT", None, last_line))
    toks.append(("EOF", None, last_line))
    return toks
