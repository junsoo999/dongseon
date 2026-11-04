"""Typer-based ``dongseon`` command line interface.

User-facing help text and messages are Korean; docstrings stay English, so every command sets ``help=``.
"""

import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import httpx
import typer
import uvicorn
from sqlalchemy import select

from dongseon.core.cities import CityNotFoundError, load_city
from dongseon.core.config import REPO_ROOT, get_settings
from dongseon.core.defaults import load_defaults
from dongseon.core.lock import JobLockedError, job_lock
from dongseon.core.usage import FreeTierExceededError, make_meter, month_usage
from dongseon.db.models import JobLog, Trip
from dongseon.db.session import get_engine, session_scope, upgrade_schema
from dongseon.places.service import resolve_pending
from dongseon.sources.google_places import GooglePlacesClient, PlacesError

if TYPE_CHECKING:
    from sqlalchemy import Engine

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


trip_app = typer.Typer(help="여행 관리", no_args_is_help=True)
places_app = typer.Typer(help="장소 관리", no_args_is_help=True)
app.add_typer(trip_app, name="trip")
app.add_typer(places_app, name="places")


def _fail(message: str, code: int = EXIT_USER_ERROR) -> typer.Exit:
    typer.echo(message, err=True)
    return typer.Exit(code)


@trip_app.command("create", help="여행을 만듭니다.")
def trip_create(
    city: Annotated[str, typer.Option("--city", help="도시 키 (config/cities/<키>.yaml)")],
    start: Annotated[str, typer.Option("--start", help="시작일 YYYY-MM-DD")],
    end: Annotated[str, typer.Option("--end", help="종료일 YYYY-MM-DD")],
    title: Annotated[str, typer.Option("--title", help="여행 이름")],
    pace: Annotated[str, typer.Option("--pace", help="relaxed | normal | packed")] = "normal",
) -> None:
    """Create a trip."""
    settings = get_settings()
    try:
        city_cfg = load_city(settings.cities_path, city)
        start_d, end_d = date.fromisoformat(start), date.fromisoformat(end)
    except CityNotFoundError as e:
        raise _fail(f"설정에 없는 도시입니다: {city}") from e
    except ValueError as e:
        raise _fail("날짜는 YYYY-MM-DD 형식이어야 합니다") from e
    if end_d < start_d:
        raise _fail("종료일이 시작일보다 빠릅니다")
    if pace not in ("relaxed", "normal", "packed"):
        raise _fail("pace는 relaxed, normal, packed 중 하나입니다")
    upgrade_schema(settings.database_file)
    with session_scope(get_engine(settings.database_file)) as session:
        trip = Trip(
            title=title.strip(),
            city_key=city_cfg.key,
            start_date=start_d,
            end_date=end_d,
            timezone=city_cfg.timezone,
            pace=pace,
            created_at=datetime.now(UTC),
        )
        session.add(trip)
        session.flush()
        typer.echo(f"여행 #{trip.id} 생성: {trip.title} ({city_cfg.name}, {start_d} ~ {end_d})")


@trip_app.command("list", help="여행 목록을 보여줍니다.")
def trip_list() -> None:
    """List trips."""
    settings = get_settings()
    upgrade_schema(settings.database_file)
    with session_scope(get_engine(settings.database_file)) as session:
        for t in session.scalars(select(Trip).order_by(Trip.start_date.desc())):
            typer.echo(f"#{t.id:<3} {t.start_date} ~ {t.end_date}  {t.city_key:<8} {t.title}")


@places_app.command("resolve", help="Google 장소를 아직 못 찾은 항목을 링크·이름으로 다시 찾습니다.")
def places_resolve(
    trip: Annotated[int | None, typer.Option("--trip", help="이 여행의 장소만")] = None,
    retry_failed: Annotated[bool, typer.Option("--retry-failed", help="실패한 항목도 다시 시도")] = False,
) -> None:
    """Resolve pending places to Google place IDs (resumable, one job at a time)."""
    settings = get_settings()
    if not settings.google_maps_server_key:
        raise _fail("GOOGLE_MAPS_SERVER_KEY가 .env에 없습니다")
    upgrade_schema(settings.database_file)
    engine = get_engine(settings.database_file)
    defaults = load_defaults(settings.defaults_file)
    try:
        with job_lock(settings.lock_path, "places-resolve"), httpx.Client(timeout=15.0) as http:
            status, error, rows = "ok", None, 0
            try:
                with session_scope(engine) as session:
                    meter = make_meter(
                        session,
                        defaults.google_free_tier,
                        warn_ratio=settings.google_free_tier_warn_ratio,
                        stop_ratio=settings.google_free_tier_stop_ratio,
                    )
                    client = GooglePlacesClient(http, settings.google_maps_server_key, meter)
                    region = None
                    if trip is not None:
                        t = session.get(Trip, trip)
                        if t is None:
                            raise _fail(f"여행 #{trip}이 없습니다")
                        city_cfg = load_city(settings.cities_path, t.city_key)
                        region = city_cfg.region_code or city_cfg.country
                    summary = resolve_pending(
                        session,
                        http,
                        client,
                        defaults.categories,
                        region_code=region,
                        retry_failed=retry_failed,
                        trip_id=trip,
                    )
                    rows = summary.resolved
                typer.echo(f"해석 완료 {summary.resolved}건, 실패 {summary.failed}건")
            except FreeTierExceededError as e:
                status, error = "quota", str(e)
                typer.echo(f"Google 무료 한도에 걸려 멈췄습니다: {e}", err=True)
            except (PlacesError, httpx.HTTPError) as e:
                status, error = "error", str(e)
                typer.echo(f"Google 호출 실패: {e}", err=True)
            _log_job(engine, "places-resolve", status, rows, error)
            if status != "ok":
                raise typer.Exit(EXIT_SYSTEM_ERROR)
    except JobLockedError as e:
        raise _fail("이미 실행 중입니다", EXIT_LOCKED) from e


