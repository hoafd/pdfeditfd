import os
import sys
from pathlib import Path
import shutil
import ctypes

def get_short_path(long_name):
    # Returns the Windows 8.3 short path to avoid Unicode errors in Paddle C++ backend
    buffer_size = 256
    buffer = ctypes.create_unicode_buffer(buffer_size)
    get_short_path_name_w = ctypes.windll.kernel32.GetShortPathNameW
    if get_short_path_name_w(long_name, buffer, buffer_size):
        return buffer.value
    return long_name

# Fix Windows console encoding
if sys.stdout is not None:
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr is not None:
    sys.stderr.reconfigure(encoding='utf-8')

# Override USERPROFILE so PaddleOCR saves to pdfeditfd/tools/paddleocr_models
root_dir = Path(__file__).resolve().parent.parent
paddleocr_models_dir = root_dir / 'tools' / 'paddleocr_models'
paddleocr_models_dir.parent.mkdir(parents=True, exist_ok=True)
paddleocr_models_dir.mkdir(exist_ok=True)

# Convert to short path to avoid "NotFound" C++ unicode errors
safe_parent_dir = get_short_path(str(paddleocr_models_dir.parent))
os.environ['USERPROFILE'] = safe_parent_dir

def clear_cache():
    cache_dir = paddleocr_models_dir / '.paddleocr'
    if cache_dir.exists():
        try:
            shutil.rmtree(cache_dir)
            print("Da xoa cache cu bi loi.")
        except Exception as e:
            print(f"Loi khi xoa cache: {e}")

if __name__ == '__main__':
    print('==========================================')
    print('  DONG BO DU LIEU AI CHO SCREEN TRANSLATOR')
    print('==========================================')
    print('Dang tai du lieu tu may chu PaddleOCR. Vui long doi vai phut...\n')
    
    # Import AFTER setting USERPROFILE so it uses the new path
    from paddleocr import PaddleOCR
    import logging
    logging.getLogger('ppocr').setLevel(logging.ERROR) # Hide debug Unicode errors
    
    success = False
    for attempt in range(3):
        try:
            print(f"[{attempt+1}/3] Tien hanh tai hoac kiem tra model Tieng Anh va Tieng Viet...")
            # This automatically downloads det, rec, and cls models if they don't exist
            PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
            PaddleOCR(use_angle_cls=True, lang='vi', show_log=False)
            success = True
            break
        except Exception as e:
            print(f"\nLoi tai du lieu: {e}")
            if "unexpected end of data" in str(e) or "tarfile" in str(e):
                print("Phat hien file tai bi loi mang, dang tien hanh xoa va tai lai...")
                clear_cache()
            elif attempt < 2:
                print("Dang thu lai...")
                
    print('\n==========================================')
    if success:
        print('DA TAI XONG TOAN BO MODEL AI THANH CONG!')
        print(f'Du lieu duoc luu tai: {paddleocr_models_dir}')
    else:
        print('KHONG THE TAI MODEL SAU 3 LAN THU.')
        print('Kiem tra lai ket noi mang cua ban hoac tai thu cong.')
    print('==========================================')
