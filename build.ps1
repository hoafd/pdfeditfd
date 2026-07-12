# build.ps1 — Dong goi PDF Editor Pro thanh EXE portable
# Gom ca: dong goi chinh (PDFEditorPro) + dong goi launcher (PDF_Editor_Launcher)
# Chay: powershell -ExecutionPolicy Bypass -File build.ps1

$ErrorActionPreference = "Continue"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

function Write-Step($step, $msg) { Write-Host "`n[$step] $msg" -ForegroundColor Cyan }
function Write-OK($msg)          { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg)        { Write-Host "  [!]  $msg" -ForegroundColor Yellow }
function Write-Err($msg)         { Write-Host "  [X]  $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "====================================================" -ForegroundColor Magenta
Write-Host "   PDF Editor Pro - Dong goi EXE Portable           " -ForegroundColor Magenta
Write-Host "====================================================" -ForegroundColor Magenta

# ── Kiem tra venv ────────────────────────────────────────────────────────────
Write-Step "1/5" "Kiem tra moi truong..."
$pythonExe = Join-Path $ProjectDir "venv\Scripts\python.exe"
$pipExe    = Join-Path $ProjectDir "venv\Scripts\pip.exe"
if (-not (Test-Path $pythonExe)) {
    Write-Err "Chua tim thay venv. Vui long chay setup.ps1 truoc!"; Read-Host; exit 1
}
Write-OK "Venv OK."

# ── Kiem tra cong cu Tesseract & Poppler (bat buoc de dong goi portable) ────
Write-Step "2/5" "Kiem tra cong cu can thiet (Tesseract, Poppler)..."

if (-not (Test-Path "tools\Tesseract-OCR\tesseract.exe")) {
    Write-Err "Khong the tim thay Tesseract (noi bo) de dong goi."
    Write-Err "Vui long chay file setup.ps1 de cai dat Tesseract truoc khi build!"
    exit 1
}
foreach ($lang in @("vie","eng")) {
    $td = "tools\Tesseract-OCR\tessdata\$lang.traineddata"
    if (-not (Test-Path $td)) {
        Write-Warn "Dang tai tessdata/$lang..."
        New-Item -ItemType Directory -Path "tools\Tesseract-OCR\tessdata" -Force | Out-Null
        Invoke-WebRequest -Uri "https://github.com/tesseract-ocr/tessdata/raw/main/$lang.traineddata" `
            -OutFile $td -UseBasicParsing
    }
}

if (-not (Test-Path "tools\poppler\Library\bin\pdftoppm.exe")) {
    Write-Warn "Poppler chua co. Dang tai..."
    New-Item -ItemType Directory -Path "tools\poppler" -Force | Out-Null
    Invoke-WebRequest -Uri "https://github.com/oschwartz10612/poppler-windows/releases/download/v24.08.0-0/Release-24.08.0-0.zip" `
        -OutFile "tools\poppler.zip" -UseBasicParsing
    if (Test-Path "tools\poppler.zip") {
        Expand-Archive "tools\poppler.zip" "tools\poppler_temp" -Force
        $sub = Get-ChildItem "tools\poppler_temp" -Directory | Select-Object -First 1
        if ($sub) { Copy-Item "$($sub.FullName)\*" "tools\poppler\" -Recurse -Force }
        Remove-Item "tools\poppler_temp","tools\poppler.zip" -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$missingTools = @()
if (-not (Test-Path "tools\Tesseract-OCR\tesseract.exe")) { $missingTools += "Tesseract" }
if (-not (Test-Path "tools\poppler\Library\bin\pdftoppm.exe")) { $missingTools += "Poppler" }
if ($missingTools.Count -gt 0) {
    Write-Err "Thieu cong cu: $($missingTools -join ', '). Khong the dong goi portable."
    Read-Host; exit 1
}
Write-OK "Tesseract OK  |  Poppler OK"

# ── Cai PyInstaller ─────────────────────────────────────────────────────────
Write-Step "3/5" "Kiem tra PyInstaller..."
& $pipExe show pyinstaller --quiet 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Warn "Dang cai PyInstaller..."
    & $pipExe install pyinstaller --quiet
}
Write-OK "PyInstaller san sang."

# ── Build chinh: PDFEditorPro ────────────────────────────────────────────────
Write-Step "4/5" "Dong goi PDFEditorPro (main.py)..."
$pyInstaller = Join-Path $ProjectDir "venv\Scripts\pyinstaller.exe"
& $pyInstaller `
    --onedir --windowed `
    --name "PDFEditorPro" `
    --icon "assets\icon.ico" `
    --add-data "assets;assets" `
    --hidden-import "PIL" `
    --hidden-import "PIL._tkinter_finder" `
    --hidden-import "customtkinter" `
    --hidden-import "cv2" `
    --hidden-import "pytesseract" `
    --hidden-import "pikepdf" `
    --hidden-import "fitz" `
    --hidden-import "fitz.fitz" `
    --hidden-import "reportlab" `
    --hidden-import "lxml" `
    --hidden-import "pdf2image" `
    --hidden-import "numpy" `
    --hidden-import "paddle" `
    --hidden-import "paddleocr" `
    --hidden-import "setuptools" `
    --collect-all "customtkinter" `
    --collect-all "fitz" `
    --collect-all "paddle" `
    --collect-all "paddleocr" `
    --collect-all "Cython" `
    --collect-all "skimage" `
    --collect-all "scipy" `
    --collect-all "shapely" `
    --collect-all "setuptools" `
    --noconfirm --clean `
    main.py

if ($LASTEXITCODE -ne 0) {
    Write-Err "Dong goi PDFEditorPro that bai!"; Read-Host; exit 1
}

# ── Copy thu muc tools ben canh file exe ─────────────────────────────────────
Write-Step "5/5" "Copy thu muc tools ben canh file EXE..."
Copy-Item -Path "tools" -Destination "dist\PDFEditorPro\tools" -Recurse -Force
Write-OK "PDFEditorPro da dong goi cung voi thu muc tools -> dist\PDFEditorPro\"

# ── Nen thanh ZIP ────────────────────────────────────────────────────────────
Write-Host "`n  Nen thu muc dist\PDFEditorPro thanh ZIP..." -ForegroundColor Cyan
& $pythonExe -c "import shutil; shutil.make_archive('dist/PDFEditorPro_Portable', 'zip', 'dist', 'PDFEditorPro')"
if (Test-Path "dist\PDFEditorPro_Portable.zip") { Write-OK "dist\PDFEditorPro_Portable.zip" }

Write-Host ""
Write-Host "====================================================" -ForegroundColor Green
Write-Host "   DONG GOI HOAN THANH!                             " -ForegroundColor Green
Write-Host "   - Portable app : dist\PDFEditorPro\              " -ForegroundColor Green
Write-Host "   - ZIP portable : dist\PDFEditorPro_Portable.zip  " -ForegroundColor Green
Write-Host "====================================================" -ForegroundColor Green
Write-Host ""
Read-Host "Nhan Enter de dong..."
