---
description: Reference when creating PRs, writing commits, or naming branches.
globs:
  - ".github/PULL_REQUEST_TEMPLATE.md"
  - ".github/**/*.md"
  - ".gitmessage.txt"
alwaysApply: false
---

# Contribution guide

This file is the agent-facing quick reference; `CONTRIBUTING.md` at the repo root is the authoritative document for human readers.

## Tags

| Tag | Meaning |
|---|---|
| `FEAT` | A new feature |
| `FIX` | A bug fix |
| `DOCS` | Documentation only changes |
| `STYLE` | Code style changes (formatting, etc.) |
| `REFACTOR` | Code refactoring without behavior change |
| `PERF` | Performance improvement |
| `TEST` | Add or correct tests |
| `BUILD` | Build system or external dependency changes |
| `CI` | CI configuration or script changes |
| `CHORE` | Other changes that don't modify src or test files |
| `REVERT` | Revert a previous commit |
| `HOTFIX` | Urgent bug fix |
| `BOT` | Automation |

## Branch naming

- Format: `<TAG>-<description>` — `<TAG>` UPPER_CASE from the list above, `<description>` lowercase kebab-case.
- Examples: `FEAT-takeout-import`, `FIX-year-end-hours-merge`, `DOCS-update-rules`.
- Create a branch before committing; do not commit directly to `main`. Commit only when the user asks.

## Commit messages

### Subject

`[TAG] <summary>` — English, 50 characters max, imperative mood, no trailing period. Template: `.gitmessage.txt`.

### Body

- Blank line between subject and body.
- Explain **what** and **why**, not how.
- Imperative ("Add trade parser", not "Added trade parser").
- Never include personal data (trip dates, companions, bookings, home location).
- Keep the `Co-Authored-By:` and session trailers required by the harness.

## PR title

`[TAG] <body>` — body is English, 1–150 characters, alphanumeric plus `` _-.,&*[]:/`<>=#+ ``, exactly one space after the tag. Validated by `pr-title-checker.yml`; `WIP:` titles skip it.

Examples: `[FEAT] Add Takeout saved-list import with place_id resolution`, `[FIX] Treat 12-31 as inside a wrapping holiday period`.

## PR body

`.github/PULL_REQUEST_TEMPLATE.md` is auto-applied. Fill in: PR type, summary, milestone, detailed description (what / why / impact area), test plan (exact commands and results), reviewer checklist.

## PR checklist

- [ ] `make lint` and `make test` pass
- [ ] Type hints and Google-style docstrings on new public Python APIs
- [ ] New behavior covered by tests (fixtures for external APIs, no real network)
- [ ] `make gen-types` output committed when API schemas changed
- [ ] No personal data in code, fixtures, or commit messages
- [ ] No hardcoded opening hours, holidays, prices or free-tier caps (config or cited research only)
- [ ] Google data stored, cached, sent to the LLM and shown only as `docs/google-terms.md` allows
- [ ] README / CLAUDE.md / `.claude/rules/` updated when relevant

## Review criteria

- **Correctness of units**: money as integer `amount` + ISO 4217 `currency`, durations in integer minutes, timezone-aware datetimes.
- **Honesty of output**: approximate travel times, AI research and unconfirmed opening hours are labeled as such.
- **Privacy**: nothing personal leaks into tracked files.
- **Type safety**: every public API has type hints.
- **Consistency**: naming and structure match existing modules.
