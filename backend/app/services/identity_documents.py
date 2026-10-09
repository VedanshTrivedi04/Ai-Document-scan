"""
Identity bundles: one person's documents (identity card, address proof,
income certificate, ...) submitted together and checked for contradictions
between them, rather than for forgery.

A case of an identity case type (app/models/case.py's IDENTITY_CASE_TYPES)
takes this path through the pipeline: images are accepted as well as PDFs,
the person's details are extracted with `LLMService.extract_identity`, and
the invoice-specific steps (line items, issuer registry, PDF forensics) are
skipped.

Stored shape, in `documents.extracted_fields`:

    {"schema": "identity",
     "document_type_confidence": float,
     "identity_fields": {<IDENTITY_FIELD_NAMES>: {value, ..., bounding_box?}},
     "faces": {"status": ok|unavailable|failed, "items": [{bounding_box, score, embedding}]},
     "core_fields": {...all null...},      # kept so older readers don't break
     "additional_fields": [...]}
"""
from __future__ import annotations

from typing import Any

from app.services.id_number_masking import mask_id_numbers, restore_id_numbers
from app.services.llm_service import IdentityAnalysis, LLMService

IDENTITY_SCHEMA = "identity"

IDENTITY_DOCUMENT_TYPE_LABELS: list[str] = [
    "national_id_card",
    "tax_id_card",
    "voter_id_card",
    "driving_licence",
    "passport",
    "birth_certificate",
    "income_certificate",
    "address_proof",
    "caste_certificate",
    "domicile_certificate",
    "marksheet",
    "degree_certificate",
    "experience_letter",
    "payslip",
    "other",
]

# Order is the order fields are located on the page and shown to a reader.
IDENTITY_FIELD_NAMES: tuple[str, ...] = (
    "full_name",
    "parent_or_spouse_name",
    "date_of_birth",
    "gender",
    "address",
    "id_number",
    "annual_income",
    "issuing_authority",
    "issue_date",
)

_EMPTY_CORE_FIELDS: dict[str, dict[str, Any]] = {
    "issuer": {"value": None, "confidence": 0.0, "uncertain": True},
    "reference_number": {"value": None, "confidence": 0.0, "uncertain": True},
    "date": {"value": None, "raw_text": None, "confidence": 0.0, "uncertain": True},
    "amount": {"value": None, "raw_text": None, "currency": None, "confidence": 0.0, "uncertain": True},
    "subtotal": {"value": None, "raw_text": None, "currency": None, "confidence": 0.0, "uncertain": True},
    "tax_amount": {"value": None, "raw_text": None, "currency": None, "confidence": 0.0, "uncertain": True},
    "tax_rate": {"value": None, "raw_text": None, "confidence": 0.0, "uncertain": True},
}


def is_identity_extraction(extracted_fields: dict[str, Any] | None) -> bool:
    return isinstance(extracted_fields, dict) and extracted_fields.get("schema") == IDENTITY_SCHEMA


def extract_identity(llm_service: LLMService, document_text: str) -> IdentityAnalysis:
    # Identity numbers never reach the model: it sees placeholders, and the
    # numbers are put back here (app/services/id_number_masking.py).
    masked_text, numbers = mask_id_numbers(document_text)
    analysis = llm_service.extract_identity(
        document_text=masked_text, document_type_labels=IDENTITY_DOCUMENT_TYPE_LABELS
    )
    if not numbers:
        return analysis
    return IdentityAnalysis.model_validate(restore_id_numbers(analysis.model_dump(), numbers))


def identity_extracted_fields(
    analysis: IdentityAnalysis, faces: dict[str, Any] | None = None
) -> dict[str, Any]:
    """The `documents.extracted_fields` value for one identity document."""
    return {
        "schema": IDENTITY_SCHEMA,
        "document_type_confidence": analysis.document_type_confidence,
        "identity_fields": analysis.identity_fields_as_dict(),
        "faces": faces if faces is not None else {"status": "unavailable", "items": []},
        "core_fields": {name: dict(field) for name, field in _EMPTY_CORE_FIELDS.items()},
        "additional_fields": [f.model_dump() for f in analysis.additional_fields],
    }
