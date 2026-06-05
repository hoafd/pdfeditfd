"""
OCR Engine module using Tesseract OCR and OpenCV.
Provides text recognition, bounding box detection, line detection,
and image preprocessing for improved OCR accuracy.
"""

import os
import cv2
import numpy as np
from PIL import Image
from pathlib import Path

try:
    import pytesseract
    from pytesseract import Output
except ImportError:
    pytesseract = None

try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None

try:
    import easyocr
except ImportError:
    easyocr = None

from src.utils import (
    get_tesseract_path, get_tessdata_dir, get_poppler_path,
    get_temp_dir, get_tools_dir, logger
)


class OCREngine:
    """
    OCR Engine wrapping Tesseract OCR with OpenCV preprocessing.
    Auto-detects system Tesseract (with potential GPU support) before
    falling back to bundled portable version.
    """

    def __init__(self):
        self._tesseract_source = "none"  # "system" or "bundled" or "none"
        self._configure_paths()
        self.default_dpi = 300
        self.default_lang = "eng+vie"
        self._check_language_packs()
        
        # Engine selection
        self.active_engine = "tesseract"
        self.easyocr_reader = None

    def set_engine(self, engine_name):
        """Switch OCR engine between 'tesseract' and 'easyocr'."""
        if engine_name == "easyocr":
            if easyocr is None:
                raise ImportError("EasyOCR is not installed. Please install it first.")
            if self.easyocr_reader is None:
                logger.info("Initializing EasyOCR reader (this may take a moment)...")
                # EasyOCR uses 'en' and 'vi' instead of 'eng' and 'vie'
                self.easyocr_reader = easyocr.Reader(['vi', 'en'])
            self.active_engine = "easyocr"
            logger.info("OCR Engine switched to EasyOCR (GPU/CPU).")
        else:
            self.active_engine = "tesseract"
            logger.info("OCR Engine switched to Tesseract.")

    def _configure_paths(self):
        """
        Configure Tesseract and Poppler paths.
        Priority: System install (may have GPU) > Bundled portable.
        """
        tesseract_path = get_tesseract_path()
        
        if tesseract_path.exists() and pytesseract:
            pytesseract.pytesseract.tesseract_cmd = str(tesseract_path)
            
            # Determine source
            bundled_dir = str(get_tools_dir() / "Tesseract-OCR")
            if bundled_dir.lower() in str(tesseract_path).lower():
                self._tesseract_source = "bundled"
                logger.info(f"Tesseract (nội bộ): {tesseract_path}")
            else:
                self._tesseract_source = "system"
                logger.info(f"Tesseract (hệ thống - ưu tiên): {tesseract_path}")
        else:
            logger.warning(
                f"Tesseract not found at {tesseract_path}. "
                "OCR features will be limited."
            )

        tessdata = get_tessdata_dir()
        if tessdata.exists():
            os.environ["TESSDATA_PREFIX"] = str(tessdata)

        self.poppler_path = get_poppler_path()
        logger.info(f"Poppler path: {self.poppler_path}")

    def _check_language_packs(self):
        """Check and log available OCR language packs."""
        tessdata = get_tessdata_dir()
        if not tessdata.exists():
            logger.warning("tessdata directory not found — OCR languages unavailable")
            return

        required_langs = {"eng": "English", "vie": "Vietnamese"}
        available = []
        missing = []

        for lang_code, lang_name in required_langs.items():
            traineddata = tessdata / f"{lang_code}.traineddata"
            if traineddata.exists():
                available.append(f"{lang_name} ({lang_code})")
            else:
                missing.append(f"{lang_name} ({lang_code})")

        if available:
            logger.info(f"OCR ngôn ngữ sẵn sàng: {', '.join(available)}")
        if missing:
            logger.warning(
                f"OCR ngôn ngữ THIẾU: {', '.join(missing)} — "
                f"Hãy tải file .traineddata vào: {tessdata}"
            )
            # Adjust default_lang to only use available languages
            available_codes = [
                code for code in required_langs
                if (tessdata / f"{code}.traineddata").exists()
            ]
            if available_codes:
                self.default_lang = "+".join(available_codes)
            else:
                self.default_lang = "eng"  # Fallback

    def get_ocr_info(self):
        """Get info about current OCR configuration for display."""
        return {
            "source": self._tesseract_source,
            "path": str(get_tesseract_path()),
            "lang": self.default_lang,
            "tessdata": str(get_tessdata_dir()),
            "active_engine": self.active_engine,
            "has_easyocr": easyocr is not None,
        }

    def is_available(self):
        """Check if OCR engine is available."""
        try:
            if pytesseract is None:
                return False
            tesseract_path = get_tesseract_path()
            return tesseract_path.exists()
        except Exception:
            return False

    # ─── PDF to Image Conversion ─────────────────────────────────────────

    def pdf_page_to_image(self, pdf_path, page_number=0, dpi=None):
        """
        Convert a specific PDF page to a PIL Image.

        Args:
            pdf_path: Path to the PDF file
            page_number: Page number (0-indexed)
            dpi: Resolution for rendering

        Returns:
            PIL Image of the page
        """
        if convert_from_path is None:
            raise ImportError("pdf2image is not installed")

        dpi = dpi or self.default_dpi

        try:
            images = convert_from_path(
                str(pdf_path),
                dpi=dpi,
                first_page=page_number + 1,
                last_page=page_number + 1,
                poppler_path=self.poppler_path
            )
            if images:
                return images[0]
            raise ValueError(f"Could not convert page {page_number}")
        except Exception as e:
            logger.error(f"PDF to image conversion failed: {e}")
            raise

    def pdf_page_to_cv2(self, pdf_path, page_number=0, dpi=None):
        """
        Convert a PDF page to an OpenCV (numpy) image.

        Args:
            pdf_path: Path to the PDF file
            page_number: Page number (0-indexed)
            dpi: Resolution for rendering

        Returns:
            OpenCV image (BGR numpy array)
        """
        pil_image = self.pdf_page_to_image(pdf_path, page_number, dpi)
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    # ─── Image Preprocessing (OpenCV) ────────────────────────────────────

    def preprocess_for_ocr(self, image, method="adaptive"):
        """
        Preprocess image for better OCR accuracy.

        Args:
            image: OpenCV image (BGR or grayscale)
            method: Preprocessing method ('adaptive', 'otsu', 'simple')

        Returns:
            Preprocessed grayscale image
        """
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Noise removal
        denoised = cv2.fastNlMeansDenoising(gray, h=10)

        # Thresholding
        if method == "adaptive":
            binary = cv2.adaptiveThreshold(
                denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 11, 2
            )
        elif method == "otsu":
            _, binary = cv2.threshold(
                denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
        else:
            _, binary = cv2.threshold(denoised, 127, 255, cv2.THRESH_BINARY)

        return binary

    def deskew_image(self, image):
        """
        Correct skew in a document image.

        Args:
            image: OpenCV image

        Returns:
            Deskewed image
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Find all non-zero pixels
        coords = np.column_stack(np.where(gray < 128))
        if len(coords) < 100:
            return image

        # Get the minimum area rectangle
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        # Only correct if angle is small
        if abs(angle) > 10:
            return image

        h, w = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            image, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )
        return rotated

    def remove_borders(self, image, border_size=10):
        """Remove dark borders from scanned document."""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if contours:
            largest = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest)
            # Add small padding
            pad = border_size
            x = max(0, x - pad)
            y = max(0, y - pad)
            w = min(image.shape[1] - x, w + 2 * pad)
            h = min(image.shape[0] - y, h + 2 * pad)
            return image[y:y + h, x:x + w]

        return image

    # ─── OCR Functions ───────────────────────────────────────────────────

    def image_to_string(self, image, lang=None, preprocess=True):
        """
        Perform OCR on an image and return the recognized text.

        Args:
            image: PIL Image, OpenCV image, or file path
            lang: OCR language(s) (default: eng+vie)
            preprocess: Whether to preprocess the image

        Returns:
            Recognized text string
        """
        img = self._prepare_image(image, preprocess)

        if self.active_engine == "easyocr" and self.easyocr_reader is not None:
            # EasyOCR expects numpy array (OpenCV format)
            if isinstance(img, Image.Image):
                cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            else:
                cv_img = img
            results = self.easyocr_reader.readtext(cv_img, detail=0)
            return "\n".join(results)

        if pytesseract is None:
            raise ImportError("pytesseract is not installed")

        lang = lang or self.default_lang
        return pytesseract.image_to_string(img, lang=lang)

    def image_to_data(self, image, lang=None, preprocess=True):
        """
        Perform OCR and return detailed data including bounding boxes.

        Args:
            image: PIL Image, OpenCV image, or file path
            lang: OCR language(s)
            preprocess: Whether to preprocess

        Returns:
            Dictionary with keys: level, page_num, block_num, par_num,
            line_num, word_num, left, top, width, height, conf, text
        """
        if pytesseract is None:
            raise ImportError("pytesseract is not installed")

        lang = lang or self.default_lang
        img = self._prepare_image(image, preprocess)

        return pytesseract.image_to_data(
            img, lang=lang, output_type=Output.DICT
        )

    def image_to_boxes(self, image, lang=None, preprocess=True):
        """
        Perform OCR and return character-level bounding boxes.

        Args:
            image: PIL Image, OpenCV image, or file path
            lang: OCR language(s)
            preprocess: Whether to preprocess

        Returns:
            String with character bounding box data
        """
        if pytesseract is None:
            raise ImportError("pytesseract is not installed")

        lang = lang or self.default_lang
        img = self._prepare_image(image, preprocess)

        return pytesseract.image_to_boxes(img, lang=lang)

    def find_text_position(self, image, search_text, lang=None):
        """
        Find the position of specific text in an image using OCR.

        Args:
            image: PIL Image or OpenCV image
            search_text: Text to search for
            lang: OCR language(s)

        Returns:
            List of dicts with keys: text, x, y, w, h, conf, line_bottom
            where line_bottom is the Y coordinate of the bottom of the text line
        """
        search_lower = search_text.lower()
        results = []

        if self.active_engine == "easyocr" and self.easyocr_reader is not None:
            img = self._prepare_image(image, preprocess=False)
            if isinstance(img, Image.Image):
                cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            else:
                cv_img = img

            read_results = self.easyocr_reader.readtext(cv_img, detail=1)
            for bbox, text, prob in read_results:
                if search_lower in text.lower():
                    # bbox format: [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
                    x_coords = [p[0] for p in bbox]
                    y_coords = [p[1] for p in bbox]
                    x_min, x_max = min(x_coords), max(x_coords)
                    y_min, y_max = min(y_coords), max(y_coords)
                    
                    results.append({
                        "text": text,
                        "x": int(x_min),
                        "y": int(y_min),
                        "w": int(x_max - x_min),
                        "h": int(y_max - y_min),
                        "conf": prob * 100,  # Convert to 0-100 scale like Tesseract
                        "line_bottom": int(y_max)
                    })
            return results

        # Tesseract fallback
        data = self.image_to_data(image, lang=lang, preprocess=True)
        
        n_boxes = len(data["text"])

        # First, try to find the text as a whole phrase across consecutive words
        for i in range(n_boxes):
            text = str(data["text"][i]).strip()
            if not text:
                continue

            # Check single word match
            if search_lower in text.lower():
                results.append({
                    "text": text,
                    "x": data["left"][i],
                    "y": data["top"][i],
                    "w": data["width"][i],
                    "h": data["height"][i],
                    "conf": data["conf"][i],
                    "line_bottom": data["top"][i] + data["height"][i]
                })

        # If no single-word match, try concatenating words on the same line
        if not results:
            lines = {}
            for i in range(n_boxes):
                text = str(data["text"][i]).strip()
                if not text:
                    continue
                line_key = (
                    data["block_num"][i],
                    data["par_num"][i],
                    data["line_num"][i]
                )
                if line_key not in lines:
                    lines[line_key] = {
                        "words": [],
                        "y_min": data["top"][i],
                        "y_max": data["top"][i] + data["height"][i]
                    }
                lines[line_key]["words"].append(text)
                lines[line_key]["y_max"] = max(
                    lines[line_key]["y_max"],
                    data["top"][i] + data["height"][i]
                )
                lines[line_key]["y_min"] = min(
                    lines[line_key]["y_min"],
                    data["top"][i]
                )

            for line_key, line_data in lines.items():
                full_line = " ".join(line_data["words"])
                if search_lower in full_line.lower():
                    results.append({
                        "text": full_line,
                        "x": 0,
                        "y": line_data["y_min"],
                        "w": 0,
                        "h": line_data["y_max"] - line_data["y_min"],
                        "conf": 0,
                        "line_bottom": line_data["y_max"]
                    })

        return results

    # ─── Line Detection (OpenCV) ─────────────────────────────────────────

    def detect_horizontal_lines(self, image, min_length_ratio=0.3):
        """
        Detect horizontal lines in an image using OpenCV.

        Args:
            image: OpenCV image
            min_length_ratio: Minimum line length as ratio of image width

        Returns:
            List of (y_position, x_start, x_end) tuples sorted by Y
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        h, w = gray.shape[:2]
        min_length = int(w * min_length_ratio)

        # Edge detection
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)

        # Detect lines using HoughLinesP
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=100,
            minLineLength=min_length,
            maxLineGap=10
        )

        horizontal_lines = []
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                # Check if line is approximately horizontal
                if abs(y2 - y1) < 5:
                    avg_y = (y1 + y2) // 2
                    horizontal_lines.append((avg_y, min(x1, x2), max(x1, x2)))

        # Sort by Y position and remove duplicates (within 5px)
        horizontal_lines.sort(key=lambda l: l[0])
        filtered = []
        for line in horizontal_lines:
            if not filtered or abs(line[0] - filtered[-1][0]) > 5:
                filtered.append(line)

        return filtered

    def detect_whitespace_gaps(self, image, min_gap_height=20):
        """
        Detect large horizontal white-space gaps in an image.
        Useful for finding natural split points between content blocks.

        Args:
            image: OpenCV image
            min_gap_height: Minimum gap height in pixels

        Returns:
            List of (gap_center_y, gap_start_y, gap_end_y) tuples
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        h, w = gray.shape[:2]

        # Binarize
        _, binary = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)

        # Calculate horizontal projection (sum of white pixels per row)
        row_sums = np.sum(binary, axis=1) / 255

        # Find rows that are mostly white (> 95% white)
        threshold = w * 0.95
        is_white_row = row_sums >= threshold

        # Find continuous white regions
        gaps = []
        in_gap = False
        gap_start = 0

        for y in range(h):
            if is_white_row[y] and not in_gap:
                in_gap = True
                gap_start = y
            elif not is_white_row[y] and in_gap:
                in_gap = False
                gap_height = y - gap_start
                if gap_height >= min_gap_height:
                    center = gap_start + gap_height // 2
                    gaps.append((center, gap_start, y))

        if in_gap:
            gap_height = h - gap_start
            if gap_height >= min_gap_height:
                center = gap_start + gap_height // 2
                gaps.append((center, gap_start, h))

        return gaps

    def detect_text_blocks(self, image, lang=None):
        """
        Detect text blocks and their positions.

        Args:
            image: OpenCV image
            lang: OCR language(s)

        Returns:
            List of dicts with keys: text, x, y, w, h, block_num
        """
        if self.active_engine == "easyocr" and self.easyocr_reader is not None:
            img = self._prepare_image(image, preprocess=False)
            if isinstance(img, Image.Image):
                cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            else:
                cv_img = img

            # detail=1 returns [(bbox, text, prob)]
            read_results = self.easyocr_reader.readtext(cv_img, detail=1, paragraph=True)
            result = []
            for i, (bbox, text, prob) in enumerate(read_results):
                x_coords = [p[0] for p in bbox]
                y_coords = [p[1] for p in bbox]
                x_min, x_max = min(x_coords), max(x_coords)
                y_min, y_max = min(y_coords), max(y_coords)
                
                result.append({
                    "text": text,
                    "x": int(x_min),
                    "y": int(y_min),
                    "w": int(x_max - x_min),
                    "h": int(y_max - y_min),
                    "block_num": i
                })
            return result

        data = self.image_to_data(image, lang=lang, preprocess=False)
        blocks = {}

        n_boxes = len(data["text"])
        for i in range(n_boxes):
            text = str(data["text"][i]).strip()
            if not text or int(data["conf"][i]) < 0:
                continue

            block_num = data["block_num"][i]
            if block_num not in blocks:
                blocks[block_num] = {
                    "text": [],
                    "x_min": data["left"][i],
                    "y_min": data["top"][i],
                    "x_max": data["left"][i] + data["width"][i],
                    "y_max": data["top"][i] + data["height"][i],
                    "block_num": block_num
                }
            else:
                blocks[block_num]["x_min"] = min(
                    blocks[block_num]["x_min"], data["left"][i]
                )
                blocks[block_num]["y_min"] = min(
                    blocks[block_num]["y_min"], data["top"][i]
                )
                blocks[block_num]["x_max"] = max(
                    blocks[block_num]["x_max"],
                    data["left"][i] + data["width"][i]
                )
                blocks[block_num]["y_max"] = max(
                    blocks[block_num]["y_max"],
                    data["top"][i] + data["height"][i]
                )
            blocks[block_num]["text"].append(text)

        result = []
        for block_num, block in sorted(blocks.items()):
            result.append({
                "text": " ".join(block["text"]),
                "x": block["x_min"],
                "y": block["y_min"],
                "w": block["x_max"] - block["x_min"],
                "h": block["y_max"] - block["y_min"],
                "block_num": block_num
            })

        return result

    # ─── Helper Methods ──────────────────────────────────────────────────

    def _prepare_image(self, image, preprocess=True):
        """Convert various image formats to a format suitable for OCR."""
        # If it's a file path
        if isinstance(image, (str, Path)):
            image = cv2.imread(str(image))
            if image is None:
                raise ValueError(f"Could not read image: {image}")

        # If it's a numpy array (OpenCV)
        if isinstance(image, np.ndarray):
            if preprocess:
                image = self.preprocess_for_ocr(image)
            # Convert to PIL for pytesseract
            if len(image.shape) == 3:
                image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            else:
                image = Image.fromarray(image)

        return image


# Singleton instance
_engine = None

def get_ocr_engine():
    """Get the singleton OCR engine instance."""
    global _engine
    if _engine is None:
        _engine = OCREngine()
    return _engine
