"""Small parsing helpers for dashboard data."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Lesson:
    day: date
    time: str
    name: str


def parse_lesson_title(title: str, day: date) -> Lesson:
    """Parse a card title such as ``8pm · scratch-1-177``."""
    time, separator, name = title.partition(" · ")
    if not separator or not time.strip() or not name.strip():
        raise ValueError(f"Unexpected lesson title: {title!r}")
    return Lesson(day=day, time=time.strip(), name=name.strip())
