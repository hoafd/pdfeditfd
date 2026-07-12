# PDF Editor Pro — Walkthrough

## Summary

Built a comprehensive, fully offline PDF editor application at `c:\Users\admin\Documents\pdfeditfd` with **23 features** including the core smart page splitting capability using OpenCV + Tesseract OCR.

---

## Files Created

### Setup & Config
| File | Purpose |
|------|---------|
| [requirements.txt](file:///c:/Users/admin/Documents/pdfeditfd/requirements.txt) | Python dependencies (9 packages) |
| [setup.bat](file:///c:/Users/admin/Documents/pdfeditfd/setup.bat) | Automated setup script |
| [run.bat](file:///c:/Users/admin/Documents/pdfeditfd/run.bat) | Application launcher |
| [main.py](file:///c:/Users/admin/Documents/pdfeditfd/main.py) | Entry point with path configuration |

### Core Modules
| File | Purpose |
|------|---------|
| [src/utils.py](file:///c:/Users/admin/Documents/pdfeditfd/src/utils.py) | Path management, coordinate conversion, logging |
| [src/ocr_engine.py](file:///c:/Users/admin/Documents/pdfeditfd/src/ocr_engine.py) | Tesseract OCR + OpenCV preprocessing engine |
| [src/pdf_operations.py](file:///c:/Users/admin/Documents/pdfeditfd/src/pdf_operations.py) | Merge, split, rotate, crop, delete, extract, compress |
| [src/pdf_split_smart.py](file:///c:/Users/admin/Documents/pdfeditfd/src/pdf_split_smart.py) | ⭐ Smart page splitting (Y coord / OCR text / auto-detect) |
| [src/pdf_annotations.py](file:///c:/Users/admin/Documents/pdfeditfd/src/pdf_annotations.py) | Highlights, shapes, freehand, sticky notes, stamps |
| [src/pdf_security.py](file:///c:/Users/admin/Documents/pdfeditfd/src/pdf_security.py) | Encrypt/decrypt with AES-256 |
| [src/pdf_text_image.py](file:///c:/Users/admin/Documents/pdfeditfd/src/pdf_text_image.py) | Add text, images, watermarks, extract content |
| [src/pdf_viewer.py](file:///c:/Users/admin/Documents/pdfeditfd/src/pdf_viewer.py) | PDF rendering, zoom, navigation, thumbnails |
| [src/app.py](file:///c:/Users/admin/Documents/pdfeditfd/src/app.py) | Main GUI application (CustomTkinter dark theme) |

---

## ⭐ Smart Page Split Feature

Three modes for splitting a PDF page into 2 separate pages:

### Mode 1: Split by Y Coordinate
- Enter Y in PDF points or percentage
- Click on page to set split point (interactive)
- Split all pages at same Y

### Mode 2: Split After Text (OCR)
1. Converts PDF page → image at 300 DPI
2. Tesseract OCR finds text + bounding boxes
3. Locates the specified keyword/phrase
4. Converts pixel coordinates → PDF points
5. Splits page below the text line

### Mode 3: Auto-Detect
- OpenCV `HoughLinesP` detects horizontal lines
- Whitespace gap detection via horizontal projection
- Ranks split points by confidence score

---

## Tools Installed (Portable)

| Tool | Version | Location |
|------|---------|----------|
| Python venv | 3.12.10 | `venv/` |
| PyMuPDF | 1.27.2.3 | venv |
| OpenCV | 4.13.0.92 | venv |
| pikepdf | 10.7.2 | venv |
| CustomTkinter | 5.2.2 | venv |
| Tesseract OCR | 5.4.0 | `tools/Tesseract-OCR/` |
| Poppler | 24.08.0 | `tools/poppler/` |
| OCR Languages | eng, vie, osd | `tools/Tesseract-OCR/tessdata/` |

---

## Verification Results

| Test | Result |
|------|--------|
| All Python packages import | ✅ Pass |
| Tesseract OCR detection | ✅ Available, v5.4.0 |
| Poppler pdftoppm | ✅ Found |
| Open PDF file (167 pages) | ✅ Pass |
| Smart split by percentage (50%) | ✅ 1 page → 2 pages (421pt each) |
| GUI application launch | ✅ Running |

---

## How to Use

### First-time setup
```batch
setup.bat
```

### Launch the application
```batch
run.bat
```
Or directly:
```batch
.\venv\Scripts\python.exe main.py
```

### Open with a specific file
```batch
.\venv\Scripts\python.exe main.py "BILL-HKA-T062026.pdf"
```

### Keyboard Shortcuts
| Key | Action |
|-----|--------|
| Ctrl+O | Open PDF |
| Ctrl+S | Save As |
| ← / → | Previous / Next page |
| Home / End | First / Last page |
| Ctrl+/– | Zoom in/out |
| Escape | Cancel split mode |
