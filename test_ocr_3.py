import os, sys, ctypes
from pathlib import Path
import numpy as np

def get_short_path(long_name):
    buffer_size = 256
    buffer = ctypes.create_unicode_buffer(buffer_size)
    get_short_path_name_w = ctypes.windll.kernel32.GetShortPathNameW
    if get_short_path_name_w(long_name, buffer, buffer_size):
        return buffer.value
    return long_name

root_dir = Path(os.getcwd())
paddleocr_models_dir = root_dir / 'tools' / 'paddleocr_models'
safe_parent_dir = get_short_path(str(paddleocr_models_dir.parent))
os.environ['USERPROFILE'] = safe_parent_dir

try:
    from paddleocr import PaddleOCR
    import logging
    logging.getLogger("ppocr").setLevel(logging.WARNING)
    ocr = PaddleOCR(use_angle_cls=False, lang='en', use_gpu=True)
    img_bgr = np.zeros((100, 100, 3), dtype=np.uint8)
    res = ocr.ocr(img_bgr, cls=False)
    print("SUCCESS OCR")
except Exception as e:
    import traceback
    traceback.print_exc()
