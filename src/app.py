"""
Main GUI Application for the PDF Editor.
Built with CustomTkinter for a modern, premium look.
Supports multi-tab concurrent page editing with background rendering.
"""

import os
import sys
import json
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
import fitz  # PyMuPDF
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from PIL import Image, ImageTk
from pathlib import Path
from datetime import datetime

try:
    import customtkinter as ctk
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
except ImportError:
    ctk = None

from src.pdf_viewer import PDFViewer
from src.pdf_operations import PDFOperations
from src.pdf_split_smart import SmartPageSplitter
from src.pdf_annotations import PDFAnnotations
from src.pdf_security import PDFSecurity
from src.pdf_text_image import PDFTextImage
from src.utils import (
    logger, format_file_size, generate_output_filename,
    get_output_dir, get_temp_dir
)
from src.i18n import t, set_language, get_language


# ─── Color Palette ──────────────────────────────────────────────────────────

COLORS = {
    "bg_dark": "#0f0f14",
    "bg_main": "#16161d",
    "bg_panel": "#1c1c26",
    "bg_card": "#22222e",
    "bg_hover": "#2a2a38",
    "bg_active": "#333345",
    "accent": "#6c5ce7",
    "accent_light": "#a29bfe",
    "accent_dark": "#4a3db8",
    "success": "#00cec9",
    "warning": "#fdcb6e",
    "danger": "#ff6b6b",
    "text_primary": "#e8e8f0",
    "text_secondary": "#9090a8",
    "text_dim": "#5a5a72",
    "border": "#2a2a3a",
    "border_light": "#3a3a4e",
    "highlight_yellow": "#ffeaa7",
    "highlight_green": "#55efc4",
    "highlight_blue": "#74b9ff",
    "highlight_pink": "#fd79a8",
    "canvas_bg": "#262633",
}


# ─── PageTab: Per-tab state for multi-page editing ───────────────────────

