"""
PDF Viewer module.
Renders PDF pages and provides navigation, zoom, and thumbnail support.
Designed for use within a CustomTkinter GUI.

Includes BackgroundRenderer for non-blocking, multi-threaded page rendering
with automatic CPU-aware worker scaling and adjacent-page pre-fetching.
"""

import os
import fitz  # PyMuPDF
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, Future
from PIL import Image, ImageTk
from src.utils import logger


# ═══════════════════════════════════════════════════════════════════════════
#  Background Renderer — Thread-safe async page rendering engine
# ═══════════════════════════════════════════════════════════════════════════

class BackgroundRenderer:
    """
    Non-blocking page rendering engine using ThreadPoolExecutor.

    Features:
    - Auto-detects optimal worker count based on CPU cores
    - Thread-safe image cache with Lock
    - Pre-fetches adjacent pages for smooth navigation
    - Cancels stale render tasks when user navigates quickly
    - Priority: active page > pre-fetch pages
    """

    def __init__(self, max_workers=None):
        # Auto-detect workers
        if max_workers is None:
            max_workers = self._detect_optimal_workers()
        self.max_workers = max_workers

        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="PDFRender"
        )

        # Thread-safe cache: (page_num, zoom) -> PIL.Image
        self._cache = {}
        self._cache_lock = threading.Lock()
        
        # Thumbnail cache
        self._thumb_cache = {}
        self._thumb_lock = threading.Lock()
        
        self._cache_max_size, self._thumb_max_size = self._detect_cache_sizes()

        # Pending futures: (page_num, zoom) -> Future
        self._pending = {}
        self._pending_lock = threading.Lock()

        # Generation counter — incremented on document change to invalidate
        self._generation = 0

        logger.info(
            f"BackgroundRenderer: {max_workers} workers "
            f"(CPU cores: {os.cpu_count()})"
        )

    @staticmethod
    def _detect_cache_sizes():
        """Auto-detect optimal cache sizes based on available RAM."""
        try:
            import psutil
            mem_gb = psutil.virtual_memory().available / (1024 ** 3)
            # Base cache size: 50 pages and 200 thumbnails per GB of available RAM
            # Max 500 pages (approx 1GB-2GB RAM) and 2000 thumbnails
            page_cache = min(500, max(50, int(mem_gb * 50)))
            thumb_cache = min(2000, max(200, int(mem_gb * 200)))
            return page_cache, thumb_cache
        except ImportError:
            return 50, 200

    @staticmethod
    def _detect_optimal_workers():
        """Auto-detect optimal number of render workers."""
        cpu_count = os.cpu_count() or 1

        # Check available memory
        try:
            import psutil
            mem_gb = psutil.virtual_memory().available / (1024 ** 3)
            # Each rendered page uses ~5-50MB depending on zoom
            mem_workers = max(1, int(mem_gb / 0.3))
        except ImportError:
            mem_workers = cpu_count

        # Scale by CPU, leave cores for UI + other work
        if cpu_count <= 2:
            render_workers = 1
        elif cpu_count <= 4:
            render_workers = 2
        elif cpu_count <= 8:
            render_workers = 3
        else:
            render_workers = min(4, cpu_count - 2)

        return max(1, min(render_workers, mem_workers))

    def get_worker_info(self):
        """Get info about the renderer for status display."""
        with self._cache_lock:
            cached = len(self._cache)
        with self._pending_lock:
            pending = len(self._pending)
        return {
            "workers": self.max_workers,
            "cached_pages": cached,
            "pending_renders": pending,
            "cpu_cores": os.cpu_count() or 1,
        }

    def invalidate_all(self):
        """Clear all caches (on document change/reload)."""
        self._generation += 1
        self.cancel_pending()
        with self._cache_lock:
            self._cache.clear()
        with self._thumb_lock:
            self._thumb_cache.clear()

    def invalidate_page(self, page_num):
        """Invalidate cache for a specific page (after edit)."""
        with self._cache_lock:
            keys_to_remove = [k for k in self._cache if k[0] == page_num]
            for k in keys_to_remove:
                del self._cache[k]
        with self._thumb_lock:
            keys_to_remove = [k for k in self._thumb_cache if k[0] == page_num]
            for k in keys_to_remove:
                del self._thumb_cache[k]

    def cancel_pending(self):
        """Cancel all pending render tasks."""
        with self._pending_lock:
            for key, future in self._pending.items():
                future.cancel()
            self._pending.clear()

    def get_cached(self, page_num, zoom):
        """Get a page image from cache (non-blocking). Returns None if not cached."""
        cache_key = (page_num, round(zoom, 3))
        with self._cache_lock:
            return self._cache.get(cache_key)

    def render_sync(self, doc, page_num, zoom):
        """
        Render a page synchronously (blocking).
        Used as fallback when async result isn't ready yet.
        """
        if not doc or page_num < 0 or page_num >= doc.page_count:
            return None

        cache_key = (page_num, round(zoom, 3))

        # Check cache first
        with self._cache_lock:
            if cache_key in self._cache:
                return self._cache[cache_key]

        # Render
        img = self._do_render(doc, page_num, zoom)

        # Store in cache
        if img is not None:
            self._put_cache(cache_key, img)

        return img

    def render_async(self, doc, page_num, zoom, root, callback, generation=None):
        """
        Render a page asynchronously in background thread.

        Args:
            doc: PyMuPDF document
            page_num: Page number (0-indexed)
            zoom: Zoom level
            root: Tkinter root (for thread-safe callback via root.after)
            callback: function(page_num, pil_image) called on main thread
            generation: Document generation (to discard stale results)
        """
        if not doc or page_num < 0 or page_num >= doc.page_count:
            return

        if generation is None:
            generation = self._generation

        cache_key = (page_num, round(zoom, 3))

        # Check cache first
        with self._cache_lock:
            cached = self._cache.get(cache_key)
        if cached is not None:
            # Already cached — call callback immediately on main thread
            root.after(0, lambda: callback(page_num, cached))
            return

        # Check if already pending
        with self._pending_lock:
            if cache_key in self._pending:
                return  # Already being rendered

        # Submit render task
        gen = generation

        def _render_task():
            if gen != self._generation:
                return None  # Stale — document changed
            return self._do_render(doc, page_num, zoom)

        future = self._executor.submit(_render_task)

        with self._pending_lock:
            self._pending[cache_key] = future

        def _on_done(fut):
            # Remove from pending
            with self._pending_lock:
                self._pending.pop(cache_key, None)

            if fut.cancelled() or gen != self._generation:
                return

            try:
                img = fut.result()
                if img is not None:
                    self._put_cache(cache_key, img)
                    # Callback on main thread
                    root.after(0, lambda: callback(page_num, img))
            except Exception as e:
                logger.error(f"Async render failed for page {page_num}: {e}")

        future.add_done_callback(_on_done)

    def prefetch_pages(self, doc, current_page, zoom, root, callback,
                       prefetch_range=2):
        """
        Pre-fetch pages adjacent to current_page in background.

        Args:
            doc: PyMuPDF document
            current_page: Currently displayed page
            zoom: Current zoom level
            root: Tkinter root for callbacks
            callback: function(page_num, pil_image)
            prefetch_range: How many pages ahead/behind to pre-fetch
        """
        if not doc:
            return

        total = doc.page_count
        gen = self._generation

        for offset in range(1, prefetch_range + 1):
            for pn in [current_page + offset, current_page - offset]:
                if 0 <= pn < total:
                    self.render_async(doc, pn, zoom, root, callback,
                                      generation=gen)

    def render_thumbnail_sync(self, doc, page_num, max_size=150):
        """Render a thumbnail synchronously."""
        if not doc or page_num < 0 or page_num >= doc.page_count:
            return None

        cache_key = (page_num, max_size)
        with self._thumb_lock:
            if cache_key in self._thumb_cache:
                return self._thumb_cache[cache_key]

        page = doc[page_num]
        zoom = max_size / max(page.rect.width, page.rect.height)
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        with self._thumb_lock:
            if len(self._thumb_cache) >= self._thumb_max_size:
                # Evict oldest entries
                keys = list(self._thumb_cache.keys())
                for k in keys[:len(keys) // 4]:
                    self._thumb_cache.pop(k, None)
            self._thumb_cache[cache_key] = img

        return img

    def shutdown(self):
        """Shutdown the renderer thread pool."""
        self.cancel_pending()
        self._executor.shutdown(wait=False)
        logger.info("BackgroundRenderer shutdown")

    # ─── Internal ────────────────────────────────────────────────────────

    @staticmethod
    def _do_render(doc, page_num, zoom):
        """Actually render a page to PIL Image (runs in worker thread)."""
        try:
            page = doc[page_num]
            mat = fitz.Matrix(zoom * 1.5, zoom * 1.5)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            return img
        except Exception as e:
            logger.error(f"Render error page {page_num}: {e}")
            return None

    def _put_cache(self, cache_key, img):
        """Put an image in cache, evicting old entries if needed."""
        with self._cache_lock:
            if len(self._cache) >= self._cache_max_size:
                # Evict ~25% of oldest entries
                keys = list(self._cache.keys())
                for k in keys[:len(keys) // 4]:
                    self._cache.pop(k, None)
            self._cache[cache_key] = img


# ═══════════════════════════════════════════════════════════════════════════
#  PDF Viewer — Page rendering, navigation, zoom, thumbnails
# ═══════════════════════════════════════════════════════════════════════════

class PDFViewer:
    """
    PDF page renderer and viewer logic.
    Converts PDF pages to images for display in a Tkinter canvas.
    Now backed by BackgroundRenderer for non-blocking rendering.
    """

    def __init__(self):
        self.doc = None
        self.current_page = 0
        self.zoom_level = 1.0
        self.min_zoom = 0.25
        self.max_zoom = 5.0
        self.zoom_step = 0.25

        # Legacy caches (kept for backward compat, but rendering
        # now goes through BackgroundRenderer)
        self._page_images = {}  # Cache rendered pages
        self._thumbnail_cache = {}

        # Background renderer (shared across tabs)
        self.renderer = BackgroundRenderer()

    def set_document(self, doc):
        """Set the PyMuPDF document to view."""
        self.doc = doc
        self.current_page = 0
        self._page_images.clear()
        self._thumbnail_cache.clear()
        self.renderer.invalidate_all()

    @property
    def page_count(self):
        return self.doc.page_count if self.doc else 0

    def get_page_image(self, page_num, zoom=None):
        """
        Render a PDF page as a PIL Image (synchronous).

        Args:
            page_num: Page number (0-indexed)
            zoom: Zoom level (None = current zoom)

        Returns:
            PIL Image of the rendered page
        """
        if not self.doc:
            return None

        if page_num < 0 or page_num >= self.doc.page_count:
            return None

        zoom = zoom or self.zoom_level

        # Use BackgroundRenderer (thread-safe, with cache)
        return self.renderer.render_sync(self.doc, page_num, zoom)

    def get_page_image_async(self, page_num, root, callback, zoom=None):
        """
        Render a PDF page asynchronously. Calls callback(page_num, image)
        on the main thread when done.

        Args:
            page_num: Page number (0-indexed)
            root: Tkinter root for thread-safe callback
            callback: function(page_num, pil_image)
            zoom: Zoom level (None = current zoom)
        """
        if not self.doc:
            return

        zoom = zoom or self.zoom_level
        self.renderer.render_async(
            self.doc, page_num, zoom, root, callback
        )

    def prefetch_adjacent(self, root, callback, prefetch_range=2):
        """Pre-fetch pages adjacent to current page."""
        if not self.doc:
            return
        self.renderer.prefetch_pages(
            self.doc, self.current_page, self.zoom_level,
            root, callback, prefetch_range
        )

    def get_page_photo(self, page_num, zoom=None):
        """
        Get a Tkinter-compatible photo image of a page.

        Args:
            page_num: Page number
            zoom: Zoom level

        Returns:
            ImageTk.PhotoImage
        """
        img = self.get_page_image(page_num, zoom)
        if img is None:
            return None
        return ImageTk.PhotoImage(img)

    def get_thumbnail(self, page_num, max_size=150):
        """
        Get a thumbnail image of a page.

        Args:
            page_num: Page number
            max_size: Maximum dimension (width or height)

        Returns:
            PIL Image thumbnail
        """
        if not self.doc or page_num < 0 or page_num >= self.doc.page_count:
            return None

        return self.renderer.render_thumbnail_sync(
            self.doc, page_num, max_size
        )

    def get_thumbnail_photo(self, page_num, max_size=150):
        """Get a Tkinter PhotoImage thumbnail."""
        img = self.get_thumbnail(page_num, max_size)
        if img is None:
            return None
        return ImageTk.PhotoImage(img)

    # ─── Navigation ──────────────────────────────────────────────────────

    def next_page(self):
        """Go to the next page."""
        if self.doc and self.current_page < self.doc.page_count - 1:
            self.current_page += 1
            return True
        return False

    def prev_page(self):
        """Go to the previous page."""
        if self.doc and self.current_page > 0:
            self.current_page -= 1
            return True
        return False

    def go_to_page(self, page_num):
        """Go to a specific page."""
        if self.doc and 0 <= page_num < self.doc.page_count:
            self.current_page = page_num
            return True
        return False

    def first_page(self):
        """Go to the first page."""
        return self.go_to_page(0)

    def last_page(self):
        """Go to the last page."""
        if self.doc:
            return self.go_to_page(self.doc.page_count - 1)
        return False

    # ─── Zoom ────────────────────────────────────────────────────────────

    def zoom_in(self):
        """Increase zoom level."""
        new_zoom = min(self.zoom_level + self.zoom_step, self.max_zoom)
        if new_zoom != self.zoom_level:
            self.zoom_level = new_zoom
            self._page_images.clear()
            return True
        return False

    def zoom_out(self):
        """Decrease zoom level."""
        new_zoom = max(self.zoom_level - self.zoom_step, self.min_zoom)
        if new_zoom != self.zoom_level:
            self.zoom_level = new_zoom
            self._page_images.clear()
            return True
        return False

    def set_zoom(self, zoom):
        """Set zoom to a specific level."""
        zoom = max(self.min_zoom, min(zoom, self.max_zoom))
        if zoom != self.zoom_level:
            self.zoom_level = zoom
            self._page_images.clear()
            return True
        return False

    def fit_width(self, canvas_width):
        """Calculate zoom to fit page width to canvas."""
        if not self.doc:
            return False

        page = self.doc[self.current_page]
        # Account for 1.5x scale in rendering
        zoom = canvas_width / (page.rect.width * 1.5)
        return self.set_zoom(zoom)

    def fit_page(self, canvas_width, canvas_height):
        """Calculate zoom to fit entire page in canvas."""
        if not self.doc:
            return False

        page = self.doc[self.current_page]
        zoom_w = canvas_width / (page.rect.width * 1.5)
        zoom_h = canvas_height / (page.rect.height * 1.5)
        zoom = min(zoom_w, zoom_h)
        return self.set_zoom(zoom)

    # ─── Page Info ───────────────────────────────────────────────────────

    def get_current_page_info(self):
        """Get info about the current page."""
        if not self.doc:
            return None

        page = self.doc[self.current_page]
        return {
            "page_num": self.current_page,
            "total_pages": self.doc.page_count,
            "width_pt": page.rect.width,
            "height_pt": page.rect.height,
            "width_mm": page.rect.width * 25.4 / 72,
            "height_mm": page.rect.height * 25.4 / 72,
            "rotation": page.rotation,
            "zoom": self.zoom_level,
        }

    def clear_cache(self):
        """Clear all image caches."""
        self._page_images.clear()
        self._thumbnail_cache.clear()
        self.renderer.invalidate_all()

    def canvas_to_pdf_coords(self, canvas_x, canvas_y):
        """
        Convert canvas coordinates to PDF page coordinates.

        Args:
            canvas_x: X position on canvas
            canvas_y: Y position on canvas

        Returns:
            Tuple (pdf_x, pdf_y) in PDF points
        """
        if not self.doc:
            return (0, 0)

        scale = self.zoom_level * 1.5
        pdf_x = canvas_x / scale
        pdf_y = canvas_y / scale

        return (pdf_x, pdf_y)

    def pdf_to_canvas_coords(self, pdf_x, pdf_y):
        """
        Convert PDF page coordinates to canvas coordinates.

        Args:
            pdf_x: X in PDF points
            pdf_y: Y in PDF points

        Returns:
            Tuple (canvas_x, canvas_y)
        """
        scale = self.zoom_level * 1.5
        return (pdf_x * scale, pdf_y * scale)
