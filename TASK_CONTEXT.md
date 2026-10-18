# Active task context

## Objective and confirmed scope
Build DubiSub: independent multilingual video/subtitle translation and video editor, Vietnamese default, selectable review and full translation/dubbing modes. `PROJECT_BRIEF.vi.md` section 12 takes precedence. No new idea/approval loop; local implementation authorized, no publication or external messaging.

## Workspace and decisions
- Verified root: `D:/WorkSpace/dubisub`; old names Film Review Studio/VioraCut. Target `ericismee/dubisub`. Preserve existing MIT license, brand assets and user changes. Do not touch NotebookE or read its secrets.
- React/TypeScript/Vite; FastAPI; SQLite WAL/migrations; separate durable worker; FFmpeg/FFprobe. Python 3.12.13 selected locally by uv; dependencies pinned in `pyproject.toml`, `uv.lock`, `frontend/package.json`, `frontend/package-lock.json`.
- UI 3600/API 6060 loopback, start script refuses occupied ports. Data defaults to `./data`, environment variables referenced by `.env.example` (not auto-loaded).

## Current state and evidence
M1 local foundation runs: create/reopen, upload/probe, embedded text-sub extraction, subtitle edit/autosave/session undo-redo, native preview/seek and actual SRT/VTT downloads. Provider settings persist configuration only, capabilities unverified; no AI/key prerequisites for M1.

14 pytest tests passed with real FFmpeg fixtures; frontend type/build and npm audit (0 vulnerabilities) passed; Playwright/Edge real UI flow passed, including Unicode/RTL and reopen/export. Details and limitations: `docs/STATUS.md`; environment: `docs/SETUP_AUDIT.md`.

## Latest UI request
Studio redesign completed with persistent media/preview/subtitle/export/timeline panels, white/black/violet styling inspired by the supplied ELG Labs page and editor screenshots. Use original assets in `assets` directly; never redraw/overwrite them. Native SVG cursors applied, text caret retained. New `frontend/src/StudioParts.tsx` contains icons, real source timeline and clear unavailable-feature panels. Extended E2E passed. Preview aspect changes do not render video; AI/editing/render milestones remain unfinished.

## Latest completed work
- Project metadata edit and recoverable delete/restore; source media/cues retained, jobs canceled on delete.
- Default dark UI, persistent theme/cursor choices, dedicated settings modal with Appearance/ASR/Translation/TTS/Storage groups.
- M2 baseline URL import (YouTube and direct files), safe DNS-pinned transport for all extractor/download requests, worker progress/cancel/retry, subtitle selection and local audio/video merge. Schema v3. Live short YouTube sample inspect/download/probe succeeded; controlled HTTP video UI flow and backend policy tests passed.
- New entrypoints: `backend/safe_http.py`, `backend/link_sources.py`, `backend/link_tasks.py`, `frontend/src/LinkImport.tsx`, `frontend/src/ProjectDialog.tsx`, `frontend/src/SettingsDialog.tsx`, `tests/test_links.py`. Test-only network exception: `tests/url_fixture_worker.py`, no production switch.

## Next step
Finish M2 hardening/thumbnail UX and longer imports. Current YouTube support excludes DRM/auth/playlist/live/manifest/JS-challenge sources; direct servers need HEAD. Keep test fixtures isolated and never weaken production network policy. M3 provider capability verification/ASR/translation; M4 timeline; M5 voices/review/dubbing. No live AI capability is currently claimed. Full crash/long-media/disk-exhaustion and full accessibility QA remain unverified.

## Entry points
`backend/app.py`, `backend/store.py`, `backend/worker.py`, `backend/subtitles.py`, `frontend/src/main.tsx`, `scripts/start.ps1`, `scripts/check_e2e.py`, `tests/test_foundation.py`, `README.vi.md`.

Run: `uv sync --locked`; `npm ci --prefix frontend`; `powershell -ExecutionPolicy Bypass -File scripts/start.ps1`; open `http://127.0.0.1:3600`.


## Latest 2026-10-18
Implemented backend/providers.py, ai_tasks.py, workflows.py, rendering.py, voices.py plus WorkflowPanel/SubtitleTools/RenderPanel/VoicePanel. Durable ASR/translation with glossary, strict output validation/checkpoints; subtitle tools; single-source MP4 exports; real cached TTS samples; persistent trash. Ollama + OpenAI-compatible translation, 24-family suggestions separated from discovered installed tags. User requests >18 models like NotebookE; implementation is independent, no NotebookE access. Ollama CLI installed but port11434 unavailable; no model downloads. Live TTS one Vietnamese sample verified; LLM/ASR currently fixture-verified only. Full review/dubbing/multitrack still pending. See latest docs/STATUS.md. User authorizes commit/push to appropriate branch with no codex/ prefix.

Latest link repair: actual long YouTube job remains running; do not restart/cancel it to deploy changes. Added bounded signed-URL refresh, transfer statistics and estimated sizes. Live short YouTube download/merge/probe passed. API transfer fields activate on next normal restart.


Latest request: voice cloning from owned/permitted video/audio. Added backend/dubbing.py, frontend/src/DubbingPanel.tsx, tests/test_dubbing.py, docs/VOICE_CLONING.vi.md. VieNeu local8001 modelvieneu-v3-turbo verified real cloning with synthetic reference. Default TTS only; Ollama11434 unavailable and translation config currently incorrectly names VieNeu, now gets actionable role-specific error. Local extraction no media transfer; inference requires explicit UI provider/data consent. VieNeu RAM embedding has no DELETE; disclosed retention, local derived deletion supported. Preserve concurrent README/RUNNING documentation edits. 33 backend tests, frontend build and extended cloning UI/E2E passed, including assignment restore after reopening the tool. Consent bound to provider fingerprint; different character voice IDs tested. Real VieNeu cloning smoke passed separately; no human similarity claim.
