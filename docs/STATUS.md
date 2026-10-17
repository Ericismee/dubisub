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
- Local start/stop scripts, sample generator, pinned Python/frontend lockfiles and bilingual run instructions.

## Verification evidence

- `.venv/Scripts/python -m pytest -q`: **8 passed**, one upstream Starlette/AnyIO deprecation warning. Tests include actual FFmpeg MKV creation/extraction, Windows paths with spaces/diacritics, UTF-8/BOM/RTL/ASS, stable IDs, SRT/VTT round-trip, HTTP range response, revision conflict, malformed/oversize upload, missing media tool, queued/running cancellation, simulated expired worker lease, retry bounds, origin checks and provider metadata secrecy.
- `npm --prefix frontend run build`: TypeScript and Vite production build passed.
- `npm audit --prefix frontend`: **0 vulnerabilities** after pinning Vite 7.3.7.
- `.venv/Scripts/python scripts/check_e2e.py`: **passed** using headless installed Edge, a real short FFmpeg MP4, separate API/worker/Vite processes and temporary SQLite storage. Covers create review-mode project, upload/probe, playback metadata/seek, edit multilingual cues, autosave, undo/redo, reload/reopen, download SRT/VTT, native subtitle-track loading, keyboard focus, 390px layout and no browser page errors.
- Screenshots: ignored `test-results/studio-desktop.png` and `test-results/studio-mobile.png`. Desktop inspected visually.

- Launcher smoke test: API `/health` returned schema 2 / ok; UI returned HTTP 200. A second launcher correctly refused occupied port 3600 without stopping the running application. The stop script terminated only the recorded launcher tree, validating its PID/start time/workspace.

## Partial and unverified areas

- Provider connection testing and live ASR/LLM/TTS are not implemented. Settings are configuration only; no model/key/service is assumed. Review/full choices preserve intent, not completed review/dubbing pipelines.
- No general timeline/render plan yet (M4); subtitle preview/export share saved cue data only. No split/merge, drift adjustment, waveform/proxy, video export or persisted undo history. Undo/redo lasts until reopen/track change.
- Browser playback of other containers/codecs is not guaranteed. Image subtitles remain detected in probe metadata; no OCR or ASR fallback. Only UTF-8 subtitle encodings are accepted.
- Lease recovery is exercised with an expired database lease; hard OS crash/power-loss recovery, multi-worker load, large/long media and real disk exhaustion have not been benchmarked. AI providers remain unconnected; see the URL-import update below for working remote imports.
- Keyboard focus and mobile overflow are checked; this is not a complete accessibility or screen-reader audit. No installer/release or CI service has been published.

## Run and next step

Run `uv sync --locked`, `npm ci --prefix frontend`, then `powershell -ExecutionPolicy Bypass -File scripts/start.ps1`; open `http://127.0.0.1:3600`. Keep the terminal open. See README.vi.md for operation and `.env.example` for environment variables (not automatically loaded).

Next: M2 controlled URL import, with local HTTP fixtures, redirect/DNS/size policies and enforceable extractor networking before enabling yt-dlp. M3 adds verified provider capabilities and ASR/translation. Do not infer AI output from synthetic sample media.

The existing MIT license and concurrent branding/Git setup were preserved. This implementation turn did not initialize Git, change remotes, commit, upload or publish anything, and did not access NotebookE.


## Studio UI refresh — 2026-10-17

- Replaced the conditional M1 form layout with a persistent studio: tool rail, project/media library, central preview, subtitle inspector, export panel and source timeline. All core surfaces are present before a project is selected; importing into an empty studio creates a project automatically.
- Uses the original `assets/wordmark.svg`, `assets/logo.svg` and `assets/banner.svg` directly through Vite imports. Original assets were not edited. White/black/violet styling follows the supplied ELG Labs reference and the project brand; layout draws from the user's video-editor screenshots.
- Added native SVG arrow cursors on fine pointers, violet filled pointer on interactive controls, normal text caret in editing fields and system fallback. No pointer follower, animation loop or per-frame React updates.
- Source timeline visualizes actual loaded media/cue timing. Working controls: play/pause, seek, cue seek, timeline zoom, media selection, fullscreen and preview aspect ratio. Aspect changes affect preview only; this is not a video renderer or multitrack edit engine.
- Media drop on the central preview imports real files. Subtitle edit/autosave/undo/redo/export and conflict fallback remain connected to the existing API. AI/review/effects/voice panels clearly show unavailable functionality; no generated content or capabilities were invented.
- Verification: TypeScript/Vite build passed; backend regression **8 passed**; extended Playwright/Edge flow passed with permanent empty-state panels, original brand images, SVG cursor CSS, actual upload/edit/save/reopen/export, timeline play/pause/seek/zoom, preview aspect changes, tool navigation retaining the subtitle editor, native VTT captions and 390px layout. No browser page errors. Desktop/mobile screenshots inspected visually.


