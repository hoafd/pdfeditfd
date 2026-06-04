# PDF Editor - Ứng dụng chỉnh sửa PDF đa năng (Offline & Self-Contained)

Xây dựng ứng dụng chỉnh sửa PDF hoàn chỉnh, chạy hoàn toàn offline trong thư mục `c:\Users\admin\Documents\pdfeditfd`. Tích hợp OpenCV + Tesseract OCR cho tính năng chia đôi trang PDF thông minh.

## User Review Required

> [!IMPORTANT]
> **Tesseract OCR**: Cần tải Tesseract OCR Windows installer từ [UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) và giải nén vào thư mục `tools/Tesseract-OCR/` trong project. Tôi sẽ tự động hóa bước này bằng script setup, nhưng cần kết nối internet **một lần duy nhất** khi chạy setup lần đầu.

> [!WARNING]  
> **Kích thước dự án**: Do tải Tesseract OCR (~70MB) + OpenCV (~50MB) + các thư viện khác, tổng dung lượng project có thể lên tới ~300-500MB. Điều này là cần thiết để đảm bảo mọi thứ chạy offline.

## Open Questions

> [!IMPORTANT]
> 1. **Ngôn ngữ OCR**: Bạn muốn Tesseract hỗ trợ nhận dạng tiếng Việt (`vie`) ngoài tiếng Anh (`eng`)? Tôi sẽ mặc định cài cả hai.
> 2. **Giao diện**: Tôi dự định dùng **CustomTkinter** (giao diện đẹp, hiện đại) thay vì Tkinter cổ điển. Bạn có đồng ý không?
> 3. **Poppler**: Thư viện `pdf2image` cần Poppler để convert PDF → Image. Tôi sẽ bundle Poppler portable vào `tools/poppler/`. Được chứ?

---

## Cấu trúc thư mục dự án

```
c:\Users\admin\Documents\pdfeditfd\
├── BILL-HKA-T062026.pdf          # File PDF mẫu của bạn
├── setup.bat                      # Script cài đặt tự động (chạy 1 lần)
├── run.bat                        # Script khởi chạy ứng dụng
├── requirements.txt               # Danh sách thư viện Python
├── main.py                        # Entry point
├── venv/                          # Môi trường ảo Python (tự tạo bởi setup.bat)
├── tools/                         # Công cụ bên ngoài (portable)
│   ├── Tesseract-OCR/             # Tesseract OCR portable
│   └── poppler/                   # Poppler portable (cho pdf2image)
├── src/                           # Mã nguồn chính
│   ├── __init__.py
│   ├── app.py                     # Ứng dụng chính (GUI)
│   ├── pdf_viewer.py              # Module hiển thị PDF
│   ├── pdf_operations.py          # Các thao tác PDF cơ bản
│   ├── pdf_split_smart.py         # Chia trang PDF thông minh (OCR + OpenCV)
│   ├── pdf_annotations.py         # Annotations, highlights, chữ ký
│   ├── pdf_security.py            # Mã hóa, giải mã, mật khẩu
│   ├── pdf_text_image.py          # Thêm text, hình ảnh, watermark
│   ├── ocr_engine.py              # OCR engine (Tesseract + OpenCV)
│   └── utils.py                   # Tiện ích chung
├── output/                        # Thư mục xuất file kết quả
└── temp/                          # File tạm trong quá trình xử lý
```

---

## Proposed Changes

### 1. Setup & Environment

#### [NEW] [setup.bat](file:///c:/Users/admin/Documents/pdfeditfd/setup.bat)
Script tự động thiết lập toàn bộ môi trường:
- Tạo Python virtual environment (`venv/`)
- Cài đặt tất cả thư viện Python từ `requirements.txt`
- Tải và giải nén Tesseract OCR portable vào `tools/Tesseract-OCR/`
- Tải và giải nén Poppler portable vào `tools/poppler/`
- Tải tessdata (eng + vie) cho OCR

#### [NEW] [run.bat](file:///c:/Users/admin/Documents/pdfeditfd/run.bat)
Script khởi chạy ứng dụng:
- Activate venv
- Set biến môi trường cho Tesseract/Poppler
- Chạy `main.py`

