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
import sys
import uuid
from pathlib import Path

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
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
from chat_service import ask_sarthi_assistant

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# State & Constants
COLLECTING_DOCS = 1
VERIFY_BUTTON_TEXT = "🔍 Verify Bundle Now"
MAX_DOCS = 5
ALBUM_DEBOUNCE_SECONDS = 1.5

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Welcomes the citizen and begins document bundle collection."""
    user = update.effective_user
    context.user_data["doc_paths"] = []
    context.user_data["quality_warnings"] = []
    context.user_data["chat_history"] = []
    
    pending = context.user_data.get("debounce_task")
    if pending and not pending.done():
        pending.cancel()

    welcome_text = (
        f"🙏 *Welcome {user.first_name}!* \n\n"
        "I am *Sarthi AI* — your Citizen Document Verification Assistant.\n\n"
        "Before submitting government welfare scheme forms (PM Awas, Scholarship, PM Kisan, Ration Card), "
        "verify your *Document Bundle (2 to 5 documents)* to catch conflicting details and avoid rejection.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📄 *Upload Documents:*\n"
        "Send photos or PDFs one-by-one or in a batch:\n"
        "• Aadhaar Card\n"
        "• PAN Card\n"
        "• Income Certificate\n"
        "• Ration Card / Voter ID / Address Proof\n\n"
        "💡 *Test Demo Bundles:* `/demo T01`, `/demo T05`, `/demo B07`\n"
        "🌐 *Multi-lingual AI:* You can talk to me in *English, Hindi (हिन्दी), Gujarati (ગુજરાતી), Marathi (मराठी)* or any native language!"
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

async def _safe_reply(update: Update, text: str, reply_markup=None):
    """Replies with Markdown, falling back to clean plain text if Telegram Markdown parsing fails."""
    try:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    except Exception as e:
        logger.warning(f"Markdown reply failed ({e}), sending plain text")
        plain = text.replace("*", "").replace("`", "").replace("_", "")
        await update.message.reply_text(plain, reply_markup=reply_markup)


async def handle_document_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collects incoming documents, buffering multi-photo albums cleanly."""
    try:
        await update.message.chat.send_action("upload_document")
    except Exception:
        pass

    doc_paths = context.user_data.setdefault("doc_paths", [])

    if len(doc_paths) >= MAX_DOCS:
        await _safe_reply(
            update,
            f"⚠️ Aap pehle hi adhiktam *{MAX_DOCS} dastavej* upload kar chuke hain. "
            f"Kripya jaanch shuru karne ke liye *'{VERIFY_BUTTON_TEXT}'* dabayein."
        )
        return COLLECTING_DOCS

    saved_path = await _save_incoming_media(update, context, f"doc_{len(doc_paths) + 1}")
    if not saved_path:
        await _safe_reply(update, "⚠️ Kripya document ki saaf photo ya image file bhejiye.")
        return COLLECTING_DOCS

    # Phase 4 Quality Check
    q_res = check_document_quality(saved_path)
    q_warnings = context.user_data.setdefault("quality_warnings", [])
    if q_res.get("warnings"):
        q_warnings.extend(q_res["warnings"])

    doc_paths.append(saved_path)
    context.user_data["doc_paths"] = doc_paths

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

    try:
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
                logger.error(f"Error extracting preview for doc {idx+1}: {e}", exc_info=True)
                extracted_previews.append(f"📄 *Dastavej {idx+1}:* Prapt hua ({path.name})")

        context.user_data["extracted_docs"] = extracted_docs
        docs_preview_text = "\n\n".join(extracted_previews)

        quality_banner = ""
        if q_warnings:
            distinct_warns = list(dict.fromkeys(q_warnings))[:2]
            quality_banner = "\n\n🔍 *Quality Notice:*\n" + "\n".join(f"  {w}" for w in distinct_warns)

        if count >= MAX_DOCS:
            msg = (
                f"✅ *Maximum {MAX_DOCS} documents received!*\n\n"
                f"{docs_preview_text}"
                f"{quality_banner}\n\n"
                "⏳ *Starting Cross-Document Contradiction Engine...*"
            )
            await _safe_reply(update, msg, reply_markup=ReplyKeyboardRemove())
            await _trigger_verification(update, context)
            return

        if count >= 2:
            keyboard = [
                [VERIFY_BUTTON_TEXT],
                ["➕ Add More Documents", "🔄 Start Over (/start)"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            msg = (
                f"✅ *Document {count} Scanned!*\n\n"
                f"{docs_preview_text}"
                f"{quality_banner}\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 Bundle: *{count}/{MAX_DOCS} Documents Received*\n\n"
                "👉 You can upload more documents (e.g. PAN / Address Proof),\n"
                f"OR tap *'{VERIFY_BUTTON_TEXT}'* below to check cross-document consistency!"
            )
            await _safe_reply(update, msg, reply_markup=reply_markup)
        else:
            keyboard = [
                ["➕ Add Next Document", "🔄 Start Over (/start)"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            msg = (
                f"✅ *First Document Scanned!*\n\n"
                f"{docs_preview_text}"
                f"{quality_banner}\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "📄 *Next Step:* Please send the second document (e.g. PAN Card or Address Proof) for Cross-Verification."
            )
            await _safe_reply(update, msg, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error in _debounced_upload_summary: {e}", exc_info=True)
        await _safe_reply(update, f"✅ Document received ({len(context.user_data.get('doc_paths', []))} files). Tap 'Verify' or send more documents.")

async def handle_verify_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Triggered when citizen clicks verify button or types /done."""
    doc_paths = context.user_data.get("doc_paths", [])
    if len(doc_paths) < 2:
        await _safe_reply(
            update,
            "⚠️ Bundle verification requires at least *2 documents*. Please send another photo or document."
        )
        return COLLECTING_DOCS

    await _trigger_verification(update, context)
    return COLLECTING_DOCS

async def _trigger_verification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Executes backend bundle verification and sends report on the spot."""
    doc_paths = context.user_data.get("doc_paths", [])
    total = len(doc_paths)

    processing_msg = await update.message.reply_text(
        f"⏳ *Verifying {total} documents...*\n"
        "_Backend Cross-Document Engine is comparing all document details..._",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )

    try:
        result_data = await verify_documents(doc_paths)
        report_text = format_citizen_report(result_data)

        # Cache for /scheme and /profile
        context.user_data["last_result"] = result_data

        keyboard = [
            ["📜 /scheme (Check Scheme)", "👤 /profile (Digital Profile)"],
            ["➕ Add More Documents", "🔄 Start Over (/start)"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        try:
            await processing_msg.delete()
        except Exception:
            pass

        await _safe_reply(update, report_text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error during bundle verification: {e}", exc_info=True)
        await processing_msg.edit_text(
            "❌ Technical issue during verification. Please try again with `/start`."
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

async def handle_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles natural language conversational queries using Groq LLM (Grounded, No Hallucination)."""
    text = update.message.text
    if not text or text.strip().startswith("/"):
        return

    # Check if action buttons were clicked
    clean_text = text.strip().lower()
    if text.strip() == VERIFY_BUTTON_TEXT or any(k in clean_text for k in ["verify bundle", "verify now", "jaanch karein", "jaanch shuru"]):
        await handle_verify_request(update, context)
        return
    if any(k in clean_text for k in ["add more", "upload more", "add next", "aur dastavej", "agla dastavej"]):
        await update.message.reply_text("📄 Please send the photo or file of the next document.")
        return
    if any(k in clean_text for k in ["start over", "new verification", "nayi jaanch"]):
        await start_command(update, context)
        return
    if any(k in clean_text for k in ["check scheme", "yojana jaanch", "scheme"]):
        await scheme_command(update, context)
        return
    if any(k in clean_text for k in ["digital profile", "view profile", "profile"]):
        await profile_command(update, context)
        return

    # Send typing feedback
    try:
        await update.message.chat.send_action("typing")
    except Exception:
        pass

    chat_history = context.user_data.setdefault("chat_history", [])
    session_context = {
        "doc_paths": context.user_data.get("doc_paths", []),
        "extracted_docs": context.user_data.get("extracted_docs", []),
        "last_result": context.user_data.get("last_result", {}),
        "quality_warnings": context.user_data.get("quality_warnings", []),
        "history": chat_history,
    }

    try:
        reply = await ask_sarthi_assistant(text, session_context, history=chat_history)
        chat_history.append({"role": "user", "content": text})
        chat_history.append({"role": "assistant", "content": reply})
        if len(chat_history) > 12:
            context.user_data["chat_history"] = chat_history[-12:]
        await _safe_reply(update, reply)
    except Exception as e:
        logger.error(f"Error handling chat message: {e}", exc_info=True)
        await _safe_reply(update, "Kripya apna sawal dobara poochein ya `/help` dekhein.")

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

    # Direct Unconditional Handlers (Never drops media uploads or button clicks)
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("demo", demo_command))
    app.add_handler(CommandHandler("scheme", scheme_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("clear", cancel_command))
    app.add_handler(CommandHandler("done", handle_verify_request))
    app.add_handler(CommandHandler("verify", handle_verify_request))

    # Media uploads (Photos, Scanned PDFs, Documents) - active at all times
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_document_upload))

    # Verification triggers & button clicks
    app.add_handler(MessageHandler(filters.Regex(r"(?i)(verify|jaanch)"), handle_verify_request))

    # Conversational LLM queries (Groq AI)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat_message))

    print("✅ Bot is online and directly connected to backend engine!")
    app.run_polling()

if __name__ == "__main__":
    main()
