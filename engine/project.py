"""Projects on disk: scenes, scripts, module scripts and assets."""
import json
import os
import re
import time
from pathlib import Path

from pawnlang import parse, PawnError
from .recent import (config_dir, default_projects_dir, load_recent, add_recent, remove_recent)  # noqa: F401
from .presets import PRESETS, NEW_SCRIPT, NEW_MODULE  # noqa: F401
from .scene import Scene
from .theme import merged as merged_theme
from .templates import TEMPLATES, build_template  # noqa: F401
from .sounds import make_default_sounds  # noqa: F401

EXT = ".pawnproj"
VERSION = "1.2"
FORMAT = 1
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
FONT_EXT = {".ttf", ".otf"}
SCENE_EXT = ".scene.json"
PREFAB_EXT = ".prefab.json"
SOUND_EXT = {".wav", ".ogg", ".mp3"}
AUDIO_TRY = (".wav", ".ogg", ".mp3")
MODULE_EXT = ".pawnmod"


def write_text_atomic(path, text):
    """Write a file so a crash halfway can never leave it half-written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


class Project:
    def __init__(self, path):
        self.path = Path(path)
        self.meta = json.loads((self.path / "project.pawnproj").read_text(encoding="utf-8"))
        self._exposed = {}
        self._hints = {}

    @property
    def name(self):
        return self.meta.get("name", self.path.name)

    # ---- scenes --------------------------------------------------------------------
    @property
    def scenes_dir(self):
        return self.path / "scenes"

    def scene_path(self, name):
        name = str(name)
        if not name or re.search(r"[\\/]", name) or name.startswith("."):
            raise ValueError(f"'{name}' isn't a good scene name.")
        return self.scenes_dir / (name + SCENE_EXT)

    def list_scenes(self):
        names = sorted(p.name[:-len(SCENE_EXT)] for p in self.scenes_dir.glob("*" + SCENE_EXT))
        return names

    def scene_exists(self, name):
        try:
            return self.scene_path(name).exists()
        except ValueError:
            return False

    @property
    def start_scene(self):
        """The scene the game starts in (Project > ... or the first one if the saved choice is gone)."""
        want = self.meta.get("start_scene", "Main")
        if self.scene_exists(want):
            return want
        names = self.list_scenes()
        return names[0] if names else "Main"

    def set_start_scene(self, name):
        self.meta["start_scene"] = name
        self.save_meta()

    @property
    def scene_file(self):
        return self.scene_path(self.start_scene)

    def new_scene_name(self, base="Level"):
        base = re.sub(r"[^A-Za-z0-9_\- ]", "_", base.strip()) or "Level"
        name, n = base, 1
        while self.scene_exists(name):
            n += 1
            name = f"{base} {n}"
        return name

    def delete_scene(self, name):
        if len(self.list_scenes()) <= 1:
            raise ValueError("A game needs at least one scene.")
        self.scene_path(name).unlink()
        if self.meta.get("start_scene") == name:
            self.meta["start_scene"] = self.list_scenes()[0]
            self.save_meta()

    @property
    def scripts_dir(self):
        return self.path / "scripts"

    @property
    def modules_dir(self):
        return self.path / "modules"

    @property
    def assets_dir(self):
        return self.path / "assets"

    # ---- settings kept in project.pawnproj ------------------------------------------
    def save_meta(self):
        write_text_atomic(self.path / "project.pawnproj", json.dumps(self.meta, indent=2))

    @property
    def theme(self):
        return merged_theme(self.meta.get("theme"))

    def set_theme(self, theme):
        self.meta["theme"] = dict(theme)
        self.save_meta()

    @property
    def audio_levels(self):
        a = self.meta.get("audio")
        return a if isinstance(a, dict) else {}

    def set_audio_levels(self, levels):
        self.meta["audio"] = {k: float(v) for k, v in levels.items()}
        self.save_meta()

    @property
    def window(self):
        """Window options for exported games, always clean and in range."""
        w = self.meta.get("window")
        w = w if isinstance(w, dict) else {}
        def num(key, default, lo, hi):
            try:
                return max(lo, min(hi, int(w.get(key, default))))
            except (TypeError, ValueError, OverflowError):
                return default
        title = w.get("title")
        return {"title": title.strip()[:80] if isinstance(title, str) and title.strip() else self.name,
                "width": num("width", 1152, 320, 7680), "height": num("height", 648, 240, 4320),
                "resizable": w.get("resizable") is not False,
                "fullscreen": w.get("fullscreen") is True,
                "min_width": num("min_width", 320, 160, 7680), "min_height": num("min_height", 240, 120, 4320)}

    def set_window(self, opts):
        self.meta["window"] = dict(opts)
        self.save_meta()
        self.meta["window"] = self.window

    def load_scene(self, name=None):
        path = self.scene_path(name) if name else self.scene_file
        return json.loads(path.read_text(encoding="utf-8"))

    def save_scene(self, data, name=None):
        path = self.scene_path(name) if name else self.scene_file
        write_text_atomic(path, json.dumps(data, indent=1))

    # ---- prefabs: saved objects that scripts can spawn("Name") --------------------------------
    @property
    def prefabs_dir(self):
        return self.path / "prefabs"

    def prefab_path(self, name):
        name = str(name)
        if not re.fullmatch(r"[A-Za-z0-9_\- ()]{1,60}", name):
            raise ValueError(f"'{name}' isn't a good prefab name.")
        return self.prefabs_dir / (name + PREFAB_EXT)

    def list_prefabs(self):
        return sorted(p.name[:-len(PREFAB_EXT)] for p in self.prefabs_dir.glob("*" + PREFAB_EXT))

    def prefab_stamp(self, name):
        try:
            return self.prefab_path(name).stat().st_mtime_ns
        except (OSError, ValueError):
            return None

    def load_prefab(self, name):
        return json.loads(self.prefab_path(name).read_text(encoding="utf-8"))

    def save_prefab(self, name, data):
        path = self.prefab_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(path, json.dumps(data, indent=1))

    # ---- scripts -----------------------------------------------------------------
    def list_scripts(self):
        return sorted(p.name for p in self.scripts_dir.glob("*.pawn"))

    def read_script(self, name):
        return (self.scripts_dir / name).read_text(encoding="utf-8")

    def write_script(self, name, text):
        write_text_atomic(self.scripts_dir / name, text)

    def script_stamp(self, name):
        """Changes whenever the script file changes (None if it doesn't exist)."""
        try:
            st = (self.scripts_dir / name).stat()
        except OSError:
            return None
        return (st.st_mtime_ns, st.st_size)

    def script_exposed(self, name):
        """Variables shown in the Inspector: {name: default}. Cached by file time."""
        path = self.scripts_dir / name
        try:
            mt = path.stat().st_mtime
        except OSError:
            return {}
        hit = self._exposed.get(name)
        if hit and hit[0] == mt:
            return hit[1]
        try:
            exp = dict(parse(path.read_text(encoding="utf-8"), name).exposed)
        except PawnError:
            exp = hit[1] if hit else {}
        self._exposed[name] = (mt, exp)
        return exp

    def script_hints(self, name):
        """Inspector hints from comments (range / choice / color / tooltip), cached by file time."""
        from .hints import parse_hints
        path = self.scripts_dir / name
        try:
            mt = path.stat().st_mtime_ns
        except OSError:
            return {}
        hit = self._hints.get(name)
        if hit and hit[0] == mt:
            return hit[1]
        try:
            h = parse_hints(path.read_text(encoding="utf-8"))
        except OSError:
            h = {}
        self._hints[name] = (mt, h)
        return h

    def new_script_name(self, base="new_script"):
        base = re.sub(r"[^A-Za-z0-9_]", "_", base.strip()) or "new_script"
        base = base[:-5] if base.endswith(".pawn") else base
        name, n = base + ".pawn", 1
        while (self.scripts_dir / name).exists():
            n += 1
            name = f"{base}_{n}.pawn"
        return name

    # ---- module scripts -----------------------------------------------------------
    def list_modules(self):
        return sorted(p.name for p in self.modules_dir.glob("*" + MODULE_EXT))

    def _module_path(self, name):
        name = str(name)
        if not name.endswith(MODULE_EXT):
            name += MODULE_EXT
        if re.search(r"[\\/]", name) or name.startswith("."):
            raise OSError("module names can't contain folders")
        return self.modules_dir / name

    def read_module(self, name):
        return self._module_path(name).read_text(encoding="utf-8")

    def write_module(self, name, text):
        write_text_atomic(self._module_path(name), text)

    def new_module_name(self, base="new_module"):
        base = re.sub(r"[^A-Za-z0-9_]", "_", base.strip()) or "new_module"
        base = base[:-len(MODULE_EXT)] if base.endswith(MODULE_EXT) else base
        name, n = base + MODULE_EXT, 1
        while (self.modules_dir / name).exists():
            n += 1
            name = f"{base}_{n}{MODULE_EXT}"
        return name

    # ---- assets -------------------------------------------------------------------
    def list_assets(self, kind=None):
        out = []
        if not self.assets_dir.exists():
            return out
        for p in sorted(self.assets_dir.rglob("*")):
            ext = p.suffix.lower()
            k = "image" if ext in IMAGE_EXT else "sound" if ext in SOUND_EXT else "font" if ext in FONT_EXT else None
            if k and (kind is None or kind == k):
                out.append((p.relative_to(self.path).as_posix(), k))
        return out

    def import_asset(self, source, subfolder=None):
        """Copy a picture, sound or font into the project. Returns its path relative to the project, or None."""
        import shutil
        src = Path(source)
        ext = src.suffix.lower()
        if ext in IMAGE_EXT:
            sub = subfolder or "sprites"
        elif ext in SOUND_EXT:
            sub = subfolder or ("music" if ext != ".wav" else "sounds")
        elif ext in FONT_EXT:
            sub = subfolder or "fonts"
        else:
            return None
        dest_dir = self.assets_dir / sub
        dest_dir.mkdir(parents=True, exist_ok=True)
        stem = re.sub(r"[^A-Za-z0-9_\-]", "_", src.stem) or "asset"
        dest, n = dest_dir / (stem + ext), 1
        if dest.exists() and dest.read_bytes() == src.read_bytes():
            return dest.relative_to(self.path).as_posix()
        while dest.exists():
            n += 1
            dest = dest_dir / f"{stem}_{n}{ext}"
        shutil.copy2(src, dest)
        return dest.relative_to(self.path).as_posix()

    def audio_path(self, name, folders=("sounds", "music")):
        """Find a sound or song by the name scripts use, e.g. play("coin") -> assets/sounds/coin.wav."""
        name = str(name)
        if not name or re.search(r"[\\/]", name) or name.startswith("."):
            return None
        for folder in folders:
            base = self.assets_dir / folder
            for cand in [base / name] + [base / (name + e) for e in AUDIO_TRY]:
                if cand.is_file():
                    return cand
        return None

    def sound_path(self, name):
        return self.audio_path(name, ("sounds", "music"))

    def music_path(self, name):
        return self.audio_path(name, ("music", "sounds"))


def safe_folder_name(name):
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip(" .") or "My Game"


def create_project(name, parent_dir, template="coin"):
    parent_dir = Path(parent_dir)
    folder = parent_dir / safe_folder_name(name)
    if folder.exists() and any(folder.iterdir()):
        raise FileExistsError(f"A folder named '{folder.name}' already exists in that location.")
    for sub in ("scenes", "scripts", "modules", "assets/sprites", "assets/sounds", "assets/music", "assets/fonts"):
        (folder / sub).mkdir(parents=True, exist_ok=True)
    meta = {"name": name.strip() or "My Game", "version": VERSION, "format": FORMAT, "created": time.time()}
    (folder / "project.pawnproj").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    proj = Project(folder)
    scene = build_template(template, proj)
    proj.save_scene(scene.to_dict(), "Main")
    return proj
