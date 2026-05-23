"""
Entry point — starts the Telegram bot and the FastAPI server (port 5000).
All webhook routes (/webhook, /webhook/payment, /webhook/test) are served
from payments.py via uvicorn on the single public port.
If the port is unavailable the webhook server is skipped and bot polling
continues running normally.
"""

import asyncio
import errno
import logging
import os
import socket
import sys

import uvicorn
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

import db
import payments
import admin_commands
from admin import cmd_ban, cmd_force_deliver, cmd_stats
from config import BOT_TOKEN
from handlers import cmd_start, handle_callback, handle_message

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
# Suppress noisy libs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

WEBHOOK_PORT = int(os.environ.get("PORT", 5000))

# Internal lock port — not exposed publicly, only used to enforce single instance.
# Binding a TCP socket is atomic and auto-released on process exit, which makes it
# reliable in containerised environments where /tmp is not shared between processes.
_LOCK_PORT = 19876


def _acquire_instance_lock() -> socket.socket:
    """Bind a loopback socket as an exclusive single-instance lock.

    If another instance is already running in this container the bind fails
    immediately and the process exits cleanly — no Telegram Conflict.
    The OS releases the socket (and the lock) automatically when the process ends.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Explicitly disable SO_REUSEADDR so the bind fails if the port is taken.
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    try:
        sock.bind(("127.0.0.1", _LOCK_PORT))
        logger.info("Instance lock acquired on port %d (pid=%d)", _LOCK_PORT, os.getpid())
        return sock  # keep reference alive — GC close would release the lock
    except OSError:
        logger.error(
            "Another bot instance is already running (lock port %d busy) — "
            "exiting to prevent Telegram Conflict error. "
            "If no other instance is running, wait a few seconds and retry.",
            _LOCK_PORT,
        )
        sys.exit(1)


async def main():
    _lock = _acquire_instance_lock()  # exits if another instance is running

    # DB init
    await db.init_db()
    logger.info("Database initialised")

    # Build Telegram Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("stats", cmd_stats))
    admin_commands.register(application)  # /deliver basic|premium|vip USER_ID
    application.add_handler(CommandHandler("force_deliver", cmd_force_deliver))
    application.add_handler(CommandHandler("ban", cmd_ban))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Inject application reference into payments module for webhook-triggered delivery
    payments.set_application(application)

    # FastAPI app for Stripe webhooks
    fastapi_app = payments.make_fastapi_app()

    # Start bot (polling)
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    logger.info("Bot polling started")

    # Start webhook server (optional — bot polling continues if port is unavailable)
    config = uvicorn.Config(
        fastapi_app,
        host="0.0.0.0",
        port=WEBHOOK_PORT,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    logger.info("Webhook server starting on port %d", WEBHOOK_PORT)

    try:
        await server.serve()
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            logger.warning(
                "Port %d already in use — webhook server skipped. "
                "Bot polling continues normally.",
                WEBHOOK_PORT,
            )
            await asyncio.Event().wait()  # block until process is killed
        else:
            raise
    finally:
        logger.info("Shutting down…")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
