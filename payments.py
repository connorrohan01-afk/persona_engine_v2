"""
Stripe webhook handler (FastAPI endpoint).
Uses pre-built Stripe Payment Links — no Checkout Session API needed.
The bot application instance is injected at startup via set_application().
"""

import hashlib
import hmac
import json
import logging

from fastapi import FastAPI, Request, Response

import db
from config import STRIPE_WEBHOOK_SECRET
from states import State

logger = logging.getLogger(__name__)

_app_ref = None  # telegram.ext.Application injected by main.py


def set_application(app):
    global _app_ref
    _app_ref = app


def make_fastapi_app() -> FastAPI:
    api = FastAPI()

    @api.post("/webhook")
    async def stripe_webhook(request: Request):
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature", "")

        if STRIPE_WEBHOOK_SECRET:
            if not _verify_stripe_signature(payload, sig_header, STRIPE_WEBHOOK_SECRET):
                logger.warning("Stripe webhook signature verification failed")
                return Response(content="Invalid signature", status_code=400)

        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            return Response(content="Bad JSON", status_code=400)

        event_type = event.get("type", "")
        logger.info("Stripe event received: %s", event_type)

        # checkout.session.completed fires for Payment Links
        if event_type == "checkout.session.completed":
            await _handle_checkout_completed(event["data"]["object"])
        # payment_intent.succeeded is an alternative signal
        elif event_type == "payment_intent.succeeded":
            await _handle_payment_intent_succeeded(event["data"]["object"])

        return Response(content="ok", status_code=200)

    return api


async def _handle_checkout_completed(session: dict):
    session_id = session.get("id", "")
    # Stripe Payment Links embed pack_id in the client_reference_id field
    pack_id = session.get("client_reference_id") or session.get("metadata", {}).get("pack_id")
    customer_telegram_id = session.get("metadata", {}).get("telegram_user_id")
    amount_total = session.get("amount_total", 0)

    if not pack_id:
        logger.warning("checkout.session.completed missing pack_id: %s", session_id)
        return

    # Try to find an undelivered purchase row first
    purchase = None
    if customer_telegram_id:
        purchase = await db.get_undelivered_purchase(int(customer_telegram_id), pack_id)

    # Fallback: look up by session id recorded when user clicked Buy
    if not purchase:
        purchase = await db.confirm_payment_by_session(session_id)

    if not purchase:
        # Create a fresh purchase record from webhook data
        if customer_telegram_id:
            user_id = int(customer_telegram_id)
            await db.upsert_user(user_id)
            purchase_id = await db.create_purchase(
                user_id=user_id,
                pack_id=pack_id,
                stripe_session=session_id,
                amount_cents=amount_total,
            )
            purchase = {"id": purchase_id, "user_id": user_id, "pack_id": pack_id}
        else:
            logger.warning("Cannot map Stripe session %s to a user — no telegram_user_id in metadata", session_id)
            return

    await _trigger_delivery(purchase["user_id"], purchase["pack_id"], purchase["id"])


async def _handle_payment_intent_succeeded(pi: dict):
    pi_id = pi.get("id", "")
    purchase = await db.confirm_payment_by_session(pi_id)
    if not purchase:
        return
    await _trigger_delivery(purchase["user_id"], purchase["pack_id"], purchase["id"])


async def _trigger_delivery(user_id: int, pack_id: str, purchase_id: int):
    if _app_ref is None:
        logger.error("_app_ref not set — cannot trigger delivery for user=%s", user_id)
        return

    from delivery import deliver_pack
    await db.set_user_state(user_id, State.DELIVERY)
    success = await deliver_pack(_app_ref.bot, user_id, pack_id, purchase_id)
    if success:
        await db.set_user_state(user_id, State.UPSELL)
        try:
            from keyboards import upsell_keyboard
            from llm import persona_message
            msg = await persona_message("upsell")
            await _app_ref.bot.send_message(
                chat_id=user_id,
                text=msg,
                reply_markup=upsell_keyboard(),
            )
        except Exception as exc:
            logger.error("Failed to send upsell message to user=%s: %s", user_id, exc)
    logger.info("PAYMENT_CONFIRMED user=%s pack=%s purchase=%s delivered=%s",
                user_id, pack_id, purchase_id, success)


def _verify_stripe_signature(payload: bytes, sig_header: str, secret: str) -> bool:
    """Validate Stripe webhook signature (HMAC-SHA256)."""
    try:
        parts = {k: v for k, v in (p.split("=", 1) for p in sig_header.split(","))}
        timestamp = parts.get("t", "")
        v1_sig = parts.get("v1", "")
        signed_payload = f"{timestamp}.".encode() + payload
        expected = hmac.new(
            secret.encode(), signed_payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, v1_sig)
    except Exception as exc:
        logger.error("Signature verification error: %s", exc)
        return False
