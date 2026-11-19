"""State shared by every interpreter of one running game: call depth, time budget, current task."""
import time

RUN_LIMIT = 0.10        # seconds one block (or one resume of a waiting block) may run
FRAME_LIMIT = 0.30      # seconds all scripts together may use in one frame
MAX_DEPTH = 80


class Context:
    def __init__(self, warn=None):
        self.depth = 0
        self.task = None            # the Task that is running right now (None outside of tasks)
        self.inst = None            # the ScriptInstance whose code is running right now
        self.run_deadline = None
        self.frame_deadline = None
        self.warn = warn            # warn(message, line, file)
        self.warned = set()

    def begin_run(self):
        self.run_deadline = time.perf_counter() + RUN_LIMIT

    def begin_frame(self):
        self.frame_deadline = time.perf_counter() + FRAME_LIMIT

    def over_budget(self):
        now = time.perf_counter()
        return (self.run_deadline is not None and now > self.run_deadline) or \
               (self.frame_deadline is not None and now > self.frame_deadline)
