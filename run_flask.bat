@echo off
REM ============================================================
REM  run_flask.bat - Start Flask Backend
REM  Double-click this file OR run: .\run_flask.bat
REM ============================================================

echo.
echo  ===================================================
echo   Online Exam Monitoring - Flask Backend
echo  ===================================================
echo.

REM Activate virtual environment
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo  [OK] Virtual environment activated: venv\
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo  [OK] Virtual environment activated: .venv\
) else (
    echo  [WARN] No venv found - using system Python
)

echo  [OK] Starting Flask on http://localhost:5000
echo.
python app.py
pause