class PageTab:
    """Holds per-tab state for multi-page concurrent editing."""

    _id_counter = 0

    def __init__(self, page_num, parent_frame):
        PageTab._id_counter += 1
        self.id = PageTab._id_counter
        self.page_num = page_num
        self.zoom_level = 1.0
        self.split_mode = False
        self.split_line_y = None
        self.scroll_x = 0.0
        self.scroll_y = 0.0
        self._photo_image = None  # Keep reference for Tk

        # Each tab has its own canvas + scrollbars inside a frame
        self.frame = tk.Frame(parent_frame, bg=COLORS["bg_dark"])

        self.h_scroll = tk.Scrollbar(self.frame, orient=tk.HORIZONTAL)
        self.v_scroll = tk.Scrollbar(self.frame, orient=tk.VERTICAL)

        self.canvas = tk.Canvas(
            self.frame,
            bg=COLORS["canvas_bg"],
            highlightthickness=0,
            xscrollcommand=self.h_scroll.set,
            yscrollcommand=self.v_scroll.set,
            cursor="arrow"
        )

        self.h_scroll.config(command=self.canvas.xview)
        self.v_scroll.config(command=self.canvas.yview)

        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    @property
    def label(self):
        return f"Page {self.page_num + 1}"

    def show(self):
        """Show this tab's frame."""
        self.frame.pack(fill=tk.BOTH, expand=True)

    def hide(self):
        """Hide this tab's frame."""
        self.frame.pack_forget()

    def save_scroll_pos(self):
        """Save current scroll position."""
        try:
            self.scroll_x = self.canvas.xview()[0]
            self.scroll_y = self.canvas.yview()[0]
        except Exception:
            pass

    def restore_scroll_pos(self):
        """Restore saved scroll position."""
        try:
            self.canvas.xview_moveto(self.scroll_x)
            self.canvas.yview_moveto(self.scroll_y)
        except Exception:
            pass

    def destroy(self):
        """Destroy this tab's widgets."""
        self._photo_image = None
        self.frame.destroy()


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class PDFEditorApp:
    """Main PDF Editor Application with CustomTkinter GUI."""

    def __init__(self, root):
        self.root = root
        self.root.title("✨ PDF Editor Pro - Offline Edition")
        
        # Set app icon
        icon_path = resource_path(os.path.join("assets", "icon.ico"))
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception as e:
                logger.warning(f"Could not load icon: {e}")
        self.root.geometry("1400x850")
        self.root.minsize(1000, 600)

        # Configure dark theme for the root
        self.root.configure(bg=COLORS["bg_dark"])

        # Core components
        self.viewer = PDFViewer()
        self.operations = PDFOperations()
        self.splitter = SmartPageSplitter()
        self.view_mode = "continuous"
        self._continuous_layouts = []
        self._continuous_images = {}
        self.annotations = PDFAnnotations()
        self.security = PDFSecurity()
        self.text_image = PDFTextImage()

        # State
        self.file_path = None
        self.doc = None
        self.current_tool = None  # 'select', 'highlight', 'draw', etc.
        self.drawing_points = []
        self.split_mode = False
        self.split_line_y = None
        
        self.multi_split_mode = False
        self.multi_split_points = []  # List of y coordinates in pixels
        self.multi_split_pdf_points = [] # List of y coordinates in PDF points

        self._photo_image = None  # Keep reference
        self._thumbnail_photos = []  # Keep references

        # ─── Selection state ─────────────────────────────────────────
        self.selected_pages = set()  # Set of selected page indices (0-indexed)

        # ─── Multi-tab state ─────────────────────────────────────────
        self._tabs = []           # List of PageTab objects
        self._active_tab = None   # Currently active PageTab
        self._max_tabs = 8        # Max simultaneous tabs
        self._tab_buttons = {}    # tab.id -> button widget

        # ─── Background task tracking ────────────────────────────────
        self._bg_tasks = 0        # Number of running background tasks
        self._bg_lock = threading.Lock()
        self._bg_executor = ThreadPoolExecutor(
            max_workers=max(1, (os.cpu_count() or 2) - 1),
            thread_name_prefix="PDFBgOp"
        )

        # Drag-to-pan state
        self._pan_start_x = 0
        self._pan_start_y = 0
        self._is_panning = False

        # Recent files
        self._recent_files = self._load_recent_files()

        # Undo/Redo
        self._undo_stack = []
        self._redo_stack = []

        # Build the UI
        self._build_ui()
        self._bind_shortcuts()
        self._setup_drag_drop()

        logger.info(
            f"PDF Editor started — "
            f"render workers: {self.viewer.renderer.max_workers}, "
            f"bg workers: {self._bg_executor._max_workers}"
        )

    # ═══════════════════════════════════════════════════════════════════════
    #  UI Construction
    # ═══════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        """Build the complete user interface."""
        # ─── Top Menu Bar ────────────────────────────────────────────
        self._build_menu()

        # ─── Main toolbar ────────────────────────────────────────────
        self._build_toolbar()

        # ─── Main content area ───────────────────────────────────────
        self.main_frame = tk.Frame(self.root, bg=COLORS["bg_dark"])
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Sidebar (Thumbnails)
        self._build_sidebar()

        # Canvas area (PDF display)
        self._build_canvas_area()

        # ─── Status bar ──────────────────────────────────────────────
        self._build_status_bar()

    def _build_menu(self):
        """Build the menu bar."""
        menubar = tk.Menu(self.root, bg=COLORS["bg_panel"],
                          fg=COLORS["text_primary"],
                          activebackground=COLORS["accent"],
                          activeforeground="white",
                          relief=tk.FLAT, bd=0)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0,
                            bg=COLORS["bg_card"],
                            fg=COLORS["text_primary"],
                            activebackground=COLORS["accent"])
        file_menu.add_command(label=t("file_open"),
                              command=self.open_file, accelerator="Ctrl+O")
        file_menu.add_command(label=t("file_save"),
                              command=self.save_file, accelerator="Ctrl+S")
        file_menu.add_separator()
        # Recent files submenu
        self.recent_menu = tk.Menu(file_menu, tearoff=0,
                                   bg=COLORS["bg_card"],
                                   fg=COLORS["text_primary"],
                                   activebackground=COLORS["accent"])
        file_menu.add_cascade(label=t("file_recent"), menu=self.recent_menu)
        self._update_recent_menu()
        file_menu.add_separator()
        file_menu.add_command(label=t("file_merge"),
                              command=self.merge_pdfs)
        file_menu.add_command(label=t("file_split_pages"),
                              command=self.split_by_pages_dialog)
        file_menu.add_command(label=t("file_split_every_n"),
                              command=self.split_every_n_pages_dialog)
        file_menu.add_command(label=t("file_compress"),
                              command=self.compress_pdf)
        file_menu.add_separator()
        file_menu.add_command(label=t("file_export_img"),
                              command=self.export_page_as_image)
        file_menu.add_command(label=t("file_print"),
                              command=self.print_pdf, accelerator="Ctrl+P")
        file_menu.add_separator()
        file_menu.add_command(label=t("file_encrypt"),
                              command=self.encrypt_pdf_dialog)
        file_menu.add_command(label=t("file_decrypt"),
                              command=self.decrypt_pdf_dialog)
        file_menu.add_separator()
        file_menu.add_command(label=t("file_props"),
                              command=self.show_metadata_dialog)
        file_menu.add_separator()
        file_menu.add_command(label=t("file_exit"),
                              command=self.root.quit)
        menubar.add_cascade(label=t("menu_file"), menu=file_menu)

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0,
                            bg=COLORS["bg_card"],
                            fg=COLORS["text_primary"],
                            activebackground=COLORS["accent"])
        edit_menu.add_command(label=t("edit_undo"),
                              command=self.undo, accelerator="Ctrl+Z")
        edit_menu.add_command(label=t("edit_redo"),
                              command=self.redo, accelerator="Ctrl+Y")
        edit_menu.add_separator()
        edit_menu.add_command(label=t("edit_find"),
                              command=self.find_text_dialog, accelerator="Ctrl+F")
        edit_menu.add_command(label=t("edit_copy"),
                              command=self.copy_page_text, accelerator="Ctrl+C")
        edit_menu.add_command(label=t("edit_goto"),
                              command=self.goto_page_dialog, accelerator="Ctrl+G")
        edit_menu.add_separator()
        edit_menu.add_command(label=t("edit_rot_cw"),
                              command=lambda: self.rotate_current(90), accelerator="R")
        edit_menu.add_command(label=t("edit_rot_ccw"),
                              command=lambda: self.rotate_current(-90))
        edit_menu.add_command(label=t("edit_rot_180"),
                              command=lambda: self.rotate_current(180))
        edit_menu.add_separator()
        edit_menu.add_command(label=t("edit_del_page"),
                              command=self.delete_current_page, accelerator="Del")
        edit_menu.add_command(label=t("edit_extract_page"),
                              command=self.extract_current_page)
        edit_menu.add_separator()
        edit_menu.add_command(label=t("edit_insert_blank_before"),
                              command=self.insert_blank_page_before)
        edit_menu.add_command(label=t("edit_insert_blank_after"),
                              command=self.insert_blank_page_after)
        menubar.add_cascade(label=t("menu_edit"), menu=edit_menu)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0,
                             bg=COLORS["bg_card"],
                             fg=COLORS["text_primary"],
                             activebackground=COLORS["accent"])
        tools_menu.add_command(label=t("tools_split_y"),
                               command=self.smart_split_y_dialog)
        tools_menu.add_command(label=t("tools_split_text"),
                               command=self.smart_split_text_dialog)
        tools_menu.add_command(label=t("tools_split_auto"),
                               command=self.smart_split_auto)
        tools_menu.add_separator()
        tools_menu.add_command(label=t("tools_add_text"),
                               command=self.add_text_dialog)
        tools_menu.add_command(label=t("tools_add_img"),
                               command=self.add_image_dialog)
        tools_menu.add_command(label=t("tools_add_wm"),
                               command=self.add_watermark_dialog)
        tools_menu.add_command(label=t("tools_add_page_num"),
                               command=self.add_page_numbers_dialog)
        tools_menu.add_separator()
        tools_menu.add_command(label=t("tools_extract_text"),
                               command=self.extract_text_dialog)
        tools_menu.add_command(label=t("tools_extract_img"),
                               command=self.extract_images)
        tools_menu.add_command(label=t("tools_ocr"),
                               command=self.ocr_text_dialog)
        menubar.add_cascade(label=t("menu_tools"), menu=tools_menu)

        # Interactive Split menu
        split_menu = tk.Menu(menubar, tearoff=0,
                             bg=COLORS["bg_card"],
                             fg=COLORS["text_primary"],
                             activebackground=COLORS["accent"])
        split_menu.add_command(
            label=t("split_interactive"),
            command=self.enable_split_mode
        )
        split_menu.add_command(
            label=t("split_pct"),
            command=self.smart_split_percentage_dialog
        )
        split_menu.add_command(
            label=t("file_split_every_n"),
            command=self.split_every_n_pages_dialog
        )
        split_menu.add_command(
            label=t("split_all_y"),
            command=self.split_all_pages_dialog
        )
        menubar.add_cascade(label=t("menu_split"), menu=split_menu)

        # Batch Operations menu
        batch_menu = tk.Menu(menubar, tearoff=0,
                             bg=COLORS["bg_card"],
                             fg=COLORS["text_primary"],
                             activebackground=COLORS["accent"])
        batch_menu.add_command(
            label=t("batch_rot"),
            command=self.batch_rotate_dialog
        )
        batch_menu.add_command(
            label=t("batch_del"),
            command=self.batch_delete_dialog
        )
        batch_menu.add_command(
            label=t("batch_extract"),
            command=self.batch_extract_dialog
        )
        batch_menu.add_separator()
        batch_menu.add_command(
            label=t("batch_split_y"),
            command=self.split_all_pages_dialog
        )
        batch_menu.add_command(
            label=t("batch_split_pct"),
            command=self.batch_split_percentage_dialog
        )
        batch_menu.add_command(
            label=t("batch_split_ocr"),
            command=self.batch_split_ocr_dialog
        )
        batch_menu.add_command(
            label=t("batch_crop_ocr"),
            command=self.batch_crop_between_texts_dialog
        )
        batch_menu.add_separator()
        batch_menu.add_command(
            label=t("batch_wm"),
            command=self.add_watermark_dialog
        )
        batch_menu.add_command(
            label=t("batch_page_num"),
            command=self.add_page_numbers_dialog
        )
        batch_menu.add_separator()
        batch_menu.add_command(
            label=t("batch_export_img"),
            command=self.batch_export_images_dialog
        )
        menubar.add_cascade(label=t("menu_batch"), menu=batch_menu)

        # Help
        help_menu = tk.Menu(menubar, tearoff=0,
                            bg=COLORS["bg_card"],
                            fg=COLORS["text_primary"],
                            activebackground=COLORS["accent"])
        help_menu.add_command(label=t("help_about"),
                              command=self.show_about)
        help_menu.add_command(label=t("help_shortcuts"),
                              command=self.show_shortcuts)
        help_menu.add_separator()
        help_menu.add_command(label="📖 Hướng dẫn sử dụng",
                              command=self.show_user_manual)
        help_menu.add_command(label="🔍 OCR Info & GPU",
                              command=self.show_ocr_info)
        menubar.add_cascade(label=t("menu_help"), menu=help_menu)

        # Language menu
        lang_menu = tk.Menu(menubar, tearoff=0,
                            bg=COLORS["bg_card"],
                            fg=COLORS["text_primary"],
                            activebackground=COLORS["accent"])
        lang_menu.add_command(label="English", command=lambda: self.change_language("en"))
        lang_menu.add_command(label="Tiếng Việt", command=lambda: self.change_language("vi"))
        menubar.add_cascade(label=t("menu_language"), menu=lang_menu)

        self.root.config(menu=menubar)

    def change_language(self, lang):
        if lang != get_language():
            set_language(lang)
            messagebox.showinfo("Restart Required", "Language changed. Please restart the application to apply changes.\nNgôn ngữ đã được thay đổi. Vui lòng khởi động lại ứng dụng.")

    def _build_toolbar(self):
        """Build the top toolbar with quick-access buttons."""
        toolbar = tk.Frame(self.root, bg=COLORS["bg_panel"], height=48)
        toolbar.pack(fill=tk.X, padx=0, pady=0)
        toolbar.pack_propagate(False)

        # Inner padding
        inner = tk.Frame(toolbar, bg=COLORS["bg_panel"])
        inner.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        btn_style = {
            "bg": COLORS["bg_card"],
            "fg": COLORS["text_primary"],
            "activebackground": COLORS["accent"],
            "activeforeground": "white",
            "relief": tk.FLAT,
            "bd": 0,
            "padx": 12,
            "pady": 4,
            "font": ("Segoe UI", 10),
            "cursor": "hand2",
        }

        # File buttons
        tk.Button(inner, text="📂 Mở", command=self.open_file,
                  **btn_style).pack(side=tk.LEFT, padx=2)
        tk.Button(inner, text="💾 Lưu", command=self.save_file,
                  **btn_style).pack(side=tk.LEFT, padx=2)
        tk.Button(inner, text="📄 Gộp", command=self.merge_pdfs,
                  **btn_style).pack(side=tk.LEFT, padx=2)
        tk.Button(inner, text="✂️ Tách", command=self.split_by_pages_dialog,
                  **btn_style).pack(side=tk.LEFT, padx=2)

        # Separator
        sep1 = tk.Frame(inner, bg=COLORS["border"], width=2, height=30)
        sep1.pack(side=tk.LEFT, padx=8, pady=4)

        # Navigation
        tk.Button(inner, text="⏮", command=self.first_page,
                  **btn_style).pack(side=tk.LEFT, padx=1)
        tk.Button(inner, text="◀", command=self.prev_page,
                  **btn_style).pack(side=tk.LEFT, padx=1)

        self.page_entry_var = tk.StringVar(value="0/0")
        page_entry = tk.Entry(inner, textvariable=self.page_entry_var,
                              bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                              insertbackground=COLORS["text_primary"],
                              relief=tk.FLAT, width=10, justify=tk.CENTER,
                              font=("Segoe UI", 10))
        page_entry.pack(side=tk.LEFT, padx=4)
        page_entry.bind("<Return>", self._on_page_entry)

        tk.Button(inner, text="▶", command=self.next_page,
                  **btn_style).pack(side=tk.LEFT, padx=1)
        tk.Button(inner, text="⏭", command=self.last_page,
                  **btn_style).pack(side=tk.LEFT, padx=1)

        # Separator
        sep2 = tk.Frame(inner, bg=COLORS["border"], width=2, height=30)
        sep2.pack(side=tk.LEFT, padx=8, pady=4)

        # Zoom
        tk.Button(inner, text="🔍−", command=self.zoom_out,
                  **btn_style).pack(side=tk.LEFT, padx=1)

        self.zoom_var = tk.StringVar(value="100%")
        zoom_label = tk.Label(inner, textvariable=self.zoom_var,
                              bg=COLORS["bg_panel"],
                              fg=COLORS["accent_light"],
                              font=("Segoe UI", 10, "bold"), width=6)
        zoom_label.pack(side=tk.LEFT, padx=4)

        tk.Button(inner, text="🔍+", command=self.zoom_in,
                  **btn_style).pack(side=tk.LEFT, padx=1)
        tk.Button(inner, text="Vừa trang", command=self.fit_width,
                  **btn_style).pack(side=tk.LEFT, padx=2)

        # Separator
        sep3 = tk.Frame(inner, bg=COLORS["border"], width=2, height=30)
        sep3.pack(side=tk.LEFT, padx=8, pady=4)
        
        # View Mode Toggle
        self._view_mode_btn = tk.Button(inner, text="📜 Cuộn liên tục", command=self.toggle_view_mode,
                                        bg=COLORS["accent"], fg="white", activebackground=COLORS["accent"],
                                        activeforeground="white", relief=tk.FLAT, bd=0, padx=12, pady=4,
                                        font=("Segoe UI", 10, "bold"), cursor="hand2")
        self._view_mode_btn.pack(side=tk.LEFT, padx=2)

        # Quick tools
        split_btn_style = btn_style.copy()
        split_btn_style["bg"] = COLORS["accent_dark"]
        split_btn_style["fg"] = "white"

        tk.Button(inner, text="✂️ Cắt Y",
                  command=self.smart_split_y_dialog,
                  **split_btn_style).pack(side=tk.LEFT, padx=2)
        tk.Button(inner, text="🔍 Cắt OCR",
                  command=self.smart_split_text_dialog,
                  **split_btn_style).pack(side=tk.LEFT, padx=2)
        tk.Button(inner, text="🖱️ Click Cắt",
                  command=self.enable_split_mode,
                  **split_btn_style).pack(side=tk.LEFT, padx=2)
        tk.Button(inner, text="✂️ Cắt nhiều",
                  command=self.enable_multi_split_mode,
                  **split_btn_style).pack(side=tk.LEFT, padx=2)

        # Separator
        sep4 = tk.Frame(inner, bg=COLORS["border"], width=2, height=30)
        sep4.pack(side=tk.LEFT, padx=8, pady=4)

        tk.Button(inner, text="🔄 Xoay",
                  command=lambda: self.rotate_current(90),
                  **btn_style).pack(side=tk.LEFT, padx=2)
        tk.Button(inner, text="🗑️ Xóa",
                  command=self.delete_current_page,
                  **btn_style).pack(side=tk.LEFT, padx=2)

    def _build_sidebar(self):
        """Build the left sidebar with page thumbnails."""
        self.sidebar = tk.Frame(self.main_frame, bg=COLORS["bg_panel"],
                                width=180)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=0, pady=0)
        self.sidebar.pack_propagate(False)

        # Sidebar header
        header_frame = tk.Frame(self.sidebar, bg=COLORS["bg_panel"])
        header_frame.pack(fill=tk.X, pady=(8, 0))
        
        header = tk.Label(header_frame, text="📄 " + t("sb_thumbnails"),
                          bg=COLORS["bg_panel"],
                          fg=COLORS["accent_light"],
                          font=("Segoe UI", 11, "bold"),
                          anchor="w", padx=12)
        header.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Batch Selection Toolbar
        sel_toolbar = tk.Frame(self.sidebar, bg=COLORS["bg_panel"])
        sel_toolbar.pack(fill=tk.X, padx=8, pady=(4, 8))
        
        row1 = tk.Frame(sel_toolbar, bg=COLORS["bg_panel"])
        row1.pack(fill=tk.X, pady=(0, 2))
        
        row2 = tk.Frame(sel_toolbar, bg=COLORS["bg_panel"])
        row2.pack(fill=tk.X)
        
        btn_font = ("Segoe UI", 8)
        
        # Row 1: All, Odd, Even
        tk.Button(row1, text=t("sb_all"), command=self._select_all,
                  bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                  relief=tk.FLAT, font=btn_font).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
        tk.Button(row1, text=t("sb_odd"), command=self._select_odd,
                  bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                  relief=tk.FLAT, font=btn_font).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
        tk.Button(row1, text=t("sb_even"), command=self._select_even,
                  bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                  relief=tk.FLAT, font=btn_font).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
                  
        # Row 2: Custom, Clear
        tk.Button(row2, text=t("sb_custom"), command=self._select_custom_dialog,
                  bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                  relief=tk.FLAT, font=btn_font).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
        tk.Button(row2, text=t("sb_clear"), command=self._clear_selection,
                  bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
                  relief=tk.FLAT, font=btn_font).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)

        # Scrollable thumbnail list
        thumb_container = tk.Frame(self.sidebar, bg=COLORS["bg_panel"])
        thumb_container.pack(fill=tk.BOTH, expand=True)

        self.thumb_canvas = tk.Canvas(thumb_container,
                                      bg=COLORS["bg_panel"],
                                      highlightthickness=0, bd=0)
        thumb_scroll = tk.Scrollbar(thumb_container,
                                     orient=tk.VERTICAL,
                                     command=self.thumb_canvas.yview)
        self.thumb_inner = tk.Frame(self.thumb_canvas,
                                     bg=COLORS["bg_panel"])

        self.thumb_inner.bind(
            "<Configure>",
            lambda e: self.thumb_canvas.configure(
                scrollregion=self.thumb_canvas.bbox("all")
            )
        )

        self.thumb_canvas.create_window(
            (0, 0), window=self.thumb_inner, anchor="nw"
        )
        self.thumb_canvas.configure(yscrollcommand=thumb_scroll.set)

        self.thumb_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        thumb_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Mouse wheel scroll for thumbnails
        self.thumb_canvas.bind_all(
            "<MouseWheel>",
            self._on_mousewheel_sidebar, add="+"
        )

    def _build_canvas_area(self):
        """Build the main canvas area with tab bar for multi-page editing."""
        self._canvas_outer = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
        self._canvas_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ─── Tab Bar ──────────────────────────────────────────────────
        self._tab_bar = tk.Frame(
            self._canvas_outer, bg=COLORS["bg_panel"], height=32
        )
        self._tab_bar.pack(fill=tk.X, side=tk.TOP)
        self._tab_bar.pack_propagate(False)

        self._tab_bar_inner = tk.Frame(
            self._tab_bar, bg=COLORS["bg_panel"]
        )
        self._tab_bar_inner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # "+" button to open a new tab
        self._tab_add_btn = tk.Button(
            self._tab_bar, text=" + ",
            command=self._open_new_tab_dialog,
            bg=COLORS["bg_hover"], fg=COLORS["accent_light"],
            activebackground=COLORS["accent"],
            activeforeground="white",
            font=("Segoe UI", 10, "bold"),
            relief=tk.FLAT, padx=6, cursor="hand2", bd=0
        )
        self._tab_add_btn.pack(side=tk.RIGHT, padx=4, pady=2)

        # Tab bar is hidden until a document is opened
        self._tab_bar.pack_forget()

        # ─── Tab Container (hosts PageTab frames) ─────────────────────
        self._tab_container = tk.Frame(
            self._canvas_outer, bg=COLORS["bg_dark"]
        )
        self._tab_container.pack(fill=tk.BOTH, expand=True)

        # ─── Default canvas (for welcome screen before any tab) ───────
        self.canvas = tk.Canvas(
            self._tab_container,
            bg=COLORS["canvas_bg"],
            highlightthickness=0,
            cursor="arrow"
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self._default_canvas = self.canvas  # Keep reference

        # Context menu (built once, reused on active canvas)
        self._build_context_menu()

        # Welcome message
        self._show_welcome()

    def _bind_canvas_events(self, canvas):
        """Bind all interaction events to a canvas (tab canvas or default)."""
        canvas.bind("<ButtonPress-1>", self._on_canvas_click)
        canvas.bind("<Motion>", self._on_canvas_motion)
        canvas.bind("<Configure>", self._on_canvas_resize)

        # Mouse wheel scroll (vertical)
        canvas.bind("<MouseWheel>", self._on_canvas_mousewheel)
        canvas.bind("<Button-4>",
                     lambda e: self._on_canvas_mousewheel_linux(e, 1))
        canvas.bind("<Button-5>",
                     lambda e: self._on_canvas_mousewheel_linux(e, -1))

        # Ctrl+Wheel = Zoom
        canvas.bind("<Control-MouseWheel>",
                     self._on_canvas_ctrl_mousewheel)

        # Shift+Wheel = Horizontal scroll
        canvas.bind("<Shift-MouseWheel>",
                     self._on_canvas_shift_mousewheel)

        # Middle-click drag to pan
        canvas.bind("<ButtonPress-2>", self._on_pan_start)
        canvas.bind("<B2-Motion>", self._on_pan_move)
        canvas.bind("<ButtonRelease-2>", self._on_pan_end)

        # Right-click drag to pan / context menu
        canvas.bind("<ButtonPress-3>",
                     self._on_right_click_or_pan_start)
        canvas.bind("<B3-Motion>", self._on_pan_move)
        canvas.bind("<ButtonRelease-3>",
                     self._on_right_click_or_pan_end)

    def _build_context_menu(self):
        """Build right-click context menu."""
        self.context_menu = tk.Menu(
            self.canvas, tearoff=0,
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            activebackground=COLORS["accent"],
            activeforeground="white",
            relief=tk.FLAT, bd=1
        )
        self.context_menu.add_command(
            label="🔍+ Zoom In", command=self.zoom_in, accelerator="Ctrl+=")
        self.context_menu.add_command(
            label="🔍− Zoom Out", command=self.zoom_out, accelerator="Ctrl+-")
        self.context_menu.add_command(
            label="↔ Fit Width", command=self.fit_width)
        self.context_menu.add_command(
            label="⊞ Fit Page", command=self.fit_page)
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="◀ Previous Page", command=self.prev_page, accelerator="←")
        self.context_menu.add_command(
            label="▶ Next Page", command=self.next_page, accelerator="→")
        self.context_menu.add_command(
            label="🔢 Go to Page...", command=self.goto_page_dialog, accelerator="Ctrl+G")
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="🔄 Rotate 90° CW", command=lambda: self.rotate_current(90))
        self.context_menu.add_command(
            label="🔄 Rotate 90° CCW", command=lambda: self.rotate_current(-90))
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="✂️ Smart Split (Y)", command=self.smart_split_y_dialog)
        self.context_menu.add_command(
            label="🔍 Smart Split (OCR)", command=self.smart_split_text_dialog)
        self.context_menu.add_command(
            label="🖱️ Click to Split", command=self.enable_split_mode)
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="📋 Copy Page Text", command=self.copy_page_text)
        self.context_menu.add_command(
            label="🔍 Find Text...", command=self.find_text_dialog)
        self.context_menu.add_command(
            label="🖼️ Export Page as Image...", command=self.export_page_as_image)
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="📝 Add Text...", command=self.add_text_dialog)
        self.context_menu.add_command(
            label="🖼️ Add Image...", command=self.add_image_dialog)
        self.context_menu.add_command(
            label="💧 Add Watermark...", command=self.add_watermark_dialog)
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="📑 Open in New Tab",
            command=lambda: self._open_page_in_new_tab(
                self.viewer.current_page))
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="🗑️ Delete Page", command=self.delete_current_page)
        self.context_menu.add_command(
            label="📋 Extract Page", command=self.extract_current_page)

    def _build_status_bar(self):
        """Build the bottom status bar with tab/CPU/progress info."""
        self.status_bar = tk.Frame(self.root, bg=COLORS["bg_panel"], height=30)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_bar.pack_propagate(False)

        self.status_inner = tk.Frame(self.status_bar, bg=COLORS["bg_panel"])
        self.status_inner.pack(fill=tk.BOTH, expand=True, padx=10)

        # Left: status message
        self.status_var = tk.StringVar(
            value="Ready — Open a PDF file to begin"
        )
        status_label = tk.Label(
            self.status_inner, textvariable=self.status_var,
            bg=COLORS["bg_panel"], fg=COLORS["text_secondary"],
            font=("Segoe UI", 9), anchor="w"
        )
        status_label.pack(side=tk.LEFT)

        # Right: file info
        self.file_info_var = tk.StringVar(value="")
        file_info_label = tk.Label(
            self.status_inner, textvariable=self.file_info_var,
            bg=COLORS["bg_panel"], fg=COLORS["text_dim"],
            font=("Segoe UI", 9), anchor="e"
        )
        file_info_label.pack(side=tk.RIGHT)

        # Right: CPU/tab info
        self._worker_info_var = tk.StringVar(value="")
        worker_label = tk.Label(
            self.status_inner, textvariable=self._worker_info_var,
            bg=COLORS["bg_panel"], fg=COLORS["accent_light"],
            font=("Segoe UI", 8), anchor="e"
        )
        worker_label.pack(side=tk.RIGHT, padx=(0, 12))

        # Progress bar (hidden by default)
        self._progress_var = tk.DoubleVar(value=0)
        self._progress_bar = ttk.Progressbar(
            self.status_inner, variable=self._progress_var,
            maximum=100, length=120, mode='determinate'
        )
        # Don't pack yet — shown only during background ops

        self._update_worker_info()

    # ═══════════════════════════════════════════════════════════════════════
    #  Keyboard Shortcuts
    # ═══════════════════════════════════════════════════════════════════════

    def _bind_shortcuts(self):
        """Bind keyboard shortcuts."""
        self.root.bind("<Control-o>", lambda e: self.open_file())
        self.root.bind("<Control-s>", lambda e: self.save_file())
        self.root.bind("<Control-p>", lambda e: self.print_pdf())
        self.root.bind("<Control-f>", lambda e: self.find_text_dialog())
        self.root.bind("<Control-g>", lambda e: self.goto_page_dialog())
        self.root.bind("<Control-c>", lambda e: self.copy_page_text())
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-y>", lambda e: self.redo())
        self.root.bind("<Left>", lambda e: self.prev_page())
        self.root.bind("<Right>", lambda e: self.next_page())
        self.root.bind("<Prior>", lambda e: self.prev_page())  # Page Up
        self.root.bind("<Next>", lambda e: self.next_page())   # Page Down
        self.root.bind("<Home>", lambda e: self.first_page())
        self.root.bind("<End>", lambda e: self.last_page())
        self.root.bind("<Control-plus>", lambda e: self.zoom_in())
        self.root.bind("<Control-equal>", lambda e: self.zoom_in())
        self.root.bind("<Control-minus>", lambda e: self.zoom_out())
        self.root.bind("<Control-0>", lambda e: self.viewer.set_zoom(1.0) or self._update_display())
        self.root.bind("<Escape>", lambda e: self.disable_split_mode())
        self.root.bind("<r>", lambda e: self.rotate_current(90))
        self.root.bind("<Delete>", lambda e: self.delete_current_page())
        self.root.bind("<F5>", lambda e: self._refresh_display())
        self.root.bind("<F11>", lambda e: self._toggle_fullscreen())
        self.root.bind("<Control-t>", lambda e: self._open_new_tab_dialog())
        self.root.bind("<Control-w>", lambda e: self._close_active_tab())

    # ═══════════════════════════════════════════════════════════════════════
    #  Multi-Tab Management
    # ═══════════════════════════════════════════════════════════════════════

    def _create_tab(self, page_num):
        """Create a new tab for the given page number.

        Returns the new PageTab, or None if max tabs reached or
        a tab for this page already exists (switches to it instead).
        """
        if not self.doc:
            return None

        page_num = max(0, min(page_num, self.doc.page_count - 1))

        # If tab already exists for this page, just switch to it
        for tab in self._tabs:
            if tab.page_num == page_num:
                self._switch_tab(tab)
                return tab

        if len(self._tabs) >= self._max_tabs:
            messagebox.showwarning(
                "Tab Limit",
                f"Maximum {self._max_tabs} tabs. Close a tab first."
            )
            return None

        # Hide default canvas if this is the first tab
        if not self._tabs:
            self._default_canvas.pack_forget()
            self._tab_bar.pack(fill=tk.X, side=tk.TOP,
                               before=self._tab_container)

        # Create the tab
        tab = PageTab(page_num, self._tab_container)
        tab.zoom_level = self.viewer.zoom_level
        self._bind_canvas_events(tab.canvas)
        
        # Hook v_scroll for continuous mode
        def _on_vscroll(*args):
            tab.canvas.yview(*args)
            if getattr(self, 'view_mode', 'single') == 'continuous':
                self._render_continuous_view()
        tab.v_scroll.config(command=_on_vscroll)
        
        self._tabs.append(tab)

        # Create tab button in tab bar
        self._create_tab_button(tab)

        # Switch to this new tab
        self._switch_tab(tab)

        logger.info(f"Created tab for page {page_num + 1} "
                     f"({len(self._tabs)} tabs open)")
        return tab

    def _create_tab_button(self, tab):
        """Create a button in the tab bar for a tab."""
        btn_frame = tk.Frame(self._tab_bar_inner, bg=COLORS["bg_panel"])
        btn_frame.pack(side=tk.LEFT, padx=1, pady=2)

        btn = tk.Button(
            btn_frame, text=f" {tab.label} ",
            command=lambda t=tab: self._switch_tab(t),
            bg=COLORS["bg_hover"], fg=COLORS["text_primary"],
            activebackground=COLORS["accent"],
            activeforeground="white",
            font=("Segoe UI", 9),
            relief=tk.FLAT, padx=4, pady=1, cursor="hand2", bd=0
        )
        btn.pack(side=tk.LEFT)

        close_btn = tk.Button(
            btn_frame, text="×",
            command=lambda t=tab: self._close_tab(t),
            bg=COLORS["bg_hover"], fg=COLORS["text_dim"],
            activebackground=COLORS["danger"],
            activeforeground="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT, padx=2, pady=1, cursor="hand2", bd=0
        )
        close_btn.pack(side=tk.LEFT)

        self._tab_buttons[tab.id] = (btn_frame, btn)

    def _switch_tab(self, tab):
        """Switch to the given tab."""
        if self._active_tab is tab:
            return

        # Save current tab state
        if self._active_tab is not None:
            self._active_tab.save_scroll_pos()
            self._active_tab.hide()

        # Activate new tab
        self._active_tab = tab
        self.canvas = tab.canvas  # Update the active canvas reference
        self.viewer.go_to_page(tab.page_num)
        self.viewer.zoom_level = tab.zoom_level
        self.split_mode = tab.split_mode
        self.split_line_y = tab.split_line_y

        tab.show()

        # Update tab button styles
        self._refresh_tab_buttons()

        # Render the page on this tab
        self._update_display()
        tab.restore_scroll_pos()

        self._update_worker_info()
        logger.debug(f"Switched to tab: {tab.label}")

    def _close_tab(self, tab):
        """Close a specific tab."""
        if tab not in self._tabs:
            return

        idx = self._tabs.index(tab)
        self._tabs.remove(tab)

        # Remove button
        btn_info = self._tab_buttons.pop(tab.id, None)
        if btn_info:
            btn_info[0].destroy()  # Destroy the frame

        # If this was the active tab, switch to another
        if self._active_tab is tab:
            self._active_tab = None
            if self._tabs:
                # Switch to nearest tab
                new_idx = min(idx, len(self._tabs) - 1)
                self._switch_tab(self._tabs[new_idx])
            else:
                # No tabs left — show default canvas + welcome
                self._tab_bar.pack_forget()
                self.canvas = self._default_canvas
                self._default_canvas.pack(fill=tk.BOTH, expand=True)
                self._show_welcome()

        tab.destroy()
        self._update_worker_info()
        logger.info(f"Closed tab (page {tab.page_num + 1}), "
                     f"{len(self._tabs)} tabs remaining")

    def _close_active_tab(self):
        """Close the currently active tab (Ctrl+W)."""
        if self._active_tab:
            self._close_tab(self._active_tab)

    def _close_all_tabs(self):
        """Close all tabs."""
        for tab in list(self._tabs):
            self._close_tab(tab)

    def _refresh_tab_buttons(self):
        """Update tab button styles to reflect active tab."""
        for tab in self._tabs:
            btn_info = self._tab_buttons.get(tab.id)
            if not btn_info:
                continue
            _, btn = btn_info
            if tab is self._active_tab:
                btn.configure(
                    bg=COLORS["accent"],
                    fg="white",
                    font=("Segoe UI", 9, "bold")
                )
            else:
                btn.configure(
                    bg=COLORS["bg_hover"],
                    fg=COLORS["text_primary"],
                    font=("Segoe UI", 9)
                )

    def _open_page_in_new_tab(self, page_num):
        """Open a specific page in a new tab."""
        if not self.doc:
            return
        self._create_tab(page_num)

    def _open_new_tab_dialog(self):
        """Dialog to choose which page to open in a new tab."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        result = simpledialog.askinteger(
            "Open in New Tab",
            f"Enter page number (1-{self.doc.page_count}):",
            initialvalue=self.viewer.current_page + 1,
            minvalue=1,
            maxvalue=self.doc.page_count
        )
        if result is not None:
            self._create_tab(result - 1)

    def _sync_tab_state(self):
        """Sync viewer state back to the active tab."""
        if self._active_tab:
            self._active_tab.page_num = self.viewer.current_page
            self._active_tab.zoom_level = self.viewer.zoom_level
            self._active_tab.split_mode = self.split_mode
            self._active_tab.split_line_y = self.split_line_y
            # Update tab button label
            btn_info = self._tab_buttons.get(self._active_tab.id)
            if btn_info:
                _, btn = btn_info
                btn.configure(text=f" {self._active_tab.label} ")

    # ═══════════════════════════════════════════════════════════════════════
    #  Background Task Helpers
    # ═══════════════════════════════════════════════════════════════════════

    def _run_in_background(self, func, callback=None, error_callback=None,
                           progress_callback=None, description="Processing"):
        """Run a function in background thread, keeping UI responsive.

        Args:
            func: Callable to run in background.
                  If progress_callback is set, func receives it as kwarg.
            callback: Called on main thread with func's return value.
            error_callback: Called on main thread with exception.
            progress_callback: Optional. If set, shows progress bar.
            description: Status bar text while running.
        """
        self._update_status(f"⏳ {description}...")

        with self._bg_lock:
            self._bg_tasks += 1
        self._update_worker_info()

        if progress_callback:
            self._progress_bar.pack(side=tk.RIGHT, padx=8)
            self._progress_var.set(0)

        def _worker():
            try:
                if progress_callback:
                    def _prog(pct, msg=""):
                        self.root.after(0, lambda: self._on_bg_progress(
                            pct, msg))
                    result = func(progress_callback=_prog)
                else:
                    result = func()

                self.root.after(0, lambda: self._on_bg_done(
                    result, callback, description))
            except Exception as e:
                self.root.after(0, lambda: self._on_bg_error(
                    e, error_callback, description))

        self._bg_executor.submit(_worker)

    def _on_bg_progress(self, pct, msg=""):
        """Handle progress update from background task."""
        self._progress_var.set(pct)
        if msg:
            self.status_var.set(f"⏳ {msg}")

    def _on_bg_done(self, result, callback, description):
        """Handle background task completion."""
        with self._bg_lock:
            self._bg_tasks = max(0, self._bg_tasks - 1)
        self._progress_bar.pack_forget()
        self._update_worker_info()
        self._update_status(f"✅ {description} — Done")

        if callback:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Callback error: {e}")
                messagebox.showerror("Error", f"Callback failed:\n{e}")

    def _on_bg_error(self, error, error_callback, description):
        """Handle background task error."""
        with self._bg_lock:
            self._bg_tasks = max(0, self._bg_tasks - 1)
        self._progress_bar.pack_forget()
        self._update_worker_info()
        self._update_status(f"❌ {description} — Failed")

        if error_callback:
            error_callback(error)
        else:
            messagebox.showerror("Error", f"{description} failed:\n{error}")

    def _update_worker_info(self):
        """Update the worker/tab info in the status bar."""
        parts = []
        if self._tabs:
            parts.append(f"📑 {len(self._tabs)} tabs")
        if self._bg_tasks > 0:
            parts.append(f"⏳ {self._bg_tasks} tasks")
        rinfo = self.viewer.renderer.get_worker_info()
        parts.append(f"⚡ {rinfo['workers']}w")
        self._worker_info_var.set("  |  ".join(parts))

    def _show_progress(self, pct):
        """Show/update progress bar."""
        self._progress_bar.pack(side=tk.RIGHT, padx=8)
        self._progress_var.set(pct)

    def _hide_progress(self):
        """Hide progress bar."""
        self._progress_bar.pack_forget()
        self._progress_var.set(0)

    # ═══════════════════════════════════════════════════════════════════════
    #  File Operations
    # ═══════════════════════════════════════════════════════════════════════

    def open_file(self, file_path=None):
        """Open a PDF file."""
        if file_path is None:
            file_path = filedialog.askopenfilename(
                title="Open PDF File",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                initialdir=str(Path.cwd())
            )

        if not file_path:
            return

        try:
            file_path = Path(file_path)
            self.doc = fitz.open(str(file_path))
            self.file_path = file_path
            self.operations.open(file_path)
            self.viewer.set_document(self.doc)

            # Close all existing tabs and create a fresh tab for page 0
            self._close_all_tabs()
            self._create_tab(0)

            self._update_thumbnails()
            self._update_status(
                f"Opened: {file_path.name} ({self.doc.page_count} pages)"
            )

            file_size = format_file_size(os.path.getsize(str(file_path)))
            self.file_info_var.set(
                f"{file_path.name}  |  {self.doc.page_count} pages  |  {file_size}"
            )

            # Update recent files
            self._add_recent_file(str(file_path))

            # Set window title
            self.root.title(f"⚡ PDF Editor Pro — {file_path.name}")

            logger.info(f"Opened file: {file_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Could not open file:\n{e}")
            logger.error(f"Failed to open file: {e}")

    def save_file(self):
        """Save the current document."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        output_path = filedialog.asksaveasfilename(
            title="Save PDF As",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialdir=str(get_output_dir()),
            initialfile=f"{self.file_path.stem}_edited.pdf"
        )

        if not output_path:
            return

        try:
            self.doc.save(output_path, garbage=4, deflate=True)
            self._update_status(f"Saved to: {Path(output_path).name}")
            messagebox.showinfo("Success", f"PDF saved to:\n{output_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save:\n{e}")

    # ═══════════════════════════════════════════════════════════════════════
    #  Display & Navigation
    # ═══════════════════════════════════════════════════════════════════════

    def _show_welcome(self):
        """Show welcome message on the canvas."""
        self.canvas.delete("all")
        cw = self.canvas.winfo_width() or 800
        ch = self.canvas.winfo_height() or 600

        self.canvas.create_text(
            cw // 2, ch // 2 - 40,
            text="⚡ PDF Editor Pro",
            font=("Segoe UI", 28, "bold"),
            fill=COLORS["accent_light"]
        )
        self.canvas.create_text(
            cw // 2, ch // 2 + 10,
            text="Offline Edition — OpenCV + Tesseract OCR",
            font=("Segoe UI", 14),
            fill=COLORS["text_secondary"]
        )
        self.canvas.create_text(
            cw // 2, ch // 2 + 50,
            text="Open a PDF file to start (Ctrl+O)",
            font=("Segoe UI", 12),
            fill=COLORS["text_dim"]
        )
        self.canvas.create_text(
            cw // 2, ch // 2 + 90,
            text="✂️ Smart Split  •  🔍 OCR  •  📝 Annotate  •  🔒 Encrypt",
            font=("Segoe UI", 11),
            fill=COLORS["text_dim"]
        )

    def toggle_view_mode(self, force_single=False):
        """Toggle between single page and continuous viewing mode."""
        if force_single or getattr(self, 'view_mode', 'single') == "continuous":
            self.view_mode = "single"
            if hasattr(self, '_view_mode_btn'):
                self._view_mode_btn.config(text="📄 Trang đơn", bg=COLORS["bg_card"])
            if hasattr(self, '_continuous_images'):
                self._continuous_images.clear()
            self._continuous_layouts = []
            self._update_display()
        else:
            self.view_mode = "continuous"
            if hasattr(self, '_view_mode_btn'):
                self._view_mode_btn.config(text="📜 Cuộn liên tục", bg=COLORS["accent"])
            self._continuous_layouts = []
            self._update_display()

    def _calculate_continuous_layout(self):
        """Calculate coordinates and dimensions for all pages in continuous view."""
        self._continuous_layouts = []
        if not self.doc: return
        
        y_offset = 20
        zoom = self.viewer.zoom_level
        cw = self.canvas.winfo_width()
        
        for i in range(self.doc.page_count):
            page = self.doc[i]
            w, h = page.rect.width, page.rect.height
            if page.rotation in (90, 270):
                w, h = h, w
                
            sw = int(w * zoom * 1.5)
            sh = int(h * zoom * 1.5)
            
            x_start = max(0, (cw - sw) // 2)
            
            self._continuous_layouts.append({
                'page': i,
                'y_start': y_offset,
                'y_end': y_offset + sh,
                'width': sw,
                'height': sh,
                'x_start': x_start
            })
            y_offset += sh + 20

    def _render_continuous_view(self):
        """Render visible pages in continuous scroll mode."""
        if not self.doc: return
        
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw <= 1 or ch <= 1: return
            
        if not hasattr(self, '_continuous_layouts') or not self._continuous_layouts:
            self._calculate_continuous_layout()
            
        if not self._continuous_layouts:
            return
            
        total_h = self._continuous_layouts[-1]['y_end'] + 20
        max_w = max((l['width'] for l in self._continuous_layouts), default=cw)
        
        self.canvas.configure(scrollregion=(0, 0, max(cw, max_w + 40), max(ch, total_h)))
        
        yview = self.canvas.yview()
        if not yview: return
        
        vp_top = yview[0] * total_h
        vp_bottom = yview[1] * total_h
        
        buffer = ch
        view_top = vp_top - buffer
        view_bottom = vp_bottom + buffer
        
        visible_pages = []
        for l in self._continuous_layouts:
            if l['y_end'] > view_top and l['y_start'] < view_bottom:
                visible_pages.append(l)
                
        if not hasattr(self, '_continuous_images'):
            self._continuous_images = {}
            
        current_visible = set(l['page'] for l in visible_pages)
        
        for p in list(self._continuous_images.keys()):
            if p not in current_visible:
                self.canvas.delete(f"page_{p}")
                del self._continuous_images[p]
                
        for l in visible_pages:
            p = l['page']
            if p not in self._continuous_images:
                img = self.viewer.get_page_image(p)
                if img:
                    photo = ImageTk.PhotoImage(img)
                    self._continuous_images[p] = photo
                    
                    self.canvas.create_rectangle(
                        l['x_start']-1, l['y_start']-1,
                        l['x_start']+l['width']+1, l['y_start']+l['height']+1,
                        outline="#555555", fill=COLORS["bg_card"],
                        tags=(f"page_{p}", "continuous_page_bg")
                    )
                    
                    self.canvas.create_text(
                        l['x_start'], l['y_start'] - 18,
                        text=f"Trang {p + 1}",
                        font=("Segoe UI", 11, "bold"),
                        fill=COLORS["text_secondary"],
                        anchor="nw",
                        tags=(f"page_{p}", "continuous_page_label")
                    )
                    
                    self.canvas.create_image(
                        l['x_start'], l['y_start'],
                        image=photo, anchor="nw",
                        tags=(f"page_{p}", "continuous_page")
                    )
                    
        if visible_pages:
            center_y = (vp_top + vp_bottom) / 2
            closest_page = min(visible_pages, key=lambda l: abs((l['y_start'] + l['y_end'])/2 - center_y))['page']
            if self.viewer.current_page != closest_page:
                self.viewer.current_page = closest_page
                self.page_entry_var.set(f"{closest_page + 1} / {self.viewer.page_count}")
                self._sync_tab_state()

    def _update_display(self):
        """Update the active tab's canvas with the current page."""
        if not self.doc:
            return

        self.canvas.delete("all")
        
        if getattr(self, 'view_mode', 'single') == "continuous":
            self._render_continuous_view()
            return

        try:
            img = self.viewer.get_page_image(self.viewer.current_page)
            if img is None:
                return

            photo = ImageTk.PhotoImage(img)

            # Store reference in active tab (if exists) AND self
            if self._active_tab:
                self._active_tab._photo_image = photo
            self._photo_image = photo

            # Center the image
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
            x = max(0, (cw - img.width) // 2)
            y = max(0, (ch - img.height) // 2)

            self.canvas.create_image(x, y, image=photo,
                                     anchor="nw", tags="page")

            # Update scroll region
            self.canvas.configure(
                scrollregion=(0, 0,
                              max(cw, img.width + 40),
                              max(ch, img.height + 40))
            )

            # Draw split line if in split mode
            if self.split_mode and self.split_line_y is not None:
                self.canvas.create_line(
                    0, self.split_line_y + y,
                    img.width + x, self.split_line_y + y,
                    fill="#ff4444", width=3, dash=(8, 4), tags="split_line"
                )
                self.canvas.create_text(
                    x + 10, self.split_line_y + y - 15,
                    text=f"\u2702 Split here (Y={self.split_line_y}px)",
                    font=("Segoe UI", 10, "bold"),
                    fill="#ff4444", anchor="nw", tags="split_line"
                )

            # Draw multi-split regions if in multi-split mode
            if self.multi_split_mode:
                pts = self.multi_split_points
                for i in range(len(pts)):
                    py = pts[i]
                    # Draw line
                    self.canvas.create_line(
                        0, py + y,
                        img.width + x, py + y,
                        fill="#00ff00" if i % 2 == 0 else "#ff0000",
                        width=2, dash=(4, 4), tags="multi_split"
                    )
                    # Draw region overlay if we have a pair
                    if i % 2 == 1:
                        y1 = pts[i-1] + y
                        y2 = py + y
                        # Overlay semi-transparent green rect (using stipple or just outline)
                        self.canvas.create_rectangle(
                            x, y1, x + img.width, y2,
                            outline="#00ff00", width=3, tags="multi_split"
                        )
                        self.canvas.create_text(
                            x + 5, y1 + 5,
                            text=f"KEEP REGION {i//2 + 1}",
                            fill="#00ff00", font=("Segoe UI", 10, "bold"),
                            anchor="nw", tags="multi_split"
                        )

            # Update page info
            page_num = self.viewer.current_page
            total = self.viewer.page_count
            self.page_entry_var.set(f"{page_num + 1} / {total}")
            self.zoom_var.set(f"{int(self.viewer.zoom_level * 100)}%")

            # Sync tab state
            self._sync_tab_state()

            # Pre-fetch adjacent pages in background
            self.viewer.prefetch_adjacent(
                self.root,
                lambda pn, _img: None,  # Just cache, no UI update needed
                prefetch_range=2
            )

        except Exception as e:
            logger.error(f"Display update error: {e}")

    def _update_thumbnails(self):
        """Update the thumbnail sidebar."""
        if not self.doc:
            return

        # Clear existing thumbnails
        for widget in self.thumb_inner.winfo_children():
            widget.destroy()
        self._thumbnail_photos = []

        for i in range(min(self.doc.page_count, 200)):  # Limit for performance
            self._create_thumbnail(i)

    def _create_thumbnail(self, page_num):
        """Create a single thumbnail widget with tab support."""
        frame = tk.Frame(self.thumb_inner, bg=COLORS["bg_panel"],
                         cursor="hand2")
        frame.pack(fill=tk.X, padx=8, pady=4)

        # Highlight current page
        is_current = page_num == self.viewer.current_page
        # Check if this page has an open tab
        has_tab = any(t.page_num == page_num for t in self._tabs)
        if is_current:
            border_color = COLORS["accent"]
        elif has_tab:
            border_color = COLORS["accent_dark"]
        else:
            border_color = COLORS["border"]

        border_frame = tk.Frame(frame, bg=border_color, padx=2, pady=2)
        border_frame.pack(fill=tk.X)

        try:
            thumb_img = self.viewer.get_thumbnail(page_num, max_size=140)
            if thumb_img:
                photo = ImageTk.PhotoImage(thumb_img)
                self._thumbnail_photos.append(photo)

                label = tk.Label(border_frame, image=photo,
                                 bg=COLORS["bg_card"])
                label.pack()
                # Single-click: navigate in active tab
                label.bind("<Button-1>",
                           lambda e, pn=page_num: self._goto_page(pn))
                # Double-click: open in new tab
                label.bind("<Double-Button-1>",
                           lambda e, pn=page_num: self._open_page_in_new_tab(pn))
        except Exception:
            pass

        # Label frame to hold Checkbutton + Label side-by-side
        lbl_frame = tk.Frame(frame, bg=COLORS["bg_panel"])
        lbl_frame.pack(pady=2)

        # Selection Checkbutton
        var = tk.BooleanVar(value=(page_num in self.selected_pages))
        chk = tk.Checkbutton(
            lbl_frame, variable=var,
            bg=COLORS["bg_panel"], activebackground=COLORS["bg_panel"],
            selectcolor=COLORS["bg_dark"], bd=0,
            command=lambda pn=page_num, v=var: self._toggle_selection(pn, v.get())
        )
        chk.pack(side=tk.LEFT)

        # Page number label + tab indicator
        tab_marker = " \ud83d\udcd1" if has_tab else ""
        num_label = tk.Label(
            lbl_frame,
            text=f"Page {page_num + 1}{tab_marker}",
            bg=COLORS["bg_panel"],
            fg=COLORS["accent_light"] if is_current else COLORS["text_dim"],
            font=("Segoe UI", 9, "bold" if is_current else "normal")
        )
        num_label.pack(side=tk.LEFT)
        num_label.bind("<Button-1>",
                       lambda e, pn=page_num: self._goto_page(pn))
        num_label.bind("<Double-Button-1>",
                       lambda e, pn=page_num: self._open_page_in_new_tab(pn))

    # ─── Selection Logic ─────────────────────────────────────────────────

    def _toggle_selection(self, page_num, is_selected):
        if is_selected:
            self.selected_pages.add(page_num)
        else:
            self.selected_pages.discard(page_num)
        self._update_status(f"{len(self.selected_pages)} pages selected")

    def _select_all(self):
        if not self.doc: return
        self.selected_pages = set(range(self.doc.page_count))
        self._update_thumbnails()
        self._update_status(f"Selected all {len(self.selected_pages)} pages")

    def _select_odd(self):
        if not self.doc: return
        # 1-indexed odd means 0, 2, 4 in 0-indexed
        self.selected_pages = set(range(0, self.doc.page_count, 2))
        self._update_thumbnails()
        self._update_status(f"Selected odd pages")

    def _select_even(self):
        if not self.doc: return
        # 1-indexed even means 1, 3, 5 in 0-indexed
        self.selected_pages = set(range(1, self.doc.page_count, 2))
        self._update_thumbnails()
        self._update_status(f"Selected even pages")

    def _select_custom_dialog(self):
        if not self.doc: return
        prompt = t("prompt_custom_pages", "Enter page ranges (e.g. 1-5, 8, 11-13):")
        result = simpledialog.askstring("Custom Selection", prompt, parent=self.root)
        if not result: return
        
        selected = set()
        total = self.doc.page_count
        
        try:
            parts = [p.strip() for p in result.split(",")]
            for p in parts:
                if not p: continue
                if "-" in p:
                    start_s, end_s = p.split("-", 1)
                    start = int(start_s.strip())
                    end = int(end_s.strip())
                    start = max(1, min(start, total))
                    end = max(1, min(end, total))
                    if start <= end:
                        for i in range(start, end + 1):
                            selected.add(i - 1)
                    else:
                        for i in range(start, end - 1, -1):
                            selected.add(i - 1)
                else:
                    val = int(p)
                    if 1 <= val <= total:
                        selected.add(val - 1)
            
            self.selected_pages = selected
            self._update_thumbnails()
            self._update_status(f"Custom selection: {len(selected)} pages")
        except ValueError:
            messagebox.showerror(t("error"), t("error_invalid_range", "Invalid page range format."))

    def _clear_selection(self):
        self.selected_pages.clear()
        self._update_thumbnails()
        self._update_status("Cleared selection")

    def _goto_page(self, page_num):
        """Navigate to a specific page in the active tab."""
        self.viewer.go_to_page(page_num)
        self._update_display()
        self._update_thumbnails()

    def _on_page_entry(self, event=None):
        """Handle page number entry."""
        try:
            text = self.page_entry_var.get().strip()
            # Handle "x / y" format
            if "/" in text:
                text = text.split("/")[0].strip()
            page_num = int(text) - 1
            if 0 <= page_num < self.viewer.page_count:
                self._goto_page(page_num)
        except ValueError:
            pass

    # ─── Navigation ──────────────────────────────────────────────────────

    def next_page(self):
        if self.viewer.next_page():
            self._sync_tab_state()
            self._update_display()
            self._update_thumbnails()

    def prev_page(self):
        if self.viewer.prev_page():
            self._sync_tab_state()
            self._update_display()
            self._update_thumbnails()

    def first_page(self):
        if self.viewer.first_page():
            self._sync_tab_state()
            self._update_display()
            self._update_thumbnails()

    def last_page(self):
        if self.viewer.last_page():
            self._sync_tab_state()
            self._update_display()
            self._update_thumbnails()

    # ─── Zoom ────────────────────────────────────────────────────────────

    def zoom_in(self):
        if self.viewer.zoom_in():
            self._sync_tab_state()
            self._update_display()

    def zoom_out(self):
        if self.viewer.zoom_out():
            self._sync_tab_state()
            self._update_display()

    def fit_width(self):
        cw = self.canvas.winfo_width()
        if self.viewer.fit_width(cw):
            self._update_display()

    # ═══════════════════════════════════════════════════════════════════════
    #  ⭐ SMART PAGE SPLITTING
    # ═══════════════════════════════════════════════════════════════════════

    def smart_split_y_dialog(self):
        """Split current page at a specific Y coordinate (PDF points)."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        page = self.doc[self.viewer.current_page]
        page_h = page.rect.height

        dialog = _SplitYDialog(self.root, page_h)
        self.root.wait_window(dialog)

        if dialog.result is not None:
            out_path = filedialog.asksaveasfilename(
                title="Lưu file Cắt Y (Save As)",
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")],
                initialfile=f"{self.file_path.stem}_split.pdf"
            )
            if not out_path:
                return

            try:
                src_path = self._get_current_pdf_path_for_batch()
                output = self.splitter.split_by_y_coordinate(
                    src_path,
                    self.viewer.current_page,
                    dialog.result,
                    output_path=out_path
                )
                self._update_status(f"Page split at Y={dialog.result:.0f}pt")
                messagebox.showinfo(
                    "Success",
                    f"Page split successfully!\nSaved to: {output}"
                )
                # Offer to open the result
                if messagebox.askyesno("Open Result",
                                        "Open the split PDF?"):
                    self.open_file(str(output))
            except Exception as e:
                messagebox.showerror("Error", f"Split failed:\n{e}")

    def smart_split_text_dialog(self):
        """Split current page after specific text found via OCR."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        dialog = _SplitTextDialog(self.root)
        self.root.wait_window(dialog)

        if dialog.result is not None:
            search_text = dialog.result

            out_path = filedialog.asksaveasfilename(
                title="Lưu file Cắt OCR (Save As)",
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")],
                initialfile=f"{self.file_path.stem}_split.pdf"
            )
            if not out_path:
                return

            self._update_status(f"Searching for text: '{search_text}'...")
            self.root.update()

            try:
                src_path = self._get_current_pdf_path_for_batch()
                output = self.splitter.split_after_text(
                    src_path,
                    self.viewer.current_page,
                    search_text,
                    output_path=out_path,
                    margin_below=dialog.margin
                )
                self._update_status(
                    f"Split after text '{search_text}'"
                )
                messagebox.showinfo(
                    "Success",
                    f"Page split after '{search_text}'!\nSaved to: {output}"
                )
                if messagebox.askyesno("Open Result",
                                        "Open the split PDF?"):
                    self.open_file(str(output))
            except ValueError as e:
                messagebox.showwarning("Text Not Found", str(e))
            except Exception as e:
                messagebox.showerror("Error", f"Split failed:\n{e}")

    def smart_split_auto(self):
        """Auto-detect and split at the best split point."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        self._update_status("Analyzing page for split points...")
        self.root.update()

        try:
            src_path = self._get_current_pdf_path_for_batch()
            split_points = self.splitter.auto_detect_split_points(
                src_path, self.viewer.current_page
            )

            if not split_points:
                messagebox.showinfo(
                    "No Split Points",
                    "No automatic split points detected on this page."
                )
                return

            # Show detected points in a dialog
            dialog = _AutoSplitDialog(self.root, split_points)
            self.root.wait_window(dialog)

            if dialog.result is not None:
                pdf_y = split_points[dialog.result]["pdf_y"]
                self._split_page_in_memory(self.viewer.current_page, pdf_y)

        except Exception as e:
            messagebox.showerror("Error", f"Auto-split failed:\n{e}")

    def smart_split_percentage_dialog(self):
        """Split at a percentage from the top."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        result = simpledialog.askfloat(
            "Split by Percentage",
            "Enter percentage from top (0-100):\n"
            "e.g., 50 = middle of page",
            initialvalue=50.0, minvalue=1.0, maxvalue=99.0
        )

        if result is not None:
            try:
                page_height = self.doc[self.viewer.current_page].rect.height
                pdf_y = page_height * result / 100.0
                self._split_page_in_memory(self.viewer.current_page, pdf_y)
            except Exception as e:
                messagebox.showerror("Error", f"Split failed:\n{e}")

    def split_all_pages_dialog(self):
        """Split all pages at the same Y coordinate."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        page = self.doc[self.viewer.current_page]
        result = simpledialog.askfloat(
            "Split All Pages",
            f"Enter Y coordinate in PDF points (page height: {page.rect.height:.0f}pt):\n"
            f"All {self.doc.page_count} pages will be split at this position.",
            initialvalue=page.rect.height / 2,
            minvalue=10, maxvalue=page.rect.height - 10
        )

        if result is not None:
            try:
                self._save_undo_state(f"Split all pages at Y={result:.0f}")
                
                initial_count = self.doc.page_count
                # Iterate backwards so we don't mess up indices
                for page_num in range(self.doc.page_count - 1, -1, -1):
                    page = self.doc[page_num]
                    page_rect = page.rect
                    
                    # Ensure Y is within page height
                    if result >= page_rect.height or result <= 0:
                        continue
                    
                    temp_doc = fitz.open()
                    temp_doc.insert_pdf(self.doc, from_page=page_num, to_page=page_num)
                    
                    self.doc.delete_page(page_num)
                    
                    self.doc.insert_pdf(temp_doc, from_page=0, to_page=0, start_at=page_num)
                    self.doc[page_num].set_cropbox(fitz.Rect(page_rect.x0, page_rect.y0, page_rect.x1, page_rect.y0 + result))
                    
                    self.doc.insert_pdf(temp_doc, from_page=0, to_page=0, start_at=page_num + 1)
                    self.doc[page_num + 1].set_cropbox(fitz.Rect(page_rect.x0, page_rect.y0 + result, page_rect.x1, page_rect.y1))
                    
                    temp_doc.close()
                    
                self.viewer.clear_cache()
                self._update_display()
                self._update_thumbnails()
                
                msg = f"Đã chia toàn bộ tài liệu từ {initial_count} trang thành {self.doc.page_count} trang!"
                self._update_status(msg)
                messagebox.showinfo("Success", msg)
            except Exception as e:
                messagebox.showerror("Error", f"Split failed:\n{e}")

    # ─── Interactive Split Mode ──────────────────────────────────────────

    def _ensure_single_mode_for_editing(self, feature_name):
        if getattr(self, 'view_mode', 'single') == "continuous":
            self.toggle_view_mode(force_single=True)
            messagebox.showinfo("Mode Switched", f"Switched to Single Page View for {feature_name}.")

    def enable_split_mode(self):
        """Enable interactive split mode - click on canvas to set split point."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return
            
        self._ensure_single_mode_for_editing("Click Split")

        self.split_mode = True
        self.split_line_y = None
        self.canvas.config(cursor="crosshair")
        self._update_status(
            "🖱️ SPLIT MODE: Click on the page to set split point. "
            "Press ESC to cancel."
        )

    def disable_split_mode(self):
        """Disable split mode."""
        self.split_mode = False
        self.split_line_y = None
        self.canvas.config(cursor="arrow")
        self.canvas.delete("split_line")
        self._update_status("Split mode cancelled.")

    def enable_multi_split_mode(self):
        """Enable multi-split crop mode."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return
            
        self._ensure_single_mode_for_editing("Multi Crop")

        self.multi_split_mode = True
        self.multi_split_points = []
        self.multi_split_pdf_points = []
        self.canvas.config(cursor="crosshair")
        self._update_display()
        
        # Add 'Apply' button to status bar temporarily
        self._apply_crop_btn = tk.Button(self.status_inner, text="✅ Apply Crop", 
                                        command=self.apply_multi_split,
                                        bg=COLORS["accent"], fg="white", bd=0, padx=10)
        self._apply_crop_btn.pack(side=tk.RIGHT, padx=5)
        
        self._update_status("✂️ MULTI-CROP: Click to set pairs of Y coordinates. Press ESC to cancel.")

    def disable_multi_split_mode(self):
        """Disable multi-split crop mode."""
        self.multi_split_mode = False
        self.multi_split_points = []
        self.multi_split_pdf_points = []
        self.canvas.config(cursor="arrow")
        self.canvas.delete("multi_split")
        if hasattr(self, '_apply_crop_btn') and self._apply_crop_btn:
            self._apply_crop_btn.destroy()
            self._apply_crop_btn = None
        self._update_display()
        self._update_status("Multi-crop mode cancelled.")

    def apply_multi_split(self):
        """Apply multi-y cropping."""
        if len(self.multi_split_pdf_points) % 2 != 0:
            messagebox.showwarning("Warning", "Please select complete pairs of points (even number of clicks).")
            return
            
        if len(self.multi_split_pdf_points) == 0:
            self.disable_multi_split_mode()
            return
            
        regions = []
        pts = sorted(self.multi_split_pdf_points)
        for i in range(0, len(pts), 2):
            regions.append((pts[i], pts[i+1]))
            
        try:
            pages_to_crop = sorted(list(self.selected_pages)) if self.selected_pages else [self.viewer.current_page]
            self._save_undo_state(f"Crop {len(pages_to_crop)} pages into {len(regions)} regions")
            
            # Process from last to first to avoid index shifting
            for page_num in sorted(pages_to_crop, reverse=True):
                page = self.doc[page_num]
                page_rect = page.rect
                
                valid_regions = []
                for y1, y2 in regions:
                    y1 = max(0, min(y1, page_rect.height))
                    y2 = max(0, min(y2, page_rect.height))
                    if y1 < y2:
                        valid_regions.append((y1, y2))
                        
                if not valid_regions:
                    continue
                    
                # Create a temporary doc with just this page to duplicate from
                temp_doc = fitz.open()
                temp_doc.insert_pdf(self.doc, from_page=page_num, to_page=page_num)
                
                # Delete the original page
                self.doc.delete_page(page_num)
                
                # Insert the copies back into the document
                for i, (y1, y2) in enumerate(valid_regions):
                    self.doc.insert_pdf(temp_doc, from_page=0, to_page=0, start_at=page_num + i)
                    new_page = self.doc[page_num + i]
                    
                    # Set the cropbox to show only the selected region
                    crop_rect = fitz.Rect(page_rect.x0, page_rect.y0 + y1, page_rect.x1, page_rect.y0 + y2)
                    new_page.set_cropbox(crop_rect)
                    
                temp_doc.close()
                
            self.disable_multi_split_mode()
            self.selected_pages.clear()
            self.viewer.clear_cache()
            self._update_display()
            self._update_thumbnails()
            
            msg = f"Đã áp dụng cắt {len(pages_to_crop)} trang (thành {len(valid_regions)} phần) trực tiếp trên tài liệu!"
            self._update_status(msg)
            messagebox.showinfo("Success", msg)
            
        except Exception as e:
            messagebox.showerror("Error", f"Crop failed:\n{e}")

    def _split_page_in_memory(self, page_num, pdf_y):
        """Helper to split a page into two at a specific Y coordinate in-memory."""
        page = self.doc[page_num]
        page_rect = page.rect
        
        self._save_undo_state(f"Split page {page_num + 1} at Y={pdf_y:.0f}")
        
        temp_doc = fitz.open()
        temp_doc.insert_pdf(self.doc, from_page=page_num, to_page=page_num)
        
        self.doc.delete_page(page_num)
        
        self.doc.insert_pdf(temp_doc, from_page=0, to_page=0, start_at=page_num)
        new_page_1 = self.doc[page_num]
        new_page_1.set_cropbox(fitz.Rect(page_rect.x0, page_rect.y0, page_rect.x1, page_rect.y0 + pdf_y))
        
        self.doc.insert_pdf(temp_doc, from_page=0, to_page=0, start_at=page_num + 1)
        new_page_2 = self.doc[page_num + 1]
        new_page_2.set_cropbox(fitz.Rect(page_rect.x0, page_rect.y0 + pdf_y, page_rect.x1, page_rect.y1))
        
        temp_doc.close()
        
        self.viewer.clear_cache()
        self._update_display()
        self._update_thumbnails()
        
        msg = "Đã chia trang thành 2 phần trực tiếp trên tài liệu!"
        self._update_status(msg)
        messagebox.showinfo("Success", msg)

    def _on_canvas_click(self, event):
        """Handle canvas click."""
        if not self.split_mode and not self.multi_split_mode or not self.doc:
            return

        # Get click position relative to the page image
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        # Find the page image bounds
        items = self.canvas.find_withtag("page")
        if not items:
            return

        bbox = self.canvas.bbox(items[0])
        if not bbox:
            return

        img_x0, img_y0, img_x1, img_y1 = bbox
        click_y_on_image = canvas_y - img_y0

        if click_y_on_image < 0 or click_y_on_image > (img_y1 - img_y0):
            return

        # Convert to PDF coordinates
        pdf_x, pdf_y = self.viewer.canvas_to_pdf_coords(
            canvas_x - img_x0, click_y_on_image
        )

        if self.multi_split_mode:
            self.multi_split_points.append(click_y_on_image)
            self.multi_split_pdf_points.append(pdf_y)
            self._update_display()
            return

        # Confirm split
        page = self.doc[self.viewer.current_page]
        if messagebox.askyesno(
            "Confirm Split",
            f"Split page {self.viewer.current_page + 1} at "
            f"Y = {pdf_y:.0f} points?\n"
            f"(Page height: {page.rect.height:.0f} points)"
        ):
            try:
                self._split_page_in_memory(self.viewer.current_page, pdf_y)
                self.disable_split_mode()
            except Exception as e:
                messagebox.showerror("Error", f"Split failed:\n{e}")

    def _on_canvas_motion(self, event):
        """Handle mouse motion on canvas."""
        if not self.split_mode or not self.doc:
            return

        canvas_y = self.canvas.canvasy(event.y)
        items = self.canvas.find_withtag("page")
        if not items:
            return

        bbox = self.canvas.bbox(items[0])
        if not bbox:
            return

        img_x0, img_y0, img_x1, img_y1 = bbox
        self.split_line_y = canvas_y - img_y0

        # Draw preview line
        self.canvas.delete("split_line")
        self.canvas.create_line(
            img_x0, canvas_y, img_x1, canvas_y,
            fill="#ff4444", width=2, dash=(8, 4), tags="split_line"
        )

        pdf_x, pdf_y = self.viewer.canvas_to_pdf_coords(0, self.split_line_y)
        self.canvas.create_text(
            img_x0 + 10, canvas_y - 15,
            text=f"✂ Y = {pdf_y:.0f} pt",
            font=("Segoe UI", 10, "bold"),
            fill="#ff4444", anchor="nw", tags="split_line"
        )

    def _on_canvas_resize(self, event):
        """Handle canvas resize."""
        if not self.doc:
            self._show_welcome()

    # ─── Mouse Wheel Scroll ──────────────────────────────────────────

    def _on_canvas_mousewheel(self, event):
        """Handle mouse wheel scroll on canvas - scroll page vertically."""
        if not self.doc:
            return
            
        if getattr(self, 'view_mode', 'single') == 'continuous':
            self.canvas.yview_scroll(-1 * (event.delta // 120), "units")
            self._render_continuous_view()
            return
            
        # Check scroll region: if image fits in canvas, change page instead
        scroll_region = self.canvas.cget("scrollregion")
        if scroll_region:
            parts = scroll_region.split()
            if len(parts) == 4:
                total_h = float(parts[3])
                canvas_h = self.canvas.winfo_height()
                if total_h > canvas_h:
                    # Scrollable - scroll the canvas
                    self.canvas.yview_scroll(-1 * (event.delta // 120), "units")
                    return
        # Not scrollable - change page
        if event.delta > 0:
            self.prev_page()
        else:
            self.next_page()

    def _on_canvas_mousewheel_linux(self, event, direction):
        """Handle mouse wheel on Linux."""
        if direction > 0:
            self._on_canvas_mousewheel(type('E', (), {'delta': 120})())
        else:
            self._on_canvas_mousewheel(type('E', (), {'delta': -120})())

    def _on_canvas_ctrl_mousewheel(self, event):
        """Ctrl + mouse wheel = zoom in/out."""
        if event.delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def _on_canvas_shift_mousewheel(self, event):
        """Shift + mouse wheel = horizontal scroll."""
        self.canvas.xview_scroll(-1 * (event.delta // 120), "units")

    # ─── Drag to Pan ─────────────────────────────────────────────────

    def _on_pan_start(self, event):
        """Start drag-to-pan (middle click)."""
        self._is_panning = True
        self._pan_start_x = event.x
        self._pan_start_y = event.y
        self.canvas.config(cursor="fleur")

    def _on_pan_move(self, event):
        """Move during pan."""
        if not self._is_panning:
            return
        dx = self._pan_start_x - event.x
        dy = self._pan_start_y - event.y
        self.canvas.xview_scroll(dx, "units")
        self.canvas.yview_scroll(dy, "units")
        self._pan_start_x = event.x
        self._pan_start_y = event.y

    def _on_pan_end(self, event):
        """End drag-to-pan."""
        self._is_panning = False
        if not self.split_mode:
            self.canvas.config(cursor="arrow")

    def _on_right_click_or_pan_start(self, event):
        """Right-click: detect if it's a click (context menu) or drag (pan)."""
        self._right_click_x = event.x
        self._right_click_y = event.y
        self._is_panning = False  # Will become True on motion

    def _on_right_click_or_pan_end(self, event):
        """Right-click release: show context menu if no drag occurred."""
        dx = abs(event.x - self._right_click_x) if hasattr(self, '_right_click_x') else 0
        dy = abs(event.y - self._right_click_y) if hasattr(self, '_right_click_y') else 0
        if dx < 5 and dy < 5 and not self._is_panning:
            # It was a click, not a drag — show context menu
            self._show_context_menu(event)
        self._is_panning = False
        if not self.split_mode:
            self.canvas.config(cursor="arrow")

    def _show_context_menu(self, event):
        """Show the right-click context menu."""
        if not self.doc:
            return
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def _on_mousewheel_sidebar(self, event):
        """Handle mousewheel in sidebar."""
        # Check if mouse is over the thumbnail area
        widget = event.widget
        try:
            if str(widget).startswith(str(self.thumb_canvas)) or \
               str(widget).startswith(str(self.thumb_inner)):
                self.thumb_canvas.yview_scroll(
                    -1 * (event.delta // 120), "units"
                )
        except Exception:
            pass

    # ─── Drag & Drop ─────────────────────────────────────────────────

    def _setup_drag_drop(self):
        """Setup file drag-and-drop support."""
        # Try to use tkinterdnd2 if available, otherwise use a simpler approach
        try:
            self.root.drop_target_register('DND_Files')
            self.root.dnd_bind('<<Drop>>', self._on_drop)
        except Exception:
            # tkinterdnd2 not available — that's fine
            pass

    def _on_drop(self, event):
        """Handle file drop."""
        file_path = event.data.strip('{}').strip('"')
        if file_path.lower().endswith('.pdf'):
            self.open_file(file_path)

    # ═══════════════════════════════════════════════════════════════════════
    #  Other Operations
    # ═══════════════════════════════════════════════════════════════════════

    def merge_pdfs(self):
        """Merge multiple PDF files."""
        files = filedialog.askopenfilenames(
            title="Select PDF files to merge",
            filetypes=[("PDF files", "*.pdf")]
        )
        if not files or len(files) < 2:
            messagebox.showwarning(
                "Warning", "Please select at least 2 PDF files to merge."
            )
            return

        out_path = filedialog.asksaveasfilename(
            title="Save Merged PDF As",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile="merged_document.pdf"
        )
        if not out_path:
            return

        try:
            output = self.operations.merge_pdfs(list(files), output_path=out_path)
            messagebox.showinfo(
                "Success",
                f"Merged {len(files)} files!\nSaved to: {output}"
            )
            if messagebox.askyesno("Open Result", "Open merged PDF?"):
                self.open_file(str(output))
        except Exception as e:
            messagebox.showerror("Error", f"Merge failed:\n{e}")

    def split_by_pages_dialog(self):
        """Split PDF by page ranges."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        initial_range = ""
        if hasattr(self, 'selected_pages') and self.selected_pages:
            # Group into ranges (e.g. 1, 2, 3 -> 1-3)
            pages = sorted(list(self.selected_pages))
            parts = []
            start = pages[0]
            prev = pages[0]
            for p in pages[1:]:
                if p == prev + 1:
                    prev = p
                else:
                    parts.append(f"{start+1}-{prev+1}" if start != prev else f"{start+1}")
                    start = p
                    prev = p
            parts.append(f"{start+1}-{prev+1}" if start != prev else f"{start+1}")
            initial_range = ",".join(parts)

        result = simpledialog.askstring(
            "Split by Pages",
            f"Total pages: {self.doc.page_count}\n"
            "Enter page ranges (e.g., '1-3,4-6,7-10'):\n"
            "Each range becomes a separate PDF.",
            initialvalue=initial_range
        )

        if not result:
            return

        try:
            ranges = []
            for part in result.split(","):
                part = part.strip()
                if "-" in part:
                    start, end = part.split("-")
                    ranges.append((int(start) - 1, int(end) - 1))
                else:
                    p = int(part) - 1
                    ranges.append((p, p))

            out_dir = filedialog.askdirectory(
                title="Select Directory to Save Split PDFs"
            )
            if not out_dir:
                return

            src_path = self._get_current_pdf_path_for_batch()
            outputs = self.operations.split_by_pages(
                src_path, ranges, output_dir=out_dir
            )
            messagebox.showinfo(
                "Success",
                f"Split into {len(outputs)} files in:\n{out_dir}\n"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Split failed:\n{e}")

    def split_every_n_pages_dialog(self):
        """Split PDF every N pages."""
        if not self.doc:
            messagebox.showwarning(t("warning", "Warning"), "No document is open.")
            return

        result = simpledialog.askinteger(
            t("file_split_every_n", "Split every N pages"),
            f"Total pages: {self.doc.page_count}\n"
            "Split into files of how many pages?",
            initialvalue=1,
            minvalue=1,
            maxvalue=self.doc.page_count
        )

        if not result:
            return

        try:
            ranges = []
            start = 0
            while start < self.doc.page_count:
                end = min(start + result - 1, self.doc.page_count - 1)
                ranges.append((start, end))
                start += result

            out_dir = filedialog.askdirectory(
                title=t("select_dir", "Select Directory to Save Split PDFs")
            )
            if not out_dir:
                return

            outputs = self.operations.split_by_pages(
                self._get_current_pdf_path_for_batch(), ranges, output_dir=out_dir
            )
            messagebox.showinfo(
                t("success", "Success"),
                f"Split into {len(outputs)} files in:\n{out_dir}\n"
            )
        except Exception as e:
            messagebox.showerror(t("error", "Error"), f"Split failed:\n{e}")

    def rotate_current(self, angle):
        """Rotate the current page or selected pages."""
        if not self.doc:
            return
        try:
            pages_to_rotate = sorted(list(self.selected_pages)) if self.selected_pages else [self.viewer.current_page]
            self._save_undo_state(f"Rotate {len(pages_to_rotate)} pages")
            for p in pages_to_rotate:
                page = self.doc[p]
                page.set_rotation(page.rotation + angle)
            self.viewer.clear_cache()
            self._update_display()
            self._update_thumbnails()
            self._update_status(f"Rotated {len(pages_to_rotate)} pages by {angle}°")
        except Exception as e:
            messagebox.showerror("Error", f"Rotate failed:\n{e}")

    def delete_current_page(self):
        """Delete the current page or selected pages."""
        if not self.doc:
            return

        pages_to_delete = sorted(list(self.selected_pages), reverse=True) if self.selected_pages else [self.viewer.current_page]
        
        if len(pages_to_delete) >= self.doc.page_count:
            messagebox.showwarning("Warning", "Cannot delete all pages in the document.")
            return

        if messagebox.askyesno(
            "Confirm Delete",
            f"Delete {len(pages_to_delete)} pages?"
        ):
            self._save_undo_state(f"Delete {len(pages_to_delete)} pages")
            for p in pages_to_delete:
                self.doc.delete_page(p)
            self.viewer.clear_cache()
            self.selected_pages.clear()
            
            # Ensure current page is valid
            if self.viewer.current_page >= self.doc.page_count:
                self.viewer.go_to_page(self.doc.page_count - 1)
            
            self._update_display()
            self._update_thumbnails()
            self._update_status(f"Deleted {len(pages_to_delete)} pages")

    def extract_current_page(self):
        """Extract current page to a new PDF."""
        if not self.doc:
            return
        try:
            page_num = self.viewer.current_page
            out_path = filedialog.asksaveasfilename(
                title="Save Extracted Page As",
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")],
                initialfile=f"{self.file_path.stem}_page{page_num + 1}.pdf"
            )
            if not out_path:
                return

            import fitz
            new_doc = fitz.open()
            new_doc.insert_pdf(self.doc, from_page=page_num, to_page=page_num)
            new_doc.save(out_path, garbage=4, deflate=True)
            new_doc.close()
            
            messagebox.showinfo(
                "Success",
                f"Page {page_num + 1} extracted to:\n{out_path}"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Extract failed:\n{e}")

    def compress_pdf(self):
        """Compress the current PDF."""
        if not self.file_path:
            messagebox.showwarning("Warning", "No document is open.")
            return

        try:
            out_path = filedialog.asksaveasfilename(
                title="Save Compressed PDF As",
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")],
                initialfile=f"{self.file_path.stem}_compressed.pdf"
            )
            if not out_path:
                return

            src_path = self._get_current_pdf_path_for_batch()
            output, orig_size, new_size = self.operations.compress_pdf(
                src_path, output_path=out_path
            )
            reduction = (1 - new_size / orig_size) * 100 if orig_size > 0 else 0
            messagebox.showinfo(
                "Compression Result",
                f"Original: {format_file_size(orig_size)}\n"
                f"Compressed: {format_file_size(new_size)}\n"
                f"Reduction: {reduction:.1f}%\n"
                f"Saved to: {output}"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Compression failed:\n{e}")

    # ─── Security ────────────────────────────────────────────────────────

    def encrypt_pdf_dialog(self):
        """Encrypt the current PDF."""
        if not self.file_path:
            messagebox.showwarning("Warning", "No document is open.")
            return

        dialog = _EncryptDialog(self.root)
        self.root.wait_window(dialog)

        if dialog.result:
            out_path = filedialog.asksaveasfilename(
                title="Save Encrypted PDF As",
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")],
                initialfile=f"{self.file_path.stem}_encrypted.pdf"
            )
            if not out_path:
                return
                
            try:
                src_path = self._get_current_pdf_path_for_batch()
                output = self.security.encrypt_pdf(
                    src_path,
                    dialog.result["user_password"],
                    dialog.result.get("owner_password"),
                    permissions=dialog.result.get("permissions"),
                    output_path=out_path
                )
                messagebox.showinfo(
                    "Success", f"PDF encrypted!\nSaved to: {output}"
                )
            except Exception as e:
                messagebox.showerror("Error", f"Encryption failed:\n{e}")

    def decrypt_pdf_dialog(self):
        """Decrypt a PDF."""
        file_path = filedialog.askopenfilename(
            title="Select encrypted PDF",
            filetypes=[("PDF files", "*.pdf")]
        )
        if not file_path:
            return

        password = simpledialog.askstring(
            "Decrypt PDF", "Enter password:", show="*"
        )
        if not password:
            return

        try:
            out_path = filedialog.asksaveasfilename(
                title="Save Decrypted PDF As",
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")],
                initialfile=f"{Path(file_path).stem}_decrypted.pdf"
            )
            if not out_path:
                return

            output = self.security.decrypt_pdf(file_path, password, output_path=out_path)
            messagebox.showinfo(
                "Success", f"PDF decrypted!\nSaved to: {output}"
            )
            if messagebox.askyesno("Open Result", "Open decrypted PDF?"):
                self.open_file(str(output))
        except ValueError:
            messagebox.showerror("Error", "Incorrect password.")
        except Exception as e:
            messagebox.showerror("Error", f"Decryption failed:\n{e}")

    # ─── Text & Image Tools ──────────────────────────────────────────────

    def add_text_dialog(self):
        """Add text to the current page."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        dialog = _AddTextDialog(self.root)
        self.root.wait_window(dialog)

        if dialog.result:
            try:
                self.text_image.add_text(
                    self.doc,
                    self.viewer.current_page,
                    dialog.result["text"],
                    (dialog.result["x"], dialog.result["y"]),
                    fontsize=dialog.result.get("fontsize", 12),
                    color=dialog.result.get("color", (0, 0, 0))
                )
                self.viewer.clear_cache()
                self._update_display()
                self._update_status("Text added")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add text:\n{e}")

    def add_image_dialog(self):
        """Add an image to the current page."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        image_path = filedialog.askopenfilename(
            title="Select Image",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff"),
                ("All files", "*.*")
            ]
        )
        if not image_path:
            return

        try:
            page = self.doc[self.viewer.current_page]
            # Place in center, 200x200 default
            cx = page.rect.width / 2
            cy = page.rect.height / 2
            rect = fitz.Rect(cx - 100, cy - 100, cx + 100, cy + 100)

            self.text_image.add_image(
                self.doc, self.viewer.current_page,
                image_path, rect
            )
            self.viewer.clear_cache()
            self._update_display()
            self._update_status("Image added")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add image:\n{e}")

    def insert_blank_page_before(self):
        """Insert a blank page before the current page."""
        self._insert_blank_page(after=False)

    def insert_blank_page_after(self):
        """Insert a blank page after the current page."""
        self._insert_blank_page(after=True)

    def _insert_blank_page(self, after=True):
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        current = self.viewer.current_page
        page = self.doc[current]

        self._save_undo_state("Insert blank page")

        insert_idx = current + 1 if after else current
        # Create a new page with the same dimensions as the current one
        self.doc.new_page(pno=insert_idx, width=page.rect.width, height=page.rect.height)

        self.viewer.clear_cache()
        if after:
            self.viewer.go_to_page(current + 1)
        self._update_display()
        self._update_thumbnails()
        action_text = "sau" if after else "trước"
        self._update_status(f"Đã chèn trang trống vào {action_text} trang {current + 1}.")

    def add_watermark_dialog(self):
        """Add watermark to the document."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        text = simpledialog.askstring(
            "Add Watermark",
            "Enter watermark text:",
            initialvalue="CONFIDENTIAL"
        )
        if not text:
            return

        try:
            self._save_undo_state("Add watermark")
            count = self.text_image.add_text_watermark(
                self.doc, text=text
            )
            self.viewer.clear_cache()
            self._update_display()
            self._update_status(f"Watermark added to {count} pages")
        except Exception as e:
            messagebox.showerror("Error", f"Watermark failed:\n{e}")

    def add_page_numbers_dialog(self):
        """Add page numbers."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        try:
            self._save_undo_state("Add page numbers")
            count = self.text_image.add_page_numbers(self.doc)
            self.viewer.clear_cache()
            self._update_display()
            self._update_status(f"Page numbers added to {count} pages")
            messagebox.showinfo("Success", f"Added page numbers to {count} pages.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed:\n{e}")

    def extract_text_dialog(self):
        """Extract text from the document."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        try:
            text = self.text_image.extract_text(self.doc)

            # Save to file
            output = get_output_dir() / f"{self.file_path.stem}_text.txt"
            with open(output, "w", encoding="utf-8") as f:
                f.write(text)

            # Show in a dialog
            dialog = _TextViewDialog(self.root, "Extracted Text", text)
            self.root.wait_window(dialog)

            self._update_status(f"Text extracted to: {output}")
        except Exception as e:
            messagebox.showerror("Error", f"Text extraction failed:\n{e}")

    def extract_images(self):
        """Extract all images from the document."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        try:
            images = self.text_image.extract_images(self.doc)
            if images:
                messagebox.showinfo(
                    "Success",
                    f"Extracted {len(images)} images to:\n{images[0].parent}"
                )
            else:
                messagebox.showinfo("Info", "No images found in the document.")
        except Exception as e:
            messagebox.showerror("Error", f"Image extraction failed:\n{e}")

    def ocr_text_dialog(self):
        """Perform OCR on the document (non-blocking)."""
        if not self.file_path:
            messagebox.showwarning("Warning", "No document is open.")
            return

        page_num = self.viewer.current_page
        file_path = str(self.file_path)

        def _do_ocr():
            return self.text_image.extract_text_with_ocr(
                file_path, page_num=page_num
            )

        def _on_done(text):
            dialog = _TextViewDialog(
                self.root,
                f"OCR Result (Page {page_num + 1})",
                text
            )
            self.root.wait_window(dialog)

        self._run_in_background(
            _do_ocr,
            callback=_on_done,
            description=f"OCR scanning page {page_num + 1}"
        )

    # ─── Help ────────────────────────────────────────────────────────────

    def show_user_manual(self):
        """Show detailed user manual dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("📖 Hướng dẫn sử dụng PDF Editor Pro")
        dialog.geometry("850x700")
        dialog.configure(bg=COLORS["bg_dark"])
        dialog.transient(self.root)
        
        # Header
        header = tk.Frame(dialog, bg=COLORS["accent"], height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="📖 HƯỚNG DẪN SỬ DỤNG", font=("Segoe UI", 16, "bold"),
                 bg=COLORS["accent"], fg="white").pack(side=tk.LEFT, padx=20, pady=15)
                 
        # Scrollable Text Area
        text_frame = tk.Frame(dialog, bg=COLORS["bg_dark"])
        text_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        text = tk.Text(text_frame, wrap=tk.WORD, font=("Segoe UI", 11),
                       bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                       padx=20, pady=20, relief=tk.FLAT,
                       insertbackground=COLORS["text_primary"],
                       spacing1=5, spacing2=2, spacing3=5)
        scrollbar = tk.Scrollbar(text_frame, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Tags for formatting
        text.tag_configure("h1", font=("Segoe UI", 14, "bold"), foreground=COLORS["accent"], spacing1=15, spacing3=10)
        text.tag_configure("h2", font=("Segoe UI", 12, "bold"), foreground="#E2E8F0", spacing1=10, spacing3=5)
        text.tag_configure("bold", font=("Segoe UI", 11, "bold"))
        text.tag_configure("code", font=("Consolas", 10), background="#1E293B", foreground="#38BDF8")
        
        content = [
            ("Chào mừng bạn đến với PDF Editor Pro!\n", "h1"),
            ("Đây là phần mềm chỉnh sửa PDF ngoại tuyến mạnh mẽ, bảo mật, xử lý mọi thứ hoàn toàn trên máy tính của bạn.\n\n", ""),
            
            ("1. CÁC THAO TÁC CƠ BẢN\n", "h1"),
            ("Mở file: ", "bold"), ("Nhấn Ctrl+O hoặc dùng nút 'Mở PDF'. Bạn cũng có thể mở danh sách file gần đây.\n", ""),
            ("Cuộn trang: ", "bold"), ("Sử dụng con lăn chuột. Phần mềm hỗ trợ cuộn liên tục (Continuous) hoặc xem từng trang (Single Page).\n", ""),
            ("Lưu file: ", "bold"), ("Sau khi chỉnh sửa, nhấn 'Lưu' (Ctrl+S) để lưu đè, hoặc 'Lưu thành' để tạo bản sao. Các file lưu tự động mặc định nằm trong thư mục 'Tài liệu' (Documents) của bạn.\n\n", ""),
            
            ("2. CÔNG CỤ TÁCH TRANG (SPLIT)\n", "h1"),
            ("Phần mềm cung cấp 3 công cụ tách trang độc đáo:\n", ""),
            ("• Tách theo tọa độ Y: ", "bold"), ("Rất hữu ích khi bạn muốn cắt bỏ phần viền thừa (ví dụ: mép dưới của file scan). Bạn điền số (ví dụ 100) để cắt 100 pixel tính từ trên xuống.\n", ""),
            ("• Tách theo chữ (OCR): ", "bold"), ("Phần mềm tự động đọc chữ trên trang và chia trang mỗi khi gặp một từ khóa bạn chỉ định (vd: 'Chương 1', 'Mục lục').\n", ""),
            ("• Tách tự động (Khoảng trắng): ", "bold"), ("Máy tự động tìm các dải giấy trắng nằm ngang (như khoảng cách giữa các khổ thơ, hình ảnh) để cắt mà không cắt ngang chữ.\n\n", ""),
            
            ("3. CHỈNH SỬA & GỘP FILE\n", "h1"),
            ("• Gộp nhiều file: ", "bold"), ("Vào 'Tệp -> Gộp PDF', chọn nhiều file PDF. Kéo thả để sắp xếp thứ tự và nhấn Gộp. File mới sẽ tự mở ra.\n", ""),
            ("• Xoay trang: ", "bold"), ("Trên thanh công cụ, nhấn 'Xoay trái/phải' trang hiện tại.\n", ""),
            ("• Chèn trang trống: ", "bold"), ("Bạn có thể thêm trang trắng vào trước/sau trang đang xem để ghi chú.\n\n", ""),
            
            ("4. THÊM NỘI DUNG (CHỮ, ẢNH, DẤU THỦY TRYỀN)\n", "h1"),
            ("• Chữ & Ảnh: ", "bold"), ("Vào menu Công cụ -> Thêm Chữ / Thêm Ảnh. Nhập nội dung, chọn màu, kích thước và TỌA ĐỘ (X, Y) để đặt vào trang.\n", ""),
            ("• Dấu thủy ấn (Watermark): ", "bold"), ("Bảo vệ bản quyền bằng cách chèn dòng chữ mờ chéo qua các trang.\n", ""),
            ("• Số trang: ", "bold"), ("Tự động đánh số thứ tự cho toàn bộ tài liệu (vd: Trang 1/10) ở góc dưới.\n\n", ""),
            
            ("5. NHẬN DẠNG CHỮ TỪ ẢNH (OCR)\n", "h1"),
            ("Nếu file PDF của bạn là ảnh chụp (không bôi đen được chữ), hãy dùng công cụ OCR:\n", ""),
            ("- Vào Công cụ -> Nhận dạng chữ (OCR).\n", ""),
            ("- Chọn ngôn ngữ (Tiếng Việt/Tiếng Anh).\n", ""),
            ("- Máy sẽ đọc ảnh và tạo ra một file PDF mới có chứa lớp chữ ẩn bên dưới. Bạn có thể bôi đen, copy và tìm kiếm chữ bình thường!\n", ""),
            ("Lưu ý: OCR khá tốn thời gian tùy độ dài file. Hãy xem mục 'Trợ giúp -> OCR Info & GPU' để tăng tốc bằng card đồ họa.\n\n", ""),
            
            ("6. XỬ LÝ HÀNG LOẠT (BATCH OPERATIONS)\n", "h1"),
            ("Menu 'Hàng loạt' (Batch) giúp bạn xử lý nhiều trang cùng lúc với hộp thoại chọn dải trang (Page Range) tiện lợi (VD: 1-5, 8, 11-15):\n", ""),
            ("• Xoay hàng loạt: ", "bold"), ("Xoay cùng lúc nhiều trang theo góc chỉ định (90, 180, 270).\n", ""),
            ("• Xóa hàng loạt: ", "bold"), ("Xóa nhanh các dải trang không cần thiết.\n", ""),
            ("• Trích xuất hàng loạt (Extract): ", "bold"), ("Lưu các dải trang được chọn thành một tệp PDF mới.\n", ""),
            ("• Xuất ảnh hàng loạt (Export Images): ", "bold"), ("Chuyển đổi các trang đã chọn thành các tệp hình ảnh (PNG/JPG).\n", ""),
            ("• Tách hàng loạt theo tỷ lệ %: ", "bold"), ("Cắt đôi (hoặc cắt theo tỷ lệ bất kỳ) cho hàng loạt trang cùng một lúc.\n", ""),
            ("• OCR Tách hàng loạt & Cắt đoạn chữ: ", "bold"), ("Áp dụng chức năng tách/cắt thông minh dựa trên AI quét chữ (OCR) cho một nhóm trang được chọn.\n\n", ""),
            
            ("7. BẢO MẬT & TỐI ƯU\n", "h1"),
            ("• Đặt mật khẩu: ", "bold"), ("Vào menu Bảo mật -> Mã hóa. Chuẩn mã hóa AES-256 an toàn nhất hiện nay.\n", ""),
            ("• Nén file: ", "bold"), ("Giảm dung lượng file PDF nặng (nhất là file scan) để dễ dàng gửi email.\n\n", ""),
            
            ("7. GIẢI QUYẾT LỖI THƯỜNG GẶP\n", "h1"),
            ("1. Mở app không lên / Thiếu thư viện: ", "bold"), ("Đảm bảo bạn đã chạy file ", ""), ("setup.bat", "code"), (" trước khi chạy file ", ""), ("run.bat", "code"), (" lần đầu.\n", ""),
            ("2. Báo lỗi Poppler khi làm OCR: ", "bold"), ("Máy cần thư viện Poppler. Lỗi này thường do setup bị lỗi mạng, hãy chạy lại setup.bat.\n", ""),
            ("3. App chạy chậm/Giật khi cuộn: ", "bold"), ("Việc render PDF độ phân giải cao tốn CPU. Hệ thống đã tối đa hóa bằng cách tự động dùng RAM để cache. Nếu RAM bạn trống nhiều, app sẽ load trước nhiều trang để cuộn mượt hơn.\n\n", ""),
            
            ("Mọi dữ liệu của bạn đều xử lý OFFLINE, không bao giờ gửi lên Internet.", "h2")
        ]
        
        text.config(state=tk.NORMAL)
        text.delete("1.0", tk.END)
        for t, tag in content:
            if tag:
                text.insert(tk.END, t, tag)
            else:
                text.insert(tk.END, t)
        text.config(state=tk.DISABLED)
        
        # Close button
        btn = tk.Button(dialog, text="Đóng Hướng Dẫn", font=("Segoe UI", 11, "bold"),
                        bg=COLORS["bg_panel"], fg="white",
                        activebackground=COLORS["accent"],
                        relief=tk.FLAT, padx=25, pady=8,
                        command=dialog.destroy)
        btn.pack(pady=(0, 20))

    def show_ocr_info(self):
        """Show OCR engine info and GPU upgrade guide."""
        from src.ocr_engine import get_ocr_engine
        engine = get_ocr_engine()
        info = engine.get_ocr_info()

        source_label = {
            "system": "✅ Hệ thống (ưu tiên)",
            "bundled": "📦 Nội bộ (bundled)",
            "none": "❌ Không tìm thấy"
        }.get(info["source"], info["source"])

        # Check GPU availability
        gpu_status = "❌ Không (Tesseract chỉ chạy CPU)"
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                gpu_status = f"✅ {gpu_name}"
            else:
                gpu_status = "⚠️ Có PyTorch nhưng không tìm thấy CUDA GPU"
        except ImportError:
            gpu_status = "❌ Chưa cài PyTorch (cần cho EasyOCR GPU)"

        dialog = tk.Toplevel(self.root)
        dialog.title("🔍 OCR Info & GPU Guide")
        dialog.geometry("720x680")
        dialog.configure(bg=COLORS["bg_dark"])
        dialog.transient(self.root)
        dialog.grab_set()

        # Scrollable text
        text = tk.Text(dialog, wrap=tk.WORD, font=("Consolas", 11),
                       bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                       padx=15, pady=15, relief=tk.FLAT,
                       insertbackground=COLORS["text_primary"])
        scrollbar = tk.Scrollbar(dialog, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        content = f"""═══════════════════════════════════════════
   THÔNG TIN OCR HIỆN TẠI
═══════════════════════════════════════════

  Nguồn Tesseract:  {source_label}
  Đường dẫn:        {info['path']}
  Ngôn ngữ mặc định: {info['lang']}
  Thư mục tessdata: {info['tessdata']}
  GPU:              {gpu_status}

═══════════════════════════════════════════
   NÂNG CẤP OCR VỚI GPU (TÙY CHỌN)
═══════════════════════════════════════════

Tesseract OCR (đang dùng) chỉ chạy trên CPU.
Nếu bạn có card GPU NVIDIA và muốn OCR nhanh
hơn 5-10 lần, bạn có thể cài thêm EasyOCR
hoặc PaddleOCR bên ngoài.

───────────────────────────────────────────
  CÁCH 1: EasyOCR (Dễ nhất, khuyên dùng)
───────────────────────────────────────────

Bước 1: Mở CMD hoặc PowerShell với quyền Admin

Bước 2: Cài PyTorch (hỗ trợ GPU CUDA):
  pip install torch torchvision --index-url \\
    https://download.pytorch.org/whl/cu121

Bước 3: Cài EasyOCR:
  pip install easyocr

Bước 4: Kiểm tra:
  python -c "import easyocr; \\
    r = easyocr.Reader(['vi','en'], gpu=True); \\
    print('EasyOCR GPU OK!')"

  * Lần chạy đầu sẽ tự tải mô hình (~100MB)
  * Hỗ trợ 80+ ngôn ngữ, tiếng Việt rất tốt
  * Dung lượng: ~2GB (PyTorch + models)

───────────────────────────────────────────
  CÁCH 2: PaddleOCR (Nhanh nhất)
───────────────────────────────────────────

Bước 1: Cài PaddlePaddle GPU:
  pip install paddlepaddle-gpu

Bước 2: Cài PaddleOCR:
  pip install paddleocr

Bước 3: Kiểm tra:
  python -c "from paddleocr import PaddleOCR; \\
    ocr = PaddleOCR(use_gpu=True, lang='vi'); \\
    print('PaddleOCR GPU OK!')"

  * Nhanh nhất trong 3 engine
  * Hỗ trợ tiếng Việt tốt
  * Dung lượng: ~1.5GB

───────────────────────────────────────────
  SO SÁNH CÁC ENGINE OCR
───────────────────────────────────────────

  Engine      | GPU | Tốc độ  | Chính xác
  ------------|-----|---------|----------
  Tesseract   | ❌  | Trung bình | Tốt
  EasyOCR     | ✅  | Nhanh    | Rất tốt
  PaddleOCR   | ✅  | Rất nhanh| Rất tốt

───────────────────────────────────────────
  LƯU Ý QUAN TRỌNG
───────────────────────────────────────────

• Cần card NVIDIA có CUDA (GTX 1050 trở lên)
• Kiểm tra CUDA: nvidia-smi (trong CMD)
• EasyOCR/PaddleOCR là TÙY CHỌN, không bắt
  buộc. Tesseract hiện tại vẫn hoạt động tốt
  cho hầu hết tài liệu.
• Sau khi cài, khởi động lại ứng dụng để
  hệ thống tự nhận diện engine mới.
"""
        text.insert("1.0", content)
        text.configure(state=tk.DISABLED)

        # Close button
        btn = tk.Button(dialog, text="Đóng", font=("Segoe UI", 12, "bold"),
                        bg=COLORS["accent"], fg="white",
                        activebackground=COLORS["accent_light"],
                        relief=tk.FLAT, padx=30, pady=8,
                        command=dialog.destroy)
        btn.pack(pady=10)

    def show_about(self):
        messagebox.showinfo(
            "About PDF Editor Pro",
            "⚡ PDF Editor Pro — Offline Edition\n\n"
            "A comprehensive PDF editor running entirely offline.\n"
            "Built with Python, PyMuPDF, OpenCV, and Tesseract OCR.\n\n"
            "Features:\n"
            "• Smart page splitting (Y coordinate / OCR text / Auto-detect)\n"
            "• Merge, split, rotate, crop pages\n"
            "• Add text, images, watermarks\n"
            "• Annotations and highlights\n"
            "• Encrypt/Decrypt with AES-256\n"
            "• OCR text recognition\n"
            "• Extract text and images\n"
            "• Compress PDF\n\n"
            "All libraries run locally — no internet required."
        )

    def show_shortcuts(self):
        shortcuts_text = (
            "═══════════  File  ═══════════\n"
            "Ctrl+O        Open PDF\n"
            "Ctrl+S        Save As\n"
            "Ctrl+P        Print\n"
            "\n═══════════  Edit  ═══════════\n"
            "Ctrl+Z        Undo\n"
            "Ctrl+Y        Redo\n"
            "Ctrl+F        Find Text\n"
            "Ctrl+C        Copy Page Text\n"
            "Ctrl+G        Go to Page\n"
            "R             Rotate 90° CW\n"
            "Delete        Delete Current Page\n"
            "\n═══════════  Navigation  ═══════════\n"
            "← / →         Previous / Next page\n"
            "Page Up/Down  Previous / Next page\n"
            "Home / End    First / Last page\n"
            "\n═══════════  View  ═══════════\n"
            "Ctrl+= / –    Zoom in / out\n"
            "Ctrl+0        Reset zoom to 100%\n"
            "Ctrl+Wheel    Zoom in / out\n"
            "Mouse Wheel   Scroll / Change page\n"
            "Shift+Wheel   Horizontal scroll\n"
            "Middle-drag   Pan view\n"
            "Right-click   Context menu\n"
            "F5            Refresh display\n"
            "F11           Toggle fullscreen\n"
            "Escape        Cancel split mode"
        )
        _TextViewDialog(self.root, "⌨️ Keyboard Shortcuts", shortcuts_text)

    # ─── Status ──────────────────────────────────────────────────────────

    def _update_status(self, message):
        """Update the status bar message."""
        self.status_var.set(message)
        logger.info(message)

    def _get_current_pdf_path_for_batch(self):
        """
        Return the path to the current document for batch operations.
        If the document has unsaved edits, it saves to a temp file first.
        """
        if not self._undo_stack:
            return str(self.file_path)
            
        import tempfile
        import os
        fd, path = tempfile.mkstemp(suffix=".pdf", prefix="pdf_edit_tmp_")
        os.close(fd)
        self.doc.save(path, garbage=4, deflate=True)
        return path

    # ═══════════════════════════════════════════════════════════════════════
    #  NEW: Additional Features
    # ═══════════════════════════════════════════════════════════════════════

    # ─── Fit Page ────────────────────────────────────────────────────────

    def fit_page(self):
        """Fit the entire page in the canvas viewport."""
        if not self.doc:
            return
        page = self.doc[self.viewer.current_page]
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        zoom_w = (cw - 40) / page.rect.width
        zoom_h = (ch - 40) / page.rect.height
        new_zoom = min(zoom_w, zoom_h)
        if hasattr(self.viewer, 'set_zoom'):
            self.viewer.set_zoom(new_zoom)
        else:
            self.viewer.zoom_level = new_zoom
        self._update_display()

    # ─── Find Text ──────────────────────────────────────────────────────

    def find_text_dialog(self):
        """Find text in the current PDF."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        search = simpledialog.askstring(
            "Find Text",
            "Enter text to search for:"
        )
        if not search:
            return

        results = []
        for i in range(self.doc.page_count):
            page = self.doc[i]
            instances = page.search_for(search)
            if instances:
                results.append((i, len(instances)))

        if not results:
            messagebox.showinfo("Not Found",
                                f"Text '{search}' not found in the document.")
            return

        # Build results message
        total = sum(count for _, count in results)
        msg_lines = [f"Found '{search}': {total} occurrences in {len(results)} pages\n"]
        for page_num, count in results[:20]:  # Limit to 20 pages
            msg_lines.append(f"  Page {page_num + 1}: {count} occurrences")
        if len(results) > 20:
            msg_lines.append(f"  ... and {len(results) - 20} more pages")

        # Navigate to first result
        first_page = results[0][0]
        self._goto_page(first_page)

        # Highlight the search results on current page
        self._highlight_search_results(search)

        messagebox.showinfo("Search Results", "\n".join(msg_lines))

    def _highlight_search_results(self, search_text):
        """Draw highlight rectangles on search results."""
        if not self.doc:
            return
        page = self.doc[self.viewer.current_page]
        instances = page.search_for(search_text)
        if not instances:
            return

        # Draw highlights on canvas
        items = self.canvas.find_withtag("page")
        if not items:
            return
        bbox = self.canvas.bbox(items[0])
        if not bbox:
            return
        img_x0, img_y0 = bbox[0], bbox[1]

        for rect in instances:
            # Convert PDF coords to canvas coords
            zoom = self.viewer.zoom_level
            x0 = img_x0 + rect.x0 * zoom
            y0 = img_y0 + rect.y0 * zoom
            x1 = img_x0 + rect.x1 * zoom
            y1 = img_y0 + rect.y1 * zoom
            self.canvas.create_rectangle(
                x0, y0, x1, y1,
                outline="#fdcb6e", fill="#fdcb6e",
                stipple="gray25", width=2,
                tags="search_highlight"
            )

        # Auto-remove after 5 seconds
        self.root.after(5000, lambda: self.canvas.delete("search_highlight"))

    # ─── Copy Page Text ─────────────────────────────────────────────────

    def copy_page_text(self):
        """Copy all text from the current page to clipboard."""
        if not self.doc:
            return
        page = self.doc[self.viewer.current_page]
        text = page.get_text("text")
        if text.strip():
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self._update_status(
                f"Copied text from page {self.viewer.current_page + 1}"
            )
        else:
            self._update_status("No text found on this page")

    # ─── Go to Page Dialog ──────────────────────────────────────────────

    def goto_page_dialog(self):
        """Open dialog to jump to a specific page."""
        if not self.doc:
            return
        result = simpledialog.askinteger(
            "Go to Page",
            f"Enter page number (1-{self.doc.page_count}):",
            initialvalue=self.viewer.current_page + 1,
            minvalue=1,
            maxvalue=self.doc.page_count
        )
        if result is not None:
            self._goto_page(result - 1)

    # ─── Export Page as Image ───────────────────────────────────────────

    def export_page_as_image(self):
        """Export the current page as PNG/JPEG image."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        file_path = filedialog.asksaveasfilename(
            title="Export Page as Image",
            defaultextension=".png",
            filetypes=[
                ("PNG Image", "*.png"),
                ("JPEG Image", "*.jpg"),
                ("BMP Image", "*.bmp"),
                ("TIFF Image", "*.tiff"),
            ],
            initialdir=str(get_output_dir()),
            initialfile=f"{self.file_path.stem}_page{self.viewer.current_page + 1}.png"
        )
        if not file_path:
            return

        try:
            dpi = 300  # High quality export
            page = self.doc[self.viewer.current_page]
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)

            if file_path.lower().endswith('.jpg') or file_path.lower().endswith('.jpeg'):
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img.save(file_path, "JPEG", quality=95)
            else:
                pix.save(file_path)

            self._update_status(f"Exported page as: {Path(file_path).name}")
            messagebox.showinfo("Success",
                                f"Page {self.viewer.current_page + 1} exported to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed:\n{e}")

    # ─── Print ──────────────────────────────────────────────────────────

    def print_pdf(self):
        """Print the current PDF using the system default printer."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        try:
            if sys.platform == 'win32':
                os.startfile(str(self.file_path), "print")
                self._update_status("Sent to printer...")
            else:
                subprocess.Popen(['lpr', str(self.file_path)])
                self._update_status("Sent to printer...")
        except Exception as e:
            messagebox.showerror("Error", f"Print failed:\n{e}\n\n"
                                "Try opening the PDF in your system viewer to print.")

    # ─── Metadata / Properties ──────────────────────────────────────────

    def show_metadata_dialog(self):
        """Show PDF metadata and properties."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        meta = self.doc.metadata
        page = self.doc[0]

        info_lines = [
            "═══  PDF Properties  ═══\n",
            f"File:       {self.file_path.name}",
            f"Size:       {format_file_size(os.path.getsize(str(self.file_path)))}",
            f"Pages:      {self.doc.page_count}",
            f"Page Size:  {page.rect.width:.0f} × {page.rect.height:.0f} pt "
            f"({page.rect.width / 72:.1f} × {page.rect.height / 72:.1f} in)",
            "",
            "═══  Metadata  ═══\n",
            f"Title:      {meta.get('title', 'N/A') or 'N/A'}",
            f"Author:     {meta.get('author', 'N/A') or 'N/A'}",
            f"Subject:    {meta.get('subject', 'N/A') or 'N/A'}",
            f"Creator:    {meta.get('creator', 'N/A') or 'N/A'}",
            f"Producer:   {meta.get('producer', 'N/A') or 'N/A'}",
            f"Created:    {meta.get('creationDate', 'N/A') or 'N/A'}",
            f"Modified:   {meta.get('modDate', 'N/A') or 'N/A'}",
            f"Format:     {meta.get('format', 'N/A') or 'N/A'}",
            f"Encrypted:  {self.doc.is_encrypted}",
            "",
            "═══  Security  ═══\n",
            f"Encrypted:  {self.doc.is_encrypted}",
            f"Permissions: print={self.doc.permissions & fitz.PDF_PERM_PRINT > 0}, "
            f"copy={self.doc.permissions & fitz.PDF_PERM_COPY > 0}",
        ]

        _TextViewDialog(self.root, "ℹ️ PDF Properties",
                        "\n".join(info_lines))

    # ─── Refresh Display ────────────────────────────────────────────────

    def _refresh_display(self):
        """Refresh the current view (F5)."""
        if self.doc:
            self.viewer.clear_cache()
            self._update_display()
            self._update_thumbnails()
            self._update_status("Display refreshed")

    # ─── Toggle Fullscreen ──────────────────────────────────────────────

    def _toggle_fullscreen(self):
        """Toggle fullscreen mode (F11)."""
        current = self.root.attributes('-fullscreen')
        self.root.attributes('-fullscreen', not current)
        if not current:
            self._update_status("Fullscreen mode (press F11 to exit)")
        else:
            self._update_status("Windowed mode")

    # ─── Recent Files ───────────────────────────────────────────────────

    def _get_recent_file_path(self):
        """Get path to recent files JSON."""
        from src.utils import get_data_dir
        return get_data_dir() / "recent_files.json"

    def _load_recent_files(self):
        """Load recent files list from disk."""
        try:
            path = self._get_recent_file_path()
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save_recent_files(self):
        """Save recent files list to disk."""
        try:
            path = self._get_recent_file_path()
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self._recent_files, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _add_recent_file(self, file_path):
        """Add a file to the recent files list."""
        file_path = str(file_path)
        if file_path in self._recent_files:
            self._recent_files.remove(file_path)
        self._recent_files.insert(0, file_path)
        self._recent_files = self._recent_files[:10]  # Keep last 10
        self._save_recent_files()
        self._update_recent_menu()

    def _update_recent_menu(self):
        """Update the Recent Files submenu."""
        try:
            self.recent_menu.delete(0, tk.END)
            if not self._recent_files:
                self.recent_menu.add_command(
                    label="(No recent files)",
                    state=tk.DISABLED
                )
                return
            for i, fp in enumerate(self._recent_files):
                name = Path(fp).name
                self.recent_menu.add_command(
                    label=f"{i + 1}. {name}",
                    command=lambda f=fp: self.open_file(f)
                )
            self.recent_menu.add_separator()
            self.recent_menu.add_command(
                label="Clear Recent Files",
                command=self._clear_recent_files
            )
        except Exception:
            pass

    def _clear_recent_files(self):
        """Clear the recent files list."""
        self._recent_files = []
        self._save_recent_files()
        self._update_recent_menu()

    # ─── Undo/Redo ──────────────────────────────────────────────────────

    def _save_undo_state(self, description=""):
        """Save current document state for undo."""
        if not self.doc:
            return
        try:
            state = self.doc.tobytes()
            self._undo_stack.append({
                'data': state,
                'page': self.viewer.current_page,
                'desc': description
            })
            # Limit stack size
            if len(self._undo_stack) > 20:
                self._undo_stack.pop(0)
            # Clear redo stack on new action
            self._redo_stack.clear()
        except Exception as e:
            logger.error(f"Undo save failed: {e}")

    def undo(self):
        """Undo the last action."""
        if not self._undo_stack:
            self._update_status("Nothing to undo")
            return
        if not self.doc:
            return

        try:
            # Save current state to redo stack
            current = self.doc.tobytes()
            self._redo_stack.append({
                'data': current,
                'page': self.viewer.current_page,
                'desc': 'redo'
            })

            # Restore previous state
            state = self._undo_stack.pop()
            self.doc = fitz.open(stream=state['data'], filetype="pdf")
            self.viewer.set_document(self.doc)
            self.viewer.go_to_page(min(state['page'],
                                       self.doc.page_count - 1))
            self._update_display()
            self._update_thumbnails()
            self._update_status(
                f"Undone: {state.get('desc', 'action')}"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Undo failed:\n{e}")

    def redo(self):
        """Redo the last undone action."""
        if not self._redo_stack:
            self._update_status("Nothing to redo")
            return
        if not self.doc:
            return

        try:
            # Save current to undo stack
            current = self.doc.tobytes()
            self._undo_stack.append({
                'data': current,
                'page': self.viewer.current_page,
                'desc': 'undo'
            })

            # Restore redo state
            state = self._redo_stack.pop()
            self.doc = fitz.open(stream=state['data'], filetype="pdf")
            self.viewer.set_document(self.doc)
            self.viewer.go_to_page(min(state['page'],
                                       self.doc.page_count - 1))
            self._update_display()
            self._update_thumbnails()
            self._update_status("Redo completed")
        except Exception as e:
            messagebox.showerror("Error", f"Redo failed:\n{e}")

    # ═══════════════════════════════════════════════════════════════════════
    #  BATCH OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════

    def _parse_page_range(self, text, total_pages):
        """Parse page range string like '1-5, 8, 10-15' or 'all'.
        Returns list of 0-indexed page numbers, or None on error.
        """
        text = text.strip().lower()
        if text in ("all", "*", ""):
            return list(range(total_pages))

        pages = set()
        try:
            for part in text.split(","):
                part = part.strip()
                if "-" in part:
                    start, end = part.split("-", 1)
                    start = int(start.strip())
                    end = int(end.strip())
                    if start < 1 or end > total_pages or start > end:
                        messagebox.showerror(
                            "Error",
                            f"Invalid range '{part}'. "
                            f"Pages must be 1-{total_pages}."
                        )
                        return None
                    pages.update(range(start - 1, end))
                else:
                    p = int(part.strip())
                    if p < 1 or p > total_pages:
                        messagebox.showerror(
                            "Error",
                            f"Page {p} out of range. "
                            f"Total pages: {total_pages}."
                        )
                        return None
                    pages.add(p - 1)
        except ValueError:
            messagebox.showerror(
                "Error",
                "Invalid page range format.\n"
                "Use: '1-5, 8, 10-15' or 'all'"
            )
            return None

        return sorted(pages)

    def batch_rotate_dialog(self):
        """Batch rotate selected pages."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        dialog = _BatchPageRangeDialog(
            self.root,
            title="🔄 Batch Rotate Pages",
            total_pages=self.doc.page_count,
            extra_label="Rotation angle:",
            extra_options=["90° CW", "90° CCW", "180°"]
        )
        self.root.wait_window(dialog)

        if dialog.result is None:
            return

        pages = self._parse_page_range(dialog.result["pages"],
                                        self.doc.page_count)
        if pages is None:
            return

        angle_map = {"90° CW": 90, "90° CCW": -90, "180°": 180}
        angle = angle_map.get(dialog.result["extra"], 90)

        self._save_undo_state(f"Batch rotate {len(pages)} pages")

        count = 0
        for pn in pages:
            page = self.doc[pn]
            page.set_rotation(page.rotation + angle)
            count += 1

        self.viewer.clear_cache()
        self._update_display()
        self._update_thumbnails()
        self._update_status(f"Rotated {count} pages by {angle}°")
        messagebox.showinfo("Done", f"Rotated {count} pages by {angle}°")

    def batch_delete_dialog(self):
        """Batch delete selected pages."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        dialog = _BatchPageRangeDialog(
            self.root,
            title="🗑️ Batch Delete Pages",
            total_pages=self.doc.page_count,
            warning="⚠️ This will permanently delete the selected pages!"
        )
        self.root.wait_window(dialog)

        if dialog.result is None:
            return

        pages = self._parse_page_range(dialog.result["pages"],
                                        self.doc.page_count)
        if pages is None:
            return

        if len(pages) >= self.doc.page_count:
            messagebox.showerror("Error", "Cannot delete ALL pages.")
            return

        if not messagebox.askyesno(
            "Confirm",
            f"Delete {len(pages)} pages?\n"
            f"Pages: {', '.join(str(p+1) for p in pages[:20])}"
            f"{'...' if len(pages) > 20 else ''}"
        ):
            return

        self._save_undo_state(f"Batch delete {len(pages)} pages")

        # Delete in reverse order to preserve indices
        for pn in reversed(pages):
            self.doc.delete_page(pn)

        self.viewer.clear_cache()
        if self.viewer.current_page >= self.doc.page_count:
            self.viewer.go_to_page(self.doc.page_count - 1)
        self._update_display()
        self._update_thumbnails()
        self._update_status(f"Deleted {len(pages)} pages")
        messagebox.showinfo("Done",
                            f"Deleted {len(pages)} pages.\n"
                            f"Remaining: {self.doc.page_count} pages.")

    def batch_extract_dialog(self):
        """Extract selected pages to a new PDF."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        dialog = _BatchPageRangeDialog(
            self.root,
            title="📋 Extract Pages to New PDF",
            total_pages=self.doc.page_count
        )
        self.root.wait_window(dialog)

        if dialog.result is None:
            return

        pages = self._parse_page_range(dialog.result["pages"],
                                        self.doc.page_count)
        if pages is None:
            return

        output_path = filedialog.asksaveasfilename(
            title="Save Extracted Pages As",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialdir=str(get_output_dir()),
            initialfile=f"{self.file_path.stem}_extracted.pdf"
        )
        if not output_path:
            return

        try:
            new_doc = fitz.open()
            for pn in pages:
                new_doc.insert_pdf(self.doc, from_page=pn, to_page=pn)
            new_doc.save(output_path, garbage=4, deflate=True)
            new_doc.close()

            self._update_status(f"Extracted {len(pages)} pages")
            messagebox.showinfo(
                "Done",
                f"Extracted {len(pages)} pages to:\n{output_path}"
            )
            if messagebox.askyesno("Open Result", "Open extracted PDF?"):
                self.open_file(output_path)
        except Exception as e:
            messagebox.showerror("Error", f"Extract failed:\n{e}")

    def batch_split_percentage_dialog(self):
        """Split all pages at the same percentage."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        dialog = _BatchPageRangeDialog(
            self.root,
            title="✂️ Split Pages at Same Percentage",
            total_pages=self.doc.page_count,
            extra_label="Split at (% from top):",
            extra_entry_default="50"
        )
        self.root.wait_window(dialog)

        if dialog.result is None:
            return

        pages = self._parse_page_range(dialog.result["pages"],
                                        self.doc.page_count)
        if pages is None:
            return

        try:
            pct = float(dialog.result.get("extra", "50"))
            if pct <= 0 or pct >= 100:
                messagebox.showerror("Error", "Percentage must be 1-99.")
                return
        except ValueError:
            messagebox.showerror("Error", "Invalid percentage value.")
            return

        try:
            output_doc = fitz.open()
            for i in range(self.doc.page_count):
                page = self.doc[i]
                h = page.rect.height
                w = page.rect.width

                if i in pages:
                    split_y = h * (pct / 100.0)
                    # Top half
                    top_page = output_doc.new_page(
                        width=w, height=split_y
                    )
                    top_page.show_pdf_page(
                        fitz.Rect(0, 0, w, split_y),
                        self.doc, i,
                        clip=fitz.Rect(0, 0, w, split_y)
                    )
                    # Bottom half
                    bottom_h = h - split_y
                    bottom_page = output_doc.new_page(
                        width=w, height=bottom_h
                    )
                    bottom_page.show_pdf_page(
                        fitz.Rect(0, 0, w, bottom_h),
                        self.doc, i,
                        clip=fitz.Rect(0, split_y, w, h)
                    )
                else:
                    # Copy page as-is
                    output_doc.insert_pdf(self.doc, from_page=i, to_page=i)

            output_path = str(
                get_output_dir() /
                f"{self.file_path.stem}_batch_split.pdf"
            )
            output_pages = output_doc.page_count
            output_doc.save(output_path, garbage=4, deflate=True)
            output_doc.close()

            self._update_status(
                f"Split {len(pages)} pages at {pct}%"
            )
            messagebox.showinfo(
                "Done",
                f"Split {len(pages)} pages at {pct}%!\n"
                f"Output: {output_pages} total pages\n"
                f"Saved to: {output_path}"
            )
            if messagebox.askyesno("Open Result", "Open split PDF?"):
                self.open_file(output_path)
        except Exception as e:
            messagebox.showerror("Error", f"Batch split failed:\n{e}")

    def batch_export_images_dialog(self):
        """Export all/selected pages as images."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        dialog = _BatchPageRangeDialog(
            self.root,
            title="🖼️ Export Pages as Images",
            total_pages=self.doc.page_count,
            extra_label="DPI (resolution):",
            extra_entry_default="300"
        )
        self.root.wait_window(dialog)

        if dialog.result is None:
            return

        pages = self._parse_page_range(dialog.result["pages"],
                                        self.doc.page_count)
        if pages is None:
            return

        try:
            dpi = int(dialog.result.get("extra", "300"))
            dpi = max(72, min(600, dpi))
        except ValueError:
            dpi = 300

        # Choose output folder
        out_dir = filedialog.askdirectory(
            title="Select Output Folder for Images",
            initialdir=str(get_output_dir())
        )
        if not out_dir:
            return

        out_dir = Path(out_dir)

        self._update_status(f"Exporting {len(pages)} pages as images...")
        self.root.update()

        try:
            for i, pn in enumerate(pages):
                page = self.doc[pn]
                mat = fitz.Matrix(dpi / 72, dpi / 72)
                pix = page.get_pixmap(matrix=mat)
                img_path = out_dir / f"{self.file_path.stem}_page{pn+1:04d}.png"
                pix.save(str(img_path))

                if (i + 1) % 10 == 0:
                    self._update_status(
                        f"Exporting page {i+1}/{len(pages)}..."
                    )
                    self.root.update()

            self._update_status(f"Exported {len(pages)} pages as images")
            messagebox.showinfo(
                "Done",
                f"Exported {len(pages)} pages as PNG images.\n"
                f"DPI: {dpi}\n"
                f"Saved to: {out_dir}"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Export failed:\n{e}")

    def batch_split_ocr_dialog(self):
        """Batch split selected pages after text found via OCR."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        dialog = _BatchOCRSplitDialog(
            self.root,
            total_pages=self.doc.page_count
        )
        self.root.wait_window(dialog)

        if dialog.result is None:
            return

        pages = self._parse_page_range(dialog.result["pages"],
                                        self.doc.page_count)
        if pages is None:
            return

        search_text = dialog.result["search_text"]
        margin = dialog.result.get("margin", 10)

        if not search_text:
            messagebox.showerror("Error", "Please enter text to search for.")
            return

        out_path = filedialog.asksaveasfilename(
            title="Save Batch Split PDF As",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile=f"{self.file_path.stem}_batch_ocr_split.pdf"
        )
        if not out_path:
            return

        self._update_status(
            f"Batch OCR Split: scanning {len(pages)} pages for '{search_text}'..."
        )
        self.root.update()

        def progress_cb(page_num, total, msg):
            self._update_status(msg)
            self.root.update()

        try:
            src_path = self._get_current_pdf_path_for_batch()
            output_path, found_count, not_found = \
                self.splitter.split_batch_after_text(
                    src_path,
                    pages,
                    search_text,
                    output_path=out_path,
                    margin_below=margin,
                    progress_callback=progress_cb
                )

            # Build result message
            msg_lines = [
                f"Batch OCR Split Complete!\n",
                f"Text searched: '{search_text}'",
                f"Pages processed: {len(pages)}",
                f"Pages split: {found_count}",
                f"Pages unchanged: {len(not_found)}",
            ]
            if not_found:
                nf_str = ", ".join(str(p) for p in not_found[:30])
                if len(not_found) > 30:
                    nf_str += f"... (+{len(not_found) - 30} more)"
                msg_lines.append(f"\nText NOT found on pages:\n{nf_str}")
            msg_lines.append(f"\nSaved to: {output_path}")

            self._update_status(
                f"Batch OCR split: {found_count}/{len(pages)} pages split"
            )
            messagebox.showinfo("Done", "\n".join(msg_lines))

            if messagebox.askyesno("Open Result", "Open the split PDF?"):
                self.open_file(str(output_path))

        except Exception as e:
            messagebox.showerror("Error", f"Batch OCR split failed:\n{e}")

    def batch_crop_between_texts_dialog(self):
        """Crop pages: keep only content between start_text and end_text."""
        if not self.doc:
            messagebox.showwarning("Warning", "No document is open.")
            return

        initial_range = "all"
        if hasattr(self, 'selected_pages') and self.selected_pages:
            initial_range = ", ".join(str(p + 1) for p in sorted(list(self.selected_pages)))

        dialog = _BatchCropBetweenTextsDialog(
            self.root,
            total_pages=self.doc.page_count,
            initial_range=initial_range
        )
        self.root.wait_window(dialog)

        if dialog.result is None:
            return

        pages = self._parse_page_range(dialog.result["pages"],
                                        self.doc.page_count)
        if pages is None:
            return

        start_text = dialog.result["start_text"]
        end_text = dialog.result["end_text"]
        margin_above = dialog.result.get("margin_above", 5)
        margin_below = dialog.result.get("margin_below", 5)
        keep_unmatched = dialog.result.get("keep_unmatched", False)

        if not start_text or not end_text:
            messagebox.showerror("Error",
                                "Both start text and end text are required.")
            return

        out_path = filedialog.asksaveasfilename(
            title="Lưu file Cắt OCR (Save As)",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile=f"{self.file_path.stem}_ocr_cropped.pdf"
        )
        if not out_path:
            return

        self._update_status(
            f"Crop between texts: scanning {len(pages)} pages..."
        )
        self.root.update()

        def progress_cb(page_num, total, msg):
            self._update_status(msg)
            self.root.update()

        template_page_num = self.viewer.current_page if dialog.result.get("use_template") else None

        try:
            src_path = self._get_current_pdf_path_for_batch()
            output_path, total_crops, skipped = \
                self.splitter.crop_between_texts(
                    src_path,
                    pages,
                    start_text,
                    end_text,
                    output_path=out_path,
                    margin_above=margin_above,
                    margin_below=margin_below,
                    keep_unmatched=keep_unmatched,
                    progress_callback=progress_cb,
                    template_page_num=template_page_num
                )

            msg_lines = [
                f"Crop Between Texts Complete!\n",
                f"Start text: '{start_text}'",
                f"End text: '{end_text}'",
                f"Pages scanned: {len(pages)}",
                f"Regions extracted: {total_crops}",
                f"Pages skipped: {len(skipped)}",
            ]
            if skipped:
                sk_str = ", ".join(str(p) for p in skipped[:30])
                if len(skipped) > 30:
                    sk_str += f"... (+{len(skipped) - 30} more)"
                msg_lines.append(
                    f"\nText not found on pages:\n{sk_str}"
                )
            msg_lines.append(f"\nSaved to: {output_path}")

            self._update_status(
                f"Cropped {total_crops} regions from {len(pages)} pages"
            )
            messagebox.showinfo("Done", "\n".join(msg_lines))

            if total_crops > 0 and messagebox.askyesno(
                "Open Result", "Open the cropped PDF?"
            ):
                self.open_file(str(output_path))

        except Exception as e:
            messagebox.showerror("Error",
                                f"Crop between texts failed:\n{e}")

