"""
bot.py: Sarthi Public Assistant - Citizen Document Contradiction Telegram Bot.
Handles single documents, multiple uploads, and Telegram albums/media-groups (up to 5 documents).
"""

import asyncio
import logging
import uuid
from pathlib import Path
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from config import TELEGRAM_BOT_TOKEN, TEMP_DIR
from verification_client import verify_documents
from explainer import format_citizen_report

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# State & Constants
COLLECTING_DOCS = 1
VERIFY_BUTTON_TEXT = "🔍 Jaanch Shuru Karein (Verify Bundle)"
MAX_DOCS = 5
ALBUM_DEBOUNCE_SECONDS = 1.5  # Wait time to collect all images sent together in an album

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Welcomes the citizen and begins document bundle collection."""
    user = update.effective_user
    context.user_data["doc_paths"] = []
    
    # Cancel any pending debounce task
    pending = context.user_data.get("debounce_task")
    if pending and not pending.done():
        pending.cancel()

    welcome_text = (
        f"🙏 *Namaste {user.first_name} ji!*\n\n"
        "Main hoon *Sarthi AI* — aapka Citizen Document Verification Assistant.\n\n"
        "Sarkari form (PM Awas, Scholarship, Ration Card, etc.) bharne se pehle "
        "apne dastavejon ke *Bundle (2 se 5 documents)* ki aapas me jaanch karwayein.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📄 *Documents Bhejiye:*\n"
        "Aap ek-ek karke ya *ek sath select karke multiple photos* bhej sakte hain "
        "(Aadhaar, PAN, Income Certificate, Ration Card, Address proof)."
    )

    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    return COLLECTING_DOCS

async def handle_document_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collects incoming documents, buffering multi-photo albums/bursts cleanly."""
    doc_paths = context.user_data.setdefault("doc_paths", [])

    if len(doc_paths) >= MAX_DOCS:
        await update.message.reply_text(
            f"⚠️ Aap pehle hi adhiktam *{MAX_DOCS} dastavej* upload kar chuke hain. "
            f"Kripya jaanch shuru karne ke liye *'{VERIFY_BUTTON_TEXT}'* dabayein.",
            parse_mode=ParseMode.MARKDOWN
        )
        return COLLECTING_DOCS

    saved_path = await _save_incoming_media(update, context, f"doc_{len(doc_paths) + 1}")
    if not saved_path:
        await update.message.reply_text("⚠️ Kripya document ki saaf photo ya image file bhejiye.")
        return COLLECTING_DOCS

    doc_paths.append(saved_path)
    context.user_data["doc_paths"] = doc_paths
    count = len(doc_paths)

    # Cancel previous debounce task if new image arrived in the same burst/album
    previous_task = context.user_data.get("debounce_task")
    if previous_task and not previous_task.done():
        previous_task.cancel()

    # Schedule debounce notification to allow all photos in an album to arrive first
    task = asyncio.create_task(_debounced_upload_summary(update, context))
    context.user_data["debounce_task"] = task

    return COLLECTING_DOCS

async def _debounced_upload_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Waits briefly for all photos sent in a batch, then replies cleanly once."""
    try:
        await asyncio.sleep(ALBUM_DEBOUNCE_SECONDS)
    except asyncio.CancelledError:
        return

    doc_paths = context.user_data.get("doc_paths", [])
    count = len(doc_paths)

    # If max 5 reached, trigger verification automatically
    if count >= MAX_DOCS:
        await update.message.reply_text(
            f"✅ *Sabhi {MAX_DOCS} dastavej prapt ho gaye!*\n"
            "Jaanch shuru ki ja rahi hai...",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove(),
        )
        await _trigger_verification(update, context)
        return

    # If 2 or more, offer Verify button
    if count >= 2:
        keyboard = [[VERIFY_BUTTON_TEXT]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        msg = (
            f"✅ *Kul {count} Dastavej Prapt Ho Gaye!*\n\n"
            f"📊 Bundle Progress: *{count}/{MAX_DOCS} documents*\n\n"
            "👉 Aap chahein toh aur bhi documents bhej sakte hain,\n"
            f"YA neeche diye gaye *'{VERIFY_BUTTON_TEXT}'* button par click karke abhi jaanch shuru kar sakte hain!"
        )
    else:
        reply_markup = ReplyKeyboardRemove()
        msg = (
            f"✅ *Pehla Dastavej Prapt Ho Gaya!*\n\n"
            "📄 Kripya doosra dastavej (jaise PAN Card ya Income Certificate) bhejiye "
            "taaki cross-verification kiya ja sake."
        )

    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def handle_verify_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Triggered when citizen clicks verify button or types /done."""
    doc_paths = context.user_data.get("doc_paths", [])
    if len(doc_paths) < 2:
        await update.message.reply_text(
            "⚠️ Bundle jaanch ke liye kam se kam *2 dastavej* zaroori hain. Kripya ek aur photo bhejiye.",
            parse_mode=ParseMode.MARKDOWN
        )
        return COLLECTING_DOCS

    await _trigger_verification(update, context)
    return ConversationHandler.END

