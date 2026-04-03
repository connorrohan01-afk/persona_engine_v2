"""
Conversation handlers — state machine driven, LLM for tone only.

Flow: GREETING → WARMUP (3-5 turns) → CURIOSITY → SOFT_INVITE → OFFER → PREVIEW → PAYMENT_PENDING → DELIVERY → UPSELL
"""

import asyncio
import logging
import random

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

import db
from config import PACKS
from delivery import deliver_pack, send_sample_images
from keyboards import (
    pack_detail_keyboard,
    packs_keyboard,
    payment_done_keyboard,
    upsell_keyboard,
)
from llm import chat_reply, persona_message
from states import State

logger = logging.getLogger(__name__)

# Words that signal positive engagement / interest
_POSITIVE = {
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "please",
    "show", "go", "tell", "more", "nice", "wow", "cool", "love",
    "omg", "lol", "haha", "hehe", "interested", "want", "do it",
    "lets", "let's", "great", "amazing", "awesome", "sounds", "good",
}

# Words that signal disinterest or rejection
_NEGATIVE = {
    "no", "nope", "nah", "stop", "leave", "bye", "goodbye", "block",
    "boring", "whatever", "not", "quit", "exit", "unsubscribe",
}

# Words/phrases that signal hesitation or ambiguity (≠ rejection, ≠ affirmative)
_HESITANT_WORDS = {
    "maybe", "idk", "dunno", "hmm", "hm", "worth", "expensive",
    "pricey", "unsure", "depends", "suppose", "guess",
}
_HESITANT_PHRASES = [
    "not sure", "is it worth", "i don't know", "i dunno",
    "i guess", "worth the", "worth it", "how much", "that much",
    "just browsing", "only browsing",
]

# Minimum warmup turns before triggering curiosity
_WARMUP_MIN_TURNS = 3

# Turns in OFFER state required before re-showing pack buttons
_OFFER_COOLDOWN_TURNS = 3

# Phrases that signal real purchase intent (stronger than affirmative)
_BUYING_SIGNAL_PHRASES = [
    "how do i buy", "how do i get", "how do i pay",
    "i'll take", "i'll get", "i want to buy", "i want to get",
    "take the", "want to pay", "sign me up", "send it", "link me",
]


def _is_buying_signal(text: str) -> bool:
    """Strong purchase intent — 'how do I buy', 'I'll take it', etc."""
    text_lower = text.lower()
    words = set(text_lower.split())
    # Unambiguous purchase words (exclude if negated)
    if words & {"buy", "purchase", "paying"} and "not" not in words and "don't" not in words:
        return True
    return any(p in text_lower for p in _BUYING_SIGNAL_PHRASES)


# ── Pacing helper ─────────────────────────────────────────────────────────────

async def _type_and_send(
    bot,
    chat_id: int,
    text: str,
    delay: float | None = None,
    **kwargs,
):
    """Show typing indicator, pause, then send message."""
    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    await asyncio.sleep(delay if delay is not None else random.uniform(1.2, 2.0))
    return await bot.send_message(chat_id=chat_id, text=text, **kwargs)


# ── Engagement helpers ────────────────────────────────────────────────────────

def _score_message(text: str) -> int:
    """Return +1 (positive), -1 (negative), or 0 (neutral) for a user message."""
    words = set(text.lower().split())
    if words & _POSITIVE:
        return 1
    if words & _NEGATIVE:
        return -1
    # Short replies often signal engagement too
    if len(text.strip()) > 2:
        return 1
    return 0


def _is_affirmative(text: str) -> bool:
    """Return True if the message is a clear yes/go-ahead.
    Hesitant phrasing ('not sure', 'maybe') takes priority and returns False.
    """
    # Hesitant always wins over accidental keyword matches
    if _is_hesitant(text):
        return False
    text_lower = text.lower().strip()
    words = set(text_lower.split())
    # "sure" only counts when not negated ("not sure" → hesitant, handled above)
    direct = bool(words & {"yes", "yeah", "yep", "yup", "ok", "okay",
                            "please", "go", "show", "do", "lets", "let's"})
    if "sure" in words and "not" not in words:
        direct = True
    phrase = any(p in text_lower for p in ["show me", "go ahead", "of course",
                                            "let's go", "lets go", "why not"])
    return direct or phrase


