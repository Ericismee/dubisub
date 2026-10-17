# GitHub AI assistant — Intern Discovery

The runner is Claude Code; the configured model is `deepseek-v4-flash-vision` served by `https://discovery-api.intern-ai.org.cn`. This is not an Anthropic model or proof of official provider support.

## Configuration

- Workflow: `.github/workflows/ai-assistant.yml`.
- Repository secret: `INTERN_DISCOVERY_TOKEN`. Stored through GitHub Secrets; never commit the value.
- GitHub authentication: Claude GitHub App token acquired through GitHub OIDC (`id-token: write`). No explicit `github_token` override is passed. The official Claude App must be installed for this repository; comments use the app identity. Intern Discovery remains the model provider.
- API auth includes the existing provider bearer token and API-key input required by the action. Both point to the same repository secret. Do not replace the endpoint with api.anthropic.com while using this provider token.
- Action and checkout are pinned to audited upstream commit IDs. Inspect release changes before updating.

## Use

Merge the setup PR to main. Open Actions → DubiSub AI assistant → Run workflow to test provider integration without posting messages or changing files. Then mention `@claude` in an issue or PR conversation comment, for example `@claude review the changes proposed in this PR; do not edit code`.

Only OWNER/MEMBER/COLLABORATOR comments trigger the workflow. Review-thread comments are not configured. The trusted main branch is checked out; PR changes should be inspected using GitHub tools, not automatically executed from a fork. Runs have an 8-turn and 10-minute limit; limits are not a billing guarantee. Disable the workflow in Actions to stop it.

The bot can respond and, when requested, modify code using permitted tools. It must follow AGENTS.md. The app token has repository-scoped permissions; app-authenticated pushes may trigger other workflows. Branch protection remains in force. Do not enable approval or bypass protections merely for this bot.

## Limits and troubleshooting

Local API compatibility is tested separately from GitHub execution. The gateway may reject requests from GitHub-hosted runner IPs or particular Claude Code API/tool features. Inspect sanitized HTTP status/model/tool errors; do not publish tokens. A successful simple API request does not prove the full agent works.

401/403: check token validity, quota and provider access. 404/model errors: verify provider model ID. GitHub permission errors: check Actions permissions. Expired token: update INTERN_DISCOVERY_TOKEN in repository secrets. Test again after changing providers or model IDs. Code and requested context are sent to Intern Discovery during runs.
