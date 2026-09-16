from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class TalkSubmission:
    id: str
    speaker_id: str
    title: str
    abstract: str
    category: str
    status: str
    ai_assessment: dict[str, Any]

    def to_dict(self) -> dict:
        return asdict(self)
