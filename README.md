# PDF Editor Pro

Một ứng dụng chỉnh sửa PDF ngoại tuyến (Offline) mạnh mẽ và bảo mật với nhiều tính năng nâng cao, được xây dựng bằng Python và Tkinter.

## 🌟 Tính năng chính

- **📄 Quản lý Trang (Page Management):**
  - Xem trước PDF với giao diện trực quan và tính năng quản lý bộ nhớ thông minh (Lazy Rendering).
  - Chọn nhiều tab và thanh thu nhỏ bên trái (Thumbnails).
  - Thêm, Xóa, Xoay trang và Trích xuất trang (Extract) tùy chọn.
  - Hỗ trợ cuộn liền mạch (Continuous Scrolling) để đọc tài liệu dễ dàng, cũng như Chế độ trang đơn (Single View) để chỉnh sửa.

- **✂️ Tách & Gộp (Split & Merge):**
  - **Merge:** Gộp nhiều tệp PDF lại với nhau.
  - **Split (Tách):** Tách một tệp PDF lớn thành nhiều tệp PDF nhỏ (ví dụ tách theo dải trang `1-3, 4-6`).
  - **Click Split:** Tách một trang giấy ra làm 2 nửa theo chiều dọc bằng cách nhấp chuột trên màn hình.
  - **Multi Crop:** Tính năng ưu việt cho phép bạn cắt nhiều vùng hiển thị linh hoạt trên trang (chọn cặp tọa độ Y để cắt). Lý tưởng cho việc cắt hóa đơn điện nước liên tục. Tất cả đều xử lý trực tiếp trên RAM, không sinh ra file tạm làm nghẽn máy.

- **🔍 Nhận dạng Ký tự Quang học (OCR):**
  - Tích hợp Tesseract OCR.
  - Đọc và bóc tách chữ từ những file PDF dạng ảnh hoặc scan.

- **📝 Đóng Dấu & Ghi chú (Watermark & Annotate):**
  - Thêm Watermark bằng chữ hoặc chèn file ảnh (Logo) vào vị trí tùy chọn.
  - Thêm Text tùy chỉnh vào giữa trang tài liệu.
  - Hỗ trợ tìm kiếm chữ (Search Text) và highlight (làm nổi bật).

- **🔒 Bảo mật (Security):**
  - **Encrypt:** Đặt mật khẩu mã hóa cho file PDF của bạn.
  - **Decrypt:** Gỡ bỏ mật khẩu bảo vệ đối với những file PDF mà bạn biết mật khẩu.
  - **Compress:** Nén file PDF để giảm dung lượng.

## 🚀 Hướng dẫn Sử dụng (Quick Start)

### Cài đặt
1. Chạy file `./build.bat` hoặc cài đặt các thư viện cần thiết thông qua file `requirements.txt`.
2. Đảm bảo đã cài đặt [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) và [Poppler](https://poppler.freedesktop.org/) để tận dụng tối đa chức năng (ứng dụng đã tích hợp sẵn thư mục tools kèm theo).

### Cách sử dụng các chức năng thường dùng
1. **Mở file:** Bấm nút `Open` hoặc kéo thả trực tiếp (Drag & Drop) một file PDF vào màn hình chính. Ứng dụng sẽ tự động vào Chế độ cuộn liên tục (Continuous View) để bạn xem toàn bộ.
2. **Cắt nhiều điểm (Multi Crop):**
   - Chuyển sang thẻ tính năng trên thanh công cụ, nhấn **Multi Crop**. Ứng dụng sẽ tự động đưa bạn về lại màn hình trang đơn (Single View) để tọa độ chính xác nhất.
   - Nhấp đúp chuột trên màn hình (Click 1 tạo vạch trên, Click 2 tạo vạch dưới) để xác định khung cần giữ lại.
   - Khi hoàn thành, chọn vùng các trang cần áp dụng phía bên trái, rồi nhấn nút **✅ Apply Crop** màu tím ở thanh trạng thái (dưới cùng bên phải).
   - Chọn nơi lưu file PDF sau khi đã cắt xong.
3. **Chuyển đổi kiểu nhìn:**
   - Trên thanh công cụ trên cùng, nhấn vào nút có hình tờ giấy (`📜 Continuous` hoặc `📄 Single View`) để thay đổi cách hiển thị file theo dạng đọc dọc liên tục hay xem kỹ từng trang.

## 📜 Điều khoản Sử dụng (Terms and License)

**BẢN QUYỀN VÀ GIẤY PHÉP SỬ DỤNG:**

- **Miễn phí sử dụng:** Ứng dụng này được cung cấp hoàn toàn miễn phí (Free to Use) cho các mục đích cá nhân và thương mại của người sử dụng.
- **Quyền chỉnh sửa:** Bạn có toàn quyền sao chép, chỉnh sửa (Modify) mã nguồn ứng dụng để phục vụ cho các tính năng và luồng công việc nội bộ của riêng bạn.
- **⛔ NGHIÊM CẤM PHÂN PHỐI (NOT FOR DISTRIBUTION):** Mặc dù bạn được phép sử dụng và chỉnh sửa, nhưng **bạn KHÔNG được phép phân phối (Distribute), chia sẻ lại, hoặc thương mại hóa (bán, cho thuê)** mã nguồn gốc hay bất kỳ phiên bản nào đã qua chỉnh sửa từ phần mềm này dưới mọi hình thức (kể cả việc upload công khai trên các diễn đàn, các kho lưu trữ mở không thuộc quyền quản lý của tác giả, hoặc bán lại như một sản phẩm phần mềm độc lập).

---
*Cảm ơn bạn đã tin dùng PDF Editor Pro. Chúc bạn có những trải nghiệm làm việc hiệu quả và tối ưu hóa thời gian tốt nhất!*
