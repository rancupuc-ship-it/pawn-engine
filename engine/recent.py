"""Where Pawn Engine keeps its settings and the recent-projects list."""
import json
import os
import sys
import time
from pathlib import Path


def config_dir():
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    d = base / "PawnEngine"
    d.mkdir(parents=True, exist_ok=True)
    return d


def default_projects_dir():
    docs = Path.home() / "Documents"
    base = docs if docs.exists() else Path.home()
    return base / "Pawn Projects"


def load_recent():
    f = config_dir() / "recent.json"
    try:
        items = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for i in items if isinstance(items, list) else []:
        try:
            if (Path(i["path"]) / "project.pawnproj").exists():
                out.append(i)
        except (KeyError, TypeError, OSError):
            continue
    return out


def _save_recent(items):
    try:
        (config_dir() / "recent.json").write_text(json.dumps(items, indent=2), encoding="utf-8")
    except OSError:
        pass


def add_recent(project):
    items = [i for i in load_recent() if Path(i["path"]) != project.path]
    items.insert(0, {"path": str(project.path), "name": project.name, "opened": time.time()})
    _save_recent(items[:20])


def remove_recent(path):
    _save_recent([i for i in load_recent() if Path(i["path"]) != Path(path)])
