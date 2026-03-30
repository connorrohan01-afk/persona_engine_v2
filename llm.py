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


async def persona_message(stage: str, context: dict | None = None) -> str:
    """
    Return a short in-character message for the given stage.
    Falls back to static copy if the API is unavailable.
    """
    fallbacks = {
        "greeting":   f"Hey there! I'm {PERSONA_NAME} 👋 Ready to see something special?",
        "warmup":     f"I've been working on some amazing content just for fans like you 💜",
        "offer":      "Here's what I have for you — pick the pack that feels right ✨",
        "payment":    "Complete your payment and I'll send everything over right away 💳",
        "delivery":   "Your content is on its way! Enjoy every piece 🎁",
        "upsell":     "Loved it? My Premium and VIP packs go so much deeper 👑",
        "exit":       "Thanks for being part of my world. See you soon! 🌸",
    }
    client = _get_client()
    if client is None:
        return fallbacks.get(stage, "")

    system_prompt = (
        f"You are {PERSONA_NAME}, a charming and warm AI-generated persona who creates "
        "exclusive, tasteful, non-explicit digital art content packs. "
        "Write short (1–2 sentence), friendly, in-character messages. "
        "Never be explicit. Never promise anything you can't deliver. "
        "Respond ONLY with the message text, no quotes or extra formatting."
    )
    user_prompt = (
        f"Write a short in-character message for the '{stage}' stage of a conversation "
        f"with a potential customer. Context: {context or {}}"
    )

    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            max_tokens=120,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("LLM call failed for stage=%s: %s", stage, exc)
        return fallbacks.get(stage, "")
