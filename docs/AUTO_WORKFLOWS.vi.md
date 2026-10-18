# DubiSub Auto — hướng dẫn và giới hạn

Mở ứng dụng bằng `powershell -ExecutionPolicy Bypass -File scripts/start.ps1`, sau đó vào http://127.0.0.1:3600. Launcher chỉ dùng cổng 3600/6060 nếu đang trống. Dừng bằng `scripts/stop.ps1` khi không có tác vụ cần giữ chạy.

## Cấu hình theo vai trò

- **ASR**: endpoint tương thích OpenAI `/audio/transcriptions`, model nhận dạng trả `segments` với thời gian thật. Chưa có ASR local/model được cài sẵn bởi mốc này. Có phụ đề thì không cần ASR. Nếu chọn `nomic-embed-text`, ứng dụng chặn vì đây là embedding, không nhận dạng lời nói.
- **LLM**: Ollama native hoặc OpenAI-compatible. Nhập endpoint/model, chọn không xác thực hoặc tên biến `DUBISUB_*` chứa Bearer key. Không nhập giá trị key vào giao diện.
- **Vision**: cấu hình riêng, có thể sao chép cấu hình LLM rồi kiểm tra khả năng ảnh. Không tự gửi video vào chat text. Hiện chỉ hỗ trợ frame JPEG; chưa có video-native.
- **TTS**: VieNeu local mặc định `http://127.0.0.1:8001/v1`, model `vieneu-v3-turbo`. Xem [giọng mẫu](VOICE_CLONING.vi.md).

“Kiểm tra kết nối & model” chỉ đọc danh sách model. “Kiểm tra text/image” chạy inference tổng hợp trong worker sau khi bạn xác nhận. Kết quả không chứng minh chất lượng AI; probe ảnh có thể thất bại nếu model đọc sai màu. Đổi endpoint/model/protocol/key-variable làm thay đổi chữ ký capability. Không tự tải model hoặc chuyển provider khi lỗi.

Tại môi trường đã kiểm tra ngày 18/10/2026: Ollama công bố `qwen2.5:7b`, `llava:latest`, `nomic-embed-text:latest`. Qwen đã dịch thật; LLaVA nhận ảnh RGB và phân tích frame thật, nhưng có lần sai phép thử màu ngẫu nhiên. `nomic-embed-text` không được chọn làm model dịch/vision. Cấu hình LLM trỏ nhầm VieNeu đã được thay bằng Qwen local, giữ bản cấu hình cũ trong `data/providers-before-auto-*.json` bị Git bỏ qua. Các vai trò khác được giữ nguyên; Vision LLaVA chỉ được thêm khi chưa có cấu hình.

## Chạy Auto

1. Nhập file hoặc dùng công cụ link để phân tích/chọn/tải nguồn vào kho. Mở dự án rồi bấm **Auto**.
2. Chọn media và track lời thoại. Ưu tiên track được chọn → track có sẵn → ASR khi thiếu. Chọn chạy lại ASR nếu muốn đối chiếu, giữ track cũ. Nếu có nhiều track, chọn rõ nguồn. Caption AI/review không được nhận làm lời thoại thật.
3. Chọn Dịch phụ đề, Tóm tắt, Kịch bản review hoặc Mô tả AI; ngôn ngữ BCP 47 mặc định `vi`. Chọn phong cách, spoiler và thời lượng lời dẫn mục tiêu. Không rút gọn bản dịch trừ khi bật rõ ràng.
4. Xem pipeline, provider/model/endpoint và loại dữ liệu sẽ truyền; xác nhận trước khi chạy. Không có ước tính chi phí nếu chưa có bảng giá/token đáng tin.
5. Dịch có thể dừng ở bản nháp hoặc tự xuất SRT/VTT/ASS. Phân tích/kịch bản luôn dừng ở bản nháp cần duyệt. Worker tiếp tục khi đóng tab; có hủy/thử lại và checkpoint. Hết 3 lần thử cần sửa cấu hình hoặc tạo lượt mới. Tối đa một pipeline đang chạy mỗi dự án, 20 toàn hệ thống; lịch sử hiển thị 100 lượt gần nhất.

