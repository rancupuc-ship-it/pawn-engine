"""Signals: objects that scripts can connect functions to and fire."""
from pawnlang import PawnError, PawnFunction


class Connection:
    def __init__(self, signal, entry):
        self.signal, self.entry = signal, entry

    def pawn_get(self, name):
        if name == "disconnect":
            return self.disconnect
        raise PawnError(f"A connection doesn't have '{name}'.", hint="try: disconnect")

    def pawn_set(self, name, value):
        raise PawnError("You can't change a connection.")

    def disconnect(self):
        if self.entry in self.signal.conns:
            self.signal.conns.remove(self.entry)


class Signal:
    def __init__(self, rt, name=None):
        self.rt, self.name = rt, name
        self.conns = []          # [inst, fn, once]
        self.fires = 0
        self.last = None

    def __repr__(self):
        return f"<signal {self.name or ''}>".replace(" >", ">")

    def pawn_get(self, name):
        if name == "connect":
            return lambda fn: self.connect(fn, False)
        if name == "once":
            return lambda fn: self.connect(fn, True)
        if name == "fire":
            return self.fire
        if name == "wait":
            return self.wait
        raise PawnError(f"A signal doesn't have '{name}'.", hint="try: connect, once, fire, wait")

    def pawn_set(self, name, value):
        raise PawnError("You can't change a signal.")

    def connect(self, fn, once):
        if not callable(fn):
            raise PawnError("connect needs a function, like  signal.connect(on_hit)",
                            hint="define it first with  def on_hit()")
        entry = [self.rt.ctx.inst, fn, once]
        self.conns.append(entry)
        return Connection(self, entry)

    def fire(self, *args):
        self.fires += 1
        self.last = args[0] if args else None
        for entry in list(self.conns):
            inst, fn, once = entry
            if inst is not None and inst.obj.dead:
                self.conns.remove(entry)
                continue
            if once:
                self.conns.remove(entry)
            host = inst or self.rt.host
            host.spawn_task(lambda fn=fn, args=args: self._call(fn, args))

    @staticmethod
    def _call(fn, args):
        if isinstance(fn, PawnFunction):
            fn.interp.call_function(fn, list(args))
        else:
            fn(*args)

    def wait(self):
        task = self.rt.ctx.task
        if task is None:
            raise PawnError("'wait' on a signal only works inside  on start,  when,  every  or  after.")
        start = self.fires
        while self.fires == start:
            task.pause(0.0)
        return self.last
