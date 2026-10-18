# Contributing to DubiSub

## Before changing code

Read AGENTS.md, docs/STATUS.md and the relevant section of PROJECT_BRIEF.vi.md. Confirm current behavior in code rather than assuming a roadmap item is implemented. Keep changes focused; preserve local work and original media. Never commit API keys, cookies, user uploads or generated media.

## Validation

Use the project lockfiles and development instructions. For backend changes, run relevant pytest cases; for frontend changes, run TypeScript/Vite build and exercise affected browser flows. Media changes need real FFmpeg fixtures and timing checks. Provider fixtures verify contracts, not model quality; report live-provider validation separately. Include exact commands, outcomes and remaining limits in the PR.

## Commit attribution

Record who actually produced each change. Keep human authors and reviewers credited. AI attribution is allowed when that tool materially authored the committed content; do not add AI identities to unrelated changes or rewrite historical commits merely to change the Contributors display.

A Git trailer is separated from the message body by a blank line:

```text
docs: explain subtitle validation

Co-authored-by: Name <verified-address>
```

Replace the example with the actual contributor identity. Verify the address through the contributor's official tooling or account; do not guess an email or reuse another person's identity. Preserve attribution when merging. A squash merge creates a new commit: inspect its author and trailers before confirming. Avoid adding the same identity as both author and co-author unnecessarily.

Claude Code is a client, not proof that the Claude model authored a change. When configured with DeepSeek, describe that assistance honestly; do not credit the official Claude account solely because of the client name. Codex reviews/comments alone are not proof that Codex authored a code commit.

## Contributors visibility

Commit metadata, PR author, bot comment identity, profile contributions and the repository Contributors list are different views. A tool's GitHub App installation or a review does not automatically add its avatar to Contributors. GitHub determines account linkage and the displayed list; even correct attribution does not guarantee immediate sidebar display. A commit on a feature branch alone is not evidence it has been included on the default branch.

## Pull requests

Describe the concrete problem, final behavior and validation. Link relevant issues, keep secrets out of logs and screenshots, and distinguish completed behavior from plans. Follow existing branch protection and reviews. Do not trigger other AI bots or automatic review loops without a human request.
