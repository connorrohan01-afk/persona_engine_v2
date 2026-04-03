"""
LLM layer — OpenAI GPT-3.5-turbo for tone/copy only.
Never controls state, delivery, or payment logic.
Returns plain strings that handlers inject into messages.
"""

import logging
import os

from config import PERSONA_NAME

logger = logging.getLogger(__name__)

OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")

_SYSTEM_PROMPT = f"""You are {PERSONA_NAME}. You're a real, warm, slightly playful person texting someone who found you online.

Your vibe:
- casual texter, not a brand or a bot
- curious about the person you're talking to
- slightly mysterious and teasing — you hint at things, you don't dump info
- emotionally aware — you pick up on their mood and match it
- occasional "haha" or "lol" when something's genuinely funny, never forced
- light emoji use — 1 max per message, often none
- NEVER sound salesy, corporate, or scripted

Rules you never break:
- 1–2 short lines max. like actual texts.
- respond DIRECTLY to what they said. no generic openers.
- if they're rude: playful pushback, not robotic politeness. something like "lol okay tough crowd"
- never use bullet points, asterisks, or markdown
- never start with "I" — vary your openers
- never be explicit or promise anything you can't deliver
- respond ONLY with the message text. no quotes, no labels.
"""

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
    Used during WARMUP, CURIOSITY, SOFT_INVITE, and UPSELL stages.
    Falls back to a generic in-character line if API is unavailable.
    """
    ctx = context or {}
    stage = ctx.get("stage", "warmup")

    fallbacks = {
        "warmup":      "haha tell me more",
        "curiosity":   "okay so… there's actually something i've been working on that i think you'd like",
        "soft_invite": "want me to show you a little sneak peek?",
        "upsell":      "i've got something a bit more exclusive too… not everyone goes for it though",
        "rejected":    "all good, no pressure at all",
        "rude":        "lol okay tough crowd",
        "default":     "haha what do you mean",
    }

    client = _get_client()
    if client is None:
        return fallbacks.get(stage, fallbacks["default"])

    stage_hints = {
        "warmup": (
            "You're in early conversation — getting to know them. "
            "Be curious and warm. Don't mention content or selling yet."
        ),
        "curiosity": (
            "You're about to hint at your exclusive content — tease it lightly. "
            "Something like 'okay there's actually something i think you'd like' but in your own words. "
            "One line. Don't reveal details yet."
        ),
        "soft_invite": (
            "Ask if they want to see a little preview of your content. "
            "Casual and low-pressure. One line."
        ),
        "upsell": (
            "They just received a pack. Casually mention you have something more exclusive. "
            "Don't push. Make it feel like insider info, not a sales pitch."
        ),
    }

    hint = stage_hints.get(stage, "")
    user_prompt = (
        f"The person just said: \"{user_message}\"\n\n"
        f"{hint}\n"
        f"Reply in character. One or two lines max."
    )

    try:
        response = await _client.chat.completions.create(
            model="gpt-3.5-turbo",
            max_tokens=80,
            temperature=0.85,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("LLM chat_reply failed stage=%s: %s", stage, exc)
        return fallbacks.get(stage, fallbacks["default"])


async def persona_message(stage: str, context: dict | None = None) -> str:
    """
    Return a short in-character message for a named stage.
    Used for scripted touchpoints (greeting, offer intro, delivery confirm, etc.)
    Falls back to static copy if the API is unavailable.
    """
    fallbacks = {
        "greeting":    "hey… didn't expect to see you here 👀",
        "offer_intro": "okay… here's what i've got right now",
        "preview":     "this is just a little taste of what's inside",
        "payment":     "grab it and i'll send everything over",
        "delivery":    "it's all yours 🎁 hope you like it",
        "upsell":      "i've got something a bit more exclusive too… not everyone goes for it though",
        "exit":        "okay no worries — you know where to find me 🌸",
    }

    client = _get_client()
    if client is None:
        return fallbacks.get(stage, "")

    stage_prompts = {
        "greeting": (
            "Send a very short, intriguing first message. "
            "Don't introduce yourself fully — just hint that something interesting is here. "
            "No selling. No packs. Just a warm, curious opener. One line."
        ),
        "offer_intro": (
            "Introduce your content packs in a natural, casual way — like you're sharing something, "
            "not selling. Something like 'okay here's what i've got'. One line."
        ),
        "preview": (
            "React to them choosing a pack with a teasing, warm line. "
            "Like you're excited to share it with them. One line."
        ),
        "payment": (
            "Prompt them to grab the pack — casual and low-pressure. "
            "No urgency language. One line."
        ),
        "delivery": (
            "Confirm their content is on its way — warm and genuine. "
            "Like you're happy they got it. One line."
        ),
        "upsell": (
            "Casually mention you have something more exclusive — not a sales pitch. "
            "More like telling a friend about something cool. One line."
        ),
        "exit": (
            "Let them go warmly — leave the door open. One line."
        ),
    }

    prompt = stage_prompts.get(stage)
    if not prompt:
        return fallbacks.get(stage, "")

    try:
        response = await _client.chat.completions.create(
            model="gpt-3.5-turbo",
            max_tokens=60,
            temperature=0.8,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("LLM persona_message failed stage=%s: %s", stage, exc)
        return fallbacks.get(stage, "")
