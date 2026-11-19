"""The optional Rust core (pawn_core). `core` is None when it isn't built; everything then runs in Python."""
import os

core = None
if not os.environ.get("PAWN_NO_NATIVE"):
    try:
        import pawn_core as core  # noqa: F401
    except ImportError:
        core = None


def available():
    return core is not None
