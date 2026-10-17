# 🎬 DubiSub

**Dịch câu chuyện. Dựng từng khung hình.**

Studio dịch video/phụ đề đa ngôn ngữ, thuyết minh AI và biên tập video. Đích mặc định là tiếng Việt; hỗ trợ các đích khác theo khả năng thực tế của provider.

[![Sao GitHub](https://img.shields.io/github/stars/ericismee/dubisub?style=for-the-badge&logo=github)](https://github.com/ericismee/dubisub/stargazers)
[![Fork GitHub](https://img.shields.io/github/forks/ericismee/dubisub?style=for-the-badge&logo=github)](https://github.com/ericismee/dubisub/forks)

> Đang ở giai đoạn đặc tả. Chưa có ứng dụng, installer hoặc bản demo hoạt động. Badge lấy số liệu thật khi repo được xuất bản.

## ✨ Mục tiêu

- 📥 Nhập video/sub từ file hoặc link được hỗ trợ; chọn chất lượng và track.
- 🌍 ASR, dịch nhiều ngôn ngữ, glossary, sửa phụ đề song song và xuất ngay SRT/VTT/ASS.
- 🎙️ Chọn giọng đúng ngôn ngữ, nam/nữ, nghe mẫu sẵn; VieNeu ưu tiên cho tiếng Việt.
- ✂️ Timeline nhiều track, cắt/ghép, chữ, overlay, âm thanh, hiệu ứng, undo/redo và autosave.
- 🎬 Chọn review tóm tắt hoặc dịch/thuyết minh/lồng tiếng toàn bộ.
- 📤 Xuất video, phụ đề hoặc audio; hủy/thử lại/phục hồi công việc dài.

Các tính năng trên là kế hoạch phát triển; xem [trạng thái thực tế](docs/STATUS.md) và [roadmap đầy đủ](README.md#-roadmap).

## 🚀 Bắt đầu phát triển

Đọc [quy tắc](AGENTS.md), [đặc tả](PROJECT_BRIEF.vi.md), [kiểm tra setup](docs/SETUP_AUDIT.md), rồi dùng [prompt chat mới](NEW_CHAT_PROMPT.md). Hiện chưa có lệnh chạy ứng dụng.

Dự án lưu dữ liệu cục bộ; nếu chọn AI từ xa, nội dung cần xử lý được gửi tới provider đã chọn. Mã nguồn, tài liệu và tài sản SVG nguyên gốc của DubiSub dùng [giấy phép MIT](LICENSE), bản quyền © 2026 ericismee. Thành phần bên thứ ba giữ giấy phép riêng. [English README](README.md).
