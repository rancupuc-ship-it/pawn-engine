"""Volume buses (master, music, sound), muting and fades. Pure python, so it can be tested without sound hardware."""

BUSES = ("master", "music", "sound")


class Mixer:
    def __init__(self, levels=None):
        self.level = {b: 1.0 for b in BUSES}
        for b, v in (levels or {}).items():
            if b in self.level:
                self.level[b] = max(0.0, min(1.0, float(v)))
        self.muted = False
        self._fade = None           # [target, units per second, stop when done]

    def set(self, bus, v):
        if bus not in self.level:
            raise KeyError(bus)
        self.level[bus] = max(0.0, min(1.0, float(v)))
        if bus == "music":
            self._fade = None

    def effective(self, bus):
        if self.muted:
            return 0.0
        if bus == "master":
            return self.level["master"]
        return self.level["master"] * self.level[bus]

    def fade_music(self, target, seconds, stop=False):
        target = max(0.0, min(1.0, float(target)))
        if seconds <= 0:
            self.level["music"] = target
            self._fade = None
            return "stop" if stop else None
        self._fade = [target, (target - self.level["music"]) / seconds, stop]
        return None

    def update(self, dt):
        """Advance a fade. Returns 'stop' when a fade-out that should stop the music has finished."""
        if self._fade is None:
            return None
        target, rate, stop = self._fade
        cur = self.level["music"] + rate * dt
        done = (rate >= 0 and cur >= target) or (rate < 0 and cur <= target) or rate == 0
        self.level["music"] = target if done else cur
        if done:
            self._fade = None
            return "stop" if stop else None
        return None

    def fading(self):
        return self._fade is not None