#### [NEW] [requirements.txt](file:///c:/Users/admin/Documents/pdfeditfd/requirements.txt)
```
PyMuPDF          # PDF manipulation core
pikepdf          # PDF surgery (merge, split, repair)
customtkinter    # Modern GUI framework
Pillow           # Image processing
opencv-python    # OpenCV cho xử lý hình ảnh
pytesseract      # Python wrapper cho Tesseract OCR
pdf2image        # Convert PDF to image
numpy            # Numpy (dependency của OpenCV)
reportlab        # Tạo PDF overlays/watermarks
```

---

### 2. Core Application (GUI)

#### [NEW] [main.py](file:///c:/Users/admin/Documents/pdfeditfd/main.py)
Entry point - khởi tạo đường dẫn tools, import và chạy App

#### [NEW] [app.py](file:///c:/Users/admin/Documents/pdfeditfd/src/app.py)
GUI chính dùng CustomTkinter với layout:
- **Thanh menu trên** (File, Edit, Tools, Page, Security, Help)
- **Sidebar trái**: Thumbnail các trang PDF
- **Canvas chính giữa**: Hiển thị trang PDF đang chọn (zoom, scroll)
- **Toolbar phải**: Các công cụ nhanh (annotate, highlight, add text...)
- **Status bar dưới**: Thông tin file, trang hiện tại

---

### 3. PDF Operations Modules

#### [NEW] [pdf_viewer.py](file:///c:/Users/admin/Documents/pdfeditfd/src/pdf_viewer.py)
Hiển thị PDF trong GUI:
- Render PDF page → image via PyMuPDF
- Zoom in/out, fit-to-width, fit-to-page
- Navigate pages (next/prev/go-to)
- Thumbnail sidebar

#### [NEW] [pdf_operations.py](file:///c:/Users/admin/Documents/pdfeditfd/src/pdf_operations.py)
Thao tác PDF cơ bản:
- **Merge**: Gộp nhiều file PDF
- **Split**: Tách trang (theo range, mỗi trang riêng lẻ)
- **Rotate**: Xoay trang (90°, 180°, 270°)
- **Crop**: Cắt trang theo vùng chọn
- **Reorder**: Sắp xếp lại thứ tự trang
- **Delete pages**: Xóa trang
- **Extract pages**: Trích xuất trang cụ thể

#### [NEW] [pdf_split_smart.py](file:///c:/Users/admin/Documents/pdfeditfd/src/pdf_split_smart.py) ⭐ **Tính năng chính**
Chia đôi trang PDF thành 2 trang riêng biệt:

**Chế độ 1 - Chia theo tọa độ Y:**
- Người dùng click vào vị trí trên canvas để chọn điểm cắt
- Hoặc nhập tọa độ Y thủ công (% hoặc pixel)
- Sử dụng PyMuPDF `CropBox` để tạo 2 trang mới

**Chế độ 2 - Chia sau dòng chữ (OCR + OpenCV):**
1. Convert PDF page → image (300 DPI) via `pdf2image`
2. OpenCV: Grayscale → Threshold → Detect horizontal lines/gaps
3. Tesseract OCR: `image_to_data()` để lấy text + bounding boxes
4. Người dùng nhập keyword/dòng chữ cần tìm
5. Tìm vị trí Y của dòng chữ đó
6. Quy đổi tọa độ image (pixels) → PDF (points) dựa trên DPI
7. Crop trang gốc thành 2 trang mới tại điểm cắt

**Chế độ 3 - Auto-detect (OpenCV):**
- Sử dụng OpenCV để phát hiện khoảng trống lớn (white-space gaps)
- Hoặc phát hiện đường kẻ ngang (horizontal lines) bằng `HoughLinesP`
- Tự động đề xuất điểm cắt

#### [NEW] [pdf_annotations.py](file:///c:/Users/admin/Documents/pdfeditfd/src/pdf_annotations.py)
Ghi chú & đánh dấu:
- **Highlight text**: Tô sáng văn bản
- **Underline/Strikethrough**: Gạch chân/gạch ngang
- **Freehand draw**: Vẽ tự do
- **Sticky notes**: Ghi chú dán
- **Shapes**: Hình chữ nhật, tròn, mũi tên
- **Stamp/Signature**: Đóng dấu, chữ ký (từ ảnh)

#### [NEW] [pdf_security.py](file:///c:/Users/admin/Documents/pdfeditfd/src/pdf_security.py)
Bảo mật:
- **Encrypt**: Mã hóa PDF với mật khẩu (AES-256)
- **Decrypt**: Giải mã PDF
- **Permissions**: Cài đặt quyền (print, copy, modify)
- **Remove password**: Gỡ mật khẩu (khi biết mật khẩu)

