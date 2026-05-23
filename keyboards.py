"""
Inline keyboard factories.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import PACKS


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✨ View Packs", callback_data="view_packs"),
    ]])


def packs_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Pack list — each button opens the Replit vault page with tg_id appended."""
    rows = []
    for pack in PACKS.values():
        rows.append([
            InlineKeyboardButton(
                f"{pack['emoji']} {pack['name']} (${pack['price_usd']})",
                url=f"{pack['payment_link']}#{user_id}",
            )
        ])
    return InlineKeyboardMarkup(rows)


def upsell_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬆️ Upgrade — see more", callback_data="view_packs")],
        [InlineKeyboardButton("❌ No thanks", callback_data="exit")],
    ])
