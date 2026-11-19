"""Pawn interpreter: walks the AST."""
import math
import sys

from . import members
from .context import Context, MAX_DEPTH
from .errors import PawnError, suggest
from .parser import MODULES
from .values import (Break, Continue, PawnFunction, Return, Scope, fmt, is_num, kind)

# Each Pawn call uses a dozen Python frames, so allow a deeper stack than the default.
if sys.getrecursionlimit() < 3000:
    sys.setrecursionlimit(3000)

MAX_TEXT = 1_000_000

# Built-ins added in later versions. A script written before they existed may already use these names for its own
# variables, so a script is allowed to take them over instead of getting an error.
SOFT_BUILTINS = frozenset("""raycast raycast_dir can_see find_path can_use wait_left angle_to shuffle wrap approach
smoothstep map_range snap chance atan2 radians degrees tan rope spring weld effect clear_effects pad pad_pressed pad_axis pad_rumble pad_connected pad_count spawn_point respawn""".split())


class PairList(list):
    """What pairs() returns: 'each k, v in pairs(t)' unpacks it into key and value."""


class Interp:
    def __init__(self, builtins, file=None, ctx=None, owner=None):
        self.b = builtins
        self.file = file
        self.ctx = ctx or Context()
        self.owner = owner              # the ScriptInstance this belongs to (None for modules)
        self.globals = Scope()
        self.steps = 0
        self._x = {n[2:]: getattr(self, n) for n in dir(self) if n.startswith("x_")}
        self._e = {n[2:]: getattr(self, n) for n in dir(self) if n.startswith("e_")}

    # ---- entry points -----------------------------------------------------
    def run_body(self, body, scope):
        for st in body:
            self.exec(st, scope)

    def exec(self, st, scope):
        self.steps += 1
        if not self.steps & 127 and self.ctx.over_budget():
            raise PawnError("This script is running too long in one frame. Is there a loop that never ends?",
                            st[1], "check your 'while' loops", self.file)
        try:
            return self._x[st[0]](st, scope)
        except PawnError as e:
            self._tag(e, st[1])
            raise
        except (Return, Break, Continue):
            raise
        except RecursionError:
            raise PawnError("A function kept calling itself too many times.", st[1], None, self.file)
        except Exception as e:  # python-level problem inside a builtin
            raise self.py_error(e, None, st[1])

    def evaluate(self, node, scope):
        try:
            return self.ev(node, scope)
        except PawnError as e:
            self._tag(e, node[1])
            raise
        except (Return, Break, Continue):
            raise
        except RecursionError:
            raise PawnError("A function kept calling itself too many times.", node[1], None, self.file)
        except Exception as e:
            raise self.py_error(e, None, node[1])

    def _tag(self, e, line):
        if e.line is None:
            e.line = line
        if e.file is None:
            e.file = self.file

    def ev(self, node, scope):
        return self._e[node[0]](node, scope)

    def py_error(self, e, name, line):
        """Turn a Python exception from inside a builtin into a friendly PawnError."""
        who = f"'{name}'" if name else "This"
        text = str(e)
        if isinstance(e, TypeError) and ("positional argument" in text or "required" in text):
            msg, hint = f"{who} was called with the wrong number of values.", None
        elif isinstance(e, ZeroDivisionError):
            msg, hint = "You can't divide by zero.", None
        elif isinstance(e, OverflowError):
            msg, hint = "That number is too big.", None
        elif isinstance(e, (TypeError, ValueError)):
            msg = f"{who} can't work with those values."
            hint = "check that you gave it the right kind of value (numbers, text or a list)"
            if "math domain" in text:
                hint = "that number isn't allowed there, like the square root of a negative"
        else:
            msg, hint = f"Something went wrong here: {e}", None
        return PawnError(msg, line, hint, self.file)

    # ---- statements -----------------------------------------------------------
    def x_expr(self, st, scope):
        self.ev(st[2], scope)

    def x_pass(self, st, scope):
        pass

    def x_promote(self, st, scope):
        if st[2] not in MODULES:
            raise PawnError(f"I don't know a module called '{st[2]}'.", st[1],
                            "available: " + ", ".join(sorted(MODULES)) + "   (for your own modules use require)")

    def x_local(self, st, scope):
        scope.vars[st[2]] = None if st[4] is None else self.ev(st[4], scope)

    def x_assign(self, st, scope):
        _, line, target, op, expr = st
        value = self.ev(expr, scope)
        if op != "=":
            cur = self.ev(target, scope)
            value = self.binop(op[0], cur, value, line)
        self.assign(target, value, scope, line)

    def assign(self, target, value, scope, line):
        k = target[0]
        if k == "name":
            name = target[2]
            sc = scope.find(name)
            if sc is None:
                if name in self.b and name not in SOFT_BUILTINS:
                    raise PawnError(f"'{name}' is built in, so you can't give it a new value.", line,
                                    f"pick a different name, or write  local {name} = ...  for your own")
                if scope.handler:
                    self._tip(name, line)
            (sc or scope).vars[name] = value
        elif k == "attr":
            obj = self.ev(target[2], scope)
            if hasattr(obj, "pawn_set"):
                obj.pawn_set(target[3], value)
            elif isinstance(obj, dict):
                obj[target[3]] = value
            else:
                raise PawnError(f"You can't change '{target[3]}' on this value.", line)
        elif k == "index":
            obj = self.ev(target[2], scope)
            idx = self.ev(target[3], scope)
            if isinstance(obj, dict):
                try:
                    obj[idx] = value
                except TypeError:
                    raise PawnError("A table key has to be a number, text or yes/no value.", line)
                return
            if not isinstance(obj, list):
                raise PawnError("Only lists and tables can be changed with [ ].", line)
            if not isinstance(idx, int) or isinstance(idx, bool) or not (-len(obj) <= idx <= len(obj)):
                raise PawnError(f"That list has {len(obj)} items, so position {fmt(idx)} doesn't exist.", line,
                                "positions start at 0")
            if idx == len(obj):
                obj.append(value)
            else:
                obj[idx] = value

    def _tip(self, name, line):
        """One friendly note per name: a variable made inside when/every/after starts fresh each run."""
        warn, key = self.ctx.warn, (self.file, name)
        if warn is None or key in self.ctx.warned:
            return
        self.ctx.warned.add(key)
        warn(f"'{name}' is a temporary variable: it starts fresh every time this block runs. "
             f"To make it remember its value, put  {name} = 0  at the top of the script. "
             f"(Write  local {name} = ...  to say the temporary is on purpose.)", line, self.file)

    def x_if(self, st, scope):
        for cond, body in st[2]:
            if self.ev(cond, scope):
                self.run_body(body, scope)
                return
        if st[3] is not None:
            self.run_body(st[3], scope)

    def x_while(self, st, scope):
        n = 0
        while self.ev(st[2], scope):
            n += 1
            if n > 100000:
                raise PawnError("This 'while' loop ran 100,000 times. It probably never ends.", st[1],
                                "use  wait frame  inside it if it should span many frames")
            try:
                self.run_body(st[3], scope)
            except Break:
                break
            except Continue:
                continue

    def x_repeat(self, st, scope):
        n = self.ev(st[2], scope)
        if not is_num(n):
            raise PawnError("'repeat' needs a number, like  repeat 5", st[1])
        for _ in range(int(n)):
            try:
                self.run_body(st[3], scope)
            except Break:
                break
            except Continue:
                continue

    def x_each(self, st, scope):
        it = self.ev(st[3], scope)
        name, name2 = st[2], st[5] if len(st) > 5 else None
        if isinstance(it, PairList):
            items = [tuple(p) for p in it] if name2 else list(it)
        elif isinstance(it, (str, list)):
            items = list(enumerate(it)) if name2 else list(it)
        elif isinstance(it, dict):
            items = list(it.items()) if name2 else list(it.keys())
        else:
            raise PawnError("'each' needs a list or table to go through, like  each coin in all(\"Coin\")", st[1])
        for item in items:
            if name2:
                scope.vars[name], scope.vars[name2] = item
            else:
                scope.vars[name] = item
            try:
                self.run_body(st[4], scope)
            except Break:
                break
            except Continue:
                continue

    def x_def(self, st, scope):
        scope.vars[st[2]] = PawnFunction(st[2], st[3], st[4], self)

    def x_return(self, st, scope):
        raise Return(None if st[2] is None else self.ev(st[2], scope))

    def x_break(self, st, scope):
        raise Break()

    def x_continue(self, st, scope):
        raise Continue()

    # ---- wait / go / tween ------------------------------------------------------
    def x_wait(self, st, scope):
        task = self.ctx.task
        if task is None:
            raise PawnError("'wait' only works inside  on start,  when,  every,  after  or a function they call.",
                            st[1], "it can't be used at the left edge of a script")
        what = st[2]
        if what == "time":
            secs = self.ev(st[3], scope)
            if not is_num(secs):
                raise PawnError(f"'wait' needs a number of seconds but got {fmt(secs)}.", st[1])
            task.pause(max(0.0, float(secs)))
        elif what == "frame":
            task.pause(0.0)
        elif what == "until":
            while not self.ev(st[3], scope):
                task.pause(0.0)
        elif what == "tweens":
            inst = self._inst(st)
            while inst.tweens_active():
                task.pause(0.0)

    def _inst(self, st):
        inst = self.ctx.inst or self.owner
        if inst is None:
            raise PawnError(f"'{st[0]}' needs a script that is attached to an object.", st[1], None, self.file)
        return inst

    def x_go(self, st, scope):
        self._inst(st).request_state(st[2], st[1])
        raise Return()

    def x_tween(self, st, scope):
        _, line, tgt, value_node, dur_node, ease = st
        inst = self._inst(st)
        if tgt[0] == "attr":
            obj = self.ev(tgt[2], scope)
            attr = tgt[3]
            if not hasattr(obj, "pawn_set"):
                raise PawnError(f"You can't tween '{attr}' on this value.", line)
            key = (id(getattr(obj, "obj", obj)), attr)

            def getter():
                return obj.pawn_get(attr)

            def setter(v):
                obj.pawn_set(attr, v)
        elif tgt[0] == "name":
            holder = scope.find(tgt[2]) or scope
            key = ("var", id(holder), tgt[2])

            def getter():
                return self.ev(tgt, scope)

            def setter(v):
                self.assign(tgt, v, scope, line)
        else:
            container = self.ev(tgt[2], scope)
            idx = self.ev(tgt[3], scope)
            key = (id(container), "idx", idx)

            def getter():
                return self.ev(tgt, scope)

            def setter(v):
                self.assign(tgt, v, scope, line)
        start, end, dur = getter(), self.ev(value_node, scope), self.ev(dur_node, scope)
        for label, v in (("The starting value", start), ("The end value", end), ("The time", dur)):
            if not is_num(v):
                raise PawnError(f"{label} of a tween has to be a number, but I got {fmt(v)}.", line)
        inst.add_tween(key, getter, setter, float(start), float(end), float(dur), ease, line)

    # ---- expressions ------------------------------------------------------------
    def e_num(self, n, scope):
        return n[2]

    def e_str(self, n, scope):
        return n[2]

    def e_bool(self, n, scope):
        return n[2]

    def e_none(self, n, scope):
        return None

    def e_interp(self, n, scope):
        out = []
        for p in n[2]:
            out.append(p if isinstance(p, str) else fmt(self.ev(p, scope)))
        return "".join(out)

    def e_name(self, n, scope):
        name = n[2]
        s = scope
        while s is not None:                 # same as scope.find(), without the extra call
            v = s.vars
            if name in v:
                return v[name]
            s = s.parent
        if name in self.b:
            return self.b[name]
        cands = scope.names() + list(self.b.keys())
        hint = suggest(name, cands) or f"give it a value first, like:  {name} = 0"
        raise PawnError(f"'{name}' isn't defined.", n[1], hint)

    def e_list(self, n, scope):
        return [self.ev(x, scope) for x in n[2]]

    def e_table(self, n, scope):
        out = {}
        for k, v in n[2]:
            key = self.ev(k, scope)
            try:
                out[key] = self.ev(v, scope)
            except TypeError:
                raise PawnError("A table key has to be a number, text or yes/no value.", n[1])
        return out

    def e_attr(self, n, scope):
        obj = self.ev(n[2], scope)
        return self.get_attr(obj, n[3], n[1])

    def e_index(self, n, scope):
        obj = self.ev(n[2], scope)
        idx = self.ev(n[3], scope)
        if isinstance(obj, dict):
            try:
                return obj.get(idx)
            except TypeError:
                raise PawnError("A table key has to be a number, text or yes/no value.", n[1])
        if isinstance(obj, (list, str)):
            if not isinstance(idx, int) or isinstance(idx, bool) or not (-len(obj) <= idx < len(obj)):
                raise PawnError(f"That has {len(obj)} items, so position {fmt(idx)} doesn't exist.", n[1],
                                "positions start at 0")
            return obj[idx]
        raise PawnError("Only lists, tables and text can be read with [ ].", n[1])

    def e_call(self, n, scope):
        fn = self.ev(n[2], scope)
        args = [self.ev(a, scope) for a in n[3]]
        if isinstance(fn, PawnFunction):
            return fn.interp.call_function(fn, args, n[1])
        if callable(fn):
            try:
                return fn(*args)
            except (PawnError, Return, Break, Continue):
                raise
            except RecursionError:
                raise
            except (TypeError, ValueError, ZeroDivisionError, OverflowError) as e:
                raise self.py_error(e, self._callee_name(n[2]), n[1])
        raise PawnError("That isn't something you can call like a function.", n[1])

    @staticmethod
    def _callee_name(node):
        if node[0] == "name":
            return node[2]
        if node[0] == "attr":
            return node[3]
        return None

    def call_function(self, fn, args, line=None):
        if len(args) != len(fn.params):
            raise PawnError(f"'{fn.name}' needs {len(fn.params)} value(s) but got {len(args)}.", line,
                            "def " + fn.name + "(" + ", ".join(fn.params) + ")")
        ctx = self.ctx
        ctx.depth += 1
        try:
            if ctx.depth > MAX_DEPTH:
                raise PawnError(f"'{fn.name}' kept calling itself too many times.", line, None, self.file)
            sc = Scope(dict(zip(fn.params, args)), self.globals)
            try:
                self.run_body(fn.body, sc)
            except Return as r:
                return r.value
            return None
        finally:
            ctx.depth -= 1

    def e_un(self, n, scope):
        v = self.ev(n[3], scope)
        if not is_num(v):
            raise PawnError("The minus sign only works on numbers.", n[1])
        return -v

    def e_not(self, n, scope):
        return not self.ev(n[2], scope)

    def e_and(self, n, scope):
        a = self.ev(n[2], scope)
        return self.ev(n[3], scope) if a else a

    def e_coalesce(self, n, scope):
        a = self.ev(n[2], scope)
        return a if a is not None else self.ev(n[3], scope)

    def e_or(self, n, scope):
        a = self.ev(n[2], scope)
        return a if a else self.ev(n[3], scope)

    def e_bin(self, n, scope):
        a, b = self._e[n[3][0]](n[3], scope), self._e[n[4][0]](n[4], scope)
        ta, tb = type(a), type(b)
        if (ta is float or ta is int) and (tb is float or tb is int):      # plain numbers: the common case
            op = n[2]
            if op == "+":
                return a + b
            if op == "-":
                return a - b
            if op == "*":
                return a * b
        return self.binop(n[2], a, b, n[1])

    def binop(self, op, a, b, line):
        if op == "+":
            if is_num(a) and is_num(b):
                return a + b
            if isinstance(a, list) and isinstance(b, list):
                return a + b
            if isinstance(a, str) or isinstance(b, str):
                return (a if isinstance(a, str) else fmt(a)) + (b if isinstance(b, str) else fmt(b))
            raise PawnError(f"I can't add {self.kind(a)} and {self.kind(b)}.", line)
        if op == "*" and isinstance(a, str) and is_num(b):
            if len(a) * max(0, int(b)) > MAX_TEXT:
                raise PawnError("That text would be longer than a million letters.", line)
            return a * int(b)
        if not (is_num(a) and is_num(b)):
            raise PawnError(f"'{op}' only works on numbers, but I got {self.kind(a)} and {self.kind(b)}.", line)
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op in ("/", "%", "//"):
            if b == 0:
                raise PawnError("You can't divide by zero.", line)
            return a / b if op == "/" else a % b if op == "%" else a // b
        if op == "^":
            try:
                if isinstance(a, int) and isinstance(b, int) and 0 <= b <= 64 and abs(a) < 1000:
                    return a ** b
                return math.pow(a, b)
            except (ValueError, OverflowError, ZeroDivisionError):
                raise PawnError(f"I can't work out {fmt(a)} ^ {fmt(b)}.", line,
                                "a negative number can't be raised to a fractional power")
        raise PawnError(f"I don't know the operator '{op}'.", line)

    def e_cmp(self, n, scope):
        op, a, b = n[2], self._e[n[3][0]](n[3], scope), self._e[n[4][0]](n[4], scope)
        if op == "==":
            return a == b
        if op == "!=":
            return a != b
        ta, tb = type(a), type(b)
        if not (((ta is float or ta is int) and (tb is float or tb is int)) or (ta is str and tb is str)
                or (is_num(a) and is_num(b)) or (isinstance(a, str) and isinstance(b, str))):
            raise PawnError(f"I can't compare {self.kind(a)} with {self.kind(b)}.", n[1])
        if op == "<":
            return a < b
        if op == ">":
            return a > b
        if op == "<=":
            return a <= b
        return a >= b

    @staticmethod
    def kind(v):
        return kind(v)

    # ---- attributes --------------------------------------------------------------
    def get_attr(self, obj, name, line):
        if hasattr(obj, "pawn_get"):
            return obj.pawn_get(name)
        return members.get_member(obj, name, line)
