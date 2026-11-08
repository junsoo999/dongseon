---
description: Reference when you need the repo's overall purpose, layout, or milestone status. Read this first before adding features or refactoring.
alwaysApply: false
---

# Project context

## Overview

`dongseon` (동선) is a local trip planner for one household. It runs on a home Mac and is used from phones,
including during the trip. It answers:

1. How do we collect and organize the places we want to visit (pins)?
2. Which neighborhood is best to stay in given the pins, and how do candidate stays compare?
3. Which flight candidate gives the most usable local time for the total cost?
4. How do we plan each day's route while respecting opening hours, closures and travel times?
5. How do we adapt to rain, closures and holidays?
6. During the trip, can we see today's plan and open directions on a phone right away?

Non-goals: booking or payment, scraping booking sites, multi-user login (remote access uses one basic-auth login at the shared edge),
real-time price comparison, blog or review crawling.

## Source of truth

- `docs/PLAN.md` — the full implementation plan (sources, schema, API, screens, milestones). No personal data; committed.
- `docs/google-terms.md` — what Google Maps Platform terms allow us to store, cache, send to an LLM and display.
- `docs/travel-data-sources.md` — which flight and hotel data services a personal app may use (terms, price).
- `config/profile.yaml` — the household's preferences (gitignored). Tests use `config/profile.example.yaml`.
- Trip dates, companions and bookings live only in the local DB.

## Repository layout

```text
dongseon/                           # repo root (uv project)
├── dongseon/                       # Python package
│   ├── main.py                     # FastAPI app factory, routers under /api, built SPA
│   ├── cli.py                      # Typer CLI (`uv run --no-sync dongseon ...`)
│   ├── core/                       # settings, profile, cities, defaults, job locks, Google usage meter
│   ├── db/                         # SQLAlchemy models, session
│   ├── api/routes/                 # REST endpoints
│   ├── sources/                    # (M1+) google_places, google_routes, open_meteo, fx, takeout
│   ├── places/ matrix/ stays/      # (M1–M2) pins, travel-time matrices, stay scoring
│   ├── flights/ planner/           # (M2–M3) flight evaluation, OR-Tools solver + validator
│   ├── llm/                        # (M4) headless Claude Code, payloads, prompts/*.md
│   ├── tripmode/                   # (M5) trip clock, weather, D-7 hours re-check, rain plans
│   └── export/                     # (M5) ICS, print HTML, My Maps CSV zip, Google Maps URLs
├── tests/unit_test/                # pytest (respx + fixtures; never real network)
├── frontend/                       # Vite + React + TypeScript (pnpm)
├── config/                         # defaults.yaml, cities/*.yaml (committed); profile.yaml (ignored)
├── data/                           # gitignored: SQLite DB, logs, locks, openapi.json
├── docs/                           # PLAN.md, google-terms.md
├── scripts/                        # install, pytest, env helpers (launchd in M5)
├── alembic/ + alembic.ini          # DB migrations (SQLite, batch mode)
└── Makefile, pyproject.toml, CLAUDE.md, CONTRIBUTING.md
```

## Process model

- Interactive work (search, autocomplete, solving, edits) runs in the API server. Long or bulk external work runs as
  CLI jobs; screens start them in the background behind a per-job file lock (`data/locks/`).
- The always-on app binds to `127.0.0.1:8100`. `make dev` runs a reloading backend on `127.0.0.1:8101` and Vite on
  port 5174 (`--host` for phones on the LAN), which proxies `/api`.
- Remote access: a separate shared edge repo (Cloudflare Tunnel + basic auth) forwards to `127.0.0.1:8100`; this repo
  knows nothing about it.
- Frontend API types are generated from the backend OpenAPI schema (`make gen-types`) and committed.

## Milestones

| # | Scope | Status |
|---|---|---|
| M0 | Scaffold, ports 8100/8101/5174, `/api/health`, React app, rules, CI, `docs/google-terms.md`, `api_usage` meter, remote access | done |
| M1 | Trips and places: Places search/autocomplete, URL paste, pins, Google map + list | done |
| M2 | Stays and flights: approximate travel times (no Google transit in Japan), neighborhood scores, stay and flight comparison | done |
| M2.5 | AI scouting: places/stay research with sources, accept/reject, search deep links, `scout` job | in review |
| M2.6 | Live prices: Ignav fares ranked by cost per usable hour, Rakuten vacancies, price history, `prices`/`daily` jobs | in review |
| M3 | Itinerary: per-date hours windows, OR-Tools solver, validator, timeline + map, edit/lock/re-solve, versions | done (Google WALK check waits for Routes API access) |
| M4 | AI: claude_cli, plan_review, rain_plan, food/hours/stay research, booking_parse, suggestion flow | done |
| M5 | Trip mode: today screen, weather/FX, D-7 hours refresh, daily + launchd, remote access, PWA offline, exports | done |
| M5+ | Local names by AI research (verified by IDs Only search), airport-zone pins on the arrival/departure day | in review |
| M6 | (optional) Takeout saved-list import (moved from M1), spending log, retrospective, paid flight/stay adapters, other cities | |

Update the status column when a milestone is accepted.
