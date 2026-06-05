@echo off
echo ==========================================
echo DONG GOI PDF EDITOR LAUNCHER
echo ==========================================

REM Kiem tra xem may da cai pyinstaller chua (Toan cau)
python -m pip install pyinstaller

echo Dang dong goi Launcher...
python -m PyInstaller --noconfirm --onefile --windowed --icon=NONE --name "PDF_Editor_Launcher" launcher.py

echo.
echo HOAN THANH!
echo File chay Launcher nam trong thu muc: dist\PDF_Editor_Launcher.exe
echo Hay copy file nay ra thu muc goc (ngang hang voi src, venv)