def _log_job(engine: "Engine", job: str, status: str, rows: int, error: str | None) -> None:
    with session_scope(engine) as session:
        row = session.scalar(select(JobLog).where(JobLog.job == job, JobLog.key == ""))
        if row is None:
            row = JobLog(job=job, key="", status=status, rows=rows, ran_at=datetime.now(UTC))
            session.add(row)
        row.status, row.rows, row.ran_at, row.error = status, rows, datetime.now(UTC), error


@app.command(help="AI가 웹을 조사해 가볼 곳·맛집·숙소 후보를 추천합니다 (출처 포함, 화면에서 수락/거절).")
def scout(
    trip: Annotated[int | None, typer.Option("--trip", help="이 여행만 (기본: 끝나지 않은 모든 여행)")] = None,
    only: Annotated[str | None, typer.Option("--only", help="place 또는 stay만")] = None,
    force: Annotated[bool, typer.Option("--force", help="입력이 같아도 다시 조사")] = False,
) -> None:
    """Research place and stay suggestions with headless Claude Code (resumable, one run at a time)."""
    from dongseon.core.profile import load_profile
    from dongseon.llm.claude_cli import ClaudeCli, LlmError
    from dongseon.scout import scout_trip

    settings = get_settings()
    if not settings.google_maps_server_key:
        raise _fail("GOOGLE_MAPS_SERVER_KEY가 .env에 없습니다")
    if only not in (None, "place", "stay"):
        raise _fail("--only는 place 또는 stay입니다")
    kinds = (only,) if only else ("place", "stay")
    upgrade_schema(settings.database_file)
    engine = get_engine(settings.database_file)
    defaults = load_defaults(settings.defaults_file)
    profile_path = (
        settings.profile_file if settings.profile_file.exists() else REPO_ROOT / "config/profile.example.yaml"
    )
    profile = load_profile(profile_path)
    llm = ClaudeCli(engine, model=settings.llm_model, daily_token_limit=settings.llm_daily_token_limit)
    status, error, rows = "ok", None, 0
    try:
        with job_lock(settings.lock_path, "scout"), httpx.Client(timeout=15.0) as http:
            with session_scope(engine) as session:
                today = datetime.now(UTC).date()
                stmt = (
                    select(Trip).where(Trip.end_date >= today) if trip is None else select(Trip).where(Trip.id == trip)
                )
                trips = session.scalars(stmt).all()
                if not trips:
                    typer.echo("조사할 여행이 없습니다")
            for t_id in [t.id for t in trips]:
                try:
                    with session_scope(engine) as session:
                        t = session.get(Trip, t_id)
                        assert t is not None
                        city = load_city(settings.cities_path, t.city_key)
                        meter = make_meter(
                            session,
                            defaults.google_free_tier,
                            warn_ratio=settings.google_free_tier_warn_ratio,
                            stop_ratio=settings.google_free_tier_stop_ratio,
                        )
                        client = GooglePlacesClient(http, settings.google_maps_server_key, meter)
                        summary = scout_trip(
                            session,
                            trip=t,
                            city=city,
                            profile=profile,
                            settings=settings,
                            llm=llm,
                            client=client,
                            http=http,
                            kinds=kinds,
                            force=force,
                        )
                    for r in summary.results:
                        label = "장소" if r.kind == "place" else "숙소"
                        if r.skipped:
                            typer.echo(f"#{t_id} {label}: 최근에 같은 조건으로 조사해서 건너뜀 (--force로 다시)")
                        else:
                            rows += r.stored
                            typer.echo(
                                f"#{t_id} {label}: 제안 {r.proposed}건 중 새 추천 {r.stored}건 (장소 매칭 실패 {r.unmatched})"
                            )
                except (LlmError, FreeTierExceededError, PlacesError, httpx.HTTPError) as e:
                    status, error = ("quota" if isinstance(e, FreeTierExceededError) else "error"), str(e)[:300]
                    typer.echo(f"#{t_id} 조사 실패: {e}", err=True)
    except JobLockedError as e:
        raise _fail("이미 실행 중입니다", EXIT_LOCKED) from e
    _log_job(engine, "scout", status, rows, error)
    if status != "ok":
        raise typer.Exit(EXIT_SYSTEM_ERROR)


