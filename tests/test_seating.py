from types import SimpleNamespace

from services.group_seating import NOT_ENOUGH_SEATS, suggest_group_seats
from services.seating import assign_open_seats, hall_configuration, hall_layout, hall_seat_ids, normalize_seat_ids


def _fake_event(capacity, taken=(), remaining=None):
    labels = list(taken)
    bookings = []
    if labels:
        bookings.append(SimpleNamespace(status="confirmed", seat_labels=labels, seats=len(labels)))
    leftover = capacity - len(labels) if remaining is None else remaining
    return SimpleNamespace(capacity=capacity, remaining_seats=leftover, bookings=bookings)


def _section_of(capacity, seat_id):
    layout = hall_layout(capacity)
    cols = int(layout["cols"])
    aisles = [int(item) for item in (layout.get("aisles_after") or [])]
    cuts = [0] + aisles + [cols]
    number = int("".join(ch for ch in seat_id if ch.isdigit()))
    col = number - 1
    for start, end in zip(cuts, cuts[1:]):
        if start <= col < end:
            return (start, end)
    return None


def _row_band_of(capacity, seat_id):
    layout = hall_layout(capacity)
    rows = int(layout["rows"])
    cuts = [0] + [int(item) for item in (layout.get("row_aisles_after") or [])] + [rows]
    row = ord(seat_id[0]) - ord("A")
    for start, end in zip(cuts, cuts[1:]):
        if start <= row < end:
            return (start, end)
    return None


def test_hall_maps_match_standard_capacities():
    assert hall_seat_ids(50)[0] == "A1"
    assert hall_seat_ids(50)[-1] == "E10"
    assert len(hall_seat_ids(50)) == 50
    assert len(hall_seat_ids(100)) == 100
    assert hall_seat_ids(100)[-1] == "J10"
    assert len(hall_seat_ids(300)) == 300
    assert hall_seat_ids(300)[-1] == "O20"


def test_standard_halls_use_partitioned_aisles():
    compact = hall_layout(100)
    assert compact["aisles_after"] == []
    assert compact["row_aisles_after"] == [5]
    assert compact["sections"] == ()
    arena = hall_layout(300)
    assert arena["aisles_after"] == [6, 14]
    assert arena["row_aisles_after"] == [7]
    assert [section[0] for section in arena["sections"]] == ["Left", "Center", "Right"]


def test_hall_configuration_describes_layout():
    compact = hall_configuration(100)
    assert compact["hall_label"] == "Grand Hall (100 seats)"
    assert compact["rows"] == 10
    assert compact["cols"] == 10
    assert compact["aisles_after"] == []
    assert "mid-house" in compact["description"]
    arena = hall_configuration(300)
    assert arena["sections"] == ["Left", "Center", "Right"]
    assert "vertical aisles" in arena["description"]


def test_nonstandard_capacity_still_fills_the_grid():
    assert len(hall_seat_ids(25)) == 25
    assert hall_seat_ids(25)[-1] == "C5"


def test_normalize_and_assign_open_seats():
    assert normalize_seat_ids("a1, B3, a1") == ["A1", "B3"]
    assert normalize_seat_ids('["c2", "C2", "D4"]') == ["C2", "D4"]
    assert assign_open_seats(50, {"A1", "A2"}, 2) == ["A3", "A4"]
    assert assign_open_seats(50, set(hall_seat_ids(50)), 1) == []


def test_group_agent_blocks_oversized_request():
    event = _fake_event(50, remaining=3)
    result = suggest_group_seats(event, 8)
    assert result["ok"] is False
    assert result["status"] == 409
    assert NOT_ENOUGH_SEATS in result["error"]
    assert result["available_count"] == 3


def test_group_agent_requires_two_or_more_seats():
    result = suggest_group_seats(_fake_event(50), 1)
    assert result["ok"] is False
    assert result["status"] == 400


def test_group_agent_finds_compact_block_without_crossing_aisle():
    result = suggest_group_seats(_fake_event(50), 6)
    assert result["ok"] is True
    assert result["mode"] == "block"
    assert result["needs_confirm"] is False
    seats = result["seat_ids"]
    assert len(seats) == 6
    sections = {_section_of(50, seat) for seat in seats}
    bands = {_row_band_of(50, seat) for seat in seats}
    assert len(sections) == 1
    assert len(bands) == 1
    rows = {seat[0] for seat in seats}
    assert len(rows) >= 2


def test_group_agent_prefers_short_block_over_long_line():
    result = suggest_group_seats(_fake_event(100), 6)
    assert result["ok"] is True
    assert result["mode"] == "block"
    rows = {seat[0] for seat in result["seat_ids"]}
    assert len(rows) >= 2
    assert len({_row_band_of(100, seat) for seat in result["seat_ids"]}) == 1


def test_group_agent_disperses_across_nearby_rows_when_block_unavailable():
    taken = [seat for seat in hall_seat_ids(50) if seat not in {"A1", "A2", "B1", "B6"}]
    result = suggest_group_seats(_fake_event(50, taken), 4)
    assert result["ok"] is True
    assert result["mode"] == "dispersed"
    assert result["needs_confirm"] is True
    assert set(result["seat_ids"]) == {"A1", "A2", "B1", "B6"}
    assert "aisle" in result["message"].lower() or "nearby" in result["message"].lower()
