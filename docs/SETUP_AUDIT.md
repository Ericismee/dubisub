# Setup audit — DubiSub

Checked 2026-10-17 on Windows. Root: D:/WorkSpace/dubisub.

## Verified tools and M1 runtime

- Product brief and milestones present; latest scope in PROJECT_BRIEF.vi.md section 12.
- AGENTS.md is shared policy; CLAUDE.md imports it; Cursor always-on rule points to it.
- Six skill entrypoints present in .agents/skills and mirrored in .claude/skills. All 100 recorded file hashes match; every mirror matches byte-for-byte. Scripts were not executed merely because a skill included them.
- System Python 3.11.9; Node v24.15.0; npm 11.12.1; uv 0.12.1; Git 2.54.0.windows.1 run successfully. uv selected Python 3.12.13 for project-local `.venv`; pinned in `.python-version`. No global Python packages were modified.
- FFmpeg and FFprobe N-126277-ga8c7afa7d7-20260826 run successfully. Actual libx264 encode, lavfi synthetic video, text-subtitle mux/extraction and probe passed. No GPU encoder benchmark is claimed.
- Bilingual README, local SVG banner, roadmap, status and new-chat prompt prepared. SVG XML parses; local Markdown file links checked.
- GitHub owner supplied by user: ericismee. Proposed repository: dubisub. Badges target ericismee/dubisub using actual GitHub metrics.
- .gitignore covers secrets, local media/models, databases, dependencies, build outputs and local Claude settings.

## Remaining setup / limitations

- Initial inspection found no Git repository. A concurrent setup later added `.git` and origin `https://github.com/Ericismee/dubisub.git`; preserved as found. This implementation turn did not initialize Git, change remotes, commit or publish. Remote authentication/availability was not tested.
- M1 now has app code, `.venv`, `uv.lock`, frontend lockfile, SQLite migrations v1/v2, durable worker, tests, local launcher and sample generator. No installer/release is available.
- Runtime versions pinned and exercised: FastAPI 0.128.8, Uvicorn 0.52.1, python-multipart 0.0.32, pysubs2 1.8.0, langcodes 3.5.0; React/React DOM 19.2.0, TypeScript 5.9.3, Vite 7.3.7. Test tools: pytest 8.4.2, httpx 0.28.1, Playwright 1.56.0. Full transitive versions in lockfiles. npm audit reports 0 vulnerabilities.
- ASR/LLM/TTS endpoints, keys, models and hardware capabilities have not been verified for this independent project. Previous hardware observations are not a fresh benchmark.
- GitHub star/fork/activity badges may show unavailable until the repository exists; no numeric metrics, CI status, release or coverage is invented.
- Application license is MIT, copyright (c) 2026 ericismee. Third-party license/notice closure must be completed before public redistribution; downloaded skill subfolders may not contain repository-level license files. See THIRD_PARTY_NOTICES.md.
- Original four skill snapshots have hashes but no recorded upstream commit; the two later skills are commit-pinned. Do not describe all six as commit-pinned.
- Local developer folders do not guarantee every agent automatically discovers skills in an existing session. Open a new project session or read SKILL.md explicitly.
- DubiSub is the official product name supplied by the user. Old Film Review Studio/VioraCut references were updated in project-owned documents; third-party skill content was left intact. No new name/trademark search was performed. Actual workspace is D:/WorkSpace/dubisub, not the old documented path.

## Prompt review

Target: portable implementation kickoff for Codex/Claude. Contract: read canonical context, execute M1, preserve user work, validate actual outputs, report limitations.

Static checks: all referenced local entrypoints exist; prompt retains both creative modes, multilingual targets, URL input, voice preview, worker reliability and real validation. It explicitly distinguishes planning from working software and avoids repeating the entire spec.

Cases reviewed: fresh project starts M1; missing provider does not block subtitle editing/export; settled requirements do not trigger a new brainstorming loop; later “gom ý tưởng” remains opt-in under AGENTS.md; README badges use the supplied owner. These are editorial/static checks, not model execution benchmarks. No token/quota savings are claimed.

## M1 verification result

8 pytest tests passed with actual FFmpeg fixtures; TypeScript/build passed; Playwright real flow passed using installed Microsoft Edge in headless mode and a temporary profile. Browser-bundled Chromium did not decode the H.264 fixture on this machine; Edge did. No personal browser profile/cookies were read. Playwright browser binaries were downloaded into its standard cache while diagnosing this.

Data for E2E is isolated in a temporary directory; test server processes are stopped afterward. Ports 3600 and 6060 were checked before launch. Screenshot artifacts are ignored under test-results. See STATUS.md for exact coverage and unverified areas.

Launch: `uv sync --locked`, `npm ci --prefix frontend`, `powershell -ExecutionPolicy Bypass -File scripts/start.ps1`; open http://127.0.0.1:3600. Environment variables are read from the process; `.env.example` is documentation and `.env` is not automatically loaded. Sample: `.venv/Scripts/python scripts/make_sample.py`.

Verdict: M1 local foundation baseline runs and has end-to-end evidence. AI providers, URL networking, video editing/rendering and production packaging remain future milestones.


## URL-import and studio update

yt-dlp 2026.8.19 is pinned in pyproject.toml/uv.lock. Its request-handler interface was inspected locally; all handlers are replaced by the DNS-pinned safe transport. No Node/remote JS solver, browser cookie or proxy integration was enabled. Manual YouTube sample jNQXAC9IVRw imported and probed successfully in temporary storage; automated tests use an explicitly injected local fixture policy. SQLite schema is now 3; connections close after transactions on Windows. Latest checks: 14 pytest tests, TypeScript/build and extended Edge E2E passed. UI is dark by default with separate settings groups and recoverable project deletion. See STATUS for unsupported source types and incomplete M2 areas.
