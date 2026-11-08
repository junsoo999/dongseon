---
description: Reference when changing build or test setup, or when running validation commands. Covers uv, pnpm, Make, and pre-commit usage.
globs:
  - "Makefile"
  - "pyproject.toml"
  - "scripts/**"
  - "tests/**"
  - "frontend/package.json"
alwaysApply: false
---

# Build and test guide

## Stack

- **Python**: 3.12 (`.python-version`), single uv project at the repo root
- **Package manager**: [uv](https://github.com/astral-sh/uv) (Python), pnpm (frontend)
- **Linter / formatter**: Ruff (Python), oxlint + Prettier (frontend)
- **Type checker**: pyright (Python), `tsc -b` (frontend, TypeScript 7)
- **Tests**: pytest under `tests/unit_test/`, Vitest under `frontend/src/**/*.test.ts(x)`

## uv environment rules (required)

### Do not

- Do not use `pip install` — use `uv add` (declared dependency) or `uv pip install` (ad hoc).
- Do not run `source .venv/bin/activate` — uv manages the environment.
- Do not invoke `python` directly — use `uv run --no-sync python`.
- Do not invoke `pytest` directly — use `uv run --no-sync pytest`.
- Do not create a second Python project (e.g. `backend/pyproject.toml`); there is one uv project at the root.

### Do

- `uv sync` — sync dependencies from `pyproject.toml` / `uv.lock`.
- `uv add <pkg>` / `uv add --dev <pkg>` — add a runtime / dev dependency.
- `uv run --no-sync dongseon <command>` — run the CLI.
- `uv run --no-sync pre-commit run --all-files` — run all hooks.
- `uv lock --upgrade` — refresh the lockfile.

### Frontend

- Use `pnpm --dir frontend <script>` from the repo root (or `pnpm <script>` inside `frontend/`).
- Do not use npm or yarn for project dependencies.

## Installation

```bash
make install                       # uv sync + pre-commit install + pnpm install + copy .env / profile.yaml if missing
make install PYTHON_VERSION=3.13   # alternative Python version (3.12 | 3.13)
```

## Common Make targets

```bash
make help                          # list available targets
make dev                           # dev backend 127.0.0.1:8101 (reload) + frontend :5174 (LAN); 8100 = always-on app
make backend / make frontend       # run one side only
make lint                          # uv run --no-sync pre-commit run --all-files
make fmt                           # ruff fix + format, prettier --write
make test                          # backend + frontend tests
make test TEST_MODE=backend        # pytest only (TEST_MODE=all|backend|frontend)
make test COVERAGE=1               # pytest with coverage report
make gen-types                     # OpenAPI -> frontend/src/api/schema.d.ts
make db-upgrade                    # apply Alembic migrations
make usage                         # Google calls per SKU this month vs free caps
make serve [HOST=127.0.0.1] [PORT=8100]  # build frontend, serve SPA + /api on one port
make clean                         # remove caches and build artifacts
```

Ports are chosen so jipsa (8000 / 8001 / 5173) and dongseon (8100 / 8101 / 5174) run side by side.

When adding a frequently used command (e.g. an ingest job), register it as a Make target and in `make help`.

## Validation commands

```bash
# All hooks
uv run --no-sync pre-commit run --all-files

# Diff only (mirrors CI on PRs)
uv run --no-sync pre-commit run --from-ref=origin/main --to-ref=HEAD

# Individual tools
uv run --no-sync ruff format .
uv run --no-sync ruff check . --fix
uv run --no-sync pyright
pnpm --dir frontend lint
pnpm --dir frontend typecheck
```

Note: `pre-commit run --all-files` only sees files tracked or staged in git. For brand-new untracked files use `--files <paths>`.

## CLI smoke tests

```bash
uv run --no-sync dongseon --help
uv run --no-sync dongseon info
uv run --no-sync dongseon openapi | head
uv run --no-sync dongseon usage
uv run --no-sync dongseon trip create --city tokyo --start 2030-12-28 --end 2031-01-01 --title "테스트"
uv run --no-sync dongseon trip list
uv run --no-sync dongseon places resolve [--trip <id>] [--retry-failed]
uv run --no-sync dongseon scout [--trip <id>] [--only place|stay] [--force]   # AI research (minutes; uses Claude Code)
uv run --no-sync dongseon review [--itinerary <id>] [--rain YYYY-MM-DD] [--force]  # AI plan review / rain plan (~1 min)
uv run --no-sync dongseon hours-research [--trip <id>] [--force]   # holiday opening hours (minutes, web)
uv run --no-sync dongseon area-notes [--trip <id>] [--force]       # stay area notes (minutes, web)
uv run --no-sync dongseon weather [--trip <id>]                    # Open-Meteo forecast / climate for trip dates
uv run --no-sync dongseon hours-refresh [--trip <id>]              # from D-7: re-check the plan with Google hours
uv run --no-sync dongseon rain-plans [--trip <id>]                 # AI rain plan for each rainy forecast date
```

## Daily job, always-on app, remote access (M5)

- `dongseon daily` (launchd `com.dongseon.daily`) runs prices, scout, weather, then the trip-window steps
  (`hours-refresh` from D-7, `hours-research --window` and `rain-plans` from D-14 until the trip ends). Each step runs
  as its own CLI process, checks its own window and keeps going when another one fails.
- `dongseon serve` runs always-on as `com.dongseon.serve` on `127.0.0.1:8100`.
- Remote access: everything outside `127.0.0.1:8100` (Cloudflare Tunnel, basic auth, routing by hostname) lives in a
  separate shared edge repo used by all self-hosted apps. Do not add proxy, tunnel or auth config here; the domain and
  credentials are kept there.
- Add the app's https origin to the Google browser key's HTTP referrer restriction, and keep the edge's default
  `Referrer-Policy` (the key checks the Referer).

## Database migrations

- Models live in `dongseon/db/models.py`; migrations in `alembic/versions/` (SQLite batch mode).
- After changing models: `uv run --no-sync alembic revision --autogenerate -m "<what>"`, review the file, then `make db-upgrade`.
- CLI jobs run `upgrade_schema()` automatically before writing.
- Tests get a fresh migrated DB from the `engine` fixture in `tests/unit_test/conftest.py`.

## Tests

- Python: `tests/unit_test/`, configured in `[tool.pytest.ini_options]`. Warnings are errors.
- Never call real external APIs in tests — mock httpx with `respx` and load responses from `tests/unit_test/fixtures/`.
- Use `config/profile.example.yaml` (fake values) in tests, never the real profile.
- Frontend: colocate `*.test.ts(x)` next to the code; mock `fetch` with `vi.stubGlobal`.

```bash
uv run --no-sync pytest                                   # whole suite
uv run --no-sync pytest tests/unit_test/test_health.py    # single file
uv run --no-sync pytest -k health                         # by keyword
pnpm --dir frontend test
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `openapi-typescript` crashes with `createKeywordTypeNode` undefined | It needs the TypeScript 5 JS API; TS 7 has none. `pnpm gen-types` runs it via `pnpm dlx` with `typescript@5.9.3` — keep it out of project dependencies. |
| pytest warns about `httpx2` | Starlette's TestClient recommends it; the warning is filtered in `pyproject.toml`. Ask before adopting `httpx2`. |
| `pre-commit run --all-files` checks nothing | Files are untracked. Stage them or pass `--files`. |
| Backend uses a different DB than expected | Relative paths in settings resolve from the repo root (`dongseon.core.config.resolve_repo_path`); check `DATABASE_PATH` in `.env`. |
| Google map does not load | The browser key's HTTP referrer restriction must list the exact origin (`http://localhost:5174/*`, the remote domain). Advanced Markers also need `VITE_GOOGLE_MAP_ID`. |
| A job says another job is running | A lock in `data/locks/` is held by a live process (locks release automatically when a process dies). |
| Port still in use after `make dev` | uvicorn's reloader can outlive the parent; `lsof -tiTCP:8101 -sTCP:LISTEN \| xargs kill`. If 8100 is taken by anything but launchd, the always-on app restarts in a loop (`data/logs/serve.log`: "address already in use"). |
| A Google call fails with `FreeTierExceededError` | The SKU reached `GOOGLE_FREE_TIER_STOP_RATIO` of its cap in `config/defaults.yaml` this billing month (Pacific time). Check `make usage`; raise the ratio only deliberately. |
