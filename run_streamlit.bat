@echo off
REM ============================================================
REM  run_streamlit.bat - Start Streamlit Dashboard
REM  Double-click this file OR run: .\run_streamlit.bat
REM ============================================================

echo.
echo  ===================================================
echo   Online Exam Monitoring - Streamlit Dashboard
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

echo  [OK] Starting Streamlit on http://localhost:8501
echo.
streamlit run dashboard.py
pause
