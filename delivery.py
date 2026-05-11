"""
Delivery logic — sends pack content to the user exactly once.
All delivery attempts are gated by the DB duplicate-delivery check.

Named helpers (deliver_starter_pack, deliver_premium_pack, deliver_vip_pack)
are the intended call sites for webhooks and admin triggers.
deliver_pack() is the core engine — called by the named helpers and legacy paths.
"""

import logging
from telegram import Bot
from telegram.error import TelegramError

import db
from config import PACKS

logger = logging.getLogger(__name__)

# Friendly tier name → pack_id
_TIER_MAP: dict[str, str] = {
    "starter": "pack_a",
    "basic":   "pack_a",
    "premium": "pack_b",
    "vip":     "pack_c",
}


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
        content_line = f"🔗 {delivery_link}" if delivery_link else "check your messages — everything comes through in a second"
        await bot.send_message(
            chat_id=user_id,
            text=(
                f"*{pack['name']}* is yours.\n\n"
                f"{pack['description']}\n\n"
                f"{content_line}"
            ),
            parse_mode="Markdown",
        )
        return True
    except TelegramError as exc:
        logger.error("Telegram send failed for user=%s: %s", user_id, exc)
        # Delivery is still marked in DB — admin can /deliver to retry
        return False


async def send_sample_images(bot: Bot, chat_id: int, pack_id: str):
    """Send up to 3 sample images for a pack (skips blank entries)."""
    pack = PACKS.get(pack_id)
    if not pack:
        return
    samples = [s.strip() for s in pack.get("sample_images", []) if s.strip()][:3]
    for sample in samples:
        try:
            await bot.send_photo(chat_id=chat_id, photo=sample)
        except TelegramError as exc:
            logger.warning("Could not send sample image %s: %s", sample, exc)


# ── Named delivery helpers (webhook + admin entry points) ─────────────────────

async def _deliver_tier(bot: Bot, user_id: int, pack_id: str) -> bool:
    """Create a purchase record and deliver. Used by named helpers and /deliver command."""
    if await db.has_been_delivered(user_id, pack_id):
        logger.info("_deliver_tier: already delivered user=%s pack=%s", user_id, pack_id)
        return False
    purchase_id = await db.create_purchase(
        user_id=user_id,
        pack_id=pack_id,
        stripe_session=None,
        amount_cents=PACKS[pack_id]["amount_cents"],
    )
    return await deliver_pack(bot, user_id, pack_id, purchase_id)


async def deliver_starter_pack(bot: Bot, user_id: int) -> bool:
    return await _deliver_tier(bot, user_id, "pack_a")


async def deliver_premium_pack(bot: Bot, user_id: int) -> bool:
    return await _deliver_tier(bot, user_id, "pack_b")


async def deliver_vip_pack(bot: Bot, user_id: int) -> bool:
    return await _deliver_tier(bot, user_id, "pack_c")


def pack_id_for_tier(tier: str) -> str | None:
    """Return pack_id for a friendly tier name ('starter', 'premium', 'vip'), or None."""
    return _TIER_MAP.get(tier.lower())
