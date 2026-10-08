from __future__ import annotations

from typing import Any

from mcp.protocol import ToolSpec
from services.scheduling import HALL_CAPACITIES, hall_label

TOOL_NAME = "venue_capacity_validator"


def run_venue_capacity_validator(arguments: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    raw_capacity = arguments.get("capacity")
    try:
        capacity = int(raw_capacity) if raw_capacity is not None and str(raw_capacity).strip() else None
    except (TypeError, ValueError):
        capacity = None
        issues.append("Hall capacity must be a number.")

    date = str(arguments.get("date") or "").strip() or None
    start_time = str(arguments.get("start_time") or "").strip() or None
    end_time = str(arguments.get("end_time") or "").strip() or None
    exclude_event_id = str(arguments.get("exclude_event_id") or "").strip() or None

    hall_ok = capacity in HALL_CAPACITIES
    if capacity is not None and not hall_ok:
        issues.append("Hall capacity must be 50, 100, or 300 seats.")

    conflict = None
    if hall_ok and date and start_time and end_time:
        try:
            from cqrs.store import EventStore

            event = EventStore().find_hall_conflict(
                capacity,
                date,
                start_time,
                end_time,
                exclude_event_id=exclude_event_id,
            )
        except Exception as exc:
            event = None
            issues.append(f"Could not check hall schedule: {exc}")
        if event is not None:
            conflict = {
                "id": event.id,
                "title": event.title,
                "date": event.date,
                "start_time": event.start_time,
                "end_time": event.end_time,
                "capacity": event.capacity,
            }
            issues.append(
                f'Hall {hall_label(capacity)} is already booked for "{event.title}" '
                f"on {event.date} {event.start_time}–{event.end_time}."
            )

    return {
        "tool": TOOL_NAME,
        "valid": not issues,
        "hall_ok": hall_ok,
        "capacity": capacity,
        "hall_label": hall_label(capacity) if capacity else None,
        "allowed_capacities": list(HALL_CAPACITIES),
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "conflict": conflict,
        "issues": issues,
    }


def venue_capacity_validator_tool() -> ToolSpec:
    return ToolSpec(
        name=TOOL_NAME,
        description=(
            "Validate event hall seat capacity (50/100/300) and detect scheduling "
            "conflicts for the requested date and time."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "capacity": {"type": "integer"},
                "date": {"type": "string"},
                "start_time": {"type": "string"},
                "end_time": {"type": "string"},
                "exclude_event_id": {"type": "string"},
            },
            "required": ["capacity"],
        },
        handler=run_venue_capacity_validator,
    )
