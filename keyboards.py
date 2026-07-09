from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import bridges


def main_menu():
    b = InlineKeyboardBuilder()
    b.button(text="🌉 Получить мосты", callback_data="menu_get")
    b.button(text="📋 Список мостов (обновляется)", callback_data="menu_list")
    b.button(text="✅ Проверить свои мосты", callback_data="menu_check")
    b.button(text="ℹ️ О боте", callback_data="menu_about")
    b.adjust(1)
    return b.as_markup()


def list_menu():
    b = InlineKeyboardBuilder()
    b.button(text="🔀 Показать другие", callback_data="list_shuffle")
    b.button(text="🔄 Обновить пул", callback_data="list_refresh")
    b.button(text="⬅️ Назад", callback_data="menu_back")
    b.adjust(2, 1)
    return b.as_markup()


def transports_menu():
    b = InlineKeyboardBuilder()
    for t in bridges.TRANSPORTS:
        b.button(text=bridges.TRANSPORT_TITLES[t], callback_data=f"get_{t}")
    b.button(text="⬅️ Назад", callback_data="menu_back")
    b.adjust(2, 2, 1)
    return b.as_markup()


def back_menu():
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Назад", callback_data="menu_back")
    return b.as_markup()


def recheck_menu(transport):
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Проверить снова", callback_data=f"recheck_{transport}")
    b.button(text="⬅️ Назад", callback_data="menu_back")
    b.adjust(1)
    return b.as_markup()
