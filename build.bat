@echo off
REM ╔══════════════════════════════════════════════════════╗
REM ║  PDF Editor Pro - Build All-in-One EXE               ║
REM ║  Creates a single portable executable                 ║
REM ╚══════════════════════════════════════════════════════╝

echo.
echo ===================================================
echo   Building PDF Editor Pro - Standalone EXE
echo ===================================================
echo.

cd /d "%~dp0"

REM Check venv
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found.
    echo Please run setup.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

REM Install PyInstaller if needed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [*] Installing PyInstaller...
    pip install pyinstaller
)

echo.
echo [*] Building executable...
echo     This may take a few minutes...
echo.

REM Build the exe with PyInstaller
pyinstaller ^
    --onedir ^
    --windowed ^
    --name "PDFEditorPro" ^
    --icon "assets\icon.ico" ^
    --add-data "assets;assets" ^
    --add-data "tools\Tesseract-OCR;tools\Tesseract-OCR" ^
    --add-data "tools\poppler;tools\poppler" ^
    --hidden-import "PIL" ^
    --hidden-import "PIL._tkinter_finder" ^
    --hidden-import "customtkinter" ^
    --hidden-import "cv2" ^
    --hidden-import "pytesseract" ^
    --hidden-import "pikepdf" ^
    --hidden-import "fitz" ^
    --hidden-import "fitz.fitz" ^
    --hidden-import "reportlab" ^
    --hidden-import "lxml" ^
    --hidden-import "pdf2image" ^
    --hidden-import "numpy" ^
    --collect-all "customtkinter" ^
    --collect-all "fitz" ^
    --noconfirm ^
    --clean ^
    main.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed!
    echo.
    echo Try the alternative build method:
    echo   build_exe.py
    pause
    exit /b 1
)

echo.
echo [*] Zipping distribution folder...
python -c "import shutil; shutil.make_archive('dist/PDFEditorPro_Portable', 'zip', 'dist', 'PDFEditorPro')"

echo.
echo ===================================================
echo   BUILD SUCCESSFUL!
echo ===================================================
echo.
echo   Output Directory: dist\PDFEditorPro
echo   Zipped Package: dist\PDFEditorPro_Portable.zip
echo.
echo   To distribute, share the zip file.
echo.
echo   The folder includes Tesseract OCR and Poppler.
echo ===================================================
echo.
pause
