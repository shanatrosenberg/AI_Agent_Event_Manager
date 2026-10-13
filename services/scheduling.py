from __future__ import annotations

import re
from datetime import date as date_cls, datetime, timezone

HALL_CAPACITIES = (50, 100, 300)
HALL_LABELS = {
    50: "Conference Room (50 seats)",
    100: "Grand Hall (100 seats)",
    300: "Main Auditorium (300 seats)",
}
BOOKABLE_STATUSES = ("active", "approved")
APPROVED_STATUSES = ("approved", "active")
CANCELLED_STATUS = "cancelled"
DELETED_STATUS = "deleted"
REMOVED_STATUSES = (CANCELLED_STATUS, DELETED_STATUS)
ORGANIZER_EVENT_STATUSES = APPROVED_STATUSES + REMOVED_STATUSES
CLOCK_PATTERN = re.compile(r"^(\d{1,2}):(\d{2})(?::\d{2})?$")
SLOT_MINUTES = 30
SESSION_DURATION_MINUTES = 90
FIRST_START_MINUTES = 8 * 60
LAST_START_MINUTES = 22 * 60


def hall_label(capacity: int | None) -> str:
    if capacity in HALL_LABELS:
        return HALL_LABELS[capacity]
    return f"{capacity} seats" if capacity else "Unassigned hall"


def parse_clock(value: str, field_name: str) -> str:
    raw = (value or "").strip()
    match = CLOCK_PATTERN.fullmatch(raw)
    if not match:
        raise ValueError(f"{field_name} must be a time in HH:MM format")
    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour > 23 or minute > 59:
        raise ValueError(f"{field_name} must be a valid 24-hour time")
    return f"{hour:02d}:{minute:02d}"


def clock_minutes(value: str) -> int:
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def clock_from_minutes(total: int) -> str:
    return f"{total // 60:02d}:{total % 60:02d}"


def is_half_hour_slot(value: str) -> bool:
    try:
        return clock_minutes(parse_clock(value, "start_time")) % SLOT_MINUTES == 0
    except ValueError:
        return False


def add_clock_minutes(value: str, minutes: int, field_name: str = "end_time") -> str:
    total = clock_minutes(parse_clock(value, field_name)) + minutes
    if total < 0 or total >= 24 * 60:
        raise ValueError("end_time must stay on the same day")
    return clock_from_minutes(total)


def session_end_time(start_time: str) -> str:
    start = parse_clock(start_time, "start_time")
    if clock_minutes(start) % SLOT_MINUTES != 0:
        raise ValueError("start_time must be on the hour or half hour.")
    return add_clock_minutes(start, SESSION_DURATION_MINUTES)


def start_time_slots() -> list[str]:
    slots = []
    for minutes in range(FIRST_START_MINUTES, LAST_START_MINUTES + 1, SLOT_MINUTES):
        start = clock_from_minutes(minutes)
        try:
            session_end_time(start)
        except ValueError:
            continue
        slots.append(start)
    return slots


def clocks_overlap(start_a: str, end_a: str, start_b: str, end_b: str) -> bool:
    return clock_minutes(start_a) < clock_minutes(end_b) and clock_minutes(start_b) < clock_minutes(end_a)


def parse_event_date(value: str) -> date_cls | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return date_cls.fromisoformat(raw[:10])
    except ValueError:
        return None


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def has_occurred(date_value: str, end_time: str | None = None, now: datetime | None = None) -> bool:
    day = parse_event_date(date_value)
    if day is None:
        return False
    current = now or utc_now()
    today = current.date()
    if day < today:
        return True
    if day > today:
        return False
    if not end_time:
        return False
    try:
        end = parse_clock(end_time, "end_time")
    except ValueError:
        return False
    return clock_minutes(end) <= current.hour * 60 + current.minute


def normalize_schedule(date: str, start_time: str, end_time: str, capacity: int) -> tuple[str, str, str, int]:
    day = (date or "").strip()
    if not day:
        raise ValueError("date cannot be empty")
    if capacity not in HALL_CAPACITIES:
        raise ValueError("Hall capacity must be 50, 100, or 300 seats.")
    start = parse_clock(start_time, "start_time")
    if clock_minutes(start) % SLOT_MINUTES != 0:
        raise ValueError("start_time must be on the hour or half hour.")
    end = session_end_time(start)
    return day, start, end, capacity
