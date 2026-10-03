@echo off
REM OpenDMO launcher for Windows 10/11. Double-click this file.
setlocal
cd /d "%~dp0"
set "PYEXE="
for %%V in (3.14 3.13 3.12 3.11) do (
  if not defined PYEXE (
    py -%%V -c "import sys" >nul 2>&1 && set "PYEXE=py -%%V"
  )
)
if not defined PYEXE (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 && set "PYEXE=python"
)
if not defined PYEXE (
  echo.
  echo [OpenDMO] Python 3.11 or newer was not found.
  echo   1. Download Python from https://www.python.org/downloads/windows/
  echo   2. During setup tick "Add python.exe to PATH".
  echo   3. Double-click start-windows.bat again.
  echo.
  pause
  exit /b 1
)
%PYEXE% run.py %*
if errorlevel 1 pause
endlocal
