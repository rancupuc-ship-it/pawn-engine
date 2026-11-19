@echo off
rem Finds Python 3.10+ and puts it in %PYEXE%. Installs Python automatically if it is missing.
set "PYEXE="

call :scan
if defined PYEXE exit /b 0

echo.
echo Python was not found on this PC. Installing it for you now...
echo.

where winget >nul 2>nul
if not errorlevel 1 (
  echo Trying the Windows package manager...
  winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
  call :scan
  if defined PYEXE exit /b 0
)

echo Downloading Python from python.org (about 25 MB)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing 'https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe' -OutFile '%TEMP%\python-setup.exe'"
if exist "%TEMP%\python-setup.exe" (
  echo Installing Python. Please wait, this can take a minute...
  "%TEMP%\python-setup.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=0 Include_test=0
  del "%TEMP%\python-setup.exe" >nul 2>nul
)
call :scan
if defined PYEXE exit /b 0

echo.
echo Could not install Python automatically.
echo Please install it from https://www.python.org/downloads/ and run this again.
exit /b 1

:scan
call :probe python
call :probe py -3
call :probe "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
call :probe "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
call :probe "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
call :probe "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
exit /b 0

:probe
if defined PYEXE exit /b 0
%* -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul
if not errorlevel 1 set "PYEXE=%*"
exit /b 0
