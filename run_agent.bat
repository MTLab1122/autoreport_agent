@echo off
setlocal
cd /d "%~dp0"

:: Ensure logs directory exists
if not exist "logs" mkdir logs

:: Execute daily run using virtual environment Python
call .\.venv\Scripts\activate.bat
python main.py --run-now >> "logs\agent_%DATE:~10,4%-%DATE:~4,2%-%DATE:~7,2%.log" 2>&1
endlocal
