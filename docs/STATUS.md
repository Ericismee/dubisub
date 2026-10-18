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


## AI workflows, subtitle editing, voice samples and MP4 export — 2026-10-18

Implemented:
- Durable ASR and multilingual translation jobs through explicitly configured providers. Translation preserves original IDs/timing and source tracks, uses glossary, validates exact cue IDs/order, checkpoints batches and resumes manual retries. Source changes invalidate translation approval. ASR extracts real PCM chunks and uses actual segment timestamps; no synthetic output fallback.
- Ollama native `/api/tags` + `/api/chat` and OpenAI-compatible translation. Settings separate protocol, endpoint, actual discovered models and a catalog of 24 Ollama families. Catalog entries are suggestions, never proof of installation/quality. No automatic model pull or silent fallback. Ollama CLI exists locally; default port 11434 was not listening during inspection. Live LLM and ASR inference remain unverified pending an available configured service/model.
- Manual subtitle tracks, split/merge/delete/add, find/replace, timing offset, CPS display, existing autosave/undo/redo, SRT/VTT/ASS export. ASS neutralizes literal override braces with fullwidth braces and literal backslashes with word joiners; ASS has centisecond precision.
- Provider voice discovery with language/gender filtering, standard/custom sample text, real cached WAV samples and stop-on-language/voice-change playback. Actual configured VieNeu service returned 25 voices and one Vietnamese sample completed successfully. This does not verify every voice/language. Providers lacking declared language metadata are not assigned invented multilingual capabilities.
- Single-source render plan shared with preview: trim, speed, canvas aspect, resolution/fps, volume, optional approved subtitles; durable FFmpeg MP4 jobs and owned artifact download. Actual exported AV duration, trim colors, dimensions and immutable input checksum tested. Not a multitrack compositor; browser preview volume is capped at 1 and subtitle styling is not pixel-identical to ASS rendering.
- Persistent project trash/restore, project search, guarded thumbnail cache and direct HEAD-rejected URL Range fallback.

Verification: backend 24 tests passed before adding the Ollama-specific test; Ollama test and final totals recorded below. TypeScript/Vite production build passed. Full Playwright flow passed before Ollama controls, including subtitle editing, real MP4 export/download, controlled translation, voice sample cache/playback and original import/settings/project flows. Controlled AI fixtures verify adapter behavior, not AI quality. Actual TTS sample separately verified. One existing Starlette/AnyIO deprecation warning remains.

Remaining: live Ollama/ASR model inference, full review-script generation, full video dubbing/speaker mapping/alignment, multitrack editing/effects/transitions, broad provider-specific voice adapters, long-media/crash/disk exhaustion and comprehensive accessibility QA. Product is NOT feature-complete. Previous M2 limits still apply except thumbnail and HEAD fallback now implemented. No NotebookE files/settings/secrets accessed.

Final verification: 25 backend tests passed (including native Ollama tags/chat fixture), TypeScript/Vite build and extended Playwright browser flow passed. Ollama has no live service at default port during this run; no live LLM/ASR claim.


## URL import repair — 2026-10-18
- Observed actual user download: 73-minute YouTube video, format399 1440p, estimated317MB; staging grew from31MB to50MB during diagnosis and heartbeat remained current. It was downloading slowly, not frozen. Previous download attempts had source rejection. Existing running child was preserved, not canceled/restarted.
- YouTube download rejection HTTP401/403/410 now refreshes signed URLs once through the same guarded extractor, preserving explicit format/subtitle IDs. Old representation/validator is discarded before the refreshed request; no cookie access or network-policy bypass. Other failures remain explicit.
- UI shows estimated format size, byte count/speed/file count when the worker provides them; stale prior errors hidden while retry runs. Existing active download keeps its old child code; detailed transfer API requires the next normal application restart.
- Live independent YouTube smoke jNQXAC9IVRw: inspect, actual format160 download, audio merge and probe succeeded in temporary storage. Controlled URL regressions6 passed, including bounded signed-URL refresh and Unicode subtitle preservation. Frontend build passed. This does not guarantee every YouTube source or the current long import/subtitle selections will succeed.

Final link checks: 26 backend tests passed; browser controlled-response test passed for byte/speed/size display and hiding stale errors; no page errors.


## Pre-merge code review — 2026-10-18
Reviewed AI/provider responses, source timing and approval, worker leases/cancellation, file commits and URL retry boundaries. Fixed voice catalog validation for malformed model/language metadata and stale pending voice-sample state on project switch. Added provider-metadata regression. Backend27 tests and frontend production build passed. Latest origin/main merged without conflict. Existing long import left running.

