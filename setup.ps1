# setup.ps1 — Cài đặt môi trường PDF Editor Pro
# Chạy: powershell -ExecutionPolicy Bypass -File setup.ps1

$ErrorActionPreference = "Continue"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

function Write-Step($step, $msg) { Write-Host "`n[$step] $msg" -ForegroundColor Cyan }
function Write-OK($msg)          { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg)        { Write-Host "  [!]  $msg" -ForegroundColor Yellow }
function Write-Err($msg)         { Write-Host "  [X]  $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "============================================" -ForegroundColor Magenta
Write-Host "   PDF Editor Pro - Cai dat moi truong      " -ForegroundColor Magenta
Write-Host "============================================" -ForegroundColor Magenta

# ── 1. Kiem tra Python ──────────────────────────────────────────────────────
Write-Step "1/5" "Kiem tra Python..."
try {
    $pyVer = python --version 2>&1
    Write-OK "Da cai: $pyVer"
} catch {
    Write-Warn "Python chua duoc cai. Dang tai Python 3.11..."
    $pySetup = Join-Path $ProjectDir "python_setup.exe"
    Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe" `
        -OutFile $pySetup -UseBasicParsing
    if (Test-Path $pySetup) {
        Start-Process $pySetup -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0" -Wait
        Remove-Item $pySetup -Force
        Write-OK "Python da duoc cai dat."
        Write-Warn "Vui long DONG cua so nay va chay lai setup.ps1!"
        pause; exit 1
    } else {
        Write-Err "Khong the tai Python. Vui long cai thu cong."; pause; exit 1
    }
}

# ── 2. Tao Virtual Environment ──────────────────────────────────────────────
Write-Step "2/5" "Tao Python Virtual Environment..."
if (-not (Test-Path "venv\Scripts\activate.ps1")) {
    python -m venv venv
    if ($LASTEXITCODE -ne 0) { Write-Err "Khong the tao venv."; pause; exit 1 }
    Write-OK "Venv da tao thanh cong."
} else {
    Write-OK "Venv da ton tai. Bo qua."
}

# Kich hoat venv
& ".\venv\Scripts\Activate.ps1"

Write-Host "`n  Cai dat Python packages..." -ForegroundColor Cyan
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Err "Cai dat goi that bai. Kiem tra ket noi mang."; pause; exit 1 }
pip install psutil tkinterdnd2 --quiet
Write-OK "Tat ca Python packages da duoc cai dat."

# ── 3. Tesseract OCR ────────────────────────────────────────────────────────
Write-Step "3/5" "Cai dat Tesseract OCR..."

