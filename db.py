import aiosqlite
import logging
from datetime import datetime

DB_PATH = "bot.db"
logger = logging.getLogger(__name__)


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id          INTEGER PRIMARY KEY,
                username         TEXT,
                state            TEXT    DEFAULT 'GREETING',
                banned           INTEGER DEFAULT 0,
                turn_count       INTEGER DEFAULT 0,
                engagement_score INTEGER DEFAULT 0,
                rejection_flag   INTEGER DEFAULT 0,
                last_offer_time  TEXT,
                created_at       TEXT    DEFAULT (datetime('now')),
                updated_at       TEXT    DEFAULT (datetime('now'))
            )
        """)
        # Migrate existing DBs — ignore errors if columns already exist
        for col_def in [
            "ALTER TABLE users ADD COLUMN turn_count INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN engagement_score INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN rejection_flag INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN last_offer_time TEXT",
            "ALTER TABLE users ADD COLUMN conversation_stage TEXT DEFAULT 'hook'",
            "ALTER TABLE users ADD COLUMN vault_seen INTEGER DEFAULT 0",
        ]:
            try:
                await db.execute(col_def)
            except Exception:
                pass
        await db.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                pack_id         TEXT    NOT NULL,
                stripe_session  TEXT,
                amount_cents    INTEGER,
                delivered       INTEGER DEFAULT 0,
                created_at      TEXT    DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.commit()


# ── User ──────────────────────────────────────────────────────────────────────

async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def upsert_user(user_id: int, username: str | None = None) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, username)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username   = excluded.username,
                updated_at = datetime('now')
        """, (user_id, username))
        await db.commit()
    return await get_user(user_id)


async def set_user_state(user_id: int, state: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users SET state = ?, updated_at = datetime('now')
            WHERE user_id = ?
        """, (state, user_id))
        await db.commit()


async def ban_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET banned = 1, updated_at = datetime('now') WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


async def is_banned(user_id: int) -> bool:
    user = await get_user(user_id)
    return bool(user and user["banned"])


# ── Engagement tracking ───────────────────────────────────────────────────────

async def increment_turn_count(user_id: int) -> int:
    """Increment and return the new turn count."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users SET turn_count = turn_count + 1, updated_at = datetime('now')
            WHERE user_id = ?
        """, (user_id,))
        await db.commit()
    user = await get_user(user_id)
    return user["turn_count"] if user else 0


async def update_engagement_score(user_id: int, delta: int) -> int:
    """Add delta to engagement_score and return new value."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users SET engagement_score = engagement_score + ?, updated_at = datetime('now')
            WHERE user_id = ?
        """, (delta, user_id))
        await db.commit()
    user = await get_user(user_id)
    return user["engagement_score"] if user else 0


async def set_rejection_flag(user_id: int, value: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users SET rejection_flag = ?, updated_at = datetime('now')
            WHERE user_id = ?
        """, (value, user_id))
        await db.commit()


async def set_conversation_stage(user_id: int, stage: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users SET conversation_stage = ?, updated_at = datetime('now')
            WHERE user_id = ?
        """, (stage, user_id))
        await db.commit()


async def set_last_offer_time(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users SET last_offer_time = datetime('now'), updated_at = datetime('now')
            WHERE user_id = ?
        """, (user_id,))
        await db.commit()


# ── Purchases ─────────────────────────────────────────────────────────────────

async def create_purchase(
    user_id: int,
    pack_id: str,
    stripe_session: str | None = None,
    amount_cents: int = 0,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO purchases (user_id, pack_id, stripe_session, amount_cents)
            VALUES (?, ?, ?, ?)
        """, (user_id, pack_id, stripe_session, amount_cents))
        await db.commit()
        return cur.lastrowid


async def mark_delivered(purchase_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE purchases SET delivered = 1 WHERE id = ?", (purchase_id,)
        )
        await db.commit()


async def has_been_delivered(user_id: int, pack_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT id FROM purchases
            WHERE user_id = ? AND pack_id = ? AND delivered = 1
            LIMIT 1
        """, (user_id, pack_id)) as cur:
            return await cur.fetchone() is not None


async def get_undelivered_purchase(user_id: int, pack_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM purchases
            WHERE user_id = ? AND pack_id = ? AND delivered = 0
            ORDER BY created_at DESC LIMIT 1
        """, (user_id, pack_id)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def confirm_payment_by_session(stripe_session: str) -> dict | None:
    """Return the purchase row matching a Stripe session/payment_intent id."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM purchases
            WHERE stripe_session = ? AND delivered = 0
            LIMIT 1
        """, (stripe_session,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


# ── Stats ─────────────────────────────────────────────────────────────────────

async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users WHERE banned = 0") as cur:
            total_users = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM purchases WHERE delivered = 1") as cur:
            total_purchases = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) FROM purchases WHERE delivered = 1"
        ) as cur:
            revenue_cents = (await cur.fetchone())[0]
    return {
        "total_users": total_users,
        "total_purchases": total_purchases,
        "revenue_cents": revenue_cents,
    }
