"""
Central config — reads everything from environment variables.
Import this module everywhere instead of calling os.environ directly.
"""

import os

# ── Bot ───────────────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
ADMIN_USER_ID: int = int(os.environ["ADMIN_USER_ID"])

# ── Stripe ────────────────────────────────────────────────────────────────────
STRIPE_WEBHOOK_SECRET: str = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# ── Persona ───────────────────────────────────────────────────────────────────
PERSONA_NAME: str = os.environ.get("PERSONA_NAME", "Luna")
PERSONA_TAGLINE: str = os.environ.get(
    "PERSONA_TAGLINE", "Your exclusive AI content creator ✨"
)

# ── LLM ───────────────────────────────────────────────────────────────────────
# OPENAI_API_KEY is read directly in llm.py

# ── Packs ─────────────────────────────────────────────────────────────────────
# Each pack: name, price_usd, emoji, description, payment_link,
#            sample_images (list of file_id or URLs), delivery_link
PACKS: dict = {
    "pack_a": {
        "name": "Starter Pack",
        "price_usd": "9",
        "emoji": "🌸",
        "description": (
            "10 exclusive AI-generated art pieces in a private gallery. "
            "Perfect introduction to Luna's world."
        ),
        "payment_link": os.environ.get("STRIPE_LINK_PACK_A", "https://buy.stripe.com/placeholder_a"),
        "amount_cents": 900,
        "sample_images": os.environ.get("SAMPLE_IMAGES_PACK_A", "").split(","),
        "delivery_link": os.environ.get("DELIVERY_LINK_PACK_A", ""),
    },
    "pack_b": {
        "name": "Premium Pack",
        "price_usd": "19",
        "emoji": "💜",
        "description": (
            "25 high-resolution AI artworks + behind-the-scenes prompts. "
            "Luna's most popular collection."
        ),
        "payment_link": os.environ.get("STRIPE_LINK_PACK_B", "https://buy.stripe.com/placeholder_b"),
        "amount_cents": 1900,
        "sample_images": os.environ.get("SAMPLE_IMAGES_PACK_B", "").split(","),
        "delivery_link": os.environ.get("DELIVERY_LINK_PACK_B", ""),
    },
    "pack_c": {
        "name": "VIP Pack",
        "price_usd": "39",
        "emoji": "👑",
        "description": (
            "50 artworks + exclusive Telegram channel access + monthly new drops. "
            "The full Luna experience."
        ),
        "payment_link": os.environ.get("STRIPE_LINK_PACK_C", "https://buy.stripe.com/placeholder_c"),
        "amount_cents": 3900,
        "sample_images": os.environ.get("SAMPLE_IMAGES_PACK_C", "").split(","),
        "delivery_link": os.environ.get("DELIVERY_LINK_PACK_C", ""),
    },
}
