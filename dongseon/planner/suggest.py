"""Apply an AI edit suggestion to a version and check it before the user sees it as applicable.

The LLM proposes edits (``move`` / ``swap`` / ``drop`` / ``add_from_pool`` / ``set_dwell``) and never sets times.
Each edit is applied to the version's layout and timed as given; when that adds problems, the days it touches are
re-solved with every other day kept in place. An edit is applicable only when the result has no new problems
(warnings or must/want pins left out) compared with the same version timed today.
"""

import datetime as dt
import json
import re
from dataclasses import dataclass, replace
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from dongseon.db.models import Itinerary
from dongseon.planner.build import Edit, PlanContext, edit_of, make_version

Op = Literal["move", "swap", "drop", "add_from_pool", "set_dwell"]
LATE_SLACK_MIN = 15  # a day ending this much later than before counts as a new problem
IGNORED = ("AI 조사 기준 영업시간",)  # informational, not a problem


class PlanEdit(BaseModel):
    """One edit proposed by the LLM (pin ids are the app's own ids from the payload)."""

    op: Op
    pin_id: int
    other_pin_id: int | None = None  # swap: the pin to trade places with
    date: dt.date | None = None  # move / add_from_pool: target date
    after_pin_id: int | None = None  # move / add_from_pool: insert after this pin (null = first)
    dwell_min: int | None = Field(default=None, ge=15, le=480)  # set_dwell
    reason: str = Field(max_length=300)


class EditNotApplicableError(ValueError):
    """The edit does not fit the version (unknown pin, wrong date, nothing to change)."""


@dataclass(frozen=True)
class Applied:
    """An edit turned into a layout for :func:`make_version`."""

    edit: Edit
    touched: frozenset[int]  # pins the edit moves, adds or changes
    days: frozenset[date]  # dates whose order changes
    dwell: dict[int, int]  # pin id -> new dwell minutes


def _where(layout: dict[date, list[int]], pin_id: int) -> date | None:
    return next((d for d, pids in layout.items() if pin_id in pids), None)


def _insert(pids: list[int], pin_id: int, after: int | None) -> list[int]:
    if after is None:
        return [pin_id, *pids]
    if after not in pids:
        raise EditNotApplicableError("after_pin_id is not on the target date")
    i = pids.index(after) + 1
    return [*pids[:i], pin_id, *pids[i:]]


def apply_edit(base: Edit, e: PlanEdit, known_pins: set[int]) -> Applied:
    """Apply one edit to a version's layout. Moved and added pins become locked, like a user's moves.

    Raises:
        EditNotApplicableError: The edit refers to unknown pins or dates, or changes nothing.
    """
    if e.pin_id not in known_pins:
        raise EditNotApplicableError("unknown pin")
    layout = {d: list(p) for d, p in base.layout.items()}
    locked, excluded = set(base.locked), set(base.excluded)
    here = _where(layout, e.pin_id)
    touched = {e.pin_id}
    days: set[date] = set()
    dwell: dict[int, int] = {}
    if e.op in ("move", "add_from_pool"):
        if e.date is None or e.date not in layout:
            raise EditNotApplicableError("target date is not in the trip")
        if e.op == "move" and here is None:
            raise EditNotApplicableError("pin is not in the plan")
        if e.op == "add_from_pool" and here is not None:
            raise EditNotApplicableError("pin is already in the plan")
        if here is not None:
            layout[here].remove(e.pin_id)
            days.add(here)
        layout[e.date] = _insert(layout[e.date], e.pin_id, e.after_pin_id)
        days.add(e.date)
        locked.add(e.pin_id)
        excluded.discard(e.pin_id)
    elif e.op == "swap":
        other = e.other_pin_id
        there = _where(layout, other) if other is not None else None
        if other is None or here is None or there is None or other == e.pin_id:
            raise EditNotApplicableError("swap needs two planned pins")
        a, b = layout[here].index(e.pin_id), layout[there].index(other)
        layout[here][a], layout[there][b] = other, e.pin_id
        touched.add(other)
        days |= {here, there}
        locked |= {e.pin_id, other}
    elif e.op == "drop":
        if here is None:
            raise EditNotApplicableError("pin is not in the plan")
        layout[here].remove(e.pin_id)
        days.add(here)
        locked.discard(e.pin_id)
        excluded.add(e.pin_id)
    else:  # set_dwell
        if e.dwell_min is None:
            raise EditNotApplicableError("set_dwell needs dwell_min")
        if here is not None:
            days.add(here)
        dwell[e.pin_id] = e.dwell_min
    edit = replace(base, layout=layout, locked=frozenset(locked), excluded=frozenset(excluded), resolve=False)
    return Applied(edit, frozenset(touched), frozenset(days), dwell)


def with_dwell(ctx: PlanContext, dwell: dict[int, int]) -> PlanContext:
    """A context whose stops use the given dwell minutes (the pins themselves are not changed)."""
    if not dwell:
        return ctx
    stops = {pid: replace(s, dwell_min=dwell[pid]) if pid in dwell else s for pid, s in ctx.stops.items()}
    return replace(ctx, stops=stops)


