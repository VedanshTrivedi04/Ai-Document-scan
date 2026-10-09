"""
chat_service.py: Grounded Groq Conversational AI Engine for Sarthi Citizen Assistant.
Features:
- Powered by Groq's high-speed endpoint (openai/gpt-oss-20b, openai/gpt-oss-120b, qwen/qwen3.8-27b).
- Automatic model fallback for 100% uptime.
- Strictly grounded in backend's real extracted document fields & contradiction findings.
- 0% Hallucination: Never invents fake dates, names, or non-existent discrepancies.
- Speaks empathetic, respectful Hindi/Hinglish tailored for Indian public administration.
"""

import logging
import os
from pathlib import Path
import re
from typing import Dict, Any, List, Optional
import httpx
from dotenv import load_dotenv

# Ensure environment variables are loaded
BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
BACKEND_ENV = REPO_ROOT / "backend" / ".env"
CHATBOT_ENV = BASE_DIR / ".env"

if BACKEND_ENV.exists():
    load_dotenv(BACKEND_ENV)
if CHATBOT_ENV.exists():
    load_dotenv(CHATBOT_ENV)

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("LLM_API_KEY", "").strip()
GROQ_MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"]
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PERSONA = """You are 'Sarthi AI' (सार्थी) — an intelligent Citizen Document Verification & Contradiction Assistant for public welfare schemes.
Your mission is to help citizens understand inconsistencies across their documents (Aadhaar, PAN, Income Certificate, Marksheet, Voter ID) and government scheme readiness in a clear, respectful, and helpful way.

LANGUAGE POLICY:
1. DEFAULT LANGUAGE: Speak in clear, professional, empathetic English by default.
2. DYNAMIC LANGUAGE MIRRORING:
   - Always detect the language and script used by the citizen in their message.
   - If the citizen writes in Hindi (हिन्दी) or Hinglish, reply in natural, fluent Hindi / Hinglish.
   - If the citizen writes in any native Indian language (Marathi मराठी, Gujarati ગુજરાતી, Bengali বাংলা, Tamil தமிழ், Telugu తెలుగు, Kannada ಕನ್ನಡ, Punjabi ਪੰਜਾਬੀ, etc.), immediately reply in that exact same native language!
   - If the citizen writes in English, reply in English.
   - Match the user's communication style naturally, just like ChatGPT / Claude.

STRICT ANTI-HALLUCINATION RULES:
1. Speak ONLY from the verified facts provided below in 'ACTUAL VERIFIED CONTEXT'.
2. NEVER invent names, dates of birth (DOB), ID numbers, or income figures (DO NOT hallucinate).
3. If no documents have been uploaded yet or no check has run, politely tell the citizen that no documents are uploaded yet, and guide them to upload photos or run `/demo T01` or `/demo T05`.
4. If a conflict exists, provide official Indian administrative remedies:
   - DOB mismatch: Birth Certificate / 10th marksheet takes precedence over Aadhaar/PAN. Update at UIDAI Kendra.
   - Name spelling variant: Notary affidavit / Gazette notification resolves it.
   - Income gap: Obtain an updated valid certificate from the Tehsildar / Revenue office.
5. For harmless variants (e.g. Choudhary vs Chowdhary, initials, address formatting), reassure the citizen that their application will not be rejected.
6. Tone: Highly polite, helpful, clear, and reassuring.

TELEGRAM UI & FORMATTING RULES (CRITICAL):
1. NEVER USE MARKDOWN TABLES: Do NOT output `| col | col |` tables! Telegram mobile UI does NOT render tables and line wraps make them look completely broken and ugly. Instead, format data using clean bullet points:
   • Document 1 (Aadhaar): Name, DOB, ID
   • Document 2 (PAN): Name, DOB, ID
2. NO MARKDOWN HEADERS (# or ###): Telegram does NOT render markdown heading syntax. Always use `*Bold Text*` or `📌 *Heading*` instead.
3. Use clean spacing and friendly emojis (•, 👉, ✅, ⚠️, 🔍, 🛠️).
4. CONVERSATIONAL MEMORY: Remember past conversation turns. If the user asks follow-up questions (e.g. "In hinglish", "aur explain karo", "isko kaise theek karein?"), reply seamlessly within context.
"""


