# PDF Editor Pro

Một ứng dụng chỉnh sửa PDF ngoại tuyến (Offline) mạnh mẽ và bảo mật với nhiều tính năng nâng cao, được xây dựng bằng Python và Tkinter.

## 🌟 Tính năng chính

- **📄 Quản lý Trang (Page Management):**
  - Xem trước PDF với giao diện trực quan và tính năng quản lý bộ nhớ đệm tự động thích ứng với RAM máy tính.
  - Hỗ trợ cuộn liền mạch (Continuous Scrolling) để đọc tài liệu dễ dàng và Chế độ trang đơn (Single View) cho các thao tác chính xác.
  - Chọn trang linh hoạt (Tất cả, Chẵn/Lẻ, hoặc chọn từng tab) ở cột Thu nhỏ (Thumbnails) bên trái.
  - Thêm, Xóa, Xoay trang, Chèn trang trống và Trích xuất trang (Extract).

- **✂️ Tách, Cắt & Gộp Thông minh (Smart Split & Merge):**
  - **Merge:** Gộp nhiều tệp PDF lại với nhau nhanh chóng.
  - **Split by Pages:** Tách tệp PDF theo dải trang (ví dụ `1-3, 4-6`).
  - **Split every N pages:** Tách đều PDF cứ mỗi N trang thành 1 file.
  - **Split by Y Coordinate:** Tách ngang trang giấy tại một tọa độ Y cụ thể (Click Split).
  - **OCR Smart Split:** Tự động quét nhận dạng chữ (OCR) và tách trang hoặc cắt vùng giữa 2 đoạn văn bản (Smart Crop Between Texts). Lý tưởng để xử lý hóa đơn điện nước liên tục.
  - **Multi Crop:** Cắt nhiều vùng hiển thị linh hoạt trên trang bằng cách nhấp chuột trên màn hình.

- **🔍 Nhận dạng Ký tự Quang học (OCR):**
  - Tích hợp Tesseract OCR.
  - Quét và bóc tách chữ từ những file PDF dạng ảnh hoặc scan (Hỗ trợ tiếng Việt và tiếng Anh).

- **📝 Đóng Dấu & Ghi chú (Watermark & Annotate):**
  - Thêm Watermark bằng chữ hoặc chèn Logo vào vị trí tùy chọn.
  - Đánh số trang tự động.
  - Hỗ trợ tìm kiếm văn bản và Highlight.

- **🔒 Bảo mật & Tối ưu hóa (Security & Compress):**
  - Đặt mật khẩu mã hóa (Encrypt) hoặc gỡ bỏ mật khẩu (Decrypt).
  - Nén file PDF để giảm dung lượng (Compress).

---

## 🚀 Hướng dẫn Sử dụng Siêu Chi tiết

### 1. Cài đặt và Khởi động lần đầu
- Để phần mềm hoạt động Offline 100%, hãy chạy file `setup.bat` trước. File này sẽ tự động thiết lập môi trường, phát hiện thư viện Tesseract (OCR) sẵn có trên máy hoặc tự tải về bản nội bộ, đồng thời tải bộ ngôn ngữ Tiếng Việt và thư viện Poppler.
- Chạy file `run.bat` để mở ứng dụng. Máy tính sẽ tự động nhận diện dung lượng RAM để cấp phát bộ nhớ đệm giúp thao tác cuộn cực kỳ mượt mà.

### 2. Các Thao tác Cơ bản
- **Mở file:** Nhấn nút `Mở PDF` (Ctrl+O) hoặc kéo thả trực tiếp một file PDF vào màn hình chính. Ứng dụng luôn mở ở **Chế độ xem (Chỉ đọc)** để tránh rủi ro thay đổi nhầm.
- **Cuộn trang:** 
  - 📜 **Cuộn liên tục (Continuous):** Hiển thị các trang nối tiếp nhau, dễ dàng đọc toàn bộ tài liệu bằng con lăn chuột.
  - 📄 **Trang đơn (Single Page):** Chỉ hiển thị 1 trang để chỉnh sửa hoặc cắt tọa độ chính xác.
- **Phóng to/Thu nhỏ:** Sử dụng các nút kính lúp `+` / `-`.
- **Lưu file:** Nhấn `Lưu` (Ctrl+S) để ghi đè, hoặc `Lưu thành` để tạo bản sao. Các file lưu tự động mặc định nằm trong thư mục **Tài liệu (Documents)** của bạn trên Windows.

### 3. Quản lý Trang (Xóa, Xoay, Trích xuất, Chèn trang)
- Ở cột Thu nhỏ (Thumbnails) bên trái, đánh dấu tick vào các trang bạn muốn thao tác (Dùng nút Chọn "Tất cả", "Chẵn", "Lẻ").
- Click chuột phải hoặc dùng menu `Chỉnh sửa`:
  - **Xoay trang:** Xoay 90°, 180°, 270°.
  - **Xóa trang:** Bỏ đi các trang thừa hoặc bị lỗi.
  - **Trích xuất (Extract):** Tách riêng các trang đã chọn thành 1 file PDF mới.
  - **Chèn trang trống:** Chèn 1 trang trắng vào vị trí trước hoặc sau trang đang xem. Trang trắng sẽ có kích thước khớp 100% với trang hiện tại.
