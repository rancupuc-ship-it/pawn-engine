"""Tiny built-in sound effects, generated in code."""
import math
import struct
import wave


def _tone(path, freqs, secs, vol=0.35):
    rate = 22050
    n = int(rate * secs)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        for i in range(n):
            t = i / n
            f = freqs[0] + (freqs[-1] - freqs[0]) * t
            env = min(1.0, (1 - t) * 4) * min(1.0, i / 200)
            v = int(32767 * vol * env * math.sin(2 * math.pi * f * i / rate))
            frames += struct.pack("<h", v)
        w.writeframes(bytes(frames))


def make_default_sounds(proj):
    d = proj.assets_dir / "sounds"
    d.mkdir(parents=True, exist_ok=True)
    _tone(d / "coin.wav", [988, 1319], 0.16)
    _tone(d / "jump.wav", [280, 620], 0.14)
