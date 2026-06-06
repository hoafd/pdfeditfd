import subprocess
import os
import sys

def main():
    # Get current dir
    if getattr(sys, 'frozen', False):
        current_dir = os.path.dirname(sys.executable)
    else:
        current_dir = os.path.dirname(os.path.abspath(__file__))

    # Path to pythonw and script
    pythonw = os.path.abspath(os.path.join(current_dir, "..", "venv", "Scripts", "python.exe"))
    script = os.path.join(current_dir, "screen_translator.py")

    if not os.path.exists(pythonw):
        import tkinter.messagebox
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        tkinter.messagebox.showerror("Lỗi", "Không tìm thấy môi trường venv của ứng dụng chính! Vui lòng cài đặt trước.")
        sys.exit(1)

    # Launch the script using the main venv
    subprocess.Popen([pythonw, script], cwd=current_dir, creationflags=0x08000000)

if __name__ == "__main__":
    main()
