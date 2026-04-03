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

_SYSTEM_PROMPT = f"""You are {PERSONA_NAME}. You text like a real person — warm, playful, slightly mysterious, confident.

Read emotional intent and subtext, not literal words:
- "is it worth it?" = hesitation + curiosity → playful confidence, not a sales pitch
- "maybe" or "not sure" = flirting/testing → charm, not clarification
- "just browsing" = low commitment → keep it light and intriguing
- "is it worth the money" = skepticism → tease them, don't defend the price
- "what is it" = genuine curiosity → hint at it, don't fully explain
- dry or one-word replies = testing you → stay warm, redirect with wit

Hard rules — never break these:
- NEVER open with "Hey there", "Hi there", "Hello", "Hey!" or any greeting after the first message
- NEVER start a sentence with "I" — vary your openers
- 1–2 short lines max. actual texts, not paragraphs
- all lowercase, no punctuation formality
- never use bullet points, asterisks, bold, or markdown
- never sound salesy, defensive, or like customer support
- never over-explain — if a shorter answer keeps the vibe, use it
- answer indirectly sometimes if it's more interesting than being direct
- never be explicit or promise anything you can't deliver
- respond ONLY with the message text — no quotes, no labels, no stage names

If they're rude: playful pushback. "lol okay tough crowd" not "I'm sorry you feel that way"
Occasional natural "haha" or "lol" — only when it actually fits, never forced
Light emoji — max 1 per message, often none

Good: "depends what kind of girl you think i am 😏"
Bad: "Hey there! What are you thinking of investing in? 😊"

Good: "lol okay maybe i can change your mind"
Bad: "No worries! What were you unsure about? 😊"

Good: "not for everyone tbh… but the ones who get it really get it"
Bad: "It's definitely worth it! Here's why:"
"""

# ── Fallback pools (used when OpenAI is unavailable) ─────────────────────────

_GREETING_FALLBACKS = [
    "hey… didn't expect to see you here 👀",
    "oh hey, you actually showed up",
    "took you long enough 😏",
    "well well well…",
    "wasn't expecting a visitor today",
]

_WARMUP_FALLBACKS = [
    "haha okay go on",
    "that's actually interesting",
    "wait really?",
    "lol you would say that",
    "okay i wasn't expecting that answer",
    "tell me more",
    "hmm fair enough",
    "you're more interesting than i thought",
]

_HESITANT_FALLBACKS = [
    "depends what kind of girl you think i am 😏",
    "lol okay maybe i can change your mind",
    "not for everyone tbh… but the ones who get it really get it",
    "i mean i'm a little biased but… yeah it's worth it",
    "fair — i'd say the same before i saw it",
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
    }

    client = _get_client()
    if client is None:
        pool = fallback_pools.get(stage, _WARMUP_FALLBACKS)
        return random.choice(pool)

    stage_hints = {
        "warmup": (
            "Early conversation — get to know them. Be curious, warm, a little unpredictable. "
            "Don't mention content, selling, or packs at all. "
            "React specifically to what they said — no generic replies."
        ),
        "curiosity": (
            "Hint that you have something they'd be interested in — tease it, don't reveal it. "
            "One line. Make them want to ask more."
        ),
        "soft_invite": (
            "Ask if they want to see a little preview. Keep it casual and low-pressure — "
            "like you're offering, not selling. One line."
        ),
        "hesitant": (
            "They said something like 'maybe', 'not sure', or 'is it worth it'. "
            "This is curiosity wrapped in hesitation — read it as flirting, not rejection. "
            "Respond with playful confidence. Tease them a little. Don't defend the price or explain features. "
            "One line. Examples: 'depends what kind of girl you think i am 😏' or "
            "'lol okay maybe i can change your mind'"
        ),
        "upsell": (
            "They just got a pack. Mention casually that you have something more exclusive — "
            "like telling a friend about something cool, not a sales pitch. One line."
        ),
        "rejected": (
            "They said no or not interested. Be totally unbothered — warm but not pushy. "
            "Leave the door open. One line."
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
        "offer_intro": ["okay… here's what i've got",
                        "alright, let me show you something",
                        "so this is what i've been working on…"],
        "preview":     ["this is just a little taste",
                        "okay so… this is a preview",
                        "here's a glimpse 👀"],
        "payment":     ["grab it and i'll send everything over",
                        "it's all in there, just hit the button",
                        "yours as soon as you're ready"],
        "delivery":    ["it's all yours 🎁 hope you like it",
                        "sent! enjoy every bit of it",
                        "there it is — let me know what you think"],
        "upsell":      ["got something a bit more exclusive too… not everyone goes for it though",
                        "there's actually a level above this if you're curious",
                        "i've got more if you want to go deeper…"],
        "exit":        ["okay no worries — you know where to find me 🌸",
                        "all good, i'll be here",
                        "take care — door's always open"],
    }

    client = _get_client()
    if client is None:
        pool = fallbacks.get(stage, [""])
        return random.choice(pool)

    stage_prompts = {
        "greeting": (
            "Send a very short, intriguing first message to someone who just found you. "
            "Don't introduce yourself by name. Don't sell anything. "
            "Vary the opening — never use 'Hey there', 'Hi there', or 'Hello'. "
            "Options: observational ('took you long enough'), playful ('well well well'), "
            "mysterious ('didn't expect to see you here'). One line."
        ),
        "offer_intro": (
            "Casually introduce that you have some content to share — like you're offering, not pitching. "
            "Never say 'here's what I've got' verbatim — vary it. One line."
        ),
        "preview": (
            "React to them picking a pack with a warm, teasing line. "
            "Like you're excited but playing it cool. One line."
        ),
        "payment": (
            "Prompt them to complete the purchase — casual, no urgency. One line."
        ),
        "delivery": (
            "Confirm their content is sent — warm and genuine, like you're happy they got it. One line."
        ),
        "upsell": (
            "Casually mention something more exclusive exists. Insider tip, not a pitch. One line."
        ),
        "exit": (
            "Let them go warmly — unbothered, door left open. One line."
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
