from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATE_FILE = DATA_DIR / "state.json"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
BOOKING_WINDOW_DAYS = int(os.getenv("BOOKING_WINDOW_DAYS", "3"))
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.outdoor.sport.mos.ru").rstrip("/")
SITE_URL = "https://outdoor.sport.mos.ru/#venues-events"


def parse_admin_ids(raw: str | None) -> list[int]:
    if not raw:
        return []
    ids: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    return ids


TELEGRAM_ADMIN_IDS = parse_admin_ids(os.getenv("TELEGRAM_ADMIN_IDS"))


@dataclass(frozen=True)
class EventSlot:
    event_id: int
    venue_id: int
    venue_title: str
    event_card_id: int
    event_type: str
    event_title: str
    event_date: str
    start_at: str
    end_at: str
    cards: int

    @property
    def key(self) -> str:
        return f"{self.event_id}"

    def format_time(self) -> str:
        start = self.start_at[:5]
        end = self.end_at[:5]
        return f"{start}–{end}"

    def format_line(self) -> str:
        return (
            f"• <b>{self.event_title}</b>\n"
            f"  {self.venue_title}\n"
            f"  {self.event_date} {self.format_time()} — "
            f"свободно мест: {self.cards}"
        )
