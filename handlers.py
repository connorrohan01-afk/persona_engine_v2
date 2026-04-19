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
from llm import (
    chat_reply,
    is_natural_message,
    persona_message,
    pick_tease_asset,
    pick_image_pre_line,
    pick_image_vault_transition,
    sanitize_reply,
)
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

# Phrases that signal explicit, firm rejection — distinct from hesitation
_STRONG_RESISTANCE_PHRASES = [
    "not interested",
    "not my type",
    "not for me",
    "i don't pay",
    "i dont pay",
    "don't pay for",
    "dont pay for",
    "never paying",
    "not paying",
    "hard pass",
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

# State 1 → 2 transition: turns in HOOK before advancing to BUILD
_HOOK_TURNS = 3
# State 4 lock: minimum turns in POST_TEASE before vault can fire
_POST_TEASE_MIN_TURNS = 2
# State 4 ceiling: after this many turns in POST_TEASE, vault fires regardless
_POST_TEASE_MAX_TURNS = 5

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
    "partial_reveal": "curiosity",  # Stage 6: highest tension — pure escalation
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
    "what's the difference", "which one", "what pack",
    "the vip", "the premium", "the starter", "pack a", "pack b", "pack c",
]

# High-intent buying questions — "what happens if I get it", "then what", etc.
_HIGH_INTENT_QUESTION_PHRASES = [
    "what happens if i get", "what happens if i buy", "what happens after",
    "what do i get", "then what", "and then what", "what next",
    "what would i get", "what would happen", "what changes",
    "so what do i get", "so what happens",
]


def _is_asking_about_content(text: str) -> bool:
    """User is directly asking about the packs or content — a natural re-offer moment."""
    text_lower = text.lower()
    return any(p in text_lower for p in _CONTENT_QUESTION_PHRASES)


def _is_high_intent_question(text: str) -> bool:
    """User is asking what they get or what happens — high-intent buying curiosity."""
    text_lower = text.lower()
    return any(p in text_lower for p in _HIGH_INTENT_QUESTION_PHRASES)


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

    if intent == "exit":
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
    """Show typing indicator, pause, then send message.

    sanitize_reply() runs on every outgoing message as the final output filter.
    """
    text = sanitize_reply(text)
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


def _is_strong_resistance(text: str) -> bool:
    """Explicit, firm rejection of the offer — 'not interested', 'I don't pay', etc.
    Distinct from hesitation (_is_hesitant) and generic negatives (_is_negative).
    Routes to clean exit, not retention.
    """
    text_lower = text.lower()
    return any(p in text_lower for p in _STRONG_RESISTANCE_PHRASES)


_EXIT_WORDS = {"bye", "goodbye", "cya"}
_EXIT_PHRASES = ["ok bye", "okay bye", "gotta go", "have to go", "see ya", "ttyl", "gtg", "talk later"]

_COMPLIMENT_WORDS = {
    "beautiful", "gorgeous", "cute", "hot", "amazing", "stunning",
    "pretty", "attractive", "lovely", "perfect", "sexy",
}
_COMPLIMENT_PHRASES = [
    "you're so", "you look", "love your", "love the way",
    "you're beautiful", "you're gorgeous", "you're cute", "you're hot",
    "you're amazing", "you're stunning", "you're perfect", "you're sexy",
    "that's beautiful", "so pretty", "i like you", "i love you",
    "you sound", "ur hot", "ur cute", "u r hot",
]


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


_SEXUAL_ESCALATION_WORDS: frozenset[str] = frozenset({
    "fuck", "fucking", "sex", "horny", "pussy", "dick", "cock",
    "tits", "boobs", "naked", "nudes", "nude", "nsfw",
})


def _is_sexual_escalation(text: str) -> bool:
    """Explicitly sexual message — escalation state, vault should not fire."""
    return bool(set(text.lower().split()) & _SEXUAL_ESCALATION_WORDS)


