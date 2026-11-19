"""Builds the Pawn Engine app with PyInstaller into dist/PawnEngine/. Used by build_exe.bat and by the GitHub build.

    python tools/build_app.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXCLUDES = ["tkinter", "unittest", "pydoc",
            "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.Qt3DCore",
            "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtPdf",
            "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtBluetooth", "PySide6.QtSensors", "PySide6.QtSerialPort",
            "numpy", "PIL"]


def command():
    sep = ";" if sys.platform.startswith("win") else ":"
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", "PawnEngine",
           "--icon", str(ROOT / "assets" / "icon.ico"), "--add-data", f"assets{sep}assets",
           "--add-data", f"release.json{sep}."]
    for m in EXCLUDES:
        cmd += ["--exclude-module", m]
    cmd += ["--hidden-import", "pawn_core", "main.py"]
    return cmd


if __name__ == "__main__":
    sys.exit(subprocess.call(command(), cwd=ROOT))
