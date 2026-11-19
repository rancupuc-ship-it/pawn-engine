"""Saving and loading the game's data (the `game` table) to files in the project's saves/ folder."""
import json
import re

from pawnlang import PawnError
from .project import write_text_atomic

MAX_DEPTH = 12


def _clean(v, depth=0):
    if depth > MAX_DEPTH:
        raise PawnError("That data is nested too deeply to save.")
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, (list, tuple)):
        return [_clean(x, depth + 1) for x in v]
    if isinstance(v, dict):
        return {str(k): _clean(x, depth + 1) for k, x in v.items()}
    raise PawnError("I can only save numbers, text, true/false, lists and tables.",
                    hint="objects can't be saved; save their names or positions instead")


def _slot_path(project, slot):
    slot = str(slot)
    if not re.fullmatch(r"[A-Za-z0-9_\- ]{1,40}", slot):
        raise PawnError(f"'{slot}' isn't a good save name.", hint="use letters, numbers, spaces, - and _")
    return project.path / "saves" / (slot + ".json")


def save(project, slot, data):
    clean = {str(k): _clean(v) for k, v in data.items() if not str(k).startswith("_")}
    path = _slot_path(project, slot)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(path, json.dumps(clean, indent=1))


def load(project, slot):
    """Returns the saved dict, or None when there is no such save (or it is damaged)."""
    path = _slot_path(project, slot)
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def exists(project, slot):
    return _slot_path(project, slot).exists()


def delete(project, slot):
    try:
        _slot_path(project, slot).unlink()
        return True
    except OSError:
        return False


def slots(project):
    d = project.path / "saves"
    return sorted(p.stem for p in d.glob("*.json")) if d.exists() else []
