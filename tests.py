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
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "1234567890:AAFakeTokenForTesting")
os.environ.setdefault("ADMIN_USER_ID", "999")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "")
os.environ.setdefault("OPENAI_API_KEY", "")

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
        # Five-state primary chain
        assert can_transition(State.GREETING, State.HOOK)
        assert can_transition(State.HOOK, State.BUILD)
        assert can_transition(State.BUILD, State.POST_TEASE)    # tease fires → POST_TEASE
        assert can_transition(State.POST_TEASE, State.OFFER)    # vault opens from POST_TEASE only
        assert can_transition(State.OFFER, State.PREVIEW)
        assert can_transition(State.OFFER, State.BUILD)         # rejection loops to BUILD
        assert can_transition(State.PREVIEW, State.PAYMENT_PENDING)
        assert can_transition(State.PAYMENT_PENDING, State.DELIVERY)
        assert can_transition(State.DELIVERY, State.UPSELL)
        assert can_transition(State.UPSELL, State.OFFER)
        assert can_transition(State.UPSELL, State.EXIT)
        # Legacy state transitions still work (old DB rows)
        assert can_transition(State.WARMUP, State.WARMUP)
        assert can_transition(State.WARMUP, State.BUILD)
        assert can_transition(State.SOFT_INVITE, State.OFFER)
        assert can_transition(State.SOFT_INVITE, State.BUILD)

    def test_invalid_transitions(self):
        assert not can_transition(State.GREETING, State.DELIVERY)
        assert not can_transition(State.DELIVERY, State.GREETING)
        assert not can_transition(State.EXIT, State.GREETING)
        assert not can_transition(State.PAYMENT_PENDING, State.UPSELL)
        assert not can_transition(State.WARMUP, State.PAYMENT_PENDING)
        assert not can_transition(State.SOFT_INVITE, State.PREVIEW)
        # STATE LOCK: vault cannot be reached without passing through POST_TEASE
        assert not can_transition(State.BUILD, State.OFFER)
        assert not can_transition(State.HOOK, State.OFFER)
        assert not can_transition(State.HOOK, State.POST_TEASE)
        assert not can_transition(State.GREETING, State.BUILD)

    def test_unknown_state(self):
        assert not can_transition("BOGUS", State.BUILD)
        assert not can_transition(State.BUILD, "BOGUS")

    def test_new_states_exist(self):
        # Primary states
        assert State.HOOK == "HOOK"
        assert State.BUILD == "BUILD"
        assert State.POST_TEASE == "POST_TEASE"
        assert State.OFFER == "OFFER"
        assert State.PREVIEW == "PREVIEW"
        # Legacy states still accessible (for old DB rows)
        assert State.WARMUP == "WARMUP"
        assert State.CURIOSITY == "CURIOSITY"
        assert State.SOFT_INVITE == "SOFT_INVITE"


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


# ── Engagement tracking ───────────────────────────────────────────────────────

class TestEngagement:
    async def test_increment_turn_count(self):
        await db.init_db()
        await db.upsert_user(501, "turner")
        assert await db.increment_turn_count(501) == 1
        assert await db.increment_turn_count(501) == 2
        assert await db.increment_turn_count(501) == 3

    async def test_update_engagement_score(self):
        await db.init_db()
        await db.upsert_user(502, "engager")
        score = await db.update_engagement_score(502, 1)
        assert score == 1
        score = await db.update_engagement_score(502, 1)
        assert score == 2
        score = await db.update_engagement_score(502, -1)
        assert score == 1

    async def test_set_rejection_flag(self):
        await db.init_db()
        await db.upsert_user(503, "rejector")
        user = await db.get_user(503)
        assert user["rejection_flag"] == 0
        await db.set_rejection_flag(503, 1)
        user = await db.get_user(503)
        assert user["rejection_flag"] == 1

    async def test_set_last_offer_time(self):
        await db.init_db()
        await db.upsert_user(504, "shopper")
        user = await db.get_user(504)
        assert user["last_offer_time"] is None
        await db.set_last_offer_time(504)
        user = await db.get_user(504)
        assert user["last_offer_time"] is not None

    async def test_new_columns_present(self):
        await db.init_db()
        await db.upsert_user(505, "coltest")
        user = await db.get_user(505)
        assert "turn_count" in user
        assert "engagement_score" in user
        assert "rejection_flag" in user
        assert "last_offer_time" in user


# ── Engagement scoring helpers ────────────────────────────────────────────────

