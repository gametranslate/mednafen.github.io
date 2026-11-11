# Mednafen Play 0.2.3 — Hướng dẫn sử dụng

Giao diện thư viện của GameTranslate, chạy Mednafen 1.32.1 ngay trong khung chính. Mặc định tiếng Anh; bộ chọn trên thanh đầu hỗ trợ Đức, Việt, Pháp, Tây Ban Nha, Ý, Hàn, Trung phồn thể/giản thể và Nhật. Nút mặt trăng/mặt trời chuyển sáng/tối ngay, kể cả khi đang chơi.

## Bắt đầu

1. Chạy bộ cài Windows x64, hoặc giải nén toàn bộ bản ZIP rồi mở mednafen-play.exe. Giữ nguyên thư mục resources bên cạnh chương trình.
2. Chọn **Thêm game → Chọn tệp game** hoặc **Quét thư mục**.
3. Với đĩa CD, chọn CUE/CCD hoặc M3U cho game nhiều đĩa. Giữ các tệp BIN/IMG và các đĩa được tham chiếu cùng cấu trúc thư mục.
4. Chọn game, nhấn **Play now / Chơi ngay**. Game nằm trong vùng bên phải sidebar. Chọn **Fullscreen** hoặc **Alt + Enter** để chỉ hiện game. **Esc** trở về cửa sổ và menu/UI, game tiếp tục chạy. **Stop game** hoặc F12 kết thúc phiên chơi bình thường.
5. Có thể kéo **một ROM** vào cửa sổ để chơi ngay, kể cả vùng game đang chạy. Thả lại cùng game sẽ tiếp tục phiên hiện tại; thả game khác sẽ dừng phiên cũ rồi mở game mới. Cài đặt chưa lưu sẽ được hỏi trước.
6. Nút **X** tự dừng game rồi đóng ứng dụng. Không cần bấm Stop trước. Nếu game treo, ứng dụng chờ tối đa khoảng 4 giây trước khi kết thúc tiến trình; tiến trình chưa lưu có thể mất.
7. **Clear library / Xóa thư viện** yêu cầu xác nhận, dừng phiên đang chạy rồi xóa danh sách và cài đặt riêng. ROM, BIOS, bản lưu và cài đặt chung được giữ nguyên.
8. **Now playing** quay lại game sau khi xem Settings hoặc About. Đổi cài đặt giả lập cần dừng game rồi lưu; ngôn ngữ và sáng/tối thay đổi ngay.

Ứng dụng cần Windows x64 và Microsoft Edge WebView2 Runtime. Bộ cài hỗ trợ cài WebView2 khi còn thiếu; bản ZIP cần có WebView2 sẵn trên máy. Bản ZIP không cần cài đặt, nhưng vẫn lưu dữ liệu trong hồ sơ Windows, không lưu cạnh EXE.

## Cài đặt theo cách bạn chơi

**Áp dụng cho → Tất cả game** là cấu hình chung. Chọn tên game để tạo cấu hình riêng; những mục chưa đổi sẽ kế thừa cấu hình chung.

Mỗi mục phổ biến có giải thích bằng ngôn ngữ giao diện. **Chi tiết** hiển thị tên kỹ thuật, giá trị mặc định và giới hạn. Nút **↶** xóa giá trị tùy chỉnh. **Lưu cài đặt** áp dụng khi mở game lần tiếp theo; cần thoát game đang chạy trước khi lưu.

| Nhóm | Nội dung |
| --- | --- |
| Chung | Giao diện sáng/tối, chương trình Mednafen, nhập/xuất cấu hình |
| Hình ảnh | Toàn màn hình, VSync, tỷ lệ, bộ lọc và phóng hình theo hệ máy |
| Âm thanh | Âm lượng, tần số, driver, độ trễ và bộ đệm |
| Điều khiển | Bàn phím, hướng dẫn gán tay cầm, phím tắt |
| BIOS & firmware | Chọn tệp khởi động; kiểm tra tồn tại và mã BIOS được hỗ trợ |
| Lưu game | Tự lưu trạng thái, tua nhanh, tua lại và nén bản lưu |
| Thư mục | Vị trí BIOS, bản lưu, save state, ảnh chụp và các dữ liệu khác |
| Theo hệ máy | Vùng máy và các tùy chọn riêng |
| Chơi qua mạng | Máy chủ, cổng, tên người chơi và mã nhóm |
| Tất cả thiết lập | Toàn bộ 7.908 khóa của Mednafen 1.32.1, bao gồm ánh xạ nút |

