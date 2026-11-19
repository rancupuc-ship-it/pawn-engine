"""A script attached to an object: its variables, handlers, running tasks, tweens and states."""
from collections import ChainMap

from pawnlang import (Interp, PawnError, Scope, Task, suggest)
from pawnlang.values import Return, Break, Continue, FastChain, is_num
from .docs import BUILTIN_DOCS
from .proxies import METHODS
from .tween import Tween, run_tweens
from pawnlang.members import LIST_MEMBERS, TABLE_MEMBERS, TEXT_MEMBERS


class _Finished:
    """Stands in for a Task when a block ran start to finish without needing one."""
    done = True
    cancelled = False

    def cancel(self):
        pass


FINISHED = _Finished()
SAFE_METHODS = frozenset(METHODS) | frozenset(LIST_MEMBERS) | frozenset(TEXT_MEMBERS) | frozenset(TABLE_MEMBERS)


def _walk(node):
    if isinstance(node, (tuple, list)):
        yield node
        for x in node:
            yield from _walk(x)


def cannot_wait(body, scope, known_names):
    """True when running this block can never need to pause: no 'wait' in it and no call to code that might wait.

    Such blocks run directly. Everything else runs as a task (greenlet), which is slower but can pause anywhere.
    """
    own = set()
    for n in _walk(body):
        if n and n[0] in ("def", "local") and len(n) > 2 and isinstance(n[2], str):
            own.add(n[2])
    for n in _walk(body):
        if not n or not isinstance(n[0], str):
            continue
        k = n[0]
        if k in ("wait", "def", "tween", "require"):
            return False
        if k == "call":
            callee = n[2]
            if callee[0] == "name":
                nm = callee[2]
                if nm not in known_names or nm in own or scope.find(nm) is not None:
                    return False
            elif callee[0] == "attr":
                if callee[3] not in SAFE_METHODS:
                    return False
            else:
                return False
    return True


class TaskHost:
    """Owns running tasks and tweens. ScriptInstance extends it; the Runtime has one for loose signal handlers."""

    obj = None

    def __init__(self, rt):
        self.rt = rt
        self.tasks = []
        self.tweens = {}
        self.file = None
        self._wait_cache = {}

    def spawn_task(self, runner, owner=None):
        t = Task(self.rt.ctx, self, runner, owner)
        self.tasks.append(t)
        t.step()
        return t

    def resume_tasks(self, dt):
        for t in list(self.tasks):
            if t.done:
                self.tasks.remove(t)
                continue
            t.sleep -= dt
            if t.sleep <= 0:
                t.step()
        self.tasks = [t for t in self.tasks if not t.done]

    def add_tween(self, key, getter, setter, start, end, dur, ease, line):
        self.tweens[key] = Tween(key, getter, setter, start, end, dur, ease, line)
        if dur <= 0:
            run_tweens(self.tweens, 0.0, self.file)

    def tweens_active(self):
        return bool(self.tweens)

    def update_tweens(self, dt):
        if self.tweens:
            run_tweens(self.tweens, dt, self.file)

    def cancel_all(self):
        for t in list(self.tasks):
            t.cancel()
        self.tasks = []
        self.tweens.clear()

    def update(self, dt):
        self.update_tweens(dt)
        self.resume_tasks(dt)


class Handler:
    """One when / every / after / watch block with its own timer and bookkeeping."""

    __slots__ = ("node", "state", "t", "fired", "task", "last", "primed")

    def __init__(self, node, state=None):
        self.node, self.state = node, state
        self.t = 0.0
        self.fired = False
        self.task = None
        self.last = None
        self.primed = False


