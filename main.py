"""
PDF Editor Pro — Offline Edition
Entry point for the application.

Configures portable tool paths and launches the GUI.
"""

import os
import sys
from pathlib import Path

# ─── Configure project paths ────────────────────────────────────────────────
# Support both normal execution and PyInstaller frozen EXE
if getattr(sys, 'frozen', False):
    # Running as PyInstaller bundle
    BUNDLE_DIR = Path(sys._MEIPASS)
    PROJECT_ROOT = Path(sys.executable).parent.resolve()
else:
    # Running as script
    BUNDLE_DIR = Path(__file__).parent.resolve()
    PROJECT_ROOT = BUNDLE_DIR

# Add project root to Python path
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Configure Tesseract OCR path — check bundle first, then project
for base in [BUNDLE_DIR, PROJECT_ROOT]:
    TESSERACT_DIR = base / "tools" / "Tesseract-OCR"
    TESSERACT_EXE = TESSERACT_DIR / "tesseract.exe"
    TESSDATA_DIR = TESSERACT_DIR / "tessdata"
    if TESSERACT_DIR.exists():
        os.environ["PATH"] = str(TESSERACT_DIR) + os.pathsep + os.environ.get("PATH", "")
        if TESSDATA_DIR.exists():
            os.environ["TESSDATA_PREFIX"] = str(TESSDATA_DIR)
        break

# Configure Poppler path
for base in [BUNDLE_DIR, PROJECT_ROOT]:
    POPPLER_DIR = base / "tools" / "poppler"
    for sub in ["Library/bin", "bin"]:
        poppler_bin = POPPLER_DIR / sub
        if poppler_bin.exists():
            os.environ["PATH"] = str(poppler_bin) + os.pathsep + os.environ.get("PATH", "")
            break

# ─── Launch the application ─────────────────────────────────────────────────

def main():
    """Main entry point."""
    import tkinter as tk

    # Check for required libraries
    missing = []
    try:
        import fitz
    except ImportError:
        missing.append("PyMuPDF")
    try:
        import PIL
    except ImportError:
        missing.append("Pillow")
    try:
        import cv2
    except ImportError:
        missing.append("opencv-python")

    if missing:
        print("=" * 60)
        print("  ERROR: Missing required libraries!")
        print(f"  Missing: {', '.join(missing)}")
        print()
        print("  Please run 'setup.bat' first to install all dependencies.")
        print("=" * 60)
        try:
            root = tk.Tk()
            root.withdraw()
            from tkinter import messagebox
            messagebox.showerror(
                "Missing Libraries",
                f"Missing required libraries: {', '.join(missing)}\n\n"
                "Please run 'setup.bat' first to install all dependencies."
            )
            root.destroy()
        except Exception:
            pass
        sys.exit(1)

    # Import and launch the app
    from src.app import PDFEditorApp

    root = tk.Tk()

    # Set icon if available
    try:
        # Use a built-in Tk icon approach
        root.iconname("PDF Editor Pro")
    except Exception:
        pass

    app = PDFEditorApp(root)

    # Auto-open file if provided as argument
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.exists(file_path) and file_path.lower().endswith('.pdf'):
            root.after(100, lambda: app.open_file(file_path))

    root.mainloop()


if __name__ == "__main__":
    main()
