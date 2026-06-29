from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from api_client import MosSportClient
from config import CHECK_INTERVAL, SITE_URL, EventSlot
from storage import Storage

logger = logging.getLogger(__name__)

EVENT_TYPE_LABELS = {
    "free_play": "Свободная игра",
    "masterclass": "Мастер-класс",
    "tournament_60": "Детский турнир",
    "tournament_120": "Турнир Американо (2ч)",
    "tournament_180": "Турнир (3ч)",
}


class SlotMonitor:
    def __init__(self, bot: Bot, storage: Storage, api: MosSportClient) -> None:
        self.bot = bot
        self.storage = storage
        self.api = api
        self._first_run = True

    async def run_forever(self) -> None:
        while True:
            try:
                await self.check_once(notify=True)
            except Exception:
                logger.exception("Ошибка при проверке слотов")
            await asyncio.sleep(CHECK_INTERVAL)

    async def check_once(self, notify: bool = False) -> list[EventSlot]:
        venue_ids = self.storage.get_monitored_venue_ids()
        event_types = self.storage.get_monitored_event_types()
        slots = await self.api.get_available_slots(
            venue_ids=venue_ids,
            event_types=event_types,
        )
        current_keys = {slot.key for slot in slots}

        if self._first_run:
            self.storage.update_known_slots(current_keys)
            self._first_run = False
            logger.info("Инициализация: зафиксировано %s слотов", len(current_keys))
            return slots

        known_keys = self.storage.known_slot_keys
        new_slots = [slot for slot in slots if slot.key not in known_keys]

        if new_slots and notify:
            await self._notify_new_slots(new_slots)

        if current_keys != known_keys:
            self.storage.update_known_slots(current_keys)

        return slots

    async def _notify_new_slots(self, slots: list[EventSlot]) -> None:
        subscribers = self.storage.subscribers
        if not subscribers:
            logger.warning("Новые слоты найдены, но нет подписчиков")
            return

        text = self._build_notification(slots)
        for chat_id in subscribers:
            try:
                await self.bot.send_message(chat_id, text, disable_web_page_preview=False)
            except Exception:
                logger.exception("Не удалось отправить уведомление в чат %s", chat_id)

    @staticmethod
    def _build_notification(slots: list[EventSlot]) -> str:
        lines = [
            "🎾 <b>Появились свободные слоты!</b>",
            "",
        ]
        for slot in slots[:20]:
            type_label = EVENT_TYPE_LABELS.get(slot.event_type, slot.event_title)
            lines.append(
                f"• <b>{type_label}</b>\n"
                f"  {slot.venue_title}\n"
                f"  {slot.event_date}, {slot.format_time()} — мест: {slot.cards}"
            )
        if len(slots) > 20:
            lines.append(f"\n…и ещё {len(slots) - 20} слотов")
        lines.extend(["", f'<a href="{SITE_URL}">Забронировать на сайте</a>'])
        return "\n".join(lines)
