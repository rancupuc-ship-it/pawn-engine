@echo off
rem Builds PawnEngine.exe (with the pawn icon) into dist\PawnEngine\ and puts a shortcut on your Desktop.
rem Installs Python by itself if you do not have it.
cd /d "%~dp0"

call setup_python.bat
if not defined PYEXE goto :fail

echo [1/6] Installing build tools. This can take a few minutes the first time...
%PYEXE% -m pip install --upgrade pip >nul
%PYEXE% -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :fail

echo [2/6] Building the fast Rust core (optional, installs Rust if needed)...
call build_native.bat

echo [3/6] Drawing the app icon...
%PYEXE% tools\make_icon.py
if errorlevel 1 goto :fail

echo [4/6] Building the app...
%PYEXE% tools\build_app.py
if errorlevel 1 goto :fail

echo [5/6] Putting Pawn Engine on your Desktop...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d=[Environment]::GetFolderPath('Desktop'); $exe='%CD%\dist\PawnEngine\PawnEngine.exe'; $s=(New-Object -ComObject WScript.Shell).CreateShortcut($d+'\Pawn Engine.lnk'); $s.TargetPath=$exe; $s.WorkingDirectory='%CD%\dist\PawnEngine'; $s.IconLocation=$exe; $s.Description='Pawn Engine'; $s.Save()" 2>nul

echo [6/6] Done!
echo.
echo   "Pawn Engine" is now on your Desktop. Double-click it to start!
echo   (The real app is in dist\PawnEngine - do not delete that folder.)
echo.
echo   To make a game .exe: open a project in Pawn Engine, then File ^> Export game.
echo.
start "" "%~dp0dist\PawnEngine\PawnEngine.exe"
pause
exit /b 0

:fail
echo.
echo Something went wrong. Scroll up to see the message, and send it to me.
pause
exit /b 1
