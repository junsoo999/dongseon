---
description: Reference when touching personal data, money/time handling, Google data, external APIs, LLM features, or opening hours. These rules apply project-wide.
globs:
  - "dongseon/**"
  - "config/**"
  - "tests/unit_test/fixtures/**"
alwaysApply: true
---

# Domain rules

## Privacy (highest priority)

- The repo is pushed to GitHub. **Never** put personal data — trip dates, companions, booking numbers, home or stay
  addresses — into tracked files, test fixtures, docs, or commit messages.
- Preferences live only in `config/profile.yaml` (gitignored); trip dates, companions and bookings only in the local DB.
- Tests and examples use `config/profile.example.yaml` (fake values).
- Before saving a Google response as a fixture, replace any personal coordinates or addresses (home, stays) with fake ones.
- Never store passport numbers, birth dates or payment details. Mask them in pasted booking mail before it reaches the LLM.

## Units

- Money: integer `amount` + ISO 4217 `currency`, stored in the original currency; KRW only at display time via `fx_rates`
  with the rate date shown. JPY and KRW have no minor unit.
- Durations: integer minutes (`_min`). Datetimes are timezone-aware: flight legs in each airport's zone, local plans in the
  trip's zone. Seoul and Tokyo share UTC+9 today, but code never assumes zones are equal.

## Facts that change

- Opening hours, holidays, prices and free-tier caps are never hardcoded. They come from config with `source_url` /
  `as_of` (`config/defaults.yaml`, `config/cities/*.yaml`) or from cited research results.
- Opening-hours precedence: user input > Google special hours > AI research > regular weekly hours. Inside a holiday
  period with only regular hours, show "미확인".
- Every itinerary time is an estimate; show the hours source and check date next to it.

## Google Maps Platform

- `docs/google-terms.md` is the authority (ToS rev. 2026-08-26, Service Specific Terms rev. 2026-10-28). Re-read it
  before touching anything that stores, caches, exports, displays or sends Google content.
- Decided with the user (2026-11-04): the conservative design in `docs/PLAN.md` section 6.
- Permanent storage: `place_id` only (refresh yearly with a free IDs Only request). Labels, notes, categories and
  priorities are user data. Never copy Google `displayName` or addresses into the DB; a search-added place's default
  label is the user's own query text.
- Caching: only latitude/longitude, at most 30 days (`geo_cache`). Names, addresses, opening hours, durations and
  distances are fetched when needed and used within that request; never write them to the DB, disk, logs, fixtures
  for runtime use, or the offline cache. Store only the app's own derived results (plans, warning codes and text).
- Travel times: Google Routes returns no transit routes in Japan (checked 2026-11-05), so transit times are the
  straight-line approximation in `dongseon/matrix/approx.py` (parameters with sources in the city YAML), always shown
  as "근사". Google WALK is used for walking legs at request time and never stored.
- LLM input: user data plus code-computed abstract flags only. Never send Google-derived opening times, travel
  minutes, names, addresses or coordinates. Build every LLM payload in `dongseon/llm/payloads.py` only.
- Offline cache: user data, `place_id`, coordinates ≤ 30 days, planned order and times, Maps URLs deep links. No map tiles.
- Maps: Google Maps JavaScript API only; never show Google content on or near a non-Google map.
- Attribution: Google content shown without a Google map carries the Google Maps logo (or `Google Maps` text) in the
  same container, plus any `attributions[]` providers.
