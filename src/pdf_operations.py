"""
PDF Operations module - Basic PDF manipulation operations.
Provides merge, split, rotate, crop, reorder, delete, and extract pages.
"""

import fitz  # PyMuPDF
from pathlib import Path
from src.utils import (
    logger, safe_operation, validate_pdf_path,
    validate_page_range, generate_output_filename, get_output_dir
)


class PDFOperations:
    """Handles basic PDF operations using PyMuPDF."""

    def __init__(self):
        self.doc = None
        self.file_path = None

    def open(self, pdf_path):
        """Open a PDF file."""
        pdf_path = validate_pdf_path(pdf_path)
        self.close()
        self.doc = fitz.open(str(pdf_path))
        self.file_path = pdf_path
        logger.info(f"Opened PDF: {pdf_path} ({self.doc.page_count} pages)")
        return self.doc

    def close(self):
        """Close the current document."""
        if self.doc:
            self.doc.close()
            self.doc = None
            self.file_path = None

    def save(self, output_path=None, garbage=4, deflate=True):
        """
        Save the current document.

        Args:
            output_path: Output file path (None = overwrite original)
            garbage: Garbage collection level (0-4)
            deflate: Whether to compress streams
        """
        if not self.doc:
            raise ValueError("No document is open")

        if output_path is None:
            output_path = generate_output_filename(self.file_path, "edited")
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self.doc.save(
            str(output_path),
            garbage=garbage,
            deflate=deflate
        )
        logger.info(f"Saved PDF to: {output_path}")
        return output_path

    @property
    def page_count(self):
        """Get the number of pages."""
        return self.doc.page_count if self.doc else 0

    def get_page(self, page_num):
        """Get a specific page."""
        if not self.doc:
            raise ValueError("No document is open")
        validate_page_range(page_num, self.doc.page_count)
        return self.doc[page_num]

    # ─── Merge ───────────────────────────────────────────────────────────

    @safe_operation
    def merge_pdfs(self, pdf_paths, output_path=None):
        """
        Merge multiple PDF files into one.

        Args:
            pdf_paths: List of PDF file paths to merge
            output_path: Output file path

        Returns:
            Path to the merged PDF
        """
        if not pdf_paths:
            raise ValueError("No PDF files to merge")

        merged = fitz.open()

        for path in pdf_paths:
            path = validate_pdf_path(path)
            doc = fitz.open(str(path))
            merged.insert_pdf(doc)
            doc.close()

        if output_path is None:
            output_path = generate_output_filename(
                pdf_paths[0], "merged"
            )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        merged.save(str(output_path))
        merged.close()

        logger.info(f"Merged {len(pdf_paths)} PDFs to: {output_path}")
        return output_path

    # ─── Split ───────────────────────────────────────────────────────────

    @safe_operation
    def split_by_pages(self, pdf_path, page_ranges, output_dir=None):
        """
        Split a PDF by page ranges.

        Args:
            pdf_path: Path to the PDF file
            page_ranges: List of (start, end) tuples (0-indexed, inclusive)
            output_dir: Output directory

        Returns:
            List of output file paths
        """
        pdf_path = validate_pdf_path(pdf_path)
        doc = fitz.open(str(pdf_path))

        if output_dir is None:
            output_dir = get_output_dir()
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_paths = []
        for i, (start, end) in enumerate(page_ranges):
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=start, to_page=end)

            output_path = output_dir / f"{pdf_path.stem}_part{i + 1}.pdf"
            new_doc.save(str(output_path))
            new_doc.close()
            output_paths.append(output_path)

        doc.close()
        logger.info(f"Split PDF into {len(output_paths)} parts")
        return output_paths

    @safe_operation
    def split_each_page(self, pdf_path, output_dir=None):
        """
        Split a PDF into individual pages.

        Args:
            pdf_path: Path to the PDF file
            output_dir: Output directory

        Returns:
            List of output file paths
        """
        pdf_path = validate_pdf_path(pdf_path)
        doc = fitz.open(str(pdf_path))

        page_ranges = [(i, i) for i in range(doc.page_count)]
        doc.close()

        return self.split_by_pages(pdf_path, page_ranges, output_dir)

    # ─── Rotate ──────────────────────────────────────────────────────────

    @safe_operation
    def rotate_pages(self, page_numbers, angle, output_path=None):
        """
        Rotate specific pages.

        Args:
            page_numbers: List of page numbers to rotate (0-indexed)
            angle: Rotation angle (90, 180, 270)
            output_path: Output file path

        Returns:
            Path to the output file
        """
        if not self.doc:
            raise ValueError("No document is open")

        if angle not in (90, 180, 270, -90, -180, -270):
            raise ValueError(f"Invalid rotation angle: {angle}")

        for page_num in page_numbers:
            validate_page_range(page_num, self.doc.page_count)
            page = self.doc[page_num]
            page.set_rotation(page.rotation + angle)

        return self.save(output_path)

    # ─── Crop ────────────────────────────────────────────────────────────

    @safe_operation
    def crop_page(self, page_num, rect, output_path=None):
        """
        Crop a page to a specific rectangle.

        Args:
            page_num: Page number (0-indexed)
            rect: Tuple (x0, y0, x1, y1) in PDF points
            output_path: Output file path

        Returns:
            Path to the output file
        """
        if not self.doc:
            raise ValueError("No document is open")

        validate_page_range(page_num, self.doc.page_count)
        page = self.doc[page_num]
        page.set_cropbox(fitz.Rect(rect))

        return self.save(output_path)

    # ─── Reorder ─────────────────────────────────────────────────────────

    @safe_operation
    def reorder_pages(self, new_order, output_path=None):
        """
        Reorder pages in the document.

        Args:
            new_order: List of page numbers in desired order (0-indexed)
            output_path: Output file path

        Returns:
            Path to the output file
        """
        if not self.doc:
            raise ValueError("No document is open")

        for page_num in new_order:
            validate_page_range(page_num, self.doc.page_count)

        self.doc.select(new_order)
        return self.save(output_path)

    # ─── Delete Pages ────────────────────────────────────────────────────

    @safe_operation
    def delete_pages(self, page_numbers, output_path=None):
        """
        Delete specific pages from the document.

        Args:
            page_numbers: List of page numbers to delete (0-indexed)
            output_path: Output file path

        Returns:
            Path to the output file
        """
        if not self.doc:
            raise ValueError("No document is open")

        # Sort in reverse to avoid index shifting
        for page_num in sorted(page_numbers, reverse=True):
            validate_page_range(page_num, self.doc.page_count)
            self.doc.delete_page(page_num)

        return self.save(output_path)

    # ─── Extract Pages ───────────────────────────────────────────────────

    @safe_operation
    def extract_pages(self, page_numbers, output_path=None):
        """
        Extract specific pages to a new PDF.

        Args:
            page_numbers: List of page numbers to extract (0-indexed)
            output_path: Output file path

        Returns:
            Path to the output file
        """
        if not self.doc:
            raise ValueError("No document is open")

        new_doc = fitz.open()
        for page_num in page_numbers:
            validate_page_range(page_num, self.doc.page_count)
            new_doc.insert_pdf(self.doc, from_page=page_num, to_page=page_num)

        if output_path is None:
            output_path = generate_output_filename(
                self.file_path, "extracted"
            )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        new_doc.save(str(output_path))
        new_doc.close()

        logger.info(f"Extracted {len(page_numbers)} pages to: {output_path}")
        return output_path

    # ─── Page Info ───────────────────────────────────────────────────────

    def get_page_info(self, page_num):
        """
        Get information about a specific page.

        Returns:
            Dictionary with page dimensions, rotation, etc.
        """
        if not self.doc:
            raise ValueError("No document is open")

        validate_page_range(page_num, self.doc.page_count)
        page = self.doc[page_num]

        return {
            "page_num": page_num,
            "width": page.rect.width,
            "height": page.rect.height,
            "rotation": page.rotation,
            "mediabox": tuple(page.mediabox),
            "cropbox": tuple(page.cropbox) if page.cropbox else None,
        }

    def render_page(self, page_num, zoom=1.0):
        """
        Render a page as a PIL Image.

        Args:
            page_num: Page number (0-indexed)
            zoom: Zoom factor (1.0 = 72 DPI)

        Returns:
            PIL Image of the rendered page
        """
        if not self.doc:
            raise ValueError("No document is open")

        validate_page_range(page_num, self.doc.page_count)
        page = self.doc[page_num]

        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        from PIL import Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return img

    # ─── Compress ────────────────────────────────────────────────────────

    @safe_operation
    def compress_pdf(self, pdf_path=None, output_path=None):
        """
        Compress a PDF file to reduce size.

        Args:
            pdf_path: Input PDF path (uses current doc if None)
            output_path: Output file path

        Returns:
            Tuple of (output_path, original_size, new_size)
        """
        if pdf_path:
            doc = fitz.open(str(pdf_path))
            original_path = Path(pdf_path)
        elif self.doc:
            doc = self.doc
            original_path = self.file_path
        else:
            raise ValueError("No document to compress")

        import os
        original_size = os.path.getsize(str(original_path))

        if output_path is None:
            output_path = generate_output_filename(original_path, "compressed")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save with maximum compression
        doc.save(
            str(output_path),
            garbage=4,
            deflate=True,
            clean=True,
            linear=True
        )

        if pdf_path:
            doc.close()

        new_size = os.path.getsize(str(output_path))
        reduction = (1 - new_size / original_size) * 100 if original_size > 0 else 0

        logger.info(
            f"Compressed PDF: {original_size} -> {new_size} bytes "
            f"({reduction:.1f}% reduction)"
        )
        return output_path, original_size, new_size
