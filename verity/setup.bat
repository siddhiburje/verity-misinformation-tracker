@echo off
REM Verity -- one-time environment setup for Windows.
REM Double-click this file, or run it from Command Prompt / PowerShell:
REM   setup.bat

echo == Verity setup (Windows) ==

where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo ERROR: "python" was not found on your PATH.
    echo Install Python 3.10+ from https://www.python.org/downloads/
    echo During install, make sure to check "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

REM 1. Virtual environment
if not exist "backend\.venv" (
    echo Creating virtual environment in backend\.venv ...
    python -m venv backend\.venv
)

REM 2. Python dependencies
echo Installing Python dependencies ...
call backend\.venv\Scripts\python.exe -m pip install --upgrade pip -q
call backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -q

REM 3. spaCy English model (not a normal PyPI package)
echo Installing spaCy English NER model ...
call backend\.venv\Scripts\python.exe -m pip install -q "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"
if errorlevel 1 (
    echo   (warning: could not install the spaCy model -- named-entity extraction
    echo    will degrade gracefully but keywords/similarity/graph still work^)
)

REM 4. Tesseract OCR check (system install, not pip)
where tesseract >nul 2>nul
if errorlevel 1 (
    if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
        echo Tesseract OCR found at C:\Program Files\Tesseract-OCR\tesseract.exe
    ) else (
        echo.
        echo   NOTE: Tesseract OCR was not found.
        echo   Image upload analysis will not work until it is installed.
        echo   Download the installer from:
        echo     https://github.com/UB-Mannheim/tesseract/wiki
        echo   During install, check "Add to PATH" if offered. If you skip that,
        echo   the app will still find it automatically at its default install
        echo   location, or you can set a TESSERACT_CMD environment variable
        echo   pointing at tesseract.exe.
        echo.
    )
) else (
    echo Tesseract OCR found on PATH.
)

REM 5. .env file
if not exist "backend\.env" (
    copy backend\.env.example backend\.env >nul
    echo Created backend\.env from backend\.env.example -- edit it to add your
    echo NEWSAPI_KEY and generate real secret keys ^(optional for local use^).
)

echo.
echo Setup complete. Next step:
echo   run.bat
echo.
pause
