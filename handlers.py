from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from api_client import MosSportClient
from config import BOOKING_WINDOW_DAYS, SITE_URL
from monitor import EVENT_TYPE_LABELS, SlotMonitor
from storage import Storage

logger = logging.getLogger(__name__)

VENUE_BUTTONS = {
    12: "Баррикадная",
    14: "Третьяковская",
    15: "Римская",
}


def setup_handlers(dp: Dispatcher, storage: Storage, api: MosSportClient, monitor: SlotMonitor) -> None:
    @dp.message(CommandStart())
    async def cmd_start(message: Message) -> None:
        storage.add_subscriber(message.chat.id)
        await message.answer(
            "Привет! Я слежу за свободными слотами на "
            '<a href="https://outdoor.sport.mos.ru/">outdoor.sport.mos.ru</a>.\n\n'
            "Когда появятся места для бронирования — пришлю уведомление.\n\n"
            "<b>Команды:</b>\n"
            "/status — текущие свободные слоты\n"
            "/venues — выбрать площадки\n"
            "/types — выбрать тип событий\n"
            "/check — проверить прямо сейчас\n"
            "/subscribe — включить уведомления\n"
            "/unsubscribe — отключить уведомления\n"
            "/help — справка",
            disable_web_page_preview=True,
        )

    @dp.message(Command("help"))
    async def cmd_help(message: Message) -> None:
        await message.answer(
            "<b>Как это работает</b>\n"
            f"Сайт открывает запись на {BOOKING_WINDOW_DAYS} дня вперёд. "
            "Бот опрашивает API каждую минуту и сообщает о <b>новых</b> слотах.\n\n"
            "По умолчанию отслеживается «Свободная игра» на всех площадках.\n\n"
            "/venues — фильтр по метро\n"
            "/types — фильтр по типу (игра, турнир, мастер-класс)\n"
            "/status — что доступно сейчас\n"
            "/check — принудительная проверка",
        )

    @dp.message(Command("subscribe"))
    async def cmd_subscribe(message: Message) -> None:
        if storage.add_subscriber(message.chat.id):
            await message.answer("Вы подписаны на уведомления ✅")
        else:
            await message.answer("Вы уже подписаны ✅")

    @dp.message(Command("unsubscribe"))
    async def cmd_unsubscribe(message: Message) -> None:
        if storage.remove_subscriber(message.chat.id):
            await message.answer("Уведомления отключены.")
        else:
            await message.answer("Вы не были подписаны.")

    @dp.message(Command("status"))
    async def cmd_status(message: Message) -> None:
        await message.answer("Проверяю слоты…")
        slots = await api.get_available_slots(
            venue_ids=storage.get_monitored_venue_ids(),
            event_types=storage.get_monitored_event_types(),
        )
        header = (
            f"<b>Свободные слоты</b> (окно {BOOKING_WINDOW_DAYS} дн.):\n"
            f"Найдено: {len(slots)}"
        )
        text = api.format_slots_message(slots, header)
        await message.answer(text, disable_web_page_preview=True)

    @dp.message(Command("check"))
    async def cmd_check(message: Message) -> None:
        await message.answer("Запускаю проверку…")
        slots = await monitor.check_once(notify=False)
        if slots:
            text = api.format_slots_message(
                slots,
                f"Проверка завершена. Активных слотов: {len(slots)}",
            )
        else:
            text = "Свободных слотов в окне бронирования нет."
        await message.answer(text, disable_web_page_preview=True)

    @dp.message(Command("venues"))
    async def cmd_venues(message: Message) -> None:
        selected = set(storage.get_monitored_venue_ids() or [])
        keyboard = _venue_keyboard(selected)
        text = (
            "Выберите площадки для мониторинга.\n"
            "Если ничего не выбрано — отслеживаются все три."
        )
        await message.answer(text, reply_markup=keyboard)

    @dp.message(Command("types"))
    async def cmd_types(message: Message) -> None:
        keyboard = _types_keyboard(storage)
        await message.answer(
            "Выберите типы событий для мониторинга:",
            reply_markup=keyboard,
        )

    @dp.callback_query(F.data.startswith("venue:"))
    async def on_venue_toggle(callback: CallbackQuery) -> None:
        if not callback.data or not callback.message:
            return
        venue_id = int(callback.data.split(":")[1])
        current = set(storage.get_monitored_venue_ids() or [])
        if venue_id in current:
            current.remove(venue_id)
        else:
            current.add(venue_id)
        storage.set_venue_ids(sorted(current))
        await callback.message.edit_reply_markup(
            reply_markup=_venue_keyboard(current),
        )
        await callback.answer("Настройки обновлены")

    @dp.callback_query(F.data == "venue:all")
    async def on_venue_all(callback: CallbackQuery) -> None:
        if not callback.message:
            return
        storage.set_venue_ids([])
        await callback.message.edit_reply_markup(reply_markup=_venue_keyboard(set()))
        await callback.answer("Все площадки")

    @dp.callback_query(F.data.startswith("etype:"))
    async def on_type_toggle(callback: CallbackQuery) -> None:
        if not callback.data or not callback.message:
            return
        etype = callback.data.split(":", 1)[1]
        if etype == "all":
            storage.set_notify_all_types(True)
        else:
            current = set(storage.get_monitored_event_types() or [])
            if etype in current:
                current.remove(etype)
            else:
                current.add(etype)
            if not current:
                current = {"free_play"}
            storage.set_event_types(sorted(current))
        await callback.message.edit_reply_markup(reply_markup=_types_keyboard(storage))
        await callback.answer("Настройки обновлены")


def _venue_keyboard(selected: set[int]) -> InlineKeyboardMarkup:
    rows = []
    for venue_id, label in VENUE_BUTTONS.items():
        mark = "✅ " if venue_id in selected else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark}{label}",
                    callback_data=f"venue:{venue_id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="Все площадки", callback_data="venue:all")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _types_keyboard(storage: Storage) -> InlineKeyboardMarkup:
    all_types = storage.settings.get("notify_all_types", False)
    selected = set(storage.get_monitored_event_types() or [])
    rows = []
    for etype, label in EVENT_TYPE_LABELS.items():
        if all_types:
            mark = ""
        else:
            mark = "✅ " if etype in selected else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark}{label}",
                    callback_data=f"etype:{etype}",
                )
            ]
        )
    all_mark = "✅ " if all_types else ""
    rows.append(
        [InlineKeyboardButton(text=f"{all_mark}Все типы", callback_data="etype:all")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
