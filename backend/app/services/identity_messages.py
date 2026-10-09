"""
What a reader sees for one finding of the identity contradiction check
(app/services/identity_comparison.py). Written for an applicant or a clerk,
not an engineer: documents are named by what they are ("income
certificate"), values are shown as a person would write them, and each
message says what differs, why it does or does not matter, and what to do.

One fixed template per reason, so the same kind of difference is always
described the same way. The templates are English; other languages come from
app/services/translation_service.py (a built-in Hindi catalog below, Google
Translation for the rest). Only the templates are translated: a person's
name, date or address is filled in afterwards and never leaves the server.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.services import translation_service

FIELD_LABELS = {
    "full_name": "Name",
    "parent_or_spouse_name": "Father's / husband's name",
    "date_of_birth": "Date of birth",
    "gender": "Gender",
    "address": "Address",
    "annual_income": "Annual income",
    "id_number": "Identity number",
    "photo": "Photograph",
}

DOCUMENT_LABELS = {
    "national_id_card": "identity card",
    "tax_id_card": "tax identity card",
    "voter_id_card": "voter identity card",
    "driving_licence": "driving licence",
    "passport": "passport",
    "birth_certificate": "birth certificate",
    "income_certificate": "income certificate",
    "address_proof": "address proof",
    "caste_certificate": "caste certificate",
    "domicile_certificate": "domicile certificate",
    "marksheet": "marksheet",
    "degree_certificate": "degree certificate",
    "experience_letter": "experience letter",
    "payslip": "payslip",
}
_UNKNOWN_DOCUMENT = "document"

SEVERITY_LABELS = {
    "critical": "Must be corrected",
    "high": "Serious mismatch",
    "medium": "Please check",
    "low": "Minor difference",
    "info": "No problem",
}

SUMMARY_CONFLICT = "{field} does not match: {a} on the {doc_a} and {b} on the {doc_b}."
SUMMARY_HARMLESS = "{field} is written differently: {a} on the {doc_a} and {b} on the {doc_b}."
# The photographs on two documents (app/services/face_service.py) have no text to quote.
SUMMARY_PHOTO_CONFLICT = "The photograph on the {doc_a} does not look like the photograph on the {doc_b}."
SUMMARY_PHOTO_UNCERTAIN = "The photograph on the {doc_a} could not be matched with the one on the {doc_b}."
SUMMARY_PHOTO_MATCH = "The photograph on the {doc_a} and the one on the {doc_b} show the same person."

HARMLESS_REASONS = {
    "spelling_variant": "Both spellings sound the same.",
    "initials": "One document uses initials for the same name.",
    "abbreviation": "One document uses a common short form of the same name.",
    "transliteration": "The documents are in different scripts and read the same.",
    "honorific_or_word_order": "Only the title or the order of the words differs.",
    "extra_middle_name": "One document leaves out a middle name.",
    "address_formatting": "Only the way the address is written differs.",
    "photo_match": "The faces look alike.",
}
_HARMLESS_FALLBACK = "The two mean the same."

CONFLICT_REASONS = {
    "different_name": "These read as two different names.",
    "possible_spelling_error": "One letter differs. This may be a spelling mistake or a different name.",
    "partial_name": "One document shows only part of the name.",
    "date_year_difference": "The years do not match.",
    "date_minor_difference": "Only one digit differs, which may be a typing mistake.",
    "date_day_month_swapped": "The day and the month appear to be swapped.",
    "date_difference": "The dates do not match.",
    "gender_difference": "The two documents state different genders.",
    "income_difference": "The two amounts do not match.",
    "address_locality_difference": "The locality, city or postal code does not match.",
    "address_difference": "The house or plot number does not match.",
    "id_number_difference": "The same kind of document shows two different numbers.",
    "unclear_reading": (
        "A value on one of the documents could not be read clearly, so this may be a misreading and not a real difference."
    ),
    "photo_different_person": "The two faces look like two different people.",
    "photo_uncertain": "The faces are not clearly the same. A small, blurred or older photograph can cause this.",
}
_CONFLICT_FALLBACK = "The two documents do not agree."
_INCOME_RATIO = "The higher amount is {ratio} times the lower one."
_YEARS_APART = "The years are {years} years apart."
_ONE_YEAR_APART = "The years are 1 year apart."

NO_ACTION = "No action is needed."
_SAME_PERSON = "Check that every document belongs to the same person, and upload the correct document."
_CORRECT_OTHER = "Check which document is correct and have the other one corrected."
_MOVED = (
    "If you have moved, upload a current address proof. Otherwise have the incorrect document corrected."
)
ACTIONS = {
    "different_name": _SAME_PERSON,
    "possible_spelling_error": _CORRECT_OTHER,
    "partial_name": "Upload a document that shows the full name.",
    "date_year_difference": _CORRECT_OTHER,
    "date_minor_difference": _CORRECT_OTHER,
    "date_day_month_swapped": _CORRECT_OTHER,
    "date_difference": _CORRECT_OTHER,
    "gender_difference": "Have the incorrect document corrected.",
    "income_difference": "Upload the most recent income certificate, or explain the difference.",
    "address_locality_difference": _MOVED,
    "address_difference": _MOVED,
    "id_number_difference": "Check that both documents belong to the same person.",
    "unclear_reading": "Check the original documents, or upload a clearer photo of the one that is hard to read.",
    "photo_different_person": _SAME_PERSON,
    "photo_uncertain": "Compare the two photographs yourself, or ask for a clearer, recent document.",
}
_ACTION_FALLBACK = _CORRECT_OTHER


def catalog_strings() -> list[str]:
    """Every English string a message can be built from."""
    strings = [
        *FIELD_LABELS.values(), *DOCUMENT_LABELS.values(), _UNKNOWN_DOCUMENT, *SEVERITY_LABELS.values(),
        SUMMARY_CONFLICT, SUMMARY_HARMLESS, SUMMARY_PHOTO_CONFLICT, SUMMARY_PHOTO_UNCERTAIN,
        SUMMARY_PHOTO_MATCH, *HARMLESS_REASONS.values(), _HARMLESS_FALLBACK,
        *CONFLICT_REASONS.values(), _CONFLICT_FALLBACK, _INCOME_RATIO, _YEARS_APART, _ONE_YEAR_APART,
        NO_ACTION, *ACTIONS.values(),
    ]
    return list(dict.fromkeys(strings))


_HINDI = {
    # fields
    "Name": "नाम",
    "Father's / husband's name": "पिता / पति का नाम",
    "Date of birth": "जन्म तिथि",
    "Gender": "लिंग",
    "Address": "पता",
    "Annual income": "वार्षिक आय",
    "Identity number": "पहचान संख्या",
    "Photograph": "फ़ोटो",
    # documents
    "identity card": "पहचान पत्र",
    "tax identity card": "कर पहचान पत्र",
    "voter identity card": "मतदाता पहचान पत्र",
    "driving licence": "ड्राइविंग लाइसेंस",
    "passport": "पासपोर्ट",
    "birth certificate": "जन्म प्रमाण पत्र",
    "income certificate": "आय प्रमाण पत्र",
    "address proof": "पते का प्रमाण",
    "caste certificate": "जाति प्रमाण पत्र",
    "domicile certificate": "निवास प्रमाण पत्र",
    "marksheet": "अंकसूची",
    "degree certificate": "डिग्री प्रमाण पत्र",
    "experience letter": "अनुभव पत्र",
    "payslip": "वेतन पर्ची",
    "document": "दस्तावेज़",
    # severity
    "Must be corrected": "सुधार ज़रूरी है",
    "Serious mismatch": "गंभीर अंतर",
    "Please check": "कृपया जाँच लें",
    "Minor difference": "मामूली अंतर",
    "No problem": "कोई समस्या नहीं",
    # summaries
    SUMMARY_CONFLICT: "{field} में अंतर है: {doc_a} पर {a} और {doc_b} पर {b}।",
    SUMMARY_HARMLESS: "{field} अलग तरीके से लिखा है: {doc_a} पर {a} और {doc_b} पर {b}।",
    SUMMARY_PHOTO_CONFLICT: "{doc_a} की फ़ोटो {doc_b} की फ़ोटो से मेल नहीं खाती।",
    SUMMARY_PHOTO_UNCERTAIN: "{doc_a} की फ़ोटो का {doc_b} की फ़ोटो से मिलान पक्का नहीं हो सका।",
    SUMMARY_PHOTO_MATCH: "{doc_a} और {doc_b} की फ़ोटो एक ही व्यक्ति की हैं।",
    "The faces look alike.": "दोनों चेहरे एक जैसे दिखते हैं।",
    "The two faces look like two different people.": "दोनों चेहरे दो अलग-अलग व्यक्तियों के लगते हैं।",
    "A value on one of the documents could not be read clearly, so this may be a misreading and not a real difference.":
        "एक दस्तावेज़ का कोई मान साफ़ पढ़ा नहीं जा सका, इसलिए यह पढ़ने की गलती हो सकती है, असली अंतर नहीं।",
    "Check the original documents, or upload a clearer photo of the one that is hard to read.":
        "मूल दस्तावेज़ देखें, या जो पढ़ने में कठिन है उसकी ज़्यादा साफ़ फ़ोटो अपलोड करें।",
    "The faces are not clearly the same. A small, blurred or older photograph can cause this.":
        "चेहरे साफ़ तौर पर एक जैसे नहीं हैं। छोटी, धुंधली या पुरानी फ़ोटो से ऐसा हो सकता है।",
    "Compare the two photographs yourself, or ask for a clearer, recent document.":
        "दोनों फ़ोटो खुद मिलाकर देखें, या ज़्यादा साफ़ और नया दस्तावेज़ माँगें।",
    # why it does not matter
    "Both spellings sound the same.": "दोनों वर्तनी का उच्चारण एक जैसा है।",
    "One document uses initials for the same name.": "एक दस्तावेज़ में उसी नाम के केवल शुरुआती अक्षर लिखे हैं।",
    "One document uses a common short form of the same name.": "एक दस्तावेज़ में उसी नाम का प्रचलित छोटा रूप लिखा है।",
    "The documents are in different scripts and read the same.": "दस्तावेज़ अलग-अलग लिपियों में हैं और पढ़ने में एक जैसे हैं।",
    "Only the title or the order of the words differs.": "केवल उपाधि या शब्दों का क्रम अलग है।",
    "One document leaves out a middle name.": "एक दस्तावेज़ में बीच का नाम नहीं लिखा है।",
    "Only the way the address is written differs.": "केवल पता लिखने का तरीका अलग है।",
    "The two mean the same.": "दोनों का अर्थ एक ही है।",
    # why it matters
    "These read as two different names.": "ये दो अलग-अलग नाम लगते हैं।",
    "One letter differs. This may be a spelling mistake or a different name.":
        "एक अक्षर अलग है। यह वर्तनी की गलती भी हो सकती है और अलग नाम भी।",
    "One document shows only part of the name.": "एक दस्तावेज़ में नाम का केवल एक हिस्सा लिखा है।",
    "The years do not match.": "वर्ष मेल नहीं खाते।",
    "Only one digit differs, which may be a typing mistake.": "केवल एक अंक अलग है, यह टाइपिंग की गलती हो सकती है।",
    "The day and the month appear to be swapped.": "दिन और महीना आपस में बदले हुए लगते हैं।",
    "The dates do not match.": "तारीखें मेल नहीं खातीं।",
    "The two documents state different genders.": "दोनों दस्तावेज़ों में लिंग अलग लिखा है।",
    "The two amounts do not match.": "दोनों राशियाँ मेल नहीं खातीं।",
    "The locality, city or postal code does not match.": "मोहल्ला, शहर या पिन कोड मेल नहीं खाता।",
    "The house or plot number does not match.": "मकान या प्लॉट नंबर मेल नहीं खाता।",
    "The same kind of document shows two different numbers.": "एक ही तरह के दस्तावेज़ पर दो अलग नंबर हैं।",
    "The two documents do not agree.": "दोनों दस्तावेज़ आपस में मेल नहीं खाते।",
    _INCOME_RATIO: "बड़ी राशि छोटी राशि की {ratio} गुना है।",
    _YEARS_APART: "वर्षों में {years} साल का अंतर है।",
    _ONE_YEAR_APART: "वर्षों में 1 साल का अंतर है।",
    # what to do
    NO_ACTION: "कुछ करने की ज़रूरत नहीं है।",
    _SAME_PERSON: "जाँच लें कि सभी दस्तावेज़ एक ही व्यक्ति के हैं, और सही दस्तावेज़ अपलोड करें।",
    _CORRECT_OTHER: "देखें कि कौन-सा दस्तावेज़ सही है और दूसरे को ठीक करवाएँ।",
    "Upload a document that shows the full name.": "ऐसा दस्तावेज़ अपलोड करें जिसमें पूरा नाम लिखा हो।",
    "Have the incorrect document corrected.": "गलत दस्तावेज़ को ठीक करवाएँ।",
    "Upload the most recent income certificate, or explain the difference.":
        "सबसे नया आय प्रमाण पत्र अपलोड करें, या अंतर का कारण बताएँ।",
    _MOVED: "अगर आपका पता बदल गया है, तो नया पते का प्रमाण अपलोड करें। नहीं तो गलत दस्तावेज़ को ठीक करवाएँ।",
    "Check that both documents belong to the same person.": "जाँच लें कि दोनों दस्तावेज़ एक ही व्यक्ति के हैं।",
}
translation_service.BUILT_IN_CATALOGS.setdefault("hi", {}).update(_HINDI)


def warm_up(language: str) -> None:
    """Translate every message string in one request, so building the
    messages of a case never calls the translation service once per finding."""
    translation_service.translate(catalog_strings(), language)


def _format_date(value: Any) -> str | None:
    try:
        parsed = date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return f"{parsed.day} {parsed.strftime('%B %Y')}"


def display_value(field_name: str, field: dict[str, Any]) -> str:
    """One field's value as a person would write it."""
    value = field.get("value")
    if value in (None, ""):
        return ""
    if field_name == "date_of_birth":
        return _format_date(value) or str(field.get("raw_text") or value)
    if field_name == "annual_income":
        if field.get("raw_text"):
            return str(field["raw_text"])
        amount = f"{float(value):,.0f}"
        return f"{field['currency']} {amount}" if field.get("currency") else amount
    if field_name == "gender":
        return str(value).capitalize()
    return str(value)


