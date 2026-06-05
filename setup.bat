@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================
echo   PDF Editor Pro - Setup Script
echo   Setting up offline environment...
echo ============================================
echo.

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

REM ========== 1. Create Python Virtual Environment ==========
echo [1/5] Creating Python virtual environment...
if not exist "venv" (
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        echo        Make sure Python 3.10+ is installed and in PATH.
        pause
        exit /b 1
    )
    echo       Virtual environment created successfully.
) else (
    echo       Virtual environment already exists. Skipping.
)
echo.

REM ========== 2. Activate venv and install packages ==========
echo [2/5] Installing Python packages...
call venv\Scripts\activate.bat

python -m pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install some packages. Check internet connection.
    pause
    exit /b 1
)
pip install psutil >nul 2>&1
echo       Python packages installed successfully.
echo.

REM ========== 3. Tesseract OCR ==========
echo [3/5] Setting up Tesseract OCR...
mkdir "tools\Tesseract-OCR" 2>nul

REM Check if system Tesseract exists
set "SYSTEM_TESS="
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
    set "SYSTEM_TESS=C:\Program Files\Tesseract-OCR\tesseract.exe"
)
if exist "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe" (
    set "SYSTEM_TESS=C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
)

if defined SYSTEM_TESS (
    echo       [AUTO] Tesseract he thong da duoc phat hien!
    echo       Duong dan: !SYSTEM_TESS!
    echo       Ung dung se tu dong su dung ban nay ^(uu tien^).
    echo       Bo qua tai Tesseract noi bo.
) else (
    if exist "tools\Tesseract-OCR\tesseract.exe" (
        echo       Tesseract OCR ^(bundled^) already installed. Skipping.
    ) else (
        echo       Downloading Tesseract OCR...
        REM Try GitHub release first
        powershell -Command "& {$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri 'https://github.com/UB-Mannheim/tesseract/releases/download/v5.5.0.20241111/tesseract-ocr-w64-setup-5.5.0.20241111.exe' -OutFile 'tools\tesseract_setup.exe' -UseBasicParsing } catch { Write-Host 'Download failed.' }}"

        if exist "tools\tesseract_setup.exe" (
            echo       Installing Tesseract OCR...
            tools\tesseract_setup.exe /S /D=%PROJECT_DIR%tools\Tesseract-OCR
            timeout /t 20 /nobreak >nul
            del "tools\tesseract_setup.exe" 2>nul

            if exist "tools\Tesseract-OCR\tesseract.exe" (
                echo       Tesseract OCR installed successfully.
            ) else (
                echo WARNING: Tesseract install failed.
                echo          Option 1: Install manually from https://github.com/UB-Mannheim/tesseract/wiki
                echo          Option 2: The app will auto-detect system Tesseract at C:\Program Files\Tesseract-OCR
            )
        ) else (
            echo WARNING: Could not download Tesseract OCR.
            echo          Option 1: Install manually from https://github.com/UB-Mannheim/tesseract/wiki
            echo          Option 2: The app will auto-detect system Tesseract at C:\Program Files\Tesseract-OCR
        )
    )
)
echo.

REM ========== 4. Vietnamese language data ==========
echo [4/5] Setting up OCR language data...

REM Determine tessdata directory
set "TESSDATA_DIR="
if defined SYSTEM_TESS (
    for %%F in ("!SYSTEM_TESS!") do set "TESS_PARENT=%%~dpF"
    set "TESSDATA_DIR=!TESS_PARENT!tessdata"
)
if not defined TESSDATA_DIR (
    set "TESSDATA_DIR=%PROJECT_DIR%tools\Tesseract-OCR\tessdata"
)
mkdir "!TESSDATA_DIR!" 2>nul

REM Check Vietnamese
if exist "!TESSDATA_DIR!\vie.traineddata" (
    echo       Vietnamese language data already exists. OK.
) else (
    echo       Downloading Vietnamese language data...
    powershell -Command "& {$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri 'https://github.com/tesseract-ocr/tessdata/raw/main/vie.traineddata' -OutFile '!TESSDATA_DIR!\vie.traineddata' -UseBasicParsing } catch { Write-Host 'Download failed.' }}"
    if exist "!TESSDATA_DIR!\vie.traineddata" (
        echo       Vietnamese language data installed.
    ) else (
        echo WARNING: Could not download vie.traineddata.
        echo          Download manually: https://github.com/tesseract-ocr/tessdata/raw/main/vie.traineddata
        echo          Place in: !TESSDATA_DIR!
    )
)

REM Check English
if exist "!TESSDATA_DIR!\eng.traineddata" (
    echo       English language data already exists. OK.
) else (
    echo       Downloading English language data...
    powershell -Command "& {$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri 'https://github.com/tesseract-ocr/tessdata/raw/main/eng.traineddata' -OutFile '!TESSDATA_DIR!\eng.traineddata' -UseBasicParsing } catch { Write-Host 'Download failed.' }}"
    if exist "!TESSDATA_DIR!\eng.traineddata" (
        echo       English language data installed.
    ) else (
        echo WARNING: Could not download eng.traineddata.
    )
)
echo.

REM ========== 5. Poppler ==========
echo [5/5] Setting up Poppler...
if exist "tools\poppler\Library\bin\pdftoppm.exe" (
    echo       Poppler already installed. Skipping.
) else (
    echo       Downloading Poppler...
    mkdir "tools\poppler" 2>nul

    powershell -Command "& {$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri 'https://github.com/oschwartz10612/poppler-windows/releases/download/v24.08.0-0/Release-24.08.0-0.zip' -OutFile 'tools\poppler.zip' -UseBasicParsing } catch { Write-Host 'Download failed.' }}"

    if exist "tools\poppler.zip" (
        echo       Extracting Poppler...

        REM Try tar first (built-in on Windows 10+), then PowerShell
        tar -xf "tools\poppler.zip" -C "tools\poppler_temp" 2>nul
        if errorlevel 1 (
            powershell -Command "& {Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory('tools\poppler.zip', 'tools\poppler_temp')}" 2>nul
        )

        REM Move contents from subdirectory
        if exist "tools\poppler_temp\poppler-24.08.0" (
            xcopy "tools\poppler_temp\poppler-24.08.0\*" "tools\poppler\" /E /I /Y >nul
        ) else (
            REM Try any subdirectory
            for /d %%D in ("tools\poppler_temp\*") do (
                xcopy "%%D\*" "tools\poppler\" /E /I /Y >nul
            )
        )

        rmdir /s /q "tools\poppler_temp" 2>nul
        del "tools\poppler.zip" 2>nul

        if exist "tools\poppler\Library\bin\pdftoppm.exe" (
            echo       Poppler installed successfully.
        ) else (
            echo WARNING: Poppler extraction may have failed.
            echo          PDF-to-image features may not work.
        )
    ) else (
        echo WARNING: Could not download Poppler.
        echo          PDF-to-image conversion may not work.
    )
)
echo.

echo ============================================
echo   Setup Complete!
echo   Run 'run.bat' to start the PDF Editor.
echo ============================================
echo.
pause
