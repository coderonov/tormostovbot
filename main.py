import asyncio
import html
import logging
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery
from aiogram.client.default import DefaultBotProperties

import config
import bridges
import checker
import keyboards
import pool

logging.basicConfig(level=logging.INFO)
router = Router()

LAST_FETCHED = {}

WELCOME_TEXT = (
    "🧅 <b>TorMostovBot</b>\n\n"
    "Получай рабочие Tor-мосты (obfs4, vanilla, meek-azure, snowflake) "
    "и проверяй их доступность прямо в Telegram.\n\n"
    "Выбери действие ниже 👇"
)

ABOUT_TEXT = (
    "ℹ️ <b>О боте</b>\n\n"
    "Бот получает встроенные мосты Tor напрямую с серверов Tor Project (moat API) "
    "и проверяет их доступность TCP-подключением к IP:порту.\n\n"
    "⚠️ Успешная проверка означает, что порт моста отвечает на подключение. "
    "Это не гарантирует полную работу obfs4/meek протокола внутри Tor Browser, "
    "но отсеивает точно нерабочие/мёртвые мосты.\n\n"
    "Для snowflake фиксированный IP не используется — транспорт работает через "
    "динамических добровольцев-прокси, поэтому проверка для него не проводится."
)


class CheckStates(StatesGroup):
    waiting_bridges = State()


def format_results(results, limit=20):
    ok = [r for r in results if r["ok"]]
    bad = [r for r in results if not r["ok"]]

    lines = []
    lines.append(f"✅ Рабочих: <b>{len(ok)}</b>   ❌ Нерабочих: <b>{len(bad)}</b>\n")

    shown = 0
    for r in ok:
        if shown >= limit:
            break
        latency_ms = int(r["latency"] * 1000) if r["latency"] else 0
        safe_line = html.escape(r["line"])
        lines.append(f"✅ <code>{safe_line}</code>\n   ⏱ {latency_ms} мс")
        shown += 1

    if len(ok) > limit:
        lines.append(f"\n… и ещё {len(ok) - limit} рабочих мостов")

    if bad:
        lines.append(f"\n❌ <b>Не отвечают ({len(bad)}):</b>")
        for r in bad[:5]:
            safe_line = html.escape(r["line"])
            lines.append(f"❌ <code>{safe_line}</code>")
        if len(bad) > 5:
            lines.append(f"… и ещё {len(bad) - 5}")

    return "\n".join(lines)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(WELCOME_TEXT, reply_markup=keyboards.main_menu())


