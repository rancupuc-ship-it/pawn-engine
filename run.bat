@echo off
rem Runs Pawn Engine straight from the source. Installs Python by itself if you do not have it.
cd /d "%~dp0"
call setup_python.bat
if not defined PYEXE (
  pause
  exit /b 1
)
%PYEXE% -c "import PySide6, greenlet" >nul 2>nul
if errorlevel 1 (
  echo Installing the pieces Pawn Engine needs. This only happens once...
  %PYEXE% -m pip install -r requirements.txt
)
%PYEXE% main.py
if errorlevel 1 pause
