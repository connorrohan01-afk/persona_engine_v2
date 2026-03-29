"""
Acceptance tests for the Telegram bot.
Run with: python -m pytest tests.py -v

Tests use an in-memory SQLite DB and mock Telegram/Stripe calls.
No network access required.
"""

import asyncio
import json
import os

# ── Set required env vars before importing app modules ────────────────────────
os.environ.setdefault("BOT_TOKEN", "1234567890:AAFakeTokenForTesting")
os.environ.setdefault("ADMIN_USER_ID", "999")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pytest
import aiosqlite

import db
from states import State, can_transition
from config import PACKS


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def use_temp_db(tmp_path, monkeypatch):
    """Each test gets its own fresh SQLite file."""
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", db_file)


@pytest.fixture
def run(event_loop):
    return event_loop.run_until_complete


# pytest-asyncio >= 0.21 needs this
pytestmark = pytest.mark.asyncio


# ── State machine ──────────────────────────────────────────────────────────────

class TestStateMachine:
    def test_valid_transitions(self):
        assert can_transition(State.GREETING, State.WARMUP)
        assert can_transition(State.WARMUP, State.OFFER)
        assert can_transition(State.OFFER, State.PAYMENT_PENDING)
        assert can_transition(State.PAYMENT_PENDING, State.DELIVERY)
        assert can_transition(State.DELIVERY, State.UPSELL)
        assert can_transition(State.UPSELL, State.OFFER)
        assert can_transition(State.UPSELL, State.EXIT)

    def test_invalid_transitions(self):
        assert not can_transition(State.GREETING, State.DELIVERY)
        assert not can_transition(State.DELIVERY, State.GREETING)
        assert not can_transition(State.EXIT, State.GREETING)
        assert not can_transition(State.PAYMENT_PENDING, State.UPSELL)

    def test_unknown_state(self):
        assert not can_transition("BOGUS", State.WARMUP)
        assert not can_transition(State.WARMUP, "BOGUS")


# ── Database ──────────────────────────────────────────────────────────────────

class TestDatabase:
    async def test_init_db(self):
        await db.init_db()

    async def test_upsert_and_get_user(self):
        await db.init_db()
        user = await db.upsert_user(101, "testuser")
        assert user["user_id"] == 101
        assert user["username"] == "testuser"
        assert user["state"] == State.GREETING
        assert user["banned"] == 0

    async def test_upsert_updates_username(self):
        await db.init_db()
        await db.upsert_user(101, "old_name")
        user = await db.upsert_user(101, "new_name")
        assert user["username"] == "new_name"

    async def test_get_user_not_found(self):
        await db.init_db()
        assert await db.get_user(99999) is None

    async def test_set_user_state(self):
        await db.init_db()
        await db.upsert_user(102, "statetest")
        await db.set_user_state(102, State.OFFER)
        user = await db.get_user(102)
        assert user["state"] == State.OFFER

    async def test_ban_user(self):
        await db.init_db()
        await db.upsert_user(103, "victim")
        assert not await db.is_banned(103)
        await db.ban_user(103)
        assert await db.is_banned(103)

    async def test_create_purchase(self):
        await db.init_db()
        await db.upsert_user(104, "buyer")
        pid = await db.create_purchase(104, "pack_a", "sess_abc", 900)
        assert isinstance(pid, int)
        assert pid > 0

    async def test_mark_delivered(self):
        await db.init_db()
        await db.upsert_user(105, "buyer2")
        pid = await db.create_purchase(105, "pack_b", "sess_def", 1900)
        assert not await db.has_been_delivered(105, "pack_b")
        await db.mark_delivered(pid)
        assert await db.has_been_delivered(105, "pack_b")

    async def test_no_double_delivery(self):
        await db.init_db()
        await db.upsert_user(106, "buyer3")
        pid = await db.create_purchase(106, "pack_c", "sess_ghi", 3900)
        await db.mark_delivered(pid)
        # Second purchase row for same user+pack, should still block
        pid2 = await db.create_purchase(106, "pack_c", "sess_jkl", 3900)
        assert await db.has_been_delivered(106, "pack_c")

    async def test_get_undelivered_purchase(self):
        await db.init_db()
        await db.upsert_user(107, "buyer4")
        pid = await db.create_purchase(107, "pack_a", "sess_mno", 900)
        row = await db.get_undelivered_purchase(107, "pack_a")
        assert row is not None
        assert row["id"] == pid
        await db.mark_delivered(pid)
        row2 = await db.get_undelivered_purchase(107, "pack_a")
        assert row2 is None

    async def test_stats(self):
        await db.init_db()
        await db.upsert_user(201, "u1")
        await db.upsert_user(202, "u2")
        pid = await db.create_purchase(201, "pack_b", "sess_s1", 1900)
        await db.mark_delivered(pid)
        stats = await db.get_stats()
        assert stats["total_users"] >= 2
        assert stats["total_purchases"] >= 1
        assert stats["revenue_cents"] >= 1900


