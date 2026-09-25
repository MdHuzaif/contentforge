# Development Rules

## The Golden Workflow (for ANY code change)

1. **PLAN** — AI creates `docs/change_plans/YYYY-MM-DD_name.md`
2. **REVIEW** — Human reviews the plan file, asks Claude to review
3. **APPROVE** — Human says "implement"
4. **IMPLEMENT** — AI applies the EXACT changes from the approved plan
5. **VERIFY** — Run tests + check production logs
6. **DOCUMENT** — Update `06_CHANGE_LOG.md` and `04_DECISION_LOG.md`

## Hard Rules

- NEVER apply code changes without an approved change plan.
- NEVER hardcode LLM quotas (e.g., "extract N products") — always dynamic.
- ALWAYS search for ALL occurrences of a pattern before fixing (e.g., target_count * 2 existed in main + retry + validation).
- ALWAYS include a rollback plan in every change plan.
- ALWAYS test on HuggingFace after push, not just locally.
- After every implementation, update `06_CHANGE_LOG.md`.

## Forbidden Patterns

- `target_count * 2` in any LLM prompt
- Committing `backend/memory/*.db` files (binary, HF rejects)
- Using `youtube-transcript-api` methods from v1.x (`get_transcript` removed)
- Forcing LLM to hit exact counts (causes hallucination)

## Git Rules

- Push to BOTH `origin` (GitHub) and `hf` (HuggingFace) after every change
- Use descriptive commit messages
- Never commit `.env`, `*.db`, `*.db-wal`, `*.db-shm` files
- Keep `.gitignore` updated for runtime files

## Commit Message Format
```
<type>: <short description>

Root cause: <why this was broken>

Fix:
- <change 1>
- <change 2>

Impact:
- Before: <old behavior>
- After: <new behavior>
```
Types: `fix`, `feat`, `docs`, `refactor`, `test`, `chore`
