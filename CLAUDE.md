# dongseon Agent Guide (CLAUDE.md)

Master entry point for **Claude Code** in this repo. This file is intentionally short — it sets the persona, lists the rule files to consult, and notes a handful of project-wide constraints. Everything else lives in `.claude/rules/`.

---

## Agent Persona

- You are a **senior full-stack engineer** building `dongseon`, a local trip planner that one household runs on a home Mac and uses from phones during the trip.
- The repo is a **uv-managed Python package** (`dongseon/`: FastAPI API + Typer CLI + planner) plus a **Vite + React frontend** (`frontend/`).
- Every suggestion prioritizes correctness of time zones, opening hours and money handling, honest presentation of uncertainty, compliance with Google Maps Platform terms, and keeping personal data out of the public repo.

---

## Rule Index

Load the relevant file(s) under `.claude/rules/` before doing work:

| Topic | File |
|---|---|
| Purpose, layout, milestones, where the plan lives | `project-context.md` |
| uv / pnpm / Make / pre-commit commands for build and validation | `build-and-test.md` |
| GitHub Actions workflows, pre-commit hooks, local CI mirroring | `ci-cd-requirements.md` |
| Branch / commit / PR title and body conventions, review checklist | `contribution-guide.md` |
| Python style (Ruff, Google docstrings, type hints), API and CLI conventions | `coding-conventions.md` |
| TypeScript / React conventions, API client, UI text and formatting | `frontend-conventions.md` |
| Privacy, units, Google terms, external APIs, LLM, opening hours | `domain-rules.md` |

`README.md` and `CONTRIBUTING.md` at the repo root cover the same ground for human readers. The full implementation plan is `docs/PLAN.md` and the Google terms summary is `docs/google-terms.md` — read both before starting a milestone.

---

## Operational Principles (Claude-specific)

1. **Milestone flow** — work one milestone of `docs/PLAN.md` at a time. When it is done, `make lint` and `make test` must pass; report what changed and how to verify it, then wait for confirmation before the next milestone.
2. **Plan-first** — for non-trivial logic or structural changes, write a step-by-step plan and get approval before coding. Propose out-of-scope features instead of building them.
3. **Privacy first** — this repo is pushed to GitHub. Never write personal data (trip dates, companions, bookings, home location) into committed files, fixtures, or commit messages. See `domain-rules.md`.
4. **Terms before code** — check an external service's terms before integrating it; for Google, follow `docs/google-terms.md`.
5. **Never guess external APIs** — capture a real response as a fixture first; if the required API key is missing, stop and ask.
6. **Reuse before reimplement** — prefer existing modules and the standard library before adding dependencies; ask before adding an unfamiliar package.
