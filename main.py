"""
Entry point — starts the Telegram bot and the Stripe webhook FastAPI server
on the same process using uvicorn + asyncio.
"""

import asyncio
import logging
import os

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

WEBHOOK_PORT = int(os.environ.get("PORT", 8080))


async def main():
    # DB init
    await db.init_db()
    logger.info("Database initialised")

    # Build Telegram Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("stats", cmd_stats))
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

    # Start webhook server
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
    finally:
        logger.info("Shutting down…")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