def _issues(it: Itinerary, ctx: PlanContext) -> tuple[set[tuple[str, str]], dict[str, int], dict[int, str]]:
    """Problem keys (where, text with numbers blanked), minutes late per date, and must/want pins left out."""
    keys: set[tuple[str, str]] = set()
    late: dict[str, int] = {}
    for item in it.items:
        for w in json.loads(item.warnings_json or "{}").get("warnings") or []:
            if w not in IGNORED:
                keys.add((f"pin:{item.pin_id}", w))
    stats = json.loads(it.solver_stats_json or "{}")
    for d, info in (stats.get("days") or {}).items():
        for w in info.get("warnings") or []:
            keys.add((d, re.sub(r"\d+", "#", w)))
        back = info.get("return_min")
        if back is not None and back > info["end_min"]:
            late[d] = back - info["end_min"]
    missing = {
        x["pin_id"]: x["label"]
        for x in stats.get("dropped") or []
        if x["priority"] in ("must", "want") and not x.get("excluded") and x["pin_id"] in ctx.pins
    }
    return keys, late, missing


def _md(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.month}/{d.day}"


def problems(before: Itinerary, after: Itinerary, ctx: PlanContext) -> list[str]:
    """New problems in ``after`` compared with ``before`` (Korean, for the user)."""
    keys_a, late_a, missing_a = _issues(before, ctx)
    keys_b, late_b, missing_b = _issues(after, ctx)
    labels = {p.id: p.place.label for p in ctx.pins.values()}
    out: list[str] = []
    for where, text in sorted(keys_b - keys_a):
        if where.startswith("pin:"):
            pid = int(where[4:])
            out.append(f"{labels.get(pid, '?')}: {text}")
        elif not text.startswith("하루 끝"):
            out.append(f"{_md(where)}: {text}")
    for d, m in sorted(late_b.items()):
        if m > late_a.get(d, 0) + LATE_SLACK_MIN:
            out.append(f"{_md(d)}: 하루 끝보다 {m}분 늦게 돌아옵니다")
    for pid, label in missing_b.items():
        if pid not in missing_a:
            out.append(f"{label}이(가) 일정에서 빠집니다")
    return out


@dataclass(frozen=True)
class Checked:
    """A checked edit: the preview version, its new problems, and the layout to save on accept."""

    preview: Itinerary
    problems: list[str]
    edit: Edit
    ctx: PlanContext
    resolved: bool  # the touched days were re-solved because timing as given added problems


def check_edit(session: Session, ctx: PlanContext, base: Edit, e: PlanEdit) -> Checked:
    """Apply an edit, time it, fall back to re-solving the touched days, and report new problems.

    Nothing is written; :func:`make_version` with ``persist=False`` builds transient previews.

    Raises:
        EditNotApplicableError: The edit does not fit the version.
    """
    applied = apply_edit(base, e, set(ctx.pins) & set(ctx.stops))
    baseline = make_version(session, ctx, replace(base, resolve=False), persist=False)
    ctx2 = with_dwell(ctx, applied.dwell)
    as_is = make_version(session, ctx2, applied.edit, origin="ai", persist=False)
    found = problems(baseline, as_is, ctx2)
    if not found:
        return Checked(as_is, [], applied.edit, ctx2, False)
    # Re-solve only the touched days: everything else stays where it is, nothing new comes in.
    layout = applied.edit.layout
    elsewhere = frozenset(p for d, pids in layout.items() if d not in applied.days for p in pids)
    placed = {p for pids in layout.values() for p in pids}
    held = frozenset(p for p in ctx.stops if p not in placed and p not in applied.touched)
    resolve_edit = replace(applied.edit, resolve=True, pinned=elsewhere, held_out=held)
    solved = make_version(session, ctx2, resolve_edit, origin="ai", persist=False)
    found2 = problems(baseline, solved, ctx2)
    if len(found2) < len(found):
        # Save the solved order as given, so accepting reproduces exactly this preview.
        final = replace(applied.edit, layout=edit_of(solved).layout, resolve=False)
        return Checked(solved, found2, final, ctx2, True)
    return Checked(as_is, found, applied.edit, ctx2, False)


def describe(e: PlanEdit, labels: dict[int, str], dates: list[date]) -> str:
    """A short Korean title for an edit, e.g. "우에노 공원 → 3일차(12/30)"."""

    def day(d: date | None) -> str:
        if d is None or d not in dates:
            return "?"
        return f"{dates.index(d) + 1}일차({d.month}/{d.day})"

    name = labels.get(e.pin_id, "?")
    if e.op == "move":
        return f"{name} → {day(e.date)}로 옮기기"
    if e.op == "add_from_pool":
        return f"{name}을(를) {day(e.date)}에 넣기"
    if e.op == "swap":
        return f"{name} ↔ {labels.get(e.other_pin_id or 0, '?')} 바꾸기"
    if e.op == "drop":
        return f"{name} 빼기"
    return f"{name} 머무는 시간 {e.dwell_min}분으로"