def _templates(
    classification: str, reason: str, detail: dict[str, Any] | None, field_name: str = ""
) -> tuple[str, str, str, dict]:
    """(summary, explanation, action) templates and the numbers they quote."""
    numbers: dict[str, Any] = {}
    if field_name == "photo":
        summary = {
            "photo_match": SUMMARY_PHOTO_MATCH,
            "photo_uncertain": SUMMARY_PHOTO_UNCERTAIN,
        }.get(reason, SUMMARY_PHOTO_CONFLICT)
        if classification == "harmless_variant":
            return summary, HARMLESS_REASONS.get(reason, _HARMLESS_FALLBACK), NO_ACTION, numbers
        return summary, CONFLICT_REASONS.get(reason, _CONFLICT_FALLBACK), ACTIONS.get(reason, _ACTION_FALLBACK), numbers
    if classification == "harmless_variant":
        return SUMMARY_HARMLESS, HARMLESS_REASONS.get(reason, _HARMLESS_FALLBACK), NO_ACTION, numbers

    explanation = CONFLICT_REASONS.get(reason, _CONFLICT_FALLBACK)
    if reason == "income_difference" and detail and detail.get("ratio"):
        explanation, numbers = _INCOME_RATIO, {"ratio": f"{detail['ratio']:g}"}
    if reason == "date_year_difference" and detail and detail.get("years_apart"):
        years = detail["years_apart"]
        explanation, numbers = (_ONE_YEAR_APART, {}) if years == 1 else (_YEARS_APART, {"years": years})
    return SUMMARY_CONFLICT, explanation, ACTIONS.get(reason, _ACTION_FALLBACK), numbers


