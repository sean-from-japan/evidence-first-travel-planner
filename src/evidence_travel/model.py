"""Input loading and deliberately small schema validation."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class InputError(ValueError):
    """Raised when an itinerary cannot be parsed safely."""


@dataclass(frozen=True)
class Itinerary:
    raw: Mapping[str, Any]
    timezone: ZoneInfo
    planning_as_of: datetime

    @property
    def sources(self) -> Sequence[Mapping[str, Any]]:
        return cast(Sequence[Mapping[str, Any]], self.raw["sources"])

    @property
    def places(self) -> Sequence[Mapping[str, Any]]:
        return cast(Sequence[Mapping[str, Any]], self.raw["places"])

    @property
    def activities(self) -> Sequence[Mapping[str, Any]]:
        return cast(Sequence[Mapping[str, Any]], self.raw["activities"])

    @property
    def reservations(self) -> Sequence[Mapping[str, Any]]:
        return cast(Sequence[Mapping[str, Any]], self.raw["reservations"])

    @property
    def transfers(self) -> Sequence[Mapping[str, Any]]:
        return cast(Sequence[Mapping[str, Any]], self.raw["transfers"])

    @property
    def fallback_plans(self) -> Sequence[Mapping[str, Any]]:
        return cast(Sequence[Mapping[str, Any]], self.raw["fallback_plans"])

    def local_datetime(self, value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise InputError(f"datetime lacks UTC offset: {value}")
        return parsed.astimezone(self.timezone)


def _require_list(data: Mapping[str, Any], key: str) -> List[Mapping[str, Any]]:
    value = data.get(key)
    if not isinstance(value, list):
        raise InputError(f"{key} must be an array")
    if not all(isinstance(item, dict) for item in value):
        raise InputError(f"every {key} item must be an object")
    return value


def _unique_ids(items: Sequence[Mapping[str, Any]], section: str) -> None:
    ids: List[str] = []
    for item in items:
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            raise InputError(f"every {section} item needs a non-empty string id")
        ids.append(item_id)
    if len(ids) != len(set(ids)):
        raise InputError(f"{section} ids must be unique")


def load_itinerary(path: Path) -> Itinerary:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"invalid JSON at line {exc.lineno}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise InputError("itinerary root must be an object")

    schema_version = data.get("schema_version")
    if schema_version != "1.0":
        raise InputError("schema_version must be '1.0'")
    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        raise InputError("metadata must be an object")
    zone_name = metadata.get("timezone")
    if not isinstance(zone_name, str):
        raise InputError("metadata.timezone must be an IANA time-zone name")
    try:
        timezone = ZoneInfo(zone_name)
    except ZoneInfoNotFoundError as exc:
        raise InputError(f"unknown time zone: {zone_name}") from exc
    as_of_raw = metadata.get("planning_as_of")
    if not isinstance(as_of_raw, str):
        raise InputError("metadata.planning_as_of must be an ISO 8601 datetime")
    try:
        planning_as_of = datetime.fromisoformat(as_of_raw)
    except ValueError as exc:
        raise InputError("metadata.planning_as_of is not ISO 8601") from exc
    if planning_as_of.tzinfo is None:
        raise InputError("metadata.planning_as_of must include a UTC offset")

    sections = [
        "sources",
        "places",
        "activities",
        "reservations",
        "transfers",
        "fallback_plans",
    ]
    for section in sections:
        _unique_ids(_require_list(data, section), section)

    for activity in data["activities"]:
        for field in ("name", "place_id", "start", "end"):
            if not isinstance(activity.get(field), str):
                raise InputError(f"activity {activity['id']} needs string {field}")
        start = datetime.fromisoformat(activity["start"])
        end = datetime.fromisoformat(activity["end"])
        if start.tzinfo is None or end.tzinfo is None:
            raise InputError(f"activity {activity['id']} times need UTC offsets")
        if end <= start:
            raise InputError(f"activity {activity['id']} must end after it starts")

    return Itinerary(data, timezone, planning_as_of.astimezone(timezone))


def by_id(items: Sequence[Mapping[str, Any]]) -> Dict[str, Mapping[str, Any]]:
    return {str(item["id"]): item for item in items}
