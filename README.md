# Luna Bot — V1 Setup Guide

AI-generated persona Telegram bot that sells compliant non-explicit content packs via Stripe Payment Links.

---

## Architecture Overview

```
User → Telegram Bot (polling) → State Machine → DB (SQLite/aiosqlite)
                                              ↓
Stripe Payment Link → Webhook (FastAPI/uvicorn) → Delivery → User
```

**State flow:** `GREETING → WARMUP → OFFER → PAYMENT_PENDING → DELIVERY → UPSELL → EXIT`

Claude API handles message tone only — never controls state or delivery.

---

## Step 1 — Telegram BotFather

1. Open Telegram and message **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the **bot token** → paste into `.env` as `BOT_TOKEN`
4. Optionally set a profile photo: `/setuserpic`
5. To find your **numeric user ID** message **@userinfobot** → copy the `Id` field → paste as `ADMIN_USER_ID`

---

## Step 2 — Stripe Payment Links

### Create three Payment Links

1. Log in to [dashboard.stripe.com](https://dashboard.stripe.com)
2. Go to **Payment Links → + New**
3. Add a one-time price product for each pack:
   - **Pack A (Starter)** — $9.00
   - **Pack B (Premium)** — $19.00
   - **Pack C (VIP)** — $39.00
4. Under **After payment → Confirmation page**, set a thank-you message
5. Under **Metadata**, add a key `pack_id` with value `pack_a` / `pack_b` / `pack_c`
   *(This lets the webhook map payments back to the right pack)*
6. Copy each Payment Link URL → paste into `.env`:
   ```
   STRIPE_LINK_PACK_A=https://buy.stripe.com/...
   STRIPE_LINK_PACK_B=https://buy.stripe.com/...
   STRIPE_LINK_PACK_C=https://buy.stripe.com/...
   ```

### Register the webhook

1. Stripe Dashboard → **Developers → Webhooks → + Add endpoint**
2. **Endpoint URL:** `https://your-replit-url.repl.co/webhook`
3. **Events to listen to:**
   - `checkout.session.completed`
   - `payment_intent.succeeded`
4. Click **Add endpoint** → copy the **Signing secret** (`whsec_...`) → paste as `STRIPE_WEBHOOK_SECRET`

---

## Step 3 — Delivery Links

For each pack, create a **private Telegram channel**:

1. Create a new private channel in Telegram
2. Go to channel settings → **Invite links → Create invite link**
3. Set **Expiry: Never** and **Limit: No limit** (or configure per-buyer limits)
4. Copy the invite link → paste into `.env`:
   ```
   DELIVERY_LINK_PACK_A=https://t.me/+...
   DELIVERY_LINK_PACK_B=https://t.me/+...
   DELIVERY_LINK_PACK_C=https://t.me/+...
   ```

Alternatively, use any direct download URL (Google Drive, Dropbox, etc.) that requires no login.

---

## Step 4 — Sample Images

Upload sample images to Telegram or use public URLs:

- **Quickest:** host 2–3 images publicly (e.g. Imgur, your CDN) and add URLs:
  ```
  SAMPLE_IMAGES_PACK_A=https://example.com/img1.jpg,https://example.com/img2.jpg
  ```
- **Telegram file_ids:** send images to your bot via a test account, then check the raw update in logs to copy `file_id` strings.

---

## Step 5 — Replit Reserved VM

1. Create a new **Python 3.11** Repl (or import from GitHub)
2. Copy all project files into the Repl (or connect via GitHub)
3. In Replit **Secrets** (padlock icon), add every variable from `.env.example`
4. Open `requirements.txt` — Replit will install deps automatically, or run:
   ```
   pip install -r requirements.txt
   ```
5. Set the **Run command** to:
   ```
   python main.py
   ```
6. Switch to a **Reserved VM** (Replit sidebar → Deployments → Reserved VM)
   — this keeps the bot running 24/7 and gives you a stable public URL for the Stripe webhook
7. Copy the public URL (e.g. `https://your-bot.repl.co`) and update the Stripe webhook endpoint

---

## Step 6 — Environment Variables

Copy `.env.example` to `.env` and fill in every value:

```bash
cp .env.example .env
```

For local development, install `python-dotenv` and add to the top of `main.py`:
```python
from dotenv import load_dotenv
load_dotenv()
```

---

## Step 7 — Running Locally

```bash
pip install -r requirements.txt
python main.py
```

For local Stripe webhook testing, use the [Stripe CLI](https://stripe.com/docs/stripe-cli):
```bash
stripe listen --forward-to localhost:8080/webhook
```

---

## Running Tests

```bash
pip install pytest pytest-asyncio
python -m pytest tests.py -v
```

---

## Admin Commands

All commands restricted to `ADMIN_USER_ID`:

| Command | Description |
|---|---|
| `/stats` | Total users, purchases, revenue |
| `/force_deliver <user_id> <pack_id>` | Manually trigger delivery |
| `/ban <user_id>` | Block a user from the bot |

---

## File Structure

```
main.py          — Entry point, bot + webhook server startup
config.py        — All env vars + pack definitions
states.py        — State machine (enum + transition table)
handlers.py      — Telegram conversation handlers
keyboards.py     — Inline keyboard factories
db.py            — SQLite schema + async CRUD
payments.py      — Stripe webhook FastAPI endpoint
delivery.py      — One-time content delivery with duplicate guard
admin.py         — Admin-only command handlers
llm.py           — Claude API tone layer (optional)
tests.py         — Acceptance tests
requirements.txt — Python dependencies
.env.example     — Environment variable template
```

---

## Constraints & Design Notes

- **No subscriptions / recurring billing** — one-time purchases only
- **Duplicate delivery prevention** — DB is marked delivered *before* the Telegram send; admin `/force_deliver` is the recovery path
- **LLM is tone-only** — Claude writes the copy; all state transitions are in Python
- **Stripe Payment Links** — no Checkout Sessions API; webhook maps via `client_reference_id` or `metadata.pack_id`
- **All content must be non-explicit** and comply with Telegram's ToS and Stripe's acceptable use policy
