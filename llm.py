"""
LLM layer — Claude API for tone/copy only.
Never controls state, delivery, or payment logic.
Returns plain strings that handlers inject into messages.
"""

import logging
from config import ANTHROPIC_API_KEY, LLM_MODEL, PERSONA_NAME

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic
        _client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    except ImportError:
        logger.warning("anthropic package not installed — LLM disabled")
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
        import anthropic
        response = await client.messages.create(
            model=LLM_MODEL,
            max_tokens=120,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text.strip()
    except Exception as exc:
        logger.error("LLM call failed for stage=%s: %s", stage, exc)
        return fallbacks.get(stage, "")
