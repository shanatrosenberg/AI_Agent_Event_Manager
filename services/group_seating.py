"""Optional Smart Group Seating Agent: compact blocks, then nearby fallback."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Iterable

from services.seating import hall_layout, hall_seat_ids, reserved_seat_ids, seat_id

PREFERRED_LINE_MAX = 4
NOT_ENOUGH_SEATS = "There aren't enough places available for a group that size."


@dataclass(frozen=True)
class SeatCoord:
    row: int
    col: int
    label: str


def _section_ranges(cols: int, aisles_after: list[int]) -> list[tuple[int, int]]:
    cuts = [0] + sorted(int(item) for item in aisles_after if int(item) > 0) + [cols]
    return [(cuts[index], cuts[index + 1]) for index in range(len(cuts) - 1) if cuts[index + 1] > cuts[index]]


def _row_bands(rows: int, row_aisles_after: list[int]) -> list[tuple[int, int]]:
    cuts = [0] + sorted(int(item) for item in row_aisles_after if int(item) > 0) + [rows]
    return [(cuts[index], cuts[index + 1]) for index in range(len(cuts) - 1) if cuts[index + 1] > cuts[index]]


def _open_coords(capacity: int | None, taken: Iterable[str]) -> list[SeatCoord]:
    reserved = {str(item).upper() for item in taken}
    layout = hall_layout(capacity)
    cols = int(layout["cols"])
    coords = []
    for index, label in enumerate(hall_seat_ids(capacity)):
        if label in reserved:
            continue
        coords.append(SeatCoord(row=index // cols, col=index % cols, label=label))
    return coords


def _open_set(coords: list[SeatCoord]) -> set[tuple[int, int]]:
    return {(item.row, item.col) for item in coords}


def _label(row: int, col: int) -> str:
    return seat_id(row, col)


def _score_block(seats: list[SeatCoord], *, rows: int, cols: int, height: int, width: int, requested: int) -> int:
    row_span = max(item.row for item in seats) - min(item.row for item in seats) + 1
    col_span = max(item.col for item in seats) - min(item.col for item in seats) + 1
    mid = (min(item.col for item in seats) + max(item.col for item in seats)) / 2
    line_penalty = 80 if height == 1 and requested > PREFERRED_LINE_MAX else 0
    return (
        line_penalty
        + (height * width - requested) * 4
        + (row_span * col_span - requested) * 2
        + min(item.row for item in seats) * 3
        + int(abs(mid - (cols - 1) / 2) * 2)
    )


def _window_seats(open_cells: set[tuple[int, int]], row0: int, col0: int, height: int, width: int) -> list[SeatCoord]:
    found = []
    for row in range(row0, row0 + height):
        for col in range(col0, col0 + width):
            if (row, col) in open_cells:
                found.append(SeatCoord(row=row, col=col, label=_label(row, col)))
    return found


def _best_compact_block(
    coords: list[SeatCoord],
    requested: int,
    *,
    rows: int,
    cols: int,
    aisles_after: list[int],
    row_aisles_after: list[int],
) -> list[SeatCoord] | None:
    open_cells = _open_set(coords)
    best: tuple[int, list[SeatCoord]] | None = None
    for row0, row1 in _row_bands(rows, row_aisles_after):
        for col0, col1 in _section_ranges(cols, aisles_after):
            section_width = col1 - col0
            band_height = row1 - row0
            max_height = min(4, requested, band_height)
            for height in range(1, max_height + 1):
                width = ceil(requested / height)
                if width > section_width:
                    continue
                for row in range(row0, row1 - height + 1):
                    for col in range(col0, col1 - width + 1):
                        found = _window_seats(open_cells, row, col, height, width)
                        if len(found) < requested:
                            continue
                        chosen = found[:requested]
                        score = _score_block(
                            chosen,
                            rows=rows,
                            cols=cols,
                            height=height,
                            width=width,
                            requested=requested,
                        )
                        if best is None or score < best[0]:
                            best = (score, chosen)
    return None if best is None else best[1]


def _row_runs(coords: list[SeatCoord], row: int, col0: int, col1: int) -> list[list[SeatCoord]]:
    in_row = [item for item in coords if item.row == row and col0 <= item.col < col1]
    in_row.sort(key=lambda item: item.col)
    runs: list[list[SeatCoord]] = []
    current: list[SeatCoord] = []
    for seat in in_row:
        if current and seat.col != current[-1].col + 1:
            runs.append(current)
            current = []
        current.append(seat)
    if current:
        runs.append(current)
    return runs


def _run_mid(run: list[SeatCoord]) -> float:
    return (run[0].col + run[-1].col) / 2


def _disperse_nearby(
    coords: list[SeatCoord],
    requested: int,
    *,
    cols: int,
    aisles_after: list[int],
    row_aisles_after: list[int],
    rows: int,
) -> list[SeatCoord]:
    runs: list[list[SeatCoord]] = []
    for row0, row1 in _row_bands(rows, row_aisles_after):
        for col0, col1 in _section_ranges(cols, aisles_after):
            for row in range(row0, row1):
                runs.extend(_row_runs(coords, row, col0, col1))
    if not runs:
        center_col = (cols - 1) / 2
        ranked = sorted(coords, key=lambda item: (item.row, abs(item.col - center_col), item.col))
        return ranked[:requested]

    runs.sort(key=lambda run: (-len(run), run[0].row, run[0].col))
    picked: list[SeatCoord] = []
    used = set()
    first = runs[0]
    picked.extend(first[:requested])
    used.add(id(first))
    while len(picked) < requested:
        last_row = picked[-1].row
        last_mid = sum(item.col for item in picked) / len(picked)
        leftover = [run for run in runs if id(run) not in used]
        if not leftover:
            break
        leftover.sort(
            key=lambda run: (
                abs(run[0].row - last_row),
                abs(_run_mid(run) - last_mid),
                run[0].row,
            )
        )
        nxt = leftover[0]
        used.add(id(nxt))
        need = requested - len(picked)
        picked.extend(nxt[:need])
    if len(picked) < requested:
        have = {item.label for item in picked}
        extras = [item for item in coords if item.label not in have]
        extras.sort(key=lambda item: (abs(item.row - picked[-1].row), abs(item.col - picked[-1].col)))
        picked.extend(extras[: requested - len(picked)])
    return picked[:requested]


def _describe(seats: list[SeatCoord], mode: str) -> str:
    labels = [item.label for item in seats]
    rows = sorted({item.row for item in seats})
    letters = [chr(ord("A") + row) for row in rows]
    if mode == "block" and len(rows) == 1:
        return f"We found a compact block in row {letters[0]}: {', '.join(labels)}."
    if mode == "block":
        return f"We found a compact block in rows {'–'.join(letters)}: {', '.join(labels)}."
    if len(rows) == 1:
        return (
            f"We couldn't keep the group in one tight block. Suggested nearby seats in row {letters[0]}: "
            f"{', '.join(labels)}."
        )
    return (
        f"We couldn't keep the group in one block without crossing an aisle. "
        f"Suggested seats across rows {' and '.join(letters)}: {', '.join(labels)}."
    )


def suggest_group_seats(event, requested: int) -> dict:
    try:
        seats = int(requested)
    except (TypeError, ValueError):
        return {"ok": False, "error": "seats must be an integer", "status": 400}
    if seats < 2:
        return {
            "ok": False,
            "error": "The seating agent is for groups of 2 or more. Pick seats on the map instead.",
            "status": 400,
        }

    remaining = event.remaining_seats
    if seats > remaining:
        suffix = "" if remaining == 1 else "s"
        return {
            "ok": False,
            "error": f"{NOT_ENOUGH_SEATS} Only {remaining} seat{suffix} remain for a group of {seats}.",
            "available_count": remaining,
            "status": 409,
        }

    layout = hall_layout(event.capacity)
    rows = int(layout["rows"])
    cols = int(layout["cols"])
    aisles = [int(item) for item in (layout.get("aisles_after") or []) if int(item) > 0]
    cross = [int(item) for item in (layout.get("row_aisles_after") or []) if int(item) > 0]
    taken = reserved_seat_ids(event)
    coords = _open_coords(event.capacity, taken)
    block = _best_compact_block(
        coords,
        seats,
        rows=rows,
        cols=cols,
        aisles_after=aisles,
        row_aisles_after=cross,
    )
    if block and len(block) == seats:
        chosen = block
        mode = "block"
        needs_confirm = False
    else:
        chosen = _disperse_nearby(
            coords,
            seats,
            cols=cols,
            aisles_after=aisles,
            row_aisles_after=cross,
            rows=rows,
        )
        mode = "dispersed"
        needs_confirm = True
    labels = [item.label for item in chosen]
    return {
        "ok": True,
        "mode": mode,
        "needs_confirm": needs_confirm,
        "seats": len(labels),
        "seat_ids": labels,
        "available_count": remaining,
        "message": _describe(chosen, mode),
    }
