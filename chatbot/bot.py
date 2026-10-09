"""
bot.py: Sarthi Public Assistant - Citizen Document Contradiction Telegram Bot.
Handles:
- Single documents & multiple photo uploads / albums
- Live OCR/Field extraction preview (Phase 1)
- Deep cross-document contradiction check (Phase 2)
- Official resolution precedence & empathetic citizen advice (Phase 3)
- Document quality & tampering pre-check (Phase 4)
- Citizen commands: /start, /demo, /scheme, /profile, /help, /cancel (Phase 5)
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
from verification_client import (
    verify_documents,
    verify_bundle_by_id,
    extract_document_fields,
    get_document_preview_summary,
)
from quality_checker import check_document_quality
from explainer import (
    format_citizen_report,
    format_scheme_eligibility,
    format_verified_profile,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# State & Constants
COLLECTING_DOCS = 1
VERIFY_BUTTON_TEXT = "🔍 Jaanch Shuru Karein (Verify Bundle)"
MAX_DOCS = 5
ALBUM_DEBOUNCE_SECONDS = 1.5

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Welcomes the citizen and begins document bundle collection."""
    user = update.effective_user
    context.user_data["doc_paths"] = []
    context.user_data["quality_warnings"] = []
    
    pending = context.user_data.get("debounce_task")
    if pending and not pending.done():
        pending.cancel()

    welcome_text = (
        f"🙏 *Namaste {user.first_name} ji!*\n\n"
        "Main hoon *Sarthi AI* — aapka Citizen Document Verification Assistant.\n\n"
        "Sarkari form (PM Awas, Scholarship, Ration Card, etc.) bharne se pehle "
        "apne dastavejon ke *Bundle (2 se 5 documents)* ki aapas me jaanch karwayein taaki form reject na ho.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📄 *Dastavej Bhejiye:*\n"
        "Aap ek-ek karke ya *ek sath select karke photos/PDFs* bhej sakte hain:\n"
        "• Aadhaar Card\n"
        "• PAN Card\n"
        "• Income Certificate\n"
        "• Ration Card / Voter ID / Address Proof\n\n"
        "💡 *Test Demo Bundles:* `/demo T01`, `/demo T05`, `/demo B07`\n"
        "ℹ️ *Commands:* `/help`, `/scheme`, `/profile`"
    )

    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    return COLLECTING_DOCS

async def demo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Allows testing any of the 14 test cards or 16 backend synthetic test bundles."""
    args = context.args
    bundle_id = args[0] if args else "T05"

    await update.message.reply_text(
        f"⏳ *Backend Contradiction Engine Chal Raha Hai...*\n"
        f"_Test Case: {bundle_id.upper()}_",
        parse_mode=ParseMode.MARKDOWN
    )

    result = verify_bundle_by_id(bundle_id)
    if not result:
        await update.message.reply_text(
            f"❌ Bundle ya Test Card '{bundle_id}' nahi mila.\n\n"
            "📋 *Uplabdh Test Sets:*\n"
            "• `/demo T01` (Aadhaar + PAN: All Clean)\n"
            "• `/demo T02` (Aadhaar + PAN: Initial & Year Diff)\n"
            "• `/demo T05` (Aadhaar + PAN: 15-Year DOB Conflict)\n"
            "• `/demo T07` (Aadhaar + PAN: Spelling Variants)\n"
            "• `/demo T11` (Income Certificates: 8x Gap)\n"
            "• `/demo B01` (PDF Bundle: All Agree)\n"
            "• `/demo B07` (PDF Bundle: DOB Year Mismatch)\n"
            "• `/demo B10` (PDF Bundle: Income Gap)",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Cache for scheme and profile commands
    context.user_data["last_result"] = result
    title = result.get("bundle_title") or f"Test Case {bundle_id.upper()}"
    report = format_citizen_report(result)
    await update.message.reply_text(f"📌 *{title}*\n\n" + report, parse_mode=ParseMode.MARKDOWN)

async def handle_document_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collects incoming documents, buffering multi-photo albums cleanly."""
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

    # Phase 4 Quality Check
    q_res = check_document_quality(saved_path)
    q_warnings = context.user_data.setdefault("quality_warnings", [])
    if q_res.get("warnings"):
        q_warnings.extend(q_res["warnings"])

    doc_paths.append(saved_path)
    context.user_data["doc_paths"] = doc_paths
    count = len(doc_paths)

    previous_task = context.user_data.get("debounce_task")
    if previous_task and not previous_task.done():
        previous_task.cancel()

    task = asyncio.create_task(_debounced_upload_summary(update, context))
    context.user_data["debounce_task"] = task

    return COLLECTING_DOCS