# ── Config / Packs ────────────────────────────────────────────────────────────

class TestConfig:
    def test_packs_exist(self):
        assert "pack_a" in PACKS
        assert "pack_b" in PACKS
        assert "pack_c" in PACKS

    def test_pack_fields(self):
        for pack_id, pack in PACKS.items():
            assert "name" in pack, f"{pack_id} missing 'name'"
            assert "price_usd" in pack, f"{pack_id} missing 'price_usd'"
            assert "payment_link" in pack, f"{pack_id} missing 'payment_link'"
            assert "amount_cents" in pack, f"{pack_id} missing 'amount_cents'"
            assert isinstance(pack["amount_cents"], int)


# ── Delivery duplicate guard ──────────────────────────────────────────────────

class TestDeliveryGuard:
    async def test_deliver_pack_prevents_duplicate(self, monkeypatch):
        """deliver_pack returns False if already delivered."""
        await db.init_db()
        await db.upsert_user(301, "buyer5")
        pid = await db.create_purchase(301, "pack_a", "sess_pqr", 900)
        await db.mark_delivered(pid)

        from delivery import deliver_pack
        from unittest.mock import AsyncMock, MagicMock
        mock_bot = AsyncMock()
        result = await deliver_pack(mock_bot, 301, "pack_a", pid)
        assert result is False
        mock_bot.send_message.assert_not_called()

    async def test_deliver_pack_sends_message(self, monkeypatch):
        """deliver_pack sends a message and marks delivered."""
        await db.init_db()
        await db.upsert_user(302, "buyer6")
        pid = await db.create_purchase(302, "pack_b", "sess_stu", 1900)

        from delivery import deliver_pack
        from unittest.mock import AsyncMock
        mock_bot = AsyncMock()
        result = await deliver_pack(mock_bot, 302, "pack_b", pid)
        assert result is True
        mock_bot.send_message.assert_called_once()
        assert await db.has_been_delivered(302, "pack_b")

    async def test_deliver_pack_unknown_pack(self):
        await db.init_db()
        from delivery import deliver_pack
        from unittest.mock import AsyncMock
        mock_bot = AsyncMock()
        result = await deliver_pack(mock_bot, 303, "pack_z", 999)
        assert result is False


# ── Stripe webhook signature ──────────────────────────────────────────────────

class TestStripeWebhook:
    def test_valid_signature(self):
        import hashlib
        import hmac as hmac_mod
        import time

        secret = "whsec_testsecret"
        payload = b'{"type":"checkout.session.completed"}'
        timestamp = str(int(time.time()))
        signed = f"{timestamp}.".encode() + payload
        sig = hmac_mod.new(secret.encode(), signed, hashlib.sha256).hexdigest()
        sig_header = f"t={timestamp},v1={sig}"

        from payments import _verify_stripe_signature
        assert _verify_stripe_signature(payload, sig_header, secret)

    def test_invalid_signature(self):
        from payments import _verify_stripe_signature
        assert not _verify_stripe_signature(b"payload", "t=1234,v1=badsig", "secret")

    def test_missing_signature_header(self):
        from payments import _verify_stripe_signature
        assert not _verify_stripe_signature(b"payload", "", "secret")


# ── Admin guard ───────────────────────────────────────────────────────────────

class TestAdminGuard:
    async def test_non_admin_blocked(self):
        from unittest.mock import AsyncMock, MagicMock
        from admin import cmd_stats

        update = MagicMock()
        update.effective_user.id = 555  # not admin (admin=999)
        context = MagicMock()

        await cmd_stats(update, context)
        update.message.reply_text.assert_not_called()

    async def test_admin_allowed(self):
        await db.init_db()
        from unittest.mock import AsyncMock, MagicMock, patch
        from admin import cmd_stats

        update = MagicMock()
        update.effective_user.id = 999  # ADMIN_USER_ID
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await cmd_stats(update, context)
        update.message.reply_text.assert_called_once()
