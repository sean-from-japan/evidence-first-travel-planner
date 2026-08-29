from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict

from evidence_travel.model import Itinerary, load_itinerary

ROOT = Path(__file__).resolve().parents[1]


def example_data() -> Dict[str, Any]:
    return json.loads(
        (ROOT / "examples" / "fictional_trip.json").read_text(encoding="utf-8")
    )


def itinerary_from_data(tmp_path: Path, data: Dict[str, Any]) -> Itinerary:
    path = tmp_path / "itinerary.json"
    path.write_text(json.dumps(copy.deepcopy(data)), encoding="utf-8")
    return load_itinerary(path)