async def _debounced_upload_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Waits briefly for all photos sent in a batch, then replies cleanly once with previews."""
    try:
        await asyncio.sleep(ALBUM_DEBOUNCE_SECONDS)
    except asyncio.CancelledError:
        return

    doc_paths = context.user_data.get("doc_paths", [])
    q_warnings = context.user_data.get("quality_warnings", [])
    count = len(doc_paths)

    # Phase 1: Real Live Extraction Preview for Citizen
    extracted_previews = []
    extracted_docs = []
    for idx, path in enumerate(doc_paths):
        try:
            bdoc = extract_document_fields(path, idx + 1)
            extracted_docs.append(bdoc)
            extracted_previews.append(get_document_preview_summary(bdoc, idx + 1))
        except Exception as e:
            logger.error(f"Error extracting preview for doc {idx+1}: {e}")
            extracted_previews.append(f"📄 *Dastavej {idx+1}:* Prapt hua")

    context.user_data["extracted_docs"] = extracted_docs
    docs_preview_text = "\n\n".join(extracted_previews)

    quality_banner = ""
    if q_warnings:
        # Show top 2 distinct warnings
        distinct_warns = list(dict.fromkeys(q_warnings))[:2]
        quality_banner = "\n\n🔍 *Quality Notice:*\n" + "\n".join(f"  {w}" for w in distinct_warns)

    if count >= MAX_DOCS:
        await update.message.reply_text(
            f"✅ *Sabhi {MAX_DOCS} dastavej prapt aur scan ho gaye!*\n\n"
            f"{docs_preview_text}"
            f"{quality_banner}\n\n"
            "⏳ *Cross-document contradiction jaanch shuru ki ja rahi hai...*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove(),
        )
        await _trigger_verification(update, context)
        return

    if count >= 2:
        keyboard = [[VERIFY_BUTTON_TEXT]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        msg = (
            f"✅ *Kul {count} Dastavej Prapt Aur Scan Ho Gaye!*\n\n"
            f"{docs_preview_text}"
            f"{quality_banner}\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Bundle: *{count}/{MAX_DOCS} documents*\n\n"
            "👉 Aap chahein toh aur bhi documents bhej sakte hain,\n"
            f"YA neeche diye gaye *'{VERIFY_BUTTON_TEXT}'* button par click karke abhi aapas me jaanch shuru karein!"
        )
    else:
        reply_markup = ReplyKeyboardRemove()
        msg = (
            f"✅ *Pehla Dastavej Prapt Aur Scan Ho Gaya!*\n\n"
            f"{docs_preview_text}"
            f"{quality_banner}\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
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
    """Executes backend bundle verification and sends report."""
    doc_paths = context.user_data.get("doc_paths", [])
    total = len(doc_paths)

    processing_msg = await update.message.reply_text(
        f"⏳ *Kul {total} dastavejon ka bundle mil gaya!*\n"
        "_Backend Cross-Document Engine sabhi documents ko aapas me mila raha hai... Kripya 2-3 second pratiksha karein..._",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )

    try:
        result_data = await verify_documents(doc_paths)
        report_text = format_citizen_report(result_data)

        # Cache for /scheme and /profile
        context.user_data["last_result"] = result_data

        await processing_msg.delete()
        await update.message.reply_text(report_text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Error during bundle verification: {e}", exc_info=True)
        await processing_msg.edit_text(
            "❌ Dastavejon ki jaanch me takneeki samasya aayi. Kripya thodi der baad `/start` karke dobara koshish karein."
        )

async def scheme_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Evaluates welfare scheme readiness (PM Awas, PM Kisan, Scholarship)."""
    last_res = context.user_data.get("last_result")
    extracted_docs = context.user_data.get("extracted_docs", [])

    if not last_res and not extracted_docs:
        await update.message.reply_text(
            "⚠️ Yojana eligibility jaanch ke liye pehle apne dastavej check karwayein.\n"
            "Shuru karne ke liye `/start` type karein ya demo dekhne ke liye `/demo T01` type karein.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    text = format_scheme_eligibility(last_res or {}, extracted_docs)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the consolidated verified digital profile."""
    extracted_docs = context.user_data.get("extracted_docs", [])

    if not extracted_docs:
        # Check if doc_paths exist
        doc_paths = context.user_data.get("doc_paths", [])
        if doc_paths:
            extracted_docs = [extract_document_fields(p, i+1) for i, p in enumerate(doc_paths)]
            context.user_data["extracted_docs"] = extracted_docs

    if not extracted_docs:
        await update.message.reply_text(
            "⚠️ Koi dastavej scan nahi hua hai. Pehle `/start` type karke photo upload karein.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    text = format_verified_profile(extracted_docs)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the bundle check and resets session."""
    pending = context.user_data.get("debounce_task")
    if pending and not pending.done():
        pending.cancel()
    context.user_data.clear()

    await update.message.reply_text(
        "Jaanch raddh (cancel) kar di gayi hai. Naya session shuru karne ke liye `/start` type karein.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage help and instructions."""
    help_text = (
        "ℹ️ *SARTHI CITIZEN ASSISTANT GUIDE:*\n\n"
        "1. `/start` — Naya document bundle upload shuru karein.\n"
        "2. Multiple photos ek sath select karke bhej sakte hain!\n"
        "3. Button dabayein: *'🔍 Jaanch Shuru Karein'*\n\n"
        "🏛️ *Yojana & Profile:*\n"
        "• `/scheme` — Sarkari Yojana (PM Awas, PM Kisan, Scholarship) eligibility check\n"
        "• `/profile` — Satypit Golden Profile card dekhein\n\n"
        "💡 *Backend Demo Bundles:*\n"
        "Aap bina upload kiye bhi instant test cases run kar sakte hain:\n"
        "• `/demo T01` — All clean (Aadhaar + PAN match)\n"
        "• `/demo T02` — Initial & birth year variation\n"
        "• `/demo T05` — 15-year DOB discrepancy\n"
        "• `/demo T07` — Harmless spelling variants\n"
        "• `/demo T11` — Income certificate gap\n"
        "• `/demo B01` — PDF clean bundle\n"
        "• `/demo B07` — PDF DOB year conflict\n\n"
        "🔄 `/cancel` — Current upload raddh karein"
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

    print("🚀 Sarthi Telegram Bot (Backend Connected) is starting...")
    
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
        fallbacks=[
            CommandHandler("cancel", cancel_command),
            CommandHandler("clear", cancel_command),
        ],
    )

    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("demo", demo_command))
    app.add_handler(CommandHandler("scheme", scheme_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(conv_handler)

    print("✅ Bot is online and directly connected to backend engine!")
    app.run_polling()

if __name__ == "__main__":
    main()
