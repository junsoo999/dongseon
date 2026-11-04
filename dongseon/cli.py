"""Typer-based ``dongseon`` command line interface.

User-facing help text and messages are Korean; docstrings stay English, so every command sets ``help=``.
"""

import json
import logging
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from dongseon.core.config import REPO_ROOT, get_settings
from dongseon.core.defaults import load_defaults
from dongseon.core.usage import month_usage
from dongseon.db.session import get_engine, session_scope, upgrade_schema

app = typer.Typer(help="dongseon 명령줄 도구", no_args_is_help=True)
db_app = typer.Typer(help="데이터베이스 관리", no_args_is_help=True)
app.add_typer(db_app, name="db")

EXIT_USER_ERROR = 1
EXIT_SYSTEM_ERROR = 2
EXIT_LOCKED = 3  # the same job is already running; nothing was done

LEVEL_LABEL = {"ok": "", "warn": "  ⚠ 경고", "stop": "  ⛔ 차단"}


@app.callback()
def _main(verbose: Annotated[bool, typer.Option("--verbose", "-v", help="상세 로그 출력")] = False) -> None:
    """Configure logging for every command."""
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@app.command(help="경로와 API 키 설정 여부를 보여줍니다.")
def info() -> None:
    """Show resolved paths and which API keys are configured."""
    settings = get_settings()
    typer.echo(f"repo root:    {REPO_ROOT}")
    typer.echo(f"database:     {settings.database_file}")
    typer.echo(f"profile:      {settings.profile_file} (exists={settings.profile_file.exists()})")
    for name, ok in settings.configured_keys.items():
        typer.echo(f"key {name:<20} {'set' if ok else 'missing'}")


@app.command(help="API 서버를 실행합니다. 기본은 127.0.0.1(이 컴퓨터에서만 접속)입니다.")
def serve(
    port: Annotated[int | None, typer.Option("--port", "-p", help="포트 (기본: DONGSEON_PORT, 8100)")] = None,
    host: Annotated[str, typer.Option("--host", help="바인딩 주소 (외부 접속을 열 때만 바꾸세요)")] = "127.0.0.1",
    reload: Annotated[bool, typer.Option(help="코드 변경 시 자동 재시작")] = True,
) -> None:
    """Run the API server (and the built frontend, if present)."""
    uvicorn.run("dongseon.main:app", host=host, port=port or get_settings().dongseon_port, reload=reload)


@app.command(help="OpenAPI 스키마를 출력합니다 (`make gen-types`에서 사용).")
def openapi(
    out: Annotated[Path | None, typer.Option("--out", "-o", help="출력 파일 (기본: stdout)")] = None,
) -> None:
    """Dump the OpenAPI schema as JSON."""
    from dongseon.main import app as fastapi_app

    schema = json.dumps(fastapi_app.openapi(), ensure_ascii=False, indent=2)
    if out is None:
        typer.echo(schema)
    else:
        out.write_text(schema + "\n", encoding="utf-8")


@db_app.command("upgrade", help="DB 스키마를 최신 마이그레이션으로 올립니다.")
def db_upgrade() -> None:
    """Apply all Alembic migrations."""
    settings = get_settings()
    upgrade_schema(settings.database_file)
    typer.echo(f"DB 스키마 최신화 완료: {settings.database_file}")


@app.command(help="이번 달 Google API 사용량을 SKU별로 무료 한도와 함께 보여줍니다.")
def usage() -> None:
    """Print this billing month's Google usage per SKU."""
    settings = get_settings()
    upgrade_schema(settings.database_file)
    tier = load_defaults(settings.defaults_file).google_free_tier
    with session_scope(get_engine(settings.database_file)) as session:
        month, rows = month_usage(
            session,
            tier,
            warn_ratio=settings.google_free_tier_warn_ratio,
            stop_ratio=settings.google_free_tier_stop_ratio,
        )
    typer.echo(f"{month} (무료 한도 {tier.as_of} 기준, {tier.source_url})")
    for r in rows:
        cap = "한도 없음" if r.cap is None else f"{r.cap:,}"
        typer.echo(f"  {r.sku:<34} {r.count:>7,} / {cap}{LEVEL_LABEL[r.level]}")
