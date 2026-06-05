import tkinter as tk
from tkinter import ttk, messagebox
import os
import subprocess
import threading
import sys

# Define colors (matching app.py dark theme)
COLORS = {
    "bg_dark": "#1e1e2e",
    "bg_panel": "#252538",
    "bg_card": "#2d2d44",
    "accent": "#7aa2f7",
    "accent_hover": "#89b4fa",
    "text_primary": "#cdd6f4",
    "text_secondary": "#a6adc8",
    "danger": "#f38ba8",
    "success": "#a6e3a1",
    "warning": "#f9e2af",
    "border": "#45475a"
}

class PDFEditorLauncher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF Editor Manager")
        self.geometry("500x550")
        self.configure(bg=COLORS["bg_dark"])
        self.resizable(False, False)
        
        # Center the window
        self.eval('tk::PlaceWindow . center')
        
        self.venv_path = os.path.join(os.getcwd(), "venv")
        self.python_exe = os.path.join(self.venv_path, "Scripts", "python.exe")
        self.site_packages = os.path.join(self.venv_path, "Lib", "site-packages")
        
        self.setup_ui()
        self.check_status()

    def setup_ui(self):
        # Header
        header_frame = tk.Frame(self, bg=COLORS["bg_panel"], height=80)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="PDF EDITOR MANAGER", font=("Segoe UI", 16, "bold"),
                 bg=COLORS["bg_panel"], fg=COLORS["accent"]).pack(pady=(15, 5))
        tk.Label(header_frame, text="Quản lý cài đặt và khởi chạy hệ thống", font=("Segoe UI", 10),
                 bg=COLORS["bg_panel"], fg=COLORS["text_secondary"]).pack()

        # Status Container
        self.status_frame = tk.Frame(self, bg=COLORS["bg_dark"], padx=30, pady=20)
        self.status_frame.pack(fill=tk.BOTH, expand=True)

        # Environment Status
        self.lbl_venv = self.create_status_row("Môi trường lõi (Python Venv):", "Đang kiểm tra...", 0)
        self.btn_setup = self.create_action_button("Cài đặt hệ thống gốc", self.run_setup, 1)

        # EasyOCR Status
        self.lbl_easy = self.create_status_row("EasyOCR (GPU AI):", "Đang kiểm tra...", 2)
        self.btn_easy = self.create_action_button("Cài đặt EasyOCR", self.install_easyocr, 3)

        # PaddleOCR Status
        self.lbl_paddle = self.create_status_row("PaddleOCR (GPU AI):", "Đang kiểm tra...", 4)
        self.btn_paddle = self.create_action_button("Cài đặt PaddleOCR", self.install_paddleocr, 5)

        # Launch Button
        launch_frame = tk.Frame(self, bg=COLORS["bg_dark"], pady=20)
        launch_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.btn_launch = tk.Button(launch_frame, text="🚀 KHỞI ĐỘNG PDF EDITOR", 
                                  font=("Segoe UI", 14, "bold"),
                                  bg=COLORS["accent"], fg="white", 
                                  activebackground=COLORS["accent_hover"], activeforeground="white",
                                  relief=tk.FLAT, pady=10, command=self.launch_app)
        self.btn_launch.pack(fill=tk.X, padx=40)

    def create_status_row(self, title, initial_status, row):
        frame = tk.Frame(self.status_frame, bg=COLORS["bg_dark"])
        frame.pack(fill=tk.X, pady=(15, 5))
        
        tk.Label(frame, text=title, font=("Segoe UI", 11, "bold"), 
                 bg=COLORS["bg_dark"], fg=COLORS["text_primary"]).pack(side=tk.LEFT)
        
        lbl_status = tk.Label(frame, text=initial_status, font=("Segoe UI", 11), 
                              bg=COLORS["bg_dark"], fg=COLORS["text_secondary"])
        lbl_status.pack(side=tk.RIGHT)
        return lbl_status

    def create_action_button(self, text, command, row):
        frame = tk.Frame(self.status_frame, bg=COLORS["bg_dark"])
        frame.pack(fill=tk.X, pady=(0, 10))
        
        btn = tk.Button(frame, text=text, font=("Segoe UI", 9),
                        bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                        activebackground=COLORS["border"], activeforeground="white",
                        relief=tk.FLAT, padx=15, pady=5, command=command)
        btn.pack(side=tk.RIGHT)
        return btn

    def check_status(self):
        # Check Venv
        has_venv = os.path.exists(self.python_exe)
        if has_venv:
            self.lbl_venv.config(text="Đã cài đặt", fg=COLORS["success"])
            self.btn_setup.config(state=tk.DISABLED, text="Hệ thống đã sẵn sàng")
        else:
            self.lbl_venv.config(text="Chưa cài đặt", fg=COLORS["danger"])
            self.btn_setup.config(state=tk.NORMAL)
            self.btn_launch.config(state=tk.DISABLED, bg=COLORS["border"])

        # Check EasyOCR
        has_easyocr = os.path.exists(os.path.join(self.site_packages, "easyocr"))
        if has_easyocr:
            self.lbl_easy.config(text="Đã cài đặt", fg=COLORS["success"])
            self.btn_easy.config(state=tk.DISABLED, text="Đã cài đặt")
        elif not has_venv:
            self.lbl_easy.config(text="Chờ Venv", fg=COLORS["warning"])
            self.btn_easy.config(state=tk.DISABLED)
        else:
            self.lbl_easy.config(text="Chưa cài đặt", fg=COLORS["danger"])
            self.btn_easy.config(state=tk.NORMAL)

        # Check PaddleOCR
        has_paddleocr = os.path.exists(os.path.join(self.site_packages, "paddleocr"))
        if has_paddleocr:
            self.lbl_paddle.config(text="Đã cài đặt", fg=COLORS["success"])
            self.btn_paddle.config(state=tk.DISABLED, text="Đã cài đặt")
        elif not has_venv:
            self.lbl_paddle.config(text="Chờ Venv", fg=COLORS["warning"])
            self.btn_paddle.config(state=tk.DISABLED)
        else:
            self.lbl_paddle.config(text="Chưa cài đặt", fg=COLORS["danger"])
            self.btn_paddle.config(state=tk.NORMAL)
            
        self.after(2000, self.check_status) # Auto-refresh every 2 seconds

    def run_setup(self):
        if not os.path.exists("setup.bat"):
            messagebox.showerror("Lỗi", "Không tìm thấy file setup.bat")
            return
        subprocess.Popen("start cmd /k setup.bat", shell=True)

    def install_easyocr(self):
        cmd = f'start cmd /k "{self.python_exe}" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121 && "{self.python_exe}" -m pip install easyocr && echo. && echo CAI DAT THANH CONG! Vui long tat cua so nay. && pause'
        subprocess.Popen(cmd, shell=True)

    def install_paddleocr(self):
        cmd = f'start cmd /k "{self.python_exe}" -m pip install paddlepaddle-gpu && "{self.python_exe}" -m pip install paddleocr==2.8.1 && echo. && echo CAI DAT THANH CONG! Vui long tat cua so nay. && pause'
        subprocess.Popen(cmd, shell=True)

    def launch_app(self):
        if not os.path.exists("run.bat"):
            messagebox.showerror("Lỗi", "Không tìm thấy file run.bat")
            return
        # Launch run.bat and close launcher
        env = os.environ.copy()
        env.pop('TCL_LIBRARY', None)
        env.pop('TK_LIBRARY', None)
        subprocess.Popen('start run.bat', shell=True, env=env)
        self.destroy()

if __name__ == "__main__":
    app = PDFEditorLauncher()
    app.mainloop()

