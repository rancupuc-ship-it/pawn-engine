@echo off
rem Builds the fast Rust core (pawn_core) and installs it. Installs Rust by itself if you do not have it.
rem If anything fails the engine still works: it just uses the slower Python version.
cd /d "%~dp0"
if not defined PYEXE call setup_python.bat
if not defined PYEXE goto :nopython

where cargo >nul 2>nul
if errorlevel 1 if exist "%USERPROFILE%\.cargo\bin\cargo.exe" set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
where cargo >nul 2>nul
if errorlevel 1 (
  echo Rust is not installed. Downloading it now. This happens only once...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest https://static.rust-lang.org/rustup/dist/x86_64-pc-windows-gnu/rustup-init.exe -OutFile '%TEMP%\rustup-init.exe'"
  if errorlevel 1 goto :norust
  rem the "gnu" toolchain brings its own linker, so Visual Studio Build Tools are not needed
  "%TEMP%\rustup-init.exe" -y --profile minimal --default-host x86_64-pc-windows-gnu --default-toolchain stable
  if errorlevel 1 goto :norust
  set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
)
where cargo >nul 2>nul
if errorlevel 1 goto :norust

%PYEXE% -m pip install --upgrade maturin >nul
if errorlevel 1 goto :norust
if exist native\target\wheels rmdir /s /q native\target\wheels
%PYEXE% -m maturin build --release -m native\Cargo.toml
if errorlevel 1 goto :norust
for %%W in (native\target\wheels\pawn_core-*.whl) do %PYEXE% -m pip install --force-reinstall "%%W"
if errorlevel 1 goto :norust
echo Fast core installed.
exit /b 0

:nopython
echo Python was not found, so the fast core was skipped.
exit /b 1

:norust
echo.
echo Could not build the fast Rust core. That is OK: Pawn Engine still works, just a bit slower.
echo If you want it later, check your internet connection and run build_native.bat again.
exit /b 1
