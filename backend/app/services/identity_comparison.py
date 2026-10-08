"""
Contradiction check for an identity bundle: the documents of one person
compared field by field (app/services/identity_documents.py).

Every pair of documents is compared on name, parent/spouse name, date of
birth, gender, address, annual income and (between identity cards of the
same kind) identity number. Each difference is classified:

* `harmless_variant` - the two documents mean the same thing and a NAMED
  reason explains the difference (initials, a customary abbreviation, a
  spelling of the same sound, another script, an honorific, word order, an
  abbreviated address). Stored with severity `info`, never raised as a
  problem, and shown so a reader can see what was ignored and why.
* `conflict` - no such reason applies. Stored with a severity.

A similarity score alone never makes a difference harmless: "Rahul Verma"
and "Rohit Verma" are 82% similar and are two people. Only a recognised
reason does. Everything here is deterministic rules, so the same bundle
always gives the same findings and each one can be explained.

Pure functions over plain dicts: no database, no model call.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from itertools import combinations
from typing import Any

from rapidfuzz.distance import OSA

from app.models.cross_document_finding import FindingSeverity
from app.services.identity_messages import describe_finding, display_value

FINDING_TYPE = "identity_consistency"
MATCH = "match"
HARMLESS = "harmless_variant"
CONFLICT = "conflict"

NAME_FIELDS = ("full_name", "parent_or_spouse_name")
COMPARED_FIELDS = (
    "full_name",
    "parent_or_spouse_name",
    "date_of_birth",
    "gender",
    "address",
    "annual_income",
    "id_number",
)

# Identity numbers are compared only between two cards of the same kind: a
# person has one of each, whereas two certificates legitimately carry
# different serial numbers.
_PERSONAL_ID_DOCUMENT_TYPES = frozenset(
    {"national_id_card", "tax_id_card", "voter_id_card", "driving_licence", "passport"}
)


@dataclass(frozen=True)
class Verdict:
    classification: str
    reason: str
    severity: FindingSeverity
    detail: dict[str, Any] | None = None


_MATCH = Verdict(MATCH, "same", FindingSeverity.info)


def _harmless(reason: str) -> Verdict:
    return Verdict(HARMLESS, reason, FindingSeverity.info)


def _conflict(reason: str, severity: FindingSeverity, **detail: Any) -> Verdict:
    return Verdict(CONFLICT, reason, severity, detail or None)


# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------

HONORIFICS = frozenset({
    "shri", "sri", "shree", "smt", "shrimati", "srimati", "mr", "mrs", "ms", "miss", "dr", "prof",
    "late", "sh", "km", "kum", "master",
})
# Customary short forms of a name part.
_NAME_ABBREVIATIONS = {"mohd": "mohammad", "md": "mohammad", "kr": "kumar", "pd": "prasad"}
# Established alternative spellings the sound rules below do not cover.
_NAME_SPELLINGS = {
    "mohammed": "mohammad", "muhammad": "mohammad", "mohamed": "mohammad",
    "mohamad": "mohammad", "muhammed": "mohammad",
}
# Letter groups that Indian names spell either way for one sound, applied in
# order. Deliberately conservative: vowels are not dropped, because that
# would merge different names (Rina / Rani, Mahesh / Mukesh). "aw" is not
# folded: in Agrawal and Rawat the two letters belong to different syllables.
_SOUND_RULES: tuple[tuple[str, str], ...] = (
    ("chh", "ch"), ("sh", "s"), ("ph", "f"), ("bh", "b"), ("dh", "d"), ("th", "t"), ("kh", "k"),
    ("gh", "g"), ("jh", "j"), ("ee", "i"), ("oo", "u"), ("ou", "o"), ("ow", "o"), ("au", "o"),
    ("ai", "e"), ("ay", "e"), ("ie", "i"), ("w", "v"), ("z", "j"), ("q", "k"),
    ("ck", "k"), ("x", "ks"),
)
_LETTERS = re.compile(r"[^\W\d_]+")
_MIN_TYPO_LENGTH = 5


def _is_latin(text: str) -> bool:
    return all(ord(ch) < 0x0250 for ch in text if ch.isalpha())


def _name_tokens(text: str) -> list[str]:
    folded = unicodedata.normalize("NFKD", text).casefold()
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch)) if _is_latin(text) else folded
    return _LETTERS.findall(folded)


def sound_key(token: str) -> str:
    """Spellings of the same sound map to the same key."""
    key = _NAME_SPELLINGS.get(token, token)
    for written, sound in _SOUND_RULES:
        key = key.replace(written, sound)
    if key.endswith("y"):
        key = key[:-1] + "i"
    return re.sub(r"(.)\1+", r"\1", key)


def _token_relation(a: str, b: str, *, cross_script: bool) -> str | None:
    """How two name parts relate, strongest first; None if they do not."""
    if a == b:
        return "exact"
    if _NAME_ABBREVIATIONS.get(a, a) == _NAME_ABBREVIATIONS.get(b, b):
        return "abbreviation"
    full_a, full_b = _NAME_ABBREVIATIONS.get(a, a), _NAME_ABBREVIATIONS.get(b, b)
    if sound_key(full_a) == sound_key(full_b):
        return "abbreviation" if (full_a != a or full_b != b) else "spelling"
    if len(a) == 1 or len(b) == 1:
        short, long = (a, b) if len(a) == 1 else (b, a)
        return "initial" if len(long) > 1 and long.startswith(short) else None
    if cross_script and min(len(a), len(b)) >= 4 and OSA.distance(sound_key(a), sound_key(b)) <= 1:
        # A transliteration is itself approximate (Ramesh / Ramesha).
        return "spelling"
    return "typo" if _one_letter_slip(a, b) else None


_VOWELS = frozenset("aeiou")


def _one_letter_slip(a: str, b: str) -> bool:
    """Whether two name parts differ the way a slip of the pen does: one
    vowel changed, one letter dropped or added, or two neighbours swapped
    (Verma / Varma, Agrawal / Agarwal). A different first letter or a changed
    consonant is a different name (Seema / Reema, Ramesh / Rajesh)."""
    key_a, key_b = sound_key(a), sound_key(b)
    if min(len(a), len(b)) < _MIN_TYPO_LENGTH or key_a[0] != key_b[0] or OSA.distance(key_a, key_b) != 1:
        return False
    if len(key_a) != len(key_b):
        return True
    changed = [(x, y) for x, y in zip(key_a, key_b) if x != y]
    return len(changed) == 2 or all(x in _VOWELS and y in _VOWELS for x, y in changed)


_RELATION_ORDER = ("exact", "abbreviation", "spelling", "initial", "typo")


def _align(tokens_a: list[str], tokens_b: list[str], *, cross_script: bool):
    """Pair up the parts of two names, strongest relation first. Returns
    (pairs as (index_a, index_b, relation), unmatched a, unmatched b)."""
    free_a, free_b = set(range(len(tokens_a))), set(range(len(tokens_b)))
    pairs: list[tuple[int, int, str]] = []
    for wanted in _RELATION_ORDER:
        for i in sorted(free_a):
            for j in sorted(free_b):
                if _token_relation(tokens_a[i], tokens_b[j], cross_script=cross_script) == wanted:
                    pairs.append((i, j, wanted))
                    free_a.discard(i)
                    free_b.discard(j)
                    break
    return pairs, sorted(free_a), sorted(free_b)


def _comparable_name(field: dict[str, Any]) -> tuple[str, bool] | None:
    """(text to compare, whether the document printed it in a non-Latin
    script), or None if the field has nothing comparable."""
    value, latin = field.get("value"), field.get("latin")
    if not value:
        return None
    if _is_latin(str(value)):
        return str(value), False
    if latin and _is_latin(str(latin)):
        return str(latin), True
    return None  # another script and no Latin form: cannot be compared by rule


def compare_names(field_a: dict[str, Any], field_b: dict[str, Any]) -> Verdict | None:
    a, b = _comparable_name(field_a), _comparable_name(field_b)
    if a is None or b is None:
        return None
    (text_a, foreign_a), (text_b, foreign_b) = a, b
    cross_script = foreign_a != foreign_b

    raw_a, raw_b = _name_tokens(text_a), _name_tokens(text_b)
    tokens_a = [t for t in raw_a if t not in HONORIFICS] or raw_a
    tokens_b = [t for t in raw_b if t not in HONORIFICS] or raw_b
    if raw_a == raw_b:
        return _harmless("transliteration") if cross_script else _MATCH

    pairs, extra_a, extra_b = _align(tokens_a, tokens_b, cross_script=cross_script)
    relations = {relation for _, _, relation in pairs}

    if extra_a and extra_b:
        return _conflict("different_name", FindingSeverity.critical)
    if "typo" in relations:
        return _conflict("possible_spelling_error", FindingSeverity.medium)
    if extra_a or extra_b:
        if len(pairs) < 2:
            return _conflict("partial_name", FindingSeverity.low)
        if cross_script:
            return _harmless("transliteration")
        if "initial" in relations:
            return _harmless("initials")
        if "abbreviation" in relations:
            return _harmless("abbreviation")
        return _harmless("extra_middle_name")

    if cross_script:
        return _harmless("transliteration")
    if "initial" in relations:
        return _harmless("initials")
    if "abbreviation" in relations:
        return _harmless("abbreviation")
    if "spelling" in relations:
        return _harmless("spelling_variant")
    # Same parts: only an honorific or the order of the words differs.
    return _harmless("honorific_or_word_order")


# ---------------------------------------------------------------------------
# Dates, gender, income, identity number
# ---------------------------------------------------------------------------

def _parse_iso(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def compare_dates(field_a: dict[str, Any], field_b: dict[str, Any]) -> Verdict | None:
    a, b = _parse_iso(field_a.get("value")), _parse_iso(field_b.get("value"))
    if a is None or b is None:
        return None
    if a == b:
        return _MATCH
    if a.year != b.year:
        return _conflict("date_year_difference", FindingSeverity.high, years_apart=abs(a.year - b.year))
    if (a.day, a.month) == (b.month, b.day):
        return _conflict("date_day_month_swapped", FindingSeverity.low)
    digits_a, digits_b = f"{a.day:02d}{a.month:02d}", f"{b.day:02d}{b.month:02d}"
    if sum(x != y for x, y in zip(digits_a, digits_b)) == 1:
        return _conflict("date_minor_difference", FindingSeverity.medium)
    return _conflict("date_difference", FindingSeverity.high)


def compare_gender(field_a: dict[str, Any], field_b: dict[str, Any]) -> Verdict | None:
    a, b = field_a.get("value"), field_b.get("value")
    if not a or not b:
        return None
    return _MATCH if a == b else _conflict("gender_difference", FindingSeverity.high)


def compare_income(field_a: dict[str, Any], field_b: dict[str, Any]) -> Verdict | None:
    a, b = field_a.get("value"), field_b.get("value")
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)) or a <= 0 or b <= 0:
        return None
    currency_a, currency_b = field_a.get("currency"), field_b.get("currency")
    if currency_a and currency_b and currency_a != currency_b:
        return None  # not comparable without a conversion rate
    low, high = sorted((float(a), float(b)))
    ratio = high / low
    if ratio <= 1.01:
        return _MATCH
    if ratio >= 2:
        severity = FindingSeverity.critical
    elif ratio >= 1.25:
        severity = FindingSeverity.high
    else:
        severity = FindingSeverity.medium
    return _conflict("income_difference", severity, ratio=round(ratio, 2))


_MASK = frozenset("X*#")


def compare_id_numbers(field_a: dict[str, Any], field_b: dict[str, Any]) -> Verdict | None:
    a = re.sub(r"[\s\-/]", "", str(field_a.get("value") or "")).upper()
    b = re.sub(r"[\s\-/]", "", str(field_b.get("value") or "")).upper()
    if not a or not b:
        return None
    if len(a) != len(b):
        return _conflict("id_number_difference", FindingSeverity.high)
    # A masked position ("XXXX XXXX 4321") agrees with anything.
    differs = any(x != y for x, y in zip(a, b) if x not in _MASK and y not in _MASK)
    return _conflict("id_number_difference", FindingSeverity.high) if differs else _MATCH


# ---------------------------------------------------------------------------
# Addresses
# ---------------------------------------------------------------------------

_ADDRESS_WORDS = {
    "rd": "road", "st": "street", "nr": "near", "opp": "opposite", "apt": "apartment", "flr": "floor",
    "sec": "sector", "col": "colony", "ngr": "nagar", "dist": "district", "distt": "district",
    "teh": "tehsil", "vill": "village", "blk": "block", "bldg": "building", "soc": "society",
    "mkt": "market", "ln": "lane", "mg": "mahatma gandhi", "mp": "madhya pradesh",
    "up": "uttar pradesh", "mh": "maharashtra", "hno": "house", "no": "", "number": "",
}
_POSTAL_CODE = re.compile(r"(?<!\d)\d{6}(?!\d)")


def _address_tokens(text: str) -> list[str]:
    folded = unicodedata.normalize("NFKC", text).casefold().replace(".", "")
    tokens: list[str] = []
    for token in re.findall(r"[^\W_]+", _POSTAL_CODE.sub(" ", folded)):
        tokens.extend(_ADDRESS_WORDS.get(token, token).split())
    return tokens


def _postal_code(field: dict[str, Any], text: str) -> str | None:
    code = re.sub(r"\D", "", str(field.get("postal_code") or ""))
    if len(code) == 6:
        return code
    found = _POSTAL_CODE.search(text)
    return found.group(0) if found else None


def compare_addresses(field_a: dict[str, Any], field_b: dict[str, Any]) -> Verdict | None:
    a, b = _comparable_name(field_a), _comparable_name(field_b)
    if a is None or b is None:
        return None
    (text_a, foreign_a), (text_b, foreign_b) = a, b
    cross_script = foreign_a != foreign_b

    code_a, code_b = _postal_code(field_a, text_a), _postal_code(field_b, text_b)
    if code_a and code_b and code_a != code_b:
        return _conflict("address_locality_difference", FindingSeverity.medium)

    tokens_a, tokens_b = _address_tokens(text_a), _address_tokens(text_b)
    if not tokens_a or not tokens_b:
        return None
    plain_a = re.sub(r"\W+", " ", text_a.casefold()).split()
    plain_b = re.sub(r"\W+", " ", text_b.casefold()).split()
    if plain_a == plain_b:
        return _harmless("transliteration") if cross_script else _MATCH
    same_meaning = _harmless("transliteration" if cross_script else "address_formatting")
    if sorted(tokens_a) == sorted(tokens_b):
        return same_meaning

    only_a = _unmatched(tokens_a, tokens_b, cross_script=cross_script)
    only_b = _unmatched(tokens_b, tokens_a, cross_script=cross_script)
    if not only_a or not only_b:
        return same_meaning  # one address just carries more detail than the other
    if all(t.isdigit() for t in only_a + only_b):
        return _conflict("address_difference", FindingSeverity.low)
    return _conflict("address_locality_difference", FindingSeverity.medium)


# Words that add no location of their own.
_ADDRESS_FILLER = frozenset({
    "near", "opposite", "behind", "beside", "post", "district", "tehsil", "village", "ward", "the", "of",
    "at", "po", "ps", "house", "flat", "plot",
})


def _same_address_word(a: str, b: str, *, cross_script: bool) -> bool:
    if a == b:
        return True
    if a.isdigit() or b.isdigit():
        return False
    key_a, key_b = sound_key(a), sound_key(b)
    if key_a == key_b:
        return True
    shortest = min(len(a), len(b))
    return shortest >= (4 if cross_script else 6) and OSA.distance(key_a, key_b) <= 1


def _unmatched(tokens: list[str], others: list[str], *, cross_script: bool) -> list[str]:
    """The words of one address the other has no counterpart for."""
    return [
        t for t in tokens
        if t not in _ADDRESS_FILLER
        and not any(_same_address_word(t, o, cross_script=cross_script) for o in others)
    ]


# ---------------------------------------------------------------------------
# The bundle
# ---------------------------------------------------------------------------

_COMPARERS = {
    "full_name": compare_names,
    "parent_or_spouse_name": compare_names,
    "date_of_birth": compare_dates,
    "gender": compare_gender,
    "address": compare_addresses,
    "annual_income": compare_income,
    "id_number": compare_id_numbers,
}


@dataclass(frozen=True)
class BundleDocument:
    """One document of the bundle, as the comparison needs it."""

    id: str
    filename: str
    document_type: str | None
    identity_fields: dict[str, dict[str, Any]]


def compare_field(field_name: str, doc_a: BundleDocument, doc_b: BundleDocument) -> Verdict | None:
    """The verdict for one field between two documents; None when either
    lacks it or the two cannot be compared."""
    if field_name == "id_number" and not (
        doc_a.document_type == doc_b.document_type and doc_a.document_type in _PERSONAL_ID_DOCUMENT_TYPES
    ):
        return None
    field_a = doc_a.identity_fields.get(field_name) or {}
    field_b = doc_b.identity_fields.get(field_name) or {}
    if field_a.get("value") in (None, "") or field_b.get("value") in (None, ""):
        return None
    return _COMPARERS[field_name](field_a, field_b)


def _evidence(field_name: str, doc: BundleDocument, same_type: bool) -> dict[str, Any]:
    field = doc.identity_fields.get(field_name) or {}
    return {
        "document_id": doc.id,
        "document_type": doc.document_type,
        "document_filename": doc.filename,
        # Two documents of one type are told apart by file name in messages.
        "distinguish_by_filename": same_type,
        "value": display_value(field_name, field),
        "bounding_box": field.get("bounding_box"),
    }


def find_identity_contradictions(documents: list[BundleDocument]) -> list[dict[str, Any]]:
    """Every difference between the documents of one bundle, as dicts ready
    for `CrossDocumentFinding(case_id=..., **finding)`. Matching values
    produce nothing."""
    findings: list[dict[str, Any]] = []
    for doc_a, doc_b in combinations(documents, 2):
        same_type = doc_a.document_type == doc_b.document_type
        for field_name in COMPARED_FIELDS:
            verdict = compare_field(field_name, doc_a, doc_b)
            if verdict is None or verdict.classification == MATCH:
                continue
            evidence = [_evidence(field_name, doc_a, same_type), _evidence(field_name, doc_b, same_type)]
            findings.append(
                {
                    "field_name": field_name,
                    "finding_type": FINDING_TYPE,
                    "classification": verdict.classification,
                    "reason": verdict.reason,
                    "severity": verdict.severity,
                    "description": describe_finding(field_name, verdict.classification, verdict.reason,
                                                    evidence, verdict.detail),
                    "document_ids": [doc_a.id, doc_b.id],
                    "evidence": evidence,
                    "detail": verdict.detail,
                }
            )
    return findings
