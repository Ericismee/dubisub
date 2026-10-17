<div align="center">

<img src="assets/banner.svg" alt="DubiSub — Translate. Dub. Create." width="100%" />

# DubiSub

**A local-first studio for multilingual video translation, subtitles, AI dubbing, and editing.**

🇻🇳 Vietnamese by default · 🌍 Built for many languages · 🎬 Your creative workflow

[![Stars](https://img.shields.io/github/stars/ericismee/dubisub?style=for-the-badge&logo=github&color=fbbf24)](https://github.com/ericismee/dubisub/stargazers)
[![Forks](https://img.shields.io/github/forks/ericismee/dubisub?style=for-the-badge&logo=github&color=8b5cf6)](https://github.com/ericismee/dubisub/forks)
[![License: MIT](https://img.shields.io/badge/License-MIT-557D61?style=for-the-badge)](LICENSE)
![Stage](https://img.shields.io/badge/stage-planning-f59e0b?style=for-the-badge)
![Platform](https://img.shields.io/badge/target-Windows-38bdf8?style=for-the-badge)

[Why DubiSub](#-why-dubisub) · [Roadmap](#-roadmap) · [Development](#-development) · [Tiếng Việt](README.vi.md)

</div>

> **Project status: planning / pre-implementation.** This repository currently contains the product specification, agent guidance, and development skills. The application, installer, demo, and release are not available yet. Star/fork badges query GitHub and become meaningful after `ericismee/dubisub` is published; no counts are fabricated.

## ✨ Why DubiSub

One workspace to take a video from its original language to a new audience: import, transcribe, translate, refine, voice, edit, and export.

The planned experience combines precise subtitle work with a general video timeline. Vietnamese is the default translation target; language availability depends on the configured ASR, translation, and voice providers. Film reviews and full-length dubbing are selectable workflows.

## 🧭 Planned workflow

**📥 Import → 📝 Transcribe → 🌍 Translate → 🎙️ Voice → ✂️ Edit → 📤 Export**

- 📥 **Files or links:** inspect video/audio/subtitle tracks, choose quality, download supported sources or import subtitles only.
- 🌍 **Multilingual subtitles:** side-by-side editing, glossary, speaker names, multiple target languages, timing validation, and versioned translations.
- 🎙️ **Voice selection:** VieNeu for Vietnamese, provider-supported voices for other languages, language/gender filters, and cached audio samples.
- ✂️ **Video editing:** multiple tracks, trim/split/ripple, proxy preview, waveform, text, overlays, transitions, keyframes, and audio mixing.
- 🎬 **Two creative modes:** film review with a new script/timeline, or translation/narration/dubbing aligned to the original video.
- 📤 **Flexible outputs:** SRT/VTT/ASS, narration audio, subtitled video, and dubbed video. Export subtitles without waiting for a video render.
- 💾 **Resilient work:** autosave, undo/redo, durable background jobs, cancellation, retry, and segment checkpoints.

All items above are planned. Completed behavior will be tracked in [STATUS](docs/STATUS.md).

## 🗺️ Roadmap

- [x] Product brief and acceptance criteria
- [x] Shared Codex / Claude / Cursor project guidance
- [x] Project-scoped development skills and hash audit
- [ ] **M1 — Foundation:** project library, upload/probe, subtitle editor, real subtitle export
- [ ] **M2 — Link import:** supported URLs, quality/track selection, bounded download jobs
- [ ] **M3 — Translation:** ASR fallback, glossary, multiple target languages, automation presets
- [ ] **M4 — Editing core:** multitrack timeline, trim/split/ripple, preview and render
- [ ] **M5 — Voice & review:** voice samples, speaker mapping, dubbing alignment, review export
- [ ] **M6 — Editing polish:** titles, overlays, transitions, keyframes, color/audio controls
- [ ] **M7 — Advanced tools:** OCR, diarization, stems, stabilization, and tracking as validated

## 🏗️ Proposed architecture

- **UI:** React + TypeScript + Vite
- **API:** async FastAPI / Python
- **Storage:** SQLite migrations and local media files
- **Jobs:** a separate durable worker with checkpoints
- **Media:** FFmpeg / FFprobe; yt-dlp adapter for supported links
- **AI:** configurable ASR, translation, and TTS adapters

Local-first means local project/media storage. Selecting a remote AI provider sends the required content to that provider; fully offline operation depends on installing compatible local models.

## 🛠️ Development

There is no application start command yet. Do not expect `npm install` or a release download to launch a studio at this stage.

1. Open the project directory in your coding agent.
2. Read [AGENTS.md](AGENTS.md), [the brief](PROJECT_BRIEF.vi.md), and [current status](docs/STATUS.md).
3. Use [NEW_CHAT_PROMPT.md](NEW_CHAT_PROMPT.md) to begin milestone 1.
4. Consult [SETUP_AUDIT.md](docs/SETUP_AUDIT.md) for verified tools and remaining setup.

The proposed development ports are UI `3600` and API `6060`, configurable and checked before launch. DubiSub is independent of NotebookE.

## 🤝 Contributing

Start with the brief and roadmap. Include a concrete use case, expected behavior, and validation evidence with proposed changes. Keep original media immutable and credentials out of Git. Use media you are authorized to process; protected/unsupported sources must fail clearly.

## 📊 Repository activity

GitHub-backed metrics below reflect the published repository, not application usage or benchmark performance.

[![Issues](https://img.shields.io/github/issues/ericismee/dubisub?logo=github)](https://github.com/ericismee/dubisub/issues)
[![Pull requests](https://img.shields.io/github/issues-pr/ericismee/dubisub?logo=github)](https://github.com/ericismee/dubisub/pulls)
[![Last commit](https://img.shields.io/github/last-commit/ericismee/dubisub?logo=git)](https://github.com/ericismee/dubisub/commits)
[![Repo size](https://img.shields.io/github/repo-size/ericismee/dubisub?logo=github)](https://github.com/ericismee/dubisub)

## 🙌 Acknowledgements & licensing

Planned integrations include FFmpeg, yt-dlp, faster-whisper, and VieNeu. Project development skills come from Anthropic, Vercel, Superpowers, and Sentry; see [SKILLS.md](SKILLS.md) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

DubiSub original project code, documentation, and original SVG brand assets are licensed under the [MIT License](LICENSE). Copyright (c) 2026 ericismee. Third-party models, voices, fonts, media tools, and included skills retain their own terms; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

---

<div align="center">If this direction would help your workflow, a ⭐ helps others discover DubiSub.</div>
