"""
Batch Processor — Parallel processing engine for PDF operations.

Features:
- Auto-detects CPU cores and optimal worker count
- ThreadPoolExecutor for parallel OCR scanning
- Cancellation support via cancel flag
- Progress tracking with callbacks
"""

import os
import sys
import threading
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger("PDFEditor")


class BatchProcessor:
    """
    Manages parallel batch processing with cancellation support.

    Usage:
        proc = BatchProcessor()
        proc.start()

        results = proc.parallel_map(
            func=scan_page,
            items=page_list,
            progress_callback=update_ui
        )

        proc.stop()
    """

    def __init__(self, max_workers=None):
        """
        Initialize the batch processor.

        Args:
            max_workers: Max parallel workers. None = auto-detect.
        """
        self._cancelled = threading.Event()
        self._running = False
        self._lock = threading.Lock()

        # Auto-detect optimal worker count
        if max_workers is None:
            max_workers = self._detect_optimal_workers()
        self.max_workers = max_workers

        logger.info(
            f"BatchProcessor: {self.max_workers} workers "
            f"(CPU cores: {os.cpu_count()})"
        )

    @staticmethod
    def _detect_optimal_workers():
        """Auto-detect the optimal number of parallel workers."""
        cpu_count = os.cpu_count() or 1

        # Check available memory (rough heuristic)
        try:
            import psutil
            mem_gb = psutil.virtual_memory().available / (1024 ** 3)
            # Each OCR worker uses ~200-500MB
            mem_workers = max(1, int(mem_gb / 0.5))
        except ImportError:
            # psutil not available, use conservative estimate
            mem_workers = cpu_count

        # Use min of CPU-based and memory-based limits
        # Leave 1-2 cores free for UI responsiveness
        if cpu_count <= 2:
            workers = 1
        elif cpu_count <= 4:
            workers = min(cpu_count - 1, mem_workers)
        else:
            workers = min(cpu_count - 2, mem_workers, 8)

        return max(1, workers)

    @staticmethod
    def get_cpu_info():
        """Get CPU information for display."""
        cpu_count = os.cpu_count() or 1
        info = {
            "cores": cpu_count,
            "platform": sys.platform,
        }
        try:
            import psutil
            mem = psutil.virtual_memory()
            info["ram_total_gb"] = round(mem.total / (1024 ** 3), 1)
            info["ram_available_gb"] = round(mem.available / (1024 ** 3), 1)
            info["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        except ImportError:
            info["ram_total_gb"] = "N/A"
            info["ram_available_gb"] = "N/A"
            info["cpu_percent"] = "N/A"
        return info

    def start(self):
        """Start/reset the processor for a new batch."""
        self._cancelled.clear()
        self._running = True

    def stop(self):
        """Stop the processor."""
        self._running = False

    def cancel(self):
        """Signal cancellation."""
        self._cancelled.set()
        logger.info("BatchProcessor: Cancellation requested")

    @property
    def is_cancelled(self):
        """Check if cancellation was requested."""
        return self._cancelled.is_set()

    def check_cancelled(self):
        """Check and raise if cancelled. Call this in worker functions."""
        if self._cancelled.is_set():
            raise CancelledException("Operation cancelled by user")

    def parallel_map(self, func, items, progress_callback=None):
        """
        Apply func to each item in parallel, with progress tracking.

        Args:
            func: Function to apply. Receives (item, index, total).
                  Should call self.check_cancelled() periodically.
            items: List of items to process.
            progress_callback: Optional callback(completed, total, result).

        Returns:
            List of (index, result) tuples, sorted by index.
            Results may be None for cancelled/failed items.
        """
        total = len(items)
        if total == 0:
            return []

        results = [None] * total
        completed = 0

        # Use single thread if only 1 worker or few items
        effective_workers = min(self.max_workers, total)

        if effective_workers <= 1:
            # Sequential processing
            for i, item in enumerate(items):
                if self.is_cancelled:
                    break
                try:
                    result = func(item, i, total)
                    results[i] = result
                except CancelledException:
                    break
                except Exception as e:
                    logger.warning(f"Item {i} failed: {e}")
                    results[i] = None
                completed += 1
                if progress_callback:
                    progress_callback(completed, total, results[i])
            return list(enumerate(results))

        # Parallel processing
        with ThreadPoolExecutor(max_workers=effective_workers) as executor:
            future_to_idx = {}
            for i, item in enumerate(items):
                if self.is_cancelled:
                    break
                future = executor.submit(func, item, i, total)
                future_to_idx[future] = i

            for future in as_completed(future_to_idx):
                if self.is_cancelled:
                    # Cancel remaining futures
                    for f in future_to_idx:
                        f.cancel()
                    break

                idx = future_to_idx[future]
                try:
                    result = future.result(timeout=120)
                    results[idx] = result
                except CancelledException:
                    # Cancel remaining
                    for f in future_to_idx:
                        f.cancel()
                    break
                except Exception as e:
                    logger.warning(f"Item {idx} failed: {e}")
                    results[idx] = None

                completed += 1
                if progress_callback:
                    progress_callback(completed, total, results[idx])

        return list(enumerate(results))


class CancelledException(Exception):
    """Raised when a batch operation is cancelled."""
    pass


# ═══════════════════════════════════════════════════════════════════════════
#  Shared Singleton — Single processor instance for the entire app
# ═══════════════════════════════════════════════════════════════════════════

_shared_processor = None
_shared_lock = threading.Lock()


def get_shared_processor():
    """
    Get the shared BatchProcessor singleton.
    Thread-safe, lazily initialized.
    """
    global _shared_processor
    if _shared_processor is None:
        with _shared_lock:
            if _shared_processor is None:
                _shared_processor = BatchProcessor()
    return _shared_processor


def get_recommended_workers(task_type="ocr"):
    """
    Get recommended worker count for a specific task type.

    Args:
        task_type: 'render', 'ocr', or 'batch'

    Returns:
        Recommended number of workers
    """
    cpu_count = os.cpu_count() or 1

    if task_type == "render":
        # Render workers — lightweight, more can run
        if cpu_count <= 2:
            return 1
        elif cpu_count <= 4:
            return 2
        elif cpu_count <= 8:
            return 3
        else:
            return min(4, cpu_count - 2)

    elif task_type == "ocr":
        # OCR workers — heavy, fewer needed
        if cpu_count <= 2:
            return 1
        elif cpu_count <= 4:
            return 1
        elif cpu_count <= 8:
            return 2
        else:
            return min(3, cpu_count - 4)

    else:  # 'batch' or generic
        if cpu_count <= 2:
            return 1
        elif cpu_count <= 4:
            return 2
        else:
            return min(cpu_count - 2, 6)

