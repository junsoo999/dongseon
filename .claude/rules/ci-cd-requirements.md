---
description: Reference when getting CI to pass or debugging a failed workflow. Covers GitHub Actions, pre-commit hooks, and local CI mirroring.
globs:
  - ".github/workflows/**/*.yml"
  - ".github/workflows/**/*.yaml"
  - ".pre-commit-config.yaml"
  - "pyproject.toml"
alwaysApply: false
---

# CI/CD requirements

All workflows run on GitHub-hosted `ubuntu-latest` runners.

## Required workflows

### 1. `pre-commit-validation` (`.github/workflows/pre-commit.yml`)

- **Trigger**: PRs targeting `main` (diff only), pushes to `main` (all files)
- **Steps**: checkout → setup-uv → pnpm + node 24 → `uv sync --locked` + `pnpm install --frozen-lockfile` → `pre-commit run`
- **Source of truth**: `.pre-commit-config.yaml`

### 2. `unit-test` (`.github/workflows/unit-test.yml`)

- **Trigger**: PRs and pushes to `main`, `workflow_dispatch`
- **Jobs**:
  - `backend` — `bash scripts/run_pytest.sh --coverage`
  - `frontend` — `pnpm test` + `pnpm build`
  - `api-types` — `make gen-types` must leave `frontend/src/api/schema.d.ts` unchanged
- **Local mirror**: `make test` and `make gen-types && git diff --exit-code frontend/src/api/schema.d.ts`

### 3. `pr-title-checker` (`.github/workflows/pr-title-checker.yml`)

- Validates `[TAG] <English body, 1–150 chars>` (see `contribution-guide.md`). Titles starting with `WIP:` skip validation.

## Pre-commit hooks

| Hook | Target | Purpose |
|---|---|---|
| `ruff-format` | `*.py` | Python format (uv-managed ruff) |
| `ruff` (`--fix`) | `*.py` | Python lint with auto-fix |
| `pyright` | `*.py` | Python type check |
| `frontend-prettier` | `frontend/src/**` | Prettier check |
| `frontend-oxlint` | `frontend/src/**` | oxlint |
| `frontend-typecheck` | `frontend/src/**`, tsconfig, vite config | `tsc -b` |
| `trailing-whitespace` / `end-of-file-fixer` | all | Whitespace hygiene |
| `check-yaml` | `*.yml` / `*.yaml` | YAML syntax |
| `check-added-large-files` | all | Block oversized files (e.g. a DB dump) |
| `detect-private-key` | all | Block committed private keys |
| `bashate` | shell | Shell script lint |
| `actionlint` | `.github/workflows/**` | Workflow lint |
| `markdownlint` | `*.md` | Markdown quality (`.markdownlint.yaml`) |

Python and frontend hooks are `repo: local` and call the project's own toolchain, so local runs, hooks, and CI use the same versions.

## Local CI mirror

```bash
uv run --no-sync pre-commit run --from-ref=origin/main --to-ref=HEAD   # diff only
uv run --no-sync pre-commit run --all-files                            # everything
make test
```

## Debugging a CI failure

1. Identify the failing hook or job from the workflow log.
2. Reproduce locally: `uv run --no-sync pre-commit run <hook-id> --files <path>`.
3. If auto-fixable (`ruff --fix`, `trailing-whitespace`), commit the fix.
4. If a hook itself is wrong, change it in a separate `[CI]` commit — do not mix infra changes into a feature change.