def _is_compliment(text: str) -> bool:
    """Direct compliment about appearance or personality — treat as positive momentum."""
    text_lower = text.lower()
    words = set(text_lower.split())
    if words & _COMPLIMENT_WORDS:
        return True
    return any(p in text_lower for p in _COMPLIMENT_PHRASES)


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


# ── Tease-image pillar ────────────────────────────────────────────────────────

# Phrases that are direct, unambiguous requests to see her — safe image triggers.
# Note: "can i see you" hits meetup routing first — intercepted below before meetup fires.
# Excluded: "where are you" — pure location, not visual request.
_IMAGE_TEASE_TRIGGER_PHRASES = [
    "what do you look like",
    "what you look like",
    "send a pic",
    "send pic",
    "send me a pic",
    "send a photo",
    "send me a photo",
    "show yourself",
    "show me a pic",
    "show me a photo",
    "show me you",
    "show me",
    "let me see you",
    "can i see you",
    "got a pic",
    "got any pics",
    "any pics",
    "see a pic",
    "pic of you",
    "photo of you",
    "pic of yourself",
]

# Minimum conversation depth before image can fire
_IMAGE_TEASE_MIN_TURNS = 3
_IMAGE_TEASE_MIN_ENGAGEMENT = 1  # at least one positive signal in the session


def _soft_tease_signal(
    text: str,
    intent: str,
    intent_level: str,
    consecutive_engaged: int = 0,
) -> str | None:
    """
    Return a string describing the matched signal, or None if no signal found.
    Used only in the SOFT path of _should_drop_image_tease.
    """
    if intent_level in ("mid", "high"):
        return f"intent_level={intent_level}"
    if "?" in text:
        return "question"
    if len(text.strip().split()) >= 5:
        return "message_length>=5"
    if _is_compliment(text):
        return "compliment"
    if _is_affirmative(text):
        return "affirmative"
    if consecutive_engaged >= 2:
        return f"consecutive_engaged={consecutive_engaged}"
    return None


def _should_drop_image_tease(
    text: str,
    turn_count: int,
    engagement: int,
    intent: str,
    intent_level: str,
    stage: str,
    already_sent: bool,
    consecutive_engaged: int = 0,
) -> bool:
    """
    Two-path gate for the image-tease pillar.

    DIRECT path — explicit visual request phrase:
      - phrase in _IMAGE_TEASE_TRIGGER_PHRASES
      - turn_count >= 2 (minimal warmup to avoid cold fire)
      - intent not exit/dry

    SOFT path — conversation momentum:
      - turn_count >= _IMAGE_TEASE_MIN_TURNS (4)
      - engagement >= _IMAGE_TEASE_MIN_ENGAGEMENT (1)
      - intent not exit/dry
      - at least one soft signal (mid/high intent, question, length, compliment,
        affirmative, or 2+ consecutive engaged turns)
    """
    if already_sent:
        logger.debug("image_tease: skip — already sent this session")
        return False

    is_direct = any(p in text.lower() for p in _IMAGE_TEASE_TRIGGER_PHRASES)

    # ── DIRECT path ──────────────────────────────────────────────────────────
    if is_direct:
        if intent in ("exit", "dry"):
            logger.debug("image_tease: DIRECT blocked — intent=%s", intent)
            return False
        if turn_count < 2:
            logger.debug("image_tease: DIRECT blocked — turn_count=%d < 2", turn_count)
            return False
        logger.info("image_tease: DIRECT trigger — phrase match turn=%d stage=%s", turn_count, stage)
        return True

    # ── SOFT path ─────────────────────────────────────────────────────────────
    if turn_count < _IMAGE_TEASE_MIN_TURNS:
        logger.debug("image_tease: SOFT blocked — turn_count=%d < %d", turn_count, _IMAGE_TEASE_MIN_TURNS)
        return False
    if engagement < _IMAGE_TEASE_MIN_ENGAGEMENT:
        logger.debug("image_tease: SOFT blocked — engagement=%d < %d", engagement, _IMAGE_TEASE_MIN_ENGAGEMENT)
        return False
    if intent == "exit":
        logger.debug("image_tease: SOFT blocked — intent=exit")
        return False
    # Note: "dry" intent is NOT a hard block here. Short playful messages like
    # "lol", "nice", "haha" are classified as dry but ARE genuine engagement.
    # The signal check below handles quality — if nothing passes, tease doesn't fire.
    signal = _soft_tease_signal(text, intent, intent_level, consecutive_engaged)
    if not signal:
        logger.debug(
            "image_tease: SOFT blocked — no signal (intent_level=%s consecutive=%d text_words=%d)",
            intent_level, consecutive_engaged, len(text.strip().split()),
        )
        return False
    logger.info(
        "image_tease: SOFT trigger — signal=%s stage=%s turn=%d engagement=%d",
        signal, stage, turn_count, engagement,
    )
    return True