# ═════════════════════════════════════════════════════════════════════════════
#  Custom Dialogs
# ═════════════════════════════════════════════════════════════════════════════

class _BatchPageRangeDialog(tk.Toplevel):
    """Reusable dialog for selecting page ranges for batch operations."""

    def __init__(self, parent, title="Batch Operation",
                 total_pages=0, warning=None,
                 extra_label=None, extra_options=None,
                 extra_entry_default=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("480x420")
        self.configure(bg=COLORS["bg_card"])
        self.resizable(False, False)
        self.result = None
        self.transient(parent)
        self.grab_set()
        self.total_pages = total_pages

        # Title
        tk.Label(
            self, text=title,
            bg=COLORS["bg_card"], fg=COLORS["accent_light"],
            font=("Segoe UI", 14, "bold")
        ).pack(pady=(20, 5))

        # Warning
        if warning:
            tk.Label(
                self, text=warning,
                bg=COLORS["bg_card"], fg=COLORS["danger"],
                font=("Segoe UI", 10, "bold")
            ).pack(pady=5)

        # Instructions
        tk.Label(
            self, text=f"Total pages in document: {total_pages}",
            bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
            font=("Segoe UI", 10)
        ).pack(pady=5)

        fields = tk.Frame(self, bg=COLORS["bg_card"])
        fields.pack(fill=tk.X, padx=30, pady=5)

        # Page range input
        tk.Label(
            fields, text="Page range:",
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            font=("Segoe UI", 11)
        ).pack(anchor="w", pady=(5, 0))

        self.range_entry = tk.Entry(
            fields, bg=COLORS["bg_dark"],
            fg=COLORS["text_primary"],
            insertbackground=COLORS["text_primary"],
            font=("Segoe UI", 11), relief=tk.FLAT
        )
        self.range_entry.pack(fill=tk.X, ipady=4, pady=3)
        self.range_entry.insert(0, "all")
        self.range_entry.focus_set()

        tk.Label(
            fields,
            text="Examples: 'all', '1-10', '1-5, 8, 10-15', '2, 4, 6'",
            bg=COLORS["bg_card"], fg=COLORS["text_dim"],
            font=("Segoe UI", 9)
        ).pack(anchor="w")

        # Quick select buttons
        quick_frame = tk.Frame(fields, bg=COLORS["bg_card"])
        quick_frame.pack(fill=tk.X, pady=(8, 0))

        qbtn_style = {
            "bg": COLORS["bg_hover"], "fg": COLORS["text_primary"],
            "activebackground": COLORS["accent"],
            "relief": tk.FLAT, "padx": 8, "pady": 2,
            "font": ("Segoe UI", 9), "cursor": "hand2",
        }
        tk.Button(
            quick_frame, text="All",
            command=lambda: self._set_range("all"),
            **qbtn_style
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            quick_frame, text="Odd",
            command=lambda: self._set_range(
                ", ".join(str(i) for i in range(1, total_pages + 1, 2))
            ),
            **qbtn_style
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            quick_frame, text="Even",
            command=lambda: self._set_range(
                ", ".join(str(i) for i in range(2, total_pages + 1, 2))
            ),
            **qbtn_style
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            quick_frame, text="First Half",
            command=lambda: self._set_range(f"1-{total_pages // 2}"),
            **qbtn_style
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            quick_frame, text="Last Half",
            command=lambda: self._set_range(
                f"{total_pages // 2 + 1}-{total_pages}"
            ),
            **qbtn_style
        ).pack(side=tk.LEFT, padx=2)

        # Extra option (rotation angle, percentage, DPI, etc.)
        self._extra_var = tk.StringVar()
        if extra_label and extra_options:
            extra_frame = tk.Frame(fields, bg=COLORS["bg_card"])
            extra_frame.pack(fill=tk.X, pady=(15, 0))

            tk.Label(
                extra_frame, text=extra_label,
                bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                font=("Segoe UI", 11)
            ).pack(anchor="w")

            self._extra_var.set(extra_options[0])
            for opt in extra_options:
                tk.Radiobutton(
                    extra_frame, text=opt, value=opt,
                    variable=self._extra_var,
                    bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                    selectcolor=COLORS["bg_dark"],
                    activebackground=COLORS["bg_card"],
                    font=("Segoe UI", 10)
                ).pack(anchor="w", padx=10)

        elif extra_label and extra_entry_default:
            extra_frame = tk.Frame(fields, bg=COLORS["bg_card"])
            extra_frame.pack(fill=tk.X, pady=(15, 0))

            tk.Label(
                extra_frame, text=extra_label,
                bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                font=("Segoe UI", 11)
            ).pack(anchor="w")

            self._extra_entry = tk.Entry(
                extra_frame, bg=COLORS["bg_dark"],
                fg=COLORS["text_primary"],
                insertbackground=COLORS["text_primary"],
                font=("Segoe UI", 11), relief=tk.FLAT, width=10
            )
            self._extra_entry.pack(anchor="w", ipady=4, pady=3)
            self._extra_entry.insert(0, extra_entry_default)
            self._extra_var = None  # Use entry instead

        # Buttons
        btn_frame = tk.Frame(self, bg=COLORS["bg_card"])
        btn_frame.pack(pady=15)

        tk.Button(
            btn_frame, text="✅ Apply", command=self._ok,
            bg=COLORS["accent"], fg="white",
            font=("Segoe UI", 11, "bold"),
            relief=tk.FLAT, padx=25, pady=6, cursor="hand2"
        ).pack(side=tk.LEFT, padx=8)

        tk.Button(
            btn_frame, text="Cancel", command=self.destroy,
            bg=COLORS["bg_hover"], fg=COLORS["text_secondary"],
            font=("Segoe UI", 11),
            relief=tk.FLAT, padx=20, pady=6, cursor="hand2"
        ).pack(side=tk.LEFT, padx=8)

        self.bind("<Return>", lambda e: self._ok())

    def _set_range(self, text):
        """Set the page range entry."""
        self.range_entry.delete(0, tk.END)
        self.range_entry.insert(0, text)

    def _ok(self):
        pages_text = self.range_entry.get().strip()
        if not pages_text:
            messagebox.showerror("Error", "Please enter a page range.")
            return

        extra_val = ""
        if self._extra_var is not None:
            extra_val = self._extra_var.get()
        elif hasattr(self, '_extra_entry'):
            extra_val = self._extra_entry.get().strip()

        self.result = {
            "pages": pages_text,
            "extra": extra_val
        }
        self.destroy()


class _BatchOCRSplitDialog(tk.Toplevel):
    """Dialog for batch OCR split — select pages + enter search text."""

    def __init__(self, parent, total_pages=0):
        super().__init__(parent)
        self.title("🔍 Batch Split by OCR Text")
        self.geometry("500x480")
        self.configure(bg=COLORS["bg_card"])
        self.resizable(False, False)
        self.result = None
        self.transient(parent)
        self.grab_set()
        self.total_pages = total_pages

        # Title
        tk.Label(
            self, text="🔍 Batch Split by OCR Text",
            bg=COLORS["bg_card"], fg=COLORS["accent_light"],
            font=("Segoe UI", 14, "bold")
        ).pack(pady=(15, 5))

        tk.Label(
            self,
            text="Split selected pages after a specific text line.\n"
                 "OCR will scan each page to find the text.",
            bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
            font=("Segoe UI", 10), justify=tk.CENTER
        ).pack(pady=5)

        fields = tk.Frame(self, bg=COLORS["bg_card"])
        fields.pack(fill=tk.X, padx=30, pady=5)

        # ─── Page range ───
        tk.Label(
            fields, text="Page range:",
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            font=("Segoe UI", 11)
        ).pack(anchor="w", pady=(8, 0))

        self.range_entry = tk.Entry(
            fields, bg=COLORS["bg_dark"],
            fg=COLORS["text_primary"],
            insertbackground=COLORS["text_primary"],
            font=("Segoe UI", 11), relief=tk.FLAT
        )
        self.range_entry.pack(fill=tk.X, ipady=4, pady=3)
        self.range_entry.insert(0, "all")

        tk.Label(
            fields,
            text="Examples: 'all', '1-10', '1-5, 8, 10-15'",
            bg=COLORS["bg_card"], fg=COLORS["text_dim"],
            font=("Segoe UI", 9)
        ).pack(anchor="w")

        # Quick buttons
        quick_frame = tk.Frame(fields, bg=COLORS["bg_card"])
        quick_frame.pack(fill=tk.X, pady=(5, 0))

        qbtn = {
            "bg": COLORS["bg_hover"], "fg": COLORS["text_primary"],
            "activebackground": COLORS["accent"],
            "relief": tk.FLAT, "padx": 8, "pady": 2,
            "font": ("Segoe UI", 9), "cursor": "hand2",
        }
        tk.Button(
            quick_frame, text="All",
            command=lambda: self._set_range("all"), **qbtn
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            quick_frame, text="Odd",
            command=lambda: self._set_range(
                ", ".join(str(i) for i in range(1, total_pages + 1, 2))
            ), **qbtn
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            quick_frame, text="Even",
            command=lambda: self._set_range(
                ", ".join(str(i) for i in range(2, total_pages + 1, 2))
            ), **qbtn
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            quick_frame, text="First Half",
            command=lambda: self._set_range(f"1-{total_pages // 2}"), **qbtn
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            quick_frame, text="Last Half",
            command=lambda: self._set_range(
                f"{total_pages // 2 + 1}-{total_pages}"
            ), **qbtn
        ).pack(side=tk.LEFT, padx=2)

        # ─── Search text ───
        tk.Label(
            fields, text="Search text (split after this text):",
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(15, 0))

        self.text_entry = tk.Entry(
            fields, bg=COLORS["bg_dark"],
            fg=COLORS["text_primary"],
            insertbackground=COLORS["text_primary"],
            font=("Segoe UI", 12), relief=tk.FLAT
        )
        self.text_entry.pack(fill=tk.X, ipady=5, pady=3)
        self.text_entry.focus_set()

        tk.Label(
            fields,
            text="The page will be split right after this text line.\n"
                 "Pages where text is NOT found will be kept unchanged.",
            bg=COLORS["bg_card"], fg=COLORS["text_dim"],
            font=("Segoe UI", 9), justify=tk.LEFT
        ).pack(anchor="w")

        # ─── Margin ───
        margin_frame = tk.Frame(fields, bg=COLORS["bg_card"])
        margin_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Label(
            margin_frame, text="Margin below text (pt):",
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            font=("Segoe UI", 10)
        ).pack(side=tk.LEFT)

        self.margin_entry = tk.Entry(
            margin_frame, width=6, bg=COLORS["bg_dark"],
            fg=COLORS["text_primary"],
            insertbackground=COLORS["text_primary"],
            font=("Segoe UI", 10), relief=tk.FLAT
        )
        self.margin_entry.pack(side=tk.LEFT, padx=8, ipady=2)
        self.margin_entry.insert(0, "10")

        # ─── Info ───
        tk.Label(
            self,
            text=f"Total pages: {total_pages}  |  OCR engine: Tesseract",
            bg=COLORS["bg_card"], fg=COLORS["text_dim"],
            font=("Segoe UI", 9)
        ).pack(pady=(8, 0))

        # ─── Buttons ───
        btn_frame = tk.Frame(self, bg=COLORS["bg_card"])
        btn_frame.pack(pady=12)

        tk.Button(
            btn_frame, text="✂️ Split Pages", command=self._ok,
            bg=COLORS["accent"], fg="white",
            font=("Segoe UI", 11, "bold"),
            relief=tk.FLAT, padx=25, pady=6, cursor="hand2"
        ).pack(side=tk.LEFT, padx=8)

        tk.Button(
            btn_frame, text="Cancel", command=self.destroy,
            bg=COLORS["bg_hover"], fg=COLORS["text_secondary"],
            font=("Segoe UI", 11),
            relief=tk.FLAT, padx=20, pady=6, cursor="hand2"
        ).pack(side=tk.LEFT, padx=8)

        self.bind("<Return>", lambda e: self._ok())

    def _set_range(self, text):
        self.range_entry.delete(0, tk.END)
        self.range_entry.insert(0, text)

    def _ok(self):
        pages_text = self.range_entry.get().strip()
        search_text = self.text_entry.get().strip()

        if not pages_text:
            messagebox.showerror("Error", "Please enter a page range.")
            return
        if not search_text:
            messagebox.showerror("Error", "Please enter text to search for.")
            return

        try:
            margin = float(self.margin_entry.get().strip() or "10")
        except ValueError:
            margin = 10

        self.result = {
            "pages": pages_text,
            "search_text": search_text,
            "margin": margin,
        }
        self.destroy()


class _BatchCropBetweenTextsDialog(tk.Toplevel):
    """Dialog for cropping pages between two text markers."""

    def __init__(self, parent, total_pages=0, initial_range="all"):
        super().__init__(parent)
        self.title("✂️ Cắt giữa hai đoạn chữ (OCR)")
        self.geometry("520x580")
        self.configure(bg=COLORS["bg_card"])
        self.resizable(False, False)
        self.result = None
        self.transient(parent)
        self.grab_set()

        # Title
        tk.Label(
            self, text="✂️ Cắt giữa hai đoạn chữ",
            bg=COLORS["bg_card"], fg=COLORS["accent_light"],
            font=("Segoe UI", 14, "bold")
        ).pack(pady=(12, 3))

        tk.Label(
            self,
            text="CHỈ giữ lại nội dung nằm giữa đoạn chữ Bắt đầu và Kết thúc.\n"
                 "1 trang có thể sinh ra NHIỀU trang nếu mẫu lặp lại.\n"
                 "Mọi thứ nằm ngoài vùng chọn sẽ bị xóa bỏ.",
            bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
            font=("Segoe UI", 9), justify=tk.CENTER
        ).pack(pady=3)

        fields = tk.Frame(self, bg=COLORS["bg_card"])
        fields.pack(fill=tk.X, padx=25, pady=3)

        # ─── Start text ───
        tk.Label(
            fields, text="Đoạn chữ BẮT ĐẦU vùng cắt:",
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(8, 0))

        self.start_entry = tk.Entry(
            fields, bg=COLORS["bg_dark"],
            fg=COLORS["text_primary"],
            insertbackground=COLORS["text_primary"],
            font=("Segoe UI", 12), relief=tk.FLAT
        )
        self.start_entry.pack(fill=tk.X, ipady=4, pady=2)
        self.start_entry.focus_set()

        # ─── End text ───
        tk.Label(
            fields, text="Đoạn chữ KẾT THÚC vùng cắt:",
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(10, 0))

        self.end_entry = tk.Entry(
            fields, bg=COLORS["bg_dark"],
            fg=COLORS["text_primary"],
            insertbackground=COLORS["text_primary"],
            font=("Segoe UI", 12), relief=tk.FLAT
        )
        self.end_entry.pack(fill=tk.X, ipady=4, pady=2)

        # ─── Page range ───
        tk.Label(
            fields, text="Phạm vi trang:",
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            font=("Segoe UI", 10)
        ).pack(anchor="w", pady=(10, 0))

        self.range_entry = tk.Entry(
            fields, bg=COLORS["bg_dark"],
            fg=COLORS["text_primary"],
            insertbackground=COLORS["text_primary"],
            font=("Segoe UI", 10), relief=tk.FLAT
        )
        self.range_entry.pack(fill=tk.X, ipady=3, pady=2)
        self.range_entry.insert(0, initial_range)

        # Quick buttons
        quick_frame = tk.Frame(fields, bg=COLORS["bg_card"])
        quick_frame.pack(fill=tk.X, pady=(4, 0))

        qbtn = {
            "bg": COLORS["bg_hover"], "fg": COLORS["text_primary"],
            "activebackground": COLORS["accent"],
            "relief": tk.FLAT, "padx": 6, "pady": 1,
            "font": ("Segoe UI", 8), "cursor": "hand2",
        }
        tk.Button(
            quick_frame, text="Tất cả",
            command=lambda: self._set_range("all"), **qbtn
        ).pack(side=tk.LEFT, padx=1)
        tk.Button(
            quick_frame, text="Lẻ",
            command=lambda: self._set_range(
                ", ".join(str(i) for i in range(1, total_pages + 1, 2))
            ), **qbtn
        ).pack(side=tk.LEFT, padx=1)
        tk.Button(
            quick_frame, text="Chẵn",
            command=lambda: self._set_range(
                ", ".join(str(i) for i in range(2, total_pages + 1, 2))
            ), **qbtn
        ).pack(side=tk.LEFT, padx=1)
        tk.Button(
            quick_frame, text="Nửa đầu",
            command=lambda: self._set_range(f"1-{total_pages // 2}"),
            **qbtn
        ).pack(side=tk.LEFT, padx=1)
        tk.Button(
            quick_frame, text="Nửa sau",
            command=lambda: self._set_range(
                f"{total_pages // 2 + 1}-{total_pages}"
            ), **qbtn
        ).pack(side=tk.LEFT, padx=1)

        # ─── Margins ───
        margin_frame = tk.Frame(fields, bg=COLORS["bg_card"])
        margin_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Label(
            margin_frame, text="Căn lề trên (pt):",
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            font=("Segoe UI", 9)
        ).pack(side=tk.LEFT)
        self.margin_above_entry = tk.Entry(
            margin_frame, width=5, bg=COLORS["bg_dark"],
            fg=COLORS["text_primary"],
            insertbackground=COLORS["text_primary"],
            font=("Segoe UI", 9), relief=tk.FLAT
        )
        self.margin_above_entry.pack(side=tk.LEFT, padx=4, ipady=2)
        self.margin_above_entry.insert(0, "5")

        tk.Label(
            margin_frame, text="  Căn lề dưới (pt):",
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            font=("Segoe UI", 9)
        ).pack(side=tk.LEFT)
        self.margin_below_entry = tk.Entry(
            margin_frame, width=5, bg=COLORS["bg_dark"],
            fg=COLORS["text_primary"],
            insertbackground=COLORS["text_primary"],
            font=("Segoe UI", 9), relief=tk.FLAT
        )
        self.margin_below_entry.pack(side=tk.LEFT, padx=4, ipady=2)
        self.margin_below_entry.insert(0, "5")

        # ─── Use template checkbox ───
        self.template_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            fields,
            text="Dùng trang hiện tại làm mẫu chuẩn (Nhanh! Quét OCR 1 lần duy nhất)",
            variable=self.template_var,
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            selectcolor=COLORS["bg_dark"],
            activebackground=COLORS["bg_card"],
            font=("Segoe UI", 9, "bold")
        ).pack(anchor="w", pady=(10, 0))

        # ─── Keep unmatched checkbox ───
        self.keep_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            fields,
            text="Giữ nguyên các trang không tìm thấy chữ (không cắt bỏ)",
            variable=self.keep_var,
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            selectcolor=COLORS["bg_dark"],
            activebackground=COLORS["bg_card"],
            font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(5, 0))

        # ─── Info ───
        tk.Label(
            self,
            text=f"Tổng số: {total_pages} trang  |  Công cụ OCR: Tesseract  |  "
                 "1 trang có thể sinh ra nhiều trang nhỏ hơn",
            bg=COLORS["bg_card"], fg=COLORS["text_dim"],
            font=("Segoe UI", 8)
        ).pack(pady=(6, 0))

        # ─── Buttons ───
        btn_frame = tk.Frame(self, bg=COLORS["bg_card"])
        btn_frame.pack(pady=10)

        tk.Button(
            btn_frame, text="✂️ Thực hiện Cắt", command=self._ok,
            bg=COLORS["accent"], fg="white",
            font=("Segoe UI", 11, "bold"),
            relief=tk.FLAT, padx=25, pady=6, cursor="hand2"
        ).pack(side=tk.LEFT, padx=8)

        tk.Button(
            btn_frame, text="Hủy", command=self.destroy,
            bg=COLORS["bg_hover"], fg=COLORS["text_secondary"],
            font=("Segoe UI", 11),
            relief=tk.FLAT, padx=20, pady=6, cursor="hand2"
        ).pack(side=tk.LEFT, padx=8)

        self.bind("<Return>", lambda e: self._ok())

    def _set_range(self, text):
        self.range_entry.delete(0, tk.END)
        self.range_entry.insert(0, text)

    def _ok(self):
        start_text = self.start_entry.get().strip()
        end_text = self.end_entry.get().strip()
        pages_text = self.range_entry.get().strip()

        if not start_text:
            messagebox.showerror("Error", "Please enter start text.")
            return
        if not end_text:
            messagebox.showerror("Error", "Please enter end text.")
            return
        if not pages_text:
            messagebox.showerror("Error", "Please enter page range.")
            return

        try:
            margin_above = float(
                self.margin_above_entry.get().strip() or "5"
            )
        except ValueError:
            margin_above = 5
        try:
            margin_below = float(
                self.margin_below_entry.get().strip() or "5"
            )
        except ValueError:
            margin_below = 5

        self.result = {
            "start_text": start_text,
            "end_text": end_text,
            "pages": pages_text,
            "margin_above": margin_above,
            "margin_below": margin_below,
            "keep_unmatched": self.keep_var.get(),
            "use_template": self.template_var.get(),
        }
        self.destroy()


