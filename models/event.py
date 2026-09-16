from dataclasses import asdict, dataclass


@dataclass
class Event:
    id: str
    organizer_id: str
    title: str
    description: str
    date: str
    capacity: int
    seats_booked: int = 0
    status: str = "active"

    @property
    def remaining_seats(self) -> int:
        return max(0, self.capacity - self.seats_booked)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["remaining_seats"] = self.remaining_seats
        data["available"] = self.status == "active" and self.remaining_seats > 0
        return data