Pre-merge browser regression passed in isolated temporary storage on ports3601/6061. A test-only Playwright header override supplied the standard allowed origin; production origin policy was unchanged. Upload/probe, subtitle edit/autosave/undo, exports, translation/voice fixtures, project management and URL import passed with no browser errors. GitHub connector PR creation unavailable (403 integration permissions); merge performed through authorized Git access.


## Project header actions — 2026-10-18
Moved edit beside the active project title and delete to the right header actions; removed row actions from the library. Actions disabled with no selected project or unsaved/busy state. Existing revision checks and delete confirmation retained. Production frontend build passed.

Studio chrome follow-up: red delete treatment including disabled state, bounded zoom minus/plus controls (100–500%, 50% steps), compact aligned header and consolidated sidebar settings entry. Browser checks passed at1256/1543/800/390px for settings dialog, zoom values/bounds, delete color and horizontal overflow; screenshot inspected. Frontend build passed.

Header theme/brand follow-up: direct persistent dark/light toggle with moon/sun and theme-specific color; sidebar remains the settings entry. Added white/purple dark logo and compact-viewBox wordmark variants derived from original assets (originals retained). Browser checks passed for toggle without dialog, reload persistence, logo color, mobile visibility/width; production build passed.


## VieNeu reference voices & narration — 2026-10-18
- TTS defaults to local VieNeu v3 Turbo; missing-provider messages separate ASR/LLM/TTS and reject VieNeu misconfigured as translation/ASR. Existing unrelated settings preserved. No live Ollama service at11434; no fake translation/ASR fallback.
- Added backend/dubbing.py and DubbingPanel.tsx: consented local3–8s FFmpeg reference extraction/preview/naming; provider contract discovery; preset/reference voices, per-character cue assignments, cached standard/custom previews, per-cue narration and regeneration, actual duration/overflow/overlap markers, PCM timeline WAV and source-video+new-audio MP4. Source immutable. Worker progress/cancel/retry/checkpoint/cache supported, max300cues/300chars per cue/2h timeline/3h job.
- Delete removes local profile, associated cache/outputs and cancels dependent jobs. VieNeu API has no DELETE for RAM embedding; UI explicitly discloses retention until provider restart before transmission. No claim of remote erasure. No autonomous external upload before user confirms target provider/data in UI.
- Actual VieNeu local cloning verified with permitted synthetic TTS reference in isolated temp storage: video/extract/enroll/two utterances/WAV+MP4/delete succeeded. Generated durations3280ms/1600ms and overflow/overlap measured. This verifies integration, not human speaker similarity.
- 31 backend tests passed, TypeScript/Vite build passed; extended browser evidence recorded after final run. Controlled fixtures are not live AI quality evidence. Remaining: automatic noise/music/multispeaker detection, diarization, word alignment/time stretch, original-background mixing/ducking, human voice quality evaluation; VI only enabled in current cloning adapter. See docs/VOICE_CLONING.vi.md.

Final voice checks: 32 backend tests passed (one existing Starlette/AnyIO deprecation); extended browser flow passed including consent, actual FFmpeg extraction/mixing, controlled clone contract, character assignment, MP4 download, per-cue regeneration/cache and deletion; no page errors. Separately verified real local VieNeu enrollment/inference with synthetic reference. TTS consent is bound to the displayed provider/model snapshot; changed settings require confirmation again before media transmission. PCM uses standard array arithmetic (Python3.11–3.13 compatible), with clipping/timeline regression.

Character/voice assignments now persist in project narration_settings and are removed when their profile is deleted. Final backend suite33 passed; frontend build passed. No README/RUNNING edits from concurrent work were included in this feature.

Final extended browser run passed after assignment persistence, including leaving/reopening the voice tool, restoring character mapping, renewed transfer consent and per-cue regeneration.


## Auto / capability / evidence-linked analysis / review baseline — 2026-10-18

