"""Pawn parser: tokens -> AST (plain tuples: (kind, line, ...))."""
from .lexer import tokenize
from .errors import PawnError
from .program import (Program, KEYWORDS, HANDLERS, MODULES, TIME_WORDS, EASINGS, STATE_ITEMS, UI_EVENTS,  # noqa: F401
                      literal as _literal, _NO)

AUG = {"+=", "-=", "*=", "/="}


class Parser:
    def __init__(self, toks):
        self.t = toks
        self.i = 0
        self.depth = 0
        self.in_state = False

    def peek(self, k=0):
        return self.t[min(self.i + k, len(self.t) - 1)]

    def at(self, typ, val=None):
        tok = self.peek()
        return tok[0] == typ and (val is None or tok[1] == val)

    def accept(self, typ, val=None):
        if self.at(typ, val):
            tok = self.peek()
            self.i += 1
            return tok
        return None

    def expect(self, typ, val=None, msg=None):
        tok = self.accept(typ, val)
        if tok is None:
            cur = self.peek()
            raise PawnError(msg or f"I expected {val or typ.lower()} here.", cur[2])
        return tok

    # ---- program / blocks -------------------------------------------------
    def parse_program(self):
        body = []
        while not self.at("EOF"):
            if self.accept("NEWLINE"):
                continue
            if self.at("INDENT"):
                raise PawnError("This line is indented, but nothing above it starts a block.", self.peek()[2])
            body.append(self.statement())
        return body

    def block(self):
        line = self.peek()[2]
        if not self.accept("NEWLINE"):
            raise PawnError("Put the lines that belong here on the next line, indented by 4 spaces.", line)
        if not self.accept("INDENT"):
            raise PawnError("This needs at least one indented line underneath it.", line)
        self.depth += 1
        stmts = []
        while not self.at("DEDENT") and not self.at("EOF"):
            if self.accept("NEWLINE"):
                continue
            stmts.append(self.statement())
        self.accept("DEDENT")
        self.depth -= 1
        return stmts

    def end_line(self):
        if self.accept("NEWLINE"):
            return
        if self.at("EOF") or self.at("DEDENT"):
            return
        tok = self.peek()
        shown = tok[1] if tok[1] is not None else tok[0].lower()
        raise PawnError(f"I didn't expect '{shown}' here.", tok[2], "each line holds one instruction")

    # ---- statements ---------------------------------------------------------
    def statement(self):
        t = self.peek()
        line = t[2]
        if t[0] == "NAME" and t[1] in KEYWORDS:
            m = getattr(self, "s_" + t[1], None)
            if m:
                return m(line)
            msgs = {"else": "'else' needs an 'if' right above it.", "elif": "'elif' needs an 'if' right above it."}
            raise PawnError(msgs.get(t[1], f"'{t[1]}' can't start a line here."), line)
        return self.simple(line)

    def simple(self, line):
        e = self.expr()
        tok = self.peek()
        if tok[0] == "OP" and (tok[1] == "=" or tok[1] in AUG):
            if e[0] not in ("name", "attr", "index"):
                raise PawnError("You can only store a value in a name, like  score = 5  or  self.x = 5", line)
            self.i += 1
            value = self.expr()
            self.end_line()
            return ("assign", line, e, tok[1], value)
        self.end_line()
        return ("expr", line, e)

    def s_if(self, line):
        self.i += 1
        conds = []
        c = self.expr()
        self.accept("OP", ":")
        conds.append((c, self.block()))
        else_body = None
        while True:
            if self.at("NAME", "elif"):
                self.i += 1
                c = self.expr()
                self.accept("OP", ":")
                conds.append((c, self.block()))
            elif self.at("NAME", "else"):
                self.i += 1
                self.accept("OP", ":")
                else_body = self.block()
                break
            else:
                break
        return ("if", line, conds, else_body)

    def s_while(self, line):
        self.i += 1
        c = self.expr()
        self.accept("OP", ":")
        return ("while", line, c, self.block())

    def s_repeat(self, line):
        self.i += 1
        n = self.expr()
        if self.at("NAME", "times"):
            self.i += 1
        self.accept("OP", ":")
        return ("repeat", line, n, self.block())

    def s_each(self, line):
        self.i += 1
        name = self.expect("NAME", msg="After 'each' put a name, like:  each coin in all(\"Coin\")")[1]
        name2 = None
        if self.accept("OP", ","):
            name2 = self.expect("NAME", msg="After the comma put a second name, like:  each key, value in table")[1]
        self.expect("NAME", "in", "I expected 'in' here, like:  each coin in all(\"Coin\")")
        it = self.expr()
        self.accept("OP", ":")
        return ("each", line, name, it, self.block(), name2)

    def s_def(self, line):
        self.i += 1
        name = self.expect("NAME", msg="After 'def' put the function's name.")[1]
        self.expect("OP", "(", "A function needs parentheses, like:  def hurt(amount)")
        params = []
        while not self.at("OP", ")"):
            params.append(self.expect("NAME", msg="I expected a parameter name here.")[1])
            if not self.accept("OP", ","):
                break
        self.expect("OP", ")", "I expected a ) here.")
        self.accept("OP", ":")
        return ("def", line, name, params, self.block())

    def s_return(self, line):
        self.i += 1
        v = None
        if not (self.at("NEWLINE") or self.at("EOF") or self.at("DEDENT")):
            v = self.expr()
        self.end_line()
        return ("return", line, v)

    def s_break(self, line):
        self.i += 1
        self.end_line()
        return ("break", line)

    def s_continue(self, line):
        self.i += 1
        self.end_line()
        return ("continue", line)

    def s_pass(self, line):
        self.i += 1
        self.end_line()
        return ("pass", line)

    def s_promote(self, line):
        self.i += 1
        name = self.expect("NAME", msg="After 'promote' put a module name, like:  promote game")[1]
        self.end_line()
        return ("promote", line, name)

    def _top_only(self, kw, line):
        if self.depth == 0 or (self.in_state and self.depth == 1):
            return
        where = "the left edge of the script or directly inside a state"
        raise PawnError(f"'{kw}' blocks must start at {where}, not inside another block.", line)

    def s_when(self, line):
        self._top_only("when", line)
        self.i += 1
        cond = self.expr()
        as_name = None
        if self.accept("NAME", "as"):
            as_name = self.expect("NAME", msg="After 'as' put a name.")[1]
        self.accept("OP", ":")
        return ("when", line, cond, as_name, self.block())

    def _timed(self, kw, line):
        self._top_only(kw, line)
        self.i += 1
        n = self.expr()
        tok = self.peek()
        if tok[0] == "NAME" and tok[1] in TIME_WORDS:
            self.i += 1
        self.accept("OP", ":")
        return (kw, line, n, self.block())

    def s_every(self, line):
        return self._timed("every", line)

    def s_after(self, line):
        return self._timed("after", line)

    def s_on(self, line):
        self._top_only("on", line)
        self.i += 1
        if self.in_state:
            if self.accept("NAME", "enter"):
                self.accept("OP", ":")
                return ("onenter", line, self.block())
            if self.accept("NAME", "exit"):
                self.accept("OP", ":")
                return ("onexit", line, self.block())
            raise PawnError("Inside a state I only know  on enter  and  on exit.", line)
        t = self.peek()
        if t[0] == "NAME" and t[1] in UI_EVENTS:
            self.i += 1
            as_name = None
            if self.accept("NAME", "as"):
                as_name = self.expect("NAME", msg="After 'as' put a name, like:  on change as v")[1]
            self.accept("OP", ":")
            return ("onevent", line, t[1], as_name, self.block())
        if not self.accept("NAME", "start"):
            raise PawnError("I only know  on start  and the mouse events  " + ", ".join(UI_EVENTS) + "  here.", line,
                            "on start runs once when the game begins; on click runs when the object is clicked")
        self.accept("OP", ":")
        return ("onstart", line, self.block())

    def s_local(self, line):
        self.i += 1
        name = self.expect("NAME", msg="After 'local' put a name, like:  local speed = 5")[1]
        typ = None
        if self.accept("OP", ":"):
            typ = self.expect("NAME", msg="After the colon put a type, like:  local speed: number = 5")[1]
        value = None
        if self.accept("OP", "="):
            value = self.expr()
        self.end_line()
        return ("local", line, name, typ, value)

    def s_wait(self, line):
        self.i += 1
        if self.accept("NAME", "until"):
            cond = self.expr()
            self.end_line()
            return ("wait", line, "until", cond)
        if self.accept("NAME", "frame"):
            self.end_line()
            return ("wait", line, "frame", None)
        if self.accept("NAME", "tweens"):
            self.end_line()
            return ("wait", line, "tweens", None)
        if self.at("NEWLINE") or self.at("EOF") or self.at("DEDENT"):
            raise PawnError("'wait' needs a time, like  wait 2 seconds", line,
                            "or:  wait until <condition>   /   wait frame")
        n = self.expr()
        tok = self.peek()
        if tok[0] == "NAME" and tok[1] in TIME_WORDS:
            self.i += 1
        self.end_line()
        return ("wait", line, "time", n)

    def s_go(self, line):
        self.i += 1
        name = self.expect("NAME", msg="After 'go' put a state name, like:  go jump")[1]
        self.end_line()
        return ("go", line, name)

    def s_tween(self, line):
        self.i += 1
        target = self.postfix()
        if target[0] not in ("name", "attr", "index"):
            raise PawnError("'tween' needs something to change, like  tween self.x to 300 over 1 second", line)
        self.expect("NAME", "to", "I expected 'to' here, like:  tween self.x to 300 over 1 second")
        value = self.expr()
        self.expect("NAME", "over", "I expected 'over' here, like:  tween self.x to 300 over 1 second")
        dur = self.expr()
        tok = self.peek()
        if tok[0] == "NAME" and tok[1] in TIME_WORDS:
            self.i += 1
        ease = "linear"
        if self.accept("NAME", "ease"):
            ease = self.expect("NAME", msg="After 'ease' put one of: " + ", ".join(EASINGS))[1]
            if ease not in EASINGS:
                raise PawnError(f"I don't know the easing '{ease}'.", line, "try: " + ", ".join(EASINGS))
        self.end_line()
        return ("tween", line, target, value, dur, ease)

    def s_watch(self, line):
        self._top_only("watch", line)
        self.i += 1
        e = self.expr()
        as_name = None
        if self.accept("NAME", "as"):
            as_name = self.expect("NAME", msg="After 'as' put a name.")[1]
        self.accept("OP", ":")
        return ("watch", line, e, as_name, self.block())

    def s_state(self, line):
        if self.depth > 0:
            raise PawnError("'state' blocks must start at the left edge of the script.", line)
        self.i += 1
        name = self.expect("NAME", msg="After 'state' put a name, like:  state idle")[1]
        self.accept("OP", ":")
        if not self.accept("NEWLINE"):
            raise PawnError("Put the lines that belong to this state on the next line, indented.", line)
        if not self.accept("INDENT"):
            raise PawnError("A state needs at least one indented line underneath it.", line)
        self.depth += 1
        self.in_state = True
        items = []
        while not self.at("DEDENT") and not self.at("EOF"):
            if self.accept("NEWLINE"):
                continue
            t = self.peek()
            if not (t[0] == "NAME" and t[1] in ("when", "every", "after", "watch", "on")):
                raise PawnError("Inside a state you can use:  on enter, on exit, when, every, after, watch.", t[2])
            items.append(self.statement())
        self.accept("DEDENT")
        self.in_state = False
        self.depth -= 1
        return ("state", line, name, items)

    # ---- expressions ----------------------------------------------------------
    def expr(self):
        left = self.or_()
        while self.peek()[0] == "OP" and self.peek()[1] == "??":      # a ?? b  means  a, or b when a is none
            line = self.peek()[2]
            self.i += 1
            left = ("coalesce", line, left, self.or_())
        return left

    def or_(self):
        left = self.and_()
        while self.at("NAME", "or"):
            line = self.peek()[2]
            self.i += 1
            left = ("or", line, left, self.and_())
        return left

    def and_(self):
        left = self.not_()
        while self.at("NAME", "and"):
            line = self.peek()[2]
            self.i += 1
            left = ("and", line, left, self.not_())
        return left

    def not_(self):
        if self.at("NAME", "not"):
            line = self.peek()[2]
            self.i += 1
            return ("not", line, self.not_())
        return self.cmp()

    def cmp(self):
        left = self.add()
        while self.peek()[0] == "OP" and self.peek()[1] in ("==", "!=", "<", ">", "<=", ">="):
            tok = self.peek()
            self.i += 1
            left = ("cmp", tok[2], tok[1], left, self.add())
        return left

    def add(self):
        left = self.mul()
        while self.peek()[0] == "OP" and self.peek()[1] in ("+", "-"):
            tok = self.peek()
            self.i += 1
            left = ("bin", tok[2], tok[1], left, self.mul())
        return left

    def mul(self):
        left = self.unary()
        while self.peek()[0] == "OP" and self.peek()[1] in ("*", "/", "%", "//"):
            tok = self.peek()
            self.i += 1
            left = ("bin", tok[2], tok[1], left, self.unary())
        return left

    def unary(self):
        if self.at("OP", "-"):
            line = self.peek()[2]
            self.i += 1
            return ("un", line, "-", self.unary())
        return self.power()

    def power(self):
        base = self.postfix()
        if self.at("OP", "^"):
            line = self.peek()[2]
            self.i += 1
            return ("bin", line, "^", base, self.unary())
        return base

    def postfix(self):
        e = self.primary()
        while True:
            tok = self.peek()
            if tok[0] == "OP" and tok[1] == "(":
                self.i += 1
                args = []
                while not self.at("OP", ")"):
                    args.append(self.expr())
                    if not self.accept("OP", ","):
                        break
                self.expect("OP", ")", "This call is missing its closing ) bracket.")
                e = ("call", tok[2], e, args)
            elif tok[0] == "OP" and tok[1] == ".":
                self.i += 1
                name = self.expect("NAME", msg="After the dot I expected a name, like  self.x")[1]
                e = ("attr", tok[2], e, name)
            elif tok[0] == "OP" and tok[1] == "[":
                self.i += 1
                idx = self.expr()
                self.expect("OP", "]", "This [ is missing its closing ].")
                e = ("index", tok[2], e, idx)
            else:
                return e

    def primary(self):
        tok = self.peek()
        typ, val, line = tok
        if typ == "NUM":
            self.i += 1
            return ("num", line, val)
        if typ == "STR":
            self.i += 1
            return self.make_str(val, line)
        if typ == "NAME":
            if val in ("true", "false"):
                self.i += 1
                return ("bool", line, val == "true")
            if val == "none":
                self.i += 1
                return ("none", line)
            if val in KEYWORDS:
                raise PawnError(f"'{val}' is a Pawn keyword, so it can't be used as a value here.", line)
            self.i += 1
            return ("name", line, val)
        if typ == "OP" and val == "(":
            self.i += 1
            e = self.expr()
            self.expect("OP", ")", "This ( is missing its closing ).")
            return e
        if typ == "OP" and val == "[":
            self.i += 1
            items = []
            while not self.at("OP", "]"):
                items.append(self.expr())
                if not self.accept("OP", ","):
                    break
            self.expect("OP", "]", "This [ is missing its closing ].")
            return ("list", line, items)
        if typ == "OP" and val == "{":
            return self.table(line)
        if typ in ("NEWLINE", "EOF", "DEDENT"):
            raise PawnError("This line ends too early. I expected a value here.", line)
        shown = val if val is not None else typ.lower()
        raise PawnError(f"I didn't expect '{shown}' here.", line)

    def table(self, line):
        self.i += 1
        items = []
        while not self.at("OP", "}"):
            t = self.peek()
            if t[0] == "OP" and t[1] == "[":
                self.i += 1
                key = self.expr()
                self.expect("OP", "]", "This [ is missing its closing ].")
            elif t[0] == "NAME" and self.peek(1)[0] == "OP" and self.peek(1)[1] in ("=", ":"):
                self.i += 1
                key = ("str", t[2], t[1])
            elif t[0] in ("STR", "NUM"):
                key = self.primary()
            else:
                raise PawnError("Table entries look like  name = value", t[2], "for example  {hp = 3, name = \"orc\"}")
            if not (self.accept("OP", "=") or self.accept("OP", ":")):
                raise PawnError("I expected  =  after the name in this table.", self.peek()[2],
                                "for example  {hp = 3}")
            items.append((key, self.expr()))
            if not self.accept("OP", ","):
                break
        self.expect("OP", "}", "This { is missing its closing }.")
        return ("table", line, items)

    def make_str(self, raw, line):
        parts, buf, i = [], [], 0
        esc = {"n": "\n", "t": "\t", '"': '"', "'": "'", "\\": "\\", "{": "{", "}": "}"}
        while i < len(raw):
            c = raw[i]
            if c == "\\" and i + 1 < len(raw):
                buf.append(esc.get(raw[i + 1], raw[i + 1]))
                i += 2
                continue
            if c == "{":
                depth, j = 1, i + 1
                while j < len(raw) and depth:
                    depth += (raw[j] == "{") - (raw[j] == "}")
                    j += 1
                if depth:
                    raise PawnError("A { in this text is missing its closing }.", line, "write \\{ for a literal brace")
                inner = raw[i + 1:j - 1]
                if buf:
                    parts.append("".join(buf))
                    buf = []
                sub = Parser(tokenize(inner, line - 1))
                e = sub.expr()
                if not (sub.at("NEWLINE") or sub.at("EOF")):
                    raise PawnError("I couldn't read what is inside { } in this text.", line)
                parts.append(e)
                i = j
                continue
            buf.append(c)
            i += 1
        if buf:
            parts.append("".join(buf))
        if all(isinstance(p, str) for p in parts):
            return ("str", line, "".join(parts))
        return ("interp", line, parts)


def parse(source, filename=None, module=False):
    try:
        toks = tokenize(source)
        body = Parser(toks).parse_program()
        return Program(body, source, module=module, file=filename)
    except PawnError as e:
        if e.file is None:
            e.file = filename
        raise
