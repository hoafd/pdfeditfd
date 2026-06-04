@echo off
chcp 65001 >nul
setlocal

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Set tool paths
set "TESSERACT_PATH=%PROJECT_DIR%tools\Tesseract-OCR"
set "POPPLER_PATH=%PROJECT_DIR%tools\poppler\Library\bin"
set "TESSDATA_PREFIX=%TESSERACT_PATH%\tessdata"

REM Add tools to PATH for this session only
set "PATH=%TESSERACT_PATH%;%POPPLER_PATH%;%PATH%"

REM Launch the application
python main.py %*

endlocal
