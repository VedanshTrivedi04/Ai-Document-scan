"""
Checks across the members of a family, on top of the per-person
contradiction check (app/services/identity_comparison.py).

Each member's details come from the verified profile of their latest case
(app/services/person_profile.py). Four things are checked:

* `member_identity` - the documents belong to the person the head entered
  (name, and date of birth when one was entered).
* `shared_address`  - the member lives at the family head's address.
* `parent_name`     - the parent named on a child's documents is the head or
  the head's spouse; the father named on the head's documents is the member
  entered as father.
* `birth_order`     - a child is born after the parents, a parent before
  the head.

The same comparison rules as between documents are used, so a spelling
variant or initials do not raise a conflict. A check that lacks a detail, or
whose detail is still disputed between the member's own documents, is
reported as `not_checked`, never guessed.

Pure functions; the messages are translated like the finding messages
(only templates are translated, never a person's details).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.models.family import CHILD_RELATIONS, RELATION_SELF
from app.services import translation_service
from app.services.identity_comparison import CONFLICT, Verdict, compare_addresses, compare_dates, compare_names

MATCH, NOT_CHECKED = "match", "not_checked"

CHECK_LABELS = {
    "member_identity": "Name and date of birth",
    "shared_address": "Address",
    "parent_name": "Parent's name",
    "birth_order": "Dates of birth",
}
RELATION_LABELS = {
    "self": "Head of family",
    "spouse": "Spouse",
    "son": "Son",
    "daughter": "Daughter",
    "father": "Father",
    "mother": "Mother",
    "other": "Other",
}

_NO_DOCUMENTS = "{member}: no documents have been checked yet."
_DETAIL_UNAVAILABLE = "{member}: not checked, because a needed detail is missing or still disputed."
_IDENTITY_OK = "{member}: the documents match the details entered for this family member."
_IDENTITY_NAME = "{member}: the documents show the name {a}, but {b} was entered for this family member."
_IDENTITY_DOB = "{member}: the documents show the date of birth {a}, but {b} was entered for this family member."
_ADDRESS_OK = "{member} has the same address as the head of the family."
_ADDRESS_DIFFERENT = "{member} has a different address ({a}) from the head of the family ({b})."
_PARENT_OK = "{member}: the parent named on the documents ({a}) is a member of this family."
_PARENT_DIFFERENT = (
    "{member}: the documents name {a} as the parent. This does not match the parents entered in this family ({b})."
)
_BIRTH_OK = "{member}: the date of birth fits the dates of birth of the parents."
_BORN_BEFORE_PARENT = "{member} ({a}) is recorded as born before or on the same day as the parent {other} ({b})."
_PARENT_BORN_AFTER = "{member} ({a}) is recorded as born after or on the same day as their child {other} ({b})."

_HINDI = {
    "Name and date of birth": "नाम और जन्म तिथि",
    "Address": "पता",
    "Parent's name": "माता-पिता का नाम",
    "Dates of birth": "जन्म तिथियाँ",
    "Head of family": "परिवार का मुखिया",
    "Spouse": "पति / पत्नी",
    "Son": "पुत्र",
    "Daughter": "पुत्री",
    "Father": "पिता",
    "Mother": "माता",
    "Other": "अन्य",
    _NO_DOCUMENTS: "{member}: अभी तक कोई दस्तावेज़ जाँचा नहीं गया है।",
    _DETAIL_UNAVAILABLE: "{member}: जाँच नहीं हुई, क्योंकि ज़रूरी जानकारी नहीं मिली या उस पर अभी अंतर है।",
    _IDENTITY_OK: "{member}: दस्तावेज़ इस सदस्य के लिए भरी गई जानकारी से मेल खाते हैं।",
    _IDENTITY_NAME: "{member}: दस्तावेज़ों में नाम {a} है, जबकि इस सदस्य के लिए {b} भरा गया था।",
    _IDENTITY_DOB: "{member}: दस्तावेज़ों में जन्म तिथि {a} है, जबकि इस सदस्य के लिए {b} भरी गई थी।",
    _ADDRESS_OK: "{member} का पता परिवार के मुखिया के पते जैसा ही है।",
    _ADDRESS_DIFFERENT: "{member} का पता ({a}) परिवार के मुखिया के पते ({b}) से अलग है।",
    _PARENT_OK: "{member}: दस्तावेज़ों में लिखे माता-पिता ({a}) इसी परिवार के सदस्य हैं।",
    _PARENT_DIFFERENT: "{member}: दस्तावेज़ों में माता-पिता का नाम {a} है। यह इस परिवार में भरे गए माता-पिता ({b}) से मेल नहीं खाता।",
    _BIRTH_OK: "{member}: जन्म तिथि माता-पिता की जन्म तिथियों के अनुसार ठीक है।",
    _BORN_BEFORE_PARENT: "{member} ({a}) का जन्म माता-पिता {other} ({b}) से पहले या उसी दिन दर्ज है।",
    _PARENT_BORN_AFTER: "{member} ({a}) का जन्म उनकी संतान {other} ({b}) के बाद या उसी दिन दर्ज है।",
}
translation_service.BUILT_IN_CATALOGS.setdefault("hi", {}).update(_HINDI)


def check_strings() -> list[str]:
    return list(_HINDI)


@dataclass(frozen=True)
class MemberDetails:
    """A family member as entered by the head, with the profile of their
    latest case (None until a case of theirs has documents)."""

    id: str
    full_name: str
    relation: str
    date_of_birth: date | None
    profile: dict[str, Any] | None


def _detail(member: MemberDetails, field_name: str) -> dict[str, Any] | None:
    """A settled profile detail as a comparable field, or None."""
    if member.profile is None:
        return None
    entry = next((f for f in member.profile["fields"] if f["field"] == field_name), None)
    if entry is None or entry["status"] not in ("agreed", "chosen") or entry["value"] in (None, ""):
        return None
    return {
        "value": entry["value"],
        "latin": entry.get("latin") or entry["value"],
        "display_value": entry["display_value"],
        "postal_code": member.profile.get("postal_code") if field_name == "address" else None,
    }


def _entered_name(member: MemberDetails) -> dict[str, Any]:
    return {"value": member.full_name, "latin": member.full_name}


def _born(member: MemberDetails) -> date | None:
    """The date of birth on the documents, else the one the head entered."""
    detail = _detail(member, "date_of_birth")
    if detail:
        try:
            return date.fromisoformat(str(detail["value"]))
        except ValueError:
            return None
    return member.date_of_birth


def _show_date(value: date) -> str:
    return f"{value.day} {value.strftime('%B %Y')}"


class _Report:
    def __init__(self, language: str):
        self.language = translation_service.normalize_language(language)
        translation_service.translate(check_strings(), self.language)  # one request, then cached
        self.items: list[dict[str, Any]] = []

    def add(self, check: str, member: MemberDetails, result: str, template: str, *, severity: str = "info", **values: Any):
        text, label = translation_service.translate([template, CHECK_LABELS[check]], self.language)
        self.items.append(
            {
                "check": check,
                "label": label,
                "member_id": member.id,
                "member_name": member.full_name,
                "relation": member.relation,
                "result": result,
                "severity": severity if result == CONFLICT else "info",
                "summary": text.format(member=member.full_name, **values),
            }
        )


def _is_conflict(verdict: Verdict | None) -> bool:
    return verdict is not None and verdict.classification == CONFLICT


def run_family_checks(members: list[MemberDetails], language: str = "en") -> list[dict[str, Any]]:
    """Every family-level check for `members`, as plain results."""
    report = _Report(language)
    head = next((m for m in members if m.relation == RELATION_SELF), None)
    spouses = [m for m in members if m.relation == "spouse"]
    parents_of_children = [m for m in [head, *spouses] if m is not None]

    for member in members:
        if member.profile is None or member.profile.get("document_count", 0) == 0:
            report.add("member_identity", member, NOT_CHECKED, _NO_DOCUMENTS)
            continue

        # 1. The documents belong to the person the head entered.
        name = _detail(member, "full_name")
        if name is None:
            report.add("member_identity", member, NOT_CHECKED, _DETAIL_UNAVAILABLE)
        else:
            verdict = compare_names(name, _entered_name(member))
            born = _detail(member, "date_of_birth")
            entered_born = {"value": member.date_of_birth.isoformat()} if member.date_of_birth else None
            date_verdict = compare_dates(born, entered_born) if born and entered_born else None
            if _is_conflict(verdict):
                report.add("member_identity", member, CONFLICT, _IDENTITY_NAME, severity=verdict.severity.value,
                           a=name["display_value"], b=member.full_name)
            elif _is_conflict(date_verdict):
                report.add("member_identity", member, CONFLICT, _IDENTITY_DOB, severity=date_verdict.severity.value,
                           a=born["display_value"], b=_show_date(member.date_of_birth))
            else:
                report.add("member_identity", member, MATCH, _IDENTITY_OK)

        # 2. Same address as the head.
        if head is not None and member is not head:
            mine, theirs = _detail(member, "address"), _detail(head, "address")
            if mine is None or theirs is None:
                report.add("shared_address", member, NOT_CHECKED, _DETAIL_UNAVAILABLE)
            else:
                verdict = compare_addresses(mine, theirs)
                if _is_conflict(verdict):
                    report.add("shared_address", member, CONFLICT, _ADDRESS_DIFFERENT, severity=verdict.severity.value,
                               a=mine["display_value"], b=theirs["display_value"])
                else:
                    report.add("shared_address", member, MATCH, _ADDRESS_OK)

        # 3. The parent named on the documents is a parent in this family.
        expected_parents: list[MemberDetails] = []
        if member.relation in CHILD_RELATIONS:
            expected_parents = parents_of_children
        elif member is head:
            expected_parents = [m for m in members if m.relation == "father"]
        if expected_parents:
            named = _detail(member, "parent_or_spouse_name")
            if named is None:
                report.add("parent_name", member, NOT_CHECKED, _DETAIL_UNAVAILABLE)
            else:
                # Against the name on the parent's own documents when settled, else as entered.
                verdicts = [
                    compare_names(named, _detail(parent, "full_name") or _entered_name(parent))
                    for parent in expected_parents
                ]
                if any(v is not None and not _is_conflict(v) for v in verdicts):
                    report.add("parent_name", member, MATCH, _PARENT_OK, a=named["display_value"])
                elif any(_is_conflict(v) for v in verdicts):
                    worst = max((v for v in verdicts if _is_conflict(v)), key=lambda v: _SEVERITY_RANK[v.severity.value])
                    report.add("parent_name", member, CONFLICT, _PARENT_DIFFERENT, severity=worst.severity.value,
                               a=named["display_value"], b=" / ".join(p.full_name for p in expected_parents))
                else:
                    report.add("parent_name", member, NOT_CHECKED, _DETAIL_UNAVAILABLE)

        # 4. Children are younger than their parents; parents older than the head.
        if member.relation in CHILD_RELATIONS and parents_of_children:
            _birth_order(report, member, parents_of_children, _BORN_BEFORE_PARENT)
        elif member.relation in ("father", "mother") and head is not None:
            _birth_order(report, member, [head], _PARENT_BORN_AFTER, member_is_elder=True)
    return report.items


_SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


def _birth_order(
    report: _Report, member: MemberDetails, others: list[MemberDetails], template: str, *, member_is_elder: bool = False
) -> None:
    born = _born(member)
    known = [(other, _born(other)) for other in others]
    known = [(other, value) for other, value in known if value is not None]
    if born is None or not known:
        report.add("birth_order", member, NOT_CHECKED, _DETAIL_UNAVAILABLE)
        return
    for other, other_born in known:
        out_of_order = born >= other_born if member_is_elder else born <= other_born
        if out_of_order:
            report.add("birth_order", member, CONFLICT, template, severity="high",
                       a=_show_date(born), b=_show_date(other_born), other=other.full_name)
            return
    report.add("birth_order", member, MATCH, _BIRTH_OK)


def count_results(checks: list[dict[str, Any]]) -> dict[str, int]:
    return {result: sum(1 for c in checks if c["result"] == result) for result in (MATCH, CONFLICT, NOT_CHECKED)}
