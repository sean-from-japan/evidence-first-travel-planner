"""Deterministic, explainable itinerary validation rules."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Set, Tuple

from evidence_travel.model import InputError, Itinerary, by_id


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str
    entity_id: str
    message: str
    constraint: str
    source_ids: Tuple[str, ...] = ()

    @property
    def sort_key(self) -> Tuple[str, str, str, str]:
        return (self.severity, self.code, self.entity_id, self.message)


def _source_ids(item: Mapping[str, Any]) -> Tuple[str, ...]:
    value = item.get("source_ids", [])
    return tuple(sorted(str(source_id) for source_id in value))


def _hhmm(value: str) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise InputError(f"invalid local time: {value}") from exc


def _window_bounds(
    day: date, opens: time, closes: time, tz: Any
) -> Tuple[datetime, datetime]:
    start = datetime.combine(day, opens, tzinfo=tz)
    end_day = day + timedelta(days=1) if closes <= opens else day
    return start, datetime.combine(end_day, closes, tzinfo=tz)


def _activity_is_open(itinerary: Itinerary, activity: Mapping[str, Any]) -> bool:
    start = itinerary.local_datetime(str(activity["start"]))
    end = itinerary.local_datetime(str(activity["end"]))
    if start.date().isoformat() in activity.get("closures", []):
        return False
    for window in activity.get("opening_windows", []):
        days = window.get("days", [])
        window_start, window_end = _window_bounds(
            start.date(),
            _hhmm(str(window["opens"])),
            _hhmm(str(window["closes"])),
            itinerary.timezone,
        )
        if start.strftime("%a") in days and window_start <= start and end <= window_end:
            return True
        previous = start.date() - timedelta(days=1)
        previous_start, previous_end = _window_bounds(
            previous,
            _hhmm(str(window["opens"])),
            _hhmm(str(window["closes"])),
            itinerary.timezone,
        )
        if (
            previous_start.strftime("%a") in days
            and previous_start <= start
            and end <= previous_end
        ):
            return True
    return False


def _overlap(
    a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime
) -> bool:
    return max(a_start, b_start) < min(a_end, b_end)


def _haversine_km(a: Mapping[str, Any], b: Mapping[str, Any]) -> float:
    lat1, lon1 = math.radians(float(a["lat"])), math.radians(float(a["lon"]))
    lat2, lon2 = math.radians(float(b["lat"])), math.radians(float(b["lon"]))
    d_lat, d_lon = lat2 - lat1, lon2 - lon1
    value = (
        math.sin(d_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2
    )
    return 6371.0088 * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def validate(itinerary: Itinerary) -> List[Issue]:
    issues: List[Issue] = []
    sources = by_id(itinerary.sources)
    places = by_id(itinerary.places)
    activities = by_id(itinerary.activities)
    reservations = by_id(itinerary.reservations)
    fallbacks = by_id(itinerary.fallback_plans)

    # Evidence existence and freshness.
    referenced: Set[str] = set()
    for section in (itinerary.activities, itinerary.reservations, itinerary.transfers):
        for item in section:
            referenced.update(_source_ids(item))
    for source_id in sorted(referenced):
        source = sources.get(source_id)
        if source is None:
            issues.append(
                Issue(
                    "EVIDENCE_MISSING",
                    "error",
                    source_id,
                    "Referenced evidence is not defined.",
                    "Every cited source_id must resolve.",
                )
            )
            continue
        checked = source.get("checked_at")
        freshness = source.get("freshness_days")
        if not isinstance(checked, str) or not isinstance(freshness, int):
            issues.append(
                Issue(
                    "EVIDENCE_MISSING",
                    "error",
                    source_id,
                    "Evidence lacks checked_at or freshness_days.",
                    "Evidence must declare when it was checked and its freshness policy.",
                    (source_id,),
                )
            )
            continue
        checked_at = itinerary.local_datetime(checked)
        age = itinerary.planning_as_of - checked_at
        if age > timedelta(days=freshness):
            issues.append(
                Issue(
                    "EVIDENCE_STALE",
                    "warning",
                    source_id,
                    f"Evidence is {age.days} days old; policy allows {freshness} days.",
                    "planning_as_of - checked_at <= freshness_days",
                    (source_id,),
                )
            )

    # Opening windows and closures.
    for activity in itinerary.activities:
        if activity.get("opening_windows") and not _activity_is_open(
            itinerary, activity
        ):
            issues.append(
                Issue(
                    "ACTIVITY_CLOSED",
                    "error",
                    str(activity["id"]),
                    "Activity is outside its opening window or falls on a closure date.",
                    "The full activity interval must fit one local opening window.",
                    _source_ids(activity),
                )
            )

    # Required bookings.
    for activity in itinerary.activities:
        if not activity.get("booking_required"):
            continue
        reservation_id = activity.get("reservation_id")
        reservation = reservations.get(str(reservation_id))
        if reservation is None or not reservation.get("booked"):
            issues.append(
                Issue(
                    "BOOKING_MISSING",
                    "error",
                    str(activity["id"]),
                    "Required booking is absent or not confirmed.",
                    "booking_required implies a booked reservation_id.",
                    _source_ids(activity),
                )
            )

    # Reservation overlaps use half-open intervals, so touching boundaries are valid.
    booked = [item for item in itinerary.reservations if item.get("booked")]
    for index, left in enumerate(booked):
        left_start = itinerary.local_datetime(str(left["start"]))
        left_end = itinerary.local_datetime(str(left["end"]))
        for right in booked[index + 1 :]:
            right_start = itinerary.local_datetime(str(right["start"]))
            right_end = itinerary.local_datetime(str(right["end"]))
            if _overlap(left_start, left_end, right_start, right_end):
                issues.append(
                    Issue(
                        "RESERVATION_OVERLAP",
                        "error",
                        f"{left['id']}+{right['id']}",
                        "Confirmed reservation windows overlap.",
                        "Confirmed reservations use non-overlapping half-open intervals.",
                        tuple(sorted(set(_source_ids(left) + _source_ids(right)))),
                    )
                )

    # Transfer feasibility and endpoint consistency.
    transfer_pairs: Set[Tuple[str, str]] = set()
    for transfer in itinerary.transfers:
        from_id, to_id = (
            str(transfer["from_activity_id"]),
            str(transfer["to_activity_id"]),
        )
        transfer_pairs.add((from_id, to_id))
        transfer_left = activities.get(from_id)
        transfer_right = activities.get(to_id)
        if transfer_left is None or transfer_right is None:
            issues.append(
                Issue(
                    "TRANSFER_IMPOSSIBLE",
                    "error",
                    str(transfer["id"]),
                    "Transfer references an unknown activity.",
                    "Both transfer endpoints must resolve.",
                    _source_ids(transfer),
                )
            )
            continue
        left_end = itinerary.local_datetime(str(transfer_left["end"]))
        right_start = itinerary.local_datetime(str(transfer_right["start"]))
        depart_after = itinerary.local_datetime(str(transfer["depart_after"]))
        arrive_by = itinerary.local_datetime(str(transfer["arrive_by"]))
        departure = max(left_end, depart_after)
        arrival = departure + timedelta(minutes=int(transfer["duration_minutes"]))
        deadline = min(
            arrive_by,
            right_start
            - timedelta(minutes=int(transfer["minimum_connection_minutes"])),
        )
        if arrival > deadline:
            shortfall = math.ceil((arrival - deadline).total_seconds() / 60)
            issues.append(
                Issue(
                    "TRANSFER_IMPOSSIBLE",
                    "error",
                    str(transfer["id"]),
                    f"Transfer misses its usable arrival deadline by {shortfall} minutes.",
                    "departure + duration <= min(arrive_by, next_start - minimum_connection)",
                    _source_ids(transfer),
                )
            )
        from_place, to_place = (
            places[str(transfer_left["place_id"])],
            places[str(transfer_right["place_id"])],
        )
        declared = float(transfer.get("distance_km", 0))
        direct = _haversine_km(from_place, to_place)
        if declared + 0.1 < direct:
            issues.append(
                Issue(
                    "GEO_ORDER_INCOMPATIBLE",
                    "error",
                    str(transfer["id"]),
                    f"Declared route distance {declared:.1f} km is shorter than the {direct:.1f} km straight-line lower bound.",
                    "route distance must be at least the great-circle distance",
                    _source_ids(transfer),
                )
            )

    ordered = sorted(
        itinerary.activities, key=lambda item: (str(item["start"]), str(item["id"]))
    )
    for left, right in zip(ordered, ordered[1:]):
        pair = (str(left["id"]), str(right["id"]))
        if left["place_id"] != right["place_id"] and pair not in transfer_pairs:
            issues.append(
                Issue(
                    "GEO_ORDER_INCOMPATIBLE",
                    "warning",
                    f"{left['id']}->{right['id']}",
                    "Consecutive activities change place without a transfer constraint.",
                    "Every place change in schedule order needs an explicit transfer.",
                )
            )

    # Fragile dependencies must name a real fallback whose activation is explicit.
    for activity in itinerary.activities:
        if not activity.get("fragile"):
            continue
        fallback_id = activity.get("fallback_plan_id")
        fallback = fallbacks.get(str(fallback_id))
        if fallback is None or not fallback.get("activation_condition"):
            issues.append(
                Issue(
                    "FALLBACK_MISSING",
                    "warning",
                    str(activity["id"]),
                    "Fragile activity has no usable fallback plan.",
                    "fragile activities need a fallback with an activation condition.",
                    _source_ids(activity),
                )
            )

    # Conflicting source facts are surfaced, never averaged into false precision.
    fact_values: Dict[Tuple[str, str], Dict[str, List[str]]] = {}
    for source in itinerary.sources:
        for fact in source.get("facts", []):
            key = (str(fact.get("subject")), str(fact.get("field")))
            value = str(fact.get("value"))
            fact_values.setdefault(key, {}).setdefault(value, []).append(
                str(source["id"])
            )
    for (subject, field), values in sorted(fact_values.items()):
        if len(values) > 1:
            ids = tuple(
                sorted(
                    source_id for grouped in values.values() for source_id in grouped
                )
            )
            rendered = ", ".join(sorted(values))
            issues.append(
                Issue(
                    "FACT_CONFLICT",
                    "warning",
                    f"{subject}.{field}",
                    f"Sources disagree: {rendered}.",
                    "Facts with the same subject and field must agree or be resolved explicitly.",
                    ids,
                )
            )

    return sorted(issues, key=lambda issue: issue.sort_key)


def count_by_severity(issues: Iterable[Issue]) -> Dict[str, int]:
    counts = {"error": 0, "warning": 0}
    for issue in issues:
        counts[issue.severity] = counts.get(issue.severity, 0) + 1
    return counts
