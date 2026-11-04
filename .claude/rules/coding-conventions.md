---
description: Reference when writing or editing Python code. Covers style, naming, docstrings, type hints, and API/CLI conventions.
globs:
  - "dongseon/**/*.py"
  - "tests/**/*.py"
alwaysApply: false
---

# Coding conventions (Python)

## General

- **PEP 8** with project overrides; **Ruff** for formatting and linting (rule set in `pyproject.toml`).
- **Google-style docstrings** required for public modules, classes, and functions (tests are exempt).
- **pyright** (standard mode) must pass.
- Python **3.12** target. Use modern syntax (`X | None`, `list[int]`, `type` aliases).
- All public functions and classes carry **type hints**.
- **uv only** — see `build-and-test.md`.

## Line length and formatting

- Max line length **119**, 4-space indentation, double quotes.

## Naming

- Functions / variables: `snake_case`; classes: `PascalCase`; constants: `UPPER_SNAKE_CASE`; private: leading underscore.
- Durations end in `_min` (integer minutes), e.g. `dwell_min`, `move_min`. Money is `amount` (integer) next to `currency`.

## Docstrings

- First line: short imperative summary ending with a period.
- Non-trivial functions: `Args` / `Returns` / `Raises` sections; types live in hints, not the docstring.

```python
def available_local_min(option: FlightOption, *, buffers: Buffers, airport_access_min: tuple[int, int]) -> int:
    """Return the minutes usable at the destination between arrival and departure.

    Args:
        option: Round-trip flight candidate with timezone-aware legs.
        buffers: Profile buffers (immigration, departure airport).
        airport_access_min: Transit minutes airport→stay on arrival and stay→airport on departure.

    Returns:
        Usable minutes; negative when the schedule cannot work.
    """
```

## Imports

- isort order: stdlib → third-party → local (`dongseon.*`), separated by blank lines.
- Unused imports only in `__init__.py`.

## `print` is forbidden

- Ruff `T20` blocks `print()`. Use `typer.echo()` in the CLI and `logging` elsewhere.

## Settings and paths

- Read configuration only through `dongseon.core.config.get_settings()`.
- Resolve file paths with `resolve_repo_path()` so every entry point uses the same files regardless of the working directory.
- Never log or return secret values; expose only "is set" booleans.

## API conventions (`dongseon/api/routes/`)

- One router module per resource; mount under `/api` in `dongseon/main.py`.
- Request/response bodies are pydantic models — never return raw dicts. The frontend types are generated from these.
- Inject dependencies with `Annotated[T, Depends(...)]` (Ruff B008).
- Interactive work (search, autocomplete, solving, edits) runs in the API server. Long or bulk external work
  (Takeout resolution, exact matrices, AI research, `daily`) runs as CLI jobs; the API starts them in the background
  behind a per-job file lock.

## CLI conventions (`dongseon/cli.py`)

- **Typer**; every command is registered on the top-level `app`.
- Keep commands thin — put logic in modules (`dongseon/places/...`, `dongseon/planner/...`) so it can be unit-tested without Typer.
- **User-facing help and messages are Korean**; docstrings, comments, identifiers, and exception messages are English. Set Korean text via `@app.command(help="...")`.
- Provide short options where reasonable (`-p/--port`, `-o/--out`).
- Exit codes: 0 success, 1 user/input error, 2 external/system error (free-tier stop, network).
- Define typed exceptions in logic modules (e.g. `FreeTierExceededError`) and translate them at the CLI boundary.

## Data handling

- Money: integer `amount` in the original currency plus ISO 4217 `currency`; convert to KRW only for display (`fx_rates`).
- Durations: integer minutes. Dates: `datetime.date`. Datetimes are always timezone-aware (Ruff DTZ): flight legs use
  each airport's zone, local plans use the trip's zone. Never assume two zones are equal because their offsets match.
- Parse external strings at the boundary and keep internal types strict.
