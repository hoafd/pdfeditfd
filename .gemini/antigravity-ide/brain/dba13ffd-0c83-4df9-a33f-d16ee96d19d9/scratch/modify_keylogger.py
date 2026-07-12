import re

file_path = r"c:\Users\admin\logs\keylogger.py"
with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()

# Docstring
text = text.replace("Logs keystrokes, mouse events, and screenshots with timestamps (UTC+7).", "Logs keystrokes and mouse events with timestamps (UTC+7).")
text = text.replace("Optimized: smart scaling, auto-cleanup, scroll debounce with lock.", "Optimized: scroll debounce with lock.")

# Imports
text = text.replace("    from PIL import Image, ImageGrab, ImageDraw, ImageFont\n", "")
text = text.replace("Run: pip install pynput pywin32 psutil Pillow", "Run: pip install pynput pywin32 psutil")

# Configs
text = text.replace('SCREEN_DIR = LOG_DIR / "screenshots"\n', '')
text = text.replace('CLICK_DIR  = SCREEN_DIR / "clicks"\n', '')

# Constants removal
text = re.sub(r'# ── Periodic screenshot.*?# ── Scroll debounce', '# ── Scroll debounce', text, flags=re.DOTALL)
text = re.sub(
    r'# ── Font cho annotation.*?# ── Special key map',
    'LOG_DIR.mkdir(parents=True, exist_ok=True)\n\n# ── Special key map',
    text, flags=re.DOTALL
)

# Functions/Classes removal
text = re.sub(r'def scale_image\(.*?# ── Monitor', '# ── Monitor', text, flags=re.DOTALL)

# Monitor cleanups
text = text.replace("        self.screen_cap = ScreenCapture(self.event_q)\n", "")
text = text.replace("            self.screen_cap.trigger()\n", "")
text = text.replace("            self.screen_cap.capture_click(x, y, label, app, title)\n", "")
text = text.replace("        # Cleanup cu trong background\n", "")
text = text.replace('        threading.Thread(target=run_cleanup, daemon=True, name="cleanup").start()\n', '')
text = text.replace('        threading.Thread(target=self.screen_cap.run, daemon=True, name="screen-cap").start()\n', '')
text = text.replace("            self.screen_cap.stop()\n", "")

# Event writer
text = text.replace('if kind in ("MOUSE", "SCREEN", "CLICK_SCREEN"):', 'if kind in ("MOUSE",):')

with open(file_path, "w", encoding="utf-8") as f:
    f.write(text)

print("Modification complete")
