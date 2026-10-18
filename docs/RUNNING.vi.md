# Chạy DubiSub trên Windows

Hướng dẫn này dùng các cửa sổ PowerShell riêng cho API, worker và frontend để bạn có thể khởi động, xem log và dừng từng phần độc lập.

## Yêu cầu

- Windows, Python 3.12.13 (được chọn trong `.python-version`), `uv`, Node.js/npm.
- FFmpeg và FFprobe trong `PATH` để xử lý media.
- Mở PowerShell tại thư mục repo `D:\WorkSpace\dubisub`.

## Cài đặt lần đầu

Chạy một lần sau khi clone repo hoặc khi dependencies thay đổi:

```powershell
Set-Location D:\WorkSpace\dubisub
uv sync --locked
npm ci --prefix frontend
```

## Chạy từng phần riêng

Trước khi chạy, kiểm tra cổng 3600 (frontend) và 6060 (API) chưa bị chương trình khác sử dụng. Không dừng tiến trình lạ để giải phóng cổng.

### 1. API backend

Trong cửa sổ PowerShell thứ nhất:

```powershell
Set-Location D:\WorkSpace\dubisub
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 6060
```

API tự khởi tạo/cập nhật cơ sở dữ liệu cục bộ tại `data\dubisub.sqlite3`. Tài liệu API ở <http://127.0.0.1:6060/docs>; kiểm tra trạng thái tại <http://127.0.0.1:6060/health>.

### 2. Worker

Trong cửa sổ PowerShell thứ hai, chạy worker để xử lý probe và các tác vụ media nền:

```powershell
Set-Location D:\WorkSpace\dubisub
.\.venv\Scripts\python.exe -m backend.worker
```

Giữ cửa sổ mở để worker tiếp tục nhận tác vụ. Worker và API dùng chung thư mục dữ liệu `data`.

### 3. Frontend

Trong cửa sổ PowerShell thứ ba:

```powershell
Set-Location D:\WorkSpace\dubisub
npm --prefix frontend run dev
```

Mở <http://127.0.0.1:3600>. Vite chuyển các yêu cầu `/api` và `/health` tới API trên cổng 6060, vì vậy cần chạy API trước hoặc cùng lúc.

## Cấu hình và dữ liệu

- Biến môi trường được đọc từ tiến trình API. `.env.example` chỉ liệt kê ví dụ; dự án **không tự nạp** file `.env`.
- Đặt biến provider trong cửa sổ PowerShell chạy API trước khi khởi động. Nếu đổi `DUBISUB_DATA_DIR`, đặt cùng giá trị trong cả cửa sổ API và worker, ví dụ: `$env:DUBISUB_DATA_DIR = 'D:\DubiSubData'`.
- Dữ liệu mặc định được lưu cục bộ trong `data`. Không xóa thư mục này nếu muốn giữ dự án và media đã nhập.
- Không cần API key để khởi chạy ứng dụng. Chỉ tác vụ sử dụng provider đã cấu hình mới cần dịch vụ hoặc thông tin xác thực tương ứng.

## Kiểm tra, xem log và dừng

Trong cửa sổ PowerShell khác, kiểm tra API:

```powershell
Invoke-RestMethod http://127.0.0.1:6060/health
```

Log API, worker và Vite được hiển thị trong cửa sổ tương ứng. Nhấn `Ctrl+C` trong từng cửa sổ để dừng đúng tiến trình đó.

## Cách khởi động gộp

Để chạy API, worker và frontend bằng một lệnh thay vì ba cửa sổ:

```powershell
Set-Location D:\WorkSpace\dubisub
powershell -ExecutionPolicy Bypass -File scripts\start.ps1
```

Mở <http://127.0.0.1:3600> và giữ cửa sổ launcher mở. Nhấn `Ctrl+C` tại đó để dừng; hoặc chạy lệnh sau trong cửa sổ PowerShell khác:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop.ps1
```

Launcher từ chối khởi động nếu cổng 3600 hoặc 6060 đã có tiến trình lắng nghe; nó không tự dừng các tiến trình đang chạy.