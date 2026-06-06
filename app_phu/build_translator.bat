@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo DONG GOI SCREEN TRANSLATOR (Nhanh)
echo ==========================================

REM Check if venv exists
set "VENV_DIR=..\venv"
if not exist "%VENV_DIR%" (
    echo [Loi] Khong tim thay moi truong venv. Hay mo Launcher de cai dat moi truong truoc!
    pause
    exit /b 1
)

set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

REM Install PyInstaller if missing
"%PYTHON_EXE%" -m pip install --progress-bar off pyinstaller deep-translator
if errorlevel 1 (
    echo [Loi] Khong the cai dat thu vien.
    exit /b 1
)

echo.
echo Dang dong goi Launcher cho Screen Translator...

REM Compile the lightweight launcher, NOT the whole script
"%PYTHON_EXE%" -m PyInstaller --noconfirm --onefile --windowed --name "Screen_Translator" --icon=NONE "translator_launcher.py"

if errorlevel 1 (
    echo.
    echo [Loi] Dong goi that bai.
    exit /b 1
)

echo.
echo HOAN THANH!
echo File chay Screen_Translator nam trong thu muc: dist\Screen_Translator.exe
echo Phan mem se dung chung thu vien cua thu muc cha de toi uu dung luong.
