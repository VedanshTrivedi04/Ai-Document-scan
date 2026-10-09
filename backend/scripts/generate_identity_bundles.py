"""
Synthetic identity bundles for the contradiction detector.

Every person, address, number and issuing office here is invented, and every
page is marked as a specimen. Nothing is modelled on a real document.

    python -m scripts.generate_identity_bundles            # -> ../sample-documents/identity-bundles
    python -m scripts.generate_identity_bundles --out DIR

Writes one folder per bundle (one bundle = one person's documents = one
case), `ground_truth.json` describing what each document says and which
differences a detector should ignore or flag, and one zip per case type in
the layout bulk upload expects (one folder per case).

Hindi documents need a Devanagari font; they are rendered as images. Without
such a font those bundles are skipped and listed under `skipped`.
"""
from __future__ import annotations

import argparse
import html
import io
import json
import zipfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pymupdf

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "sample-documents" / "identity-bundles"

_DEVANAGARI_FONTS = (
    Path(r"C:\Windows\Fonts\Nirmala.ttc"),
    Path(r"C:\Windows\Fonts\Nirmala.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf"),
    Path("/usr/share/fonts/noto/NotoSansDevanagari-Regular.ttf"),
    Path("/Library/Fonts/NotoSansDevanagari-Regular.ttf"),
    Path("/System/Library/Fonts/Supplemental/Devanagari Sangam MN.ttc"),
)

_DATE_FORMATS = {
    "slash": "%d/%m/%Y",
    "dash": "%d-%m-%Y",
    "month": "%d %B %Y",
    "short": "%d-%b-%Y",
}

_TITLES = {
    "national_id_card": ("Sample Identity Authority", "IDENTITY CARD"),
    "tax_id_card": ("Sample Revenue Department", "TAX IDENTITY CARD"),
    "voter_id_card": ("Sample Election Office", "VOTER IDENTITY CARD"),
    "income_certificate": ("Office of the Sample Tehsildar", "INCOME CERTIFICATE"),
    "address_proof": ("Sample City Power Supply Co.", "ELECTRICITY BILL"),
    "marksheet": ("Sample Board of Secondary Education", "STATEMENT OF MARKS"),
    "degree_certificate": ("Sample State University", "DEGREE CERTIFICATE"),
    "experience_letter": ("Sample Software Pvt. Ltd.", "EXPERIENCE LETTER"),
}
_TITLES_HI = {
    "national_id_card": ("नमूना पहचान प्राधिकरण", "पहचान पत्र"),
    "income_certificate": ("कार्यालय नमूना तहसीलदार", "आय प्रमाण पत्र"),
}
_LABELS = {
    "name": "Name",
    "parent": "Father's / Husband's Name",
    "dob": "Date of Birth",
    "gender": "Gender",
    "address": "Address",
    "id_number": "Number",
    "income": "Annual Income",
    "issue_date": "Date of Issue",
}
_LABELS_HI = {
    "name": "नाम",
    "parent": "पिता / पति का नाम",
    "dob": "जन्म तिथि",
    "gender": "लिंग",
    "address": "पता",
    "id_number": "संख्या",
    "income": "वार्षिक आय",
    "issue_date": "जारी करने की तिथि",
}
_GENDER_HI = {"male": "पुरुष", "female": "महिला"}


@dataclass
class Doc:
    """One document, exactly as it prints each detail."""

    document_type: str
    fmt: str  # pdf | png | jpg | tiff
    name: str
    parent: str | None = None
    dob: date | None = None
    dob_format: str = "slash"
    gender: str | None = None
    address: str | None = None
    postal_code: str | None = None
    id_number: str | None = None
    income: int | None = None
    issue_date: date | None = None
    # Hindi documents: the same details as printed in Devanagari. `name`,
    # `parent` and `address` then hold the expected Latin transliteration.
    name_hi: str | None = None
    parent_hi: str | None = None
    address_hi: str | None = None
    # A portrait (image bytes) printed on the card, for the photograph check
    # (scripts/generate_photo_bundles.py). The page is then wider.
    photo: bytes | None = None

    @property
    def hindi(self) -> bool:
        return self.name_hi is not None


