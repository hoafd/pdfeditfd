import os
import ctypes
from pathlib import Path

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
    ocr = PaddleOCR(use_angle_cls=False, lang='en', use_gpu=True)
    print("SUCCESS")
except Exception as e:
    print("ERROR: " + str(e))