@app.command(help="실시간 가격을 가져옵니다: Ignav 항공 운임과 楽天トラベル 빈방 (끝나지 않은 여행).")
def prices(
    trip: Annotated[int | None, typer.Option("--trip", help="이 여행만")] = None,
    max_stops: Annotated[int, typer.Option("--max-stops", help="경유 횟수 상한 (0 = 직항)")] = 0,
) -> None:
    """Refresh fares and hotel vacancies for upcoming trips (one run at a time)."""
    from dongseon.core.profile import load_profile
    from dongseon.prices import refresh_prices
    from dongseon.sources.ignav import IgnavClient
    from dongseon.sources.rakuten import RakutenClient

    settings = get_settings()
    has_rakuten = bool(settings.rakuten_app_id and settings.rakuten_access_key and settings.rakuten_referer)
    if not settings.ignav_api_key and not has_rakuten:
        raise _fail("IGNAV_API_KEY나 RAKUTEN_APP_ID/RAKUTEN_ACCESS_KEY/RAKUTEN_REFERER가 .env에 없습니다")
    upgrade_schema(settings.database_file)
    engine = get_engine(settings.database_file)
    defaults = load_defaults(settings.defaults_file)
    profile_path = (
        settings.profile_file if settings.profile_file.exists() else REPO_ROOT / "config/profile.example.yaml"
    )
    profile = load_profile(profile_path)
    status, errors, rows = "ok", [], 0
    try:
        with job_lock(settings.lock_path, "prices"), httpx.Client(timeout=30.0) as http:
            ignav = IgnavClient(http, settings.ignav_api_key) if settings.ignav_api_key else None
            rakuten = (
                RakutenClient(
                    http,
                    app_id=settings.rakuten_app_id,
                    access_key=settings.rakuten_access_key,
                    referer=settings.rakuten_referer,
                )
                if has_rakuten
                else None
            )
            with session_scope(engine) as session:
                today = datetime.now(UTC).date()
                stmt = (
                    select(Trip).where(Trip.end_date >= today) if trip is None else select(Trip).where(Trip.id == trip)
                )
                trip_ids = [t.id for t in session.scalars(stmt)]
            for t_id in trip_ids:
                with session_scope(engine) as session:
                    t = session.get(Trip, t_id)
                    assert t is not None
                    places = None
                    if settings.google_maps_server_key:
                        meter = make_meter(
                            session,
                            defaults.google_free_tier,
                            warn_ratio=settings.google_free_tier_warn_ratio,
                            stop_ratio=settings.google_free_tier_stop_ratio,
                        )
                        places = GooglePlacesClient(http, settings.google_maps_server_key, meter)
                    summary = refresh_prices(
                        session,
                        trip=t,
                        city=load_city(settings.cities_path, t.city_key),
                        profile=profile,
                        settings=settings,
                        http=http,
                        places=places,
                        ignav=ignav,
                        rakuten=rakuten,
                        max_stops=max_stops,
                    )
                rows += sum(summary.fares.values()) + sum(summary.hotels.values())
                fares = ", ".join(f"{k} {v}건" for k, v in summary.fares.items()) or "없음"
                hotels = ", ".join(f"{k} {v}곳" for k, v in summary.hotels.items()) or "없음"
                typer.echo(f"#{t_id} 항공 운임: {fares} · 빈방: {hotels}")
                for e in summary.errors:
                    typer.echo(f"#{t_id} 실패: {e}", err=True)
                errors += summary.errors
    except JobLockedError as e:
        raise _fail("이미 실행 중입니다", EXIT_LOCKED) from e
    if errors:
        status = "error"
    _log_job(engine, "prices", status, rows, "; ".join(errors)[:300] or None)
    if errors and rows == 0:
        raise typer.Exit(EXIT_SYSTEM_ERROR)


@app.command(help="매일 할 작업을 순서대로 실행합니다 (실시간 가격 → AI 추천, 단계별 실패와 무관하게 계속).")
def daily(
    log: Annotated[
        Path | None, typer.Option("--log", help="출력을 이어서 기록할 파일 (기본: data/logs/daily.log)")
    ] = None,
) -> None:
    """Run the daily pipeline and record it in job_log."""
    from dongseon.daily import run_daily

    target = log or (REPO_ROOT / "data" / "logs" / "daily.log")
    target.parent.mkdir(parents=True, exist_ok=True)
    results = run_daily(target)
    settings = get_settings()
    upgrade_schema(settings.database_file)
    ok = any(r.returncode in (0, 3) for r in results)
    _log_job(get_engine(settings.database_file), "daily", "ok" if ok else "error", len(results), None)
    if not ok:
        raise typer.Exit(EXIT_SYSTEM_ERROR)