@dataclass
class Expected:
    field: str
    documents: tuple[int, int]  # indexes into the bundle's documents
    classification: str  # harmless_variant | conflict
    reason: str
    severity: str  # info | low | medium | high | critical
    note: str = ""


@dataclass
class Bundle:
    id: str
    title: str
    kind: str
    documents: list[Doc]
    expected: list[Expected] = field(default_factory=list)
    case_type: str = "identity_verification"
    family: str | None = None
    relation: str | None = None


def _income_text(amount: int) -> str:
    """Indian digit grouping: 480000 -> 'Rs. 4,80,000'."""
    digits = str(amount)
    head, tail = digits[:-3], digits[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return "Rs. " + ",".join(groups + [tail]) if groups else f"Rs. {tail}"


def _printed(doc: Doc) -> dict[str, str]:
    """The text each row of the document shows."""
    rows: dict[str, str] = {"name": doc.name_hi or doc.name}
    if doc.parent:
        rows["parent"] = doc.parent_hi or doc.parent
    if doc.dob:
        rows["dob"] = doc.dob.strftime(_DATE_FORMATS[doc.dob_format])
    if doc.gender:
        rows["gender"] = _GENDER_HI[doc.gender] if doc.hindi else doc.gender.capitalize()
    if doc.address:
        rows["address"] = (doc.address_hi or doc.address) + (f" - {doc.postal_code}" if doc.postal_code else "")
    if doc.id_number:
        rows["id_number"] = doc.id_number
    if doc.income is not None:
        rows["income"] = _income_text(doc.income)
    if doc.issue_date:
        rows["issue_date"] = doc.issue_date.strftime(_DATE_FORMATS["dash"])
    return rows


def _field(value: Any, **extra: Any) -> dict[str, Any]:
    present = value is not None
    return {"value": value, **extra, "confidence": 0.95 if present else 0.0, "uncertain": not present}


def ground_truth_fields(doc: Doc) -> dict[str, dict[str, Any]]:
    """What a correct extraction of `doc` returns, in the stored
    `identity_fields` shape (app/services/identity_documents.py)."""
    printed = _printed(doc)
    return {
        "full_name": _field(printed["name"], latin=doc.name),
        "parent_or_spouse_name": _field(printed.get("parent"), latin=doc.parent),
        "date_of_birth": _field(doc.dob.isoformat() if doc.dob else None, raw_text=printed.get("dob")),
        "gender": _field(doc.gender, raw_text=printed.get("gender")),
        "address": _field(
            printed.get("address"),
            latin=f"{doc.address} - {doc.postal_code}" if doc.address and doc.postal_code else doc.address,
            postal_code=doc.postal_code,
        ),
        "id_number": _field(doc.id_number),
        "annual_income": _field(
            float(doc.income) if doc.income is not None else None,
            raw_text=printed.get("income"),
            currency="INR" if doc.income is not None else None,
        ),
        "issuing_authority": _field((_TITLES_HI if doc.hindi else _TITLES)[doc.document_type][0]),
        "issue_date": _field(
            doc.issue_date.isoformat() if doc.issue_date else None, raw_text=printed.get("issue_date")
        ),
    }


def find_devanagari_font() -> Path | None:
    return next((p for p in _DEVANAGARI_FONTS if p.exists()), None)


_CSS = """
body { font-family: %s; font-size: 12px; color: #111; margin: 0; }
p { margin: 5px 0 0 0; }
.authority { font-size: 15px; font-weight: bold; text-align: center; }
.title { font-size: 13px; text-align: center; letter-spacing: 1px; }
.label { color: #444; }
.specimen { font-size: 9px; text-align: center; color: #a00; }
"""

_LEFT, _RIGHT, _LABEL_RIGHT, _VALUE_LEFT, _BOTTOM = 28, 392, 160, 170, 262
_PHOTO_COLUMN = 110  # extra page width for a portrait


def render_pdf(doc: Doc, devanagari_font: Path | None) -> pymupdf.Document:
    """One page: heading, then one row per detail (label left, value right),
    each placed explicitly so labels and values never run into each other."""
    pdf = pymupdf.open()
    page = pdf.new_page(width=420 + (_PHOTO_COLUMN if doc.photo else 0), height=300)
    page.draw_rect(pymupdf.Rect(12, 12, page.rect.width - 12, 288), color=(0.3, 0.3, 0.3), width=1)
    if doc.photo:
        left = _RIGHT + 18
        page.insert_image(pymupdf.Rect(left, 58, left + 90, 173), stream=doc.photo, keep_proportion=True)
        page.draw_rect(pymupdf.Rect(left, 58, left + 90, 173), color=(0.3, 0.3, 0.3), width=0.6)
    archive, css = None, _CSS % "sans-serif"
    if doc.hindi:
        if devanagari_font is None:
            raise RuntimeError("No Devanagari font found for a Hindi document.")
        archive = pymupdf.Archive(str(devanagari_font.parent))
        css = f"@font-face {{ font-family: hin; src: url({devanagari_font.name}); }}" + _CSS % "hin"

    def place(x0: float, x1: float, y: float, css_class: str, text: str) -> float:
        """Draw `text` at (x0..x1, y) and return the height it used."""
        box = pymupdf.Rect(x0, y, x1, _BOTTOM)
        spare, scale = page.insert_htmlbox(
            box, f"<p class='{css_class}'>{html.escape(text)}</p>", css=css, archive=archive, scale_low=1
        )
        if spare < 0 or scale != 1:
            raise RuntimeError(f"The {doc.document_type} for {doc.name} does not fit on its page.")
        return box.height - spare

    authority, title = (_TITLES_HI if doc.hindi else _TITLES)[doc.document_type]
    labels = _LABELS_HI if doc.hindi else _LABELS
    y = 20.0
    y += place(_LEFT, _RIGHT, y, "authority", authority)
    y += place(_LEFT, _RIGHT, y, "title", title) + 10
    for key, text in _printed(doc).items():
        used = max(
            place(_LEFT, _LABEL_RIGHT, y, "label", labels[key]),
            place(_VALUE_LEFT, _RIGHT, y, "value", text),
        )
        y += used + 3
    page.insert_htmlbox(
        pymupdf.Rect(_LEFT, 268, page.rect.width - 28, 284),
        "<p class='specimen'>SPECIMEN - SYNTHETIC TEST DOCUMENT - NOT A REAL RECORD</p>",
        css=css, archive=archive,
    )
    pdf.set_metadata({"title": "Synthetic test document", "producer": "generate_identity_bundles"})
    return pdf


def render(doc: Doc, devanagari_font: Path | None) -> bytes:
    pdf = render_pdf(doc, devanagari_font)
    try:
        if doc.fmt == "pdf":
            return pdf.tobytes(garbage=4, deflate=True, no_new_id=True)
        pixmap = pdf[0].get_pixmap(dpi=170)
        if doc.fmt == "png":
            return pixmap.tobytes("png")
        if doc.fmt == "jpg":
            return pixmap.tobytes("jpeg", jpg_quality=88)
        buffer = io.BytesIO()
        pixmap.pil_save(buffer, format="TIFF", compression="tiff_lzw")
        return buffer.getvalue()
    finally:
        pdf.close()


def _slug(document_type: str, index: int, fmt: str) -> str:
    return f"{index + 1:02d}-{document_type.replace('_', '-')}.{fmt}"


# ---------------------------------------------------------------------------
# The bundles. Each one isolates a case a detector must get right.
# ---------------------------------------------------------------------------

def build_bundles() -> list[Bundle]:
    bundles: list[Bundle] = []

    # 1. Everything agrees. Only the date formats differ.
    addr = "22 Tilak Path, Sector 4, Indore, Madhya Pradesh"
    bundles.append(Bundle(
        "B01-clean", "All documents agree", "clean",
        [
            Doc("national_id_card", "pdf", "Kavita Rao Deshmukh", "Suresh Rao Deshmukh", date(1990, 3, 12),
                "slash", "female", addr, "452001", "XXXX XXXX 1107"),
            Doc("tax_id_card", "pdf", "Kavita Rao Deshmukh", "Suresh Rao Deshmukh", date(1990, 3, 12),
                "month", id_number="QWKPD4417L"),
            Doc("income_certificate", "pdf", "Kavita Rao Deshmukh", "Suresh Rao Deshmukh", address=addr,
                postal_code="452001", id_number="IC/2026/004417", income=120000, issue_date=date(2026, 1, 10)),
        ],
    ))

    # 2. The same sounds spelled differently, and an abbreviated address.
    bundles.append(Bundle(
        "B02-spelling-variants", "Phonetic spelling and address abbreviations", "harmless",
        [
            Doc("national_id_card", "pdf", "Sunita Choudhary", "Ramlal Choudhary", date(1988, 7, 5), "slash",
                "female", "45 Mahatma Gandhi Road, Near Bus Stand, Ujjain, Madhya Pradesh", "456001",
                "XXXX XXXX 2290"),
            Doc("tax_id_card", "pdf", "Suneeta Chowdhary", "Ramlal Chowdhary", date(1988, 7, 5), "dash",
                id_number="BNTPC8821K"),
            Doc("address_proof", "pdf", "Sunita Choudhary", address="45 M.G. Rd, Nr Bus Stand, Ujjain, MP",
                postal_code="456001", id_number="EB-7741-2290", issue_date=date(2026, 2, 3)),
        ],
        [
            Expected("full_name", (0, 1), "harmless_variant", "spelling_variant", "info"),
            Expected("parent_or_spouse_name", (0, 1), "harmless_variant", "spelling_variant", "info"),
            Expected("full_name", (1, 2), "harmless_variant", "spelling_variant", "info"),
            Expected("address", (0, 2), "harmless_variant", "address_formatting", "info"),
        ],
    ))

    # 3. Initials, an honorific and a different word order.
    bundles.append(Bundle(
        "B03-initials-and-order", "Initials, honorific and word order", "harmless",
        [
            Doc("national_id_card", "pdf", "Ajay Prakash Sharma", "Om Prakash Sharma", date(1985, 11, 23),
                "slash", "male", "7 Shastri Nagar, Bhopal, Madhya Pradesh", "462003", "XXXX XXXX 3358"),
            Doc("tax_id_card", "pdf", "A. P. Sharma", "O. P. Sharma", date(1985, 11, 23), "slash",
                id_number="CLMPS5530Q"),
            Doc("voter_id_card", "pdf", "Shri Sharma Ajay Prakash", "Om Prakash Sharma", date(1985, 11, 23),
                "month", "male", "7 Shastri Nagar, Bhopal, Madhya Pradesh", "462003", "SVX4410927"),
        ],
        [
            Expected("full_name", (0, 1), "harmless_variant", "initials", "info"),
            Expected("parent_or_spouse_name", (0, 1), "harmless_variant", "initials", "info"),
            Expected("full_name", (0, 2), "harmless_variant", "honorific_or_word_order", "info"),
            Expected("full_name", (1, 2), "harmless_variant", "initials", "info"),
            Expected("parent_or_spouse_name", (1, 2), "harmless_variant", "initials", "info"),
        ],
    ))

    # 4. A customary abbreviation of a name.
    bundles.append(Bundle(
        "B04-name-abbreviation", "Customary abbreviation of a name", "harmless",
        [
            Doc("national_id_card", "pdf", "Mohammad Asif Khan", "Mohammad Yusuf Khan", date(1993, 1, 30),
                "slash", "male", "112 Idgah Hills, Bhopal, Madhya Pradesh", "462001", "XXXX XXXX 4471"),
            Doc("tax_id_card", "pdf", "Mohd. Asif Khan", "Mohd. Yusuf Khan", date(1993, 1, 30), "slash",
                id_number="DRKPK6642M"),
            Doc("income_certificate", "pdf", "Md Asif Khan", "Mohammad Yusuf Khan",
                address="112 Idgah Hills, Bhopal, Madhya Pradesh", postal_code="462001",
                id_number="IC/2026/006642", income=96000, issue_date=date(2026, 3, 18)),
        ],
        [
            Expected("full_name", (0, 1), "harmless_variant", "abbreviation", "info"),
            Expected("parent_or_spouse_name", (0, 1), "harmless_variant", "abbreviation", "info"),
            Expected("full_name", (0, 2), "harmless_variant", "abbreviation", "info"),
            Expected("full_name", (1, 2), "harmless_variant", "abbreviation", "info"),
            Expected("parent_or_spouse_name", (1, 2), "harmless_variant", "abbreviation", "info"),
        ],
    ))

    # 5. One document in Hindi, the others in English.
    bundles.append(Bundle(
        "B05-hindi-transliteration", "Hindi document against English documents", "harmless",
        [
            Doc("national_id_card", "png", "Ramesh Kumar Sharma", "Krishna Prasad Sharma", date(1979, 9, 14),
                "slash", "male", "18 Gandhi Chowk, Dewas, Madhya Pradesh", "455001", "XXXX XXXX 5512",
                name_hi="रमेश कुमार शर्मा", parent_hi="कृष्ण प्रसाद शर्मा",
                address_hi="18 गांधी चौक, देवास, मध्य प्रदेश"),
            Doc("tax_id_card", "pdf", "Ramesh Kumar Sharma", "Krishna Prasad Sharma", date(1979, 9, 14),
                "month", id_number="EPLPS7753R"),
            Doc("income_certificate", "pdf", "Ramesh Kumar Sharma", "Krishna Prasad Sharma",
                address="18 Gandhi Chowk, Dewas, Madhya Pradesh", postal_code="455001",
                id_number="IC/2026/007753", income=180000, issue_date=date(2026, 2, 21)),
        ],
        [
            Expected("full_name", (0, 1), "harmless_variant", "transliteration", "info"),
            Expected("full_name", (0, 2), "harmless_variant", "transliteration", "info"),
            Expected("parent_or_spouse_name", (0, 1), "harmless_variant", "transliteration", "info"),
            Expected("parent_or_spouse_name", (0, 2), "harmless_variant", "transliteration", "info"),
            Expected("address", (0, 2), "harmless_variant", "transliteration", "info"),
        ],
    ))

    # 6. Date of birth one day apart: likely a typing mistake.
    bundles.append(Bundle(
        "B06-dob-minor-typo", "Date of birth differs by one day", "conflict",
        [
            Doc("national_id_card", "pdf", "Pooja Nair", "Gopalan Nair", date(1995, 8, 15), "slash", "female",
                "3 Lake View Colony, Jabalpur, Madhya Pradesh", "482001", "XXXX XXXX 6634"),
            Doc("tax_id_card", "pdf", "Pooja Nair", "Gopalan Nair", date(1995, 8, 16), "slash",
                id_number="FQMPN8864S"),
        ],
        [Expected("date_of_birth", (0, 1), "conflict", "date_minor_difference", "medium")],
    ))

    # 7. Birth year fifteen years apart.
    bundles.append(Bundle(
        "B07-dob-year-conflict", "Birth year differs by fifteen years", "conflict",
        [
            Doc("national_id_card", "pdf", "Vikram Singh Rathore", "Bhanu Singh Rathore", date(1982, 3, 12),
                "slash", "male", "61 Fort Road, Gwalior, Madhya Pradesh", "474001", "XXXX XXXX 7745"),
            Doc("income_certificate", "pdf", "Vikram Singh Rathore", "Bhanu Singh Rathore",
                address="61 Fort Road, Gwalior, Madhya Pradesh", postal_code="474001",
                id_number="IC/2026/009975", income=84000, issue_date=date(2026, 1, 28)),
            Doc("voter_id_card", "pdf", "Vikram Singh Rathore", "Bhanu Singh Rathore", date(1997, 3, 12),
                "slash", "male", "61 Fort Road, Gwalior, Madhya Pradesh", "474001", "SVX7719045"),
        ],
        [Expected("date_of_birth", (0, 2), "conflict", "date_year_difference", "high")],
    ))

    # 8. A different person's document in the bundle.
    bundles.append(Bundle(
        "B08-different-person", "A document that belongs to someone else", "conflict",
        [
            Doc("national_id_card", "pdf", "Rahul Verma", "Dinesh Verma", date(1991, 6, 2), "slash", "male",
                "9 Station Road, Sagar, Madhya Pradesh", "470002", "XXXX XXXX 8856"),
            Doc("tax_id_card", "pdf", "Sanjay Singh", "Harpal Singh", date(1991, 6, 2), "slash",
                id_number="GRNPS9086T"),
        ],
        [
            Expected("full_name", (0, 1), "conflict", "different_name", "critical"),
            Expected("parent_or_spouse_name", (0, 1), "conflict", "different_name", "critical"),
        ],
    ))

    # 9. Similar-looking names that are different people. A similarity score
    #    alone would pass this; no naming convention explains the difference.
    bundles.append(Bundle(
        "B09-similar-but-different-name", "Similar spelling, different given name", "conflict",
        [
            Doc("national_id_card", "pdf", "Rahul Verma", "Dinesh Verma", date(1991, 6, 2), "slash", "male",
                "9 Station Road, Sagar, Madhya Pradesh", "470002", "XXXX XXXX 8856"),
            Doc("tax_id_card", "pdf", "Rohit Verma", "Dinesh Verma", date(1991, 6, 2), "slash",
                id_number="HSNPV1197U"),
        ],
        [Expected("full_name", (0, 1), "conflict", "different_name", "critical",
                  "High string similarity; must still be a conflict.")],
    ))

    # 10. Two income documents that disagree eightfold.
    bundles.append(Bundle(
        "B10-income-conflict", "Annual income differs eightfold", "conflict",
        [
            Doc("national_id_card", "pdf", "Meena Kumari Yadav", "Shivnath Yadav", date(1987, 12, 9), "slash",
                "female", "27 Azad Ward, Rewa, Madhya Pradesh", "486001", "XXXX XXXX 9967"),
            Doc("income_certificate", "pdf", "Meena Kumari Yadav", "Shivnath Yadav",
                address="27 Azad Ward, Rewa, Madhya Pradesh", postal_code="486001",
                id_number="IC/2026/011208", income=60000, issue_date=date(2026, 2, 11)),
            Doc("income_certificate", "pdf", "Meena Kumari Yadav", "Shivnath Yadav",
                address="27 Azad Ward, Rewa, Madhya Pradesh", postal_code="486001",
                id_number="IC/2025/030417", income=480000, issue_date=date(2025, 8, 4)),
        ],
        [Expected("annual_income", (1, 2), "conflict", "income_difference", "critical")],
    ))

    # 11. Gender and postal code disagree.
    bundles.append(Bundle(
        "B11-gender-and-address", "Gender and postal code differ", "conflict",
        [
            Doc("national_id_card", "pdf", "Kiran Patel", "Bharat Patel", date(1994, 4, 20), "slash", "female",
                "5 Narmada Colony, Khargone, Madhya Pradesh", "451001", "XXXX XXXX 1078"),
            Doc("voter_id_card", "pdf", "Kiran Patel", "Bharat Patel", date(1994, 4, 20), "slash", "male",
                "5 Narmada Colony, Khandwa, Madhya Pradesh", "450001", "SVX1120876"),
        ],
        [
            Expected("gender", (0, 1), "conflict", "gender_difference", "high"),
            Expected("address", (0, 1), "conflict", "address_locality_difference", "medium"),
        ],
    ))

    # 12. Same details, three image formats.
    addr = "40 Rajwada Lane, Indore, Madhya Pradesh"
    bundles.append(Bundle(
        "B12-image-formats", "Scanned images instead of PDFs", "clean",
        [
            Doc("national_id_card", "jpg", "Anjali Mehta", "Prakash Mehta", date(1996, 10, 1), "slash", "female",
                addr, "452002", "XXXX XXXX 2189"),
            Doc("tax_id_card", "png", "Anjali Mehta", "Prakash Mehta", date(1996, 10, 1), "short",
                id_number="JTPPM2208V"),
            Doc("address_proof", "tiff", "Anjali Mehta", address=addr, postal_code="452002",
                id_number="EB-3310-2189", issue_date=date(2026, 3, 2)),
        ],
    ))

    # 13. Hiring: a candidate's academic and employment documents.
    bundles.append(Bundle(
        "H01-hiring-candidate", "Candidate documents with one real conflict", "conflict",
        [
            Doc("national_id_card", "pdf", "Nikhil Joshi", "Madhav Joshi", date(1998, 5, 17), "slash", "male",
                "88 Vijay Nagar, Indore, Madhya Pradesh", "452010", "XXXX XXXX 3290"),
            Doc("marksheet", "pdf", "Nikhil M. Joshi", "Madhav Joshi", date(1998, 5, 17), "month",
                id_number="SB/2014/771203", issue_date=date(2014, 5, 30)),
            Doc("degree_certificate", "pdf", "Nikhil Madhav Joshi", "Madhav Joshi", date(1999, 5, 17), "month",
                id_number="SSU/BE/2020/04417", issue_date=date(2020, 7, 15)),
            Doc("experience_letter", "pdf", "Nikhil Joshi", id_number="SS/HR/2024/118",
                issue_date=date(2024, 3, 31)),
        ],
        [
            Expected("full_name", (0, 1), "harmless_variant", "extra_middle_name", "info"),
            Expected("full_name", (0, 2), "harmless_variant", "extra_middle_name", "info"),
            Expected("full_name", (1, 2), "harmless_variant", "initials", "info"),
            Expected("full_name", (1, 3), "harmless_variant", "extra_middle_name", "info"),
            Expected("full_name", (2, 3), "harmless_variant", "extra_middle_name", "info"),
            Expected("date_of_birth", (0, 2), "conflict", "date_year_difference", "high"),
            Expected("date_of_birth", (1, 2), "conflict", "date_year_difference", "high"),
        ],
        case_type="hiring_verification",
    ))

    # 14. A family of three. Each member is one bundle.
    home = "12 Sarafa Bazar, Ratlam, Madhya Pradesh"
    bundles.append(Bundle(
        "F01-head", "Family head", "clean",
        [
            Doc("national_id_card", "pdf", "Mahesh Chand Agrawal", "Ratan Lal Agrawal", date(1975, 2, 8),
                "slash", "male", home, "457001", "XXXX XXXX 4301"),
            Doc("income_certificate", "pdf", "Mahesh Chand Agrawal", "Ratan Lal Agrawal", address=home,
                postal_code="457001", id_number="IC/2026/014301", income=240000, issue_date=date(2026, 1, 5)),
        ],
        family="F01", relation="head",
    ))
    bundles.append(Bundle(
        "F01-spouse", "Spouse of the family head", "clean",
        [
            Doc("national_id_card", "pdf", "Sarla Agrawal", "Mahesh Chand Agrawal", date(1978, 6, 19), "slash",
                "female", home, "457001", "XXXX XXXX 4302"),
            Doc("voter_id_card", "pdf", "Sarla Agrawal", "Mahesh Chand Agrawal", date(1978, 6, 19), "slash",
                "female", home, "457001", "SVX4302118"),
        ],
        family="F01", relation="spouse",
    ))
    bundles.append(Bundle(
        "F01-child", "Child whose document names a different father", "conflict",
        [
            Doc("national_id_card", "pdf", "Tanvi Agrawal", "Mahesh Chand Agrawal", date(2004, 9, 27), "slash",
                "female", home, "457001", "XXXX XXXX 4303"),
            Doc("marksheet", "pdf", "Tanvi Agrawal", "Mukesh Chand Agrawal", date(2004, 9, 27), "month",
                id_number="SB/2020/330417", issue_date=date(2020, 6, 12)),
        ],
        [Expected("parent_or_spouse_name", (0, 1), "conflict", "different_name", "critical",
                  "Mahesh / Mukesh: similar spelling, different given name.")],
        family="F01", relation="child",
    ))
    return bundles


FAMILIES = [
    {
        "id": "F01",
        "head": "F01-head",
        "members": [
            {"bundle": "F01-head", "relation": "head"},
            {"bundle": "F01-spouse", "relation": "spouse"},
            {"bundle": "F01-child", "relation": "child"},
        ],
        "expected": [
            {"check": "shared_address", "result": "match"},
            {"check": "birth_order", "result": "match"},
            {"check": "parent_name", "member": "F01-child", "result": "conflict",
             "note": "The child's marksheet names Mukesh Chand Agrawal; the head is Mahesh Chand Agrawal."},
        ],
    }
]


def generate(out_dir: Path) -> dict[str, Any]:
    """Write every bundle under `out_dir` and return the ground truth."""
    out_dir.mkdir(parents=True, exist_ok=True)
    font = find_devanagari_font()
    truth: dict[str, Any] = {
        "note": "Synthetic test data. Every person, address and number is invented.",
        "bundles": [],
        "families": FAMILIES,
        "skipped": [],
    }
    zips: dict[str, list[tuple[str, bytes]]] = {}

    for bundle in build_bundles():
        if font is None and any(doc.hindi for doc in bundle.documents):
            truth["skipped"].append({"bundle": bundle.id, "reason": "No Devanagari font on this machine."})
            continue
        folder = out_dir / bundle.id
        folder.mkdir(exist_ok=True)
        documents = []
        for index, doc in enumerate(bundle.documents):
            filename = _slug(doc.document_type, index, doc.fmt)
            content = render(doc, font)
            (folder / filename).write_bytes(content)
            zips.setdefault(bundle.case_type, []).append((f"{bundle.id}/{filename}", content))
            documents.append({
                "file": filename,
                "document_type": doc.document_type,
                "language": "hi" if doc.hindi else "en",
                "identity_fields": ground_truth_fields(doc),
            })
        truth["bundles"].append({
            "id": bundle.id,
            "title": bundle.title,
            "kind": bundle.kind,
            "case_type": bundle.case_type,
            "family": bundle.family,
            "relation": bundle.relation,
            "documents": documents,
            "expected_findings": [
                {
                    "field": e.field,
                    "documents": [documents[e.documents[0]]["file"], documents[e.documents[1]]["file"]],
                    "classification": e.classification,
                    "reason": e.reason,
                    "severity": e.severity,
                    **({"note": e.note} if e.note else {}),
                }
                for e in bundle.expected
            ],
        })

    for case_type, entries in zips.items():
        with zipfile.ZipFile(out_dir / f"{case_type.replace('_', '-')}-bundles.zip", "w", zipfile.ZIP_DEFLATED) as zf:
            for name, content in entries:
                zf.writestr(zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0)), content)

    (out_dir / "ground_truth.json").write_text(
        json.dumps(truth, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return truth


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    truth = generate(args.out)
    files = sum(len(b["documents"]) for b in truth["bundles"])
    print(f"{len(truth['bundles'])} bundles, {files} documents -> {args.out}")
    for skipped in truth["skipped"]:
        print(f"skipped {skipped['bundle']}: {skipped['reason']}")


if __name__ == "__main__":
    main()
