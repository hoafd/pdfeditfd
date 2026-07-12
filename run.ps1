# run.ps1 — Khoi dong PDF Editor Pro
# Chay: powershell -ExecutionPolicy Bypass -File run.ps1

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

function Write-Err($msg) { Write-Host "[X] $msg" -ForegroundColor Red }

# Kiem tra venv
$pythonExe = Join-Path $ProjectDir "venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    Write-Err "Chua tim thay venv. Vui long chay setup.ps1 truoc!"
    Read-Host "Nhan Enter de dong..."; exit 1
}

# Kiem tra thu vien chinh
& $pythonExe -c "import fitz, PIL, cv2" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Err "Thieu thu vien. Vui long chay setup.ps1 truoc!"
    Read-Host "Nhan Enter de dong..."; exit 1
}

# Thiet lap duong dan cong cu
$TesseractPath = Join-Path $ProjectDir "tools\Tesseract-OCR"
$PopplerPath   = Join-Path $ProjectDir "tools\poppler\Library\bin"
$env:TESSDATA_PREFIX = Join-Path $TesseractPath "tessdata"

$env:PATH = "$TesseractPath;$PopplerPath;$env:PATH"

# Khoi dong ung dung (an cua so console)
Write-Host "Dang khoi dong PDF Editor..." -ForegroundColor Cyan
& $pythonExe main.py $args