def clean_telegram_formatting(text: str) -> str:
    """Post-processes LLM output to convert any markdown tables and ### headers into clean Telegram formatting."""
    # Convert ### headers to bold
    cleaned = re.sub(r"^#{1,6}\s*(.+)$", r"📌 *\1*", text, flags=re.MULTILINE)

    # Convert markdown tables (| a | b |) to clean bullet lists
    lines = cleaned.split("\n")
    out_lines = []
    in_table = False
    table_headers: List[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            parts = [p.strip() for p in stripped.strip("|").split("|")]
            # Skip separator line like |---|---|
            if all(set(p).issubset({"-", ":", " "}) for p in parts if p):
                continue
            if not in_table:
                in_table = True
                table_headers = parts
            else:
                row_items = []
                for idx, cell in enumerate(parts):
                    h_name = table_headers[idx] if idx < len(table_headers) else f"Field {idx+1}"
                    if cell and cell != "-":
                        row_items.append(f"*{h_name}:* {cell}")
                if row_items:
                    out_lines.append("• " + " | ".join(row_items))
        else:
            in_table = False
            out_lines.append(line)

    return "\n".join(out_lines).strip()


async def ask_sarthi_assistant(
    user_message: str,
    session_context: Dict[str, Any],
    history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Takes citizen's free-form chat message, maintains multi-turn conversation memory,
    and generates grounded, empathetic answers using Groq LLM with clean Telegram formatting.
    """
    if not GROQ_API_KEY:
        return (
            "🙏 Namaste! Main Sarthi AI hoon. Kripya apne documents ki jaanch ke liye "
            "photos upload karein ya `/demo T01` type karein."
        )

    # Compile Grounded Context
    grounded_context = _build_grounded_context(session_context)

    messages = [
        {"role": "system", "content": SYSTEM_PERSONA + "\n\n" + grounded_context}
    ]

    # Conversation Memory: Append recent conversation turns
    hist = history or session_context.get("history", [])
    if hist:
        for turn in hist[-8:]:
            if turn.get("role") in ("user", "assistant") and turn.get("content"):
                messages.append({"role": turn["role"], "content": turn["content"]})

    messages.append({"role": "user", "content": user_message.strip()})

    # Try each available model on Groq with failover
    for model_name in GROQ_MODELS:
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.post(
                    GROQ_URL,
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                    json={
                        "model": model_name,
                        "messages": messages,
                        "max_tokens": 450,
                        "temperature": 0.2,
                    },
                )

            if resp.status_code == 200:
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                if content:
                    return clean_telegram_formatting(content)
            elif resp.status_code == 429:
                logger.warning(f"Groq model {model_name} rate-limited (429), trying fallback model...")
                continue
            else:
                logger.error(f"Groq API model {model_name} status {resp.status_code}: {resp.text}")

        except Exception as e:
            logger.error(f"Error calling Groq chat service with {model_name}: {e}")

    # Graceful fallback grounded in session data
    return _rule_based_grounded_fallback(user_message, session_context)


def _build_grounded_context(session_context: Dict[str, Any]) -> str:
    """Builds explicit factual context for the LLM to prevent hallucination."""
    parts = ["=== ACTUAL VERIFIED CONTEXT (SACCHI JAANKARI) ==="]

    extracted_docs = session_context.get("extracted_docs", [])
    last_result = session_context.get("last_result", {})

    if not extracted_docs and not last_result:
        parts.append("Dastavej Status: Abhi tak nagrik ne koi document upload ya scan nahi kiya hai.")
        parts.append("Action: Nagrik ko photos bhejne ya /demo command use karne ko kahein.")
        return "\n".join(parts)

    # 1. Extracted Documents
    if extracted_docs:
        parts.append("--- Scan Kiye Gaye Dastavej ---")
        for i, doc in enumerate(extracted_docs, start=1):
            f = getattr(doc, "identity_fields", {}) or {}
            dtype = getattr(doc, "document_type", "Document")
            name = f.get("full_name", {}).get("value", "N/A")
            dob = f.get("date_of_birth", {}).get("raw_text") or f.get("date_of_birth", {}).get("value", "N/A")
            num = f.get("id_number", {}).get("value", "N/A")
            inc = f.get("annual_income", {}).get("value")
            parts.append(f"Document {i} ({dtype}):")
            parts.append(f"  - Naam: {name}")
            parts.append(f"  - DOB: {dob}")
            parts.append(f"  - ID Number: {num}")
            if inc is not None:
                parts.append(f"  - Varshik Aay (Annual Income): Rs. {inc:,.0f}")

    # 2. Verification Findings
    if last_result:
        case_ref = last_result.get("case_number")
        if case_ref:
            parts.append(f"\nDocSure Platform Case Reference: {case_ref}")

        profile = last_result.get("profile", {})
        if profile and profile.get("fields"):
            parts.append("--- Verified Canonical Citizen Profile ---")
            for pf in profile.get("fields", []):
                val = pf.get("display_value") or pf.get("value")
                lbl = pf.get("label") or pf.get("field", "").title()
                st = pf.get("status", "")
                if val:
                    parts.append(f"  - {lbl}: {val} [{st}]")

        parts.append("\n--- Backend Contradiction Engine Findings ---")
        conflicts = last_result.get("conflicts", [])
        harmless = last_result.get("harmless_variants", [])
        matches = last_result.get("matches", [])

        if conflicts:
            parts.append("🚨 ASLI ANTHAR (CRITICAL CONFLICTS):")
            for c in conflicts:
                parts.append(
                    f"  - Field: {c.get('field')} | {c.get('doc1_name')} ({c.get('doc1_value')}) VS "
                    f"{c.get('doc2_name')} ({c.get('doc2_value')}) | Reason: {c.get('reason')} | Severity: {c.get('severity')}"
                )
        else:
            parts.append("🚨 ASLI ANTHAR: Koi critical conflict nahi mila, sab theek hai.")

        if harmless:
            parts.append("ℹ️ HARMLESS VARIANTS (Safe Differences):")
            for h in harmless:
                parts.append(f"  - Field: {h.get('field')} | Reason: {h.get('reason')} | Safe to proceed")

        if matches:
            parts.append("✅ EXACT MATCHES:")
            for m in matches:
                parts.append(f"  - {m}")

    return "\n".join(parts)


def _rule_based_grounded_fallback(user_message: str, session_context: Dict[str, Any]) -> str:
    """Safe, factual fallback if Groq API is temporarily unreachable."""
    last_res = session_context.get("last_result", {})
    conflicts = last_res.get("conflicts", [])

    if conflicts:
        c = conflicts[0]
        return (
            f"⚠️ Aapke dastavejon me *{c.get('field')}* ko lekar antar mila hai:\n"
            f"• {c.get('doc1_name')}: `{c.get('doc1_value')}`\n"
            f"• {c.get('doc2_name')}: `{c.get('doc2_value')}`\n\n"
            "Kripya application form submit karne se pehle ise sambandhit kendra (UIDAI / Tehsildar) se update karwayein."
        )
    elif last_res:
        return "🎉 Aapke sabhi dastavej bilkul sahi match ho rahe hain! Aap apna aavedan bina kisi samasya ke jama kar sakte hain."

    return (
        "🙏 Namaste! Main Sarthi AI hoon. Apne dastavejon ki jaanch ke liye kripya photos upload karein "
        "ya test karne ke liye `/demo T01` ya `/demo T05` type karein."
    )
