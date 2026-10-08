"""
explainer.py: Formats multi-document bundle contradiction data into clear, empathetic advice.
"""

from typing import Dict, Any

def format_citizen_report(data: Dict[str, Any]) -> str:
    """
    Takes verification result dictionary for a document bundle (up to 5 documents)
    and formats it into an easy-to-read, structured Telegram report.
    """
    total_docs = data.get("total_documents_scanned", 2)
    scanned_docs = data.get("scanned_documents", [])
    matches = data.get("matches", [])
    harmless_variants = data.get("harmless_variants", [])
    conflicts = data.get("conflicts", [])

    lines = [
        "══════════════════════════",
        "🇮🇳 *SARTHI PUBLIC ASSISTANT*",
        f"📋 *Bundle Jaanch Report ({total_docs} Dastavej Scan Kiye Gaye)*",
        "══════════════════════════\n"
    ]

    # Scanned documents overview
    if scanned_docs:
        lines.append("📑 *Scan Kiye Gaye Dastavej:*")
        for doc in scanned_docs:
            lines.append(f"  • {doc}")
        lines.append("")

    # Critical Conflicts
    if conflicts:
        lines.append("🚨 *KHATRA: Critical Conflicts Mile Hain!*")
        lines.append("_Neeche diye gaye bado antar ki wajah se application reject ho sakti hai:_\n")
        
        for idx, conf in enumerate(conflicts, start=1):
            field = conf.get("field", "Field")
            d1_name = conf.get("doc1_name", "Document 1")
            val1 = conf.get("doc1_value", "N/A")
            d2_name = conf.get("doc2_name", "Document 2")
            val2 = conf.get("doc2_value", "N/A")
            severity = conf.get("severity", "HIGH")
            msg = conf.get("message", "Contradiction detected")
            
            lines.append(f"*{idx}. {field}* [Severity: *{severity}*]")
            lines.append(f"  • *{d1_name}:* `{val1}`")
            lines.append(f"  • *{d2_name}:* `{val2}`")
            lines.append(f"  • *Karan:* _{msg}_\n")

    # Harmless Variants
    if harmless_variants:
        lines.append("ℹ️ *HARMLESS VARIANTS (Chhoti Galtiyan - Safe):*")
        lines.append("_Inhe AI ne harmless maan kar pass kar diya hai:_\n")
        
        for h in harmless_variants:
            field = h.get("field", "Field")
            doc1 = h.get("doc1", "")
            doc2 = h.get("doc2", "")
            reason = h.get("reason", "Minor variation")
            lines.append(f"  • *{field}:*")
            lines.append(f"    ↳ `{doc1}` vs `{doc2}`")
            lines.append(f"    ↳ _{reason}_\n")

    # Clean Matches
    if matches:
        lines.append("✅ *BILKUL SAHI MILAN (Exact Matches):*")
        for m in matches:
            lines.append(f"  • {m}")
        lines.append("")

    # Actionable Guidance
    lines.append("──────────────────────────")
    if conflicts:
        lines.append("💡 *AGLA KADAM (Action Advice):*")
        lines.append("1. Kripya application form abhi submit *NA* karein.")
        lines.append("2. Pehle apne Block / Tehsildar office se conflicting certificate (DOB / Income) ko correct karwayein.")
        lines.append("3. Correction ke baad naye document ke sath aavedan karein.")
    else:
        lines.append("🎉 *SAB KUCH SAHI HAI!*")
        lines.append("Aapke bundle ke saare dastavej aapas me match ho rahe hain. Aap apna aavedan bina kisi sankoch ke submit kar sakte hain!")

    lines.append("──────────────────────────")
    lines.append("🔄 _Naya bundle check karne ke liye type kijiye: /start_")

    return "\n".join(lines)
