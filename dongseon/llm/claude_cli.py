"""Structured calls to headless Claude Code (``claude -p``) on the user's own subscription.

Each call runs with no tools, no MCP servers, no settings and a short system prompt, so only the given
input reaches the model (about a thousand tokens of overhead instead of the full agent context). The
answer must match a JSON Schema (``--json-schema``); the CLI returns it as ``structured_output``.

Prompts live in ``dongseon/llm/prompts/<name>_v<N>.md``; the file name is the prompt version.
"""

import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from dongseon.db.models import LlmRun
from dongseon.db.session import session_scope

PROMPTS_DIR = Path(__file__).parent / "prompts"
TIMEOUT_S = 300


class LlmError(RuntimeError):
    """The Claude Code call failed or returned no structured output."""


class TokenLimitError(LlmError):
    """Today's ``LLM_DAILY_TOKEN_LIMIT`` is used up."""


@dataclass(frozen=True)
class Prompt:
    """A versioned prompt file."""

    version: str  # e.g. "places_research_v1"
    system: str
    instructions: str


@dataclass(frozen=True)
class LlmResult:
    """Structured output plus usage."""

    data: Any
    tokens: int
    cost_usd: float | None


def load_prompt(version: str) -> Prompt:
    """Load ``prompts/<version>.md``: the part before ``<!-- instructions -->`` is the system prompt."""
    text = (PROMPTS_DIR / f"{version}.md").read_text(encoding="utf-8")
    system, _, instructions = text.partition("<!-- instructions -->")
    return Prompt(version, system.strip(), instructions.strip())


Runner = Callable[[list[str], str, int], str]  # (argv, stdin, timeout_s) -> stdout


def _subprocess_runner(argv: list[str], stdin: str, timeout: int) -> str:
    with tempfile.TemporaryDirectory() as cwd:  # no project files in reach
        proc = subprocess.run(argv, input=stdin, capture_output=True, text=True, timeout=timeout, cwd=cwd, check=False)
    if proc.returncode != 0 and not proc.stdout.strip():
        raise LlmError(f"claude exited with {proc.returncode}: {proc.stderr.strip()[:300]}")
    return proc.stdout


def claude_bin() -> str:
    """Path of the ``claude`` CLI (``CLAUDE_BIN`` overrides)."""
    found = os.environ.get("CLAUDE_BIN") or shutil.which("claude")
    if not found and (Path.home() / ".local" / "bin" / "claude").exists():  # launchd PATH may omit it
        found = str(Path.home() / ".local" / "bin" / "claude")
    if not found:
        raise LlmError("claude CLI not found (install Claude Code or set CLAUDE_BIN)")
    return found


def tokens_used_today(session: Session) -> int:
    """Tokens recorded in ``llm_runs`` over the last 24 hours."""
    since = datetime.now(UTC) - timedelta(days=1)
    used = session.scalar(select(func.coalesce(func.sum(LlmRun.tokens), 0)).where(LlmRun.created_at >= since))
    return int(used or 0)


class ClaudeCli:
    """Runs one structured prompt per call and records usage."""

    def __init__(self, engine: Engine, *, model: str, daily_token_limit: int, runner: Runner | None = None) -> None:
        """Create a caller.

        Args:
            engine: Database engine (usage is recorded in ``llm_runs``, also for failed calls).
            model: Model alias or id passed to ``--model``; empty uses Claude Code's default.
            daily_token_limit: Refuse new calls once this many tokens were used in 24 hours.
            runner: Executes the CLI; the default runs ``claude`` in an empty temporary directory.
        """
        self._engine = engine
        self.model = model
        self.daily_token_limit = daily_token_limit
        self._runner = runner or _subprocess_runner

    def run(
        self,
        kind: str,
        prompt: Prompt,
        payload: Any,
        schema: dict,
        *,
        tools: tuple[str, ...] = (),
        timeout: int = TIMEOUT_S,
    ) -> LlmResult:
        """Send ``payload`` (as JSON) with the prompt's instructions and return the schema-valid answer.

        ``tools`` enables (and pre-approves) built-in tools such as ``("WebSearch", "WebFetch")``; by default
        the model has no tools at all.

        Raises:
            TokenLimitError: The daily token limit is reached.
            LlmError: The call failed.
        """
        with session_scope(self._engine) as session:
            used = tokens_used_today(session)
        if used >= self.daily_token_limit:
            raise TokenLimitError(f"LLM_DAILY_TOKEN_LIMIT ({self.daily_token_limit}) reached")
        argv = [
            claude_bin() if self._runner is _subprocess_runner else "claude",
            "-p",
            *(["--model", self.model] if self.model else []),
            "--output-format",
            "json",
            "--no-session-persistence",
            "--tools",
            ",".join(tools),
            *(["--allowedTools", *tools] if tools else []),
            "--strict-mcp-config",
            "--setting-sources",
            "",
            "--disable-slash-commands",
            "--system-prompt",
            prompt.system,
            "--json-schema",
            json.dumps(schema, ensure_ascii=False),
        ]
        stdin = f"{prompt.instructions}\n\n<input>\n{json.dumps(payload, ensure_ascii=False, default=str)}\n</input>"
        error: str | None = None
        tokens, cost, data = 0, None, None
        try:
            raw = json.loads(self._runner(argv, stdin, timeout))
            usage = raw.get("usage") or {}
            tokens = sum(
                int(usage.get(k) or 0)
                for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
            )
            cost = raw.get("total_cost_usd")
            if raw.get("is_error") or raw.get("structured_output") is None:
                error = str(raw.get("result") or raw.get("subtype") or "no structured output")[:300]
            else:
                data = raw["structured_output"]
        except (LlmError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            error = str(e)[:300]
        with session_scope(self._engine) as session:
            session.add(
                LlmRun(
                    kind=kind,
                    model=self.model or "default",
                    prompt_version=prompt.version,
                    tokens=tokens,
                    cost_usd=cost,
                    ok=error is None,
                    error=error,
                    created_at=datetime.now(UTC),
                )
            )
        if error is not None:
            raise LlmError(error)
        return LlmResult(data, tokens, cost)
