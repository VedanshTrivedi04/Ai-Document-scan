"""
The verified profile of the person an identity case is about: one final
value per detail, taken from the case's documents, with the document it came
from. It is what a form is pre-filled from (app/services/form_templates.py).

Per field:

* `agreed`   - every document that states it agrees (identical, or a
               difference the contradiction check or a reviewer judged
               harmless). The value shown is taken from the most suitable
               document.
* `conflict` - at least one unresolved contradiction between two documents
               (app/services/identity_comparison.py). No value is given: a
               form must not be filled from a detail the documents dispute.
               The candidates are listed, with the one most documents agree
               on suggested.
* `chosen`   - a reviewer picked which document's value is the right one.
* `missing`  - no document states it.

Computed from what is stored (the documents' extracted fields, the findings
and their review decisions, the reviewer's choices on the case); nothing is
re-extracted and no model is called.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.services.identity_comparison import HONORIFICS
from app.services.identity_messages import FIELD_LABELS, display_value

PROFILE_FIELDS: tuple[str, ...] = (
    "full_name",
    "parent_or_spouse_name",
    "date_of_birth",
    "gender",
    "address",
    "annual_income",
)

# Which document's wording is used when several agree. Lower is preferred.
_DOCUMENT_PRIORITY = {
    "national_id_card": 0,
    "passport": 1,
    "voter_id_card": 2,
    "driving_licence": 3,
    "tax_id_card": 4,
    "birth_certificate": 5,
    "address_proof": 6,
    "income_certificate": 7,
}
_FIELD_PREFERRED_DOCUMENT = {"address": "address_proof", "annual_income": "income_certificate"}
_PERSONAL_ID_DOCUMENT_TYPES = ("national_id_card", "tax_id_card", "voter_id_card", "driving_licence", "passport")
_UNRESOLVED = ("open", "conflict_confirmed")


@dataclass(frozen=True)
class ProfileDocument:
    id: str
    filename: str
    document_type: str | None
    identity_fields: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class FindingState:
    """One stored finding, as far as the profile needs it."""

    field_name: str
    document_ids: tuple[str, ...]
    resolution: str  # open | conflict_confirmed | no_issue


def _has_value(doc: ProfileDocument, field_name: str) -> bool:
    return (doc.identity_fields.get(field_name) or {}).get("value") not in (None, "")


def _priority(doc: ProfileDocument, field_name: str) -> tuple[int, int]:
    preferred = 0 if doc.document_type == _FIELD_PREFERRED_DOCUMENT.get(field_name) else 1
    return (preferred, _DOCUMENT_PRIORITY.get(doc.document_type or "", 50))


def _name_fullness(doc: ProfileDocument, field_name: str) -> int:
    """How many whole words a name has: "Ajay Prakash Sharma" over "A. P. Sharma"."""
    field = doc.identity_fields.get(field_name) or {}
    text = str(field.get("latin") or field.get("value") or "")
    words = text.replace(".", " ").split()
    return sum(1 for word in words if len(word) > 1 and word.casefold() not in HONORIFICS)


def _issue_date(doc: ProfileDocument) -> date:
    try:
        return date.fromisoformat(str((doc.identity_fields.get("issue_date") or {}).get("value")))
    except ValueError:
        return date.min


def _best(documents: list[ProfileDocument], field_name: str) -> ProfileDocument:
    """The document whose wording represents a group of agreeing documents."""
    if field_name in ("full_name", "parent_or_spouse_name"):
        return min(documents, key=lambda d: (-_name_fullness(d, field_name), _priority(d, field_name)))
    if field_name == "annual_income":
        return min(documents, key=lambda d: (-_issue_date(d).toordinal(), _priority(d, field_name)))
    return min(documents, key=lambda d: _priority(d, field_name))


def _groups(holders: list[ProfileDocument], disputed: set[frozenset[str]]) -> list[list[ProfileDocument]]:
    """Documents that agree with each other, directly or through another."""
    parent = {d.id: d.id for d in holders}

    def root(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(holders):
        for b in holders[i + 1 :]:
            if frozenset((a.id, b.id)) not in disputed:
                parent[root(a.id)] = root(b.id)
    grouped: dict[str, list[ProfileDocument]] = {}
    for doc in holders:
        grouped.setdefault(root(doc.id), []).append(doc)
    return list(grouped.values())


def _source(doc: ProfileDocument, field_name: str) -> dict[str, Any]:
    field = doc.identity_fields.get(field_name) or {}
    return {
        "value": field.get("value"),
        "display_value": display_value(field_name, field),
        "latin": field.get("latin"),
        "document_id": doc.id,
        "document_type": doc.document_type,
        "document_filename": doc.filename,
    }


def _field_entry(
    field_name: str,
    documents: list[ProfileDocument],
    findings: list[FindingState],
    override: dict[str, Any] | None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "field": field_name,
        "label": FIELD_LABELS.get(field_name, field_name),
        "status": "missing",
        "value": None,
        "display_value": None,
        "latin": None,
        "document_id": None,
        "document_type": None,
        "document_filename": None,
        "candidates": [],
        "suggested_document_id": None,
        "documents_to_correct": [],
    }
    holders = [d for d in documents if _has_value(d, field_name)]
    if not holders:
        return entry

    ids = {d.id for d in holders}
    disputed = {
        frozenset(f.document_ids)
        for f in findings
        if f.field_name == field_name and f.resolution in _UNRESOLVED and set(f.document_ids) <= ids
    }
    groups = sorted(
        _groups(holders, disputed), key=lambda g: (-len(g), _priority(_best(g, field_name), field_name))
    )
    entry["candidates"] = [
        {**_source(_best(group, field_name), field_name), "document_ids": [d.id for d in group]} for group in groups
    ]

    chosen = next((d for d in holders if override and d.id == override.get("document_id")), None)
    if chosen is not None:
        entry.update(status="chosen", **_source(chosen, field_name))
        return entry
    if disputed:
        entry["status"] = "conflict"
        # More than half of the documents agreeing points at the others as the ones to correct.
        if len(groups[0]) * 2 > len(holders):
            entry["suggested_document_id"] = entry["candidates"][0]["document_id"]
            entry["documents_to_correct"] = [d.id for group in groups[1:] for d in group]
        return entry
    entry.update(status="agreed", **_source(_best(holders, field_name), field_name))
    return entry


def build_profile(
    documents: list[ProfileDocument],
    findings: list[FindingState],
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The profile of the person `documents` belong to."""
    overrides = overrides or {}
    fields = [_field_entry(name, documents, findings, overrides.get(name)) for name in PROFILE_FIELDS]
    by_name = {f["field"]: f for f in fields}

    address = by_name["address"]
    address_doc = next((d for d in documents if d.id == address["document_id"]), None)
    postal_code = (address_doc.identity_fields.get("address") or {}).get("postal_code") if address_doc else None

    id_numbers: dict[str, dict[str, Any]] = {}
    for document_type in _PERSONAL_ID_DOCUMENT_TYPES:
        holders = [d for d in documents if d.document_type == document_type and _has_value(d, "id_number")]
        disputed = any(
            f.field_name == "id_number" and f.resolution in _UNRESOLVED
            and set(f.document_ids) <= {d.id for d in holders}
            for f in findings
        )
        if holders and not disputed:
            id_numbers[document_type] = _source(holders[0], "id_number")

    counts = {status: sum(1 for f in fields if f["status"] == status) for status in ("agreed", "chosen", "conflict", "missing")}
    return {
        "fields": fields,
        "postal_code": postal_code,
        "id_numbers": id_numbers,
        "counts": counts,
        "ready": counts["conflict"] == 0,
    }
