@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================
echo   PDF Editor - Setup Script
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
        echo ERROR: Failed to create virtual environment. Make sure Python 3.12+ is installed.
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
    echo ERROR: Failed to install some packages. Check your internet connection.
    pause
    exit /b 1
)
echo       Python packages installed successfully.
echo.

REM ========== 3. Download Tesseract OCR ==========
echo [3/5] Setting up Tesseract OCR...
if not exist "tools\Tesseract-OCR\tesseract.exe" (
    echo       Downloading Tesseract OCR...
    mkdir "tools\Tesseract-OCR" 2>nul
    
    REM Download Tesseract installer using PowerShell
    powershell -Command "& {$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri 'https://github.com/UB-Mannheim/tesseract/releases/download/v5.5.0.20241111/tesseract-ocr-w64-setup-5.5.0.20241111.exe' -OutFile 'tools\tesseract_setup.exe' -UseBasicParsing } catch { Write-Host 'Download failed, trying alternative...'; Invoke-WebRequest -Uri 'https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.5.0.20241111.exe' -OutFile 'tools\tesseract_setup.exe' -UseBasicParsing }}"
    
    if exist "tools\tesseract_setup.exe" (
        echo       Installing Tesseract OCR to tools\Tesseract-OCR...
        tools\tesseract_setup.exe /S /D=%PROJECT_DIR%tools\Tesseract-OCR
        
        REM Wait for installation
        timeout /t 15 /nobreak >nul
        
        REM Cleanup installer
        del "tools\tesseract_setup.exe" 2>nul
        
        if exist "tools\Tesseract-OCR\tesseract.exe" (
            echo       Tesseract OCR installed successfully.
        ) else (
            echo WARNING: Tesseract may not have installed correctly.
            echo          Please manually install Tesseract to: %PROJECT_DIR%tools\Tesseract-OCR\
            echo          Download from: https://github.com/UB-Mannheim/tesseract/wiki
        )
    ) else (
        echo WARNING: Could not download Tesseract OCR.
        echo          Please manually install Tesseract to: %PROJECT_DIR%tools\Tesseract-OCR\
        echo          Download from: https://github.com/UB-Mannheim/tesseract/wiki
    )
) else (
    echo       Tesseract OCR already installed. Skipping.
)
echo.

REM ========== 4. Download Vietnamese language data ==========
echo [4/5] Setting up OCR language data...
if not exist "tools\Tesseract-OCR\tessdata\vie.traineddata" (
    echo       Downloading Vietnamese language data...
    powershell -Command "& {$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri 'https://github.com/tesseract-ocr/tessdata/raw/main/vie.traineddata' -OutFile 'tools\Tesseract-OCR\tessdata\vie.traineddata' -UseBasicParsing } catch { Write-Host 'WARNING: Could not download Vietnamese language data.' }}"
    if exist "tools\Tesseract-OCR\tessdata\vie.traineddata" (
        echo       Vietnamese language data installed.
    ) else (
        echo WARNING: Could not download Vietnamese language data.
    )
) else (
    echo       Vietnamese language data already exists. Skipping.
)
echo.

REM ========== 5. Download Poppler ==========
echo [5/5] Setting up Poppler...
if not exist "tools\poppler\Library\bin\pdftoppm.exe" (
    echo       Downloading Poppler...
    powershell -Command "& {$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri 'https://github.com/oschwartz10612/poppler-windows/releases/download/v24.08.0-0/Release-24.08.0-0.zip' -OutFile 'tools\poppler.zip' -UseBasicParsing } catch { Write-Host 'Download failed' }}"
    
    if exist "tools\poppler.zip" (
        echo       Extracting Poppler...
        powershell -Command "Expand-Archive -Path 'tools\poppler.zip' -DestinationPath 'tools\poppler_temp' -Force"
        
        REM Move contents (the zip has a subdirectory)
        if exist "tools\poppler_temp\poppler-24.08.0" (
            xcopy "tools\poppler_temp\poppler-24.08.0\*" "tools\poppler\" /E /I /Y >nul
        ) else (
            xcopy "tools\poppler_temp\*" "tools\poppler\" /E /I /Y >nul
        )
        
        REM Cleanup
        rmdir /s /q "tools\poppler_temp" 2>nul
        del "tools\poppler.zip" 2>nul
        
        echo       Poppler installed successfully.
    ) else (
        echo WARNING: Could not download Poppler.
        echo          PDF to image conversion may not work.
    )
) else (
    echo       Poppler already installed. Skipping.
)
echo.

REM ========== Create output and temp directories ==========
mkdir output 2>nul
mkdir temp 2>nul

echo ============================================
echo   Setup Complete!
echo   Run 'run.bat' to start the PDF Editor.
echo ============================================
echo.
pause
