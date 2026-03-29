"""
Admin command handlers — all restricted to ADMIN_USER_ID.
"""

import logging
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

import db
from config import ADMIN_USER_ID
from delivery import deliver_pack
from states import State

logger = logging.getLogger(__name__)


def admin_only(func):
    """Decorator: silently ignore commands from non-admins."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_USER_ID:
            logger.warning(
                "Unauthorized admin command attempt by user=%s",
                update.effective_user.id,
            )
            return
        return await func(update, context)
    return wrapper


@admin_only
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = await db.get_stats()
    revenue_dollars = stats["revenue_cents"] / 100
    text = (
        "📊 *Bot Stats*\n\n"
        f"👤 Total users: {stats['total_users']}\n"
        f"🛍️ Total purchases delivered: {stats['total_purchases']}\n"
        f"💰 Total revenue: ${revenue_dollars:.2f}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


@admin_only
async def cmd_force_deliver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Usage: /force_deliver <user_id> <pack_id>
    Example: /force_deliver 123456789 pack_b
    """
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /force_deliver <user_id> <pack_id>")
        return

    try:
        target_user_id = int(args[0])
    except ValueError:
        await update.message.reply_text("Invalid user_id — must be an integer.")
        return

    pack_id = args[1].lower()

    user = await db.get_user(target_user_id)
    if not user:
        await update.message.reply_text(f"User {target_user_id} not found in DB.")
        return

    # Check if already delivered
    if await db.has_been_delivered(target_user_id, pack_id):
        await update.message.reply_text(
            f"⚠️ {pack_id} already delivered to user {target_user_id}."
        )
        return

    # Create a manual purchase record
    purchase_id = await db.create_purchase(
        user_id=target_user_id,
        pack_id=pack_id,
        stripe_session="admin_force",
        amount_cents=0,
    )
    await db.set_user_state(target_user_id, State.DELIVERY)
    success = await deliver_pack(context.bot, target_user_id, pack_id, purchase_id)

    if success:
        await db.set_user_state(target_user_id, State.UPSELL)
        await update.message.reply_text(
            f"✅ Delivery sent to user {target_user_id} for {pack_id}."
        )
    else:
        await update.message.reply_text(
            f"❌ Delivery failed for user {target_user_id} / {pack_id}. "
            "Check logs for details."
        )
    logger.info("ADMIN_FORCE_DELIVER admin=%s target=%s pack=%s success=%s",
                update.effective_user.id, target_user_id, pack_id, success)


@admin_only
async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Usage: /ban <user_id>
    """
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /ban <user_id>")
        return

    try:
        target_user_id = int(args[0])
    except ValueError:
        await update.message.reply_text("Invalid user_id — must be an integer.")
        return

    if target_user_id == ADMIN_USER_ID:
        await update.message.reply_text("❌ Cannot ban the admin.")
        return

    await db.ban_user(target_user_id)
    await update.message.reply_text(f"🚫 User {target_user_id} has been banned.")
    logger.info("ADMIN_BAN admin=%s target=%s", update.effective_user.id, target_user_id)