def _is_negative(text: str) -> bool:
    words = set(text.lower().split())
    return bool(words & {"no", "nope", "nah", "not", "stop", "bye", "quit"})


def _is_hesitant(text: str) -> bool:
    """
    Return True for ambiguous/hesitant responses that are curiosity in disguise —
    'maybe', 'not sure', 'is it worth it', 'I guess', 'just browsing'.
    These should trigger a flirty exchange, NOT immediate pack display.
    """
    text_lower = text.lower()
    words = set(text_lower.split())
    if words & _HESITANT_WORDS:
        return True
    return any(p in text_lower for p in _HESITANT_PHRASES)


# ── Guard / user helper ───────────────────────────────────────────────────────

async def _guard(update: Update) -> bool:
    """Return True (and reply) if user is banned."""
    if await db.is_banned(update.effective_user.id):
        await update.effective_message.reply_text(
            "Your access to this bot has been restricted."
        )
        return True
    return False


async def _get_or_create_user(update: Update) -> dict:
    u = update.effective_user
    return await db.upsert_user(u.id, u.username)


# ── /start ────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _guard(update):
        return

    user = await _get_or_create_user(update)
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Resume if mid-funnel
    if user["state"] not in (State.GREETING, State.EXIT):
        await _type_and_send(
            context.bot, chat_id,
            "hey, you're back 👀 just say something and we'll pick up where we left off",
        )
        return

    # Fresh start — one greeting, no keyboards, no packs, wait for reply
    await db.set_user_state(user_id, State.WARMUP)
    greeting = await persona_message("greeting")
    await _type_and_send(context.bot, chat_id, greeting)


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
        await _show_pack_preview(update, context, pack_id)
    elif data.startswith("paid_"):
        pack_id = data[len("paid_"):]
        await _handle_paid_claim(update, context, pack_id)
    elif data == "exit":
        await _handle_exit(update, context)
    else:
        logger.warning("Unknown callback_data: %s", data)


# ── Offer / packs ─────────────────────────────────────────────────────────────

async def _show_packs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    await db.set_user_state(user_id, State.OFFER)
    await db.set_last_offer_time(user_id)
    context.user_data["offer_turn_count"] = 0  # reset cooldown on every pack display

    intro = await persona_message("offer_intro")
    await _type_and_send(context.bot, chat_id, intro, reply_markup=packs_keyboard())


# ── Pack preview (PREVIEW state) ──────────────────────────────────────────────

async def _show_pack_preview(
    update: Update, context: ContextTypes.DEFAULT_TYPE, pack_id: str
):
    if pack_id not in PACKS:
        await update.effective_message.reply_text("hmm, can't find that one")
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    pack = PACKS[pack_id]

    await db.set_user_state(user_id, State.PREVIEW)

    # 1. Send preview images (best-effort, no crash if missing)
    await send_sample_images(context.bot, chat_id, pack_id)

    # 2. Teasing message
    preview_text = await persona_message("preview")
    await _type_and_send(context.bot, chat_id, preview_text, delay=1.0)

    # 3. Pack detail + buy button
    payment_line = await persona_message("payment")
    detail = (
        f"{pack['emoji']} {pack['name']} — ${pack['price_usd']}\n\n"
        f"{pack['description']}\n\n"
        f"{payment_line}"
    )
    await _type_and_send(
        context.bot, chat_id, detail,
        delay=1.2,
        reply_markup=pack_detail_keyboard(pack_id),
    )

    # 4. Transition to PAYMENT_PENDING and record pending purchase
    await db.set_user_state(user_id, State.PAYMENT_PENDING)
    if not await db.get_undelivered_purchase(user_id, pack_id):
        await db.create_purchase(
            user_id=user_id,
            pack_id=pack_id,
            stripe_session=None,
            amount_cents=pack["amount_cents"],
        )

    # 5. "I've paid" fallback button
    await _type_and_send(
        context.bot, chat_id,
        "tap below once you're done 👇",
        delay=0.8,
        reply_markup=payment_done_keyboard(pack_id),
    )


