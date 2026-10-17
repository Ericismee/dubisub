# 🎬 DubiSub

**Dịch câu chuyện. Dựng từng khung hình.**

Studio dịch video/phụ đề đa ngôn ngữ, thuyết minh AI và biên tập video. Đích mặc định là tiếng Việt; hỗ trợ các đích khác theo khả năng thực tế của provider.

[![Sao GitHub](https://img.shields.io/github/stars/ericismee/dubisub?style=for-the-badge&logo=github)](https://github.com/ericismee/dubisub/stargazers)
[![Fork GitHub](https://img.shields.io/github/forks/ericismee/dubisub?style=for-the-badge&logo=github)](https://github.com/ericismee/dubisub/forks)

> M1 đã có ứng dụng cục bộ và luồng kiểm thử thật: tạo/mở dự án, nhập/probe video, sửa/tự lưu phụ đề và xuất SRT/VTT. Chưa có ASR, dịch AI, giọng đọc, dựng review hoặc installer.

## ✨ Mục tiêu

- 📥 Nhập video/sub từ file hoặc link được hỗ trợ; chọn chất lượng và track.
- 🌍 ASR, dịch nhiều ngôn ngữ, glossary, sửa phụ đề song song và xuất ngay SRT/VTT/ASS.
- 🎙️ Chọn giọng đúng ngôn ngữ, nam/nữ, nghe mẫu sẵn; VieNeu ưu tiên cho tiếng Việt.
- ✂️ Timeline nhiều track, cắt/ghép, chữ, overlay, âm thanh, hiệu ứng, undo/redo và autosave.
- 🎬 Chọn review tóm tắt hoặc dịch/thuyết minh/lồng tiếng toàn bộ.
- 📤 Xuất video, phụ đề hoặc audio; hủy/thử lại/phục hồi công việc dài.

Các tính năng trên là kế hoạch phát triển; xem [trạng thái thực tế](docs/STATUS.md) và [roadmap đầy đủ](README.md#-roadmap).

## 🚀 Bắt đầu phát triển

Yêu cầu: Windows, uv, Node/npm, FFmpeg và FFprobe trong PATH. Chạy:

```powershell
cd D:/WorkSpace/dubisub
uv sync --locked
npm ci --prefix frontend
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

Mở **http://127.0.0.1:3600**; API ở `127.0.0.1:6060`. Giữ terminal mở; Ctrl+C để dừng, hoặc chạy `powershell -ExecutionPolicy Bypass -File scripts/stop.ps1` ở terminal khác. Script từ chối cổng đã có dịch vụ, không tắt tiến trình khác.

Tạo dự án → nhập video và SRT/VTT/ASS → sửa chữ/thời gian → đợi “Đã tự lưu” → mở lại từ thư viện → xuất SRT/VTT. Bấm số câu để seek video; track chữ trong video được worker trích xuất. MP4 H.264 đã kiểm tra trên Edge; định dạng khác tùy codec trình duyệt. ASS chuyển thành chữ thuần, không giữ hiệu ứng.

Tạo mẫu tự sinh: `.venv/Scripts/python scripts/make_sample.py` (ở `data/samples`). Kiểm thử: `.venv/Scripts/python -m pytest -q`, `npm --prefix frontend run build`, `.venv/Scripts/python scripts/check_e2e.py` và `npm audit --prefix frontend`.

`.env.example` liệt kê biến môi trường; chưa tự nạp file `.env`. M1 không cần key. Cấu hình AI chỉ lưu endpoint/model/tên biến khóa và luôn báo chưa xác minh. Xem [trạng thái](docs/STATUS.md), [setup](docs/SETUP_AUDIT.md) và [đặc tả](PROJECT_BRIEF.vi.md).

Dự án lưu dữ liệu cục bộ; nếu chọn AI từ xa, nội dung cần xử lý được gửi tới provider đã chọn. Mã nguồn, tài liệu và tài sản SVG nguyên gốc của DubiSub dùng [giấy phép MIT](LICENSE), bản quyền © 2026 ericismee. Thành phần bên thứ ba giữ giấy phép riêng. [English README](README.md).