- Usage: every billable call goes through a meter (`dongseon.core.usage.make_meter()`, which commits each count in the
  caller's session because SQLite has one writer) before it is sent. Caps live in `config/defaults.yaml`;
  calls stop at `GOOGLE_FREE_TIER_STOP_RATIO`. Use the cheapest FieldMask (IDs Only, then Essentials) and request
  Enterprise fields (opening hours) only for must/want pins on the days they are needed. Note each field's SKU next to the
  FieldMask constant.

## Other external APIs

- Never guess response fields. Capture one real response into `tests/unit_test/fixtures/`, then write the parser against it.
- Google fixtures keep the captured structure but replace names, addresses and coordinates with fake values (place IDs
  may stay), so the repo stores no Google Maps Content. See `tests/unit_test/fixtures/google_places/README.md`.
- If the required API key is missing from `.env`, stop and ask the user.
- Check terms before integrating a service. Not used, by design: flight search APIs (Amadeus Self-Service ended
  2026-07-17), hotel partner APIs, Tabelog, Naver blogs and booking-site screens (deep links only).
- Record units of work in `job_log` so jobs resume; retry only transient errors (5xx, timeout) with exponential backoff, max 3.

## Itinerary solver

- `dongseon/planner/solver.py` (OR-Tools): one vehicle per day, one node per pin per allowed day in a single
  disjunction (penalty = priority weight × 10,000), a soft cap of even visits per day (below the drop penalties).
  `extended_swap_active` and `relocate_and_make_active` must stay on, or visits never move between days.
- Python 9.15 bindings: `SetAllowedVehiclesForIndex` takes no list; restrict days with `VehicleVar(idx).SetValues`.
  pytest must ignore the SWIG `builtin type ... has no __module__` DeprecationWarning (as errors it crashes import).
- Locked visits (`itinerary_items.locked`) keep their date and order on a re-solve: one copy on that day,
  `LOCK_PENALTY`, and cumul precedence constraints. Pins the user removed stay out (`solver_stats_json.excluded`).
- Every version is timed by `solver.schedule()` (earliest start along the order) and checked in
  `planner/build.py` (`_visit_warnings`), whether it came from the solver or a user edit. Edits, re-solves and
  restores always create a new version; only the active version can be edited (409 otherwise).
- Opening hours come from `dongseon/planner/hours.py`: user > Google special (7 days) > AI research > Google weekly;
  Google hours are fetched for must/want pins only and held in process memory for 10 minutes, never stored.

## Flight and hotel prices

- Ignav (`dongseon/sources/ignav.py`): terms (effective 2026-10-01) allow keeping and analyzing returned flight
  data; no attribution. One credit per successful request: search each home airport × city airport once a day,
  fetch booking links only when the user adds a fare.
- Flight search conditions live per trip in `fare_prefs` (travelers, airports, stops, local departure hours, bags,
  max price, excluded carriers); unset fields fall back to the profile and city config. A refresh replaces all fares.
- Rakuten Travel (`dongseon/sources/rakuten.py`): send the registered site URL as both `Referer` and `Origin`
  (`RAKUTEN_REFERER`, personal, `.env` only), at most about one request per second, and show
  "Supported by Rakuten Developers". The API reports only the first night's rate, so totals are labeled estimates.
- Hotel searches use the stay areas' station coordinates from the city config, never Google coordinates.

## LLM

- Headless Claude Code (`claude -p`, `--json-schema`) on the user's subscription, ported from jipsa's `claude_cli.py`.
  No Anthropic API key. Tools are off except for research tasks (`WebSearch`, `WebFetch`).
- Prompts live in `dongseon/llm/prompts/<name>_v<N>.md`; the file name is the version. Outputs use fixed JSON schemas
  validated with pydantic. Cache by input snapshot hash + prompt version; respect `LLM_DAILY_TOKEN_LIMIT`.
- The LLM proposes edits (`move` / `swap` / `drop` / `add_from_pool` / `set_dwell`) and never sets times.
  `dongseon/planner/suggest.py` applies each edit to the version, times it as given and, if that adds problems,
  re-solves only the touched days (`Edit.pinned` / `Edit.held_out` keep the rest without marking locks). An edit is
  "적용 가능" only with no new warnings and no newly dropped must/want pins versus the same version timed today.
  Previews are transient versions (`make_version(persist=False)`); preview and accept re-check against the active
  version, and accepting saves a new version with origin "ai".
- Plan review and rain plans (`dongseon/llm/plan_review.py`, `dongseon review [--rain DATE]`, job lock `review`)
  store `ai_suggestions` rows of kind `plan_review` (day titles, notes) and `plan_edit`; a new run expires pending
  rows of the same scope, and rejected edit titles are sent back as `rejected`. Indoor categories for rain plans
  live in `config/defaults.yaml` (`categories.indoor`).
- Research results without a source URL are dropped. Everything AI-generated carries "AI 제안".
- Scouting (`dongseon/llm/research.py`, `dongseon scout`): suggestions are matched to place IDs with IDs Only search,
  matches farther than 40 km from the city center are dropped, and the same input is not researched again within 7 days.
  Accepting makes a "maybe" pin (`added_by=ai`) or a stay candidate; rejected names are sent back as `rejected`.
- Holiday hours research (`dongseon/llm/hours_research.py`, `dongseon hours-research`): must/want pins with trip
  dates in a holiday period, in batches of 6, from the user's label, category and note only. A date is stored as
  `hours_overrides(source=ai_research)` only when open (with times) or closed, with a source URL and not low
  confidence; pins with rows for every holiday date checked within 7 days are skipped. Shown as "AI 조사 · 확인 필요"
  with the source link.
- Stay area notes (`dongseon/llm/area_notes.py`, `dongseon area-notes`): `ai_suggestions` kind `area_note`, one per
  configured area label, sources required.
- Booking emails (`dongseon/llm/booking.py`, `POST /trips/{id}/parse-booking`): mask card numbers (Luhn), passport
  numbers, birth dates, emails and phone numbers before the call (no tools); the text is never stored and the result
  is only a draft the user confirms in the flight or stay form.
- Never collect listings from booking sites (Airbnb, Booking.com, Google Flights pages). Open them as deep links
  (`dongseon/links.py`) and let the user add what they pick.