#### [NEW] [pdf_text_image.py](file:///c:/Users/admin/Documents/pdfeditfd/src/pdf_text_image.py)
Thêm nội dung:
- **Add text**: Thêm text vào vị trí bất kỳ (chọn font, size, color)
- **Add image**: Chèn hình ảnh vào trang
- **Watermark**: Thêm watermark (text hoặc image, mờ/đậm)
- **Header/Footer**: Thêm đánh số trang, tiêu đề
- **Background**: Thay đổi nền trang

#### [NEW] [pdf_text_image.py](file:///c:/Users/admin/Documents/pdfeditfd/src/pdf_text_image.py)
Trích xuất nội dung:
- **Extract text**: Trích xuất toàn bộ text (PyMuPDF + OCR fallback)
- **Extract images**: Trích xuất tất cả hình ảnh
- **OCR to text**: Nhận dạng text từ PDF scan

---

### 4. OCR & Image Processing Engine

#### [NEW] [ocr_engine.py](file:///c:/Users/admin/Documents/pdfeditfd/src/ocr_engine.py)
Engine OCR + xử lý ảnh:
- Config Tesseract path portable (`tools/Tesseract-OCR/tesseract.exe`)
- Config Poppler path (`tools/poppler/bin/`)
- **Preprocessing pipeline** (OpenCV):
  - Grayscale conversion
  - Adaptive thresholding / Otsu binarization
  - Noise removal (morphological operations)
  - Deskew (chỉnh nghiêng)
  - Border removal
- **OCR functions**:
  - `image_to_string()`: Nhận dạng text
  - `image_to_data()`: Nhận dạng text + vị trí (bounding boxes)
  - `image_to_boxes()`: Character-level bounding boxes
- **Line detection** (OpenCV):
  - Detect horizontal lines via `HoughLinesP`
  - Detect white-space gaps
  - Find text blocks and gaps between them

---

### 5. Utilities

#### [NEW] [utils.py](file:///c:/Users/admin/Documents/pdfeditfd/src/utils.py)
Tiện ích chung:
- Path management (project-relative paths)
- Coordinate conversion (PDF points ↔ image pixels)
- Temporary file management
- Logging
- File size formatting
- Error handling decorators

---

## Tổng hợp tính năng

| # | Tính năng | Thư viện |
|---|-----------|----------|
| 1 | Xem PDF (zoom, scroll, navigate) | PyMuPDF |
| 2 | Merge (gộp PDF) | PyMuPDF |
| 3 | Split trang (range/từng trang) | PyMuPDF |
| 4 | ⭐ Split theo tọa độ Y | PyMuPDF |
| 5 | ⭐ Split sau dòng chữ OCR | Tesseract + OpenCV + PyMuPDF |
| 6 | ⭐ Auto-detect điểm cắt | OpenCV + PyMuPDF |
| 7 | Rotate trang | PyMuPDF |
| 8 | Crop trang | PyMuPDF |
| 9 | Delete/Reorder trang | PyMuPDF |
| 10 | Add text | PyMuPDF + ReportLab |
| 11 | Add image | PyMuPDF |
| 12 | Watermark | PyMuPDF + ReportLab |
| 13 | Highlight/Underline/Strikeout | PyMuPDF |
| 14 | Freehand draw | PyMuPDF |
| 15 | Sticky notes | PyMuPDF |
| 16 | Stamp/Signature | PyMuPDF |
| 17 | Encrypt/Decrypt | pikepdf |
| 18 | Password protect | pikepdf |
| 19 | Extract text | PyMuPDF + Tesseract |
| 20 | Extract images | PyMuPDF |
| 21 | OCR (scan → text) | Tesseract + OpenCV |
| 22 | Compress PDF | PyMuPDF |
| 23 | Header/Footer/Page numbers | PyMuPDF + ReportLab |

---

## Verification Plan

### Automated Tests
1. Chạy `setup.bat` để xác nhận cài đặt thành công
2. Chạy `run.bat` để khởi động ứng dụng
3. Test mở file `BILL-HKA-T062026.pdf`
4. Test tính năng chia trang với file mẫu
5. Test OCR nhận dạng text trong file mẫu

### Manual Verification
1. Kiểm tra giao diện GUI hiển thị đúng
2. Test từng tính năng một với file PDF mẫu
3. Kiểm tra file output được lưu đúng vào `output/`
