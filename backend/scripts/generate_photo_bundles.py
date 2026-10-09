"""
Identity bundles whose cards carry a photograph, for the photograph check
(app/services/face_service.py).

No portrait is stored in this repository. You supply a folder of portraits
you are allowed to use (synthetic faces, or people who agreed), named by
person and shot:

    portraits/person_a_1.jpg   person_a_2.jpg   (the same person, two photos)
    portraits/person_b_1.jpg                    (someone else)

    python -m scripts.generate_photo_bundles --portraits DIR [--out DIR]

Writes one folder per bundle plus `ground_truth.json` (what the photograph
check should say for each pair of documents). Every name, number and office
is invented and every page is marked as a specimen.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from scripts.generate_identity_bundles import Doc, find_devanagari_font, ground_truth_fields, render

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "sample-documents" / "photo-bundles"

_ADDRESS = "14 Lake View Road, Sector 9, Bhopal, Madhya Pradesh"
_NAME, _PARENT = "Meera Anil Kulkarni", "Anil Kulkarni"


def _read(folder: Path, name: str) -> np.ndarray:
    path = next((p for p in sorted(folder.glob(f"{name}.*")) if p.suffix.lower() in {".jpg", ".jpeg", ".png"}), None)
    if path is None:
        raise SystemExit(f"Missing portrait {name}.jpg in {folder}")
    image = cv2.imread(str(path))
    if image is None:
        raise SystemExit(f"Could not read {path}")
    return image


def _face_crop(image: np.ndarray) -> np.ndarray:
    """A card-style crop around the face. Needs the face models."""
    from app.services import face_service

    detector, _ = face_service._load_models()
    detector.setInputSize((image.shape[1], image.shape[0]))
    _, found = detector.detect(image)
    if found is None:
        return image
    x, y, w, h = (int(v) for v in found[0][:4])
    margin = int(0.4 * w)
    return image[max(0, y - margin): y + h + margin, max(0, x - margin): x + w + int(0.4 * w) + 1]


def _encode(image: np.ndarray, quality: int = 90) -> bytes:
    return cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])[1].tobytes()


def _card_photo(image: np.ndarray, height: int = 330, quality: int = 90) -> bytes:
    crop = _face_crop(image)
    ratio = 90 / 115
    width = int(height * ratio)
    return _encode(cv2.resize(crop, (width, height), interpolation=cv2.INTER_AREA), quality)


def _photocopied(image: np.ndarray) -> bytes:
    """A grey, soft, heavily compressed copy: what a bad photocopy does."""
    small = cv2.resize(_face_crop(image), (72, 92), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), 1.1)
    grey = cv2.cvtColor(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    return _encode(cv2.resize(grey, (270, 345), interpolation=cv2.INTER_CUBIC), 35)


def build(portraits: Path) -> list[dict[str, Any]]:
    a1, a2, b1 = _read(portraits, "person_a_1"), _read(portraits, "person_a_2"), _read(portraits, "person_b_1")

    def card(document_type: str, fmt: str, photo: bytes | None, **extra: Any) -> Doc:
        values = dict(
            name=_NAME, parent=_PARENT, dob=date(1991, 6, 18), dob_format="slash", gender="female",
            address=_ADDRESS, postal_code="462016", photo=photo,
        )
        values.update(extra)
        return Doc(document_type, fmt, **values)

    income = Doc(
        "income_certificate", "pdf", _NAME, _PARENT, address=_ADDRESS, postal_code="462016",
        id_number="IC/2026/009912", income=180000, issue_date=date(2026, 2, 2),
    )
    return [
        {
            "id": "P01-same-person",
            "title": "Three cards, the same person on each",
            "documents": [
                card("national_id_card", "pdf", _card_photo(a1), id_number="XXXX XXXX 5521"),
                card("voter_id_card", "pdf", _card_photo(a2), id_number="MPV/0198/553421"),
                card("tax_id_card", "png", _card_photo(a1, 300, 80), id_number="DKQPK5521M"),
                income,
            ],
            "expected_photo": {(0, 1): "photo_match", (0, 2): "photo_match", (1, 2): "photo_match"},
        },
        {
            "id": "P02-another-persons-photo",
            "title": "Everything agrees except the photograph on the voter card",
            "documents": [
                card("national_id_card", "pdf", _card_photo(a1), id_number="XXXX XXXX 5521"),
                card("voter_id_card", "pdf", _card_photo(b1), id_number="MPV/0198/553421"),
                income,
            ],
            "expected_photo": {(0, 1): "photo_different_person"},
        },
        {
            "id": "P03-photocopy-quality",
            "title": "The same person, but one card is a poor photocopy",
            "documents": [
                card("national_id_card", "pdf", _card_photo(a1), id_number="XXXX XXXX 5521"),
                card("voter_id_card", "jpg", _photocopied(a2), id_number="MPV/0198/553421"),
            ],
            # A poor copy may land in "please look"; it must never read as a different person.
            "expected_photo": {(0, 1): "photo_match|photo_uncertain"},
        },
        {
            "id": "P04-no-photo-on-one-card",
            "title": "A card without a photograph is left out of the comparison",
            "documents": [
                card("national_id_card", "pdf", _card_photo(a1), id_number="XXXX XXXX 5521"),
                card("tax_id_card", "pdf", None, id_number="DKQPK5521M"),
                income,
            ],
            "expected_photo": {},
        },
    ]


def generate(portraits: Path, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    font = find_devanagari_font()
    truth: dict[str, Any] = {
        "note": "Synthetic test data. Every person, address and number is invented; portraits were supplied by the developer.",
        "bundles": [],
    }
    for bundle in build(portraits):
        folder = out_dir / bundle["id"]
        folder.mkdir(exist_ok=True)
        documents = []
        for index, doc in enumerate(bundle["documents"]):
            filename = f"{index + 1:02d}-{doc.document_type.replace('_', '-')}.{doc.fmt}"
            (folder / filename).write_bytes(render(doc, font))
            documents.append(
                {
                    "file": filename,
                    "document_type": doc.document_type,
                    "has_photo": doc.photo is not None,
                    "identity_fields": ground_truth_fields(doc),
                }
            )
        truth["bundles"].append(
            {
                "id": bundle["id"],
                "title": bundle["title"],
                "case_type": "identity_verification",
                "documents": documents,
                "expected_photo_findings": [
                    {
                        "documents": [documents[a]["file"], documents[b]["file"]],
                        "reason": reason,
                    }
                    for (a, b), reason in bundle["expected_photo"].items()
                ],
            }
        )
    (out_dir / "ground_truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return truth


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--portraits", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    truth = generate(args.portraits, args.out)
    print(f"{len(truth['bundles'])} bundles -> {args.out}")


if __name__ == "__main__":
    main()