class _SplitYDialog(tk.Toplevel):
    """Dialog for entering Y coordinate for page splitting."""

    def __init__(self, parent, page_height):
        super().__init__(parent)
        self.title("✂️ Split by Y Coordinate")
        self.geometry("400x250")
        self.configure(bg=COLORS["bg_card"])
        self.resizable(False, False)
        self.result = None
        self.transient(parent)
        self.grab_set()

        tk.Label(
            self, text="Split Page by Y Coordinate",
            bg=COLORS["bg_card"], fg=COLORS["accent_light"],
            font=("Segoe UI", 14, "bold")
        ).pack(pady=(20, 5))

        tk.Label(
            self, text=f"Page height: {page_height:.0f} points",
            bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
            font=("Segoe UI", 10)
        ).pack(pady=5)

        tk.Label(
            self, text="Enter Y coordinate (points from top):",
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            font=("Segoe UI", 11)
        ).pack(pady=(15, 5))

        self.entry = tk.Entry(
            self, bg=COLORS["bg_dark"], fg=COLORS["text_primary"],
            insertbackground=COLORS["text_primary"],
            font=("Segoe UI", 12), justify=tk.CENTER,
            relief=tk.FLAT, width=15
        )
        self.entry.pack(pady=5, ipady=4)
        self.entry.insert(0, str(int(page_height / 2)))
        self.entry.select_range(0, tk.END)
        self.entry.focus_set()
        self.entry.bind("<Return>", lambda e: self._ok())

        btn_frame = tk.Frame(self, bg=COLORS["bg_card"])
        btn_frame.pack(pady=15)

        tk.Button(
            btn_frame, text="✂️ Split", command=self._ok,
            bg=COLORS["accent"], fg="white",
            font=("Segoe UI", 11, "bold"),
            relief=tk.FLAT, padx=20, pady=6, cursor="hand2"
        ).pack(side=tk.LEFT, padx=8)

        tk.Button(
            btn_frame, text="Cancel", command=self.destroy,
            bg=COLORS["bg_hover"], fg=COLORS["text_secondary"],
            font=("Segoe UI", 11),
            relief=tk.FLAT, padx=20, pady=6, cursor="hand2"
        ).pack(side=tk.LEFT, padx=8)

    def _ok(self):
        try:
            self.result = float(self.entry.get())
            self.destroy()
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number.")


