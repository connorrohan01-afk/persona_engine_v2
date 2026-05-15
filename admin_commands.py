"""
Admin delivery commands module.

Exposes register(application) — call this from main.py to wire up
the /deliver command onto the Telegram Application.

Usage (admin only):
  /deliver basic   USER_ID
  /deliver premium USER_ID
  /deliver vip     USER_ID
  /deliver starter USER_ID   (alias for basic)
"""

import logging
import os
from functools import wraps

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

import db
from delivery import (
    deliver_basic_pack,
    deliver_premium_pack,
    deliver_vip_pack,
    pack_id_for_tier,
)
from states import State

logger = logging.getLogger(__name__)

# Read from ADMIN_TELEGRAM_ID first, fall back to ADMIN_USER_ID for compatibility
ADMIN_ID: int = int(
    os.environ.get("ADMIN_TELEGRAM_ID") or os.environ.get("ADMIN_USER_ID", "0")
)

_DELIVER_FN_MAP = {
    "pack_a": deliver_basic_pack,
    "pack_b": deliver_premium_pack,
    "pack_c": deliver_vip_pack,
}


def _admin_only(func):
    """Silently ignore commands from non-admins."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            logger.warning(
                "Unauthorized /deliver attempt by user=%s",
                update.effective_user.id,
            )
            return
        return await func(update, context)
    return wrapper


@_admin_only
async def _cmd_deliver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /deliver basic|premium|vip USER_ID

    Manually deliver a pack to a user for testing or support.
    Aliases: starter = basic
    """
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: /deliver basic|premium|vip USER_ID\n"
            "Example: /deliver premium 123456789\n"
            "Aliases: starter = basic"
        )
        return

    tier = args[0].lower()
    pack_id = pack_id_for_tier(tier)
    if not pack_id:
        await update.message.reply_text(
            f"Unknown tier '{tier}'. Valid options: basic, premium, vip"
        )
        return

    try:
        target_user_id = int(args[1])
    except ValueError:
        await update.message.reply_text("Invalid USER_ID — must be an integer.")
        return

    user = await db.get_user(target_user_id)
    if not user:
        await update.message.reply_text(f"User {target_user_id} not found in DB.")
        return

    if await db.has_been_delivered(target_user_id, pack_id):
        await update.message.reply_text(
            f"⚠️ {tier} already delivered to user {target_user_id}."
        )
        return

    await update.message.reply_text(f"Delivering {tier} to {target_user_id}…")
    await db.set_user_state(target_user_id, State.DELIVERY)

    deliver_fn = _DELIVER_FN_MAP[pack_id]
    success = await deliver_fn(target_user_id)

    if success:
        await db.set_user_state(target_user_id, State.UPSELL)
        await update.message.reply_text(
            f"✅ {tier} delivered to user {target_user_id}."
        )
    else:
        await update.message.reply_text(
            f"❌ Delivery failed for user {target_user_id} / {tier}. Check logs."
        )

    logger.info(
        "ADMIN_CMD_DELIVER admin=%s target=%s tier=%s pack=%s success=%s",
        update.effective_user.id, target_user_id, tier, pack_id, success,
    )


def register(application) -> None:
    """Register admin delivery command onto a Telegram Application instance."""
    application.add_handler(CommandHandler("deliver", _cmd_deliver))
