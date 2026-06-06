REM echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo DONG GOI SCREEN TRANSLATOR
echo ==========================================

REM Check if venv exists
set "VENV_DIR=..\venv"
if not exist "%VENV_DIR%" (
    echo [Loi] Khong tim thay moi truong venv. Hay mo Launcher de cai dat moi truong truoc!
    
    exit /b 1
)

set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "PIP_EXE=%VENV_DIR%\Scripts\pip.exe"

REM Ensure pyinstaller and deep-translator are installed
"%PYTHON_EXE%" -m pip install --progress-bar off pyinstaller deep-translator
if errorlevel 1 (
    echo [Loi] Khong the cai dat thu vien.
    
    exit /b 1
)

echo.
echo Dang dong goi Screen Translator...

"%PYTHON_EXE%" -m PyInstaller --noconfirm --onedir --windowed --name "Screen_Translator" --icon=NONE "screen_translator.py"

if errorlevel 1 (
    echo.
    echo [Loi] Dong goi that bai.
    
    exit /b 1
)

echo.
echo HOAN THANH!
echo File chay Launcher nam trong thu muc: dist\Screen_Translator\Screen_Translator.exe
echo Hay tao shortcut cua file do ra man hinh Desktop nhe!