def build_message(
    field_name: str,
    classification: str,
    reason: str,
    severity: str,
    evidence: list[dict[str, Any]],
    detail: dict[str, Any] | None = None,
    language: str = "en",
) -> dict[str, str]:
    """The finding as text in `language`: what differs (`summary`), why it
    does or does not matter (`explanation`), what to do (`action`), all three
    together (`text`), and the labels to show beside them."""
    language = translation_service.normalize_language(language)
    first, second = evidence
    summary, explanation, action, numbers = _templates(classification, reason, detail, field_name)
    field_label = FIELD_LABELS.get(field_name, field_name.replace("_", " ").capitalize())
    severity_label = SEVERITY_LABELS.get(severity, severity.capitalize())
    documents = [DOCUMENT_LABELS.get(e.get("document_type") or "", _UNKNOWN_DOCUMENT) for e in evidence]

    summary, explanation, action, field_label, severity_label, doc_a, doc_b = translation_service.translate(
        [summary, explanation, action, field_label, severity_label, *documents], language
    )

    def named(label: str, item: dict[str, Any]) -> str:
        # Two documents of one kind, or of an unknown kind, are told apart by file name.
        by_name = item.get("distinguish_by_filename") or item.get("document_type") not in DOCUMENT_LABELS
        return f"{label} ({item.get('document_filename')})" if by_name else label

    summary = summary.format(
        field=field_label, a=first["value"], b=second["value"], doc_a=named(doc_a, first), doc_b=named(doc_b, second)
    )
    explanation = explanation.format(**numbers)
    return {
        "language": language,
        "field_label": field_label,
        "severity_label": severity_label,
        "summary": summary,
        "explanation": explanation,
        "action": action,
        "text": f"{summary} {explanation} {action}",
    }


def describe_finding(
    field_name: str,
    classification: str,
    reason: str,
    evidence: list[dict[str, Any]],
    detail: dict[str, Any] | None = None,
) -> str:
    """The stored English description: what differs and why. A harmless
    variant also says that nothing needs doing."""
    message = build_message(field_name, classification, reason, "info", evidence, detail, "en")
    text = f"{message['summary']} {message['explanation']}"
    return f"{text} {message['action']}" if classification == "harmless_variant" else text
