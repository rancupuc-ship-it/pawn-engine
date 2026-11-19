"""Pawn Engine entry point.

    python main.py               open the main menu / editor
    python main.py --play DIR    run an exported game folder
    python main.py PROJECT       open a project (a project folder or its project.pawnproj file)
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def project_arg(args):
    """A project given on the command line (double-clicking a .pawnproj file does this), or None."""
    for a in args:
        if a.startswith("--"):
            continue
        p = Path(a)
        if p.is_file() and p.name.endswith(".pawnproj"):
            p = p.parent
        if p.is_dir() and (p / "project.pawnproj").exists():
            return p
    return None


def main():
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from engine.paths import app_dir, resource

    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PawnEngine.App")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName("Pawn Engine")
    app.setWindowIcon(QIcon(str(resource("assets/icon.png"))))
    from ui.theme import apply_theme
    apply_theme(app)

    args = sys.argv[1:]
    play_dir = None
    if "--play" in args and args.index("--play") + 1 < len(args):
        play_dir = Path(args[args.index("--play") + 1])
    elif (app_dir() / "game" / "project.pawnproj").exists():
        play_dir = app_dir() / "game"

    if play_dir is not None:
        from ui.player import PlayerWindow
        win = PlayerWindow(play_dir)
        win.show()
        sys.exit(app.exec())

    from ui.app import App
    controller = App()
    opened = project_arg(args)
    if opened is not None:
        controller.open_project(opened)
        if controller.editor is None:
            controller.show_launcher()
    else:
        controller.show_launcher()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
