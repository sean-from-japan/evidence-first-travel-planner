"""Optional live-data boundaries; the core never imports a provider SDK."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Tuple


@dataclass(frozen=True)
class RouteObservation:
    duration_minutes: int
    distance_km: float
    checked_at: datetime
    source_reference: str


@dataclass(frozen=True)
class PlaceObservation:
    coordinates: Tuple[float, float]
    checked_at: datetime
    source_reference: str


class RouteProvider(Protocol):
    def route(self, origin: str, destination: str, mode: str) -> RouteObservation: ...


class PlaceProvider(Protocol):
    def resolve(self, query: str) -> PlaceObservation: ...
