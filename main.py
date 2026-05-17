"""
Entry point — starts the Telegram bot and the FastAPI server (port 5000).
All webhook routes (/webhook, /webhook/payment, /webhook/test) are served
from payments.py via uvicorn on the single public port.
If the port is unavailable the webhook server is skipped and bot polling
continues running normally.
"""

import asyncio
import errno
import fcntl
import logging
import os
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
_LOCK_FILE = "/tmp/luna-bot.lock"


def _acquire_instance_lock() -> object:
    """Open an exclusive file lock so only one bot process can run at a time.
    A second process that calls this will log an error and exit immediately,
    which prevents telegram.error.Conflict from two pollers hitting the same token.
    The lock is automatically released when the process exits (OS closes the fd).
    """
    try:
        fp = open(_LOCK_FILE, "w")
        fcntl.flock(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fp.write(str(os.getpid()))
        fp.flush()
        logger.info("Instance lock acquired (pid=%d)", os.getpid())
        return fp  # keep reference alive — GC would release the lock
    except OSError:
        logger.error(
            "Another bot instance is already running — exiting to avoid Conflict. "
            "Stop the other process first, or delete %s if it is stale.",
            _LOCK_FILE,
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
