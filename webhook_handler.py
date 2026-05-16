"""
Payment webhook handler — Flask app on port 5001.

Endpoints:
  POST /webhook/payment  — production endpoint for Segpay/CCBill
                           requires X-Webhook-Signature header
  POST /webhook/test     — test endpoint, no signature check
                           *** REMOVE BEFORE FULL PRODUCTION ***

Run via start_webhook_server() which starts a background daemon thread.
The main asyncio event loop is untouched — each delivery call gets its
own temporary event loop in the Flask thread.
"""

import asyncio
import hashlib
import hmac
import logging
import os
import threading

from flask import Flask, jsonify, request
from flask_cors import CORS

from delivery import deliver_basic_pack, deliver_premium_pack, deliver_vip_pack

logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins=["https://ariaaccess.replit.app"])

_DELIVER_MAP = {
    "basic":   deliver_basic_pack,
    "starter": deliver_basic_pack,
    "premium": deliver_premium_pack,
    "vip":     deliver_vip_pack,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run_async(coro):
    """Run an async coroutine from a sync Flask route using a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _verify_signature(payload: bytes, received_sig: str) -> bool:
    """
    Verify webhook payload signature.

    Stubbed for HMAC-SHA256 using WEBHOOK_SECRET env var.
    Replace with processor-specific logic:
      Segpay:  HMAC-SHA256
      CCBill:  MD5 or SHA-256 depending on API plan
    """
    secret = os.environ.get("WEBHOOK_SECRET", "")
    if not secret:
        logger.warning("_verify_signature: WEBHOOK_SECRET not set — rejecting all requests")
        return False
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_sig)


def _parse_payload(data: dict) -> tuple[str | None, int | None]:
    """
    Extract tier and tg_id from a webhook payload dict.

    Accepted field names (processor-agnostic):
      tid       — transaction ID (logged only, not required)
      tg_id     — Telegram user ID (also accepted: telegram_id, user_id)
      tier      — pack tier: basic/starter/premium/vip
                  (also accepted: pack, product)
    """
    tier  = data.get("tier") or data.get("pack") or data.get("product")
    tg_id = data.get("tg_id") or data.get("telegram_id") or data.get("user_id")
    if tg_id is not None:
        try:
            tg_id = int(tg_id)
        except (ValueError, TypeError):
            tg_id = None
    return tier, tg_id


# ── Production endpoint ───────────────────────────────────────────────────────

@app.post("/webhook/payment")
def payment_webhook():
    """
    Production payment webhook — requires valid X-Webhook-Signature header.
    Replace _verify_signature() internals with processor-specific logic.
    """
    payload = request.get_data()
    sig = request.headers.get("X-Webhook-Signature", "")

    if not _verify_signature(payload, sig):
        logger.warning("Webhook signature verification failed from %s", request.remote_addr)
        return jsonify({"error": "invalid signature"}), 401

    data = request.get_json(force=True, silent=True) or {}
    tid = data.get("tid", "")
    tier, tg_id = _parse_payload(data)

    if not tier or not tg_id:
        logger.warning("Webhook missing tier or tg_id: tid=%s payload=%s", tid, data)
        return jsonify({"error": "missing tier or tg_id"}), 400

    deliver_fn = _DELIVER_MAP.get(tier.lower())
    if not deliver_fn:
        logger.warning("Webhook unknown tier='%s': tid=%s", tier, tid)
        return jsonify({"error": f"unknown tier: {tier}"}), 400

    success = _run_async(deliver_fn(tg_id))
    logger.info("WEBHOOK_DELIVER tier=%s tg_id=%s tid=%s success=%s", tier, tg_id, tid, success)
    return jsonify({"ok": True, "delivered": success})


# ── Test endpoint — REMOVE BEFORE FULL PRODUCTION ────────────────────────────

@app.post("/webhook/test")
def test_webhook():
    """
    Test delivery endpoint — NO signature verification.

    Accepts JSON:
      {"tier": "basic"|"premium"|"vip", "tg_id": 123456789}

    Use this to manually simulate a completed payment during development.

    ╔══════════════════════════════════════════════════════════════╗
    ║  TODO: REMOVE THIS ENDPOINT BEFORE FULL PRODUCTION LAUNCH.  ║
    ║  It allows anyone to trigger delivery without auth.          ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    data = request.get_json(force=True, silent=True) or {}
    tier, tg_id = _parse_payload(data)

    if not tier or not tg_id:
        return jsonify({"error": "missing tier or tg_id"}), 400

    deliver_fn = _DELIVER_MAP.get(tier.lower())
    if not deliver_fn:
        return jsonify({"error": f"unknown tier: {tier}"}), 400

    success = _run_async(deliver_fn(tg_id))
    logger.info("TEST_WEBHOOK_DELIVER tier=%s tg_id=%s success=%s", tier, tg_id, success)
    return jsonify({"ok": True, "delivered": success})

# ── END TEST ENDPOINT ─────────────────────────────────────────────────────────


# ── Server launcher ───────────────────────────────────────────────────────────

def start_webhook_server(port: int = 5001) -> threading.Thread:
    """Start Flask webhook server in a background daemon thread.
    Returns the thread so the caller can monitor it if needed.
    """
    def _run():
        logger.info("Payment webhook server starting on port %d", port)
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

    t = threading.Thread(target=_run, daemon=True, name="webhook-server")
    t.start()
    return t
