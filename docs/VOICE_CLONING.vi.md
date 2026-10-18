# Giọng từ video và lời đọc VieNeu

Mở studio tại http://127.0.0.1:3600, chọn dự án và media đã probe, rồi công cụ **Giọng đọc**.

1. Bấm **Kiểm tra VieNeu & lấy giọng**. TTS mặc định là `http://127.0.0.1:8001/v1`, model `vieneu-v3-turbo`. Service phải chạy; DubiSub không tự tải model hoặc khởi động/chỉnh dịch vụ bên ngoài.
2. Mở **Lấy giọng mẫu từ media**, chọn 3–8 giây, nghe lại, sửa điểm cắt và đặt tên. Xác nhận quyền sử dụng và đoạn sạch, một người nói. FFmpeg cắt cục bộ, chuẩn hóa loudness, mono 48 kHz PCM16; nguồn không thay đổi. Mẫu im lặng bị từ chối. Chưa có phát hiện nhạc nền/nhiều người nói tự động.
3. Chọn **Giọng từ video của tôi** hoặc **Giọng có sẵn**. Hiện adapter cloning chỉ bật tiếng Việt đã kiểm tra. Kiểm tra provider hiển thị trước khi đánh dấu đồng ý truyền dữ liệu. Tạo mẫu nghe từ văn bản; nghe lại dùng cache.
4. Với track phụ đề: duyệt ASR/bản dịch trước; gán giọng cho các nhân vật rồi gán từng câu. Chạy đọc track hoặc tạo lại riêng câu. Nội dung có thể sửa tại đây hoặc editor chính và được autosave. Sau khi sửa bản dịch phải duyệt lại. Chạy lại toàn track để phối các câu mới với cache của các câu không thay đổi.
5. Kết quả ghi thời lượng thực, tràn và chồng tiếng. Audio đặt tại timestamp gốc, không tự ép tốc độ hoặc đổi giọng. Sửa text/timing nếu cần. WAV phối có giới hạn 2 giờ; các đoạn chồng sẽ cộng audio có clipping giới hạn. Xuất MP4 dùng video gốc, thay audio gốc bằng lời đọc; chưa ducking/giữ nhạc nền hoặc áp render-plan hiệu ứng vào MP4 lời đọc. Nếu audio dài hơn video, audio có thể tiếp tục sau hình cuối; hãy xử lý cảnh báo trước khi xuất chính thức.
6. Có thể tải WAV, MP4 và phụ đề SRT/VTT/ASS ở panel xuất phụ đề. Xóa hồ sơ sẽ xóa WAV mẫu, cache/bản đọc liên quan tại DubiSub và hủy các tác vụ dùng giọng đó. Không xóa nguồn video/audio.

## Provider, quyền và giới hạn

- ASR/Whisper lấy lời thoại và timecode; LLM/Ollama dịch; VieNeu chỉ TTS. Không đặt model VieNeu vào nhóm dịch hoặc ASR. Ollama local chưa có dịch vụ tại cổng11434 lúc kiểm tra; cần chọn provider/model LLM thực tế, không có fallback giả.
- Cloning kiểm tra model từ `/v1/models` và schema multipart `POST /v1/voices` từ OpenAPI. Không suy luận mọi endpoint OpenAI-compatible đều cloning được. Mỗi lần cần tạo audio clone chưa cache sẽ đăng ký lại từ mẫu bất biến, nên không mất khả năng dùng hồ sơ sau khi provider restart.
- Chỉ khi xác nhận mới gửi văn bản và WAV mẫu đến provider hiển thị. Toàn bộ video không gửi để cloning. API hiện tại của VieNeu lưu embedding trong RAM và **không có DELETE**. Embedding đã gửi chỉ mất khi chủ dịch vụ khởi động lại; DubiSub không tự thay đổi tiến trình đó. Không hứa xóa từ xa tức thời.
- Worker có progress/cancel/retry, cache theo dự án, nội dung, giọng/mẫu, provider/model và thiết lập; mỗi câu đã hoàn thành được checkpoint/index. Tác vụ thất bại không đổi giọng ngầm; retry dùng cache đã hoàn tất. Mỗi tác vụ tối đa300 câu, mỗi câu300 ký tự, timeline2giờ, thời gian3giờ. Câu dài cần tách/sửa trước.
- Độ giống, phát âm, cảm xúc phụ thuộc mẫu và model. Chưa đánh giá bằng giọng người thật hoặc benchmark nhiều người/ngôn ngữ; không có diarization tự động, tách nhạc, forced alignment theo từ hoặc time-stretch tự động.

## Bằng chứng

Kiểm tra VieNeu local thật với reference tổng hợp từ preset (không dùng giọng người dùng chưa xác nhận): sinh WAV, dựng video tạm, cắt5giây, đăng ký clone, đọc2câu, xuất WAV/MP4 và xóa dữ liệu cục bộ thành công. Thời lượng hai câu3280ms/1600ms, cảnh báo tràn1780ms/700ms và chồng tiếng đúng cửa sổ nguồn. Đây là kiểm chứng tích hợp, không phải thước đo độ giống giọng người thật. Test fixture kiểm tra contract, consent, FFmpeg, cache/retry và cảnh báo, không được coi là kết quả AI thật.

Nguồn API/SDK chính thức đã đọc: https://github.com/pnnbao97/VieNeu-TTS và `apps/openai_speech.py`; đối chiếu trực tiếp OpenAPI của service local. Phối PCM16 theo block bằng thư viện chuẩn `array`, có clipping giới hạn và xử lý byte order; không phụ thuộc module `audioop` đã bị bỏ ở Python3.13.

Kiểm tra cuối:33 pytest; TypeScript/Vite build; Playwright mở rộng với worker/FFmpeg thật và provider fixture, không lỗi trang. Consent gắn fingerprint provider; nếu cấu hình đổi phải kiểm tra/xác nhận lại. Hai ID giọng nhân vật khác nhau, cache retry và PCM clipping/timeline có regression.

Gán giọng/nhân vật được lưu trong project khi xếp hàng đọc track, được khôi phục khi mở lại công cụ. Xác nhận truyền dữ liệu không được lưu ngầm; nếu rời công cụ hoặc provider thay đổi, cần kiểm tra/xác nhận lại.