Ô **Tìm cài đặt** tìm cả tên tiếng Việt và khóa như sound.volume. Các mô tả chuyên sâu chưa được dịch vẫn giữ tiếng Anh gốc.

## BIOS, tay cầm và lưu game

- **BIOS:** chọn tệp của bạn trong BIOS & firmware, rồi nhấn Kiểm tra BIOS. Chỉ cần BIOS của hệ máy/vùng bạn sử dụng. Đối chiếu SHA-256 có sẵn cho 3 BIOS PlayStation và 2 BIOS Saturn; các firmware khác được kiểm tra tồn tại.
- **Tay cầm:** cắm trước khi mở game; trong game nhấn **Alt + Shift + 1**, rồi làm theo hướng dẫn. Thoát game bình thường để lưu. Các ánh xạ thay đổi trong Mednafen được đọc lại vào giao diện. Gán trực tiếp trong GUI hiện hỗ trợ bàn phím.
- **Lưu nhanh:** mặc định F1 lưu, F2 tải, F3 chuyển ô tiếp theo, Shift + F3 về ô trước; 0–9 chọn trực tiếp ô. Bản lưu từ menu trong game/thẻ nhớ khác với save state. Nên tiếp tục dùng menu Save của game cho tiến trình lâu dài.
- **Nhiều đĩa:** dùng danh sách M3U. Mặc định F8 mở/đóng khay đĩa, F6 chọn đĩa. Có thể đổi phím trong Tất cả thiết lập.
- **Netplay:** lưu thông tin kết nối, mở game, nhấn T rồi nhập /server. Cần cùng bản game và phiên bản Mednafen tương thích.

## Dữ liệu và xử lý lỗi

**Cài đặt → Chung → Mở thư mục dữ liệu** mở vị trí chính xác trên máy. Mặc định là thư mục us.gametranslate.mednafen-play trong AppData/Roaming:

- library.json: thư viện, cấu hình chung, cấu hình riêng; library.json.bak: bản dự phòng lần lưu trước.
- mednafen/sav: bản lưu trong game; mednafen/mcs: save state; mednafen/firmware: BIOS.
- mednafen/play-profile.cfg: cấu hình phiên chơi do giao diện tạo.
- mednafen/mednafen.cfg: tệp nền được tạo lại từ cấu hình giao diện khi mở game. Muốn đưa cấu hình cũ vào ứng dụng, dùng **Nhập cấu hình** rồi **Lưu cài đặt**.

Đường dẫn tương đối của các thư mục Mednafen tính từ thư mục mednafen trong dữ liệu ứng dụng. Đổi vị trí không tự di chuyển các bản lưu cũ. Sao lưu toàn bộ thư mục dữ liệu và các thư mục lưu tùy chỉnh trước khi chuyển máy.

**Bỏ khỏi thư viện** không xóa ROM hoặc bản lưu. Với đĩa không tự nhận diện đúng, mở dấu **…** ở thẻ game và chọn hệ máy. Nếu game không mở, xem **Nhật ký** và kiểm tra đường dẫn, tệp đĩa, BIOS.

## Giới hạn và ghi công

Đã kiểm tra Namco Super Wars (WonderSwan) đến màn hình tiêu đề và đoạn mở đầu bằng cả OpenGL và phần mềm, trong môi trường chạy ngầm riêng. Esc giữ phiên chơi; chuyển Settings và quay lại game, dừng bình thường đều có kiểm tra. Chưa playtest toàn bộ game, tay cầm vật lý, Netplay, toàn bộ hệ máy hoặc nhiều màn hình/DPI. Bản dịch tự động có thể cần chỉnh câu; mô tả kỹ thuật chuyên sâu vẫn giữ tiếng Anh khi chưa dịch.

Các tùy chọn fullscreen gốc như độ phân giải, stretch và phím chuyển fullscreen do giao diện quản lý: game luôn vừa khung và giữ tỷ lệ; fullscreen dùng màn hình đang đặt ứng dụng. Những mục gốc này hiển thị lời giải thích thay cho điều khiển không có tác dụng. Cài đặt engine tùy chọn chỉ chấp nhận đúng bộ Mednafen/adapter đi kèm; xóa đường dẫn riêng để dùng lại mặc định.

