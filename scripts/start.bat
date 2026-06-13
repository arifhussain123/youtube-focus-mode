@echo off
REM One-click backend startup for Windows. Double-click or run from a terminal.
REM Forwards any flags to auto_start.py, e.g.:  scripts\start.bat --prod
setlocal

set "SCRIPT_DIR=%~dp0"

where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py "%SCRIPT_DIR%auto_start.py" %*
  goto :done
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python "%SCRIPT_DIR%auto_start.py" %*
  goto :done
)

echo ERROR: Python not found. Install it from https://www.python.org/downloads/
:done
pause
