# Bắt đầu triển khai DubiSub

Bạn là kỹ sư phụ trách xây DubiSub — studio dịch video/phụ đề đa ngôn ngữ và biên tập video chạy cục bộ trên Windows. Làm việc tại `D:/WorkSpace/dubisub`; tên repo dự kiến `ericismee/dubisub`. Giữ nguyên đường dẫn thư mục hiện tại.

## Đọc ngữ cảnh

Đọc `AGENTS.md`, `TASK_CONTEXT.md`, `docs/STATUS.md` và `docs/SETUP_AUDIT.md`. Đọc `PROJECT_BRIEF.vi.md` một lần để nắm sản phẩm; phần 12 ưu tiên khi các phần cũ khác nhau. Tra `SKILLS.md` để chọn skill phù hợp và chỉ đọc các reference cần cho công việc. Claude dùng `CLAUDE.md` làm entrypoint; không nạp lại những nội dung đã được import.

## Mục tiêu đã chốt

- Upload hoặc nhập link video/sub: kiểm tra metadata/track/chất lượng, tải có kiểm soát; hỗ trợ sub-only/audio-only và fallback ASR khi được cấu hình.
- Dịch từ nhiều ngôn ngữ sang tiếng Việt hoặc nhiều đích khác, glossary, editor gốc/dịch, timing, phiên bản; xuất SRT/VTT/ASS độc lập với render.
- Hai chế độ tùy chọn: review với lời bình/timeline mới; dịch/thuyết minh/lồng tiếng toàn bộ theo timeline gốc.
- VieNeu ưu tiên cho tiếng Việt; registry capability cho mọi provider/ngôn ngữ/giọng; lọc nam/nữ và mẫu nghe cache sẵn. Dùng mã BCP 47 thay vì nhãn ngôn ngữ khi gọi API.
- Trình dựng video: timeline đa track, trim/split/ripple, proxy/waveform, undo/redo/autosave; sau đó chữ/overlay/transition/keyframe/color/audio và export preset.
- Xây các mốc chạy thật trong đặc tả. CapCut là tham chiếu nhóm tính năng, không phải lời hứa ngang toàn bộ sản phẩm.

## Bắt đầu làm ngay

1. Kiểm tra lại môi trường và trạng thái file hiện tại; bảo toàn thay đổi có sẵn. Nêu kế hoạch ngắn, quyết định cần thiết và bắt đầu M1, không chỉ viết thêm tài liệu.
2. Stack đề xuất React/TypeScript/Vite, FastAPI async, SQLite migration, worker bền vững, FFmpeg/FFprobe. UI 3600/API 6060 phải kiểm tra xung đột. Pin dependencies và tạo cấu hình mẫu không chứa secret.
3. M1 phải có tạo/mở project, upload/probe video, nhập/sửa subtitle, lưu/mở lại và xuất subtitle thực; health/worker và lỗi dễ hiểu. Kiểm thử pytest với media fixture thật, frontend type/build và Playwright cho luồng chính.
4. Cập nhật `docs/STATUS.md` và `TASK_CONTEXT.md` bằng bằng chứng test, lệnh chạy, phần hoàn thành và bước kế tiếp. Tiếp tục các mốc khi điều kiện cho phép.

Tách biệt NotebookE; không lấy key hoặc chỉnh tiến trình dự án đó. Không tự đổi tên thư mục, publish repo, hoặc giả lập kết quả AI thành tính năng hoạt động. Chưa giả định provider/key/model có sẵn. Chỉ hỏi điều thực sự chặn triển khai, còn quyết định kỹ thuật thông thường tự giải quyết và ghi lại. Chỉ dùng brainstorming nếu còn yêu cầu mơ hồ; mục tiêu hiện tại là triển khai, không mở lại vòng thu thập ý tưởng.

README đã có nhận diện DubiSub và badge cho ericismee/dubisub. Giữ trạng thái chính xác, thay phần kế hoạch bằng hướng dẫn chạy khi đã kiểm chứng; giữ giấy phép MIT đã được chủ dự án chọn và kiểm tra license bên thứ ba trước khi xuất bản.