About ghi công Mednafen developers/contributors, SDL (Sam Lantinga và cộng tác viên), Tauri, React và Lucide/Feather. GameTranslate chỉ bổ sung thư viện, UI Settings, ngôn ngữ và tích hợp cửa sổ. Nút Star mở GitHub gốc; ứng dụng không tự bấm star. Logo góc dưới bên trái mở https://gametranslate.us.

Không kèm ROM/BIOS. Mã nguồn Mednafen tương ứng, giấy phép và notices nằm trong resources; mã nguồn frontend/adapter có gói ZIP riêng. Bản Windows chưa ký số. Linux, macOS và Android chưa có bản chạy game; xem PORTS.md. Bộ cài đã được kiểm tra bằng cách giải nén ứng dụng, chưa chạy cài/gỡ trên máy Windows sạch.

## Nếu game không hiện hình

Bản 0.2.2 tách vùng vẽ giao diện khỏi khung game để tránh giao diện che hình dù vẫn có tiếng. Vùng này tự cập nhật khi đổi kích thước hoặc fullscreen, và khôi phục khi mở Settings, About, Log hoặc dừng game. Người dùng đã xác nhận bản 0.2.2 hết màn đen và chơi được ngày 11/11/2026.

Ứng dụng theo dõi khung hình đầu tiên và báo lỗi sau 15 giây nếu engine chưa xuất khung hình. Chỉ số này không bảo đảm hình đã hiện trên màn hình thực tế. Mở **Log** để xem chẩn đoán; có thể thử kết xuất **Software** trong Settings → Video. **Stop game** có ở cả vùng chơi lẫn thư viện để giải phóng phiên.

Khi đổi bản, tự đóng ứng dụng cũ rồi chạy bản mới; không mở hai bản cùng lúc vì chúng dùng chung thư mục dữ liệu. Không cần xóa thư viện hoặc bản lưu.

## Bàn phím trong bản 0.2.3

- Khi vùng game đang mở, Tab và các phím chơi game được gửi tới Mednafen; Tab không nhảy qua các nút giao diện. Giữ Tab để tua nhanh, thả ra để trở về tốc độ thường. Mở menu hoặc chuyển ứng dụng sẽ nhả các phím đang giữ.
- Mũi tên: di chuyển. Z/X, A/S: các nút hành động; Q/W: nút vai trên các tay cầm thông dụng. Enter: Start; Shift phải: Select. Xem ánh xạ đầy đủ cho từng hệ máy trong Settings → Controls. WonderSwan dùng mũi tên cho cụm X và WASD cho cụm Y. Mega Drive/Saturn dùng Z/X/C và A/S/D cho sáu nút.
- F1 lưu nhanh vào ô hiện tại; F2 tải ô hiện tại; F3 sang ô tiếp theo; Shift + F3 về ô trước. Chuyển ô không tự lưu hoặc tải. Các phím này chỉ áp dụng cho save state, không thay cách lưu trong menu của game.
- Esc thoát fullscreen; Esc khi đang ở chế độ cửa sổ đưa về thư viện nhưng giữ game chạy. Alt + Enter đổi fullscreen. Alt + F4 đóng ứng dụng và dừng game bình thường. Các menu Settings vẫn dùng Tab và nhập chữ như thường.
- Các phím gốc bị trùng đã chuyển: Ctrl + F1 mở trợ giúp Mednafen; Ctrl + F2 cấu hình phím lệnh; Ctrl + Shift + F2 thêm ánh xạ; Ctrl + F3 phát hiện nút trục; Ctrl + Shift + F3 nhận lại tay cầm. F12 vẫn là phím dừng game của Mednafen.
- Cấu hình phím đã tùy chỉnh được giữ. Để thay bằng bộ mới, chọn hệ máy trong Settings → Controls → Use recommended keys, dừng game nếu đang chạy rồi Save settings.

Ô System trong Video/Controls/System chọn nhóm cài đặt của hệ máy cần xem, không đổi hệ máy của game đang chạy. Lựa chọn hệ máy và trang cài đặt được nhớ tự động trên máy này, không cần Save. Khi chỉnh một tùy chọn thật (ví dụ bộ lọc hoặc scanlines), nút Save hoạt động sau khi dừng game.
