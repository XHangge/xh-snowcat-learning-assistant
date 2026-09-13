@echo off
setlocal
cd /d "%~dp0"

rem Use the system Python (it already has all dependencies installed)
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found on PATH.
    echo Install Python 3 first, then run this again.
    pause
    exit /b 1
)

rem Quick check: are the core dependencies present?
python -c "import chromadb, PySide6" >nul 2>nul
if errorlevel 1 (
    echo [Setup] Installing dependencies, please wait...
    python -m pip install -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo.
        echo [ERROR] Dependency install failed. See the message above.
        pause
        exit /b 1
    )
)

rem Launch the GUI (pythonw = no console window)
start "" pythonw "%~dp0main.py"
endlocal
