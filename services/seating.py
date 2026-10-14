"""Hall seating maps sized to the 50 / 100 / 300 seat venues."""

from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy import inspect, text

from extensions import db
from services.scheduling import hall_label

HALL_LAYOUTS: dict[int, dict[str, object]] = {
    50: {
        "rows": 5,
        "cols": 10,
        "aisles_after": [5],
        "sections": (("Left", 5), ("Right", 5)),
    },
    100: {
        "rows": 10,
        "cols": 10,
        "aisles_after": [],
        "row_aisles_after": [5],
        "sections": (),
    },
    300: {
        "rows": 15,
        "cols": 20,
        "aisles_after": [6, 14],
        "row_aisles_after": [7],
        "sections": (("Left", 6), ("Center", 8), ("Right", 6)),
    },
}


def hall_layout(capacity: int | None) -> dict[str, object]:
    if capacity in HALL_LAYOUTS:
        layout = dict(HALL_LAYOUTS[capacity])
        aisles = list(layout.get("aisles_after") or [])
        layout["aisles_after"] = aisles
        layout["aisle_after"] = aisles[0] if aisles else 0
        layout["row_aisles_after"] = list(layout.get("row_aisles_after") or [])
        return layout
    total = max(0, int(capacity or 0))
    cols = 10
    rows = max(1, (total + cols - 1) // cols) if total else 1
    aisle = cols // 2
    return {
        "rows": rows,
        "cols": cols,
        "aisles_after": [aisle],
        "aisle_after": aisle,
        "row_aisles_after": [rows // 2] if rows > 2 else [],
        "sections": (("Left", aisle), ("Right", cols - aisle)),
    }


def hall_configuration(capacity: int | None) -> dict[str, Any]:
    layout = hall_layout(capacity)
    raw_sections = layout.get("sections") or ()
    if raw_sections and isinstance(raw_sections[0], dict):
        section_names = [str(item.get("name") or "").strip() for item in raw_sections if item.get("name")]
    else:
        section_names = [str(name).strip() for name, _width in raw_sections if name]
    vertical = [int(item) for item in (layout.get("aisles_after") or []) if int(item) > 0]
    cross = [int(item) for item in (layout.get("row_aisles_after") or []) if int(item) > 0]
    parts = [hall_label(capacity), f"{layout['rows']}×{layout['cols']} grid"]
    if section_names:
        parts.append(f"{' / '.join(section_names)} sections")
    if vertical:
        parts.append("vertical aisles after columns " + ", ".join(str(item) for item in vertical))
    else:
        parts.append("no vertical aisles")
    if cross:
        after_rows = ", ".join(chr(ord("A") + item - 1) for item in cross if item > 0)
        parts.append(f"mid-house cross-aisle after row {after_rows}" if after_rows else "mid-house cross-aisle")
    return {
        "capacity": capacity,
        "hall_label": hall_label(capacity),
        "rows": layout["rows"],
        "cols": layout["cols"],
        "sections": section_names,
        "aisles_after": vertical,
        "row_aisles_after": cross,
        "description": " · ".join(parts),
    }


def seat_id(row_index: int, col_index: int) -> str:
    return f"{chr(ord('A') + row_index)}{col_index + 1}"


def hall_seat_ids(capacity: int | None) -> list[str]:
    layout = hall_layout(capacity)
    seats: list[str] = []
    total = int(capacity or 0)
    for row in range(int(layout["rows"])):
        for col in range(int(layout["cols"])):
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


def owned_seat_ids(event, attendee_id: str | None) -> set[str]:
    user = str(attendee_id or "").strip()
    if not user or event is None:
        return set()
    owned: set[str] = set()
    for booking in event.bookings or []:
        if (booking.status or "confirmed") != "confirmed":
            continue
        if str(booking.attendee_id or "").strip() != user:
            continue
        labels = normalize_seat_ids(getattr(booking, "seat_labels", None))
        if labels:
            owned.update(labels)
    return owned


def assign_open_seats(capacity: int | None, taken: Iterable[str], count: int) -> list[str]:
    reserved = {str(item).upper() for item in taken}
    open_seats = [seat for seat in hall_seat_ids(capacity) if seat not in reserved]
    if count > len(open_seats):
        return []
    return open_seats[:count]


def seating_map_payload(event, attendee_id: str | None = None) -> dict[str, Any]:
    layout = hall_layout(event.capacity)
    taken = reserved_seat_ids(event)
    owned = owned_seat_ids(event, attendee_id)
    seats = []
    cols = int(layout["cols"])
    for index, label in enumerate(hall_seat_ids(event.capacity)):
        row = index // cols
        col = index % cols
        seats.append(
            {
                "id": label,
                "row": chr(ord("A") + row),
                "number": col + 1,
                "available": label not in taken,
                "owned": label in owned,
            }
        )
    aisles = [int(item) for item in (layout.get("aisles_after") or []) if int(item) > 0]
    row_aisles = [int(item) for item in (layout.get("row_aisles_after") or []) if int(item) > 0]
    sections = [
        {"name": name, "cols": int(width)}
        for name, width in (layout.get("sections") or ())
    ]
    return {
        "event_id": event.id,
        "capacity": event.capacity,
        "hall_label": event.hall_label,
        "rows": layout["rows"],
        "cols": layout["cols"],
        "aisle_after": aisles[0] if aisles else 0,
        "aisles_after": aisles,
        "row_aisles_after": row_aisles,
        "sections": sections,
        "taken": sorted(taken),
        "owned": sorted(owned),
        "owned_count": len(owned),
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
