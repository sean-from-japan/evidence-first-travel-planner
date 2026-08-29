from __future__ import annotations

from datetime import datetime, timedelta

from evidence_travel.validator import _activity_is_open, _overlap, validate
from tests.helpers import example_data, itinerary_from_data


def test_fictional_example_exercises_every_required_failure_class(tmp_path):
    issues = validate(itinerary_from_data(tmp_path, example_data()))
    codes = {issue.code for issue in issues}
    assert {
        "EVIDENCE_STALE",
        "EVIDENCE_MISSING",
        "ACTIVITY_CLOSED",
        "TRANSFER_IMPOSSIBLE",
        "RESERVATION_OVERLAP",
        "BOOKING_MISSING",
        "GEO_ORDER_INCOMPATIBLE",
        "FALLBACK_MISSING",
        "FACT_CONFLICT",
    } <= codes
    assert all(issue.constraint for issue in issues)


def test_half_open_reservation_boundary_has_no_overlap():
    start = datetime.fromisoformat("2032-05-03T09:00:00+02:00")
    boundary = start + timedelta(hours=1)
    end = boundary + timedelta(hours=1)
    assert not _overlap(start, boundary, boundary, end)
    assert _overlap(start, end, boundary, end)


def test_overlap_is_cross_checked_with_minute_set_oracle():
    start = datetime.fromisoformat("2032-05-03T09:00:00+02:00")
    for left_duration, right_offset, right_duration in [
        (30, 30, 20),
        (31, 30, 1),
        (80, 20, 5),
    ]:
        left_end = start + timedelta(minutes=left_duration)
        right_start = start + timedelta(minutes=right_offset)
        right_end = right_start + timedelta(minutes=right_duration)
        left_minutes = set(range(0, left_duration))
        right_minutes = set(range(right_offset, right_offset + right_duration))
        oracle = bool(left_minutes & right_minutes)
        assert _overlap(start, left_end, right_start, right_end) is oracle


def test_overnight_opening_window_accepts_activity_after_midnight(tmp_path):
    data = example_data()
    activity = data["activities"][1]
    activity["start"] = "2032-05-04T00:15:00+02:00"
    activity["end"] = "2032-05-04T01:00:00+02:00"
    activity["opening_windows"] = [
        {"days": ["Mon"], "opens": "22:00", "closes": "02:00"}
    ]
    itinerary = itinerary_from_data(tmp_path, data)
    assert _activity_is_open(itinerary, itinerary.activities[1])


def test_closing_time_is_exclusive_for_activity_end(tmp_path):
    data = example_data()
    activity = data["activities"][1]
    activity["start"] = "2032-05-03T17:00:00+02:00"
    activity["end"] = "2032-05-03T18:00:00+02:00"
    itinerary = itinerary_from_data(tmp_path, data)
    assert _activity_is_open(itinerary, itinerary.activities[1])


def test_transfer_shortfall_matches_epoch_arithmetic_oracle(tmp_path):
    itinerary = itinerary_from_data(tmp_path, example_data())
    issue = next(
        item for item in validate(itinerary) if item.code == "TRANSFER_IMPOSSIBLE"
    )
    transfer = itinerary.transfers[0]
    preceding_end = itinerary.local_datetime(str(itinerary.activities[1]["end"]))
    depart_after = itinerary.local_datetime(str(transfer["depart_after"]))
    departure_epoch = max(preceding_end.timestamp(), depart_after.timestamp())
    arrival_epoch = departure_epoch + int(transfer["duration_minutes"]) * 60
    next_start = itinerary.local_datetime(
        str(itinerary.activities[3]["start"])
    ).timestamp()
    arrive_by = itinerary.local_datetime(str(transfer["arrive_by"])).timestamp()
    deadline_epoch = min(
        arrive_by, next_start - int(transfer["minimum_connection_minutes"]) * 60
    )
    oracle_shortfall = int((arrival_epoch - deadline_epoch + 59) // 60)
    assert f"{oracle_shortfall} minutes" in issue.message
