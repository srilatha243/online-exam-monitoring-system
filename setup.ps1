# ============================================================
#  setup.ps1 - One-click project setup
#  Run once after cloning: .\setup.ps1
# ============================================================

Write-Host ""
Write-Host " ============================================" -ForegroundColor Cyan
Write-Host "  Online Exam Monitoring - Project Setup" -ForegroundColor Cyan
Write-Host " ============================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Create virtual environments
if (-not (Test-Path ".\venv")) {
    Write-Host " [1/4] Creating virtual environment (venv)..." -ForegroundColor Yellow
    python -m venv venv
    Write-Host " [OK]  venv created." -ForegroundColor Green
} else {
    Write-Host " [1/4] venv already exists - skipping." -ForegroundColor Gray
}

# Step 2: Create .venv as a directory junction pointing to venv
if (-not (Test-Path ".\.venv")) {
    Write-Host " [2/4] Creating .venv junction -> venv..." -ForegroundColor Yellow
    cmd /c mklink /J .venv venv
    Write-Host " [OK]  .venv junction created." -ForegroundColor Green
} else {
    Write-Host " [2/4] .venv already exists - skipping." -ForegroundColor Gray
}

# Step 3: Install requirements
Write-Host " [3/4] Installing dependencies from requirements.txt..." -ForegroundColor Yellow
& ".\venv\Scripts\pip" install -r requirements.txt

# Step 4: Copy Haar Cascade
Write-Host " [4/4] Fixing Haar Cascade XML..." -ForegroundColor Yellow
& ".\venv\Scripts\python" -c "import cv2, shutil, os; src = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'; os.makedirs('data/haarcascades', exist_ok=True); shutil.copy(src, 'data/haarcascades/haarcascade_frontalface_default.xml'); print('Cascade OK')"

Write-Host ""
Write-Host " ============================================" -ForegroundColor Green
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host " ============================================" -ForegroundColor Green
Write-Host ""
Write-Host " Activate environment:" -ForegroundColor White
Write-Host "   . .\activate.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Host " Start Flask:     python app.py" -ForegroundColor White
Write-Host " Start Streamlit: streamlit run dashboard.py" -ForegroundColor White
Write-Host ""
