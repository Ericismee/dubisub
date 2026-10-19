# Tách audio local (thử nghiệm)

Không cài vào môi trường API hoặc VieNeu. Runtime đã kiểm thử trên Windows CPU:

```powershell
uv venv --python 3.12 data/separator-runtime/.venv
uv pip install --python data/separator-runtime/.venv/Scripts/python.exe -r scripts/separator-runtime-requirements.txt
```

Model duy nhất được adapter chấp nhận: HTDemucs từ bản phát hành Demucs chính thức (MIT). Đây là model huấn luyện cho **nhạc**, chưa chứng minh tách thoại phim sạch. Mã audio-separator MIT, model và dữ liệu huấn luyện là các thành phần riêng; xem [REFERENCES.md](REFERENCES.md).

- Weight: `https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/955717e8-8726e21a.th`
- Lưu: `data/separator-runtime/models/955717e8-8726e21a.th`
- SHA256: `8726e21a993978c7ba086d3872e7608d7d5bfca646ca4aca459ffda844faa8b4`
- File `htdemucs.yaml` cùng thư mục có nội dung `models: ['955717e8']`.

Không phân phối weight trong Git. Adapter kiểm hash trước khi nạp, chỉ cho phép checkpoint đã đăng ký và dùng `weights_only=True` với allowlist lớp cụ thể. Trong tác vụ, các đường tải model/metadata qua requests, urllib và torch hub bị tắt; không gửi media ra ngoài. CPU hai luồng; không tranh GPU với TTS.

Trong **Giọng → Tách nền & thoại**, chọn tối đa 30 giây, tách rồi nghe cả vocal/nền. Chỉ sau khi đánh dấu chấp nhận mẫu mới cho chạy toàn video (tối đa 20 phút/lượt). Kết quả nền là tổng drums+bass+other, **không phải** stem nhạc và SFX độc lập. Nền có thể còn thoại, vocal có thể chứa nhạc, hiệu ứng có thể bị mất. Không tự đổi model khi lỗi. Mẫu thử chưa duyệt không được dùng làm nền cho toàn phim.

Worker lưu checkpoint từng đoạn, cache theo nguồn/model/thiết lập, chồng 500 ms hai đầu và crossfade một giây khi nối. Hủy dùng cùng cơ chế dừng cây subprocess của media worker. Hai WAV đầu ra stereo 48 kHz phải khớp thời lượng nguồn trước khi lưu. Bộ phối âm dùng nền + TTS + vocal gốc tùy chọn, không cộng lại cả bản mix gốc.

Kiểm thử thật 2026-10-19: đoạn phim 180–195s tạo hai WAV 15.000s, stereo 48 kHz. Inference 19.43s, tổng worker 22.08s trên CPU hai luồng. Đây là số đo một mẫu, không phải benchmark chất lượng hoặc tốc độ toàn phim. Mẫu được giữ **chưa duyệt** để người dùng nghe. Không tích hợp ProPainter vì điều khoản phi thương mại; hiện chỉ có làm mờ OCR theo vùng/thời gian, chưa có inpainting.
