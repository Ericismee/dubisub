# Run DubiSub on Windows

This guide uses separate PowerShell windows for the API, worker, and frontend so you can start, inspect, and stop each process independently.

## Prerequisites

- Windows, Python 3.12.13 (selected by `.python-version`), `uv`, and Node.js/npm.
- FFmpeg and FFprobe on `PATH` for media processing.
- Open PowerShell in the repository at `D:\WorkSpace\dubisub`.

## First-time setup

Run once after cloning the repository or when dependencies change:

```powershell
Set-Location D:\WorkSpace\dubisub
uv sync --locked
npm ci --prefix frontend
```

## Run each component separately

Before starting, check that ports 3600 (frontend) and 6060 (API) are not already in use. Do not stop an unrelated process to free a port.

### 1. Backend API

In the first PowerShell window:

```powershell
Set-Location D:\WorkSpace\dubisub
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 6060
```

The API initializes or updates the local database at `data\dubisub.sqlite3`. Browse the API docs at <http://127.0.0.1:6060/docs> or check its health at <http://127.0.0.1:6060/health>.

### 2. Worker

In a second PowerShell window, start the worker to process probes and background media jobs:

```powershell
Set-Location D:\WorkSpace\dubisub
.\.venv\Scripts\python.exe -m backend.worker
```

Keep this window open so the worker can continue accepting jobs. The API and worker share the `data` directory.

### 3. Frontend

In a third PowerShell window:

```powershell
Set-Location D:\WorkSpace\dubisub
npm --prefix frontend run dev
```

Open <http://127.0.0.1:3600>. Vite proxies `/api` and `/health` requests to the API on port 6060, so start the API first or at the same time.

## Configuration and data

- The API process reads provider environment variables. `.env.example` is a reference only; the project does **not automatically load** a `.env` file.
- Set provider variables in the PowerShell window before starting the API. If you change `DUBISUB_DATA_DIR`, set the same value in both the API and worker windows, for example: `$env:DUBISUB_DATA_DIR = 'D:\DubiSubData'`.
- Data is stored locally in `data` by default. Do not remove that directory if you want to keep your projects and imported media.
- No API key is required to start the application. Only tasks using a configured provider require the corresponding service or credentials.

## Check, view logs, and stop

In another PowerShell window, check the API:

```powershell
Invoke-RestMethod http://127.0.0.1:6060/health
```

API, worker, and Vite logs appear in their respective windows. Press `Ctrl+C` in each window to stop that process.

## Start all components together

To start the API, worker, and frontend with one command instead of three windows:

```powershell
Set-Location D:\WorkSpace\dubisub
powershell -ExecutionPolicy Bypass -File scripts\start.ps1
```

Open <http://127.0.0.1:3600> and keep the launcher window open. Press `Ctrl+C` there to stop, or run this command from another PowerShell window:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop.ps1
```

The launcher refuses to start if another process is already listening on port 3600 or 6060; it does not stop existing processes.
