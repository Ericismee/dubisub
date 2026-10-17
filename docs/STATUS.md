# DubiSub — status

Updated 2026-10-17. Root verified: `D:/WorkSpace/dubisub`. Target repository: `ericismee/dubisub`.

## M1: local foundation baseline verified

- React/TypeScript/Vite UI, FastAPI API and independent Python worker. UI 3600, API 6060, bound to loopback.
- SQLite WAL, transactional migrations through version 2; versioned project documents, stable cue/asset/job IDs and revision conflict detection.
- Create/list/reopen projects; persist review/full mode and BCP 47 target (Vietnamese default). Library currently lists the latest 100 projects.
- Chunked upload to UUID paths with checksum, size limit and disk reserve; source files never edited. FFprobe inspects actual streams; worker extracts supported embedded text subtitles via FFmpeg. Network protocols/playlists disabled for local inspection.
- Import UTF-8/BOM SRT/VTT/ASS, Unicode/CJK/RTL text, integer millisecond timing, edit validation, autosave, explicit save, session undo/redo and reopen from SQLite.
- Native video preview, cue seek and VTT subtitle track from the same saved cues used for export. MP4 H.264 playback verified on Windows Edge.
- Download real SRT/VTT without AI or video render. ASS imports flatten styling and effects to plain text.
- Durable job claim, heartbeat/lease recovery, process timeout, output bounds, cancel and bounded manual retry (3 attempts). Probe/extraction commits metadata, tracks and completion in one transaction to prevent duplicate tracks on retry. Progress is coarse (10/100), not continuous media progress.
- Provider configuration persists endpoint/model/key environment-variable name only. Keys are not stored or returned. Capabilities stay empty/unverified; no AI request occurs in M1.
- Local start script, sample generator, pinned Python/frontend lockfiles and bilingual run instructions.

## Verification evidence

- `.venv/Scripts/python -m pytest -q`: **7 passed**, one upstream Starlette/AnyIO deprecation warning. Tests include actual FFmpeg MKV creation/extraction, Windows paths with spaces/diacritics, UTF-8/BOM/RTL/ASS, stable IDs, SRT/VTT round-trip, HTTP range response, revision conflict, malformed/oversize upload, missing media tool, queued/running cancellation, simulated expired worker lease, retry bounds, origin checks and provider metadata secrecy.
- `npm --prefix frontend run build`: TypeScript and Vite production build passed.
- `npm audit --prefix frontend`: **0 vulnerabilities** after pinning Vite 7.3.7.
- `.venv/Scripts/python scripts/check_e2e.py`: **passed** using headless installed Edge, a real short FFmpeg MP4, separate API/worker/Vite processes and temporary SQLite storage. Covers create review-mode project, upload/probe, playback metadata/seek, edit multilingual cues, autosave, undo/redo, reload/reopen, download SRT/VTT, native subtitle-track loading, keyboard focus, 390px layout and no browser page errors.
- Screenshots: ignored `test-results/studio-desktop.png` and `test-results/studio-mobile.png`. Desktop inspected visually.

## Partial and unverified areas

- Provider connection testing and live ASR/LLM/TTS are not implemented. Settings are configuration only; no model/key/service is assumed. Review/full choices preserve intent, not completed review/dubbing pipelines.
- No general timeline/render plan yet (M4); subtitle preview/export share saved cue data only. No split/merge, drift adjustment, waveform/proxy, video export or persisted undo history. Undo/redo lasts until reopen/track change.
- Browser playback of other containers/codecs is not guaranteed. Image subtitles remain detected in probe metadata; no OCR or ASR fallback. Only UTF-8 subtitle encodings are accepted.
- Lease recovery is exercised with an expired database lease; hard OS crash/power-loss recovery, multi-worker load, large/long media and real disk exhaustion have not been benchmarked. External imports/providers are disabled, not mocked.
- Keyboard focus and mobile overflow are checked; this is not a complete accessibility or screen-reader audit. No installer/release or CI service has been published.

## Run and next step

Run `uv sync --locked`, `npm ci --prefix frontend`, then `powershell -ExecutionPolicy Bypass -File scripts/start.ps1`; open `http://127.0.0.1:3600`. Keep the terminal open. See README.vi.md for operation and `.env.example` for environment variables (not automatically loaded).

Next: M2 controlled URL import, with local HTTP fixtures, redirect/DNS/size policies and enforceable extractor networking before enabling yt-dlp. M3 adds verified provider capabilities and ASR/translation. Do not infer AI output from synthetic sample media.

The existing MIT license and concurrent branding/Git setup were preserved. This implementation turn did not initialize Git, change remotes, commit, upload or publish anything, and did not access NotebookE.
