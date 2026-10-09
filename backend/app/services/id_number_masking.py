"""
Keeping identity numbers away from the language model.

An identity bundle's OCR text goes to a language model for extraction
(app/services/identity_documents.py), and that model may be a third-party
service. Numbers with a fixed printed shape (national identity, tax identity,
voter identity, passport, driving licence) are found here, on this machine,
and replaced by placeholders such as `[ID_NUMBER_1]` before the text leaves.
The model only decides WHICH placeholder is the document's own number; the
real digits are put back locally in its reply.

Numbers with no fixed shape (a certificate's serial such as "IC/2026/004417")
are not recognised and still reach the model.
"""
from __future__ import annotations

import re
from typing import Any

# Longest shape first: where two could start at the same place, the first wins.
_SHAPES: tuple[str, ...] = (
    r"[A-Z]{2}[ -]?[0-9]{2}[ -]?(?:19|20)[0-9]{2}[ -]?[0-9]{7}",  # driving licence
    r"(?:[0-9Xx*#]{4}[ -]?){2}[0-9]{4}",  # 12-digit national identity, masked or not
    r"[A-Z]{5}[0-9]{4}[A-Z]",  # tax identity
    r"[A-Z]{3}[0-9]{7}",  # voter identity
    r"[A-Z][0-9]{7}",  # passport
)
_ID_NUMBER = re.compile(r"(?<![A-Za-z0-9*#])(?:" + "|".join(_SHAPES) + r")(?![A-Za-z0-9*#])")

# Tolerant of a model that drops the brackets or changes the case.
_PLACEHOLDER = re.compile(r"\[?\s*ID[_ ]NUMBER[_ ]([0-9]+)\s*\]?", re.IGNORECASE)


def mask_id_numbers(text: str) -> tuple[str, list[str]]:
    """`text` with every recognised number replaced by `[ID_NUMBER_n]`, and
    the numbers themselves: placeholder n stands for `numbers[n - 1]`. The
    same printed number always gets the same placeholder."""
    numbers: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        printed = match.group(0)
        if printed not in numbers:
            numbers.append(printed)
        return f"[ID_NUMBER_{numbers.index(printed) + 1}]"

    return _ID_NUMBER.sub(_replace, text or ""), numbers


def _restore_text(text: str, numbers: list[str]) -> str | None:
    unknown = False

    def _replace(match: re.Match[str]) -> str:
        nonlocal unknown
        index = int(match.group(1))
        if 1 <= index <= len(numbers):
            return numbers[index - 1]
        unknown = True  # a placeholder the model made up: there is no number to give back
        return ""

    restored = _PLACEHOLDER.sub(_replace, text)
    if unknown and not restored.strip():
        return None
    return restored


def restore_id_numbers(value: Any, numbers: list[str]) -> Any:
    """`value` (a string, or dicts and lists of them) with every placeholder
    replaced by the number it stands for."""
    if isinstance(value, str):
        return _restore_text(value, numbers)
    if isinstance(value, dict):
        return {key: restore_id_numbers(item, numbers) for key, item in value.items()}
    if isinstance(value, list):
        return [restore_id_numbers(item, numbers) for item in value]
    return value