Implemented within the existing provider, worker, subtitle and dubbing modules:
- Schema4 adds durable pipeline orchestration and configuration-signature capability records. Separate ASR/LLM/Vision/TTS settings, explicit synthetic inference probes, authentication choice via environment-key references, presets and actual model discovery. Model listing alone never verifies inference.
- Auto wizard plans/discloses providers/data before consent, then uses existing ASR/translation jobs and actual SRT/VTT/ASS export. Source-track priority, multilingual targets, cancellation/retry/checkpoint, source hash invalidation, stable child IDs and independent destination failures. Preserves source and raw ASR; 600s chunks with10s overlap, real provider timestamps, confidence/boundary review flags and cross-chunk deduplication.
- Frame sampling via existing FFmpeg worker: max16frames,4/request,640px/256KiB per frame. Evidence-linked scene observations and transcript/vision summary/review/description drafts. Strict structured citations; short request aliases map back to stable evidence IDs after validation. Editable approval, source seek, Markdown/JSON exports, stale transcript protection. Grouped analysis is bounded; hierarchical whole-video reduction and video-native remain pending.
- Approved scripts reuse existing VieNeu preset/reference voices and content-addressed audio cache. Measured narration creates a separate review subtitle/output timeline. MP4 baseline uses first cited scene per paragraph, freeze tails,640x360/25fps and replacement audio; actual duration validated. Review preview/timeline uses generated output, while evidence seek returns to source. Source renderer rejects review subtitles. Scene selection/editor, background mixing and review burn-in remain pending.
- UI: darker light-theme rail/labels/ruler, compact sticky blurred header, narrower rail, common SVG edit icon, clearer ASR/LLM sections, workspace navigation and Auto guide. Original brand assets retained.

Evidence:
- Full backend regression43 passed (existing Starlette/AnyIO deprecation only); new targeted capability/migration/pipeline/analysis/review tests use controlled adapters plus actual FFmpeg. Re-run results recorded below if subsequent changes require it.
- TypeScript/Vite build passed. Extended Playwright/Edge passed Auto inference probe→multilingual sub export→review draft→approve→TTS→MP4, review preview/new timeline, prior cloning/edit/export flows, Unicode/RTL, keyboard focus and390px overflow. Test-only3601/6061 isolation retained production origin policy. Light screenshot after theme transition inspected separately.
- Actual local Ollama now available: qwen2.5:7b, llava:latest, nomic-embed-text:latest. Qwen nonce/text and Vietnamese translation→SRT/VTT/ASS passed. LLaVA declared vision and correctly read RGB and yellow/green/white synthetic images; frame+transcript→Qwen summary with real evidence/timecode passed via scripts/check_ai_live.py. Random color probe had failures: no claim of general image accuracy. Unknown model evidence IDs were rejected; alias correction was then verified live.
- Actual VieNeu preset narration→review WAV/MP4 passed with permitted generated test video/script:5280ms+3280ms, output timeline0–8560ms, freeze tails3280ms/1280ms. Prior real reference cloning verification remains documented above. These are integration smokes, not human similarity/AI-quality benchmarks.
- User's erroneous translation→VieNeu config was replaced with verified local Qwen; previous settings backed up under ignored data. Existing other roles preserved; local LLaVA added only when Vision absent. No model downloads, secret lookup in other projects or NotebookE changes.

Remaining: actual ASR service/model absent (faster-whisper not installed); raw-video→real-ASR end-to-end still unverified. Also separate LLM proofreading, word alignment/diarization/noise detection, hierarchical summaries, native-video, editable review scenes, integrated one-run auto-to-video, provider cost accounting and exhaustive crash/long-video/disk/cancellation QA. Auto analysis stops for explicit draft approval; manual subtitle editing/export remains independent of AI.

See docs/AUTO_WORKFLOWS.vi.md for opening the app, exact commands, disclosures and limits. Concurrent README.md/README.vi.md and docs/RUNNING.* edits preserved separately.


Final hardening: full backend suite45 passed; final frontend build and extended Playwright passed. Added process-group/tree cancellation with an actual sleeping grandchild regression (Windows taskkill /T, POSIX process group), bounded active pipelines (one/project,20global),100-item history, ASR original JSON download and metadata preservation for untouched cues. Source media remains under the same FFmpeg protocol/format allowlists. Launcher stop tolerates children exiting during taskkill; final own-app stop/start and API/schema4/UI3600 checks passed.

Concurrent workspace commit b076138 was already pushed while this turn ran, including the shared implementation and README/RUNNING edits. It was preserved; only remaining hardening/status changes are committed afterwards. Final environment check found ASR newly configured to nomic-embed-text:latest (embedding-only, not an ASR provider). Its configuration was retained, with an actionable role guard preventing audio from being sent to that model; targeted provider/dubbing5 tests passed. A genuine Whisper-compatible endpoint/model is still required for real ASR.
