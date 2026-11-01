@echo off
REM Verity -- start the server on Windows (run setup.bat first if you haven't).
cd /d "%~dp0backend"

if exist ".venv\Scripts\python.exe" (
    echo Starting Verity on http://localhost:5000 ...
    echo Press CTRL+C in this window to stop the server.
    echo.
    ".venv\Scripts\python.exe" app.py
) else (
    echo.
    echo ERROR: backend\.venv was not found. Run setup.bat first.
    echo.
    pause
)
