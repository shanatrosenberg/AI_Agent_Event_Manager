from __future__ import annotations

import re

HALL_CAPACITIES = (50, 100, 300)
HALL_LABELS = {
    50: "50 seats",
    100: "100 seats",
    300: "300 seats",
}
BOOKABLE_STATUSES = ("active", "approved")
APPROVED_STATUSES = ("approved", "active")
CLOCK_PATTERN = re.compile(r"^(\d{1,2}):(\d{2})(?::\d{2})?$")


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


def clocks_overlap(start_a: str, end_a: str, start_b: str, end_b: str) -> bool:
    return clock_minutes(start_a) < clock_minutes(end_b) and clock_minutes(start_b) < clock_minutes(end_a)


def normalize_schedule(date: str, start_time: str, end_time: str, capacity: int) -> tuple[str, str, str, int]:
    day = (date or "").strip()
    if not day:
        raise ValueError("date cannot be empty")
    if capacity not in HALL_CAPACITIES:
        raise ValueError("Hall capacity must be 50, 100, or 300 seats.")
    start = parse_clock(start_time, "start_time")
    end = parse_clock(end_time, "end_time")
    if clock_minutes(start) >= clock_minutes(end):
        raise ValueError("end_time must be after start_time")
    return day, start, end, capacity