def _post_tease_ready(text: str, intent: str, post_tease_turns: int) -> bool:
    """
    True when POST_TEASE state should transition to vault (OFFER).

    Rules:
    - Hard minimum: _POST_TEASE_MIN_TURNS turns must have passed first.
    - Hard maximum: _POST_TEASE_MAX_TURNS turns — vault fires regardless.
    - Between min and max: require at least one qualifying signal:
      curiosity, compliment, affirmative, direct question, or non-exit engagement.
    """
    if post_tease_turns < _POST_TEASE_MIN_TURNS:
        return False
    if post_tease_turns >= _POST_TEASE_MAX_TURNS:
        return True
    # Qualifying signal check
    return (
        "?" in text
        or _is_compliment(text)
        or _is_affirmative(text)
        or intent not in ("exit", "dry")
    )


async def _drop_image_tease(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
) -> None:
    """
    Tease-image flow (first half — runs immediately on trigger):
      1. Micro-hesitation beat
      2. Photo + caption
      3. Post-image line (casual, not hype)
      4. Follow-up curiosity line (tension/reaction — invites user reply)

    Vault transition + buttons are intentionally deferred.
    They fire on the user's next message via the post_tease_pending flag.
    This ensures at least one user reply before any monetization.

    Uses the asset config from llm.TEASE_ASSETS so adding new images
    only requires adding an entry there.
    """
    asset = pick_tease_asset()
    caption = asset.caption()
    post_line = asset.post_line()
    pre_line = pick_image_pre_line()

    logger.info("image_tease: dropping asset=%s", asset.path)

    # Step 1 — micro-hesitation beat before photo
    await _type_and_send(context.bot, chat_id, pre_line, delay=random.uniform(1.0, 1.5))

    # Step 2 — photo
    await context.bot.send_chat_action(chat_id=chat_id, action="upload_photo")
    await asyncio.sleep(random.uniform(1.0, 1.6))
    try:
        with open(asset.path, "rb") as f:
            await context.bot.send_photo(chat_id=chat_id, photo=f, caption=caption)
    except FileNotFoundError:
        logger.error("image_tease: asset not found at %s", asset.path)
        return  # abort — don't send hollow copy without the image
    except Exception as exc:
        logger.error("image_tease: failed to send photo: %s", exc)
        return

    # Step 3 — one short casual line, then stop
    await _type_and_send(context.bot, chat_id, post_line, delay=random.uniform(1.2, 1.8))

    # Enter POST_TEASE state — vault is locked until min turns have passed
    user_id = update.effective_user.id
    await db.set_user_state(user_id, State.POST_TEASE)
    context.user_data["post_tease_turns"] = 0
    logger.info("state: BUILD → POST_TEASE")




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



def _push_history(user_data: dict, user_msg: str, assistant_msg: str) -> None:
    """Append a turn to the in-session history buffer (capped at 16 messages = 8 turns)."""
    history = user_data.get("history", [])
    history.append({"role": "user", "content": user_msg})
    history.append({"role": "assistant", "content": assistant_msg})
    user_data["history"] = history[-16:]


