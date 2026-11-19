"""Export a project as a standalone game folder."""
import shutil
import sys
from pathlib import Path

from .paths import ROOT, app_dir, frozen
from .project import safe_folder_name

GAME_DIRS = ("scenes", "scripts", "modules", "prefabs", "assets")


def copy_project(project, dest_game):
    dest_game = Path(dest_game)
    if dest_game.exists():
        shutil.rmtree(dest_game)
    dest_game.mkdir(parents=True)
    shutil.copy2(project.path / "project.pawnproj", dest_game / "project.pawnproj")
    for d in GAME_DIRS:
        src = project.path / d
        if src.exists():
            shutil.copytree(src, dest_game / d)


def export_game(project, dest_dir, game_name, overwrite=False):
    """Returns (folder, launcher_path, is_real_exe)."""
    safe = safe_folder_name(game_name)
    out = Path(dest_dir) / safe
    if out.exists():
        if not overwrite:
            raise FileExistsError(f"A folder named '{safe}' already exists there.")
        if out.resolve().parent != Path(dest_dir).resolve():
            raise ValueError("That game name would point outside the chosen folder.")
        shutil.rmtree(out)
    if frozen():
        if Path(dest_dir).resolve().is_relative_to(app_dir().resolve()):
            raise ValueError("Pick a folder outside the Pawn Engine folder to export into.")
        # Running as PawnEngine.exe: the game is this same app + the project data next to it.
        shutil.copytree(app_dir(), out, ignore=shutil.ignore_patterns("game", "*.log", "*.pdb", "__pycache__"))
        exe_name = Path(sys.executable).name
        suffix = Path(exe_name).suffix
        launcher = out / (safe + suffix)
        (out / exe_name).rename(launcher)
        copy_project(project, out / "game")
        return out, launcher, suffix.lower() == ".exe"
    # Running from source: bundle the source so the game runs with Python installed.
    out.mkdir(parents=True)
    app = out / "app"
    app.mkdir()
    for item in ("main.py", "pawnlang", "engine", "ui", "assets"):
        src = ROOT / item
        if src.is_dir():
            shutil.copytree(src, app / item, ignore=shutil.ignore_patterns("__pycache__"))
        elif src.exists():
            shutil.copy2(src, app / item)
    copy_project(project, out / "game")
    bat = out / f"Play {safe}.bat"
    bat.write_text('@echo off\r\ncd /d "%~dp0"\r\npython app\\main.py --play game\r\n', encoding="utf-8")
    sh = out / "play.sh"
    sh.write_text('#!/bin/sh\ncd "$(dirname "$0")"\npython3 app/main.py --play game\n', encoding="utf-8")
    return out, bat, False
