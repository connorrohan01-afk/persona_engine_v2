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
from response_library import pick_line
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

# Turns in OFFER state before Luna will consider re-showing pack buttons
_OFFER_COOLDOWN_TURNS = 5
# Max turns in OFFER without a click before dropping back to warmup
_OFFER_MAX_TURNS = 10
# Min turns between consecutive soft-invite / pack-intro moments
_PACK_INTRO_COOLDOWN = 4
# Minimum turns before vault fires for a HIGH intent user (bypasses stage gate)
_HIGH_INTENT_MIN_TURNS = 2

# 6-stage escalation model — offer only unlocks after partial_reveal
# Stage 1 HOOK:          light tease, playful tension, no selling
# Stage 2 INTRIGUE:      imply they're different, make them feel selected
# Stage 3 MICRO_REWARD:  small emotional payoff, slight warmth shift
# Stage 4 TENSION_BUILD: pull back, make them want more
# Stage 5 TEASE:         hint at what exists without explaining
# Stage 6 PARTIAL_REVEAL: close to unlocking — THEN introduce vault
_STAGE_ORDER = ["hook", "intrigue", "micro_reward", "tension_build", "tease", "partial_reveal"]

# Minimum engaged turns per stage before advancing
_STAGE_THRESHOLDS: dict[str, int] = {
    "hook":          1,
    "intrigue":      2,
    "micro_reward":  2,
    "tension_build": 2,
    "tease":         2,
    # partial_reveal: no threshold — terminal pre-offer stage
}

# Maps conversation stage → response library category for normal (non-intent) turns
_STAGE_TO_CATEGORY: dict[str, str] = {
    "hook":          "tension",    # Stage 1: light tease, establish intrigue
    "intrigue":      "pull",       # Stage 2: selective attention, feel chosen
    "micro_reward":  "pull",       # Stage 3: slight warmth, small payoff
    "tension_build": "tension",    # Stage 4: pull back, increase want
    "tease":         "curiosity",  # Stage 5: hint at what exists
    "partial_reveal": "reward",    # Stage 6: close to unlocking
    "post_offer":    "pull",       # hold interest, no spam
    "post_purchase": "pull",
}

# Migrate any legacy stage names (from sessions started before the 6-stage model)
_STAGE_MIGRATION: dict[str, str] = {
    "warmup":       "intrigue",
    "tension":      "tension_build",
    "curiosity":    "tease",
    "reveal_ready": "partial_reveal",
}


def _stage_to_category(stage: str) -> str:
    return _STAGE_TO_CATEGORY.get(stage, "tension")

# Phrases signalling curiosity about content — used for stage fast-tracking
_BUYING_CURIOSITY_PHRASES = [
    "what's in", "what is in", "what do i get", "what's included",
    "tell me more", "what kind", "what does it", "see more",
    "what do you have", "what is it", "more info", "can i see",
    "worth it", "how much", "is it worth", "what pack",
    "what's the difference", "show me what",
    # buy-signal additions
    "i want more", "want more", "show me more", "i'm curious",
    "you haven't shown", "haven't shown me", "what else",
    "been holding back", "what are you hiding", "what don't i know",
]

# Phrases that signal real purchase intent (stronger than affirmative)
_BUYING_SIGNAL_PHRASES = [
    "how do i buy", "how do i get", "how do i pay",
    "i'll take", "i'll get", "i want to buy", "i want to get",
    "take the", "want to pay", "sign me up", "send it", "link me",
]

# Phrases that signal clear, explicit intent — trigger immediate vault approach
_STRONG_BUY_PHRASES = [
    "i want more", "show me everything", "i want to see",
    "take my money", "just show me", "let me in",
    "i'm interested", "i want access", "where do i sign",
]


def _is_buying_signal(text: str) -> bool:
    """Strong purchase intent — 'how do I buy', 'I'll take it', etc."""
    text_lower = text.lower()
    words = set(text_lower.split())
    # Unambiguous purchase words (exclude if negated)
    if words & {"buy", "purchase", "paying"} and "not" not in words and "don't" not in words:
        return True
    return any(p in text_lower for p in _BUYING_SIGNAL_PHRASES)


