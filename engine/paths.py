import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def frozen():
    return bool(getattr(sys, "frozen", False))


def app_dir():
    return Path(sys.executable).parent if frozen() else ROOT


def resource(rel):
    base = Path(getattr(sys, "_MEIPASS", ROOT))
    return base / rel
