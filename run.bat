@echo off
chcp 65001 >nul
setlocal

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ============================================================
    echo   Python is not installed or not in PATH!
    echo   Please run 'setup.bat' first to install Python automatically.
    echo ============================================================
    pause
    exit /b 1
)

REM Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo ============================================================
    echo   Virtual environment not found!
    echo   Please run 'setup.bat' first to install all dependencies.
    echo ============================================================
    pause
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Check critical packages
python -c "import fitz, PIL, cv2" 2>nul
if errorlevel 1 (
    echo ============================================================
    echo   ERROR: Missing required libraries!
    echo   Please run 'setup.bat' first to install all dependencies.
    echo ============================================================
    pause
    exit /b 1
)

REM Set bundled tool paths
set "TESSERACT_PATH=%PROJECT_DIR%tools\Tesseract-OCR"
set "POPPLER_PATH=%PROJECT_DIR%tools\poppler\Library\bin"
set "TESSDATA_PREFIX=%TESSERACT_PATH%\tessdata"

REM Also add system Tesseract to PATH if exists
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
    set "PATH=C:\Program Files\Tesseract-OCR;%PATH%"
)

REM Add bundled tools to PATH
set "PATH=%TESSERACT_PATH%;%POPPLER_PATH%;%PATH%"

REM Launch the application
python main.py %*

endlocal
