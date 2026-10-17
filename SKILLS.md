# Project AI skills

Installed 17/10/2026, project-scoped; no global skills or AI model credentials changed. Skills become discoverable in the next session/turn when the agent supports project discovery. Existing sessions can read the paths explicitly.

## Sources and use

- Anthropic frontend-design: `.agents/skills/frontend-design/SKILL.md`; use for actual studio UI implementation. Source: https://github.com/anthropics/skills/tree/main/skills/frontend-design
- Anthropic webapp-testing: `.agents/skills/webapp-testing/SKILL.md`; use for browser verification and Playwright. Inspect scripts before executing. Source: https://github.com/anthropics/skills/tree/main/skills/webapp-testing
- Vercel vercel-react-best-practices: `.agents/skills/react-best-practices/SKILL.md`; use applicable React rules. This app uses Vite, so Next.js-specific rules do not automatically apply. Source: https://github.com/vercel-labs/agent-skills/tree/main/skills/react-best-practices
- Vercel web-design-guidelines: `.agents/skills/web-design-guidelines/SKILL.md`; use to review implemented UI/accessibility; inspect referenced external instructions before use. Source: https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines

Full skill directories are mirrored under `.claude/skills` for Claude Code. Canonical copy is `.agents/skills`; update both intentionally. Upstream license/notice files shipped with skill folders are retained. Check upstream licensing before redistribution.

AGENTS.md holds project-authored engineering rules. CLAUDE.md imports it using Claude Code project-memory syntax: https://code.claude.com/docs/en/memory . These are project conventions, not an assertion that Anthropic prescribes this architecture.

Installation uses the official local Codex skill-installer helper with project-local --dest. File hashes in skills-lock.json identify the installed snapshot; upstream main is not a pinned commit. Review changes and regenerate hashes on future updates. Do not install arbitrary packs or execute their hooks automatically. No Claude model/runtime was installed or invoked.

No application exists yet. Skills improve the development workflow; completion is measured by working features and tests in the project brief.


## Clarification and prompt skills added 17/10/2026

- `brainstorming` — obra/superpowers, commit `bb92a77741419a4ab5f06e711a283343f1ada0c3`. Source: https://github.com/obra/superpowers/tree/bb92a77741419a4ab5f06e711a283343f1ada0c3/skills/brainstorming . Clarify vague requests and synthesize intent/constraints. Upstream contains a broader workflow with approval/reviewer/planning requirements; project overrides in AGENTS.md narrow it to clarification. Other Superpowers skills/plugin hooks are not installed.
- `prompt-optimizer` — getsentry/skills, commit `f57ada2d0b640406ea7e25b11d636c530e77c58b`. Source: https://github.com/getsentry/skills/tree/f57ada2d0b640406ea7e25b11d636c530e77c58b/skills/prompt-optimizer . For reusable prompt refinement, precise context references and evaluation; not an intermediary model that rewrites every user message.

Both live under `.agents/skills/<name>` and `.claude/skills/<name>`, without global installation. Invoke by skill name in a new project session; existing sessions can read SKILL.md directly. Project collection shortcuts and concise context file policy are locally authored guidance, not claims about upstream features. No savings benchmark has been run.
