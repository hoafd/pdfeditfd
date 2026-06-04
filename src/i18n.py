import json
from pathlib import Path
from src.utils import logger, get_output_dir

SETTINGS_FILE = get_output_dir() / "settings.json"

TRANSLATIONS = {
    "en": {
        # Menus
        "menu_file": "  File  ",
        "menu_edit": "  Edit  ",
        "menu_tools": "  Tools  ",
        "menu_split": "  ✂ Split  ",
        "menu_batch": "  📦 Batch  ",
        "menu_help": "  Help  ",
        "menu_language": "  🌐 Language  ",

        "file_open": "📂 Open PDF...",
        "file_save": "💾 Save As...",
        "file_recent": "📋 Recent Files",
        "file_merge": "📄 Merge PDFs...",
        "file_split_pages": "📑 Split by Pages...",
        "file_split_every_n": "📑 Split every N pages...",
        "file_compress": "📦 Compress PDF",
        "file_export_img": "🖼️ Export Page as Image...",
        "file_print": "🖨️ Print...",
        "file_encrypt": "🔒 Encrypt PDF...",
        "file_decrypt": "🔓 Decrypt PDF...",
        "file_props": "ℹ️ PDF Properties / Metadata...",
        "file_exit": "❌ Exit",

        "edit_undo": "↩️ Undo",
        "edit_redo": "↪️ Redo",
        "edit_find": "🔍 Find Text...",
        "edit_copy": "📋 Copy Page Text",
        "edit_goto": "🔢 Go to Page...",
        "edit_rot_cw": "🔄 Rotate 90° CW",
        "edit_rot_ccw": "🔄 Rotate 90° CCW",
        "edit_rot_180": "🔄 Rotate 180°",
        "edit_del_page": "🗑️ Delete Current Page",
        "edit_extract_page": "📋 Extract Current Page",
        "edit_insert_blank_before": "📄 Insert Blank Page Before",
        "edit_insert_blank_after": "📄 Insert Blank Page After",

        "tools_split_y": "✂️ Smart Split (Y Coordinate)",
        "tools_split_text": "🔍 Smart Split (After Text - OCR)",
        "tools_split_auto": "🤖 Smart Split (Auto-Detect)",
        "tools_add_text": "📝 Add Text...",
        "tools_add_img": "🖼️ Add Image...",
        "tools_add_wm": "💧 Add Watermark...",
        "tools_add_page_num": "🔢 Add Page Numbers",
        "tools_extract_text": "📄 Extract All Text",
        "tools_extract_img": "🖼️ Extract All Images",
        "tools_ocr": "🔍 OCR Text (Tesseract)",

        "split_interactive": "🖱️ Click to Split (Interactive)",
        "split_pct": "📏 Split by Percentage...",
        "split_all_y": "✂️ Split ALL Pages at Same Y...",

        "batch_rot": "🔄 Rotate Pages...",
        "batch_del": "🗑️ Delete Pages...",
        "batch_extract": "📋 Extract Pages to New PDF...",
        "batch_split_y": "✂️ Split ALL Pages at Same Y...",
        "batch_split_pct": "✂️ Split ALL Pages at Same %...",
        "batch_split_ocr": "🔍 Split Pages by OCR Text...",
        "batch_crop_ocr": "✂️ Crop Between Texts (OCR)...",
        "batch_wm": "💧 Watermark ALL Pages...",
        "batch_page_num": "🔢 Add Page Numbers to ALL...",
        "batch_export_img": "🖼️ Export ALL Pages as Images...",

        "help_about": "ℹ️ About",
        "help_shortcuts": "⌨️ Keyboard Shortcuts",

        # Toolbar
        "tb_open": "📂 Open",
        "tb_save": "💾 Save",
        "tb_merge": "📄 Merge",
        "tb_split": "✂️ Split",
        "tb_del": "🗑️ Delete",
        "tb_rot": "🔄 Rotate",
        "tb_select": "🖱️ Select",
        "tb_draw": "✏️ Draw",
        "tb_highlight": "🖍️ Highlight",
        "tb_text": "📝 Text",
        "tb_image": "🖼️ Image",
        "tb_split_mode": "✂️ Split Mode",
        "tb_multi_crop": "✂️ Multi-Crop",

        # Sidebar
        "sb_thumbnails": "Thumbnails",
        "sb_all": "All",
        "sb_odd": "Odd",
        "sb_even": "Even",
        "sb_custom": "Custom",
        "sb_clear": "Clear",

        # General
        "lang_en": "English",
        "lang_vi": "Tiếng Việt",
        "success": "Success",
        "warning": "Warning",
        "error": "Error",
        "done": "Done",
        "cancel": "Cancel",
    },
    "vi": {
        # Menus
        "menu_file": "  Tệp  ",
        "menu_edit": "  Chỉnh sửa  ",
        "menu_tools": "  Công cụ  ",
        "menu_split": "  ✂ Tách  ",
        "menu_batch": "  📦 Hàng loạt  ",
        "menu_help": "  Trợ giúp  ",
        "menu_language": "  🌐 Ngôn ngữ  ",

        "file_open": "📂 Mở PDF...",
        "file_save": "💾 Lưu thành...",
        "file_recent": "📋 Tệp gần đây",
        "file_merge": "📄 Gộp nhiều PDF...",
        "file_split_pages": "📑 Tách theo trang...",
        "file_split_every_n": "📑 Tách cứ mỗi N trang thành 1 file...",
        "file_compress": "📦 Nén PDF",
        "file_export_img": "🖼️ Xuất trang thành ảnh...",
        "file_print": "🖨️ In...",
        "file_encrypt": "🔒 Đặt mật khẩu...",
        "file_decrypt": "🔓 Gỡ mật khẩu...",
        "file_props": "ℹ️ Thuộc tính PDF...",
        "file_exit": "❌ Thoát",

        "edit_undo": "↩️ Hoàn tác",
        "edit_redo": "↪️ Làm lại",
        "edit_find": "🔍 Tìm kiếm chữ...",
        "edit_copy": "📋 Copy chữ trong trang",
        "edit_goto": "🔢 Chuyển đến trang...",
        "edit_rot_cw": "🔄 Xoay phải 90°",
        "edit_rot_ccw": "🔄 Xoay trái 90°",
        "edit_rot_180": "🔄 Xoay 180°",
        "edit_del_page": "🗑️ Xóa trang",
        "edit_extract_page": "📋 Trích xuất trang",
        "edit_insert_blank_before": "📄 Chèn trang trống vào trước",
        "edit_insert_blank_after": "📄 Chèn trang trống vào sau",

        "tools_split_y": "✂️ Cắt ngang trang (Theo tọa độ Y)",
        "tools_split_text": "🔍 Cắt ngang trang (Sau đoạn chữ OCR)",
        "tools_split_auto": "🤖 Tự động nhận diện điểm cắt",
        "tools_add_text": "📝 Thêm chữ...",
        "tools_add_img": "🖼️ Thêm ảnh...",
        "tools_add_wm": "💧 Thêm đóng dấu (Watermark)...",
        "tools_add_page_num": "🔢 Thêm số trang",
        "tools_extract_text": "📄 Trích xuất toàn bộ chữ",
        "tools_extract_img": "🖼️ Trích xuất toàn bộ ảnh",
        "tools_ocr": "🔍 Đọc chữ từ ảnh (OCR)",

        "split_interactive": "🖱️ Click để cắt (Thủ công)",
        "split_pct": "📏 Cắt theo tỷ lệ %...",
        "split_all_y": "✂️ Cắt TẤT CẢ trang cùng tọa độ...",

        "batch_rot": "🔄 Xoay nhiều trang...",
        "batch_del": "🗑️ Xóa nhiều trang...",
        "batch_extract": "📋 Trích xuất nhiều trang ra PDF mới...",
        "batch_split_y": "✂️ Cắt TẤT CẢ trang cùng tọa độ...",
        "batch_split_pct": "✂️ Cắt TẤT CẢ trang cùng tỷ lệ %...",
        "batch_split_ocr": "🔍 Cắt trang hàng loạt bằng OCR...",
        "batch_crop_ocr": "✂️ Lấy phần giữa 2 đoạn chữ (OCR)...",
        "batch_wm": "💧 Đóng dấu (Watermark) TẤT CẢ trang...",
        "batch_page_num": "🔢 Thêm số trang cho TẤT CẢ...",
        "batch_export_img": "🖼️ Xuất TẤT CẢ trang ra ảnh...",

        "help_about": "ℹ️ Giới thiệu",
        "help_shortcuts": "⌨️ Phím tắt",

        # Toolbar
        "tb_open": "📂 Mở",
        "tb_save": "💾 Lưu",
        "tb_merge": "📄 Gộp",
        "tb_split": "✂️ Tách",
        "tb_del": "🗑️ Xóa",
        "tb_rot": "🔄 Xoay",
        "tb_select": "🖱️ Chọn",
        "tb_draw": "✏️ Vẽ",
        "tb_highlight": "🖍️ Bôi màu",
        "tb_text": "📝 Thêm chữ",
        "tb_image": "🖼️ Thêm ảnh",
        "tb_split_mode": "✂️ Chế độ cắt",
        "tb_multi_crop": "✂️ Cắt nhiều",

        # Sidebar
        "sb_thumbnails": "Trang",
        "sb_all": "Tất cả",
        "sb_odd": "Lẻ",
        "sb_even": "Chẵn",
        "sb_custom": "Tùy chọn",
        "sb_clear": "Bỏ chọn",

        # General
        "lang_en": "English",
        "lang_vi": "Tiếng Việt",
        "success": "Thành công",
        "warning": "Cảnh báo",
        "error": "Lỗi",
        "done": "Xong",
        "cancel": "Hủy",
    }
}

_current_lang = "vi"

def init_i18n():
    global _current_lang
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                lang = data.get("language", "vi")
                if lang in TRANSLATIONS:
                    _current_lang = lang
    except Exception as e:
        logger.warning(f"Failed to load settings: {e}")

def get_language():
    return _current_lang

def set_language(lang):
    global _current_lang
    if lang in TRANSLATIONS:
        _current_lang = lang
        try:
            SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            if SETTINGS_FILE.exists():
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data["language"] = _current_lang
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.warning(f"Failed to save settings: {e}")

def t(key, default=None):
    if default is None:
        default = key
    return TRANSLATIONS.get(_current_lang, TRANSLATIONS["en"]).get(key, TRANSLATIONS["en"].get(key, default))

# Initialize immediately
init_i18n()