def _is_strong_buy_signal(text: str) -> bool:
    """Explicit, unambiguous interest — triggers immediate 4-step vault approach."""
    text_lower = text.lower()
    if _is_buying_signal(text_lower):
        return True
    return any(p in text_lower for p in _STRONG_BUY_PHRASES)


# Phrases that indicate the user is asking about the content specifically
_CONTENT_QUESTION_PHRASES = [
    "what's in", "what is in", "what do i get", "what's included",
    "more about", "tell me about", "what kind", "what does it",
    "show me", "what's the difference", "which one", "what pack",
    "the vip", "the premium", "the starter", "pack a", "pack b", "pack c",
]


def _is_asking_about_content(text: str) -> bool:
    """User is directly asking about the packs or content — a natural re-offer moment."""
    text_lower = text.lower()
    return any(p in text_lower for p in _CONTENT_QUESTION_PHRASES)


def has_buying_signal(text: str) -> bool:
    """
    Broader curiosity/interest signal for stage fast-tracking.
    Includes direct purchase intent AND content curiosity questions.
    """
    if _is_buying_signal(text):
        return True
    text_lower = text.lower()
    return any(p in text_lower for p in _BUYING_CURIOSITY_PHRASES)


def _maybe_advance_stage(
    user_data: dict, intent: str, signal: bool, intent_level: str = "low"
) -> str:
    """
    Advance conversation_stage through the 6-stage escalation model.

    HIGH intent  — pushes directly to tease/partial_reveal immediately.
    MID intent   — advances at half the normal per-stage threshold.
    Signal       — fast-tracks past early stages.
    Dry/exit     — holds the current stage.
    """
    stage = user_data.get("conversation_stage", "hook")

    if stage in _STAGE_MIGRATION:
        stage = _STAGE_MIGRATION[stage]
        user_data["conversation_stage"] = stage

    if stage not in _STAGE_ORDER:
        return stage

    # HIGH intent: jump past slow-build stages immediately
    if intent_level == "high":
        if stage in ("hook", "intrigue", "micro_reward", "tension_build"):
            user_data["conversation_stage"] = "tease"
            user_data["stage_turn_count"] = 0
            return "tease"
        if stage == "tease":
            user_data["conversation_stage"] = "partial_reveal"
            user_data["stage_turn_count"] = 0
            return "partial_reveal"

    # Buying/curiosity signal fast-tracks
    if signal:
        if stage in ("hook", "intrigue", "micro_reward"):
            user_data["conversation_stage"] = "tease"
            user_data["stage_turn_count"] = 0
            return "tease"
        if stage in ("tension_build", "tease"):
            user_data["conversation_stage"] = "partial_reveal"
            user_data["stage_turn_count"] = 0
            return "partial_reveal"

    if intent in ("exit", "dry"):
        return stage

    stage_turns = user_data.get("stage_turn_count", 0) + 1
    user_data["stage_turn_count"] = stage_turns

    # MID intent: advance at half the threshold — engaged users don't wait as long
    threshold = _STAGE_THRESHOLDS.get(stage, 999)
    if intent_level == "mid":
        threshold = max(1, threshold // 2)

    if stage_turns >= threshold:
        try:
            idx = _STAGE_ORDER.index(stage)
        except ValueError:
            return stage
        if idx + 1 < len(_STAGE_ORDER):
            new_stage = _STAGE_ORDER[idx + 1]
            user_data["conversation_stage"] = new_stage
            user_data["stage_turn_count"] = 0
            return new_stage

    return stage


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


_EXIT_WORDS = {"bye", "goodbye", "cya"}
_EXIT_PHRASES = ["ok bye", "okay bye", "gotta go", "have to go", "see ya", "ttyl", "gtg", "talk later"]


def _is_exit_attempt(text: str) -> bool:
    """Soft exit signal — 'bye', 'ok bye', 'gotta go'. Distinct from content rejection."""
    text_lower = text.lower().strip()
    words = set(text_lower.split())
    if words & _EXIT_WORDS:
        return True
    return any(p in text_lower for p in _EXIT_PHRASES)


def _is_dry(text: str) -> bool:
    """One- to three-word low-effort reply that isn't a clear signal of any kind."""
    words = text.strip().split()
    if len(words) > 3:
        return False
    # Don't classify a meaningful short signal as dry
    return not (
        _is_affirmative(text)
        or _is_negative(text)
        or _is_buying_signal(text)
        or _is_hesitant(text)
        or _is_exit_attempt(text)
    )


# ── Intent level classification ───────────────────────────────────────────────

_HIGH_INTENT_PHRASES = [
    "what is it", "what's in it", "how much", "what does it cost",
    "worth it", "is it worth", "i want", "want to see",
    "what do i get", "what do you have", "tell me more",
    "what's included", "more info", "how do i get",
    "i'm interested", "interested in", "i want more", "show me more",
    "what pack", "what's the difference", "show me", "let me see",
    "what are you hiding", "what's behind", "what don't i see",
]


def _classify_intent_level(text: str, intent: str, signal: bool) -> str:
    """
    LOW  — passive, short, dry, unresponsive
    MID  — engaged, asking questions, playing along
    HIGH — signalling desire, asking price, expressing want, curiosity about content
    Drives vault timing and stage acceleration.
    """
    text_lower = text.lower()
    if signal or any(p in text_lower for p in _HIGH_INTENT_PHRASES):
        return "high"
    if intent in ("exit", "dry"):
        return "low"
    words = text.strip().split()
    if len(words) >= 4 or "?" in text or intent in ("normal", "objection"):
        return "mid"
    if len(words) >= 2 and intent == "normal":
        return "mid"
    return "low"


_MEETUP_WORDS = {"meet", "meetup", "irl"}
_MEETUP_PHRASES = [
    "come over", "where are you", "where you at", "link up", "can i see you",
    "are you near", "where do you live", "in person", "real life", "your location",
]

_OBJECTION_PHRASES = [
    "not worth it", "too expensive", "not sure if", "don't think so",
    "idk if it", "is it worth", "not for me", "not interested",
]


def detect_intent(text: str, last_message: str | None = None) -> str:
    """
    Classify a user message into a routing intent.
    Determines whether to use a library response or fall through to LLM.
    """
    text_lower = text.lower().strip()
    words = set(text_lower.split())

    # Meetup — always redirect, never reject directly
    if words & _MEETUP_WORDS or any(p in text_lower for p in _MEETUP_PHRASES):
        return "meetup"

    # Repeat — same text as their previous message
    if last_message and text_lower == last_message.lower().strip():
        return "repeat_test"

    # Exit — soft disengagement
    if _is_exit_attempt(text):
        return "exit"

    # Objection — hesitation or explicit doubt about value
    if _is_hesitant(text) or any(p in text_lower for p in _OBJECTION_PHRASES):
        return "objection"

    # Dry — low-effort, low-word-count reply
    if _is_dry(text):
        return "dry"

    return "normal"


# ── Response memory helpers ──────────────────────────────────────────────────



def _track_response(user_data: dict, category: str, line: str) -> None:
    """Record a sent response in session memory for anti-repetition and stall tracking."""
    user_data["last_response_category"] = category

    recent_cats = user_data.get("recent_categories", [])
    recent_cats.append(category)
    user_data["recent_categories"] = recent_cats[-3:]

    recent_lines_used = user_data.get("recent_lines", [])
    recent_lines_used.append(line)
    user_data["recent_lines"] = recent_lines_used[-2:]

    # Stall counter — resets on any escalating category, increments on low-energy ones
    _low_energy = {"dry", "challenge", "redirect", "repeat"}
    if category in _low_energy:
        user_data["stall_count"] = user_data.get("stall_count", 0) + 1
    else:
        user_data["stall_count"] = 0


def _is_stalling(user_data: dict) -> bool:
    """Two consecutive low-energy responses without escalation → stalling."""
    return user_data.get("stall_count", 0) >= 2


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
            "hey, you're back. just say something",
        )
        return

    # Fresh start — one greeting, no keyboards, no packs, wait for reply
    await db.set_user_state(user_id, State.WARMUP)
    context.user_data["conversation_stage"] = "hook"
    context.user_data["stage_turn_count"] = 0
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
    context.user_data["offer_turn_count"] = 0
    context.user_data["last_offer_turn"] = context.user_data.get("current_turn", 0)
    context.user_data["conversation_stage"] = "post_offer"
    context.user_data["stage_turn_count"] = 0

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
        "tap the button when you're ready",
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
        context.user_data["conversation_stage"] = "post_purchase"
        context.user_data["stage_turn_count"] = 0
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

    # ── Intent classification ─────────────────────────────────────────────────
    last_message = context.user_data.get("last_message")
    intent = detect_intent(text, last_message)
    context.user_data["last_message"] = text

    # ── Meetup redirect — intercept before all state routing ─────────────────
    if intent == "meetup":
        reply = pick_line("redirect", context.user_data.get("recent_lines", []))
        _track_response(context.user_data, "redirect", reply)
        await _type_and_send(context.bot, chat_id, reply)
        return

    # ── Repeat test — call out the loop ──────────────────────────────────────
    if intent == "repeat_test":
        reply = pick_line("repeat", context.user_data.get("recent_lines", []))
        _track_response(context.user_data, "repeat", reply)
        await _type_and_send(context.bot, chat_id, reply)
        return

    # ── Exit interception: one re-engagement attempt before allowing exit ─────
    if intent == "exit" and state not in (State.EXIT, State.PAYMENT_PENDING):
        exit_count = context.user_data.get("exit_attempts", 0)
        if exit_count == 0:
            context.user_data["exit_attempts"] = 1
            recent = context.user_data.get("recent_lines", [])
            reply = pick_line("retention", recent)
            _track_response(context.user_data, "retention", reply)
            await _type_and_send(context.bot, chat_id, reply)
            # If user was deep in the funnel, add a vault hint after the retention line
            current_stage = context.user_data.get("conversation_stage", "hook")
            if current_stage in ("tease", "partial_reveal"):
                await asyncio.sleep(random.uniform(2.0, 3.0))
                recent = context.user_data.get("recent_lines", [])
                vault_hint = pick_line("curiosity", recent)
                _track_response(context.user_data, "curiosity", vault_hint)
                await _type_and_send(context.bot, chat_id, vault_hint, delay=0.8)
            return
        # Second exit attempt — let them go
        context.user_data.pop("exit_attempts", None)
        await db.set_user_state(user_id, State.EXIT)
        exit_msg = await persona_message("exit")
        await _type_and_send(context.bot, chat_id, exit_msg)
        return

    # Any non-exit message resets the exit attempt counter
    context.user_data.pop("exit_attempts", None)

    # ── WARMUP: engage naturally, track turns, advance when ready ────────────
    if state in (State.GREETING, State.WARMUP):
        turn_count = await db.increment_turn_count(user_id)
        context.user_data["current_turn"] = turn_count
        score_delta = _score_message(text)
        engagement = await db.update_engagement_score(user_id, score_delta)

        signal = has_buying_signal(text)
        strong = _is_strong_buy_signal(text)
        intent_level = _classify_intent_level(text, intent, signal)
        stage = _maybe_advance_stage(context.user_data, intent, signal, intent_level)

        # Track intent escalation — reward users who lean in
        prev_intent_level = context.user_data.get("last_intent_level", "low")
        context.user_data["last_intent_level"] = intent_level
        intent_escalated = (
            (prev_intent_level == "low" and intent_level in ("mid", "high"))
            or (prev_intent_level == "mid" and intent_level == "high")
        )

        last_offer_turn = context.user_data.get("last_offer_turn", -_PACK_INTRO_COOLDOWN)
        # High-intent users aren't held at a long cooldown — act when they're ready
        cooldown_threshold = 2 if intent_level == "high" else _PACK_INTRO_COOLDOWN
        cooldown_ok = (turn_count - last_offer_turn) >= cooldown_threshold

        # ── Vault decision ────────────────────────────────────────────────────
        # HIGH intent: vault after _HIGH_INTENT_MIN_TURNS (2) regardless of stage
        # Strong buy signal: vault after normal min turns
        # Natural progression: vault when stage reaches partial_reveal
        vault_now = (
            engagement >= 0
            and cooldown_ok
            and (
                (intent_level == "high" and turn_count >= _HIGH_INTENT_MIN_TURNS)
                or (strong and turn_count >= _WARMUP_MIN_TURNS)
                or stage == "partial_reveal"
            )
        )
        if vault_now:
            context.user_data["conversation_stage"] = "partial_reveal"
            recent = context.user_data.get("recent_lines", [])
            framing = pick_line("reward", recent)
            _track_response(context.user_data, "reward", framing)
            await _type_and_send(context.bot, chat_id, framing)
            await asyncio.sleep(random.uniform(1.2, 2.0))
            await _show_packs(update, context)
            return

        # ── Normal response ───────────────────────────────────────────────────
        recent = context.user_data.get("recent_lines", [])

        # Stall override — two consecutive low-energy replies means we're looping
        if _is_stalling(context.user_data) and intent not in ("exit", "dry"):
            force_cat = "curiosity" if stage in ("tease", "partial_reveal") else "tension"
            reply = pick_line(force_cat, recent)
            _track_response(context.user_data, force_cat, reply)
            await _type_and_send(context.bot, chat_id, reply)
            return

        if intent == "dry":
            reply = pick_line("dry", recent)
            _track_response(context.user_data, "dry", reply)
        elif intent == "objection":
            # High-intent hesitation: use curiosity pull, not pushback
            cat = "curiosity" if intent_level == "high" else "challenge"
            reply = pick_line(cat, recent)
            _track_response(context.user_data, cat, reply)
        elif intent_escalated:
            # User leaned in — reward the investment with selective attention
            reply = pick_line("pull", recent)
            _track_response(context.user_data, "pull", reply)
        else:
            cat = _stage_to_category(stage)
            reply = pick_line(cat, recent)
            _track_response(context.user_data, cat, reply)
        await _type_and_send(context.bot, chat_id, reply)
        return

    # ── SOFT_INVITE: show packs only on clear signal, never by default ───────
    if state == State.SOFT_INVITE:
        invite_attempts = context.user_data.get("soft_invite_attempts", 0)

        if _is_affirmative(text) or _is_buying_signal(text):
            # Clear yes — show packs
            context.user_data.pop("soft_invite_attempts", None)
            await _show_packs(update, context)

        elif _is_negative(text):
            # No means no — don't chase, drop back to warmup
            await db.set_rejection_flag(user_id, 1)
            await db.set_user_state(user_id, State.WARMUP)
            context.user_data.pop("soft_invite_attempts", None)
            reply = await chat_reply(text, context={"stage": "rejected"})
            await _type_and_send(context.bot, chat_id, reply)

        elif invite_attempts >= 2:
            # She's not chasing. Drop back to warmup naturally — door stays open.
            context.user_data.pop("soft_invite_attempts", None)
            await db.set_user_state(user_id, State.WARMUP)
            reply = await chat_reply(text, context={"stage": "rejected"})
            await _type_and_send(context.bot, chat_id, reply)

        else:
            # Hesitant, chatting, or ambiguous — respond in character, increment counter
            context.user_data["soft_invite_attempts"] = invite_attempts + 1
            signal = has_buying_signal(text)
            intent_level = _classify_intent_level(text, intent, signal)
            stage = _maybe_advance_stage(context.user_data, intent, signal, intent_level)
            recent = context.user_data.get("recent_lines", [])
            if intent == "objection":
                reply = pick_line("objection", recent)
                _track_response(context.user_data, "objection", reply)
            elif intent == "dry":
                reply = pick_line("dry", recent)
                _track_response(context.user_data, "dry", reply)
            else:
                cat = _stage_to_category(stage)
                reply = pick_line(cat, recent)
                _track_response(context.user_data, cat, reply)
            await _type_and_send(context.bot, chat_id, reply)

        return

    # ── CURIOSITY: treat like WARMUP with intent awareness ───────────────────
    if state == State.CURIOSITY:
        signal = has_buying_signal(text)
        strong = _is_strong_buy_signal(text)
        intent_level = _classify_intent_level(text, intent, signal)
        stage = _maybe_advance_stage(context.user_data, intent, signal, intent_level)
        turn_count = context.user_data.get("current_turn", 0)
        last_offer_turn = context.user_data.get("last_offer_turn", -_PACK_INTRO_COOLDOWN)
        cooldown_threshold = 2 if intent_level == "high" else _PACK_INTRO_COOLDOWN
        cooldown_ok = (turn_count - last_offer_turn) >= cooldown_threshold
        if cooldown_ok and (intent_level == "high" or strong or stage == "partial_reveal"):
            recent = context.user_data.get("recent_lines", [])
            framing = pick_line("reward", recent)
            _track_response(context.user_data, "reward", framing)
            await _type_and_send(context.bot, chat_id, framing)
            await asyncio.sleep(random.uniform(1.2, 2.0))
            await _show_packs(update, context)
            return
        recent = context.user_data.get("recent_lines", [])
        if intent == "dry":
            reply = pick_line("dry", recent)
            _track_response(context.user_data, "dry", reply)
        elif intent == "objection":
            cat = "curiosity" if intent_level == "high" else "challenge"
            reply = pick_line(cat, recent)
            _track_response(context.user_data, cat, reply)
        else:
            cat = _stage_to_category(stage)
            reply = pick_line(cat, recent)
            _track_response(context.user_data, cat, reply)
        await _type_and_send(context.bot, chat_id, reply)
        return

    # ── OFFER: user chatting after seeing packs — never auto-repeat buttons ───
    if state == State.OFFER:
        offer_turns = context.user_data.get("offer_turn_count", 0)

        if _is_buying_signal(text):
            # Explicit purchase intent — re-show packs immediately
            context.user_data["offer_turn_count"] = 0
            await _show_packs(update, context)
            return

        offer_turns += 1
        context.user_data["offer_turn_count"] = offer_turns

        if offer_turns >= _OFFER_MAX_TURNS:
            # Too long without clicking — drop back to warmup gracefully, no pressure
            context.user_data["offer_turn_count"] = 0
            await db.set_user_state(user_id, State.WARMUP)
            reply = await chat_reply(text, context={"stage": "rejected"})
            await _type_and_send(context.bot, chat_id, reply)
            return

        if _is_negative(text):
            # Hard no — back to warmup, leave door open
            context.user_data["offer_turn_count"] = 0
            await db.set_user_state(user_id, State.WARMUP)
            reply = await chat_reply(text, context={"stage": "rejected"})
            await _type_and_send(context.bot, chat_id, reply)
            return

        if offer_turns >= _OFFER_COOLDOWN_TURNS and _is_asking_about_content(text):
            # User is asking directly about the content after a gap — natural re-offer moment
            context.user_data["offer_turn_count"] = 0
            await _show_packs(update, context)
            return

        # Default: respond conversationally — no buttons, no re-offer push
        stage = context.user_data.get("conversation_stage", "post_offer")
        recent = context.user_data.get("recent_lines", [])
        if intent == "objection":
            reply = pick_line("challenge", recent)
            _track_response(context.user_data, "challenge", reply)
        elif intent == "dry":
            reply = pick_line("dry", recent)
            _track_response(context.user_data, "dry", reply)
        else:
            cat = _stage_to_category(stage)
            reply = pick_line(cat, recent)
            _track_response(context.user_data, cat, reply)
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
