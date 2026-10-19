# VieNeu local đã kiểm tra

Runtime riêng, không cài SDK vào môi trường FastAPI chính:

```powershell
uv venv data/vieneu-runtime/.venv --python 3.12
uv pip sync --python data/vieneu-runtime/.venv/Scripts/python.exe scripts/vieneu-runtime-requirements.txt
./scripts/start_vieneu.ps1
```

File requirements ghi lại môi trường thực tế đã chạy, gồm cả thư viện OCR dùng kiểm tra nội bộ. Entry point chính thức là `apps.openai_speech` của VieNeu 3.8.3, CPU/ONNX/fp32, một stream. Giữ cửa sổ launcher mở. Studio chạy riêng bằng `./scripts/start.ps1`.

Trong Cài đặt → Giọng đọc: endpoint `http://127.0.0.1:8001/v1`, model `vieneu-v3-turbo`. Kiểm tra API và lấy danh sách giọng trước khi tạo lời đọc. VieNeu chỉ làm TTS; ASR và LLM là cấu hình riêng.

Lần đầu SDK tải model công khai vào `data/vieneu-runtime/huggingface`, không dùng ngầm token Hugging Face. ONNXRuntime có thể từ chối external-data symlink sau lần tải đầu. Chạy lại launcher: `prepare_vieneu_models.py` chỉ sao chép các link file đang tồn tại và trỏ vào chính runtime này. Không tắt kiểm tra bảo mật ONNX, không sửa cache toàn cục. Launcher từ chối chạy khi port đã có dịch vụ, không tự dừng tiến trình khác.

Model đã dùng cho smoke test: VieNeu-TTS-v3-Turbo snapshot `61b85e3d937fbbacb387714180e8182823512523`; MOSS-Audio-Tokenizer-Nano-ONNX snapshot `ceff0d0749bfb3fa2d61149794ec6feef0d1e1ae`. Model download phụ thuộc SDK/upstream; không cam kết mọi phiên bản tương lai tương thích.

Kết quả thật, lệnh kiểm thử và giới hạn chất lượng tại [STATUS.md](STATUS.md). Media, model, cache và dữ liệu giọng nằm trong `data/` bị Git bỏ qua.
