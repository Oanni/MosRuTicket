from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import aiohttp

from config import API_BASE_URL, BOOKING_WINDOW_DAYS, EventSlot


class MosSportApiError(Exception):
    pass


class MosSportClient:
    def __init__(self, base_url: str = API_BASE_URL) -> None:
        self.base_url = base_url
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _get(self, path: str) -> dict[str, Any]:
        session = await self._get_session()
        url = f"{self.base_url}{path}"
        async with session.get(url) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise MosSportApiError(f"{resp.status} {url}: {text[:200]}")
            return await resp.json()

    async def get_venues(self) -> list[dict[str, Any]]:
        data = await self._get("/items/venues?fields=id,title,address,sort&sort=sort&limit=-1")
        return data.get("data", [])

    async def get_available_slots(
        self,
        venue_ids: list[int] | None = None,
        event_types: list[str] | None = None,
        today: date | None = None,
    ) -> list[EventSlot]:
        today = today or date.today()
        end_date = today + timedelta(days=BOOKING_WINDOW_DAYS)
        venues = await self.get_venues()
        if venue_ids:
            venues = [v for v in venues if v["id"] in venue_ids]

        slots: list[EventSlot] = []
        for venue in venues:
            venue_id = venue["id"]
            venue_title = venue.get("title", f"Площадка {venue_id}")
            cards_data = await self._get(
                "/items/event_cards"
                f"?filter[venue_id][_eq]={venue_id}"
                "&fields=id,title,event_type,events.id,events.event_date,"
                "events.start_at,events.end_at,events.cards,events.status"
                "&limit=-1"
            )
            for card in cards_data.get("data", []):
                card_type = card.get("event_type") or ""
                if event_types and card_type not in event_types:
                    continue
                for event in card.get("events") or []:
                    if event.get("status") != "published":
                        continue
                    cards_count = event.get("cards") or 0
                    if cards_count <= 0:
                        continue
                    event_date = event.get("event_date") or ""
                    if not event_date:
                        continue
                    if event_date < today.isoformat() or event_date > end_date.isoformat():
                        continue
                    slots.append(
                        EventSlot(
                            event_id=int(event["id"]),
                            venue_id=int(venue_id),
                            venue_title=venue_title,
                            event_card_id=int(card["id"]),
                            event_type=card_type,
                            event_title=card.get("title") or card_type,
                            event_date=event_date,
                            start_at=event.get("start_at") or "",
                            end_at=event.get("end_at") or "",
                            cards=int(cards_count),
                        )
                    )

        slots.sort(key=lambda s: (s.event_date, s.start_at, s.venue_title, s.event_title))
        return slots

    @staticmethod
    def format_slots_message(slots: list[EventSlot], header: str) -> str:
        if not slots:
            return f"{header}\n\nСвободных слотов в окне бронирования нет."
        lines = [header, ""]
        current_group = ""
        for slot in slots:
            group = f"{slot.venue_title} — {slot.event_date}"
            if group != current_group:
                if current_group:
                    lines.append("")
                lines.append(f"<b>{slot.venue_title}</b> ({slot.event_date})")
                current_group = group
            lines.append(
                f"• {slot.event_title}, {slot.format_time()} — мест: {slot.cards}"
            )
        lines.append("")
        lines.append('<a href="https://outdoor.sport.mos.ru/#venues-events">Открыть сайт</a>')
        return "\n".join(lines)
