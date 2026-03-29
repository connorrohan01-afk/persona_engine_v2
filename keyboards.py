"""
Inline keyboard factories.
All pack metadata lives here so it's one place to update prices / links.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import PACKS


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✨ View Packs", callback_data="view_packs"),
    ]])


def packs_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for pack_id, pack in PACKS.items():
        rows.append([
            InlineKeyboardButton(
                f"{pack['emoji']} {pack['name']} (${pack['price_usd']})",
                callback_data=f"pack_{pack_id}",
            )
        ])
    return InlineKeyboardMarkup(rows)


def pack_detail_keyboard(pack_id: str) -> InlineKeyboardMarkup:
    pack = PACKS[pack_id]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Buy Now", url=pack["payment_link"])],
        [InlineKeyboardButton("⬅️ Back to Packs", callback_data="view_packs")],
    ])


def upsell_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬆️ Upgrade — see more", callback_data="view_packs")],
        [InlineKeyboardButton("❌ No thanks", callback_data="exit")],
    ])


def payment_done_keyboard(pack_id: str) -> InlineKeyboardMarkup:
    """Button the user presses after completing payment."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ I've paid — send my pack!", callback_data=f"paid_{pack_id}"),
    ]])
