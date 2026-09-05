# Contributing to PackSure AI

> Hackathon MVP — Internal developer workflow guide.

## Branches

| Branch | Owner | Purpose |
|---|---|---|
| `main` | Both | Stable, demo-ready code |
| `frontend-dev` | Developer 1 | All frontend work |
| `backend-dev` | Developer 2 | All backend + AI + OCR work |

## Workflow

```bash
# Developer 1 — Frontend
git checkout frontend-dev
git pull origin frontend-dev
# ... make changes ...
git add .
git commit -m "feat(frontend): describe your change"
git push origin frontend-dev

# Developer 2 — Backend
git checkout backend-dev
git pull origin backend-dev
# ... make changes ...
git add .
git commit -m "feat(backend): describe your change"
git push origin backend-dev

# Merging to main (both developers, when stable)
git checkout main
git pull origin main
git merge frontend-dev   # or backend-dev
git push origin main
```

## Rules

- **Do not commit directly to `main`** during active development.
- **Pull before starting work** to avoid conflicts.
- **Make small, focused commits** — one logical change per commit.
- **Use descriptive commit messages** (see format below).
- **Do not modify the other developer's area** unnecessarily.
- **Merge only tested code** to `main`.
- **Never commit secrets** — no `.env`, no API keys, no credentials.

## Commit Message Format

```
type(scope): short description

Optional longer description.
```

### Types
| Type | When to use |
|---|---|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no logic change |
| `refactor` | Code restructure, no new feature |
| `test` | Adding or updating tests |
| `chore` | Build, config, dependencies |

### Scopes
`frontend`, `backend`, `ocr`, `rules`, `ai`, `db`, `docs`, `ci`

### Examples
```
feat(frontend): add scan upload UI
feat(backend): add OCR endpoint placeholder
feat(rules): add declaration validator skeleton
fix(frontend): fix evidence viewer layout
docs: update architecture pipeline diagram
chore(backend): add requirements.txt
```

## File Ownership

| Developer | Files |
|---|---|
| Developer 1 | `frontend/` |
| Developer 2 | `backend/`, `database/` |
| Both | `docs/`, `research/`, `README.md`, root config |