class _SplitTextDialog(tk.Toplevel):
    """Dialog for entering text to split after (OCR)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("🔍 Split After Text (OCR)")
        self.geometry("450x300")
        self.configure(bg=COLORS["bg_card"])
        self.resizable(False, False)
        self.result = None
        self.margin = 10
        self.transient(parent)
        self.grab_set()

        tk.Label(
            self, text="Split After Text (OCR Detection)",
            bg=COLORS["bg_card"], fg=COLORS["accent_light"],
            font=("Segoe UI", 14, "bold")
        ).pack(pady=(20, 5))

        tk.Label(
            self,
            text="Enter the text/keyword to search for.\n"
                 "The page will be split just below this text line.",
            bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
            font=("Segoe UI", 10), justify=tk.CENTER
        ).pack(pady=10)

        tk.Label(
            self, text="Search text:",
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            font=("Segoe UI", 11), anchor="w"
        ).pack(fill=tk.X, padx=40)

        self.entry = tk.Entry(
            self, bg=COLORS["bg_dark"], fg=COLORS["text_primary"],
            insertbackground=COLORS["text_primary"],
            font=("Segoe UI", 12),
            relief=tk.FLAT, width=30
        )
        self.entry.pack(padx=40, pady=5, ipady=4, fill=tk.X)
        self.entry.focus_set()
        self.entry.bind("<Return>", lambda e: self._ok())

        # Margin setting
        margin_frame = tk.Frame(self, bg=COLORS["bg_card"])
        margin_frame.pack(fill=tk.X, padx=40, pady=5)

        tk.Label(
            margin_frame, text="Margin below text (pt):",
            bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
            font=("Segoe UI", 10)
        ).pack(side=tk.LEFT)

        self.margin_entry = tk.Entry(
            margin_frame, bg=COLORS["bg_dark"],
            fg=COLORS["text_primary"],
            insertbackground=COLORS["text_primary"],
            font=("Segoe UI", 10), relief=tk.FLAT, width=6
        )
        self.margin_entry.pack(side=tk.LEFT, padx=8, ipady=2)
        self.margin_entry.insert(0, "10")

        btn_frame = tk.Frame(self, bg=COLORS["bg_card"])
        btn_frame.pack(pady=15)

        tk.Button(
            btn_frame, text="🔍 Search & Split", command=self._ok,
            bg=COLORS["accent"], fg="white",
            font=("Segoe UI", 11, "bold"),
            relief=tk.FLAT, padx=20, pady=6, cursor="hand2"
        ).pack(side=tk.LEFT, padx=8)

        tk.Button(
            btn_frame, text="Cancel", command=self.destroy,
            bg=COLORS["bg_hover"], fg=COLORS["text_secondary"],
            font=("Segoe UI", 11),
            relief=tk.FLAT, padx=20, pady=6, cursor="hand2"
        ).pack(side=tk.LEFT, padx=8)

    def _ok(self):
        text = self.entry.get().strip()
        if not text:
            messagebox.showerror("Error", "Please enter search text.")
            return
        try:
            self.margin = float(self.margin_entry.get())
        except ValueError:
            self.margin = 10

        self.result = text
        self.destroy()


class _AutoSplitDialog(tk.Toplevel):
    """Dialog showing auto-detected split points."""

    def __init__(self, parent, split_points):
        super().__init__(parent)
        self.title("🤖 Auto-Detected Split Points")
        self.geometry("500x400")
        self.configure(bg=COLORS["bg_card"])
        self.result = None
        self.transient(parent)
        self.grab_set()

        tk.Label(
            self, text="Auto-Detected Split Points",
            bg=COLORS["bg_card"], fg=COLORS["accent_light"],
            font=("Segoe UI", 14, "bold")
        ).pack(pady=(20, 5))

        tk.Label(
            self, text="Select a split point:",
            bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
            font=("Segoe UI", 10)
        ).pack(pady=5)

        # Listbox
        list_frame = tk.Frame(self, bg=COLORS["bg_card"])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(
            list_frame, bg=COLORS["bg_dark"],
            fg=COLORS["text_primary"],
            selectbackground=COLORS["accent"],
            font=("Consolas", 10),
            yscrollcommand=scrollbar.set,
            relief=tk.FLAT
        )
        self.listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)

        for i, sp in enumerate(split_points):
            emoji = "📏" if sp["type"] == "line" else "⬜"
            self.listbox.insert(
                tk.END,
                f"  {emoji} #{i + 1}  |  {sp['description']}  "
                f"|  conf: {sp['confidence']:.2f}"
            )

        if split_points:
            self.listbox.selection_set(0)

        btn_frame = tk.Frame(self, bg=COLORS["bg_card"])
        btn_frame.pack(pady=15)

        tk.Button(
            btn_frame, text="✂️ Split Here", command=self._ok,
            bg=COLORS["accent"], fg="white",
            font=("Segoe UI", 11, "bold"),
            relief=tk.FLAT, padx=20, pady=6, cursor="hand2"
        ).pack(side=tk.LEFT, padx=8)

        tk.Button(
            btn_frame, text="Cancel", command=self.destroy,
            bg=COLORS["bg_hover"], fg=COLORS["text_secondary"],
            font=("Segoe UI", 11),
            relief=tk.FLAT, padx=20, pady=6, cursor="hand2"
        ).pack(side=tk.LEFT, padx=8)

    def _ok(self):
        sel = self.listbox.curselection()
        if sel:
            self.result = sel[0]
            self.destroy()
        else:
            messagebox.showwarning("Warning", "Please select a split point.")


class _EncryptDialog(tk.Toplevel):
    """Dialog for PDF encryption settings."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("🔒 Encrypt PDF")
        self.geometry("400x350")
        self.configure(bg=COLORS["bg_card"])
        self.resizable(False, False)
        self.result = None
        self.transient(parent)
        self.grab_set()

        tk.Label(
            self, text="Encrypt PDF",
            bg=COLORS["bg_card"], fg=COLORS["accent_light"],
            font=("Segoe UI", 14, "bold")
        ).pack(pady=(20, 15))

        fields = tk.Frame(self, bg=COLORS["bg_card"])
        fields.pack(fill=tk.X, padx=30)

        tk.Label(fields, text="User Password:",
                 bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                 font=("Segoe UI", 11)).pack(anchor="w", pady=(5, 0))
        self.user_pw = tk.Entry(fields, show="*",
                                bg=COLORS["bg_dark"],
                                fg=COLORS["text_primary"],
                                insertbackground=COLORS["text_primary"],
                                font=("Segoe UI", 11), relief=tk.FLAT)
        self.user_pw.pack(fill=tk.X, ipady=4, pady=3)
        self.user_pw.focus_set()

        tk.Label(fields, text="Owner Password (optional):",
                 bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                 font=("Segoe UI", 11)).pack(anchor="w", pady=(10, 0))
        self.owner_pw = tk.Entry(fields, show="*",
                                 bg=COLORS["bg_dark"],
                                 fg=COLORS["text_primary"],
                                 insertbackground=COLORS["text_primary"],
                                 font=("Segoe UI", 11), relief=tk.FLAT)
        self.owner_pw.pack(fill=tk.X, ipady=4, pady=3)

        # Permissions
        self.allow_print = tk.BooleanVar(value=True)
        self.allow_copy = tk.BooleanVar(value=False)

        perm_frame = tk.Frame(self, bg=COLORS["bg_card"])
        perm_frame.pack(fill=tk.X, padx=30, pady=10)

        tk.Checkbutton(
            perm_frame, text="Allow Printing",
            variable=self.allow_print,
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            selectcolor=COLORS["bg_dark"],
            activebackground=COLORS["bg_card"],
            font=("Segoe UI", 10)
        ).pack(anchor="w")

        tk.Checkbutton(
            perm_frame, text="Allow Copying Text",
            variable=self.allow_copy,
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            selectcolor=COLORS["bg_dark"],
            activebackground=COLORS["bg_card"],
            font=("Segoe UI", 10)
        ).pack(anchor="w")

        btn_frame = tk.Frame(self, bg=COLORS["bg_card"])
        btn_frame.pack(pady=15)

        tk.Button(
            btn_frame, text="🔒 Encrypt", command=self._ok,
            bg=COLORS["accent"], fg="white",
            font=("Segoe UI", 11, "bold"),
            relief=tk.FLAT, padx=20, pady=6, cursor="hand2"
        ).pack(side=tk.LEFT, padx=8)

        tk.Button(
            btn_frame, text="Cancel", command=self.destroy,
            bg=COLORS["bg_hover"], fg=COLORS["text_secondary"],
            font=("Segoe UI", 11),
            relief=tk.FLAT, padx=20, pady=6, cursor="hand2"
        ).pack(side=tk.LEFT, padx=8)

    def _ok(self):
        user_pw = self.user_pw.get()
        if not user_pw:
            messagebox.showerror("Error", "User password is required.")
            return

        owner_pw = self.owner_pw.get() or None

        self.result = {
            "user_password": user_pw,
            "owner_password": owner_pw,
            "permissions": {
                "print": self.allow_print.get(),
                "copy": self.allow_copy.get(),
                "modify": False,
                "annotate": False,
                "fill_forms": True,
            }
        }
        self.destroy()