- *Lưu ý:* Các thao tác này được lưu tạm trên RAM. Bạn phải `Lưu file` để áp dụng vào ổ cứng.

### 4. Công cụ Tách & Cắt PDF (Split & Crop)
- **Tách theo khoảng cách (Auto-Split):** Tự động tìm dải trắng nằm ngang giữa các đoạn văn để chia nhỏ file mà không làm đứt chữ.
- **Tách theo Tọa độ Y (Click Split):** Màn hình hiển thị con trỏ ngang, click vào đâu hệ thống sẽ cắt dọc file tại đó. Rất hợp cắt lề dưới hóa đơn/vé.
- **Tách bằng Nhận dạng chữ (OCR Smart Split):** Ứng dụng tự động đọc chữ (kể cả ảnh scan) và chia trang mỗi khi gặp "Từ khóa bắt đầu" bạn chỉ định (VD: "Chương mới").
- **Cắt giữa 2 đoạn văn (OCR Crop):** Nhập "Từ khóa bắt đầu" và "Kết thúc", AI sẽ tìm và chỉ cắt lấy khúc giữa hai chữ đó.

### 5. Thêm Nội dung & Nhận dạng chữ (OCR)
- **Thêm Chữ / Ảnh:** Menu `Công cụ`. Cho phép chèn thêm nội dung bằng tọa độ (X, Y) chính xác.
- **Nhận dạng chữ (OCR):** Nếu file PDF là ảnh chụp, dùng OCR để quét lại. Nó sẽ tạo ra 1 file mới có lớp text chìm, giúp bạn có thể bôi đen, copy và tìm kiếm chữ cái như file Word.
- **Tăng tốc OCR bằng GPU:** OCR mặc định chạy trên CPU. Nếu máy có card màn hình NVIDIA, hãy vào `Trợ giúp -> OCR Info & GPU` để xem cách cài thêm EasyOCR giúp tăng tốc 10x.
- **Đánh số trang:** Tự động chèn số (VD: Trang 1/10) vào góc dưới.

### 6. Xử lý Hàng loạt (Batch Operations)
Menu `Hàng loạt` cung cấp sức mạnh để xử lý hàng chục, hàng trăm trang cùng một lúc. Bạn có thể nhập dải trang mong muốn (VD: `1-5, 8, 11-15`) để:
- **Xoay / Xóa / Trích xuất hàng loạt:** Quản lý hàng loạt trang trong chớp mắt.
- **Xuất ảnh hàng loạt:** Chuyển đổi một dải trang cụ thể thành file hình ảnh (PNG/JPG).
- **Tách hàng loạt theo tỷ lệ %:** Cắt đôi hoặc cắt theo tỷ lệ % cụ thể trên nhiều trang cùng lúc. Rất hữu ích khi cần chia đôi tài liệu A3 thành A4 đồng loạt.
- **OCR Tách hàng loạt & Cắt đoạn chữ:** Chạy công cụ tách thông minh (dựa trên chữ viết) xuyên suốt nhiều trang đã định sẵn.

### 7. Bảo mật và Tối ưu (Security)
- **Mã hóa (Encrypt):** Đặt mật khẩu AES-256 bảo vệ tuyệt đối.
- **Gỡ mật khẩu (Decrypt):** Mở khóa PDF.
- **Nén (Compress):** Giảm dung lượng file scan lớn để gửi mail.
- **Giải quyết lỗi:** Nếu có lỗi thư viện, hãy đóng app và chạy lại `setup.bat`.

---

## 📜 Điều khoản Sử dụng (Terms and License)

**BẢN QUYỀN VÀ GIẤY PHÉP SỬ DỤNG:**

- **Miễn phí sử dụng:** Ứng dụng này được cung cấp hoàn toàn miễn phí (Free to Use) cho các mục đích cá nhân và thương mại của người sử dụng.
- **Quyền chỉnh sửa:** Bạn có toàn quyền sao chép, chỉnh sửa (Modify) mã nguồn ứng dụng để phục vụ cho các tính năng và luồng công việc nội bộ của riêng bạn.
- **⛔ NGHIÊM CẤM PHÂN PHỐI (NOT FOR DISTRIBUTION):** Mặc dù bạn được phép sử dụng và chỉnh sửa, nhưng **bạn KHÔNG được phép phân phối (Distribute), chia sẻ lại, hoặc thương mại hóa (bán, cho thuê)** mã nguồn gốc hay bất kỳ phiên bản nào đã qua chỉnh sửa từ phần mềm này dưới mọi hình thức.

---
*Cảm ơn bạn đã tin dùng PDF Editor Pro. Mọi dữ liệu của bạn đều được bảo mật tuyệt đối 100% OFFLINE!*
