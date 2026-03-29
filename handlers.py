"""
Core conversation handlers — state machine driven, no LLM control.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

import db
from config import PACKS, PERSONA_NAME
from delivery import deliver_pack, send_sample_images
from keyboards import (
    main_menu_keyboard,
    pack_detail_keyboard,
    packs_keyboard,
    payment_done_keyboard,
    upsell_keyboard,
)
from llm import persona_message
from states import State

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_or_create_user(update: Update) -> dict:
    u = update.effective_user
    return await db.upsert_user(u.id, u.username)


async def _guard(update: Update) -> bool:
    """Return True (and reply) if user is banned."""
    if await db.is_banned(update.effective_user.id):
        await update.effective_message.reply_text(
            "Your access to this bot has been restricted."
        )
        return True
    return False


# ── /start ────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _guard(update):
        return

    user = await _get_or_create_user(update)

    # Allow restart from EXIT or GREETING; otherwise resume current state
    if user["state"] not in (State.GREETING, State.EXIT):
        await update.message.reply_text(
            f"Welcome back! Use the menu below to continue.",
            reply_markup=main_menu_keyboard(),
        )
        return

    await db.set_user_state(update.effective_user.id, State.WARMUP)
    greeting = await persona_message("greeting")
    warmup = await persona_message("warmup")

    await update.message.reply_text(
        f"*Hi, I'm {PERSONA_NAME}!* 👋\n\n{greeting}\n\n{warmup}",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


# ── Callback query dispatcher ─────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if await _guard(update):
        return

    data = query.data

    if data == "view_packs":
        await _show_packs(update, context)
    elif data.startswith("pack_"):
        pack_id = data[len("pack_"):]
        await _show_pack_detail(update, context, pack_id)
    elif data.startswith("paid_"):
        pack_id = data[len("paid_"):]
        await _handle_paid_claim(update, context, pack_id)
    elif data == "exit":
        await _handle_exit(update, context)
    else:
        logger.warning("Unknown callback_data: %s", data)


# ── View packs ────────────────────────────────────────────────────────────────

async def _show_packs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await db.get_user(user_id)

    if user and user["state"] in (State.GREETING, State.WARMUP):
        await db.set_user_state(user_id, State.OFFER)

    offer_text = await persona_message("offer")
    await update.effective_message.reply_text(
        f"{offer_text}\n\n*Choose a pack:*",
        parse_mode="Markdown",
        reply_markup=packs_keyboard(),
    )


# ── Pack detail ───────────────────────────────────────────────────────────────

async def _show_pack_detail(
    update: Update, context: ContextTypes.DEFAULT_TYPE, pack_id: str
):
    if pack_id not in PACKS:
        await update.effective_message.reply_text("Pack not found.")
        return

    user_id = update.effective_user.id
    pack = PACKS[pack_id]

    # Send sample images (best-effort)
    await send_sample_images(context.bot, user_id, pack_id)

    payment_text = await persona_message("payment")
    detail_text = (
        f"{pack['emoji']} *{pack['name']}* — ${pack['price_usd']}\n\n"
        f"{pack['description']}\n\n"
        f"{payment_text}\n\n"
        f"After completing payment, tap the button below 👇"
    )
    await update.effective_message.reply_text(
        detail_text,
        parse_mode="Markdown",
        reply_markup=pack_detail_keyboard(pack_id),
    )

    # Record pending purchase when user views the pack detail
    await db.set_user_state(user_id, State.PAYMENT_PENDING)
    existing = await db.get_undelivered_purchase(user_id, pack_id)
    if not existing:
        await db.create_purchase(
            user_id=user_id,
            pack_id=pack_id,
            stripe_session=None,
            amount_cents=pack["amount_cents"],
        )

    # Show "I've paid" button in a follow-up (Stripe webhook is primary path)
    await context.bot.send_message(
        chat_id=user_id,
        text="Tap below once your payment is complete:",
        reply_markup=payment_done_keyboard(pack_id),
    )


# ── Manual "I've paid" claim ──────────────────────────────────────────────────

async def _handle_paid_claim(
    update: Update, context: ContextTypes.DEFAULT_TYPE, pack_id: str
):
    """
    User taps "I've paid".  Stripe webhook is the authoritative path.
    This is a fallback for when webhooks are delayed — it checks DB for
    an undelivered purchase and delivers if one exists (webhook may have
    already created it).  If no purchase exists, prompt to complete payment.
    """
    user_id = update.effective_user.id

    if await db.has_been_delivered(user_id, pack_id):
        await update.effective_message.reply_text(
            "✅ You already have this pack! Check your previous messages."
        )
        return

    purchase = await db.get_undelivered_purchase(user_id, pack_id)
    if not purchase:
        await update.effective_message.reply_text(
            "We haven't received your payment yet. Please complete the payment via the link above, "
            "then tap this button again."
        )
        return

    await db.set_user_state(user_id, State.DELIVERY)
    success = await deliver_pack(context.bot, user_id, pack_id, purchase["id"])

    if success:
        await db.set_user_state(user_id, State.UPSELL)
        upsell_text = await persona_message("upsell")
        await context.bot.send_message(
            chat_id=user_id,
            text=upsell_text,
            reply_markup=upsell_keyboard(),
        )
    else:
        await update.effective_message.reply_text(
            "There was an issue sending your content. Please contact support or try again shortly."
        )


# ── Exit ──────────────────────────────────────────────────────────────────────

async def _handle_exit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await db.set_user_state(user_id, State.EXIT)
    exit_text = await persona_message("exit")
    await update.effective_message.reply_text(exit_text)


# ── Fallback for plain text messages ─────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _guard(update):
        return
    await _get_or_create_user(update)
    # Nudge the user back into the flow
    await update.message.reply_text(
        "Use the menu to browse packs 👇",
        reply_markup=main_menu_keyboard(),
    )