## Project management, dark UI, grouped settings and URL import — 2026-10-17

Completed and verified:
- Edit project name, workflow mode and BCP 47 target with revision checking. Existing media/cues are preserved; changing the target does not translate content.
- Delete confirmation removes the project from the library and cancels queued/running jobs. Deletion is recoverable: source files and documents are retained, with an immediate Restore action and API restore endpoint. This is not permanent disk cleanup.
- Dark theme is now the default. Settings offer dark/light and custom/system cursors, saved in browser-local preferences. Original assets are reused; the wordmark retains its original colors on a transparent background, per the latest user preference; its source is unchanged.
- Dedicated modal settings with keyboard focus containment: Appearance, ASR, Translation, TTS, Storage & Media. Each AI section edits only its own endpoint/model/key-variable reference. Settings remain configuration only; no live AI capability is claimed.
- M2 URL-import baseline: paste a single YouTube/shorts/youtu.be URL or direct media/SRT/VTT/ASS URL, inspect in a durable worker, select format/video/audio/subtitle-only and up to five subtitle tracks, then import directly into the local asset store. Auto/manual captions are distinguished. Video-only streams are merged with available audio using local FFmpeg. Media remains in DubiSub storage; the user need not download and upload manually.
- SQLite schema v3 records remote sources, selections and provenance; raw signed stream URLs stay in local ignored storage, never in the public API. Imported files get SHA-256 checksums; metadata is confirmed by the existing FFprobe job. Staging cleanup is scoped to each job. Validated Range/If-Range resume is supported when an interrupted file has an ETag/Last-Modified validator; manual failure/cancel cleanup removes temporary data.
- Network transport pins a validated public DNS address for the socket connection, verifies TLS against the original hostname, revalidates redirects, restricts HTTP(S)/ports, limits redirects/request count/bytes/time/disk and ignores environment proxies. Every yt-dlp request uses this transport with no fallback handlers, external downloaders, JS runtimes, browser cookie reading or remote components. Local/private/link-local/mapped IP targets are rejected. An exact loopback fixture exception exists only in test-injected clients, never in production API/environment settings.

Evidence:
- Backend pytest: **14 passed**, with one existing upstream deprecation warning. New tests cover edit/conflict/delete/restore/source preservation; private/mixed-DNS/redirect blocking; extractor no-fallback policy; oversize rejection; ETag/Range continuation; actual HTTP subtitle import/export and actual HTTP video download/probe; production worker rejecting loopback targets.
- TypeScript/Vite build passed. Extended Playwright/Edge passed: existing subtitle flow plus default dark, light/dark switching, grouped provider save, project edit/cancel-delete/delete/restore with retained subtitle content, and UI analyze/import of a controlled HTTP video through an explicitly test-only worker.
- Manual live YouTube smoke: public video `jNQXAC9IVRw` ("Me at the zoo"), format 160 plus available audio, inspect/download/merge/probe all succeeded. Temporary project and media were removed after the test. This is a single successful sample, not support for every video/website. The older yt-dlp test video BaW_jenozKc was unavailable and was not used as proof of functionality.
- Screenshots inspected: `test-results/studio-dark-managed.png`, `studio-settings.png`, `studio-link-import.png` (ignored).

Remaining M2 limitations: no playlist, live streams, DRM, authenticated/cookie sources, arbitrary page extractors, thumbnail preview, HLS/DASH manifest downloads or JS challenge runtime. Only direct HTTP(S) formats reported by the YouTube extractor are offered; some videos may require unsupported verification. Direct servers must support HEAD. Format links can expire; re-analyze the source. No automatic ASR/translation is triggered. Full crash/disk-exhaustion and large-file benchmarks remain pending. Do not call M2 complete beyond this verified baseline.
