import subprocess
import os
import sys

def find_pdfeditfd_root():
    # 1. Kiểm tra nếu file exe đang nằm bên trong thư mục pdfeditfd (app_phu)
    if getattr(sys, 'frozen', False):
        current = os.path.dirname(sys.executable)
    else:
        current = os.path.dirname(os.path.abspath(__file__))
        
    check_dir = current
    while check_dir and check_dir != os.path.dirname(check_dir):
        if os.path.exists(os.path.join(check_dir, "venv", "Scripts", "python.exe")) and os.path.exists(os.path.join(check_dir, "app_phu", "screen_translator.py")):
            return check_dir
        check_dir = os.path.dirname(check_dir)
        
    # 2. Kiểm tra đường dẫn đã lưu trước đó (để tăng tốc)
    appdata = os.getenv('APPDATA')
    config_file = os.path.join(appdata, "pdfeditfd_path.txt")
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                saved_path = f.read().strip()
                if os.path.exists(os.path.join(saved_path, "venv", "Scripts", "python.exe")):
                    return saved_path
        except:
            pass
            
    # 3. Tự động quét toàn bộ User Profile để tìm thư mục pdfeditfd
    import tkinter as tk
    import tkinter.messagebox
    root = tk.Tk()
    root.withdraw()
    
    # Hiển thị thông báo đang tìm kiếm (vì quá trình quét có thể mất 5-10 giây)
    search_win = tk.Toplevel(root)
    search_win.title("Đang dò tìm thư viện...")
    search_win.geometry("350x100")
    search_win.eval('tk::PlaceWindow . center')
    search_win.attributes("-topmost", True)
    tk.Label(search_win, text="Lần đầu chạy: Đang tự động quét tìm\nthư mục gốc 'pdfeditfd' trên máy...\nVui lòng chờ trong giây lát!", font=("Segoe UI", 10)).pack(expand=True)
    search_win.update()
    
    user_profile = os.getenv('USERPROFILE')
    try:
        # Tìm file PDF_Editor_Launcher.exe làm điểm mốc
        cmd = f'dir /s /b "{user_profile}\\PDF_Editor_Launcher.exe"'
        result = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL, text=True, creationflags=0x08000000)
        search_win.destroy()
        if result:
            lines = result.strip().split('\n')
            if lines:
                launcher_path = lines[0].strip()
                root_path = os.path.dirname(launcher_path)
                # Lưu lại để lần sau không phải quét nữa
                try:
                    with open(config_file, "w", encoding="utf-8") as f:
                        f.write(root_path)
                except:
                    pass
                return root_path
    except Exception:
        search_win.destroy()
        pass
    
    tkinter.messagebox.showerror("Lỗi", "Không thể tự động tìm thấy thư mục gốc 'pdfeditfd'! Vui lòng đặt file này vào lại thư mục app_phu hoặc chạy ứng dụng chính trước.")
    sys.exit(1)


def main():
    try:
        root_path = find_pdfeditfd_root()
        if not root_path:
            sys.exit(1)

        # Path to pythonw and script based on root path
        pythonw = os.path.join(root_path, "venv", "Scripts", "pythonw.exe")
        script = os.path.join(root_path, "app_phu", "screen_translator.py")

        if not os.path.exists(pythonw) or not os.path.exists(script):
            import tkinter.messagebox
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            tkinter.messagebox.showerror("Lỗi", f"Thấy thư mục gốc {root_path} nhưng không tìm thấy file script hoặc venv!")
            sys.exit(1)

        # Launch the script using the main venv
        env = os.environ.copy()
        env.pop('TCL_LIBRARY', None)
        env.pop('TK_LIBRARY', None)
        
        log_file = open(os.path.join(os.getenv('USERPROFILE'), "translator_cmd_error.log"), "w", encoding="utf-8")
        p = subprocess.Popen(
            [pythonw, script], 
            cwd=os.path.join(root_path, "app_phu"), 
            stdin=subprocess.DEVNULL,
            stdout=log_file, 
            stderr=subprocess.STDOUT,
            env=env
        )
        # Không cần đợi p.wait() vì pythonw tự ngầm, Launcher có thể tắt luôn.

        log_file.close()
    except Exception as e:
        import traceback
        with open(os.path.join(os.getenv('USERPROFILE'), "launcher_error.log"), "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())

if __name__ == "__main__":
    main()