class _AddTextDialog(tk.Toplevel):
    """Dialog for adding text to a page."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("📝 Add Text")
        self.geometry("400x380")
        self.configure(bg=COLORS["bg_card"])
        self.resizable(False, False)
        self.result = None
        self.transient(parent)
        self.grab_set()

        tk.Label(
            self, text="Add Text to Page",
            bg=COLORS["bg_card"], fg=COLORS["accent_light"],
            font=("Segoe UI", 14, "bold")
        ).pack(pady=(20, 15))

        fields = tk.Frame(self, bg=COLORS["bg_card"])
        fields.pack(fill=tk.X, padx=30)

        tk.Label(fields, text="Text:",
                 bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                 font=("Segoe UI", 11)).pack(anchor="w")
        self.text_entry = tk.Text(
            fields, height=4,
            bg=COLORS["bg_dark"], fg=COLORS["text_primary"],
            insertbackground=COLORS["text_primary"],
            font=("Segoe UI", 11), relief=tk.FLAT
        )
        self.text_entry.pack(fill=tk.X, pady=3)
        self.text_entry.focus_set()

        pos_frame = tk.Frame(fields, bg=COLORS["bg_card"])
        pos_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Label(pos_frame, text="X:",
                 bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                 font=("Segoe UI", 11)).pack(side=tk.LEFT)
        self.x_entry = tk.Entry(pos_frame, width=8,
                                bg=COLORS["bg_dark"],
                                fg=COLORS["text_primary"],
                                insertbackground=COLORS["text_primary"],
                                font=("Segoe UI", 11), relief=tk.FLAT)
        self.x_entry.pack(side=tk.LEFT, padx=5, ipady=3)
        self.x_entry.insert(0, "72")

        tk.Label(pos_frame, text="  Y:",
                 bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                 font=("Segoe UI", 11)).pack(side=tk.LEFT)
        self.y_entry = tk.Entry(pos_frame, width=8,
                                bg=COLORS["bg_dark"],
                                fg=COLORS["text_primary"],
                                insertbackground=COLORS["text_primary"],
                                font=("Segoe UI", 11), relief=tk.FLAT)
        self.y_entry.pack(side=tk.LEFT, padx=5, ipady=3)
        self.y_entry.insert(0, "72")

        size_frame = tk.Frame(fields, bg=COLORS["bg_card"])
        size_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Label(size_frame, text="Font size:",
                 bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                 font=("Segoe UI", 11)).pack(side=tk.LEFT)
        self.size_entry = tk.Entry(size_frame, width=5,
                                   bg=COLORS["bg_dark"],
                                   fg=COLORS["text_primary"],
                                   insertbackground=COLORS["text_primary"],
                                   font=("Segoe UI", 11), relief=tk.FLAT)
        self.size_entry.pack(side=tk.LEFT, padx=5, ipady=3)
        self.size_entry.insert(0, "12")

        btn_frame = tk.Frame(self, bg=COLORS["bg_card"])
        btn_frame.pack(pady=15)

        tk.Button(
            btn_frame, text="📝 Add Text", command=self._ok,
            bg=COLORS["accent"], fg="white",
            font=("Segoe UI", 11, "bold"),
            relief=tk.FLAT, padx=20, pady=6, cursor="hand2"
        ).pack(side=tk.LEFT, padx=8)

        tk.Button(
            btn_frame, text="Cancel", command=self.destroy,
            bg=COLORS["bg_hover"], fg=COLORS["text_secondary"],
            font=("Segoe UI", 11),
            relief=tk.FLAT, padx=20, pady=6, cursor="hand2"
        ).pack(side=tk.LEFT, padx=8)

    def _ok(self):
        text = self.text_entry.get("1.0", tk.END).strip()
        if not text:
            messagebox.showerror("Error", "Please enter text.")
            return

        try:
            self.result = {
                "text": text,
                "x": float(self.x_entry.get()),
                "y": float(self.y_entry.get()),
                "fontsize": float(self.size_entry.get()),
                "color": (0, 0, 0),
            }
            self.destroy()
        except ValueError:
            messagebox.showerror("Error", "Invalid position or size values.")


class _TextViewDialog(tk.Toplevel):
    """Dialog for viewing extracted text."""

    def __init__(self, parent, title, text):
        super().__init__(parent)
        self.title(title)
        self.geometry("700x500")
        self.configure(bg=COLORS["bg_card"])
        self.transient(parent)

        header = tk.Label(
            self, text=title,
            bg=COLORS["bg_card"], fg=COLORS["accent_light"],
            font=("Segoe UI", 14, "bold")
        )
        header.pack(pady=(15, 10))

        text_frame = tk.Frame(self, bg=COLORS["bg_card"])
        text_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))

        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_widget = tk.Text(
            text_frame,
            bg=COLORS["bg_dark"], fg=COLORS["text_primary"],
            insertbackground=COLORS["text_primary"],
            font=("Consolas", 10),
            relief=tk.FLAT, wrap=tk.WORD,
            yscrollcommand=scrollbar.set
        )
        self.text_widget.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.text_widget.yview)

        self.text_widget.insert("1.0", text)
        self.text_widget.config(state=tk.NORMAL)

        btn_frame = tk.Frame(self, bg=COLORS["bg_card"])
        btn_frame.pack(pady=10)

        tk.Button(
            btn_frame, text="📋 Copy All",
            command=lambda: self._copy(text),
            bg=COLORS["accent"], fg="white",
            font=("Segoe UI", 10, "bold"),
            relief=tk.FLAT, padx=15, pady=4, cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            btn_frame, text="Close", command=self.destroy,
            bg=COLORS["bg_hover"], fg=COLORS["text_secondary"],
            font=("Segoe UI", 10),
            relief=tk.FLAT, padx=15, pady=4, cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)

    def _copy(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Copied", "Text copied to clipboard!")