async def _trigger_verification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Executes bundle verification and sends report."""
    doc_paths = context.user_data.get("doc_paths", [])
    total = len(doc_paths)

    processing_msg = await update.message.reply_text(
        f"⏳ *Kul {total} dastavejon ka bundle mil gaya!*\n"
        "_AI Cross-Document Contradiction Engine sabhi documents ko aapas me mila raha hai... Kripya 2-3 second pratiksha karein..._",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )

    try:
        result_data = await verify_documents(doc_paths)
        report_text = format_citizen_report(result_data)

        await processing_msg.delete()
        await update.message.reply_text(report_text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Error during bundle verification: {e}", exc_info=True)
        await processing_msg.edit_text(
            "❌ Dastavejon ki jaanch me takneeki samasya aayi. Kripya thodi der baad `/start` karke dobara koshish karein."
        )

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the bundle check."""
    pending = context.user_data.get("debounce_task")
    if pending and not pending.done():
        pending.cancel()
    context.user_data.clear()

    await update.message.reply_text(
        "Jaanch raddh (cancel) kar di gayi hai. Dobara shuru karne ke liye `/start` type karein.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage help."""
    help_text = (
        "ℹ️ *Sarthi Bundle Verifier Guide:*\n\n"
        "1. `/start` dabayein.\n"
        "2. Apne documents (2 se 5 tak) bhejte jayein (ek-ek karke ya gallery se ek sath multiple select karke!):\n"
        "   • Aadhaar Card\n"
        "   • PAN Card\n"
        "   • Income Certificate\n"
        "   • Ration Card / Caste Certificate\n"
        "   • Address Proof / Bijli Bill\n"
        "3. Jab sabhi documents bhej dein, toh button dabayein: *'🔍 Jaanch Shuru Karein'*\n"
        "4. AI pura bundle aapas me cross-check karke detail report dega!"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def _save_incoming_media(update: Update, context: ContextTypes.DEFAULT_TYPE, tag: str) -> Path | None:
    """Helper to download incoming photos or document files."""
    session_id = str(uuid.uuid4())[:8]
    file_obj = None
    ext = ".jpg"

    if update.message.photo:
        file_obj = await update.message.photo[-1].get_file()
    elif update.message.document:
        doc = update.message.document
        file_obj = await doc.get_file()
        if doc.file_name and "." in doc.file_name:
            ext = "." + doc.file_name.split(".")[-1]

    if not file_obj:
        return None

    save_path = TEMP_DIR / f"{tag}_{session_id}{ext}"
    await file_obj.download_to_drive(custom_path=save_path)
    return save_path

def main():
    """Starts the Sarthi Telegram Bot."""
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not found in .env or environment!")
        return

    print("🚀 Sarthi Telegram Bot (Album/Multi-Upload Enabled) is starting...")
    
    t_request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
    )
    
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).request(t_request).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states={
            COLLECTING_DOCS: [
                MessageHandler(filters.Regex(f"^{VERIFY_BUTTON_TEXT}$"), handle_verify_request),
                CommandHandler("done", handle_verify_request),
                MessageHandler(filters.PHOTO | filters.Document.ALL, handle_document_upload),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
    )

    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(conv_handler)

    print("✅ Bot is online and listening for messages (Multi-Document Album Support Active)!")
    app.run_polling()

if __name__ == "__main__":
    main()