Track nguồn và mỗi bản dịch riêng biệt, giữ ID/thời gian. Thay đổi nguồn dừng pipeline và làm mất hiệu lực kết quả liên quan. ASR dùng chunk 600 giây, bước 590 giây; chống trùng câu trùng nội dung/thời gian giữa các chunk. Giữ bản ASR nguyên gốc trong `raw_cues`, có tải JSON; confidence không chắc/ranh giới chunk được đánh dấu để nghe lại. Chưa có hiệu đính LLM riêng, diarization hoặc word alignment.

## Phân tích, giọng và review

**Phân tích cảnh & kịch bản** hiển thị phạm vi transcript-only hoặc transcript + frame lấy mẫu, ID bằng chứng và mốc nguồn. Bấm mốc để seek nguồn. Có sửa/duyệt nội dung, xuất Markdown/JSON. Alias bằng chứng ngắn trong request được validate rồi ánh xạ về ID thật; model viện dẫn ID lạ sẽ thất bại, không được tự sửa thành bằng chứng giả.

Vision lấy tối đa 16 frame, theo khoảng thời gian, tối đa 4 ảnh/request, 640px/256KiB mỗi ảnh. Không xem liên tục, không nghe audio, không OCR, không suy ra chuyển động giữa frame. Phân tích transcript chia nhóm tối đa 40 bằng chứng/24.000 ký tự, tối đa 100 nhóm. Hiện chưa có tóm tắt phân cấp toàn video hoặc chọn cảnh tự động.

Sau khi duyệt kịch bản, mở **Giọng đọc → Đọc kịch bản / dựng video review**. Chọn preset hoặc hồ sơ giọng mẫu, kiểm tra VieNeu, xác nhận dữ liệu TTS sẽ nhận, chọn kịch bản đã duyệt rồi tạo lời dẫn. Mỗi đoạn tối đa 300 ký tự; sửa/tách đoạn dài trước khi tạo. Cache theo văn bản/giọng/model; sửa một đoạn và chạy lại sẽ dùng lại cache của đoạn không đổi.

Timeline lời dẫn được tạo từ thời lượng WAV đo thật, lượng tử hóa điểm bắt đầu đoạn theo 25fps; giữ mốc nguồn riêng. Track `review` chỉ xuất hiện sau khi có audio, không chia đều thời gian giả. Chọn track này để preview audio/video review và timeline mới. Bấm bằng chứng trong phân tích sẽ trở về preview nguồn.

MP4 review baseline: 640×360/25fps, cảnh từ bằng chứng đầu tiên của mỗi đoạn, giữ hình cuối nếu cảnh ngắn hơn lời dẫn; audio gốc được thay thế. Không cắt mất lời. Có WAV, MP4 và track phụ đề review SRT/VTT/ASS riêng; MP4 review hiện chưa burn-in phụ đề. Không gắn phụ đề review vào renderer timeline nguồn. Chưa có giao diện đổi/sắp xếp cảnh review, multitrack hoặc trộn/duck nhạc nền.

## Kiểm chứng

```powershell
uv run pytest -q
npm run build --prefix frontend
# Cần 3600/6060 trống; dùng dữ liệu fixture cô lập:
uv run python scripts/check_e2e.py
# Inference thật, chỉ gửi transcript/frame tổng hợp được phép sử dụng:
uv run python scripts/check_ai_live.py --llm-model qwen2.5:7b --vision-model llava:latest
```

Pytest/Playwright fixture chứng minh giao thức, timing và vòng đời job, không chứng minh chất lượng AI. Smoke thật đã kiểm chứng Qwen dịch → SRT/VTT/ASS, LLaVA + Qwen frame/transcript → tóm tắt có timecode, và VieNeu → WAV/MP4 review (hai đoạn 5280ms/3280ms). Output kiểm tra nằm trong `test-results/` bị Git bỏ qua. Chưa kiểm chứng ASR thật, chất lượng người nói thật hoặc phim dài.

Tiếp theo: ASR local/provider thật; hiệu đính riêng; tóm tắt phân cấp; chọn/sửa cảnh review; pipeline một lần chạy đến video theo preset đã xác nhận; video-native; kiểm thử mất mạng/rate-limit/restart/disk exhaustion chuyên sâu. Không coi baseline này là hoàn tất toàn bộ đặc tả.

Giao thức ảnh Ollama được đối chiếu với [tài liệu Vision chính thức](https://docs.ollama.com/capabilities/vision) và [API model details](https://github.com/ollama/ollama/blob/main/docs/api.md).
