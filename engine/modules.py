"""Module scripts: shared code that scripts load with  require("name")."""
from collections import ChainMap

from pawnlang import Interp, PawnError, Scope, parse, suggest
from pawnlang.values import FastChain, Return

LOADING = object()


class ModuleLoader:
    def __init__(self, rt):
        self.rt = rt
        self.values = {}        # name -> the value the module returned
        self.files = {}

    @staticmethod
    def clean(name):
        name = str(name).strip()
        return name[:-8] if name.endswith(".pawnmod") else name

    def require(self, name):
        name = self.clean(name)
        if name in self.values:
            v = self.values[name]
            if v is LOADING:
                raise PawnError(f"The module '{name}' needs itself (a circular require).",
                                hint="two modules can't require each other while they are loading")
            return v
        value = self._load(name)
        self.values[name] = value
        return value

    def _run(self, name):
        rt = self.rt
        try:
            text = rt.project.read_module(name)
        except OSError:
            have = rt.project.list_modules()
            raise PawnError(f"I can't find a module script called '{name}'.",
                            hint=suggest(name, [m[:-8] for m in have]) or
                            ("available: " + ", ".join(m[:-8] for m in have) if have else
                             "make one in the Project panel (New module script)"))
        file = name + ".pawnmod"
        prog = parse(text, file, module=True)
        interp = Interp(FastChain({}, rt.shared), file, ctx=rt.ctx)
        interp.globals = Scope()
        result = None
        try:
            for st in prog.toplevel:
                interp.exec(st, interp.globals)
        except Return as r:
            result = r.value
        if result is None:
            raise PawnError(f"The module '{name}' didn't return anything.", file=file,
                            hint="end it with  return {...}  or  return some_function")
        return result

    def _load(self, name):
        self.values[name] = LOADING
        try:
            return self._run(name)
        except BaseException:
            self.values.pop(name, None)
            raise

    def reload(self, name):
        """Re-run a module after it was saved. Scripts that already hold its table see the new contents."""
        name = self.clean(name)
        old = self.values.get(name)
        if old is None or old is LOADING:
            return 0
        new = self._run(name)
        if isinstance(old, dict) and isinstance(new, dict):
            old.clear()
            old.update(new)
        else:
            self.values[name] = new
        return 1
