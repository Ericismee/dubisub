# Setup audit — DubiSub

Checked 2026-10-17 on Windows. Root: D:/WorkSpace/dubisub.

## Ready for development

- Product brief and milestones present; latest scope in PROJECT_BRIEF.vi.md section 12.
- AGENTS.md is shared policy; CLAUDE.md imports it; Cursor always-on rule points to it.
- Six skill entrypoints present in .agents/skills and mirrored in .claude/skills. All 100 recorded file hashes match; every mirror matches byte-for-byte. Scripts were not executed merely because a skill included them.
- Python 3.11.9; Node v24.15.0; npm 11.12.1; uv 0.12.1; Git 2.54.0.windows.1 run successfully.
- FFmpeg and FFprobe N-126277-ga8c7afa7d7 run successfully. Specific encoder/filter availability remains to be tested during implementation.
- Bilingual README, local SVG banner, roadmap, status and new-chat prompt prepared. SVG XML parses; local Markdown file links checked.
- GitHub owner supplied by user: ericismee. Proposed repository: dubisub. Badges target ericismee/dubisub using actual GitHub metrics.
- .gitignore covers secrets, local media/models, databases, dependencies, build outputs and local Claude settings.

## Remaining setup / limitations

- No Git repository, remote creation or publication performed. Repo availability under the supplied account is not authenticated/verified. GitHub CLI was not found on PATH during this check; it is optional.
- No app code, dependency lockfiles, virtual environment, migrations, worker, tests or installer exist yet. These belong to M1 and subsequent milestones.
- Runtime dependency versions and Node/Python compatibility need to be pinned and tested against the implemented stack.
- ASR/LLM/TTS endpoints, keys, models and hardware capabilities have not been verified for this independent project. Previous hardware observations are not a fresh benchmark.
- GitHub star/fork/activity badges may show unavailable until the repository exists; no numeric metrics, CI status, release or coverage is invented.
- Application license is MIT, copyright (c) 2026 ericismee. Third-party license/notice closure must be completed before public redistribution; downloaded skill subfolders may not contain repository-level license files. See THIRD_PARTY_NOTICES.md.
- Original four skill snapshots have hashes but no recorded upstream commit; the two later skills are commit-pinned. Do not describe all six as commit-pinned.
- Local developer folders do not guarantee every agent automatically discovers skills in an existing session. Open a new project session or read SKILL.md explicitly.
- DubiSub is a chosen working product name. A preliminary exact-name web search found no result; no trademark clearance is claimed. Folder has not been renamed.

## Prompt review

Target: portable implementation kickoff for Codex/Claude. Contract: read canonical context, execute M1, preserve user work, validate actual outputs, report limitations.

Static checks: all referenced local entrypoints exist; prompt retains both creative modes, multilingual targets, URL input, voice preview, worker reliability and real validation. It explicitly distinguishes planning from working software and avoids repeating the entire spec.

Cases reviewed: fresh project starts M1; missing provider does not block subtitle editing/export; settled requirements do not trigger a new brainstorming loop; later “gom ý tưởng” remains opt-in under AGENTS.md; README badges use the supplied owner. These are editorial/static checks, not model execution benchmarks. No token/quota savings are claimed.

Verdict: planning and agent setup are ready to begin implementation. Application/runtime setup is not complete because implementation has not started.
