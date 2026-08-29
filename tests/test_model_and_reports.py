from __future__ import annotations

import json

import pytest

from evidence_travel.model import InputError
from evidence_travel.report import render_html, render_markdown, summary
from evidence_travel.validator import validate
from tests.helpers import ROOT, example_data, itinerary_from_data


def test_schema_document_is_parseable_and_declares_all_sections():
    schema = json.loads(
        (ROOT / "schemas" / "itinerary.schema.json").read_text(encoding="utf-8")
    )
    assert schema["$schema"].endswith("2020-12/schema")
    assert set(schema["required"]) == {
        "schema_version",
        "metadata",
        "sources",
        "places",
        "activities",
        "reservations",
        "transfers",
        "fallback_plans",
    }


def test_windows_timezone_fallback_is_pinned():
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "tzdata==2026.3; platform_system == 'Windows'" in project


def test_duplicate_ids_are_rejected(tmp_path):
    data = example_data()
    data["places"].append(dict(data["places"][0]))
    with pytest.raises(InputError, match="places ids must be unique"):
        itinerary_from_data(tmp_path, data)


def test_offsetless_activity_is_rejected(tmp_path):
    data = example_data()
    data["activities"][0]["start"] = "2032-05-03T08:00:00"
    with pytest.raises(InputError, match="times need UTC offsets"):
        itinerary_from_data(tmp_path, data)


def test_outputs_are_deterministic_and_back_reference_evidence(tmp_path):
    itinerary = itinerary_from_data(tmp_path, example_data())
    first = validate(itinerary)
    second = validate(itinerary)
    assert summary(first) == summary(second)
    markdown = render_markdown(itinerary, first)
    assert markdown == render_markdown(itinerary, second)
    assert "src_city_museum" in markdown
    page = render_html(itinerary, first)
    assert '<meta charset="utf-8">' in page
    assert 'name="viewport"' in page
    assert "validation-summary" in page
