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

REM Check if tools exist for packaging
call venv\Scripts\activate.bat
echo [*] Kiểm tra thư viện nhúng (Portable Tools)...

if not exist "tools\Tesseract-OCR\tesseract.exe" (
    echo.
    echo [*] Đang tải Tesseract OCR nội bộ (Bắt buộc để đóng gói Portable)...
    mkdir "tools\Tesseract-OCR" 2>nul
    powershell -Command "& {$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri 'https://github.com/UB-Mannheim/tesseract/releases/download/v5.5.0.20241111/tesseract-ocr-w64-setup-5.5.0.20241111.exe' -OutFile 'tools\tesseract_setup.exe' -UseBasicParsing } catch { Write-Host 'Download failed.' }}"
    
    if exist "tools\tesseract_setup.exe" (
        tools\tesseract_setup.exe /S /D=%~dp0tools\Tesseract-OCR
        timeout /t 20 /nobreak >nul
        del "tools\tesseract_setup.exe" 2>nul
    )
)

if not exist "tools\Tesseract-OCR\tessdata\vie.traineddata" (
    echo [*] Đang tải gói ngôn ngữ Tiếng Việt...
    mkdir "tools\Tesseract-OCR\tessdata" 2>nul
    powershell -Command "& {$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri 'https://github.com/tesseract-ocr/tessdata/raw/main/vie.traineddata' -OutFile 'tools\Tesseract-OCR\tessdata\vie.traineddata' -UseBasicParsing } catch { Write-Host 'Download failed.' }}"
)
if not exist "tools\Tesseract-OCR\tessdata\eng.traineddata" (
    echo [*] Đang tải gói ngôn ngữ Tiếng Anh...
    mkdir "tools\Tesseract-OCR\tessdata" 2>nul
    powershell -Command "& {$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri 'https://github.com/tesseract-ocr/tessdata/raw/main/eng.traineddata' -OutFile 'tools\Tesseract-OCR\tessdata\eng.traineddata' -UseBasicParsing } catch { Write-Host 'Download failed.' }}"
)

if not exist "tools\poppler\Library\bin\pdftoppm.exe" (
    echo [*] Đang tải Poppler nội bộ...
    mkdir "tools\poppler" 2>nul
    powershell -Command "& {$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri 'https://github.com/oschwartz10612/poppler-windows/releases/download/v24.08.0-0/Release-24.08.0-0.zip' -OutFile 'tools\poppler.zip' -UseBasicParsing } catch { Write-Host 'Download failed.' }}"
    if exist "tools\poppler.zip" (
        tar -xf "tools\poppler.zip" -C "tools\poppler_temp" 2>nul
        if errorlevel 1 (
            powershell -Command "& {Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory('tools\poppler.zip', 'tools\poppler_temp')}" 2>nul
        )
        if exist "tools\poppler_temp\poppler-24.08.0" (
            xcopy "tools\poppler_temp\poppler-24.08.0\*" "tools\poppler\" /E /I /Y >nul
        ) else (
            for /d %%D in ("tools\poppler_temp\*") do (
                xcopy "%%D\*" "tools\poppler\" /E /I /Y >nul
            )
        )
        rmdir /s /q "tools\poppler_temp" 2>nul
        del "tools\poppler.zip" 2>nul
    )
)

set "MISSING_TOOLS="
if not exist "tools\Tesseract-OCR\tesseract.exe" set "MISSING_TOOLS=1"
if not exist "tools\poppler\Library\bin\pdftoppm.exe" set "MISSING_TOOLS=1"

if defined MISSING_TOOLS (
    echo.
    echo [LỖI NGHIÊM TRỌNG] Quá trình tự động tải thất bại!
    echo Vui lòng kiểm tra kết nối mạng hoặc tải thủ công vào thư mục tools\
    pause
    exit /b 1
)

echo     - Tesseract OCR: OK
echo     - Poppler: OK
echo.
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
