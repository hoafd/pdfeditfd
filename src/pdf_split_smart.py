"""
Smart PDF Page Splitting module.
Split a single PDF page into two separate pages using:
1. Manual Y coordinate
2. OCR text detection (split after a specific text line)
3. Auto-detection of split points (horizontal lines, whitespace gaps)

Uses OpenCV + Tesseract OCR for intelligent content analysis.
"""

import fitz  # PyMuPDF
import cv2
import numpy as np
from pathlib import Path
from PIL import Image

from src.utils import (
    logger, safe_operation, validate_pdf_path,
    validate_page_range, generate_output_filename,
    pixels_to_pdf_points, get_output_dir, get_temp_dir
)
from src.ocr_engine import get_ocr_engine


class SmartPageSplitter:
    """
    Intelligently split PDF pages into two parts.
    Supports manual Y-coordinate, text-based, and auto-detection splitting.
    """

    def __init__(self):
        self.ocr = get_ocr_engine()
        self.default_dpi = 300

    # ─── Mode 1: Split by Y Coordinate ───────────────────────────────────

    @safe_operation
    def split_by_y_coordinate(self, pdf_path, page_num, split_y_points,
                               output_path=None):
        """
        Split a PDF page into two pages at a specific Y coordinate (PDF points).

        Args:
            pdf_path: Path to the PDF file
            page_num: Page number to split (0-indexed)
            split_y_points: Y coordinate in PDF points (from top of page)
            output_path: Output file path

        Returns:
            Path to the output PDF with the page split into two
        """
        pdf_path = validate_pdf_path(pdf_path)
        doc = fitz.open(str(pdf_path))
        validate_page_range(page_num, doc.page_count)

        page = doc[page_num]
        page_rect = page.rect  # (x0, y0, x1, y1)

        # Validate split point
        if split_y_points <= 0 or split_y_points >= page_rect.height:
            raise ValueError(
                f"Split Y ({split_y_points}) must be between 0 and "
                f"{page_rect.height} points"
            )

        # Create output document
        output_doc = fitz.open()

        # Copy pages before the split page
        if page_num > 0:
            output_doc.insert_pdf(doc, from_page=0, to_page=page_num - 1)

        # Create top half
        top_rect = fitz.Rect(
            page_rect.x0, page_rect.y0,
            page_rect.x1, page_rect.y0 + split_y_points
        )
        # Create bottom half
        bottom_rect = fitz.Rect(
            page_rect.x0, page_rect.y0 + split_y_points,
            page_rect.x1, page_rect.y1
        )

        # Insert top half as new page
        new_page_top = output_doc.new_page(
            width=top_rect.width, height=top_rect.height
        )
        new_page_top.show_pdf_page(
            fitz.Rect(0, 0, top_rect.width, top_rect.height),
            doc, page_num,
            clip=top_rect
        )

        # Insert bottom half as new page
        new_page_bottom = output_doc.new_page(
            width=bottom_rect.width, height=bottom_rect.height
        )
        new_page_bottom.show_pdf_page(
            fitz.Rect(0, 0, bottom_rect.width, bottom_rect.height),
            doc, page_num,
            clip=bottom_rect
        )

        # Copy pages after the split page
        if page_num < doc.page_count - 1:
            output_doc.insert_pdf(
                doc, from_page=page_num + 1,
                to_page=doc.page_count - 1
            )

        # Save
        if output_path is None:
            output_path = generate_output_filename(pdf_path, "split")
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_doc.save(str(output_path), garbage=4, deflate=True)
        output_doc.close()
        doc.close()

        logger.info(
            f"Split page {page_num} at Y={split_y_points}pt -> {output_path}"
        )
        return output_path

    @safe_operation
    def crop_multiple_y_regions(self, pdf_path, page_num, regions, output_path=None):
        """
        Crop a page into multiple separate pages based on multiple Y regions.
        
        Args:
            pdf_path: Path to the PDF file
            page_num: Page number to split
            regions: List of (y1_points, y2_points) tuples
            output_path: Output file path
            
        Returns:
            Path to the output PDF
        """
        pdf_path = validate_pdf_path(pdf_path)
        doc = fitz.open(str(pdf_path))
        validate_page_range(page_num, doc.page_count)
        
        page = doc[page_num]
        page_rect = page.rect
        
        output_doc = fitz.open()
        
        # Copy pages before
        if page_num > 0:
            output_doc.insert_pdf(doc, from_page=0, to_page=page_num - 1)
            
        # Add cropped regions
        for y1, y2 in regions:
            y1 = max(0, min(y1, page_rect.height))
            y2 = max(0, min(y2, page_rect.height))
            if y1 >= y2:
                continue
                
            crop_rect = fitz.Rect(page_rect.x0, page_rect.y0 + y1, page_rect.x1, page_rect.y0 + y2)
            new_page = output_doc.new_page(width=crop_rect.width, height=crop_rect.height)
            new_page.show_pdf_page(
                fitz.Rect(0, 0, crop_rect.width, crop_rect.height),
                doc, page_num,
                clip=crop_rect
            )
            
        # Copy pages after
        if page_num < doc.page_count - 1:
            output_doc.insert_pdf(doc, from_page=page_num + 1, to_page=doc.page_count - 1)
            
        if output_path is None:
            output_path = generate_output_filename(pdf_path, "multicrop")
            
        output_doc.save(str(output_path), garbage=4, deflate=True)
        return output_path

    @safe_operation
    def batch_crop_multiple_y_regions(self, pdf_path, page_numbers, regions, output_path=None):
        """
        Apply multi-Y cropping to multiple pages.
        For each page in page_numbers, it extracts the defined Y-regions into new pages.
        Pages not in page_numbers are kept as-is.
        """
        pdf_path = validate_pdf_path(pdf_path)
        doc = fitz.open(str(pdf_path))
        output_doc = fitz.open()
        page_numbers_set = set(page_numbers)
        
        for page_num in range(doc.page_count):
            page = doc[page_num]
            page_rect = page.rect
            
            if page_num not in page_numbers_set:
                output_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                continue
                
            # Add cropped regions for this page
            for y1, y2 in regions:
                y1 = max(0, min(y1, page_rect.height))
                y2 = max(0, min(y2, page_rect.height))
                if y1 >= y2:
                    continue
                    
                crop_rect = fitz.Rect(page_rect.x0, page_rect.y0 + y1, page_rect.x1, page_rect.y0 + y2)
                new_page = output_doc.new_page(width=crop_rect.width, height=crop_rect.height)
                new_page.show_pdf_page(
                    fitz.Rect(0, 0, crop_rect.width, crop_rect.height),
                    doc, page_num,
                    clip=crop_rect
                )
                
        if output_path is None:
            output_path = generate_output_filename(pdf_path, "batch_multicrop")
            
        output_doc.save(str(output_path), garbage=4, deflate=True)
        return output_path

    @safe_operation
    def split_by_y_percentage(self, pdf_path, page_num, percentage,
                               output_path=None):
        """
        Split a PDF page at a percentage from the top.

        Args:
            pdf_path: Path to the PDF file
            page_num: Page number (0-indexed)
            percentage: Percentage from top (0-100)
            output_path: Output file path

        Returns:
            Path to the output PDF
        """
        pdf_path = validate_pdf_path(pdf_path)
        doc = fitz.open(str(pdf_path))
        validate_page_range(page_num, doc.page_count)

        page = doc[page_num]
        split_y = page.rect.height * percentage / 100.0
        doc.close()

        return self.split_by_y_coordinate(
            pdf_path, page_num, split_y, output_path
        )

    # ─── Mode 2: Split After Text (OCR) ──────────────────────────────────

    @safe_operation
    def split_after_text(self, pdf_path, page_num, search_text,
                          output_path=None, margin_below=10, lang=None):
        """
        Split a PDF page after a specific text line found via OCR.

        Pipeline:
        1. Convert PDF page to high-res image
        2. Use Tesseract OCR to find text position
        3. Convert image coordinates to PDF coordinates
        4. Split at the detected position

        Args:
            pdf_path: Path to the PDF file
            page_num: Page number (0-indexed)
            search_text: Text to search for (split happens after this text)
            output_path: Output file path
            margin_below: Extra margin below the text line (in PDF points)
            lang: OCR language (default: eng+vie)

        Returns:
            Path to the output PDF

        Raises:
            ValueError: If the text is not found on the page
        """
        pdf_path = validate_pdf_path(pdf_path)

        # Step 1: Convert page to image for OCR
        logger.info(f"Converting page {page_num} to image for OCR...")
        cv2_image = self.ocr.pdf_page_to_cv2(
            pdf_path, page_num, dpi=self.default_dpi
        )
        image_height = cv2_image.shape[0]

        # Step 2: Find text position using OCR
        logger.info(f"Searching for text: '{search_text}'...")
        positions = self.ocr.find_text_position(cv2_image, search_text, lang)

        if not positions:
            raise ValueError(
                f"Text '{search_text}' not found on page {page_num}. "
                "Try different search terms or check the OCR language setting."
            )

        # Use the first match - get the bottom of the text line
        match = positions[0]
        pixel_y = match["line_bottom"]
        logger.info(
            f"Found text at pixel Y={pixel_y}, "
            f"confidence={match['conf']}"
        )

        # Step 3: Convert pixel Y to PDF points
        doc = fitz.open(str(pdf_path))
        page = doc[page_num]
        pdf_page_height = page.rect.height
        doc.close()

        split_y_points = pixels_to_pdf_points(
            pixel_y, image_height, pdf_page_height, self.default_dpi
        )
        split_y_points += margin_below

        # Ensure split point is within bounds
        split_y_points = max(10, min(split_y_points, pdf_page_height - 10))

        logger.info(
            f"Split point: pixel Y={pixel_y} -> PDF Y={split_y_points}pt "
            f"(page height={pdf_page_height}pt)"
        )

        # Step 4: Perform the split
        return self.split_by_y_coordinate(
            pdf_path, page_num, split_y_points, output_path
        )

    def preview_text_search(self, pdf_path, page_num, search_text, lang=None):
        """
        Preview text search results without splitting.
        Returns the found positions and a preview image.

        Args:
            pdf_path: Path to the PDF file
            page_num: Page number (0-indexed)
            search_text: Text to search for
            lang: OCR language

        Returns:
            Tuple of (positions_list, annotated_pil_image)
        """
        # Convert to image
        cv2_image = self.ocr.pdf_page_to_cv2(
            pdf_path, page_num, dpi=self.default_dpi
        )

        # Find text
        positions = self.ocr.find_text_position(cv2_image, search_text, lang)

        # Draw rectangles on the image
        annotated = cv2_image.copy()
        for pos in positions:
            y = pos["y"]
            h = pos["h"]
            img_h, img_w = annotated.shape[:2]

            # Draw the text bounding box
            if pos["w"] > 0:
                cv2.rectangle(
                    annotated,
                    (pos["x"], y),
                    (pos["x"] + pos["w"], y + h),
                    (0, 255, 0), 2
                )

            # Draw the split line (full width, red)
            split_y = pos["line_bottom"]
            cv2.line(
                annotated,
                (0, split_y), (img_w, split_y),
                (0, 0, 255), 3
            )

            # Add label
            cv2.putText(
                annotated,
                f"Split here (Y={split_y}px)",
                (10, split_y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8, (0, 0, 255), 2
            )

        # Convert to PIL
        annotated_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(annotated_rgb)

        return positions, pil_image

    # ─── Mode 3: Auto-detect Split Points ────────────────────────────────

    @safe_operation
    def auto_detect_split_points(self, pdf_path, page_num):
        """
        Automatically detect potential split points on a PDF page.
        Uses OpenCV to find horizontal lines and whitespace gaps.

        Args:
            pdf_path: Path to the PDF file
            page_num: Page number (0-indexed)

        Returns:
            List of dicts with keys:
                type: 'line' or 'gap'
                pixel_y: Y position in pixels
                pdf_y: Y position in PDF points
                confidence: Detection confidence (0-1)
                description: Human-readable description
        """
        pdf_path = validate_pdf_path(pdf_path)

        # Convert page to image
        cv2_image = self.ocr.pdf_page_to_cv2(
            pdf_path, page_num, dpi=self.default_dpi
        )
        image_height = cv2_image.shape[0]

        # Get PDF page height for coordinate conversion
        doc = fitz.open(str(pdf_path))
        page = doc[page_num]
        pdf_page_height = page.rect.height
        doc.close()

        split_points = []

        # Detect horizontal lines
        h_lines = self.ocr.detect_horizontal_lines(cv2_image)
        for y, x1, x2 in h_lines:
            # Skip lines too close to top/bottom (< 10% from edges)
            if y < image_height * 0.1 or y > image_height * 0.9:
                continue

            line_length = x2 - x1
            img_width = cv2_image.shape[1]
            confidence = min(1.0, line_length / (img_width * 0.5))

            pdf_y = pixels_to_pdf_points(
                y, image_height, pdf_page_height, self.default_dpi
            )

            split_points.append({
                "type": "line",
                "pixel_y": y,
                "pdf_y": pdf_y,
                "confidence": confidence,
                "description": f"Horizontal line at Y={y}px ({pdf_y:.0f}pt)"
            })

        # Detect whitespace gaps
        gaps = self.ocr.detect_whitespace_gaps(cv2_image, min_gap_height=30)
        for center_y, start_y, end_y in gaps:
            # Skip gaps too close to top/bottom
            if center_y < image_height * 0.1 or center_y > image_height * 0.9:
                continue

            gap_height = end_y - start_y
            confidence = min(1.0, gap_height / 100.0)

            pdf_y = pixels_to_pdf_points(
                center_y, image_height, pdf_page_height, self.default_dpi
            )

            split_points.append({
                "type": "gap",
                "pixel_y": center_y,
                "pdf_y": pdf_y,
                "confidence": confidence,
                "description": (
                    f"Whitespace gap at Y={center_y}px ({pdf_y:.0f}pt), "
                    f"height={gap_height}px"
                )
            })

        # Sort by confidence (highest first)
        split_points.sort(key=lambda p: p["confidence"], reverse=True)

        logger.info(f"Found {len(split_points)} potential split points")
        return split_points

    def preview_split_points(self, pdf_path, page_num):
        """
        Generate a preview image showing all detected split points.

        Args:
            pdf_path: Path to the PDF file
            page_num: Page number (0-indexed)

        Returns:
            Tuple of (split_points_list, annotated_pil_image)
        """
        # Convert to image
        cv2_image = self.ocr.pdf_page_to_cv2(
            pdf_path, page_num, dpi=self.default_dpi
        )
        split_points = self.auto_detect_split_points(pdf_path, page_num)

        # Draw split points on image
        annotated = cv2_image.copy()
        img_w = annotated.shape[1]

        for i, sp in enumerate(split_points):
            y = sp["pixel_y"]
            color = (0, 0, 255) if sp["type"] == "line" else (255, 128, 0)
            thickness = 3 if sp["confidence"] > 0.5 else 1

            cv2.line(annotated, (0, y), (img_w, y), color, thickness)

            label = f"#{i + 1} {sp['type']} (conf={sp['confidence']:.2f})"
            cv2.putText(
                annotated, label,
                (10, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6, color, 2
            )

        # Convert to PIL
        annotated_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(annotated_rgb)

        return split_points, pil_image

    @safe_operation
    def split_at_auto_detected(self, pdf_path, page_num, point_index=0,
                                output_path=None):
        """
        Split at an auto-detected split point.

        Args:
            pdf_path: Path to the PDF file
            page_num: Page number (0-indexed)
            point_index: Index of the split point to use (0 = best)
            output_path: Output file path

        Returns:
            Path to the output PDF
        """
        split_points = self.auto_detect_split_points(pdf_path, page_num)

        if not split_points:
            raise ValueError("No split points detected on this page")

        if point_index >= len(split_points):
            raise ValueError(
                f"Point index {point_index} is out of range "
                f"(0-{len(split_points) - 1})"
            )

        sp = split_points[point_index]
        logger.info(f"Splitting at: {sp['description']}")

        return self.split_by_y_coordinate(
            pdf_path, page_num, sp["pdf_y"], output_path
        )

    # ─── Batch Split ─────────────────────────────────────────────────────

    @safe_operation
    def split_all_pages_by_y(self, pdf_path, split_y_points,
                              output_path=None):
        """
        Split ALL pages in a PDF at the same Y coordinate.

        Args:
            pdf_path: Path to the PDF file
            split_y_points: Y coordinate in PDF points
            output_path: Output file path

        Returns:
            Path to the output PDF
        """
        pdf_path = validate_pdf_path(pdf_path)
        doc = fitz.open(str(pdf_path))

        output_doc = fitz.open()

        for page_num in range(doc.page_count):
            page = doc[page_num]
            page_rect = page.rect

            actual_split = min(split_y_points, page_rect.height - 1)
            if actual_split <= 0:
                # Page too small, just copy it
                output_doc.insert_pdf(
                    doc, from_page=page_num, to_page=page_num
                )
                continue

            # Top half
            top_rect = fitz.Rect(
                page_rect.x0, page_rect.y0,
                page_rect.x1, page_rect.y0 + actual_split
            )
            new_top = output_doc.new_page(
                width=top_rect.width, height=top_rect.height
            )
            new_top.show_pdf_page(
                fitz.Rect(0, 0, top_rect.width, top_rect.height),
                doc, page_num, clip=top_rect
            )

            # Bottom half
            bottom_rect = fitz.Rect(
                page_rect.x0, page_rect.y0 + actual_split,
                page_rect.x1, page_rect.y1
            )
            new_bottom = output_doc.new_page(
                width=bottom_rect.width, height=bottom_rect.height
            )
            new_bottom.show_pdf_page(
                fitz.Rect(0, 0, bottom_rect.width, bottom_rect.height),
                doc, page_num, clip=bottom_rect
            )

        if output_path is None:
            output_path = generate_output_filename(pdf_path, "split_all")
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_doc.save(str(output_path), garbage=4, deflate=True)
        output_doc.close()
        doc.close()

        logger.info(f"Split all pages at Y={split_y_points}pt -> {output_path}")
        return output_path

    # ─── Batch OCR Split ─────────────────────────────────────────────────

    def split_batch_after_text(self, pdf_path, page_numbers, search_text,
                                output_path=None, margin_below=10, lang=None,
                                progress_callback=None):
        """
        Split multiple pages after specific text found via OCR.
        Pages where text is NOT found are copied as-is.

        Args:
            pdf_path: Path to the PDF file
            page_numbers: List of 0-indexed page numbers to process
            search_text: Text to search for on each page
            output_path: Output file path
            margin_below: Extra margin below the text line (PDF points)
            lang: OCR language
            progress_callback: Optional function(page_num, total, status_msg)

        Returns:
            Tuple of (output_path, found_count, not_found_pages)
        """
        pdf_path = validate_pdf_path(pdf_path)
        doc = fitz.open(str(pdf_path))
        output_doc = fitz.open()

        found_count = 0
        not_found_pages = []
        page_numbers_set = set(page_numbers)

        for page_num in range(doc.page_count):
            page = doc[page_num]
            page_rect = page.rect

            if page_num not in page_numbers_set:
                # Not selected — copy as-is
                output_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                continue

            if progress_callback:
                progress_callback(
                    page_num, doc.page_count,
                    f"OCR scanning page {page_num + 1}..."
                )

            # Try to find text on this page via OCR
            try:
                cv2_image = self.ocr.pdf_page_to_cv2(
                    pdf_path, page_num, dpi=self.default_dpi
                )
                image_height = cv2_image.shape[0]
                positions = self.ocr.find_text_position(
                    cv2_image, search_text, lang
                )
            except Exception as e:
                logger.warning(f"OCR failed on page {page_num}: {e}")
                positions = []

            if not positions:
                # Text not found — copy as-is
                output_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                not_found_pages.append(page_num + 1)
                continue

            # Text found — calculate split point
            match = positions[0]
            pixel_y = match["line_bottom"]
            pdf_page_height = page_rect.height

            split_y = pixels_to_pdf_points(
                pixel_y, image_height, pdf_page_height, self.default_dpi
            )
            split_y += margin_below
            split_y = max(10, min(split_y, pdf_page_height - 10))

            logger.info(
                f"Page {page_num + 1}: Found '{search_text}' -> "
                f"split at Y={split_y:.0f}pt"
            )

            # Create top half
            top_rect = fitz.Rect(
                page_rect.x0, page_rect.y0,
                page_rect.x1, page_rect.y0 + split_y
            )
            new_top = output_doc.new_page(
                width=top_rect.width, height=top_rect.height
            )
            new_top.show_pdf_page(
                fitz.Rect(0, 0, top_rect.width, top_rect.height),
                doc, page_num, clip=top_rect
            )

            # Create bottom half
            bottom_rect = fitz.Rect(
                page_rect.x0, page_rect.y0 + split_y,
                page_rect.x1, page_rect.y1
            )
            new_bottom = output_doc.new_page(
                width=bottom_rect.width, height=bottom_rect.height
            )
            new_bottom.show_pdf_page(
                fitz.Rect(0, 0, bottom_rect.width, bottom_rect.height),
                doc, page_num, clip=bottom_rect
            )

            found_count += 1

        # Save
        if output_path is None:
            output_path = generate_output_filename(pdf_path, "batch_ocr_split")
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_doc.save(str(output_path), garbage=4, deflate=True)
        output_doc.close()
        doc.close()

        logger.info(
            f"Batch OCR split: {found_count}/{len(page_numbers)} pages split, "
            f"output -> {output_path}"
        )
        return output_path, found_count, not_found_pages

    # ─── Crop Between Texts ──────────────────────────────────────────────

    def crop_between_texts(self, pdf_path, page_numbers, start_text, end_text,
                            output_path=None, margin_above=5, margin_below=5,
                            lang=None, keep_unmatched=False,
                            progress_callback=None, template_page_num=None):
        """
        Crop pages to only keep content between start_text and end_text.
        Runs OCR concurrently using BatchProcessor.
        """
        pdf_path = validate_pdf_path(pdf_path)
        
        # 1. Prepare tasks
        page_numbers_set = set(page_numbers)
        tasks = [p for p in page_numbers_set]
        
        from src.batch_processor import get_shared_processor
        processor = get_shared_processor()
        
        def _ocr_worker(page_num, idx, total):
            # Worker function: opens its own fitz.doc to avoid thread issues
            try:
                # We need page_rect for pdf_page_height
                doc_w = fitz.open(str(pdf_path))
                page_rect = doc_w[page_num].rect
                pdf_page_height = page_rect.height
                doc_w.close()
                
                cv2_image = self.ocr.pdf_page_to_cv2(
                    pdf_path, page_num, dpi=self.default_dpi
                )
                image_height = cv2_image.shape[0]

                start_positions = self.ocr.find_text_position(
                    cv2_image, start_text, lang
                )
                end_positions = self.ocr.find_text_position(
                    cv2_image, end_text, lang
                )
                
                if not start_positions or not end_positions:
                    return page_num, None
                    
                # Convert to PDF points
                starts_pdf = []
                for sp in start_positions:
                    y_px = sp["y"]
                    y_pt = pixels_to_pdf_points(
                        y_px, image_height, pdf_page_height, self.default_dpi
                    )
                    starts_pdf.append(max(0, y_pt - margin_above))

                ends_pdf = []
                for ep in end_positions:
                    y_px = ep["line_bottom"]
                    y_pt = pixels_to_pdf_points(
                        y_px, image_height, pdf_page_height, self.default_dpi
                    )
                    ends_pdf.append(min(pdf_page_height, y_pt + margin_below))

                starts_pdf.sort()
                ends_pdf.sort()

                pairs = []
                used_ends = set()
                for s_y in starts_pdf:
                    best_end = None
                    best_idx = -1
                    for e_idx, e_y in enumerate(ends_pdf):
                        if e_idx in used_ends: continue
                        if e_y > s_y:
                            best_end = e_y
                            best_idx = e_idx
                            break
                    if best_end is not None:
                        pairs.append((s_y, best_end))
                        used_ends.add(best_idx)
                
                return page_num, pairs if pairs else None
                
            except Exception as e:
                logger.warning(f"OCR failed on page {page_num + 1}: {e}")
                return page_num, None

        # 2. Run OCR
        page_results = {}
        if template_page_num is not None:
            if progress_callback:
                progress_callback(1, 1, f"Scanning template page {template_page_num + 1}...")
            _, pairs = _ocr_worker(template_page_num, 0, 1)
            if pairs:
                for p in page_numbers_set:
                    page_results[p] = pairs
        else:
            results = processor.parallel_map(tasks, _ocr_worker, progress_callback)
            if processor.is_cancelled:
                return None, 0, []
                
            for p_num, pairs in results:
                if pairs:
                    page_results[p_num] = pairs
        
        # 3. Build Output PDF
        doc = fitz.open(str(pdf_path))
        output_doc = fitz.open()
        
        total_crops = 0
        skipped_pages = []
        
        for page_num in range(doc.page_count):
            page = doc[page_num]
            page_rect = page.rect
            
            if page_num not in page_numbers_set:
                if keep_unmatched:
                    output_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                continue
                
            pairs = page_results.get(page_num)
            
            if not pairs:
                if keep_unmatched:
                    output_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                skipped_pages.append(page_num + 1)
                continue
                
            # Create cropped pages
            for i, (crop_top, crop_bottom) in enumerate(pairs):
                crop_height = crop_bottom - crop_top
                if crop_height < 10:
                    continue
                    
                clip_rect = fitz.Rect(
                    page_rect.x0, crop_top,
                    page_rect.x1, crop_bottom
                )
                new_page = output_doc.new_page(
                    width=clip_rect.width, height=clip_rect.height
                )
                new_page.show_pdf_page(
                    fitz.Rect(0, 0, clip_rect.width, clip_rect.height),
                    doc, page_num, clip=clip_rect
                )
                total_crops += 1

        if output_path is None:
            output_path = generate_output_filename(pdf_path, "crop_between")
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_doc.save(str(output_path), garbage=4, deflate=True)
        
        output_doc.close()
        doc.close()

        logger.info(
            f"Crop between texts: {total_crops} regions extracted "
            f"from {len(page_numbers)} pages -> {output_path}"
        )
        return output_path, total_crops, skipped_pages


