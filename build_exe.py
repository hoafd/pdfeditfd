"""
Build script for creating a standalone PDF Editor Pro executable.

Usage:
    python build_exe.py          # Build onefile EXE
    python build_exe.py --dir    # Build directory-based (faster startup)
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()


def ensure_pyinstaller():
    """Install PyInstaller if not available."""
    try:
        import PyInstaller
        print(f"[OK] PyInstaller {PyInstaller.__version__} found")
    except ImportError:
        print("[*] Installing PyInstaller...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "pyinstaller"
        ])


def build(onefile=True):
    """Build the executable."""
    print("=" * 60)
    print("  PDF Editor Pro — Build System")
    print("=" * 60)
    print()

    ensure_pyinstaller()

    # Determine paths
    tesseract_dir = PROJECT_ROOT / "tools" / "Tesseract-OCR"
    poppler_dir = PROJECT_ROOT / "tools" / "poppler"

    # Base PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "PDFEditorPro",
        "--windowed",  # No console window
        "--noconfirm",
        "--clean",
    ]

    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    # Add tool data
    sep = ";" if sys.platform == "win32" else ":"

    if tesseract_dir.exists():
        cmd.extend([
            "--add-data", f"{tesseract_dir}{sep}tools/Tesseract-OCR"
        ])
        print(f"[+] Bundling Tesseract OCR from: {tesseract_dir}")
    else:
        print("[!] WARNING: Tesseract-OCR not found, OCR will not work")

    if poppler_dir.exists():
        cmd.extend([
            "--add-data", f"{poppler_dir}{sep}tools/poppler"
        ])
        print(f"[+] Bundling Poppler from: {poppler_dir}")
    else:
        print("[!] WARNING: Poppler not found, some features may not work")

    # Hidden imports for all dependencies
    hidden_imports = [
        "PIL", "PIL._tkinter_finder", "PIL.Image", "PIL.ImageTk",
        "customtkinter", "customtkinter.windows",
        "cv2", "numpy",
        "pytesseract",
        "pikepdf", "pikepdf._core",
        "fitz", "fitz.fitz",
        "reportlab", "reportlab.lib", "reportlab.pdfgen",
        "lxml", "lxml.etree",
        "pdf2image",
        "darkdetect",
        "tkinter", "tkinter.filedialog", "tkinter.messagebox",
        "json", "logging", "pathlib", "datetime",
    ]

    for imp in hidden_imports:
        cmd.extend(["--hidden-import", imp])

    # Collect all files for customtkinter (it has themes/assets)
    cmd.extend(["--collect-all", "customtkinter"])
    cmd.extend(["--collect-all", "fitz"])

    # Source files to include
    src_dir = PROJECT_ROOT / "src"
    if src_dir.exists():
        cmd.extend(["--add-data", f"{src_dir}{sep}src"])

    # Entry point
    cmd.append(str(PROJECT_ROOT / "main.py"))

    print()
    print("[*] Starting build...")
    print(f"    Mode: {'Single file (onefile)' if onefile else 'Directory'}")
    print(f"    Command: {' '.join(cmd[:10])}...")
    print()

    # Run PyInstaller
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))

    if result.returncode != 0:
        print()
        print("[ERROR] Build failed!")
        print("        Check the output above for details.")
        return False

    # Show results
    if onefile:
        exe_path = PROJECT_ROOT / "dist" / "PDFEditorPro.exe"
    else:
        exe_path = PROJECT_ROOT / "dist" / "PDFEditorPro" / "PDFEditorPro.exe"

    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print()
        print("=" * 60)
        print("  BUILD SUCCESSFUL!")
        print("=" * 60)
        print()
        print(f"  Output: {exe_path}")
        print(f"  Size:   {size_mb:.1f} MB")
        print()
        if onefile:
            print("  To distribute:")
            print(f"    Copy: {exe_path}")
            print()
            print("  Note: First launch may be slower (extracting tools)")
        else:
            dist_dir = PROJECT_ROOT / "dist" / "PDFEditorPro"
            print("  To distribute:")
            print(f"    Copy entire folder: {dist_dir}")
        print("=" * 60)
        return True
    else:
        print("[ERROR] EXE not found after build!")
        return False


def clean():
    """Clean build artifacts."""
    for d in ["build", "dist", "__pycache__"]:
        p = PROJECT_ROOT / d
        if p.exists():
            shutil.rmtree(p)
            print(f"[*] Removed: {p}")

    spec = PROJECT_ROOT / "PDFEditorPro.spec"
    if spec.exists():
        spec.unlink()
        print(f"[*] Removed: {spec}")


if __name__ == "__main__":
    if "--clean" in sys.argv:
        clean()
    elif "--dir" in sys.argv:
        build(onefile=False)
    else:
        build(onefile=True)
