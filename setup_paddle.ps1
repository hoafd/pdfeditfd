# ============================================
#    PDF Editor Pro - Cai dat PaddleOCR
# ============================================

$ProjectDir = $PSScriptRoot
$venv = Join-Path $ProjectDir "venv"
$pythonExe = Join-Path $venv "Scripts\python.exe"
$pipExe = Join-Path $venv "Scripts\pip.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Host "[X] Loi: Chua co Virtual Environment. Vui long chay setup.ps1 truoc!" -ForegroundColor Red
    Read-Host "Nhan Enter de dong..."
    exit 1
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Cai dat PaddleOCR (Ho tro Tieng Viet, toc do cao)" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Qua trinh nay se tai khoang 1GB du lieu (thu vien + AI models)." -ForegroundColor Yellow
Write-Host "Vui long cho doi trong giay lat..." -ForegroundColor Yellow
Write-Host ""

Write-Host "[1/2] Dang cai dat thu vien Python (paddlepaddle, paddleocr)..." -ForegroundColor Cyan
& $pipExe install "paddlepaddle<3.0.0" "paddleocr>=2.8.1,<3.0.0"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] Loi khi tai thu vien. Vui long kiem tra ket noi mang." -ForegroundColor Red
    Read-Host "Nhan Enter de dong..."
    exit 1
}

Write-Host ""
Write-Host "[2/2] Dang tai AI Models (chv4) vao thu muc tools\paddleocr..." -ForegroundColor Cyan
# Chay doan script Python de ep PaddleOCR tu dong tai model
$pyScript = @"
import sys, os
sys.path.append(r'$ProjectDir')
from src.ocr_engine import get_ocr_engine

print('Dang khoi tao PaddleOCR de kich hoat trinh tai model...')
engine = get_ocr_engine()
engine.set_engine('paddleocr')

# Goi them mot lan ham ocr de chac chan model duoc tai ve
reader = engine._get_paddle_reader()
if reader:
    import numpy as np
    reader.ocr(np.zeros((10, 10, 3), dtype=np.uint8), cls=False)
    print('[OK] Tai Model thanh cong!')
else:
    print('[X] Loi: Khong the khoi tao PaddleOCR reader.')
    sys.exit(1)
"@

& $pythonExe -c $pyScript

if ($LASTEXITCODE -eq 0) {
    # Fallback: Kiem tra neu model lo bi tai vao thu muc mac dinh cua he thong thay vi thu muc tools
    $defaultPaddleDir = Join-Path $env:USERPROFILE ".paddleocr\whl"
    $targetPaddleDir = Join-Path $ProjectDir "tools\paddleocr\whl"
    if (Test-Path $defaultPaddleDir) {
        Write-Host "Dang di chuyen file model tu thu muc he thong vao thu muc tools..." -ForegroundColor Yellow
        if (-not (Test-Path $targetPaddleDir)) {
            New-Item -ItemType Directory -Force -Path $targetPaddleDir | Out-Null
        }
        Copy-Item -Path "$defaultPaddleDir\*" -Destination $targetPaddleDir -Recurse -Force
        # Co the xoa thu muc mac dinh de tiet kiem dung luong
        # Remove-Item -Path $defaultPaddleDir -Recurse -Force
    }

    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host " CAI DAT PADDLEOCR HOAN TAT!" -ForegroundColor Green
    Write-Host " Thu muc AI models da duoc luu tai: tools\paddleocr" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[X] Co loi xay ra trong qua trinh tai AI Models." -ForegroundColor Red
}

Read-Host "Nhan Enter de dong..."
