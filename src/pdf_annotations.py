"""
PDF Annotations module.
Provides highlighting, underlining, strikethrough, freehand drawing,
sticky notes, shapes, stamps, and signatures.
"""

import fitz  # PyMuPDF
from pathlib import Path
from PIL import Image as PILImage
from src.utils import logger, safe_operation


class PDFAnnotations:
    """Handles PDF annotation operations using PyMuPDF."""

    # ─── Highlight / Markup ──────────────────────────────────────────────

    @staticmethod
    @safe_operation
    def highlight_text(page, quad_or_rect, color=(1, 1, 0)):
        """
        Add a highlight annotation to text.

        Args:
            page: PyMuPDF page object
            quad_or_rect: fitz.Quad or fitz.Rect of the text area
            color: RGB tuple (0-1 range), default yellow

        Returns:
            The annotation object
        """
        annot = page.add_highlight_annot(quad_or_rect)
        annot.set_colors(stroke=color)
        annot.update()
        logger.info(f"Added highlight at {quad_or_rect}")
        return annot

    @staticmethod
    @safe_operation
    def underline_text(page, quad_or_rect, color=(0, 0, 1)):
        """Add an underline annotation."""
        annot = page.add_underline_annot(quad_or_rect)
        annot.set_colors(stroke=color)
        annot.update()
        return annot

    @staticmethod
    @safe_operation
    def strikethrough_text(page, quad_or_rect, color=(1, 0, 0)):
        """Add a strikethrough annotation."""
        annot = page.add_strikeout_annot(quad_or_rect)
        annot.set_colors(stroke=color)
        annot.update()
        return annot

    @staticmethod
    @safe_operation
    def squiggly_underline(page, quad_or_rect, color=(0, 0.5, 0)):
        """Add a squiggly underline annotation."""
        annot = page.add_squiggly_annot(quad_or_rect)
        annot.set_colors(stroke=color)
        annot.update()
        return annot

    # ─── Shapes ──────────────────────────────────────────────────────────

    @staticmethod
    @safe_operation
    def add_rectangle(page, rect, color=(1, 0, 0), fill=None,
                      width=1.0, opacity=1.0):
        """
        Draw a rectangle on the page.

        Args:
            page: PyMuPDF page object
            rect: fitz.Rect for the rectangle
            color: Stroke color RGB (0-1)
            fill: Fill color RGB or None
            width: Line width
            opacity: Opacity (0-1)

        Returns:
            Shape object
        """
        shape = page.new_shape()
        shape.draw_rect(rect)
        shape.finish(
            color=color,
            fill=fill,
            width=width,
            stroke_opacity=opacity,
            fill_opacity=opacity * 0.3 if fill else 0
        )
        shape.commit()
        return shape

    @staticmethod
    @safe_operation
    def add_circle(page, rect, color=(0, 0, 1), fill=None,
                   width=1.0, opacity=1.0):
        """Draw a circle/ellipse on the page."""
        shape = page.new_shape()
        center = rect.tl + (rect.br - rect.tl) / 2
        radius_x = rect.width / 2
        radius_y = rect.height / 2
        # Use draw_oval for ellipse support
        shape.draw_oval(rect)
        shape.finish(
            color=color,
            fill=fill,
            width=width,
            stroke_opacity=opacity,
            fill_opacity=opacity * 0.3 if fill else 0
        )
        shape.commit()
        return shape

    @staticmethod
    @safe_operation
    def add_line(page, start_point, end_point, color=(0, 0, 0),
                 width=1.0):
        """
        Draw a line on the page.

        Args:
            page: PyMuPDF page object
            start_point: fitz.Point for start
            end_point: fitz.Point for end
            color: Line color RGB (0-1)
            width: Line width
        """
        shape = page.new_shape()
        shape.draw_line(start_point, end_point)
        shape.finish(color=color, width=width)
        shape.commit()
        return shape

    @staticmethod
    @safe_operation
    def add_arrow(page, start_point, end_point, color=(0, 0, 0),
                  width=1.5):
        """Draw an arrow on the page."""
        annot = page.add_line_annot(start_point, end_point)
        annot.set_colors(stroke=color)
        annot.set_border(width=width)
        # Set line ending to arrow
        annot.set_line_ends(fitz.PDF_ANNOT_LE_NONE, fitz.PDF_ANNOT_LE_OPEN_ARROW)
        annot.update()
        return annot

    # ─── Freehand Drawing ────────────────────────────────────────────────

    @staticmethod
    @safe_operation
    def add_freehand(page, points, color=(0, 0, 0), width=2.0):
        """
        Draw a freehand path on the page.

        Args:
            page: PyMuPDF page object
            points: List of fitz.Point objects
            color: Stroke color RGB (0-1)
            width: Line width

        Returns:
            Shape object
        """
        if len(points) < 2:
            return None

        shape = page.new_shape()
        shape.draw_polyline(points)
        shape.finish(color=color, width=width, closePath=False)
        shape.commit()
        return shape

    @staticmethod
    @safe_operation
    def add_ink_annotation(page, paths, color=(0, 0, 0), width=2.0):
        """
        Add an ink (freehand) annotation.

        Args:
            page: PyMuPDF page object
            paths: List of lists of (x, y) tuples
            color: Stroke color
            width: Line width

        Returns:
            Annotation object
        """
        annot = page.add_ink_annot(paths)
        annot.set_colors(stroke=color)
        annot.set_border(width=width)
        annot.update()
        return annot

    # ─── Sticky Notes ────────────────────────────────────────────────────

    @staticmethod
    @safe_operation
    def add_sticky_note(page, point, text, icon="Note",
                        color=(1, 1, 0)):
        """
        Add a sticky note annotation.

        Args:
            page: PyMuPDF page object
            point: fitz.Point for the note position
            text: Note text content
            icon: Icon type ('Note', 'Comment', 'Help', 'Insert',
                  'Key', 'NewParagraph', 'Paragraph')
            color: Note color RGB (0-1)

        Returns:
            Annotation object
        """
        annot = page.add_text_annot(point, text, icon=icon)
        annot.set_colors(stroke=color)
        annot.update()
        logger.info(f"Added sticky note at {point}")
        return annot

    # ─── Stamps & Signatures ────────────────────────────────────────────

    @staticmethod
    @safe_operation
    def add_stamp(page, rect, stamp_text="APPROVED", color=(1, 0, 0),
                  rotation=0):
        """
        Add a text stamp to the page.

        Args:
            page: PyMuPDF page object
            rect: fitz.Rect for stamp placement
            stamp_text: Text for the stamp
            color: Text color RGB (0-1)
            rotation: Rotation angle in degrees
        """
        annot = page.add_stamp_annot(rect, stamp=0)
        annot.set_info(content=stamp_text)
        annot.set_colors(stroke=color)
        annot.set_rotation(rotation)
        annot.update()
        return annot

    @staticmethod
    @safe_operation
    def add_signature_image(page, rect, image_path, keep_proportion=True):
        """
        Add a signature image to the page.

        Args:
            page: PyMuPDF page object
            rect: fitz.Rect for signature placement
            image_path: Path to the signature image (PNG with transparency)
            keep_proportion: Whether to maintain aspect ratio
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Signature image not found: {image_path}")

        if keep_proportion:
            # Calculate proportional rect
            img = PILImage.open(str(image_path))
            img_w, img_h = img.size
            aspect = img_w / img_h

            rect_aspect = rect.width / rect.height
            if rect_aspect > aspect:
                # Too wide, adjust width
                new_width = rect.height * aspect
                x_offset = (rect.width - new_width) / 2
                rect = fitz.Rect(
                    rect.x0 + x_offset, rect.y0,
                    rect.x0 + x_offset + new_width, rect.y1
                )
            else:
                # Too tall, adjust height
                new_height = rect.width / aspect
                y_offset = (rect.height - new_height) / 2
                rect = fitz.Rect(
                    rect.x0, rect.y0 + y_offset,
                    rect.x1, rect.y0 + y_offset + new_height
                )

        page.insert_image(rect, filename=str(image_path))
        logger.info(f"Added signature image at {rect}")

    # ─── Annotation Management ───────────────────────────────────────────

    @staticmethod
    def get_annotations(page):
        """Get all annotations on a page."""
        annotations = []
        for annot in page.annots():
            annotations.append({
                "type": annot.type[1],
                "rect": tuple(annot.rect),
                "content": annot.info.get("content", ""),
                "author": annot.info.get("title", ""),
                "created": annot.info.get("creationDate", ""),
            })
        return annotations

    @staticmethod
    @safe_operation
    def delete_annotation(page, annot):
        """Delete a specific annotation."""
        page.delete_annot(annot)
        logger.info("Deleted annotation")

    @staticmethod
    @safe_operation
    def delete_all_annotations(page):
        """Delete all annotations from a page."""
        annots = list(page.annots())
        for annot in annots:
            page.delete_annot(annot)
        logger.info(f"Deleted {len(annots)} annotations")

    # ─── Text Search & Highlight ─────────────────────────────────────────

    @staticmethod
    @safe_operation
    def search_and_highlight(page, search_text, color=(1, 1, 0)):
        """
        Search for text on a page and highlight all occurrences.

        Args:
            page: PyMuPDF page object
            search_text: Text to search for
            color: Highlight color RGB (0-1)

        Returns:
            Number of highlights added
        """
        instances = page.search_for(search_text)
        for inst in instances:
            annot = page.add_highlight_annot(inst)
            annot.set_colors(stroke=color)
            annot.update()

        logger.info(
            f"Highlighted {len(instances)} instances of '{search_text}'"
        )
        return len(instances)