def _track_response(user_data: dict, category: str, line: str) -> None:
    """Record a sent response in session memory for anti-repetition and stall tracking."""
    user_data["last_response_category"] = category

    recent_cats = user_data.get("recent_categories", [])
    recent_cats.append(category)
    user_data["recent_categories"] = recent_cats[-3:]

    recent_lines_used = user_data.get("recent_lines", [])
    recent_lines_used.append(line)
    user_data["recent_lines"] = recent_lines_used[-2:]

    # Stall counter — resets on escalating categories, increments on flat/low-energy ones
    # "tension" and "pull" are escalating but library picks can still feel flat — only reset on LLM turns
    _low_energy = {"dry", "repeat", "tension", "pull", "curiosity"}
    if category in _low_energy:
        user_data["stall_count"] = user_data.get("stall_count", 0) + 1
    else:
        user_data["stall_count"] = 0


def _is_stalling(user_data: dict) -> bool:
    """Two consecutive library/low-energy responses → stalling. Force LLM escalation."""
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
        # Restore conversation progress from DB in case of bot restart
        context.user_data.setdefault(
            "conversation_stage", user.get("conversation_stage", "hook")
        )
        context.user_data.setdefault("stage_turn_count", 0)
        await _type_and_send(
            context.bot, chat_id,
            "hey, you're back. just say something",
        )
        return

    # Fresh start — one greeting, no keyboards, no packs, wait for reply
    await db.set_user_state(user_id, State.HOOK)
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

    # Restore conversation stage from DB if the session is fresh (e.g. after bot restart)
    if "conversation_stage" not in context.user_data:
        context.user_data["conversation_stage"] = user.get("conversation_stage", "hook")

    # ── Intent classification ─────────────────────────────────────────────────
    last_message = context.user_data.get("last_message")
    intent = detect_intent(text, last_message)
    context.user_data["last_message"] = text

    # ── Meetup redirect — intercept before all state routing ─────────────────
    if intent == "meetup":
        # Tease intercept: "can i see you" and similar visual requests hit meetup intent
        # but should fire the image tease when gate conditions are met.
        if not context.user_data.get("image_tease_sent", False):
            _mt_stage      = context.user_data.get("conversation_stage", user.get("conversation_stage", "hook"))
            _mt_turns      = user.get("turn_count", 0)
            _mt_eng        = user.get("engagement_score", 0)
            _mt_intent_lvl = _classify_intent_level(text, "meetup", False)
            _mt_consec     = context.user_data.get("consecutive_engaged", 0)
            if _should_drop_image_tease(
                text=text,
                turn_count=_mt_turns,
                engagement=_mt_eng,
                intent="neutral",       # meetup is not rejection — don't block on it
                intent_level=_mt_intent_lvl,
                stage=_mt_stage,
                already_sent=False,
                consecutive_engaged=_mt_consec,
            ):
                context.user_data["image_tease_sent"] = True
                logger.info("image_tease: firing (meetup intercept) stage=%s turn=%d engagement=%d", _mt_stage, _mt_turns, _mt_eng)
                await _drop_image_tease(update, context, chat_id)
                return

        history = context.user_data.get("history", [])
        reply = await chat_reply(text, context={"stage": "meetup"}, history=history)
        _track_response(context.user_data, "redirect", reply)
        _push_history(context.user_data, text, reply)
        await _type_and_send(context.bot, chat_id, reply)
        return

    # ── Repeat test — call out the loop ──────────────────────────────────────
    if intent == "repeat_test":
        _rp_recent = context.user_data.get("recent_lines", [])
        reply = pick_line("repeat", _rp_recent)
        for _ in range(2):
            if is_natural_message(reply):
                break
            reply = pick_line("repeat", _rp_recent)
        _track_response(context.user_data, "repeat", reply)
        await _type_and_send(context.bot, chat_id, reply)
        return

    # ── Exit interception: one re-engagement attempt before allowing exit ─────
    if intent == "exit" and state not in (State.EXIT, State.PAYMENT_PENDING):
        exit_count = context.user_data.get("exit_attempts", 0)
        if exit_count == 0:
            context.user_data["exit_attempts"] = 1
            history = context.user_data.get("history", [])
            # LLM exit line so it references the specific moment, not a generic library pick
            reply = await chat_reply(text, context={"stage": "reengagement"}, history=history)
            _track_response(context.user_data, "retention", reply)
            _push_history(context.user_data, text, reply)
            await _type_and_send(context.bot, chat_id, reply)
            return
        # Second exit attempt — let them go
        context.user_data.pop("exit_attempts", None)
        await db.set_user_state(user_id, State.EXIT)
        exit_msg = await persona_message("exit")
        await _type_and_send(context.bot, chat_id, exit_msg)
        return

    # Any non-exit message resets the exit attempt counter
    context.user_data.pop("exit_attempts", None)

    # ── STATE 1: HOOK — strict lock, no tease, no vault, no selling ─────────
    if state in (State.HOOK, State.GREETING):
        history = context.user_data.get("history", [])
        turn_count = await db.increment_turn_count(user_id)
        context.user_data["current_turn"] = turn_count
        score_delta = _score_message(text)
        await db.update_engagement_score(user_id, score_delta)

        signal = has_buying_signal(text)
        intent_level = _classify_intent_level(text, intent, signal)
        stage = _maybe_advance_stage(context.user_data, intent, signal, intent_level)

        # Non-linear HOOK→BUILD: advance early on genuine engagement, hard cap at _HOOK_TURNS
        _hook_advance = (
            turn_count >= _HOOK_TURNS
            or (turn_count >= 2 and intent_level in ("mid", "high"))
        )
        if _hook_advance:
            await db.set_user_state(user_id, State.BUILD)
            logger.info("state: HOOK → BUILD at turn=%d intent_level=%s", turn_count, intent_level)

        if intent == "dry" and "?" not in text:
            reply = await chat_reply(text, context={"stage": "dry"}, history=history)
        else:
            reply = await chat_reply(text, context={"stage": stage}, history=history)
        _track_response(context.user_data, stage, reply)
        _push_history(context.user_data, text, reply)
        await _type_and_send(context.bot, chat_id, reply)
        return

    # ── STATE 2: BUILD — tease trigger live, vault locked ───────────────────
    # WARMUP is the legacy name — migrated to BUILD on startup, handled here as fallback.
    if state in (State.BUILD, State.WARMUP):
        history = context.user_data.get("history", [])
        turn_count = await db.increment_turn_count(user_id)
        context.user_data["current_turn"] = turn_count
        score_delta = _score_message(text)
        engagement = await db.update_engagement_score(user_id, score_delta)

        signal = has_buying_signal(text)
        strong = _is_strong_buy_signal(text)
        intent_level = _classify_intent_level(text, intent, signal)
        stage = _maybe_advance_stage(context.user_data, intent, signal, intent_level)

        # Track consecutive positively-scored turns (used by SOFT tease path).
        # Uses score_delta > 0 rather than intent != "dry" so short playful messages
        # like "lol", "nice", "haha" (score=+1 but classified as dry) build momentum.
        # Only intent=exit or a negative score resets the counter.
        if intent != "exit" and score_delta > 0:
            context.user_data["consecutive_engaged"] = context.user_data.get("consecutive_engaged", 0) + 1
        elif intent == "exit" or score_delta < 0:
            context.user_data["consecutive_engaged"] = 0
        # score_delta == 0 ("k", "ok") → counter neither increments nor resets
        consecutive_engaged = context.user_data.get("consecutive_engaged", 0)

        # ── Image-tease trigger — the ONLY path to POST_TEASE from BUILD ─────
        # STATE LOCK: no vault shortcut here. Vault is only reachable via POST_TEASE.
        if _should_drop_image_tease(
            text=text,
            turn_count=turn_count,
            engagement=engagement,
            intent=intent,
            intent_level=intent_level,
            stage=stage,
            already_sent=context.user_data.get("image_tease_sent", False),
            consecutive_engaged=consecutive_engaged,
        ):
            context.user_data["image_tease_sent"] = True
            await _drop_image_tease(update, context, chat_id)
            return

        # ── Normal response ───────────────────────────────────────────────────

        # Stall override — two consecutive low-energy replies → advance stage and force LLM
        if _is_stalling(context.user_data) and intent != "exit":
            if stage in _STAGE_ORDER:
                idx = _STAGE_ORDER.index(stage)
                next_stage = _STAGE_ORDER[min(idx + 1, len(_STAGE_ORDER) - 1)]
            else:
                next_stage = "intrigue"
            context.user_data["conversation_stage"] = next_stage
            context.user_data["stage_turn_count"] = 0
            reply = await chat_reply(text, context={"stage": next_stage}, history=history)
            _track_response(context.user_data, next_stage, reply)
            _push_history(context.user_data, text, reply)
            await _type_and_send(context.bot, chat_id, reply)
            return

        # Compliment — treat as momentum, reward then hold back slightly
        if _is_compliment(text) and intent not in ("exit",):
            reply = await chat_reply(text, context={"stage": "micro_reward"}, history=history)
            _track_response(context.user_data, "pull", reply)
            _push_history(context.user_data, text, reply)
            await _type_and_send(context.bot, chat_id, reply)
            return

        # Grounding rhythm — every 4–6 normal exchanges, shift from tease to a real moment
        _ground_turns = context.user_data.get("turns_since_grounding", 0) + 1
        _ground_threshold = context.user_data.get("grounding_threshold", random.randint(4, 6))
        _grounding_due = _ground_turns >= _ground_threshold
        if _grounding_due:
            context.user_data["turns_since_grounding"] = 0
            context.user_data["grounding_threshold"] = random.randint(4, 6)
        else:
            context.user_data["turns_since_grounding"] = _ground_turns

        if intent == "dry" and "?" not in text:
            # Dry: keep flat — grounding doesn't apply to low-energy exchanges
            reply = await chat_reply(text, context={"stage": "dry"}, history=history)
            _track_response(context.user_data, "dry", reply)
            _push_history(context.user_data, text, reply)
            await _type_and_send(context.bot, chat_id, reply)
        elif (
            intent == "objection"
            or intent_level in ("mid", "high")
            or "?" in text
        ):
            reply = await chat_reply(
                text,
                context={"stage": stage, "grounding_due": _grounding_due},
                history=history,
            )
            _track_response(context.user_data, stage, reply)
            _push_history(context.user_data, text, reply)
            await _type_and_send(context.bot, chat_id, reply)
        else:
            reply = await chat_reply(
                text,
                context={"stage": stage, "grounding_due": _grounding_due},
                history=history,
            )
            _track_response(context.user_data, stage, reply)
            _push_history(context.user_data, text, reply)
            await _type_and_send(context.bot, chat_id, reply)
        return

    # ── STATE 4: POST_TEASE — emotional pull, vault locked until min turns ───
    if state == State.POST_TEASE:
        history = context.user_data.get("history", [])
        post_tease_turns = context.user_data.get("post_tease_turns", 0) + 1
        context.user_data["post_tease_turns"] = post_tease_turns
        logger.info("state: POST_TEASE turn=%d", post_tease_turns)

        # Priority gate: block vault if user is in wrong state
        # Blocked: active question, objection/resistance, exit, or sexual escalation
        # Exception: buying signal overrides all blocks
        _priority_block = (
            (
                "?" in text
                or intent in ("exit", "objection")
                or _is_sexual_escalation(text)
                or _is_strong_resistance(text)
            )
            and not _is_buying_signal(text)
        )

        if not _priority_block and _post_tease_ready(text, intent, post_tease_turns):
            # Minimum turns met, engagement signal present, correct state — transition to vault
            context.user_data.pop("post_tease_turns", None)
            vault_line = pick_image_vault_transition()
            await _type_and_send(context.bot, chat_id, vault_line, delay=random.uniform(1.5, 2.2))
            await asyncio.sleep(random.uniform(0.5, 0.9))
            await _show_packs(update, context)
            return

        # Still building — LLM reacts directly to what they said, no vault hints
        reply = await chat_reply(text, context={"stage": "post_image_reaction"}, history=history)
        _push_history(context.user_data, text, reply)
        await _type_and_send(context.bot, chat_id, reply, delay=random.uniform(1.0, 1.6))
        return

    # ── SOFT_INVITE: show packs only on clear signal, never by default ───────
    if state == State.SOFT_INVITE:
        history = context.user_data.get("history", [])
        invite_attempts = context.user_data.get("soft_invite_attempts", 0)

        if _is_affirmative(text) or _is_buying_signal(text):
            # Clear yes — show packs
            context.user_data.pop("soft_invite_attempts", None)
            await _show_packs(update, context)

        elif _is_negative(text):
            # No means no — don't chase, drop back to warmup
            await db.set_rejection_flag(user_id, 1)
            await db.set_user_state(user_id, State.BUILD)
            context.user_data.pop("soft_invite_attempts", None)
            reply = await chat_reply(text, context={"stage": "rejected"}, history=history)
            _push_history(context.user_data, text, reply)
            await _type_and_send(context.bot, chat_id, reply)

        elif invite_attempts >= 2:
            # She's not chasing. Drop back to warmup naturally — door stays open.
            context.user_data.pop("soft_invite_attempts", None)
            await db.set_user_state(user_id, State.BUILD)
            reply = await chat_reply(text, context={"stage": "rejected"}, history=history)
            _push_history(context.user_data, text, reply)
            await _type_and_send(context.bot, chat_id, reply)

        else:
            # Hesitant, chatting, or ambiguous — respond in character via LLM
            context.user_data["soft_invite_attempts"] = invite_attempts + 1
            signal = has_buying_signal(text)
            intent_level = _classify_intent_level(text, intent, signal)
            _maybe_advance_stage(context.user_data, intent, signal, intent_level)
            llm_stage = stage
            reply = await chat_reply(text, context={"stage": llm_stage}, history=history)
            _track_response(context.user_data, llm_stage, reply)
            _push_history(context.user_data, text, reply)
            await _type_and_send(context.bot, chat_id, reply)

        return

    # ── CURIOSITY: treat like WARMUP with intent awareness ───────────────────
    if state == State.CURIOSITY:
        history = context.user_data.get("history", [])
        signal = has_buying_signal(text)
        intent_level = _classify_intent_level(text, intent, signal)
        stage = _maybe_advance_stage(context.user_data, intent, signal, intent_level)
        if intent == "dry" and "?" not in text:
            reply = await chat_reply(text, context={"stage": "dry"}, history=history)
            _track_response(context.user_data, "dry", reply)
            _push_history(context.user_data, text, reply)
        elif intent == "objection" or "?" in text:
            reply = await chat_reply(text, context={"stage": stage}, history=history)
            _track_response(context.user_data, stage, reply)
            _push_history(context.user_data, text, reply)
        else:
            reply = await chat_reply(text, context={"stage": stage}, history=history)
            _track_response(context.user_data, stage, reply)
            _push_history(context.user_data, text, reply)
        await _type_and_send(context.bot, chat_id, reply)
        return

    # ── OFFER: user chatting after seeing packs — never auto-repeat buttons ───
    if state == State.OFFER:
        history = context.user_data.get("history", [])
        offer_turns = context.user_data.get("offer_turn_count", 0)

        if _is_buying_signal(text):
            # Explicit purchase intent — re-show packs immediately, clear any resistance flag
            context.user_data["offer_turn_count"] = 0
            context.user_data.pop("strong_resistance", None)
            await _show_packs(update, context)
            return

        offer_turns += 1
        context.user_data["offer_turn_count"] = offer_turns

        if offer_turns >= _OFFER_MAX_TURNS:
            # Timed out — drop back to warmup without pressure
            context.user_data["offer_turn_count"] = 0
            await db.set_user_state(user_id, State.BUILD)
            reply = await chat_reply(text, context={"stage": "post_offer_objection"}, history=history)
            _push_history(context.user_data, text, reply)
            await _type_and_send(context.bot, chat_id, reply)
            return

        if _is_strong_resistance(text):
            # PATH B — explicit rejection: acknowledge once, no chase, no re-offer
            context.user_data["offer_turn_count"] = 0
            context.user_data["strong_resistance"] = True
            await db.set_user_state(user_id, State.BUILD)
            reply = await chat_reply(text, context={"stage": "clean_exit"}, history=history)
            _push_history(context.user_data, text, reply)
            await _type_and_send(context.bot, chat_id, reply)
            return

        if _is_negative(text):
            # PATH A — light rejection: warm acknowledgment, stay in conversation
            context.user_data["offer_turn_count"] = 0
            await db.set_user_state(user_id, State.BUILD)
            reply = await chat_reply(text, context={"stage": "soft_retain"}, history=history)
            _push_history(context.user_data, text, reply)
            await _type_and_send(context.bot, chat_id, reply)
            return

        if offer_turns >= _OFFER_COOLDOWN_TURNS and _is_asking_about_content(text) and not context.user_data.get("strong_resistance"):
            # User is asking directly about the content after a gap — natural re-offer moment
            context.user_data["offer_turn_count"] = 0
            await _show_packs(update, context)
            return

        # Default: respond conversationally — no buttons, no re-offer push
        stage = context.user_data.get("conversation_stage", "warmup")
        if intent == "objection":
            # Hesitant/uncertain after seeing packs — maintain intrigue, don't push or drop
            reply = await chat_reply(text, context={"stage": "post_offer_objection"}, history=history)
            _track_response(context.user_data, "post_offer_objection", reply)
            _push_history(context.user_data, text, reply)
        elif _is_asking_about_content(text) or "?" in text:
            # Direct question — answer it, do not tease or redirect to vault
            reply = await chat_reply(text, context={"stage": "answer_intent"}, history=history)
            _track_response(context.user_data, "answer_intent", reply)
            _push_history(context.user_data, text, reply)
        elif intent == "dry" and "?" not in text:
            reply = await chat_reply(text, context={"stage": "dry"}, history=history)
            _track_response(context.user_data, "dry", reply)
            _push_history(context.user_data, text, reply)
        else:
            reply = await chat_reply(text, context={"stage": stage}, history=history)
            _track_response(context.user_data, stage, reply)
            _push_history(context.user_data, text, reply)
        await _type_and_send(context.bot, chat_id, reply)
        return

    # ── PAYMENT_PENDING: reassure, don't spam ─────────────────────────────────
    if state == State.PAYMENT_PENDING:
        await _type_and_send(
            context.bot, chat_id,
            "just pay through the link above — i'll send everything over right away",
            delay=1.0,
        )
        return

    # ── UPSELL: light touch — no repeated keyboard ────────────────────────────
    if state == State.UPSELL:
        history = context.user_data.get("history", [])
        if _is_affirmative(text) or _is_buying_signal(text):
            await _show_packs(update, context)
        elif _is_negative(text):
            await db.set_user_state(user_id, State.EXIT)
            exit_msg = await persona_message("exit")
            await _type_and_send(context.bot, chat_id, exit_msg)
        else:
            # Conversational reply only — keyboard was already shown at delivery
            reply = await chat_reply(text, context={"stage": "upsell"}, history=history)
            _push_history(context.user_data, text, reply)
            await _type_and_send(context.bot, chat_id, reply)
        return

    # ── EXIT / fallback: never go silent ─────────────────────────────────────
    history = context.user_data.get("history", [])
    reply = await chat_reply(text, context={"stage": "warmup"}, history=history)
    _push_history(context.user_data, text, reply)
    await _type_and_send(context.bot, chat_id, reply)