if (Test-Path "tools\Tesseract-OCR\tesseract.exe") {
    Write-OK "Tesseract (noi bo) da co san."
    $TessDir = "$ProjectDir\tools\Tesseract-OCR"
} else {
    Write-Warn "Dang tai Tesseract OCR..."
    New-Item -ItemType Directory -Path "tools\Tesseract-OCR" -Force | Out-Null
    $tessSetup = Join-Path $ProjectDir "tools\tesseract_setup.exe"

    if (-not (Test-Path $tessSetup)) {
        # ... logic tai file ...
        $downloadUrl = $null
        try {
            $releases = Invoke-RestMethod -Uri "https://api.github.com/repos/tesseract-ocr/tesseract/releases" -UseBasicParsing
            foreach ($rel in $releases) {
                $asset = $rel.assets | Where-Object { $_.name -like "*w64-setup*.exe" } | Select-Object -First 1
                if ($asset) { $downloadUrl = $asset.browser_download_url; break }
            }
            if (-not $downloadUrl) {
                $releases = Invoke-RestMethod -Uri "https://api.github.com/repos/UB-Mannheim/tesseract/releases" -UseBasicParsing
                foreach ($rel in $releases) {
                    $asset = $rel.assets | Where-Object { $_.name -like "*w64-setup*.exe" } | Select-Object -First 1
                    if ($asset) { $downloadUrl = $asset.browser_download_url; break }
                }
            }
        } catch {}

        if (-not $downloadUrl) {
            Write-Warn "  Khong the tu dong tim thay link tai. Vui long cai thu cong."
            exit 1
        }
        
        # Kiem tra xem he thong da cai Tesseract chua
        $sysTess = "C:\Program Files\Tesseract-OCR\tesseract.exe"
        if (Test-Path $sysTess) {
            Write-Warn "  Phat hien Tesseract o he thong. Tien hanh copy vao thu muc noi bo (tools) de lam Portable..."
            Copy-Item -Path "C:\Program Files\Tesseract-OCR\*" -Destination "tools\Tesseract-OCR\" -Recurse -Force
        } else {
            Write-Warn "  Tim thay link tai chinh xac: $downloadUrl"
            try { Invoke-WebRequest -Uri $downloadUrl -OutFile $tessSetup -UseBasicParsing } catch {}
        }
    }

    if (Test-Path $tessSetup) {
        Write-Warn "  Dang cai dat Tesseract (co the mat 30 giay)..."
        $installDir = Join-Path $ProjectDir "tools\Tesseract-OCR"
        cmd /c "`"$tessSetup`" /S /D=$installDir" 2>$null
        Start-Sleep 15
        Remove-Item $tessSetup -Force -ErrorAction SilentlyContinue
        
        # NSIS installer bug: Neu da tung cai Tesseract, no se phot lo /D va cai vao C:\Program Files
        # Ta kiem tra va copy neu no bi the
        if (-not (Test-Path "tools\Tesseract-OCR\tesseract.exe") -and (Test-Path "C:\Program Files\Tesseract-OCR\tesseract.exe")) {
            Write-Warn "  Installer da tu dong cai vao he thong thay vi noi bo. Tien hanh copy sang noi bo..."
            Copy-Item -Path "C:\Program Files\Tesseract-OCR\*" -Destination "tools\Tesseract-OCR\" -Recurse -Force
        }
    }

    if (Test-Path "tools\Tesseract-OCR\tesseract.exe") {
        Write-OK "Tesseract da cai thanh cong."
    } else {
        Write-Warn "Cai Tesseract that bai. Vui long cai thu cong:"
        Write-Warn "  Truy cap: https://github.com/UB-Mannheim/tesseract/wiki"
        Write-Warn "  Tai file: tesseract-ocr-w64-setup-*.exe"
        Write-Warn "  Cai vao:  $ProjectDir\tools\Tesseract-OCR"
    }
    $TessDir = "$ProjectDir\tools\Tesseract-OCR"
}



# ── 4. Tessdata (vie + eng) ─────────────────────────────────────────────────
Write-Step "4/5" "Cai dat du lieu ngon ngu OCR..."
$TessData = "$ProjectDir\tools\Tesseract-OCR\tessdata"
New-Item -ItemType Directory -Path $TessData -Force | Out-Null

foreach ($lang in @("vie", "eng")) {
    $td = Join-Path $TessData "$lang.traineddata"
    if (Test-Path $td) {
        Write-OK "Ngon ngu '$lang' da co."
    } else {
        Write-Warn "Dang tai '$lang.traineddata'..."
        try {
            Invoke-WebRequest -Uri "https://github.com/tesseract-ocr/tessdata/raw/main/$lang.traineddata" `
                -OutFile $td -UseBasicParsing
            Write-OK "Da tai '$lang.traineddata'."
        } catch {
            Write-Warn "Khong tai duoc '$lang.traineddata'. Tai thu cong: https://github.com/tesseract-ocr/tessdata"
        }
    }
}

# ── 5. Poppler ──────────────────────────────────────────────────────────────
Write-Step "5/5" "Cai dat Poppler..."
if (Test-Path "tools\poppler\Library\bin\pdftoppm.exe") {
    Write-OK "Poppler da co san."
} else {
    Write-Warn "Dang tai Poppler..."
    New-Item -ItemType Directory -Path "tools\poppler" -Force | Out-Null
    try {
        Invoke-WebRequest -Uri "https://github.com/oschwartz10612/poppler-windows/releases/download/v24.08.0-0/Release-24.08.0-0.zip" `
            -OutFile "tools\poppler.zip" -UseBasicParsing
        Expand-Archive -Path "tools\poppler.zip" -DestinationPath "tools\poppler_temp" -Force
        $sub = Get-ChildItem "tools\poppler_temp" -Directory | Select-Object -First 1
        if ($sub) { Copy-Item "$($sub.FullName)\*" "tools\poppler\" -Recurse -Force }
        Remove-Item "tools\poppler_temp", "tools\poppler.zip" -Recurse -Force -ErrorAction SilentlyContinue
        if (Test-Path "tools\poppler\Library\bin\pdftoppm.exe") { Write-OK "Poppler da cai." }
        else { Write-Warn "Giai nen Poppler co the that bai." }
    } catch {
        Write-Warn "Khong tai duoc Poppler."
    }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "   Cai dat hoan tat!                        " -ForegroundColor Green
Write-Host "   Chay: .\run.ps1 de khoi dong ung dung.  " -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Read-Host "Nhan Enter de dong..."
