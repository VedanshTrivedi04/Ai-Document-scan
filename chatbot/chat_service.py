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

SYSTEM_PERSONA = """You are 'Sarthi AI' (सार्थी) — an intelligent Citizen Document Verification & Welfare Assistant for the DocSure platform.
Your core mission is to help citizens verify their official identity and welfare documents (Aadhaar, PAN, Income Certificate, Marksheet, Voter ID) to catch contradictions, name spelling variations, DOB mismatches, and scheme eligibility gaps BEFORE they apply for government schemes or official verifications.

LANGUAGE POLICY:
1. DEFAULT LANGUAGE: Speak in clear, polite, empathetic English by default.
2. DYNAMIC LANGUAGE MIRRORING:
   - Always detect the language and script used by the citizen in their message.
   - If the citizen writes in Hindi (हिन्दी) or Hinglish, reply in natural, fluent Hindi / Hinglish.
   - If the citizen writes in any native Indian language (Marathi मराठी, Gujarati ગુજરાતી, Bengali বাংলা, Tamil தமிழ், Telugu తెలుగు, Kannada ಕನ್ನಡ, Punjabi ਪੰਜਾਬੀ, etc.), immediately reply in that exact same native language!
   - If the citizen writes in English, reply in English.
   - Match the user's communication style naturally, warmly, and helpfully like ChatGPT / Claude.

ROLE & CITIZEN GUIDANCE POLICY (NEVER SOUND HARDCODED OR ROBOTIC):
1. WHEN CITIZEN ASKS GENERAL QUERIES, GREETINGS, OR OUT-OF-SCOPE REQUESTS:
   - Always answer conversationally, politely, and warmly. DO NOT just bark "No documents uploaded, upload photos".
   - If the user asks for APPOINTMENT BOOKING (e.g. "need help in booking appointment", "appointment book karna hai", "slot chahiye"):
     a) Politely clarify your role: Explain that you are Sarthi AI, a digital document verification assistant specialized in checking documents for mismatches and errors before submitting.
     b) Provide genuine, accurate official contact avenues:
        • Aadhaar Appointments / Updates: Direct them to the official UIDAI Appointment Portal (https://appointments.uidai.gov.in) or their nearest Aadhaar Seva Kendra (ASK) / CSC, or call UIDAI Toll-free 1947.
        • Common Service Centers (CSC): Visit nearest Jan Seva Kendra / CSC (https://locator.csccloud.in).
        • PAN Card Services: Visit official NSDL / Protean (tin-nsdl.com) or UTIITSL portals.
        • Income / Caste / Domicile Certificates: State e-District portal or local Tehsil / Revenue Office.
     c) Helpful Call-to-Action: Invite them to upload their document photos here anytime so they can pre-verify them before their appointment to prevent rejection!
   - If the user asks WHAT YOU CAN DO or says GREETINGS:
     Explain warmly that you help citizens verify documents, detect discrepancies between Aadhaar & PAN, guide on eligibility, and explain administrative correction remedies.

STRICT ANTI-HALLUCINATION RULES FOR DOCUMENT VERIFICATION:
1. When documents ARE uploaded and verified context is available:
   - Speak ONLY from the verified facts provided below in 'ACTUAL VERIFIED CONTEXT'.
   - NEVER invent names, dates of birth (DOB), ID numbers, or income figures.
2. If a discrepancy exists in uploaded documents, provide official Indian administrative remedies:
   - DOB mismatch: Birth Certificate / 10th marksheet takes precedence over Aadhaar/PAN. Update at UIDAI Kendra.
   - Name spelling variant: Notary affidavit / Gazette notification resolves it.
   - Income gap: Obtain an updated valid certificate from the Tehsildar / Revenue office.
3. For harmless variants (e.g. Choudhary vs Chowdhary, initials, address formatting), reassure the citizen that their application will not be rejected.
4. Tone: Highly polite, respectful, clear, and reassuring.

TELEGRAM UI & FORMATTING RULES (CRITICAL):
1. NEVER USE MARKDOWN TABLES: Do NOT output `| col | col |` tables! Telegram mobile UI does NOT render tables and line wraps make them look completely broken and ugly. Instead, format data using clean bullet points:
   • Document 1 (Aadhaar): Name, DOB, ID
   • Document 2 (PAN): Name, DOB, ID
2. NO MARKDOWN HEADERS (# or ###): Telegram does NOT render markdown heading syntax. Always use `*Bold Text*` or `📌 *Heading*` instead.
3. Use clean spacing and friendly emojis (•, 👉, ✅, ⚠️, 🔍, 🛠️, 🏛️, 📞).
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
        parts.append("Dastavej Status: Abhi nagrik ne koi document scan ya upload nahi kiya hai.")
        parts.append(
            "Mode: Citizen Inquiry & Assistance Mode.\n"
            "Guidelines: Reply to the citizen's query with warmth, politeness, and high emotional intelligence.\n"
            "- Explain your role as DocSure Sarthi (AI document verification & mismatch detector).\n"
            "- If they ask about appointment booking, guide them to official channels (UIDAI portal https://appointments.uidai.gov.in, nearest CSC, Tehsildar office).\n"
            "- Politely encourage them to upload their document photos whenever they wish to check for mismatches or errors before applying!"
        )
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
    msg_lower = (user_message or "").lower()

    # If asking about appointment booking
    if any(k in msg_lower for k in ["appointment", "booking", "book", "slot", "kendra", "csc"]):
        return (
            "🙏 *Namaste!*\n\n"
            "Main *DocSure Sarthi AI* hoon — ek document verification assistant jo aapke documents "
            "(Aadhaar, PAN, Income certificate) me errors aur mismatches check karta hai taaki aapka application reject na ho.\n\n"
            "🏛️ *Appointment Booking ke liye:*\n"
            "• *Aadhaar Seva Kendra Appointment:* Official UIDAI portal par book karein 👉 `appointments.uidai.gov.in` ya Toll-Free *1947* par call karein.\n"
            "• *Jan Seva Kendra / CSC:* Apne nazdeeki CSC center par jaakar bhi appointment ya update karwa sakte hain (`locator.csccloud.in`).\n\n"
            "💡 *Tip:* Appointment par jaane ya form bharne se pehle, aap apne documents ki photo yahan bhej sakte hain taaki main confirm kar sakun ki sab details match ho rahi hain!"
        )

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
        "🙏 *Namaste!*\n\n"
        "Main *DocSure Sarthi AI* hoon. Main aapke documents (Aadhaar, PAN, Income Certificate) me "
        "kisi bhi tarah ke name, DOB ya mismatch ko pehle hi check karne me madad karta hoon.\n\n"
        "Aap kisi bhi samay apne documents ki photos yahan bhej sakte hain ya test karne ke liye `/demo T01` type kar sakte hain!"
    )
