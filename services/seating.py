"""Hall seating maps sized to the 50 / 100 / 300 seat venues."""

from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy import inspect, text

from extensions import db

HALL_LAYOUTS: dict[int, dict[str, int]] = {
    50: {"rows": 5, "cols": 10, "aisle_after": 5},
    100: {"rows": 10, "cols": 10, "aisle_after": 5},
    300: {"rows": 15, "cols": 20, "aisle_after": 10},
}


def hall_layout(capacity: int | None) -> dict[str, int]:
    if capacity in HALL_LAYOUTS:
        return dict(HALL_LAYOUTS[capacity])
    total = max(0, int(capacity or 0))
    cols = 10
    rows = max(1, (total + cols - 1) // cols) if total else 1
    return {"rows": rows, "cols": cols, "aisle_after": cols // 2}


def seat_id(row_index: int, col_index: int) -> str:
    return f"{chr(ord('A') + row_index)}{col_index + 1}"


def hall_seat_ids(capacity: int | None) -> list[str]:
    layout = hall_layout(capacity)
    seats: list[str] = []
    total = int(capacity or 0)
    for row in range(layout["rows"]):
        for col in range(layout["cols"]):
            if len(seats) >= total:
                return seats
            seats.append(seat_id(row, col))
    return seats


def normalize_seat_ids(raw: Any) -> list[str]:
    if raw in (None, ""):
        return []
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("[") and text.endswith("]"):
            try:
                import json

                parsed = json.loads(text)
                return normalize_seat_ids(parsed)
            except ValueError:
                pass
        values = [part.strip() for part in text.replace(";", ",").split(",")]
    elif isinstance(raw, (list, tuple, set)):
        values = [str(item).strip() for item in raw]
    else:
        return []
    seen: set[str] = set()
    seats: list[str] = []
    for value in values:
        label = value.upper().replace(" ", "")
        if not label or label in seen:
            continue
        seen.add(label)
        seats.append(label)
    return seats


def reserved_seat_ids(event) -> set[str]:
    if event is None:
        return set()
    layout = hall_seat_ids(event.capacity)
    taken: set[str] = set()
    unlabeled = 0
    bookings = [
        booking
        for booking in (event.bookings or [])
        if (booking.status or "confirmed") == "confirmed"
    ]
    for booking in bookings:
        labels = normalize_seat_ids(getattr(booking, "seat_labels", None))
        if labels:
            taken.update(labels)
        else:
            unlabeled += int(booking.seats or 0)
    if unlabeled:
        for seat in layout:
            if unlabeled <= 0:
                break
            if seat in taken:
                continue
            taken.add(seat)
            unlabeled -= 1
    return taken


def assign_open_seats(capacity: int | None, taken: Iterable[str], count: int) -> list[str]:
    reserved = {str(item).upper() for item in taken}
    open_seats = [seat for seat in hall_seat_ids(capacity) if seat not in reserved]
    if count > len(open_seats):
        return []
    return open_seats[:count]


def seating_map_payload(event) -> dict[str, Any]:
    layout = hall_layout(event.capacity)
    taken = reserved_seat_ids(event)
    seats = []
    for index, label in enumerate(hall_seat_ids(event.capacity)):
        row = index // layout["cols"]
        col = index % layout["cols"]
        seats.append(
            {
                "id": label,
                "row": chr(ord("A") + row),
                "number": col + 1,
                "available": label not in taken,
            }
        )
    return {
        "event_id": event.id,
        "capacity": event.capacity,
        "hall_label": event.hall_label,
        "rows": layout["rows"],
        "cols": layout["cols"],
        "aisle_after": layout["aisle_after"],
        "taken": sorted(taken),
        "available_count": event.remaining_seats,
        "seats": seats,
    }


def ensure_booking_seat_schema() -> None:
    inspector = inspect(db.engine)
    if "bookings" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("bookings")}
    if "seat_labels" in columns:
        return
    dialect = db.engine.dialect.name
    if dialect == "sqlite":
        db.session.execute(text("ALTER TABLE bookings ADD COLUMN seat_labels TEXT"))
    else:
        db.session.execute(text("ALTER TABLE bookings ADD seat_labels NVARCHAR(MAX) NULL"))
    db.session.commit()
