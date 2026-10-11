from services.seating import assign_open_seats, hall_seat_ids, normalize_seat_ids


def test_hall_maps_match_standard_capacities():
    assert hall_seat_ids(50)[0] == "A1"
    assert hall_seat_ids(50)[-1] == "E10"
    assert len(hall_seat_ids(50)) == 50
    assert len(hall_seat_ids(100)) == 100
    assert hall_seat_ids(100)[-1] == "J10"
    assert len(hall_seat_ids(300)) == 300
    assert hall_seat_ids(300)[-1] == "O20"


def test_nonstandard_capacity_still_fills_the_grid():
    assert len(hall_seat_ids(25)) == 25
    assert hall_seat_ids(25)[-1] == "C5"


def test_normalize_and_assign_open_seats():
    assert normalize_seat_ids("a1, B3, a1") == ["A1", "B3"]
    assert normalize_seat_ids('["c2", "C2", "D4"]') == ["C2", "D4"]
    assert assign_open_seats(50, {"A1", "A2"}, 2) == ["A3", "A4"]
    assert assign_open_seats(50, set(hall_seat_ids(50)), 1) == []
