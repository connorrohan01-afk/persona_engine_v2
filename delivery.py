"""
Delivery logic — sends pack content to the user exactly once.

Named helpers (deliver_basic_pack, deliver_premium_pack, deliver_vip_pack)
create their own Bot() from BOT_TOKEN and are the primary call sites for
webhooks and admin triggers.

deliver_pack() is the internal engine — takes a pre-built bot instance,
used by the payments.py webhook flow.
"""

import asyncio
import logging
import os

from telegram import Bot
from telegram.error import TelegramError

import db
from config import PACKS

logger = logging.getLogger(__name__)

# Paced delivery config per tier
_PACK_DELIVERY: dict[str, dict] = {
    "pack_a": {
        "opener":  "here's what i put together for you...",
        "batches": [3, 3, 4],
        "closer":  "that's your collection. let me know what you think 🖤",
    },
    "pack_b": {
        "opener":  "here's your collection. took a while to put this together...",
        "batches": [10, 12, 13],
        "closer":  "that's everything in your pack. more dropping soon 🖤",
    },
    "pack_c": {
        "opener":  "everything. this is the full vault...",
        "batches": [20, 25, 30],
        "closer":  "that's the full vault. you've got everything 🖤",
    },
}

# Friendly tier name → pack_id
_TIER_MAP: dict[str, str] = {
    "starter": "pack_a",
    "basic":   "pack_a",
    "premium": "pack_b",
    "vip":     "pack_c",
}


async def _send_pack_images(bot: Bot, user_id: int, pack_id: str) -> None:
    """Send images in paced batches with psychological timing.

    Flow: opener → 1.5s → batch → 3s → batch → 3s → batch → 4s → closer
    0.4s between each individual image within a batch.
    """
    config  = _PACK_DELIVERY.get(pack_id, _PACK_DELIVERY["pack_a"])
    batches = config["batches"]

    # Opener
    try:
        await bot.send_message(chat_id=user_id, text=config["opener"])
    except TelegramError as exc:
        logger.warning("Could not send opener to user=%s: %s", user_id, exc)
    await asyncio.sleep(1.5)

    # Images in batches
    image_index = 1
    for batch_num, batch_size in enumerate(batches):
        for _ in range(batch_size):
            try:
                await bot.send_photo(
                    chat_id=user_id,
                    photo=f"https://picsum.photos/800/600?random={image_index}",
                )
            except TelegramError as exc:
                logger.warning("Could not send image %d to user=%s: %s", image_index, user_id, exc)
            image_index += 1
            await asyncio.sleep(0.4)

        # 3s pause between batches, skip after last batch
        if batch_num < len(batches) - 1:
            await asyncio.sleep(3.0)

    # Pause before closer
    await asyncio.sleep(4.0)

    # Closer
    try:
        await bot.send_message(chat_id=user_id, text=config["closer"])
    except TelegramError as exc:
        logger.warning("Could not send closer to user=%s: %s", user_id, exc)


async def deliver_pack(bot: Bot, user_id: int, pack_id: str, purchase_id: int) -> bool:
    """
    Attempt to deliver pack_id to user_id.
    Returns True on success, False if already delivered or on error.
    Marks the purchase as delivered in DB BEFORE sending to prevent
    double-delivery even if the send partially fails.
    """
    if pack_id not in PACKS:
        logger.error("deliver_pack: unknown pack_id=%s", pack_id)
        return False

    # Hard duplicate-delivery guard
    if await db.has_been_delivered(user_id, pack_id):
        logger.warning("Duplicate delivery blocked: user=%s pack=%s", user_id, pack_id)
        return False

    await db.mark_delivered(purchase_id)
    logger.info("DELIVERY user=%s pack=%s purchase=%s", user_id, pack_id, purchase_id)

    try:
        await _send_pack_images(bot, user_id, pack_id)
        return True
    except Exception as exc:
        logger.error("Delivery failed for user=%s: %s", user_id, exc)
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

async def _deliver_tier_with_token(user_id: int, pack_id: str) -> bool:
    """Create Bot from env token, create purchase record, then deliver. DB-gated."""
    if pack_id not in PACKS:
        logger.error("_deliver_tier_with_token: unknown pack_id=%s", pack_id)
        return False

    if await db.has_been_delivered(user_id, pack_id):
        logger.info("_deliver_tier_with_token: already delivered user=%s pack=%s", user_id, pack_id)
        return False

    purchase_id = await db.create_purchase(
        user_id=user_id,
        pack_id=pack_id,
        stripe_session=None,
        amount_cents=PACKS[pack_id]["amount_cents"],
    )
    async with Bot(token=os.environ["TELEGRAM_BOT_TOKEN"]) as bot:
        return await deliver_pack(bot, user_id, pack_id, purchase_id)


async def deliver_basic_pack(user_id: int) -> bool:
    """Deliver Starter/Basic pack (10 images) to user_id."""
    return await _deliver_tier_with_token(user_id, "pack_a")


async def deliver_premium_pack(user_id: int) -> bool:
    """Deliver Premium pack (35 images) to user_id."""
    return await _deliver_tier_with_token(user_id, "pack_b")


async def deliver_vip_pack(user_id: int) -> bool:
    """Deliver VIP pack (75 images) to user_id."""
    return await _deliver_tier_with_token(user_id, "pack_c")


def pack_id_for_tier(tier: str) -> str | None:
    """Return pack_id for a friendly tier name ('starter'/'basic'/'premium'/'vip'), or None."""
    return _TIER_MAP.get(tier.lower())
