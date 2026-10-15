@echo off
setlocal
cd /d "%~dp0"

:: Ensure directories exist
if not exist "logs" mkdir logs
if not exist "reports" mkdir reports

:: Execute daily run using virtual environment Python
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py --run-now
) else (
    python main.py --run-now
)
endlocal