@router.callback_query(F.data == "menu_back")
async def cb_back(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(WELCOME_TEXT, reply_markup=keyboards.main_menu())
    await call.answer()


@router.callback_query(F.data == "menu_about")
async def cb_about(call: CallbackQuery):
    await call.message.edit_text(ABOUT_TEXT, reply_markup=keyboards.back_menu())
    await call.answer()


@router.callback_query(F.data == "menu_get")
async def cb_get_menu(call: CallbackQuery):
    await call.message.edit_text(
        "🌉 Выбери тип моста:", reply_markup=keyboards.transports_menu()
    )
    await call.answer()


LIST_SAMPLE_SIZE = 20
LIST_TRANSPORT = "obfs4"


async def render_list(message: Message, edit: bool):
    if pool.pool_size(LIST_TRANSPORT) == 0:
        fetched = await bridges.get_bridges(LIST_TRANSPORT)
        pool.add_lines(LIST_TRANSPORT, fetched)

    lines = pool.get_lines(LIST_TRANSPORT, 40)

    if not lines:
        fetched = await bridges.get_bridges(LIST_TRANSPORT)
        if not fetched:
            text = (
                "😔 Не удалось получить мосты с серверов Tor Project. "
                "Попробуй обновить пул чуть позже."
            )
            markup = keyboards.list_menu()
            if edit:
                await message.edit_text(text, reply_markup=markup)
            else:
                await message.answer(text, reply_markup=markup)
            return
        lines = fetched
        pool.add_lines(LIST_TRANSPORT, fetched)

    wait_msg = await message.answer("⏳ Проверяю мосты...")

    results = await checker.check_bridges(lines)
    valid = [r for r in results if r["ok"]]

    if not valid:
        await wait_msg.edit_text(
            "😔 Среди полученных мостов нет валидных. "
            "Попробуй обновить пул.",
            reply_markup=keyboards.list_menu(),
        )
        return

    shown = valid[:LIST_SAMPLE_SIZE]
    body_lines = []
    total_est = len("🌉 <b>obfs4</b>\n<pre>\n</pre>\n")
    for r in shown:
        safe = html.escape(r["line"])
        if total_est + len(safe) + 20 > 4000:
            break
        body_lines.append(safe)
        total_est += len(safe) + 1

    body = "\n".join(body_lines)

    now = datetime.now(timezone.utc).strftime("%H:%M UTC, %d %B")

    extra = ""
    total_valid = len(valid)
    if total_valid > len(body_lines):
        remaining = total_valid - len(body_lines)
        extra = f"\n… и ещё {remaining} валидных"
    elif total_valid < len(lines):
        extra = f"\n✅ {total_valid}/{len(lines)} валидных"

    text = (
        f"🌉 <b>obfs4</b>\n"
        f"<pre>{body}</pre>\n"
        f"{now}{extra}"
    )

    if edit:
        await wait_msg.delete()
        await message.edit_text(text, reply_markup=keyboards.list_menu())
    else:
        await wait_msg.edit_text(text, reply_markup=keyboards.list_menu())


@router.callback_query(F.data == "menu_list")
async def cb_menu_list(call: CallbackQuery):
    await call.answer()
    await render_list(call.message, edit=True)


@router.callback_query(F.data == "list_shuffle")
async def cb_list_shuffle(call: CallbackQuery):
    await call.answer("Показываю другие мосты")
    await render_list(call.message, edit=True)


@router.callback_query(F.data == "list_refresh")
async def cb_list_refresh(call: CallbackQuery):
    await call.answer("Обновляю пул...")
    fetched = await bridges.get_bridges(LIST_TRANSPORT)
    added = pool.add_lines(LIST_TRANSPORT, fetched)
    await render_list(call.message, edit=True)
    if added:
        await call.message.answer(f"➕ Добавлено новых мостов в пул: {added}")


@router.callback_query(F.data == "menu_check")
async def cb_check_menu(call: CallbackQuery, state: FSMContext):
    await state.set_state(CheckStates.waiting_bridges)
    await call.message.edit_text(
        "✉️ Пришли мне мосты, которые нужно проверить (каждый с новой строки).\n\n"
        "Поддерживаются форматы obfs4, vanilla, meek_lite.",
        reply_markup=keyboards.back_menu(),
    )
    await call.answer()


async def send_transport_bridges(target_message: Message, transport: str, edit=False):
    if transport == "snowflake":
        text = (
            "🌨 <b>Snowflake</b>\n\n"
            "Этот транспорт не использует фиксированный IP — клиенты подключаются "
            "через динамических добровольцев-прокси и брокер Tor Project.\n\n"
            "Просто включи <code>snowflake</code> как встроенный мост в настройках "
            "Tor Browser — отдельная строка моста не требуется."
        )
        if edit:
            await target_message.edit_text(text, reply_markup=keyboards.back_menu())
        else:
            await target_message.answer(text, reply_markup=keyboards.back_menu())
        return

    wait_msg = await target_message.answer("⏳ Получаю мосты и проверяю их...")
    lines = await bridges.get_bridges(transport)

    if not lines:
        await wait_msg.edit_text(
            "😔 Не удалось получить мосты с серверов Tor Project. "
            "Попробуй ещё раз чуть позже.",
            reply_markup=keyboards.back_menu(),
        )
        return

    results = await checker.check_bridges(lines)
    LAST_FETCHED[transport] = lines

    title = f"🌉 <b>{bridges.TRANSPORT_TITLES.get(transport, transport)}</b>\n\n"
    body = format_results(results)
    text = title + body

    if len(text) > 3800:
        text = text[:3800] + "\n\n… (сообщение обрезано)"

    await wait_msg.edit_text(text, reply_markup=keyboards.recheck_menu(transport))


@router.callback_query(F.data.startswith("get_"))
async def cb_get_transport(call: CallbackQuery):
    transport = call.data[len("get_"):]
    await call.answer()
    await send_transport_bridges(call.message, transport, edit=False)


@router.callback_query(F.data.startswith("recheck_"))
async def cb_recheck(call: CallbackQuery):
    transport = call.data[len("recheck_"):]
    await call.answer("Проверяю заново...")
    lines = LAST_FETCHED.get(transport) or await bridges.get_bridges(transport)
    if not lines:
        await call.message.edit_text(
            "😔 Не удалось получить мосты.", reply_markup=keyboards.back_menu()
        )
        return
    wait_text = call.message.text or ""
    results = await checker.check_bridges(lines)
    title = f"🌉 <b>{bridges.TRANSPORT_TITLES.get(transport, transport)}</b>\n\n"
    body = format_results(results)
    text = title + body
    if len(text) > 3800:
        text = text[:3800] + "\n\n… (сообщение обрезано)"
    await call.message.edit_text(text, reply_markup=keyboards.recheck_menu(transport))


@router.message(CheckStates.waiting_bridges)
async def process_custom_bridges(message: Message, state: FSMContext):
    raw_lines = [l.strip() for l in message.text.splitlines() if l.strip()]
    if not raw_lines:
        await message.answer("Пришли хотя бы одну строку моста.")
        return

    wait_msg = await message.answer(f"⏳ Проверяю {len(raw_lines)} мост(ов)...")
    results = await checker.check_bridges(raw_lines)
    body = format_results(results, limit=30)
    await wait_msg.edit_text(
        "✅ <b>Результат проверки</b>\n\n" + body, reply_markup=keyboards.back_menu()
    )
    await state.clear()


async def main():
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
