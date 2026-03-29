"""
Delivery logic — sends pack content to the user exactly once.
All delivery attempts are gated by the DB duplicate-delivery check.
"""

import logging
from telegram import Bot
from telegram.error import TelegramError

import db
from config import PACKS

logger = logging.getLogger(__name__)


async def deliver_pack(bot: Bot, user_id: int, pack_id: str, purchase_id: int) -> bool:
    """
    Attempt to deliver pack_id to user_id.
    Returns True on success, False if already delivered or on error.
    Marks the purchase as delivered in DB before sending to prevent double-delivery
    even if the send itself partially fails.
    """
    if pack_id not in PACKS:
        logger.error("deliver_pack: unknown pack_id=%s", pack_id)
        return False

    # Hard duplicate-delivery guard
    if await db.has_been_delivered(user_id, pack_id):
        logger.warning("Duplicate delivery blocked: user=%s pack=%s", user_id, pack_id)
        return False

    pack = PACKS[pack_id]
    delivery_link = pack.get("delivery_link", "").strip()

    # Mark delivered BEFORE sending so a retry can't sneak through on a crash
    await db.mark_delivered(purchase_id)
    logger.info("DELIVERY user=%s pack=%s purchase=%s", user_id, pack_id, purchase_id)

    try:
        await bot.send_message(
            chat_id=user_id,
            text=(
                f"🎁 *Your {pack['name']} is here!*\n\n"
                f"{pack['description']}\n\n"
                f"{'🔗 Access your content: ' + delivery_link if delivery_link else '⚠️ Your content link will be sent by the admin shortly.'}"
            ),
            parse_mode="Markdown",
        )
        return True
    except TelegramError as exc:
        logger.error("Telegram send failed for user=%s: %s", user_id, exc)
        # Delivery is still marked in DB — admin can /force_deliver if needed
        return False


async def send_sample_images(bot: Bot, chat_id: int, pack_id: str):
    """Send up to 3 sample images for a pack (skips blank entries)."""
    pack = PACKS.get(pack_id)
    if not pack:
        return
    samples = [s.strip() for s in pack.get("sample_images", []) if s.strip()][:3]
    for sample in samples:
        try:
            if sample.startswith("http"):
                await bot.send_photo(chat_id=chat_id, photo=sample)
            else:
                await bot.send_photo(chat_id=chat_id, photo=sample)
        except TelegramError as exc:
            logger.warning("Could not send sample image %s: %s", sample, exc)
