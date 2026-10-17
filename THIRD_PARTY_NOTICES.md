# Third-party material

Development skill snapshots are included under `.agents/skills` and mirrored under `.claude/skills`:

- anthropics/skills: frontend-design and webapp-testing
- vercel-labs/agent-skills: react-best-practices and web-design-guidelines
- obra/superpowers: brainstorming
- getsentry/skills: prompt-optimizer

See SKILLS.md for source URLs and skills-lock.json for file hashes and pinned commits where recorded. Preserve included notices. Inclusion here does not replace or relicense upstream terms. Before public redistribution, verify the license covering each snapshot and add any required repository-level license/notice files not included in downloaded subdirectories.

M1 invokes the separately installed FFmpeg/FFprobe (N-126277-ga8c7afa7d7-20260826 on the checked machine); these binaries are not bundled. Python dependencies are pinned in pyproject.toml/uv.lock; frontend dependencies are pinned in frontend/package.json and package-lock.json. Preserve their upstream license notices on redistribution. yt-dlp, ASR/TTS models and voice assets remain planned integrations. No font files or model weights are bundled. FFmpeg distribution requires review of the actual build configuration (the checked machine uses a GPL-enabled build).

## DubiSub branding and project license

Original project code, documentation, and SVG brand assets are covered by the root MIT LICENSE, copyright (c) 2026 ericismee. This does not relicense third-party material. The custom logo combines a geometric D with a speech/caption shape; no third-party logo asset is included. SVG text references system font fallbacks (Trebuchet MS, Century Gothic, Arial); font files are not bundled. No trademark registration or exclusive-name claim is made.