class ScriptInstance(TaskHost):
    def __init__(self, rt, obj, ref, prog):
        super().__init__(rt)
        self.obj, self.ref, self.prog = obj, ref, prog
        self.file = ref["file"]
        self.fields = {}
        self.scope = Scope(self.fields)
        from .proxies import ObjProxy
        self.proxy = ObjProxy(obj, rt)
        extras = {
            "self": self.proxy,
            "touching": lambda target: rt.touching(obj, target),
            "nearest": lambda target: rt.nearest(obj, target),
            "destroy": lambda target=None: rt.destroy(obj if target is None else target),
            "current_state": lambda: self.state,
            "in_state": lambda name: self.state == name,
        }
        self.interp = Interp(FastChain(extras, rt.shared), self.file, ctx=rt.ctx, owner=self)
        self.interp.globals = self.scope
        self.state = None
        self.pending_state = None
        self._build(prog)

    # ---- setup ---------------------------------------------------------------
    def _build(self, prog):
        self.handlers = [Handler(n) for n in prog.handlers if n[0] not in ("onstart", "onevent")]
        self.start_bodies = [n[2] for n in prog.handlers if n[0] == "onstart"]
        self.event_bodies = {}          # "click" -> [(name given with 'as', body)]
        for n in prog.handlers:
            if n[0] == "onevent":
                self.event_bodies.setdefault(n[2], []).append((n[3], n[4]))
        self.state_defs = {}
        for s in prog.states:
            enter = [i[2] for i in s[3] if i[0] == "onenter"]
            exit_ = [i[2] for i in s[3] if i[0] == "onexit"]
            hs = [i for i in s[3] if i[0] not in ("onenter", "onexit")]
            self.state_defs[s[2]] = (enter, exit_, hs)
        self.state_handlers = []

    def _active(self):
        return _Active(self.rt.ctx, self)

    def _override(self, st):
        """After an exposed variable gets its default, replace it with the value set in the Inspector."""
        if st[0] == "assign" and st[2][0] == "name" and st[2][2] in self.prog.exposed:
            n = st[2][2]
            vals = self.ref.get("values", {})
            if n in vals:
                self.fields[n] = vals[n]

    # ---- lifecycle ---------------------------------------------------------------
    def start(self):
        self._started = True
        with self._active():
            self.rt.ctx.begin_run()
            for st in self.prog.toplevel:
                self.interp.exec(st, self.scope)
                self._override(st)
            for body in self.start_bodies:
                self._run_body(body)
            if self.state_defs:
                self.pending_state = next(iter(self.state_defs))
            self._apply_state()

    def hot_reload(self, prog):
        old = self.prog
        self.cancel_all()
        self.prog = prog
        self._build(prog)
        with self._active():
            self.rt.ctx.begin_run()
            for st in prog.toplevel:
                if st[0] == "def":
                    self.interp.exec(st, self.scope)
                elif st[0] == "local" and st[2] not in self.fields:
                    self.interp.exec(st, self.scope)
                elif st[0] == "assign" and st[2][0] == "name" and st[3] == "=":
                    n = st[2][2]
                    if n in prog.exposed:
                        # reset to the new default only if the default changed (or the variable is new)
                        if n not in self.fields or n not in old.exposed or old.exposed[n] != prog.exposed[n]:
                            self.interp.exec(st, self.scope)
                            self._override(st)
                        else:
                            self._override(st)
                    elif n not in self.fields:
                        self.interp.exec(st, self.scope)
            if self.state_defs:
                keep = self.state if self.state in self.state_defs else next(iter(self.state_defs))
                self.state = None
                self._enter_state(keep, run_enter=False)
            else:
                self.state = None

    # ---- running bodies ----------------------------------------------------------
    def _run_body(self, body, extra=None, owner=None, repeating=False):
        # 'repeating' blocks (when / every / watch) get the "temporary variable" tip; one-off blocks don't
        scope = Scope(extra or {}, self.scope, handler=repeating)
        key = id(body)
        cached = self._wait_cache.get(key)
        if cached is None or cached[0] is not body:
            cached = (body, cannot_wait(body, self.scope, BUILTIN_DOCS))
            self._wait_cache[key] = cached
        if cached[1]:
            ctx = self.rt.ctx
            saved = ctx.task, ctx.inst, ctx.depth
            ctx.task, ctx.inst, ctx.depth = None, self, 0
            ctx.begin_run()
            try:
                self.interp.run_body(body, scope)
            except (Return, Break, Continue):
                pass
            finally:
                ctx.task, ctx.inst, ctx.depth = saved
            return FINISHED

        def runner():
            try:
                self.interp.run_body(body, scope)
            except (Return, Break, Continue):
                pass

        return self.spawn_task(runner, owner)

    # ---- per-frame ---------------------------------------------------------------
    def tick(self, dt):
        with self._active():
            self.update_tweens(dt)
            self.resume_tasks(dt)
            self._apply_state()
            for h in self.handlers:
                self._tick_handler(h, dt)
                if self.obj.dead:
                    return
            for h in self.state_handlers:
                self._tick_handler(h, dt)
                if self.obj.dead:
                    return
            self._apply_state()

    def _tick_handler(self, h, dt):
        n, kind, interp, ctx = h.node, h.node[0], self.interp, self.rt.ctx
        if kind == "when":
            if h.task is not None and not h.task.done:
                return          # still busy waiting: don't start it again on top of itself
            ctx.begin_run()
            val = interp.evaluate(n[2], self.scope)
            if val:
                h.task = self._run_body(n[4], {n[3]: val} if n[3] else None, h.state, True)
        elif kind == "watch":
            ctx.begin_run()
            val = interp.evaluate(n[2], self.scope)
            if not h.primed:
                h.primed, h.last = True, val
            elif val != h.last:
                old, h.last = h.last, val
                extra = {"old": old}
                if n[3]:
                    extra[n[3]] = val
                self._run_body(n[4], extra, h.state, True)
        elif kind in ("every", "after"):
            ctx.begin_run()
            secs = interp.evaluate(n[2], self.scope)
            if not is_num(secs) or secs <= 0:
                raise PawnError(f"'{kind}' needs a time above zero, like  {kind} 2 seconds", n[1], None, self.file)
            if kind == "every":
                h.t += dt
                guard = 0
                while h.t >= secs and guard < 5:
                    h.t -= secs
                    guard += 1
                    self._run_body(n[3], None, h.state, True)
                    if self.obj.dead:
                        return
            elif not h.fired:
                h.t += dt
                if h.t >= secs:
                    h.fired = True
                    self._run_body(n[3], None, h.state)

    # ---- mouse / UI events ------------------------------------------------------------
    def fire_event(self, name, value=None):
        bodies = self.event_bodies.get(name)
        if not bodies:
            return
        with self._active():
            for as_name, body in bodies:
                self._run_body(body, {as_name: value} if as_name else None, None, True)

    # ---- states --------------------------------------------------------------------
    def request_state(self, name, line=None):
        if name not in self.state_defs:
            raise PawnError(f"There is no state called '{name}'.", line,
                            suggest(name, list(self.state_defs)) or f"declare it with  state {name}", self.file)
        self.pending_state = name

    def _apply_state(self):
        guard = 0
        while self.pending_state is not None and guard < 20:
            name, self.pending_state = self.pending_state, None
            guard += 1
            self._enter_state(name)

    def _enter_state(self, name, run_enter=True):
        old = self.state
        if old is not None:
            for t in list(self.tasks):
                if t.owner == old:
                    t.cancel()
            for body in self.state_defs[old][1]:
                self._run_body(body)
        self.state = name
        enter, _exit, hs = self.state_defs[name]
        self.state_handlers = [Handler(n, name) for n in hs]
        if run_enter:
            for body in enter:
                self._run_body(body, None, name)


class _Active:
    """Marks which script is running, so signals and tweens know who they belong to."""

    def __init__(self, ctx, inst):
        self.ctx, self.inst = ctx, inst

    def __enter__(self):
        self.prev = self.ctx.inst
        self.ctx.inst = self.inst

    def __exit__(self, *exc):
        self.ctx.inst = self.prev
        return False
