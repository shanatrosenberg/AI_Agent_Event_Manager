from dataclasses import asdict, dataclass


@dataclass
class Booking:
    id: str
    attendee_id: str
    event_id: str
    seats: int
    status: str

    def to_dict(self) -> dict:
        return asdict(self)
