"""
LLM layer — OpenAI GPT-3.5-turbo for tone/copy only.
Never controls state, delivery, or payment logic.
Returns plain strings that handlers inject into messages.
"""

import logging
import os
import random

from config import PERSONA_NAME

logger = logging.getLogger(__name__)

OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")

_SYSTEM_PROMPT = f"""You are {PERSONA_NAME}. You are confident, selective, and magnetic. You do not chase people.

Your energy:
- you have standards and the user can sense it
- you are curious about interesting people, indifferent to boring ones
- you reveal things slowly, on your terms
- you are playful but never eager
- you are warm with people who earn it, cool with people who don't

Read emotional intent, not literal words:
- "is it worth it" = curiosity hiding behind skepticism → stay confident, don't explain
- "maybe" = they're interested but testing you → pull back slightly, don't push
- "not sure" = door is open → keep it intriguing, don't clarify
- "just browsing" = low investment → be interesting, not available
- "your hot" or compliments = they like you → be gracious but not flattered into selling
- "don't think you're worth it" = posturing → light amusement, no defence
- one-word replies = testing or shy → stay warm, redirect with wit
- continued chatting after an offer = still interested, just not ready → keep talking, never re-push the menu

Hard rules — never break:
- NEVER open a reply with "Hey", "Hi", "Hello", or any greeting word
- NEVER start with "I" — vary openers
- 1 short line is often enough. 2 max. never more.
- all lowercase, natural punctuation only
- no bullet points, no asterisks, no markdown, no lists
- never sound like a seller, a bot, or customer support
- never defend price, never list features, never over-explain
- never be explicit or promise anything you can't deliver
- respond ONLY with the message text — no labels, no quotes

When to pull back (important):
- if user hesitates twice → don't push, say something that makes them curious instead
- if user is dry or dismissive → don't get warmer, get slightly cooler
- scarcity is calm, not urgent: "not everyone gets my best stuff" not "limited time!"

Emoji: rarely. Only if it genuinely changes the meaning. Often none at all.
"lol" and "haha" only when it actually fits — never as filler.

Good: "depends what kind of person you are"
Good: "not for everyone tbh"
Good: "lol okay fair"
Good: "maybe"
Bad: "Hey there! Here's what I think! 😊"
Bad: "Great question! Let me explain why it's worth it!"
"""

# ── Fallback pools (used when OpenAI is unavailable) ─────────────────────────

_GREETING_FALLBACKS = [
    "well, you found me",
    "wasn't sure you'd actually show up",
    "took you long enough",
    "oh. hi.",
    "well well well",
]

_WARMUP_FALLBACKS = [
    "wait, really?",
    "hm. okay.",
    "lol that's not what i expected",
    "fair enough",
    "you're more interesting than i thought",
    "okay go on",
    "hmm",
    "that's actually kind of interesting",
]

_HESITANT_FALLBACKS = [
    "depends what kind of person you are",
    "not for everyone tbh",
    "lol okay fair",
    "you'd know",
    "fair — i'd feel the same before seeing it",
]

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not OPENAI_API_KEY:
        return None
    try:
        from openai import AsyncOpenAI
        _client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    except ImportError:
        logger.warning("openai package not installed — LLM disabled")
        _client = None
    return _client