# ── Manual "I've paid" claim ──────────────────────────────────────────────────

async def _handle_paid_claim(
    update: Update, context: ContextTypes.DEFAULT_TYPE, pack_id: str
):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if await db.has_been_delivered(user_id, pack_id):
        await _type_and_send(
            context.bot, chat_id,
            "you already have this one! scroll up 👆"
        )
        return

    purchase = await db.get_undelivered_purchase(user_id, pack_id)
    if not purchase:
        await _type_and_send(
            context.bot, chat_id,
            "i haven't seen your payment come through yet — try again in a sec or use the link above"
        )
        return

    await db.set_user_state(user_id, State.DELIVERY)
    success = await deliver_pack(context.bot, user_id, pack_id, purchase["id"])

    if success:
        await db.set_user_state(user_id, State.UPSELL)
        delivery_msg = await persona_message("delivery")
        await _type_and_send(context.bot, chat_id, delivery_msg, delay=1.0)
        # Light upsell — wait a beat so it doesn't feel instant
        await asyncio.sleep(2.5)
        upsell_msg = await chat_reply("", context={"stage": "upsell"})
        await _type_and_send(
            context.bot, chat_id, upsell_msg,
            delay=1.5,
            reply_markup=upsell_keyboard(),
        )
    else:
        await _type_and_send(
            context.bot, chat_id,
            "something went wrong on my end — drop me a message and i'll sort it"
        )


# ── Exit ──────────────────────────────────────────────────────────────────────

async def _handle_exit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    await db.set_user_state(user_id, State.EXIT)
    exit_msg = await persona_message("exit")
    await _type_and_send(context.bot, chat_id, exit_msg)


