# DubiSub — active context

## Objective / rules
Independent multilingual video/subtitle studio, Vietnamese default; translation/full dubbing and review. Latest user request: Auto transcript→translation/sub export, evidence-linked vision/summary/review, integrated VieNeu reference voices; clearer light UI/configuration. Implement runnable milestones A–D, no new idea/approval loop. PROJECT_BRIEF.vi.md section12 takes precedence. Root D:/WorkSpace/dubisub; repo ericismee/dubisub. Never touch NotebookE or its secrets/processes. Preserve user edits; no fake AI output or silent provider/voice fallback. Earlier user authorizes push to suitable branch without codex/; do not auto merge.

## Architecture / entrypoints
React/TS/Vite, FastAPI, SQLite WAL schema4, durable worker, FFmpeg/FFprobe, safe yt-dlp adapter. Existing upload/link/provider/ASR/translation/dubbing/render modules reused. Core: backend/app.py, store.py, worker.py, providers.py, ai_tasks.py, dubbing.py, rendering.py. New: capabilities.py, pipelines.py, analysis.py, review_render.py; frontend AutoWizard.tsx/AnalysisPanel.tsx plus existing settings/workflow/dubbing panels. Documentation: docs/STATUS.md, docs/AUTO_WORKFLOWS.vi.md, docs/VOICE_CLONING.vi.md.

## Implemented / verified
Foundation, safe URL imports, immutable media, stable subtitle IDs, Unicode/RTL editing/autosave/undo/export; projects edit/recoverable trash/library; single-source MP4; cached preset/reference VieNeu narration and per-character voices. Prior reference-cloning smoke used permitted synthetic voice, not human similarity evaluation.
Auto baseline: disclosure/consent, capability checks, source-track priority/ASR fallback, multiple target languages, durable child jobs, cancel/retry/checkpoint/invalidation, actual sub exports. ASR overlap and raw_cues archive. Frame sampling and evidence-linked editable summary/review/description drafts, Markdown/JSON. Approved scripts→existing TTS→measured new review timeline and WAV/MP4; source timing remains separate; proper review preview, no source-render misuse. Smaller blurred chrome, clearer light labels/timeline, common edit SVG and workspace navigation.
Tests:45 backend tests passed, frontend build and extended Playwright passed; later rechecks recorded in STATUS. Fixture AI is only protocol/timing proof. Live Qwen translation/sub exports and LLaVA frame+transcript→Qwen timecoded summary passed using generated media, reproducible scripts/check_ai_live.py. Live VieNeu review segments5280ms/3280ms→8560ms MP4 passed, test-results artifacts ignored by Git. LLaVA random color probes sometimes fail; no general accuracy promise.

## Current environment / prerequisites
Open http://127.0.0.1:3600; API6060; start scripts/start.ps1, stop scripts/stop.ps1. Before restart check jobs queued/running and preserve them. Stop only workspace-recorded launcher; no other service restarts. Local Ollama11434 now running, discovered qwen2.5:7b, llava:latest, nomic-embed-text:latest. Production LLM fixed from erroneous VieNeu to Qwen local, prior provider refs backed up under ignored data; TTS retained VieNeu8001/vieneu-v3-turbo; Vision LLaVA added only if absent. No model downloads. ASR not ready: current selected nomic-embed-text:latest is embedding-only and now blocked by role validation; faster-whisper absent; do not claim real ASR verification.

## Limits / next work
A works as baseline after source import; analysis/review stops for draft approval and TTS continuation is explicit. B frame-based/grouped baseline; no native-video or hierarchical whole-video reduction. C reference cloning/narration baseline, no automatic music/multispeaker detection, diarization, word alignment/background mixing. D first-evidence-scene/freeze-tail640x360/25fps review baseline, separate subtitles; no scene reorder UI or review burn-in. Remaining: real ASR, separate LLM proofreading, hierarchical summaries, scene editing, full one-run Auto→video, exhaustive failure/restart/long/disk QA. Finish latest checks/docs and push appropriate feature branch; never label complete spec.

## Preserve concurrent changes
README.md, README.vi.md modified; docs/RUNNING.en.md and docs/RUNNING.vi.md untracked at turn start. Do not overwrite these unrelated edits; concurrent commit b076138 has now included them. Existing branch feat/vieneu-reference-dubbing at bd87f5b before Auto work. Concurrent commit b076138 already pushed the shared implementation and README/RUNNING edits during this turn; preserve it. Remaining changes are hardening/docs. Original brand assets and third-party skills untouched.

## Commands
uv run pytest -q
npm run build --prefix frontend
uv run python scripts/check_e2e.py (requires3600/6060 free; isolated fixture data)
uv run python scripts/check_ai_live.py --llm-model qwen2.5:7b --vision-model llava:latest
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
