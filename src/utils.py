"""
Utility functions for the PDF Editor application.
Provides path management, coordinate conversion, logging, and common helpers.
"""

import os
import sys
import logging
import tempfile
import shutil
from pathlib import Path
from datetime import datetime


# ─── Project Paths ───────────────────────────────────────────────────────────

def get_project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent.resolve()


def get_tools_dir():
    """Get the tools directory path."""
    return get_project_root() / "tools"


def get_tesseract_path():
    """Get the Tesseract executable path."""
    return get_tools_dir() / "Tesseract-OCR" / "tesseract.exe"


def get_tessdata_dir():
    """Get the tessdata directory path."""
    return get_tools_dir() / "Tesseract-OCR" / "tessdata"


def get_poppler_path():
    """Get the Poppler bin directory path."""
    poppler_dir = get_tools_dir() / "poppler"
    # Check common structures
    for sub in ["Library/bin", "bin", "poppler-24.08.0/Library/bin"]:
        p = poppler_dir / sub
        if p.exists():
            return str(p)
    return str(poppler_dir / "Library" / "bin")


def get_output_dir():
    """Get the output directory path, creating it if needed."""
    d = get_project_root() / "output"
    d.mkdir(exist_ok=True)
    return d


def get_temp_dir():
    """Get the temp directory path, creating it if needed."""
    d = get_project_root() / "temp"
    d.mkdir(exist_ok=True)
    return d

import io

# ─── Logging Setup ──────────────────────────────────────────────────────────

def setup_logging(level=logging.INFO):
    """Set up logging for the application."""
    log_dir = get_project_root() / "logs"
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / f"pdfeditor_{datetime.now().strftime('%Y%m%d')}.log"
    
    # Wrap stdout to handle unicode/emoji on Windows (cp1252 -> utf-8)
    try:
        stdout_stream = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
    except Exception:
        stdout_stream = sys.stdout
    
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(stdout_stream)
        ]
    )
    return logging.getLogger("PDFEditor")


logger = setup_logging()


# ─── Coordinate Conversion ──────────────────────────────────────────────────

def pixels_to_pdf_points(pixel_y, image_height, pdf_page_height, dpi=300):
    """
    Convert a Y coordinate from image pixels to PDF points.
    
    PDF coordinate system: origin at bottom-left, Y increases upward.
    Image coordinate system: origin at top-left, Y increases downward.
    
    Args:
        pixel_y: Y coordinate in image pixels (from top)
        image_height: Total height of the image in pixels
        pdf_page_height: Height of the PDF page in points
        dpi: DPI used when rendering the image
    
    Returns:
        Y coordinate in PDF points (from bottom)
    """
    # Convert pixels to points (1 point = 1/72 inch)
    points_from_top = pixel_y * 72.0 / dpi
    return points_from_top


def pdf_points_to_pixels(pdf_y, pdf_page_height, image_height, dpi=300):
    """
    Convert a Y coordinate from PDF points to image pixels.
    
    Args:
        pdf_y: Y coordinate in PDF points (from top of mediabox)
        pdf_page_height: Height of the PDF page in points
        image_height: Total height of the image in pixels
        dpi: DPI used when rendering the image
    
    Returns:
        Y coordinate in image pixels (from top)
    """
    pixel_y = pdf_y * dpi / 72.0
    return int(pixel_y)


def percentage_to_pdf_points(percentage, pdf_page_height):
    """
    Convert a percentage (0-100) to PDF points from top.
    
    Args:
        percentage: Percentage from top of page (0 = top, 100 = bottom)
        pdf_page_height: Height of the PDF page in points
    
    Returns:
        Y coordinate in PDF points from top
    """
    return pdf_page_height * percentage / 100.0


# ─── File Helpers ────────────────────────────────────────────────────────────

def format_file_size(size_bytes):
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def get_unique_filename(directory, base_name, extension):
    """
    Generate a unique filename in the given directory.
    If the file already exists, appends _1, _2, etc.
    """
    directory = Path(directory)
    candidate = directory / f"{base_name}{extension}"
    if not candidate.exists():
        return candidate
    
    counter = 1
    while True:
        candidate = directory / f"{base_name}_{counter}{extension}"
        if not candidate.exists():
            return candidate
        counter += 1


def generate_output_filename(input_path, suffix="edited", output_dir=None):
    """
    Generate an output filename based on the input file.
    
    Args:
        input_path: Path to the input file
        suffix: Suffix to add (e.g., 'edited', 'merged', 'split')
        output_dir: Output directory (defaults to project output/)
    
    Returns:
        Path object for the output file
    """
    input_path = Path(input_path)
    if output_dir is None:
        output_dir = get_output_dir()
    else:
        output_dir = Path(output_dir)
    
    base_name = f"{input_path.stem}_{suffix}"
    return get_unique_filename(output_dir, base_name, input_path.suffix)


def cleanup_temp():
    """Clean up temporary files."""
    temp_dir = get_temp_dir()
    for item in temp_dir.iterdir():
        try:
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        except Exception as e:
            logger.warning(f"Could not clean up {item}: {e}")


# ─── Error Handling ──────────────────────────────────────────────────────────

def safe_operation(func):
    """Decorator for safe PDF operations with error handling."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
            raise
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


# ─── Validation ──────────────────────────────────────────────────────────────

def validate_pdf_path(path):
    """Validate that the given path is a valid PDF file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not path.suffix.lower() == ".pdf":
        raise ValueError(f"Not a PDF file: {path}")
    return path


def validate_page_range(page_num, total_pages):
    """Validate that the page number is within range."""
    if page_num < 0 or page_num >= total_pages:
        raise ValueError(f"Page {page_num} is out of range (0-{total_pages - 1})")
    return True
