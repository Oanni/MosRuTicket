from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import DATA_DIR, STATE_FILE, TELEGRAM_ADMIN_IDS


def _default_state() -> dict[str, Any]:
    return {
        "subscribers": [],
        "settings": {
            "venue_ids": [],
            "event_types": ["free_play"],
            "notify_all_types": False,
        },
        "known_slot_keys": [],
    }


class Storage:
    def __init__(self, path: Path = STATE_FILE) -> None:
        self.path = path
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            return _default_state()
        try:
            with self.path.open(encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return _default_state()
        defaults = _default_state()
        for key, value in defaults.items():
            data.setdefault(key, value)
        data["settings"].setdefault("venue_ids", [])
        data["settings"].setdefault("event_types", ["free_play"])
        data["settings"].setdefault("notify_all_types", False)
        return data

    def save(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    @property
    def subscribers(self) -> list[int]:
        ids = list(self._data.get("subscribers", []))
        for admin_id in TELEGRAM_ADMIN_IDS:
            if admin_id not in ids:
                ids.append(admin_id)
        return ids

    def add_subscriber(self, chat_id: int) -> bool:
        subscribers = self._data.setdefault("subscribers", [])
        if chat_id in subscribers:
            return False
        subscribers.append(chat_id)
        self.save()
        return True

    def remove_subscriber(self, chat_id: int) -> bool:
        subscribers = self._data.setdefault("subscribers", [])
        if chat_id not in subscribers:
            return False
        subscribers.remove(chat_id)
        self.save()
        return True

    @property
    def settings(self) -> dict[str, Any]:
        return self._data.setdefault("settings", {})

    def set_venue_ids(self, venue_ids: list[int]) -> None:
        self.settings["venue_ids"] = venue_ids
        self.save()

    def set_event_types(self, event_types: list[str]) -> None:
        self.settings["event_types"] = event_types
        self.settings["notify_all_types"] = False
        self.save()

    def set_notify_all_types(self, enabled: bool) -> None:
        self.settings["notify_all_types"] = enabled
        if enabled:
            self.settings["event_types"] = []
        self.save()

    def get_monitored_event_types(self) -> list[str] | None:
        if self.settings.get("notify_all_types"):
            return None
        return list(self.settings.get("event_types") or ["free_play"])

    def get_monitored_venue_ids(self) -> list[int] | None:
        venue_ids = self.settings.get("venue_ids") or []
        return venue_ids or None

    @property
    def known_slot_keys(self) -> set[str]:
        return set(self._data.get("known_slot_keys", []))

    def update_known_slots(self, keys: set[str]) -> None:
        self._data["known_slot_keys"] = sorted(keys)
        self.save()