class TestEngagementScoring:
    def test_positive_score(self):
        from handlers import _score_message
        assert _score_message("yeah sounds cool") == 1
        assert _score_message("omg yes please") == 1

    def test_negative_score(self):
        from handlers import _score_message
        assert _score_message("no thanks bye") == -1

    def test_neutral_score(self):
        from handlers import _score_message
        # A short message with no keywords
        assert _score_message("k") == 0

    def test_affirmative_detection(self):
        from handlers import _is_affirmative
        assert _is_affirmative("yeah sure")
        assert _is_affirmative("show me")
        assert _is_affirmative("go ahead")
        assert _is_affirmative("ok")
        assert not _is_affirmative("nope")
        assert not _is_affirmative("maybe later")

    def test_negative_detection(self):
        from handlers import _is_negative
        assert _is_negative("no thanks")
        assert _is_negative("nah")
        assert not _is_negative("yeah definitely")

    def test_hesitant_detection(self):
        from handlers import _is_hesitant
        # Classic hesitant / ambiguous inputs
        assert _is_hesitant("maybe")
        assert _is_hesitant("not sure")
        assert _is_hesitant("is it worth it")
        assert _is_hesitant("i guess")
        assert _is_hesitant("idk")
        assert _is_hesitant("just browsing")
        assert _is_hesitant("is it worth the money")
        # Should NOT be hesitant
        assert not _is_hesitant("yes please")
        assert not _is_hesitant("no thanks")
        assert not _is_hesitant("show me")

    def test_hesitant_not_affirmative_or_negative(self):
        from handlers import _is_hesitant, _is_affirmative, _is_negative
        for phrase in ["maybe", "not sure", "i guess", "idk"]:
            assert _is_hesitant(phrase)
            assert not _is_affirmative(phrase)

    def test_fallback_pools_are_varied(self):
        from llm import _GREETING_FALLBACKS, _WARMUP_FALLBACKS, _HESITANT_FALLBACKS
        assert len(_GREETING_FALLBACKS) >= 5
        assert len(_WARMUP_FALLBACKS) >= 8
        assert len(_HESITANT_FALLBACKS) >= 4
        # All entries are non-empty strings
        for pool in (_GREETING_FALLBACKS, _WARMUP_FALLBACKS, _HESITANT_FALLBACKS):
            for line in pool:
                assert isinstance(line, str) and len(line) > 0
        # No greeting openers contain banned phrases
        banned = ["hey there", "hi there", "hello", "hey!"]
        for line in _GREETING_FALLBACKS:
            for b in banned:
                assert b not in line.lower(), f"Banned opener '{b}' found in: {line}"

    def test_buying_signal_detection(self):
        from handlers import _is_buying_signal
        assert _is_buying_signal("how do i buy this")
        assert _is_buying_signal("i'll take it")
        assert _is_buying_signal("how do i pay")
        assert _is_buying_signal("i want to buy")
        assert _is_buying_signal("send it")
        # Negated / ambiguous should NOT trigger
        assert not _is_buying_signal("not buying this")
        assert not _is_buying_signal("maybe later")
        assert not _is_buying_signal("just looking")

    def test_offer_cooldown_constant(self):
        from handlers import _OFFER_COOLDOWN_TURNS, _OFFER_MAX_TURNS
        # Cooldown must be substantial — no eager re-offers
        assert _OFFER_COOLDOWN_TURNS >= 4
        assert _OFFER_MAX_TURNS > _OFFER_COOLDOWN_TURNS

    def test_buying_signal_beats_hesitant(self):
        from handlers import _is_buying_signal, _is_hesitant
        # Buying signals should not be classified as hesitant
        for phrase in ["how do i buy", "i'll take it", "send it"]:
            assert _is_buying_signal(phrase)
            assert not _is_hesitant(phrase)

    def test_content_question_detection(self):
        from handlers import _is_asking_about_content
        assert _is_asking_about_content("what's in the vip pack")
        assert _is_asking_about_content("what do i get")
        assert _is_asking_about_content("what's the difference")
        assert _is_asking_about_content("tell me more about pack b")
        assert _is_asking_about_content("which one should i get")
        # Generic chat should not trigger
        assert not _is_asking_about_content("that sounds cool")
        assert not _is_asking_about_content("haha okay")
        assert not _is_asking_about_content("how are you")

    def test_greeting_fallbacks_have_no_emoji(self):
        from llm import _GREETING_FALLBACKS
        emoji_ranges = range(0x1F300, 0x1FAFF)
        for line in _GREETING_FALLBACKS:
            for ch in line:
                assert ord(ch) not in emoji_ranges, f"Emoji found in greeting: {line!r}"

    def test_warmup_fallbacks_no_eager_lines(self):
        from llm import _WARMUP_FALLBACKS
        eager = ["tell me more", "go on", "haha okay go on"]
        for line in _WARMUP_FALLBACKS:
            assert line not in eager, f"Eager line found in warmup pool: {line!r}"

    def test_new_llm_stages_have_fallbacks(self):
        """post_offer and objection stages must have fallback copy."""
        import os
        os.environ.setdefault("OPENAI_API_KEY", "")
        # Import after env is set so _get_client() returns None
        import importlib
        import llm as llm_module
        # Call synchronously via the fallback path (no API key)
        import asyncio
        async def _check():
            r1 = await llm_module.chat_reply("hmm", context={"stage": "post_offer"})
            r2 = await llm_module.chat_reply("not worth it", context={"stage": "objection"})
            assert isinstance(r1, str) and len(r1) > 0
            assert isinstance(r2, str) and len(r2) > 0
        asyncio.get_event_loop().run_until_complete(_check())


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