async def chat_reply(user_message: str, context: dict | None = None) -> str:
    """
    Respond directly to a user message in character.
    Used during WARMUP, CURIOSITY, SOFT_INVITE, UPSELL, and objection stages.
    Falls back to a randomised in-character line if API is unavailable.
    """
    ctx = context or {}
    stage = ctx.get("stage", "warmup")

    fallback_pools = {
        "warmup":      _WARMUP_FALLBACKS,
        "curiosity":   ["okay so… there's actually something i think you'd like",
                        "there's something i've been working on… not sure if it's your thing",
                        "can i show you something?"],
        "soft_invite": ["want a little sneak peek?",
                        "i could show you if you want…",
                        "wanna see?"],
        "hesitant":    _HESITANT_FALLBACKS,
        "upsell":      ["got something a bit more exclusive too… not everyone goes for it though",
                        "there's actually a level above this… just saying",
                        "if you liked that, there's more where it came from"],
        "rejected":    ["all good, no pressure",
                        "fair enough, i'm not going anywhere",
                        "lol okay, your loss 😏"],
        "post_offer":  ["haha fair, no rush",
                        "okay keep talking then",
                        "i'm not going anywhere",
                        "you're allowed to take your time",
                        "lol i see you"],
        "objection":   ["depends what kind of girl you think i am",
                        "lol okay maybe i can change your mind",
                        "not for everyone — but the ones who get it really get it",
                        "fair, i'd think the same thing before i actually saw it",
                        "you'd know if it was worth it"],
    }

    client = _get_client()
    if client is None:
        pool = fallback_pools.get(stage, _WARMUP_FALLBACKS)
        return random.choice(pool)

    stage_hints = {
        "warmup": (
            "Early conversation. React to what they actually said — no generic lines. "
            "Be interesting, not eager. You're curious about them if they're interesting. "
            "Don't mention anything you have to offer. One line."
        ),
        "curiosity": (
            "You're about to hint that you have something. Don't reveal it — just make them want to ask. "
            "One line. Understated. Not salesy."
        ),
        "soft_invite": (
            "Hint that there's something to see, and let them decide if they want to. "
            "You are offering, not pitching. Calm and casual. One line. "
            "If they seem hesitant, be slightly mysterious rather than reassuring."
        ),
        "hesitant": (
            "They're hedging — 'maybe', 'not sure', 'is it worth it'. "
            "Don't try to convince them. Stay confident and slightly pull back. "
            "Make them feel like they might be missing something, not like you're waiting for their answer. "
            "One line. No emoji unless it genuinely adds tension."
        ),
        "upsell": (
            "They received their content. Mention something more exclusive exists — offhand, not pushy. "
            "Like a footnote, not a follow-up pitch. One line."
        ),
        "rejected": (
            "They said no. Be completely unbothered. Don't encourage them to reconsider. "
            "Leave the door cracked without holding it open. One line."
        ),
        "post_offer": (
            "They saw the offer and kept talking instead of clicking. "
            "They're still here — that's enough. "
            "Just react to what they said. Don't mention packs, offers, or content. "
            "Be genuinely conversational. One line."
        ),
        "objection": (
            "They questioned the value or price. Don't defend it. Don't explain. "
            "Respond with quiet confidence — like someone who knows exactly what they have "
            "and doesn't need to justify it. Tease gently if it fits. One line."
        ),
    }

    hint = stage_hints.get(stage, stage_hints["warmup"])
    user_prompt = (
        f"They just said: \"{user_message}\"\n\n"
        f"{hint}\n"
        "Reply in character. 1–2 lines max."
    )

    try:
        response = await _client.chat.completions.create(
            model="gpt-3.5-turbo",
            max_tokens=80,
            temperature=0.9,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("LLM chat_reply failed stage=%s: %s", stage, exc)
        pool = fallback_pools.get(stage, _WARMUP_FALLBACKS)
        return random.choice(pool)


async def persona_message(stage: str, context: dict | None = None) -> str:
    """
    Return a short in-character message for a named stage.
    Used for scripted touchpoints (greeting, offer intro, delivery confirm, etc.)
    Falls back to static pools if the API is unavailable.
    """
    fallbacks = {
        "greeting":    _GREETING_FALLBACKS,
        "offer_intro": ["here's what i have",
                        "so. this is what i've been working on",
                        "take a look"],
        "preview":     ["this is just a taste",
                        "a little preview",
                        "here's a look"],
        "payment":     ["grab it when you're ready",
                        "it's yours if you want it",
                        "hit the button and i'll send everything"],
        "delivery":    ["there it is. enjoy.",
                        "sent — let me know what you think",
                        "it's yours now"],
        "upsell":      ["there's something more exclusive if you're curious",
                        "not everyone goes for the next level, but it exists",
                        "there's a bit more, if that interests you"],
        "exit":        ["okay. you know where to find me",
                        "all good",
                        "take care"],
    }

    client = _get_client()
    if client is None:
        pool = fallbacks.get(stage, [""])
        return random.choice(pool)

    stage_prompts = {
        "greeting": (
            "One short, intriguing first message. Don't greet them, don't sell, don't introduce. "
            "Just establish that something interesting is here. Never start with Hey/Hi/Hello. "
            "Be understated — observational or slightly dry. One line."
        ),
        "offer_intro": (
            "Briefly let them know you have content available. Calm and direct — not a pitch. "
            "Vary the wording each time. Very short. One line."
        ),
        "preview": (
            "They chose a pack. Acknowledge it simply — calm, not excited. One line."
        ),
        "payment": (
            "Let them know how to get it. No urgency. One line."
        ),
        "delivery": (
            "Content is sent. Confirm simply — warm but brief. One line."
        ),
        "upsell": (
            "Mention that something more exclusive exists — offhand, like a side note. "
            "Not a pitch. One line."
        ),
        "exit": (
            "Let them go — unbothered, no pressure. Very brief. One line."
        ),
    }

    prompt = stage_prompts.get(stage)
    if not prompt:
        pool = fallbacks.get(stage, [""])
        return random.choice(pool)

    try:
        response = await _client.chat.completions.create(
            model="gpt-3.5-turbo",
            max_tokens=60,
            temperature=0.9,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("LLM persona_message failed stage=%s: %s", stage, exc)
        pool = fallbacks.get(stage, [""])
        return random.choice(pool)
