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

## 🚀 Hướng dẫn Sử dụng Chi tiết

### 1. Cài đặt và Khởi động
- Đảm bảo máy tính đã cài đặt [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) và [Poppler](https://poppler.freedesktop.org/) (ứng dụng đã tích hợp sẵn trong thư mục `tools`).
- Chạy file `./run.bat` để mở ứng dụng. Máy tính sẽ tự động nhận diện dung lượng RAM trống để cấp phát bộ nhớ đệm giúp thao tác cuộn mượt mà nhất.

### 2. Các Thao tác Cơ bản
- **Mở file:** Nhấn nút `Mở PDF` (biểu tượng thư mục) hoặc kéo thả trực tiếp (Drag & Drop) một file PDF vào màn hình chính. Ứng dụng mặc định mở ở **Chế độ xem (Chỉ đọc)** để tránh sai sót.
- **Chế độ hiển thị:** 
  - 📜 **Cuộn liên tục:** Phù hợp để đọc nhanh toàn bộ tài liệu. (Hiển thị số thứ tự trang X/Y ở góc để dễ theo dõi).
  - 📄 **Trang đơn:** Chỉ hiển thị 1 trang, phù hợp để chỉnh sửa hoặc cắt tọa độ chính xác.
- **Phóng to/Thu nhỏ:** Sử dụng các nút kính lúp `+` / `-` hoặc nhập mức thu phóng mong muốn.

### 3. Quản lý Trang (Xóa, Xoay, Trích xuất, Chèn trang)
- **Chọn trang:** Ở cột Thu nhỏ (Thumbnails) bên trái, bạn có thể click vào các ô vuông để chọn trang cần thao tác. Có thể dùng nút "Tất cả", "Chẵn", "Lẻ" để chọn nhanh.
- **Thực hiện lệnh:** Sau khi chọn trang, nhấp chuột phải vào cột Thumbnail hoặc chọn từ menu `Chỉnh sửa` phía trên để:
  - **Xoay trang:** Xoay 90°, 180°, 270°.
  - **Xóa trang:** Xóa các trang bị lỗi.
  - **Trích xuất (Extract):** Lưu các trang đã chọn thành 1 file PDF mới.
  - **Chèn trang trống:** Chèn 1 trang trắng vào trước hoặc sau trang đang chọn (kích thước trang trắng sẽ tự động khớp với trang hiện tại).
- *Lưu ý:* Các thao tác như Xóa/Xoay/Chèn sẽ được lưu tạm trong RAM. Bạn cần vào `Tệp` -> `Lưu file` (hoặc Ctrl+S) để ghi đè thay đổi lên ổ cứng.

### 4. Tính năng Tách / Cắt Nâng cao (Split & Crop)
Ứng dụng cung cấp các công cụ cắt/tách mạnh mẽ trong menu `Công cụ (Tools)`:

- **Tách mỗi N trang:** Tự động chia nhỏ file PDF, cứ N trang sẽ tạo thành 1 file mới. Rất hữu ích khi xử lý lô tài liệu gom chung.
- **Tách theo dải trang:** Nhập dải trang mong muốn (VD: `1-5, 6-10`) để tách thành các file tương ứng.
- **Tách ngang theo Click chuột (Tọa độ Y):** 
  - Chọn tính năng này, màn hình sẽ hiển thị con trỏ chéo. Bạn click vào một điểm trên trang, hệ thống sẽ cắt đôi tờ giấy theo đường ngang tại điểm click đó.
- **Cắt giữa 2 đoạn văn bản (OCR Crop Between Texts):** 
  - Tính năng độc quyền cho hóa đơn: Nhập "Từ khóa bắt đầu" và "Từ khóa kết thúc".
  - Ứng dụng sẽ tự động dùng AI (OCR) đọc chữ trên từng trang, xác định chính xác vị trí của 2 từ khóa và cắt lấy phần nội dung nằm giữa chúng.
  - *Mẹo:* Trước khi chạy các công cụ Tách hàng loạt, ứng dụng sẽ tự động sao lưu các thay đổi chưa lưu (như xóa/xoay trang) vào file tạm để đảm bảo kết quả cắt ra trùng khớp 100% với những gì bạn thấy trên màn hình! Trước khi cắt, hệ thống luôn hiện hộp thoại hỏi bạn muốn lưu kết quả ở đâu.

### 5. Cắt nhiều vùng thủ công (Multi Crop)
- Mở menu `Công cụ` -> `Multi Crop`. Ứng dụng sẽ tự động đưa bạn về lại màn hình trang đơn (Single View).
- **Cách cắt:** Nhấp đúp chuột trên màn hình:
  - Lần Click 1: Tạo vạch ngang trên cùng.
  - Lần Click 2: Tạo vạch ngang dưới cùng để xác định vùng cần giữ lại.
- Sau khi đóng khung xong, chọn các trang cần áp dụng ở cột bên trái, rồi nhấn nút **✅ Apply Crop** màu tím ở góc dưới cùng bên phải.
- Mọi xử lý diễn ra trực tiếp trên RAM, không sinh file rác, tốc độ cực nhanh.

### 6. Bảo mật và Tiện ích khác
- **Đánh số trang:** Menu `Công cụ` -> `Đánh số trang`. Tự động chèn số trang vào góc dưới tài liệu.
- **Watermark:** Đóng dấu bản quyền bằng chữ hoặc hình ảnh.
- **Bảo mật:** Menu `Bảo mật (Security)` cho phép bạn Nén file (Compress) cho nhẹ đi, Đặt mật khẩu (Encrypt) hoặc Gỡ mật khẩu (Decrypt) hàng loạt.

---

## 📜 Điều khoản Sử dụng (Terms and License)

**BẢN QUYỀN VÀ GIẤY PHÉP SỬ DỤNG:**

- **Miễn phí sử dụng:** Ứng dụng này được cung cấp hoàn toàn miễn phí (Free to Use) cho các mục đích cá nhân và thương mại của người sử dụng.
- **Quyền chỉnh sửa:** Bạn có toàn quyền sao chép, chỉnh sửa (Modify) mã nguồn ứng dụng để phục vụ cho các tính năng và luồng công việc nội bộ của riêng bạn.
- **⛔ NGHIÊM CẤM PHÂN PHỐI (NOT FOR DISTRIBUTION):** Mặc dù bạn được phép sử dụng và chỉnh sửa, nhưng **bạn KHÔNG được phép phân phối (Distribute), chia sẻ lại, hoặc thương mại hóa (bán, cho thuê)** mã nguồn gốc hay bất kỳ phiên bản nào đã qua chỉnh sửa từ phần mềm này dưới mọi hình thức (kể cả việc upload công khai trên các diễn đàn, các kho lưu trữ mở không thuộc quyền quản lý của tác giả, hoặc bán lại như một sản phẩm phần mềm độc lập).

---
*Cảm ơn bạn đã tin dùng PDF Editor Pro. Chúc bạn có những trải nghiệm làm việc hiệu quả và tối ưu hóa thời gian tốt nhất!*
