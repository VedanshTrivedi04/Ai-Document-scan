"""
explainer.py: Formats multi-document bundle contradiction data into clear, empathetic advice.
Features:
1. Citizen Report with resolution guidance and official precedence (UIDAI, Tehsildar, Gazette).
2. Scheme Pre-Check (/scheme) for PM Awas, PM Kisan, Post-Matric Scholarship, and Ayushman Bharat.
3. Verified Golden Profile summary (/profile).
"""

from typing import Dict, Any, List, Optional


def calculate_risk_assessment(
    conflicts: List[Dict[str, Any]],
    harmless_variants: List[Dict[str, Any]],
    quality_warnings: Optional[List[str]] = None,
    backend_score: Optional[int] = None,
    backend_tier: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Computes an audit-grade risk score (0 - 100) and risk tier matching the DocSure platform.
    """
    if backend_score is not None and backend_tier:
        tier_str = str(backend_tier).upper()
        tier_label = "🔴 HIGH RISK" if tier_str == "HIGH" else ("🟡 MEDIUM RISK" if tier_str == "MEDIUM" else "🟢 LOW RISK")
        verdict = (
            "Action Required (High Rejection Probability)" if tier_str == "HIGH"
            else ("Review Advised (Minor Discrepancies)" if tier_str == "MEDIUM" else "Clean Match (Safe to Proceed)")
        )
        return {
            "score": backend_score,
            "tier": tier_str,
            "tier_label": tier_label,
            "verdict": verdict,
        }

    score = 0
    reasons = []

    for c in conflicts:
        sev = str(c.get("severity", "HIGH")).upper()
        if sev in ("CRITICAL", "VERY HIGH"):
            score += 45
            reasons.append(f"Critical conflict: {c.get('field', 'Field')}")
        elif sev == "HIGH":
            score += 35
            reasons.append(f"High severity conflict: {c.get('field', 'Field')}")
        elif sev == "MEDIUM":
            score += 20
            reasons.append(f"Medium discrepancy: {c.get('field', 'Field')}")
        else:
            score += 10
            reasons.append(f"Discrepancy: {c.get('field', 'Field')}")

    for _ in harmless_variants:
        score += 5

    if quality_warnings:
        score += min(len(quality_warnings) * 10, 20)

    score = min(max(score, 0), 100)

    if score >= 70 or any(str(c.get("severity", "")).upper() in ("CRITICAL", "HIGH") for c in conflicts):
        tier = "HIGH"
        tier_label = "🔴 HIGH RISK"
        verdict = "Action Required (High Rejection Probability)"
    elif score >= 25 or any(str(c.get("severity", "")).upper() == "MEDIUM" for c in conflicts):
        tier = "MEDIUM"
        tier_label = "🟡 MEDIUM RISK"
        verdict = "Review Advised (Minor Discrepancies)"
    else:
        tier = "LOW"
        tier_label = "🟢 LOW RISK"
        verdict = "Clean Match (Safe to Proceed)"

    return {
        "score": score,
        "tier": tier,
        "tier_label": tier_label,
        "verdict": verdict,
        "reasons": reasons,
    }


def format_citizen_report(data: Dict[str, Any], lang: str = "hi") -> str:
    """
    Takes verification result dictionary for a document bundle (up to 5 documents)
    and formats it into an easy-to-read, structured Telegram report with Risk Score and Severity badges.
    """
    total_docs = data.get("total_documents_scanned", 2)
    scanned_docs = data.get("scanned_documents", [])
    matches = data.get("matches", [])
    harmless_variants = data.get("harmless_variants", [])
    conflicts = data.get("conflicts", [])

    case_num = data.get("case_number")
    risk_info = data.get("risk_assessment")
    if not risk_info:
        raw_c = data.get("raw_case") or {}
        b_score = raw_c.get("risk_score")
        b_tier = raw_c.get("risk_tier")
        risk_info = calculate_risk_assessment(conflicts, harmless_variants, data.get("quality_warnings"), b_score, b_tier)
        data["risk_assessment"] = risk_info

    score = risk_info.get("score", 0)
    tier_label = risk_info.get("tier_label", "🟢 LOW RISK")
    verdict = risk_info.get("verdict", "Safe to Proceed")

    lines = [
        "══════════════════════════",
        "🇮🇳 *SARTHI CITIZEN ASSISTANT*",
        f"📋 *Bundle Verification Report ({total_docs} Documents)*",
        "══════════════════════════\n"
    ]
    if case_num:
        lines.append(f"📌 *DocSure Case Reference:* `{case_num}`")

    lines.append(f"🎯 *Risk Assessment:*")
    lines.append(f"  • *Risk Score:* `{score}/100`  |  *Tier:* *{tier_label}*")
    lines.append(f"  • *Status:* _{verdict}_\n")

    # Scanned documents overview
    if scanned_docs:
        lines.append("📑 *Scanned Documents:*")
        for doc in scanned_docs:
            lines.append(f"  • {doc}")
        lines.append("")

    # Critical Conflicts
    if conflicts:
        lines.append("🚨 *CRITICAL CONFLICTS DETECTED:*")
        lines.append("_These discrepancies can cause welfare scheme applications to be rejected:_\n")

        for idx, conf in enumerate(conflicts, start=1):
            field = conf.get("field", "Field")
            d1_name = conf.get("doc1_name", "Document 1")
            val1 = conf.get("doc1_value", "N/A")
            d2_name = conf.get("doc2_name", "Document 2")
            val2 = conf.get("doc2_value", "N/A")
            severity_str = str(conf.get("severity", "HIGH")).upper()
            msg = conf.get("message", "Contradiction detected")
            reason = conf.get("reason", "")

            # Visual Severity Badge
            if severity_str in ("CRITICAL", "VERY HIGH"):
                sev_badge = "🔴 CRITICAL"
            elif severity_str == "HIGH":
                sev_badge = "🟠 HIGH"
            elif severity_str == "MEDIUM":
                sev_badge = "🟡 MEDIUM"
            else:
                sev_badge = "🟢 LOW"

            lines.append(f"*{idx}. {field}* [Severity: *{sev_badge}*]")
            lines.append(f"  • *{d1_name}:* `{val1}`")
            lines.append(f"  • *{d2_name}:* `{val2}`")
            lines.append(f"  • *Reason:* _{msg}_")

            # Official Resolution Precedence Advice
            advice = _get_resolution_precedence(field, reason, d1_name, d2_name)
            if advice:
                lines.append(f"  • 🛠️ *Remedy:* {advice}")
            lines.append("")

    # Harmless Variants
    if harmless_variants:
        lines.append("ℹ️ *HARMLESS VARIANTS (Safe Minor Differences):*")
        lines.append("_Identified as harmless by AI rules (Application will not be rejected):_\n")

        for h in harmless_variants:
            field = h.get("field", "Field")
            d1_name = h.get("doc1_name", "Document 1")
            val1 = h.get("doc1_value", "")
            d2_name = h.get("doc2_name", "Document 2")
            val2 = h.get("doc2_value", "")
            msg = h.get("message") or h.get("reason", "Spelling ya format difference")

            lines.append(f"  • *{field}* [Severity: *🟢 LOW (Safe)*]")
            if val1 and val2:
                lines.append(f"    ↳ `{val1}` ({d1_name}) vs `{val2}` ({d2_name})")
            lines.append(f"    ↳ _{msg}_\n")

    # Clean Matches
    if matches:
        lines.append("✅ *EXACT MATCHES:* [Severity: *🟢 SAFE*]")
        for m in matches:
            lines.append(f"  • {m}")
        lines.append("")

    # Actionable Guidance
    lines.append("──────────────────────────")
    if conflicts:
        lines.append("💡 *ACTION ADVICE:*")
        lines.append("1. Do NOT submit application forms with conflicting details.")
        lines.append("2. Follow the recommended remedy above to update documents at UIDAI / Tehsildar / CSC center.")
        lines.append("3. Once corrected, re-verify and proceed with your application.")
    else:
        lines.append("🎉 *ALL CLEAR - MATCH CONFIRMED!*")
        lines.append("All documents in your bundle match consistently. You can safely proceed with your application!")

    lines.append("──────────────────────────")
    lines.append("👉 *Check scheme eligibility:* `/scheme`")
    lines.append("👉 *View verified digital profile:* `/profile`")
    lines.append("🔄 *Start a new verification:* `/start`")

    return "\n".join(lines)


def _get_resolution_precedence(field: str, reason: str, d1: str, d2: str) -> str:
    """Provides legal/administrative precedence guidance under Indian government rules."""
    f = field.lower()
    r = reason.lower()

    if "date" in f or "dob" in f or "year" in r:
        return "Janam Praman Patra (Birth Certificate) ya 10th Class Marksheet ko UIDAI se prathmikta di jaati hai. Aadhaar Kendra par jakar Date of Birth update karwayein."
    if "income" in f:
        return "Aay Praman Patra (Income Certificate) sirf 1 se 3 saal ke liye valid hota hai. Tehsildar / Revenue Department se taza aay praman patra banwayein."
    if "name" in f and "different" in r:
        return "Dono dastavej alag-alag vyakti ke lag rahe hain. Kripya sunishchit karein ki dono dastavej ek hi aavedak ke hon."
    if "name" in f:
        return "Naam me chhota antar Gazette Notification ya SDM / Notary dwara Affidavit (Shapath Patra) banwakar theek kiya ja sakta hai."
    if "address" in f:
        return "Pate (Address) me antar hone par UIDAI Portal (myaadhaar.uidai.gov.in) par jakar naya valid Address Proof (jaise Bijli Bill ya Voter ID) upload karke pata update karwayein."
    if "gender" in f:
        return "Gender mismatch ko nazdeeki Aadhaar / PAN kendra par jakar turant update karwayein."
    return "Sambandhit vibhag (CSC / Tehsildar karyalay) me jakar dastavej sudhar karwayein."


def format_scheme_eligibility(result_data: Dict[str, Any], documents: List[Any]) -> str:
    """Evaluates bundle readiness for popular Indian welfare schemes."""
    conflicts = result_data.get("conflicts", [])
    has_conflicts = len(conflicts) > 0

    # Extract available fields
    doc_types = [d.document_type for d in documents] if documents else []
    income_val = None
    has_aadhaar = any("national" in dt or "aadhaar" in dt for dt in doc_types)
    has_pan = any("tax" in dt or "pan" in dt for dt in doc_types)
    has_income = any("income" in dt for dt in doc_types)

    for d in documents:
        if getattr(d, "identity_fields", None):
            inc = d.identity_fields.get("annual_income", {}).get("value")
            if inc is not None:
                income_val = float(inc)

    lines = [
        "══════════════════════════",
        "🏛️ *SARKARI YOJANA ELIGIBILITY CHECK*",
        "══════════════════════════\n",
    ]

    if has_conflicts:
        lines.append("⚠️ *Chetawani:* Bundle me conflicts maujood hain. Kisi bhi yojana me form reject ho sakta hai.\n")

    # 1. PM Awas Yojana (PMAY)
    lines.append("🏠 *1. Pradhan Mantri Awas Yojana (PMAY)*")
    if not has_income:
        lines.append("  • ⚠️ *Income Certificate:* Zaroori hai par bundle me nahi mila.")
    elif income_val and income_val <= 300000:
        lines.append(f"  • ✅ *Aay Shreni:* EWS (Rs. {income_val:,.0f}/saal) - Subsidy Hetu Yogya!")
    elif income_val and income_val <= 600000:
        lines.append(f"  • ✅ *Aay Shreni:* LIG (Rs. {income_val:,.0f}/saal) - Yogya!")
    else:
        lines.append("  • ℹ️ Aay सीमा 3 se 6 lakh se adhik hone par subsidy kam mil sakti hai.")
    lines.append("  • " + ("❌ *Status:* Conflicts ke karan pending" if has_conflicts else "✅ *Status:* Documents Ready"))
    lines.append("")

    # 2. PM Kisan Samman Nidhi
    lines.append("🌾 *2. PM-KISAN Samman Nidhi*")
    lines.append("  • Aadhaar Name Match: " + ("❌ Mismatch" if any("name" in c.get("field", "").lower() for c in conflicts) else "✅ Sahi Match"))
    lines.append("  • Bank-Aadhaar Seeding: Zaroori")
    lines.append("  • " + ("❌ *Status:* Name/DOB Conflict" if has_conflicts else "✅ *Status:* Eligible"))
    lines.append("")

    # 3. Post-Matric Scholarship
    lines.append("🎓 *3. Post-Matric Scholarship (SC/ST/OBC/Minority)*")
    if income_val and income_val <= 250000:
        lines.append(f"  • ✅ *Aay Shart:* Rs. {income_val:,.0f} (<= 2.5 Lakh) - Yogya!")
    elif income_val:
        lines.append(f"  • ⚠️ *Aay Shart:* Rs. {income_val:,.0f} (2.5 Lakh se adhik hone par scholarship me samasya ho sakti hai)")
    else:
        lines.append("  • ℹ️ Aay praman patra (Income Certificate) add karein.")
    lines.append("  • " + ("❌ *Status:* Conflict Resolution Required" if has_conflicts else "✅ *Status:* Eligible"))
    lines.append("")

    # 4. Ayushman Bharat (PM-JAY)
    lines.append("🏥 *4. Ayushman Bharat (5 Lakh Health Card)*")
    lines.append("  • Aadhaar Card: " + ("✅ Verified" if has_aadhaar else "⚠️ Missing"))
    lines.append("  • Ration Card / SECC Data milan aavashyak hai.")
    lines.append("")

    lines.append("──────────────────────────")
    lines.append("💡 *Tip:* Form bharne se pehle sabhi dastavej sudharwayein taaki labh turant mile.")

    return "\n".join(lines)


def format_verified_profile(documents: List[Any]) -> str:
    """Builds a consolidated golden profile from verified bundle documents."""
    if not documents:
        return "⚠️ Koi dastavej upload nahi hua hai. Pehle `/start` karke documents bhejiye."

    name = "N/A"
    dob = "N/A"
    parent = "N/A"
    gender = "N/A"
    address = "N/A"
    id_cards = []

    for d in documents:
        f = getattr(d, "identity_fields", {}) or {}
        if name == "N/A" and f.get("full_name", {}).get("value"):
            name = f["full_name"]["value"]
        if dob == "N/A" and (f.get("date_of_birth", {}).get("raw_text") or f.get("date_of_birth", {}).get("value")):
            dob = f["date_of_birth"].get("raw_text") or f["date_of_birth"].get("value")
        if parent == "N/A" and f.get("parent_or_spouse_name", {}).get("value"):
            parent = f["parent_or_spouse_name"]["value"]
        if gender == "N/A" and (f.get("gender", {}).get("raw_text") or f.get("gender", {}).get("value")):
            gender = f["gender"].get("raw_text") or f["gender"].get("value")
        if address == "N/A" and f.get("address", {}).get("value"):
            address = f["address"]["value"]

        doc_type = getattr(d, "document_type", "doc")
        id_num = f.get("id_number", {}).get("value")
        if id_num:
            id_cards.append(f"  • *{doc_type.replace('_', ' ').title()}:* `{id_num}`")

    lines = [
        "══════════════════════════",
        "🎖️ *SARTHI VERIFIED CITIZEN PROFILE*",
        "══════════════════════════",
        "_Aapke satyapit dastavejon ka canonical profile:_\n",
        f"👤 *Pura Naam:* `{name}`",
        f"📅 *Janam Tithi (DOB):* `{dob}`",
        f"👪 *Pita / Pati:* `{parent}`",
        f"⚧ *Ling (Gender):* `{gender}`",
        f"📍 *Pata (Address):* `{address}`\n",
        "🪪 *ID Praman Patra:*",
    ]
    if id_cards:
        lines.extend(id_cards)
    else:
        lines.append("  • Koi specific ID number uplabdh nahi.")

    lines.append("\n──────────────────────────")
    lines.append("💡 *Tip:* Aap in verified details ka prayog kisi bhi sarkari form me bina sankoch ke kar sakte hain.")

    return "\n".join(lines)
