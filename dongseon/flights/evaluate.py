"""Usable local time of a round-trip flight option.

usable = (return departure - departure-airport buffer - stay→airport) - (arrival + immigration buffer + airport→stay)
"""

import itertools
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from dongseon.core.profile import Buffers


@dataclass(frozen=True)
class LegTimes:
    """A leg's airports and UTC times."""

    direction: str  # out | back
    dep_airport: str
    dep_at: datetime
    arr_airport: str
    arr_at: datetime


@dataclass(frozen=True)
class Evaluation:
    """When the trip can start and must end at the destination, and the minutes in between."""

    arrival_airport: str
    arrival_at: datetime
    ready_at: datetime | None
    departure_airport: str
    departure_at: datetime
    leave_by: datetime | None
    access_in_min: int | None
    access_out_min: int | None
    usable_min: int | None
    warnings: list[str] = field(default_factory=list)


def check_legs(legs: list[LegTimes]) -> list[str]:
    """Return problems with leg order and times (Korean messages)."""
    problems: list[str] = []
    for leg in legs:
        if leg.arr_at <= leg.dep_at:
            problems.append(f"{leg.dep_airport}→{leg.arr_airport}: 도착이 출발보다 빠릅니다")
    for direction in ("out", "back"):
        chain = sorted((leg for leg in legs if leg.direction == direction), key=lambda leg: leg.dep_at)
        for prev, nxt in itertools.pairwise(chain):
            if nxt.dep_airport != prev.arr_airport:
                problems.append(f"{prev.arr_airport}에 도착한 뒤 {nxt.dep_airport}에서 출발합니다")
            if nxt.dep_at < prev.arr_at:
                problems.append(f"{nxt.dep_airport} 출발이 앞 구간 도착보다 빠릅니다")
    outs = [leg for leg in legs if leg.direction == "out"]
    backs = [leg for leg in legs if leg.direction == "back"]
    if outs and backs and min(b.dep_at for b in backs) <= max(o.arr_at for o in outs):
        problems.append("귀국편 출발이 출국편 도착보다 빠릅니다")
    return problems


def evaluate(legs: list[LegTimes], buffers: Buffers, access_min: dict[str, int]) -> Evaluation | None:
    """Evaluate an option with both directions; ``None`` when a direction is missing.

    Args:
        legs: All legs of the option.
        buffers: Profile buffers (immigration after arrival, airport time before departure).
        access_min: Minutes between the reference stay and each destination airport (by IATA code).
    """
    outs = sorted((leg for leg in legs if leg.direction == "out"), key=lambda leg: leg.dep_at)
    backs = sorted((leg for leg in legs if leg.direction == "back"), key=lambda leg: leg.dep_at)
    if not outs or not backs:
        return None
    arrival, departure = outs[-1], backs[0]
    warnings: list[str] = []
    access_in = access_min.get(arrival.arr_airport)
    access_out = access_min.get(departure.dep_airport)
    for code, value in ((arrival.arr_airport, access_in), (departure.dep_airport, access_out)):
        if value is None:
            warnings.append(f"{code}↔숙소 이동시간을 몰라 가용 시간을 계산하지 못했습니다")
    ready_at = (
        arrival.arr_at + timedelta(minutes=buffers.arrival_immigration + access_in) if access_in is not None else None
    )
    leave_by = (
        departure.dep_at - timedelta(minutes=buffers.departure_airport + access_out)
        if access_out is not None
        else None
    )
    usable = round((leave_by - ready_at).total_seconds() / 60) if ready_at and leave_by else None
    if usable is not None and usable <= 0:
        warnings.append("현지에서 쓸 수 있는 시간이 없습니다")
    return Evaluation(
        arrival_airport=arrival.arr_airport,
        arrival_at=arrival.arr_at,
        ready_at=ready_at,
        departure_airport=departure.dep_airport,
        departure_at=departure.dep_at,
        leave_by=leave_by,
        access_in_min=access_in,
        access_out_min=access_out,
        usable_min=usable,
        warnings=warnings,
    )
