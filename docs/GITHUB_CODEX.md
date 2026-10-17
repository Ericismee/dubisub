# Codex on GitHub

## Chosen integration

Use the official Codex GitHub integration for native `@codex review` behavior and the Codex connector identity. This is separate from `.github/workflows/ai-assistant.yml`, which runs Claude Code with DeepSeek through Intern Discovery. No OpenAI API key or ChatGPT login token has been copied to GitHub.

## One-time account connection (account owner)

1. Open https://chatgpt.com/settings/code-review while signed into the ChatGPT account that should supply Codex access.
2. Connect GitHub if requested and grant access to `Ericismee/dubisub`. Complete GitHub authorization yourself; do not share passwords, API keys or OAuth tokens in chat.
3. Select the repository and enable Code Review. Leave automatic reviews off initially if you want explicit, on-demand usage only. Eligibility and quota depend on the connected account; being logged into GitHub CLI does not enable this integration.
4. Return to a suitable open PR and comment `@codex review`. Expect a reaction and then a review by the Codex connector. AGENTS.md contains project-specific review rules.
5. Only after a successful review, optionally enable automatic reviews in repository/personal preferences. Explicitly request fixes with `@codex fix the P1 issue` if you want code changes; review itself should remain read-only.

## Status and validation

Repository-side review guidance and this setup guide are prepared. Account connection, repository authorization, quota eligibility, and a live Codex review are not verified by this configuration commit. Do not claim Codex is active until a real connector response appears. No external trigger comment is posted automatically.

If no response appears, confirm repository access and Code Review settings and use the exact `@codex review` trigger in a PR comment. A normal `github-actions[bot]` comment does not prove native Codex integration. Do not use Intern Discovery keys as OpenAI keys or upload the desktop session's auth.json to CI.

## Alternative: Codex GitHub Action

The official `openai/codex-action` is available when an API-backed CI workflow is desired. It needs separate provider/API authentication and does not inherently create the native Codex connector identity. The repository currently has no OPENAI_API_KEY secret, so an unconfigured second workflow has not been added.

Sources checked 2026-10-17:
- https://learn.chatgpt.com/docs/third-party/github
- https://learn.chatgpt.com/docs/github-action
