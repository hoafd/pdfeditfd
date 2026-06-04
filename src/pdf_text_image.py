"""
PDF Text & Image module.
Provides functionality to add text, images, watermarks, headers/footers,
and to extract text and images from PDF files.
"""

import fitz  # PyMuPDF
import io
from pathlib import Path
from PIL import Image as PILImage
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from src.utils import (
    logger, safe_operation, validate_pdf_path,
    validate_page_range, generate_output_filename, get_output_dir
)


class PDFTextImage:
    """Handles text and image operations on PDF files."""

    # ─── Add Text ────────────────────────────────────────────────────────

    @staticmethod
    @safe_operation
    def add_text(doc, page_num, text, position, fontsize=12,
                 fontname="helv", color=(0, 0, 0), rotation=0, opacity=1.0):
        """
        Add text to a specific position on a page.

        Args:
            doc: PyMuPDF document object
            page_num: Page number (0-indexed)
            text: Text to add
            position: Tuple (x, y) in PDF points
            fontsize: Font size in points
            fontname: Font name ('helv', 'tiro', 'cour', 'symb', 'zadb')
            color: RGB color tuple (0-1 range)
            rotation: Text rotation in degrees
            opacity: Text opacity (0-1)

        Returns:
            The text insertion result
        """
        validate_page_range(page_num, doc.page_count)
        page = doc[page_num]

        x, y = position
        # Insert text
        rc = page.insert_text(
            fitz.Point(x, y),
            text,
            fontsize=fontsize,
            fontname=fontname,
            color=color,
            rotate=rotation,
            overlay=True,
        )

        logger.info(f"Added text at ({x}, {y}) on page {page_num}")
        return rc

    @staticmethod
    @safe_operation
    def add_text_box(doc, page_num, text, rect, fontsize=12,
                     fontname="helv", color=(0, 0, 0), align=0):
        """
        Add text within a rectangular area with automatic line wrapping.

        Args:
            doc: PyMuPDF document object
            page_num: Page number
            text: Text to add
            rect: fitz.Rect defining the text area
            fontsize: Font size
            fontname: Font name
            color: RGB color
            align: 0=left, 1=center, 2=right, 3=justify

        Returns:
            Overflow text (if any)
        """
        validate_page_range(page_num, doc.page_count)
        page = doc[page_num]

        rc = page.insert_textbox(
            rect, text,
            fontsize=fontsize,
            fontname=fontname,
            color=color,
            align=align,
            overlay=True,
        )

        logger.info(f"Added text box on page {page_num}")
        return rc

    # ─── Add Image ───────────────────────────────────────────────────────

    @staticmethod
    @safe_operation
    def add_image(doc, page_num, image_path, rect, keep_proportion=True,
                  overlay=True):
        """
        Insert an image into a page.

        Args:
            doc: PyMuPDF document object
            page_num: Page number
            image_path: Path to the image file
            rect: fitz.Rect for image placement
            keep_proportion: Maintain aspect ratio
            overlay: If True, place on top of existing content

        Returns:
            The page object
        """
        validate_page_range(page_num, doc.page_count)
        page = doc[page_num]

        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        if keep_proportion:
            img = PILImage.open(str(image_path))
            img_w, img_h = img.size
            aspect = img_w / img_h

            rect_aspect = rect.width / rect.height
            if rect_aspect > aspect:
                new_width = rect.height * aspect
                x_offset = (rect.width - new_width) / 2
                rect = fitz.Rect(
                    rect.x0 + x_offset, rect.y0,
                    rect.x0 + x_offset + new_width, rect.y1
                )
            else:
                new_height = rect.width / aspect
                y_offset = (rect.height - new_height) / 2
                rect = fitz.Rect(
                    rect.x0, rect.y0 + y_offset,
                    rect.x1, rect.y0 + y_offset + new_height
                )

        page.insert_image(rect, filename=str(image_path), overlay=overlay)
        logger.info(f"Added image {image_path.name} at {rect} on page {page_num}")
        return page

    # ─── Watermark ───────────────────────────────────────────────────────

    @staticmethod
    @safe_operation
    def add_text_watermark(doc, text="CONFIDENTIAL", fontsize=60,
                           color=(0.8, 0.8, 0.8), rotation=45,
                           opacity=0.3, pages=None):
        """
        Add a text watermark to pages.

        Args:
            doc: PyMuPDF document object
            text: Watermark text
            fontsize: Font size
            color: RGB color (0-1)
            rotation: Rotation angle
            opacity: Opacity (0-1)
            pages: List of page numbers (None = all pages)

        Returns:
            Number of pages watermarked
        """
        if pages is None:
            pages = range(doc.page_count)

        count = 0
        for page_num in pages:
            if page_num >= doc.page_count:
                continue

            page = doc[page_num]
            rect = page.rect

            # Center of page
            center_x = rect.width / 2
            center_y = rect.height / 2

            # Create text writer for watermark
            tw = fitz.TextWriter(page.rect)
            font = fitz.Font("helv")

            # Calculate text width for centering
            text_width = font.text_length(text, fontsize=fontsize)
            start_x = center_x - text_width / 2
            start_y = center_y

            tw.append(
                fitz.Point(start_x, start_y),
                text,
                font=font,
                fontsize=fontsize,
            )

            tw.write_text(page, color=color, opacity=opacity,
                         morph=(fitz.Point(center_x, center_y),
                                fitz.Matrix(rotation)))
            count += 1

        logger.info(f"Added text watermark to {count} pages")
        return count

    @staticmethod
    @safe_operation
    def add_image_watermark(doc, image_path, opacity=0.3,
                            scale=0.5, pages=None):
        """
        Add an image watermark to pages.

        Args:
            doc: PyMuPDF document object
            image_path: Path to watermark image
            opacity: Image opacity (0-1)
            scale: Scale factor for the image
            pages: List of page numbers (None = all pages)

        Returns:
            Number of pages watermarked
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Watermark image not found: {image_path}")

        if pages is None:
            pages = range(doc.page_count)

        # Get image dimensions
        img = PILImage.open(str(image_path))
        img_w, img_h = img.size

        count = 0
        for page_num in pages:
            if page_num >= doc.page_count:
                continue

            page = doc[page_num]
            rect = page.rect

            # Calculate centered position
            wm_w = img_w * scale * 72 / 96  # Convert pixels to points
            wm_h = img_h * scale * 72 / 96

            x = (rect.width - wm_w) / 2
            y = (rect.height - wm_h) / 2

            wm_rect = fitz.Rect(x, y, x + wm_w, y + wm_h)

            page.insert_image(
                wm_rect,
                filename=str(image_path),
                overlay=True,
                alpha=int(opacity * 255) if hasattr(fitz, '__version__') else -1
            )
            count += 1

        logger.info(f"Added image watermark to {count} pages")
        return count

    # ─── Header & Footer ─────────────────────────────────────────────────

    @staticmethod
    @safe_operation
    def add_page_numbers(doc, position="bottom-center", fontsize=10,
                         color=(0, 0, 0), start_num=1, prefix="",
                         suffix="", pages=None, margin=36):
        """
        Add page numbers to the document.

        Args:
            doc: PyMuPDF document object
            position: 'bottom-center', 'bottom-right', 'bottom-left',
                      'top-center', 'top-right', 'top-left'
            fontsize: Font size
            color: RGB color
            start_num: Starting page number
            prefix: Text before number (e.g., "Page ")
            suffix: Text after number (e.g., " of {total}")
            pages: Page numbers to add to (None = all)
            margin: Margin from edge in points

        Returns:
            Number of pages numbered
        """
        if pages is None:
            pages = range(doc.page_count)

        total = doc.page_count
        count = 0

        for page_num in pages:
            if page_num >= doc.page_count:
                continue

            page = doc[page_num]
            rect = page.rect
            num = start_num + page_num

            text = f"{prefix}{num}{suffix}".format(total=total)

            # Calculate position
            if "bottom" in position:
                y = rect.height - margin
            else:
                y = margin + fontsize

            if "center" in position:
                # Approximate center
                text_width = len(text) * fontsize * 0.5
                x = (rect.width - text_width) / 2
            elif "right" in position:
                text_width = len(text) * fontsize * 0.5
                x = rect.width - margin - text_width
            else:
                x = margin

            page.insert_text(
                fitz.Point(x, y),
                text,
                fontsize=fontsize,
                fontname="helv",
                color=color,
            )
            count += 1

        logger.info(f"Added page numbers to {count} pages")
        return count

    @staticmethod
    @safe_operation
    def add_header_footer(doc, header_text=None, footer_text=None,
                          fontsize=9, color=(0.3, 0.3, 0.3),
                          pages=None, margin=36):
        """
        Add header and/or footer text to pages.

        Args:
            doc: PyMuPDF document object
            header_text: Text for header (None = no header)
            footer_text: Text for footer (None = no footer)
            fontsize: Font size
            color: RGB color
            pages: Page numbers (None = all)
            margin: Margin from edge in points

        Returns:
            Number of pages modified
        """
        if pages is None:
            pages = range(doc.page_count)

        count = 0
        for page_num in pages:
            if page_num >= doc.page_count:
                continue

            page = doc[page_num]
            rect = page.rect

            if header_text:
                text_width = len(header_text) * fontsize * 0.5
                x = (rect.width - text_width) / 2
                page.insert_text(
                    fitz.Point(x, margin),
                    header_text,
                    fontsize=fontsize,
                    fontname="helv",
                    color=color,
                )

            if footer_text:
                text_width = len(footer_text) * fontsize * 0.5
                x = (rect.width - text_width) / 2
                page.insert_text(
                    fitz.Point(x, rect.height - margin),
                    footer_text,
                    fontsize=fontsize,
                    fontname="helv",
                    color=color,
                )
            count += 1

        logger.info(f"Added header/footer to {count} pages")
        return count

    # ─── Extract Text ────────────────────────────────────────────────────

    @staticmethod
    @safe_operation
    def extract_text(doc, page_num=None, method="text"):
        """
        Extract text from the document.

        Args:
            doc: PyMuPDF document object
            page_num: Specific page (None = all pages)
            method: Extraction method ('text', 'blocks', 'words', 'dict')

        Returns:
            Extracted text string or structured data
        """
        if page_num is not None:
            validate_page_range(page_num, doc.page_count)
            page = doc[page_num]

            if method == "text":
                return page.get_text("text")
            elif method == "blocks":
                return page.get_text("blocks")
            elif method == "words":
                return page.get_text("words")
            elif method == "dict":
                return page.get_text("dict")
        else:
            # Extract from all pages
            all_text = []
            for i in range(doc.page_count):
                page = doc[i]
                text = page.get_text("text")
                all_text.append(f"--- Page {i + 1} ---\n{text}")
            return "\n\n".join(all_text)

    @staticmethod
    @safe_operation
    def extract_text_with_ocr(pdf_path, page_num=None, lang="eng+vie"):
        """
        Extract text using OCR (for scanned PDFs).

        Args:
            pdf_path: Path to the PDF
            page_num: Specific page (None = all pages)
            lang: OCR language

        Returns:
            Extracted text string
        """
        from src.ocr_engine import get_ocr_engine
        ocr = get_ocr_engine()

        doc = fitz.open(str(pdf_path))
        pages = [page_num] if page_num is not None else range(doc.page_count)
        doc.close()

        all_text = []
        for pn in pages:
            cv2_img = ocr.pdf_page_to_cv2(pdf_path, pn)
            text = ocr.image_to_string(cv2_img, lang=lang)
            all_text.append(f"--- Page {pn + 1} ---\n{text}")

        return "\n\n".join(all_text)

    # ─── Extract Images ──────────────────────────────────────────────────

    @staticmethod
    @safe_operation
    def extract_images(doc, page_num=None, output_dir=None, min_size=100):
        """
        Extract images from the document.

        Args:
            doc: PyMuPDF document object
            page_num: Specific page (None = all pages)
            output_dir: Directory to save images
            min_size: Minimum image dimension (width or height)

        Returns:
            List of saved image paths
        """
        if output_dir is None:
            output_dir = get_output_dir() / "extracted_images"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        pages = [page_num] if page_num is not None else range(doc.page_count)
        saved_images = []
        image_count = 0

        for pn in pages:
            if pn >= doc.page_count:
                continue

            page = doc[pn]
            images = page.get_images()

            for img_index, img in enumerate(images):
                xref = img[0]
                try:
                    base_image = doc.extract_image(xref)
                    if base_image is None:
                        continue

                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    width = base_image.get("width", 0)
                    height = base_image.get("height", 0)

                    # Skip small images
                    if width < min_size and height < min_size:
                        continue

                    image_count += 1
                    filename = f"page{pn + 1}_img{image_count}.{image_ext}"
                    filepath = output_dir / filename

                    with open(filepath, "wb") as f:
                        f.write(image_bytes)

                    saved_images.append(filepath)
                except Exception as e:
                    logger.warning(f"Could not extract image {xref}: {e}")

        logger.info(f"Extracted {len(saved_images)} images")
        return saved_images

    # ─── Background Color ────────────────────────────────────────────────

    @staticmethod
    @safe_operation
    def set_page_background(doc, page_num, color=(1, 1, 1)):
        """
        Set a solid background color for a page.

        Args:
            doc: PyMuPDF document object
            page_num: Page number
            color: RGB color (0-1)
        """
        validate_page_range(page_num, doc.page_count)
        page = doc[page_num]

        shape = page.new_shape()
        shape.draw_rect(page.rect)
        shape.finish(fill=color, color=color)
        shape.commit(overlay=False)

        logger.info(f"Set background color on page {page_num}")
