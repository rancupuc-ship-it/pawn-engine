"""Tasks: a running block of Pawn code that can pause with 'wait' and be resumed later.

Each task runs inside a greenlet, so 'wait' works at any depth: inside loops, inside functions,
even inside functions that are called from other functions.
"""
import greenlet


class TaskExit(BaseException):
    """Raised inside a task that was cancelled. Not an Exception, so scripts can't swallow it."""


class Task:
    def __init__(self, ctx, inst, runner, owner=None, label=""):
        self.ctx, self.inst, self.runner = ctx, inst, runner
        self.owner = owner              # name of the state that started it (or None)
        self.label = label
        self.sleep = 0.0
        self.depth = 0
        self.done = False
        self.cancelled = False
        self.g = greenlet.greenlet(self._main)

    def _main(self):
        try:
            self.runner()
        except TaskExit:
            pass

    # ---- called from the scheduler ---------------------------------------
    def step(self):
        if self.done:
            return
        ctx = self.ctx
        prev_task, prev_inst, prev_depth = ctx.task, ctx.inst, ctx.depth
        ctx.task, ctx.inst, ctx.depth = self, self.inst, self.depth
        ctx.begin_run()
        self.g.parent = greenlet.getcurrent()
        try:
            self.g.switch()
        finally:
            self.depth = ctx.depth
            ctx.task, ctx.inst, ctx.depth = prev_task, prev_inst, prev_depth
            if self.g.dead:
                self.done = True

    def cancel(self):
        if self.done:
            return
        self.cancelled = True
        if self.ctx.task is self:       # cancelling itself: it stops at its next pause
            return
        self.done = True
        try:
            self.g.throw(TaskExit)
        except TaskExit:
            pass
        except greenlet.error:
            pass

    # ---- called from inside the task --------------------------------------
    def pause(self, seconds=0.0):
        self.sleep = seconds
        self.g.parent.switch()
        if self.cancelled:
            raise TaskExit()
