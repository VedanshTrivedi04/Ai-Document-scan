"""
Application forms that can be pre-filled from a case's verified profile
(app/services/person_profile.py).

The forms here are sample forms written for this application; they are not
copies of any authority's form. Each field names the profile detail it is
filled from, or none when the applicant must enter it.

A field whose detail the documents dispute is left empty and marked
`needs_attention`: a form is never filled from a value under conflict.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.services import translation_service

FILLED, NEEDS_ATTENTION, TO_FILL = "filled", "needs_attention", "to_fill"

_NOTE_CONFLICT = "Your documents do not agree on this detail. It is filled in once the conflict is resolved."
_NOTE_NOT_FOUND = "Not found on your documents. Please enter it."
_GENDER_OPTIONS = {"male": "Male", "female": "Female", "other": "Other"}


@dataclass(frozen=True)
class FormField:
    key: str
    label: str
    type: str = "text"  # text | textarea | date | number | select
    source: str | None = None  # a profile detail, or None: the applicant enters it
    required: bool = True


@dataclass(frozen=True)
class FormTemplate:
    id: str
    title: str
    description: str
    case_types: tuple[str, ...]
    fields: tuple[FormField, ...]


_PERSON = (
    FormField("applicant_name", "Full name", source="full_name"),
    FormField("parent_name", "Father's / husband's name", source="parent_or_spouse_name"),
    FormField("date_of_birth", "Date of birth", "date", source="date_of_birth"),
    FormField("gender", "Gender", "select", source="gender"),
    FormField("address", "Address", "textarea", source="address"),
    FormField("postal_code", "Postal code", source="postal_code"),
)

FORMS: tuple[FormTemplate, ...] = (
    FormTemplate(
        "income_certificate_application",
        "Application for an income certificate",
        "Request a certificate of your family's annual income.",
        ("identity_verification",),
        (
            *_PERSON,
            FormField("identity_number", "Identity card number", source="id_number:national_id_card"),
            FormField("annual_income", "Annual income", "number", source="annual_income"),
            FormField("purpose", "Purpose of the certificate"),
            FormField("mobile_number", "Mobile number"),
        ),
    ),
    FormTemplate(
        "scholarship_application",
        "Scholarship application",
        "Apply for a scholarship based on family income.",
        ("identity_verification",),
        (
            *_PERSON,
            FormField("age", "Age (years)", "number", source="age"),
            FormField("identity_number", "Identity card number", source="id_number:national_id_card"),
            FormField("annual_income", "Family annual income", "number", source="annual_income"),
            FormField("institution", "Name of the school or college"),
            FormField("course", "Class or course"),
            FormField("bank_account", "Bank account number"),
        ),
    ),
    FormTemplate(
        "domicile_certificate_application",
        "Application for a domicile certificate",
        "Request a certificate of residence.",
        ("identity_verification",),
        (
            *_PERSON,
            FormField("identity_number", "Identity card number", source="id_number:national_id_card"),
            FormField("voter_number", "Voter identity card number", source="id_number:voter_id_card", required=False),
            FormField("years_of_residence", "Years living at this address", "number"),
        ),
    ),
    FormTemplate(
        "employee_joining_form",
        "Employee joining form",
        "Details of a new employee for the employer's records.",
        ("hiring_verification",),
        (
            *_PERSON,
            FormField("identity_number", "Identity card number", source="id_number:national_id_card"),
            FormField("tax_number", "Tax identity number", source="id_number:tax_id_card", required=False),
            FormField("mobile_number", "Mobile number"),
            FormField("emergency_contact", "Emergency contact name and number"),
            FormField("joining_date", "Date of joining", "date"),
        ),
    ),
)
_FORMS_BY_ID = {form.id: form for form in FORMS}


def get_form(form_id: str) -> FormTemplate | None:
    return _FORMS_BY_ID.get(form_id)


def forms_for(case_type: str | None = None) -> list[FormTemplate]:
    return [form for form in FORMS if case_type is None or case_type in form.case_types]


def form_strings() -> list[str]:
    """Every English string of the forms, for one translation request."""
    strings = [_NOTE_CONFLICT, _NOTE_NOT_FOUND, *_GENDER_OPTIONS.values()]
    for form in FORMS:
        strings += [form.title, form.description, *(f.label for f in form.fields)]
    return list(dict.fromkeys(strings))


def describe_form(form: FormTemplate, language: str = "en") -> dict[str, Any]:
    title, description, *labels = translation_service.translate(
        [form.title, form.description, *(f.label for f in form.fields)], language
    )
    return {
        "id": form.id,
        "title": title,
        "description": description,
        "case_types": list(form.case_types),
        "field_count": len(form.fields),
        "prefilled_field_count": sum(1 for f in form.fields if f.source),
        "fields": [
            {"key": f.key, "label": label, "type": f.type, "required": f.required, "prefilled": f.source is not None}
            for f, label in zip(form.fields, labels)
        ],
    }


def _age(born: str, today: date) -> int | None:
    try:
        birth = date.fromisoformat(born)
    except (TypeError, ValueError):
        return None
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


def _from_profile(source: str, profile: dict[str, Any], today: date) -> tuple[str, dict[str, Any] | None]:
    """(status of the profile detail, where its value comes from) for a
    form field's source. The dict carries value, display_value and the
    document; None when there is no value."""
    fields = {f["field"]: f for f in profile["fields"]}
    if source.startswith("id_number:"):
        found = profile["id_numbers"].get(source.split(":", 1)[1])
        return ("agreed", found) if found else ("missing", None)
    if source == "postal_code":
        address = fields["address"]
        if address["status"] in ("conflict", "missing") or not profile.get("postal_code"):
            return address["status"] if address["status"] == "conflict" else "missing", None
        return "agreed", {**address, "value": profile["postal_code"], "display_value": profile["postal_code"]}
    if source == "age":
        born = fields["date_of_birth"]
        age = _age(born["value"], today) if born["value"] else None
        if age is None:
            return born["status"] if born["status"] == "conflict" else "missing", None
        return "agreed", {**born, "value": age, "display_value": str(age)}
    entry = fields[source]
    return entry["status"], (entry if entry["value"] not in (None, "") else None)


def prefill(form: FormTemplate, profile: dict[str, Any], *, language: str = "en", today: date | None = None) -> dict[str, Any]:
    """`form` with every field the profile can supply filled in."""
    today = today or date.today()
    language = translation_service.normalize_language(language)
    translation_service.translate(form_strings(), language)  # one request, then cached
    described = describe_form(form, language)
    note_conflict, note_not_found = translation_service.translate([_NOTE_CONFLICT, _NOTE_NOT_FOUND], language)
    gender_labels = dict(zip(_GENDER_OPTIONS, translation_service.translate(list(_GENDER_OPTIONS.values()), language)))

    filled_fields: list[dict[str, Any]] = []
    for definition, shown in zip(form.fields, described["fields"]):
        item: dict[str, Any] = {
            **shown,
            "value": None,
            "display_value": None,
            "status": TO_FILL,
            "note": None,
            "source_field": None,
            "source_document_id": None,
            "source_document_type": None,
            "source_document_filename": None,
        }
        if definition.type == "select" and definition.source == "gender":
            item["options"] = [{"value": value, "label": label} for value, label in gender_labels.items()]
        if definition.source:
            status, found = _from_profile(definition.source, profile, today)
            item["source_field"] = definition.source
            if status == "conflict":
                item.update(status=NEEDS_ATTENTION, note=note_conflict)
            elif found is None:
                item["note"] = note_not_found
            else:
                item.update(
                    status=FILLED,
                    value=found["value"],
                    display_value=found["display_value"],
                    source_document_id=found["document_id"],
                    source_document_type=found["document_type"],
                    source_document_filename=found["document_filename"],
                )
                if definition.source == "gender":
                    item["display_value"] = gender_labels.get(found["value"], found["display_value"])
        filled_fields.append(item)

    counts = {s: sum(1 for f in filled_fields if f["status"] == s) for s in (FILLED, NEEDS_ATTENTION, TO_FILL)}
    return {
        "form": {k: described[k] for k in ("id", "title", "description", "case_types")},
        "language": language,
        "fields": filled_fields,
        "counts": counts,
        "ready": counts[NEEDS_ATTENTION] == 0,
    }


_HINDI = {
    _NOTE_CONFLICT: "आपके दस्तावेज़ों में यह जानकारी मेल नहीं खाती। अंतर सुलझने के बाद यह भर दी जाएगी।",
    _NOTE_NOT_FOUND: "यह आपके दस्तावेज़ों में नहीं मिली। कृपया इसे भरें।",
    "Male": "पुरुष",
    "Female": "महिला",
    "Other": "अन्य",
    "Full name": "पूरा नाम",
    "Father's / husband's name": "पिता / पति का नाम",
    "Date of birth": "जन्म तिथि",
    "Gender": "लिंग",
    "Address": "पता",
    "Postal code": "पिन कोड",
    "Identity card number": "पहचान पत्र संख्या",
    "Annual income": "वार्षिक आय",
    "Family annual income": "परिवार की वार्षिक आय",
    "Purpose of the certificate": "प्रमाण पत्र का उद्देश्य",
    "Mobile number": "मोबाइल नंबर",
    "Age (years)": "आयु (वर्ष)",
    "Name of the school or college": "स्कूल या कॉलेज का नाम",
    "Class or course": "कक्षा या पाठ्यक्रम",
    "Bank account number": "बैंक खाता संख्या",
    "Voter identity card number": "मतदाता पहचान पत्र संख्या",
    "Years living at this address": "इस पते पर रहने के वर्ष",
    "Tax identity number": "कर पहचान संख्या",
    "Emergency contact name and number": "आपातकालीन संपर्क का नाम और नंबर",
    "Date of joining": "कार्यभार ग्रहण करने की तिथि",
    "Application for an income certificate": "आय प्रमाण पत्र के लिए आवेदन",
    "Request a certificate of your family's annual income.": "अपने परिवार की वार्षिक आय का प्रमाण पत्र माँगें।",
    "Scholarship application": "छात्रवृत्ति आवेदन",
    "Apply for a scholarship based on family income.": "परिवार की आय के आधार पर छात्रवृत्ति के लिए आवेदन करें।",
    "Application for a domicile certificate": "निवास प्रमाण पत्र के लिए आवेदन",
    "Request a certificate of residence.": "निवास का प्रमाण पत्र माँगें।",
    "Employee joining form": "कर्मचारी कार्यभार ग्रहण प्रपत्र",
    "Details of a new employee for the employer's records.": "नियोक्ता के रिकॉर्ड के लिए नए कर्मचारी का विवरण।",
}
translation_service.BUILT_IN_CATALOGS.setdefault("hi", {}).update(_HINDI)