# ── Main message handler ──────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _guard(update):
        return

    user = await _get_or_create_user(update)
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text = update.message.text or ""
    state = user["state"]

    # ── WARMUP: engage naturally, track turns, advance when ready ────────────
    if state in (State.GREETING, State.WARMUP):
        turn_count = await db.increment_turn_count(user_id)
        score_delta = _score_message(text)
        engagement = await db.update_engagement_score(user_id, score_delta)

        reply = await chat_reply(text, context={"stage": "warmup"})
        await _type_and_send(context.bot, chat_id, reply)

        # Advance to CURIOSITY when enough engaged turns have happened
        if turn_count >= _WARMUP_MIN_TURNS and engagement >= 0:
            await db.set_user_state(user_id, State.CURIOSITY)
            # Curiosity hint after a natural pause
            await asyncio.sleep(random.uniform(1.5, 2.5))
            curiosity_msg = await chat_reply(text, context={"stage": "curiosity"})
            await _type_and_send(context.bot, chat_id, curiosity_msg, delay=1.5)
            # Immediately follow with soft invite
            await asyncio.sleep(random.uniform(1.0, 1.8))
            soft_invite_msg = await chat_reply("", context={"stage": "soft_invite"})
            await _type_and_send(context.bot, chat_id, soft_invite_msg, delay=1.2)
            await db.set_user_state(user_id, State.SOFT_INVITE)
        return

    # ── SOFT_INVITE: gate pack display behind engagement signal ──────────────
    if state == State.SOFT_INVITE:
        # Track how many times we've already done a flirty exchange here
        invite_attempts = context.user_data.get("soft_invite_attempts", 0)

        if _is_affirmative(text):
            # Clear yes — show packs immediately
            context.user_data.pop("soft_invite_attempts", None)
            await _show_packs(update, context)

        elif _is_negative(text) and invite_attempts == 0:
            # First clear no — back to warmup, leave door open
            await db.set_rejection_flag(user_id, 1)
            await db.set_user_state(user_id, State.WARMUP)
            context.user_data.pop("soft_invite_attempts", None)
            reply = await chat_reply(text, context={"stage": "rejected"})
            await _type_and_send(context.bot, chat_id, reply)

        elif _is_hesitant(text) and invite_attempts == 0:
            # First hesitant/ambiguous reply — one flirty exchange, stay in SOFT_INVITE
            context.user_data["soft_invite_attempts"] = 1
            reply = await chat_reply(text, context={"stage": "hesitant"})
            await _type_and_send(context.bot, chat_id, reply)

        else:
            # Second response (any kind) or second no — show packs, they've been warmed enough
            context.user_data.pop("soft_invite_attempts", None)
            await _show_packs(update, context)

        return

    # ── CURIOSITY: shouldn't normally receive a text here, treat like WARMUP ─
    if state == State.CURIOSITY:
        reply = await chat_reply(text, context={"stage": "warmup"})
        await _type_and_send(context.bot, chat_id, reply)
        return

    # ── OFFER: user is chatting instead of clicking — apply cooldown logic ───
    if state == State.OFFER:
        offer_turns = context.user_data.get("offer_turn_count", 0)

        if _is_buying_signal(text):
            # Unambiguous purchase intent — re-show packs now regardless of cooldown
            context.user_data["offer_turn_count"] = 0
            await _show_packs(update, context)
            return

        # Increment turns-since-last-offer counter
        offer_turns += 1
        context.user_data["offer_turn_count"] = offer_turns

        if offer_turns >= _OFFER_COOLDOWN_TURNS:
            # Cooldown passed — re-introduce packs naturally, but only if not a hard no
            if _is_negative(text):
                # They're drifting away — drop back to warmup, no pressure
                context.user_data["offer_turn_count"] = 0
                await db.set_user_state(user_id, State.WARMUP)
                reply = await chat_reply(text, context={"stage": "rejected"})
                await _type_and_send(context.bot, chat_id, reply)
            else:
                # Re-engage then re-offer: one conversational line, then buttons
                context.user_data["offer_turn_count"] = 0
                bridge = await chat_reply(text, context={"stage": "post_offer"})
                await _type_and_send(context.bot, chat_id, bridge)
                await asyncio.sleep(random.uniform(1.0, 1.6))
                await _show_packs(update, context)
        else:
            # Still within cooldown — respond conversationally, no buttons
            if _is_hesitant(text) or _is_negative(text):
                reply = await chat_reply(text, context={"stage": "objection"})
            else:
                reply = await chat_reply(text, context={"stage": "post_offer"})
            await _type_and_send(context.bot, chat_id, reply)

        return

    # ── PAYMENT_PENDING: reassure, don't spam ─────────────────────────────────
    if state == State.PAYMENT_PENDING:
        await _type_and_send(
            context.bot, chat_id,
            "just use the link above to pay and then hit that button — i'll send everything over right away",
            delay=1.0,
        )
        return

    # ── UPSELL: light touch — no repeated keyboard ────────────────────────────
    if state == State.UPSELL:
        if _is_affirmative(text) or _is_buying_signal(text):
            await _show_packs(update, context)
        elif _is_negative(text):
            await db.set_user_state(user_id, State.EXIT)
            exit_msg = await persona_message("exit")
            await _type_and_send(context.bot, chat_id, exit_msg)
        else:
            # Conversational reply only — keyboard was already shown at delivery
            reply = await chat_reply(text, context={"stage": "upsell"})
            await _type_and_send(context.bot, chat_id, reply)
        return

    # ── EXIT / fallback: never go silent ─────────────────────────────────────
    reply = await chat_reply(text, context={"stage": "warmup"})
    await _type_and_send(context.bot, chat_id, reply)
