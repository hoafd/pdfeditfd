import tkinter as tk
from tkinter import ttk, messagebox
from PIL import ImageGrab
import subprocess
import sys
import os
import threading
import numpy as np

# Auto-install deep-translator if missing
try:
    from deep_translator import GoogleTranslator
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "deep-translator"])
    from deep_translator import GoogleTranslator

# Theme colors
COLORS = {
    "bg_dark": "#1e1e2e",
    "bg_panel": "#252538",
    "accent": "#7aa2f7",
    "text_primary": "#cdd6f4",
}

LANGUAGES = ["Tiếng Anh", "Tiếng Trung", "Tiếng Nhật", "Tiếng Hàn", "Tiếng Pháp/Đức (Latin)"]

class AutoOCREngine:
    def __init__(self, lang_name):
        self.engine_type = None
        self.engine = None
        
        # 1. Try PaddleOCR (Mạnh nhất, đặc biệt cho Tiếng Việt/Trung/Nhật)
        try:
            from paddleocr import PaddleOCR
            import logging
            logging.getLogger("ppocr").setLevel(logging.WARNING)
            
            paddle_lang_map = {
                "Tiếng Anh": "en",
                "Tiếng Trung": "ch",
                "Tiếng Nhật": "japan",
                "Tiếng Hàn": "korean",
                "Tiếng Pháp/Đức (Latin)": "latin"
            }
            lang = paddle_lang_map.get(lang_name, "en")
            self.engine = PaddleOCR(use_angle_cls=False, lang=lang, use_gpu=True)
            self.engine_type = "paddleocr"
            print(f"Loaded PaddleOCR ({lang})")
            return
        except ImportError:
            pass

        # 2. Try EasyOCR (Rất mạnh, hỗ trợ nhiều ngôn ngữ)
        try:
            import easyocr
            easy_lang_map = {
                "Tiếng Anh": ["en"],
                "Tiếng Trung": ["ch_sim", "en"],
                "Tiếng Nhật": ["ja", "en"],
                "Tiếng Hàn": ["ko", "en"],
                "Tiếng Pháp/Đức (Latin)": ["fr", "de", "en"]
            }
            langs = easy_lang_map.get(lang_name, ["en"])
            self.engine = easyocr.Reader(langs, gpu=True)
            self.engine_type = "easyocr"
            print(f"Loaded EasyOCR ({langs})")
            return
        except ImportError:
            pass

        raise Exception("Không tìm thấy lõi AI nào (PaddleOCR/EasyOCR)! Hãy mở Launcher để tải AI.")

    def do_ocr(self, img_np):
        if self.engine_type == "paddleocr":
            img_bgr = img_np[:, :, ::-1] # RGB to BGR
            result = self.engine.ocr(img_bgr, cls=False)
            text_lines = []
            if result and result[0]:
                for line in result[0]:
                    text_lines.append(line[1][0])
            return "\n".join(text_lines)
            
        elif self.engine_type == "easyocr":
            result = self.engine.readtext(img_np)
            text_lines = [r[1] for r in result]
            return "\n".join(text_lines)
            
        return ""


class SnippingOverlay(tk.Toplevel):
    def __init__(self, parent, on_snip):
        super().__init__(parent)
        self.on_snip = on_snip
        self.attributes("-fullscreen", True)
        self.attributes("-alpha", 0.5)
        self.config(cursor="cross")
        self.attributes("-topmost", True)
        
        self.canvas = tk.Canvas(self, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.start_x = None
        self.start_y = None
        self.rect = None
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Escape>", lambda e: self.destroy())
        
    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="#7aa2f7", width=3, fill="white")

    def on_drag(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)
        self.destroy()
        if x2 - x1 > 10 and y2 - y1 > 10:
            self.on_snip(x1, y1, x2, y2)


class ResultWindow(tk.Toplevel):
    def __init__(self, parent, original_text, x, y):
        super().__init__(parent)
        self.title("Kết quả Dịch")
        self.attributes("-topmost", True)
        self.configure(bg=COLORS["bg_dark"])
        
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        win_w, win_h = 450, 350
        
        pos_x = min(x, screen_w - win_w)
        pos_y = min(y, screen_h - win_h)
        self.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        
        # Original Text
        lbl_frame1 = tk.Frame(self, bg=COLORS["bg_dark"])
        lbl_frame1.pack(fill=tk.X, padx=10, pady=(10,0))
        tk.Label(lbl_frame1, text="Bản gốc:", bg=COLORS["bg_dark"], fg=COLORS["text_primary"], font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        tk.Button(lbl_frame1, text="Copy", bg=COLORS["bg_panel"], fg=COLORS["accent"], relief=tk.FLAT, command=lambda: self.copy_text(self.txt_orig.get("1.0", tk.END))).pack(side=tk.RIGHT)

        self.txt_orig = tk.Text(self, height=4, bg=COLORS["bg_panel"], fg=COLORS["text_primary"], font=("Consolas", 10))
        self.txt_orig.pack(fill=tk.X, padx=10, pady=5)
        self.txt_orig.insert(tk.END, original_text)
        
        # Translate Button
        self.btn_trans = tk.Button(self, text="⬇ Dịch sang Tiếng Việt", bg=COLORS["accent"], fg="white", font=("Segoe UI", 10, "bold"), command=self.do_translate, relief=tk.FLAT)
        self.btn_trans.pack(pady=5)
        
        # Translated Text
        lbl_frame2 = tk.Frame(self, bg=COLORS["bg_dark"])
        lbl_frame2.pack(fill=tk.X, padx=10)
        tk.Label(lbl_frame2, text="Bản dịch:", bg=COLORS["bg_dark"], fg=COLORS["text_primary"], font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        tk.Button(lbl_frame2, text="Copy", bg=COLORS["bg_panel"], fg=COLORS["accent"], relief=tk.FLAT, command=lambda: self.copy_text(self.txt_trans.get("1.0", tk.END))).pack(side=tk.RIGHT)

        self.txt_trans = tk.Text(self, height=6, bg=COLORS["bg_panel"], fg=COLORS["text_primary"], font=("Consolas", 10))
        self.txt_trans.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5,10))
        
    def copy_text(self, text):
        self.clipboard_clear()
        self.clipboard_append(text.strip())
        
    def do_translate(self):
        text = self.txt_orig.get("1.0", tk.END).strip()
        if not text:
            return
        self.btn_trans.config(text="Đang dịch...", state=tk.DISABLED)
        
        def trans_thread():
            try:
                translated = GoogleTranslator(source='auto', target='vi').translate(text)
                self.txt_trans.delete("1.0", tk.END)
                self.txt_trans.insert(tk.END, translated)
            except Exception as e:
                messagebox.showerror("Lỗi dịch thuật", str(e))
            finally:
                self.btn_trans.config(text="⬇ Dịch sang Tiếng Việt", state=tk.NORMAL)
                
        threading.Thread(target=trans_thread, daemon=True).start()


class ScreenTranslatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("App Phụ: Dịch Màn Hình")
        self.geometry("260x170")
        self.configure(bg=COLORS["bg_dark"])
        self.attributes("-topmost", True)
        self.eval('tk::PlaceWindow . center')
        
        self.ocr_engine = None
        self.current_lang = None
        
        # UI
        tk.Label(self, text="Ngôn ngữ trên màn hình:", bg=COLORS["bg_dark"], fg=COLORS["text_primary"]).pack(pady=(10, 0))
        
        self.cb_lang = ttk.Combobox(self, values=LANGUAGES, state="readonly")
        self.cb_lang.current(0)
        self.cb_lang.pack(fill=tk.X, padx=20, pady=5)
        
        self.lbl_status = tk.Label(self, text="", bg=COLORS["bg_dark"], fg=COLORS["accent"], font=("Segoe UI", 8))
        self.lbl_status.pack()
        
        self.btn_snip = tk.Button(self, text="✂ Khoanh vùng & Dịch", font=("Segoe UI", 11, "bold"),
                                  bg=COLORS["accent"], fg="white", relief=tk.FLAT,
                                  command=self.start_snip)
        self.btn_snip.pack(expand=True, fill=tk.BOTH, padx=20, pady=(0, 15))
        
    def load_ocr(self, on_done):
        lang_name = self.cb_lang.get()
        
        if self.ocr_engine is None or self.current_lang != lang_name:
            self.btn_snip.config(text="Đang tải AI...", state=tk.DISABLED)
            self.lbl_status.config(text="Khởi động bộ máy nhận diện...")
            self.update()
            
            def load_thread():
                try:
                    self.ocr_engine = AutoOCREngine(lang_name)
                    self.current_lang = lang_name
                    # Back to main thread
                    self.after(0, lambda: self.on_ocr_loaded(True, on_done))
                except Exception as e:
                    err_msg = str(e)
                    self.after(0, lambda msg=err_msg: self.on_ocr_loaded(False, msg))
                    
            threading.Thread(target=load_thread, daemon=True).start()
        else:
            on_done()
            
    def on_ocr_loaded(self, success, result):
        self.btn_snip.config(text="✂ Khoanh vùng & Dịch", state=tk.NORMAL)
        if success:
            self.lbl_status.config(text=f"Đang dùng: {self.ocr_engine.engine_type.upper()}")
            result() # Call on_done
        else:
            self.lbl_status.config(text="Lỗi AI!", fg="red")
            messagebox.showerror("Lỗi OCR", result)
                
    def start_snip(self):
        # Load OCR then snip
        self.load_ocr(self._do_snip)
        
    def _do_snip(self):
        self.withdraw() # Hide main window
        SnippingOverlay(self, self.process_snip)
        
    def process_snip(self, x1, y1, x2, y2):
        self.deiconify() # Show main window again
        self.btn_snip.config(text="Đang đọc chữ...", state=tk.DISABLED)
        self.update()
        
        def process_thread():
            try:
                # Grab the region
                img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
                img_np = np.array(img)
                
                # Run OCR
                full_text = self.ocr_engine.do_ocr(img_np).strip()
                
                self.after(0, lambda: self.on_process_done(True, full_text, x2, y1))
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda msg=err_msg: self.on_process_done(False, msg, 0, 0))
                
        threading.Thread(target=process_thread, daemon=True).start()

    def on_process_done(self, success, text, x, y):
        self.btn_snip.config(text="✂ Khoanh vùng & Dịch", state=tk.NORMAL)
        if success:
            if text:
                ResultWindow(self, text, x, y) # Show window near top-right of snip
            else:
                messagebox.showinfo("Kết quả", "Không tìm thấy chữ nào trong vùng chọn.")
        else:
            messagebox.showerror("Lỗi OCR", text)

if __name__ == "__main__":
    app = ScreenTranslatorApp()
    app.mainloop()
