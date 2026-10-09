"""
Writes invented Aadhaar-style and PAN-style test cards for manual upload
testing (docs/UPLOAD_TESTING_GUIDE.md).

Every person, number and address is made up. Every card says SPECIMEN, carries
no emblem, photo or real layout, and is not meant to pass for a real document.

    python -m scripts.generate_test_cards

Output: sample-documents/test-cards/<set>/*.png|jpg and MANIFEST.json (what
each card states and what the detector is expected to say; the expectations
are the author's reading of the comparison rules, not a measured result).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parents[2] / "sample-documents" / "test-cards"
W, H = 900, 560
_FONTS = Path(r"C:\Windows\Fonts")
_LATIN = [_FONTS / "arial.ttf", Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]
_LATIN_B = [_FONTS / "arialbd.ttf", Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]
_DEVA = [_FONTS / "Nirmala.ttc", Path("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf")]


def _font(paths: list[Path], size: int) -> ImageFont.FreeTypeFont:
    for p in paths:
        if p.exists():
            return ImageFont.truetype(str(p), size)
    raise SystemExit(f"No usable font among {[str(p) for p in paths]}")


def card(title: str, subtitle: str, rows: list[tuple[str, str]], accent: str, devanagari: bool = False) -> Image.Image:
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([10, 10, W - 10, H - 10], outline=accent, width=5)
    d.rectangle([10, 10, W - 10, 90], fill=accent)
    body = _font(_DEVA if devanagari else _LATIN, 30)
    label = _font(_DEVA if devanagari else _LATIN, 22)
    d.text((34, 20), title, fill="white", font=_font(_DEVA if devanagari else _LATIN_B, 34))
    d.text((34, 66), subtitle, fill="white", font=_font(_LATIN, 16))
    y = 108
    for key, value in rows:
        d.text((40, y), key, fill="#555555", font=label)
        d.text((40, y + 26), value, fill="#111111", font=body)
        y += 66
    d.text((W // 2, H - 30), "SPECIMEN - NOT A REAL DOCUMENT", fill="#b00020", font=_font(_LATIN_B, 24), anchor="mm")
    return img


def aadhaar(name, parent, dob, gender, number, address, *, hindi=False):
    if hindi:
        rows = [("नाम", name), ("पिता का नाम", parent), ("जन्म तिथि", dob), ("लिंग", gender),
                ("पहचान संख्या", number), ("पता", address)]
        return card("SPECIMEN - पहचान पत्र", "Aadhaar-style identity card (invented)", rows, "#1d3f7a", True)
    rows = [("Name", name), ("Father / Spouse", parent), ("Date of birth", dob), ("Gender", gender),
            ("ID number", number), ("Address", address)]
    return card("SPECIMEN IDENTITY CARD", "Aadhaar-style card (invented data)", rows, "#1d3f7a")


def pan(name, parent, dob, number):
    rows = [("Name", name), ("Father's name", parent), ("Date of birth", dob), ("Permanent account number", number)]
    return card("SPECIMEN TAX CARD", "PAN-style card (invented data)", rows, "#6a1b4d")


def income(name, parent, income_text, number, address, issued):
    rows = [("Name", name), ("Father / Spouse", parent), ("Annual income", income_text),
            ("Certificate number", number), ("Address", address), ("Date of issue", issued)]
    return card("SPECIMEN INCOME CERTIFICATE", "Issued by: Sample Tehsildar Office (invented)", rows, "#2e6b3a")


ADDR = "124 Residency Road, Indore, Madhya Pradesh - 452001"
SETS: list[dict] = []


def add(sid, title, expect, files):
    SETS.append({"id": sid, "title": title, "expected": expect, "files": files})


def build() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []

    def save(sid, fname, img, fmt="PNG", **kw):
        folder = OUT / sid
        folder.mkdir(exist_ok=True)
        img.save(folder / fname, fmt, **kw)
        return f"{sid}/{fname}"

    def entry(sid, title, expected, items):
        manifest.append({"id": sid, "title": title, "expected": expected, "documents": items})

    # T01 clean
    f = [save("T01-clean", "aadhaar.png", aadhaar("Rahul Sharma", "Mohan Sharma", "15/08/1990", "Male", "9101 2233 4455", ADDR)),
         save("T01-clean", "pan.png", pan("Rahul Sharma", "Mohan Sharma", "15/08/1990", "ABCPR4821K"))]
    entry("T01-clean", "Every shared detail agrees", "No findings", f)

    # T02 initial in the name, one year apart in the birth year
    f = [save("T02-initial-and-year", "aadhaar.png", aadhaar("Rahul Sharma", "Mohan Sharma", "15/08/1990", "Male", "9101 2233 4455", ADDR)),
         save("T02-initial-and-year", "pan.png", pan("Rahul K. Sharma", "Mohan Sharma", "15/08/1991", "ABCPR4821K"))]
    entry("T02-initial-and-year", "Extra initial in the name; birth year differs by one",
          "Name: not predicted with confidence (harmless extra initial or low partial-name; record which). DOB: conflict, year difference (high)", f)

    # T03 day/month swapped
    f = [save("T03-dob-day-month-swapped", "aadhaar.png", aadhaar("Neha Verma", "Anil Verma", "12/03/1992", "Female", "8123 4567 9012", ADDR)),
         save("T03-dob-day-month-swapped", "pan.png", pan("Neha Verma", "Anil Verma", "03/12/1992", "BXPNV7745M"))]
    entry("T03-dob-day-month-swapped", "Day and month swapped", "DOB: conflict, low severity", f)

    # T04 one digit in the day
    f = [save("T04-dob-one-digit", "aadhaar.png", aadhaar("Amit Joshi", "Sunil Joshi", "15/08/1995", "Male", "7234 5678 1234", ADDR)),
         save("T04-dob-one-digit", "pan.png", pan("Amit Joshi", "Sunil Joshi", "16/08/1995", "CDQAJ3390P"))]
    entry("T04-dob-one-digit", "One digit of the day differs", "DOB: conflict, date_minor_difference (medium)", f)

    # T05 big year gap
    f = [save("T05-dob-15-years", "aadhaar.png", aadhaar("Vikas Rathore", "Bhanu Rathore", "12/03/1982", "Male", "6345 6789 2345", ADDR)),
         save("T05-dob-15-years", "pan.png", pan("Vikas Rathore", "Bhanu Rathore", "12/03/1997", "DEFVR1182Q"))]
    entry("T05-dob-15-years", "Birth year 15 years apart", "DOB: conflict, date_year_difference (high)", f)

    # T06 honorific and capitals
    f = [save("T06-honorific-capitals", "aadhaar.png", aadhaar("SHRI SURESH KUMAR GUPTA", "RAMESH GUPTA", "05/01/1980", "Male", "5456 7890 3456", ADDR)),
         save("T06-honorific-capitals", "pan.png", pan("Suresh Kumar Gupta", "Ramesh Gupta", "05/01/1980", "EFGSG5521R"))]
    entry("T06-honorific-capitals", "Capital letters and a title on one card", "No conflict; name harmless (honorific / case)", f)

    # T07 spelling variant
    f = [save("T07-spelling-variant", "aadhaar.png", aadhaar("Sunita Choudhary", "Ramlal Choudhary", "07/09/1988", "Female", "4567 8901 4567", ADDR)),
         save("T07-spelling-variant", "pan.png", pan("Suneeta Chowdhary", "Ramlal Chowdhary", "07/09/1988", "FGHSC8801S"))]
    entry("T07-spelling-variant", "Same sound, different spelling", "Name and parent: harmless spelling_variant", f)

    # T08 different person
    f = [save("T08-different-person", "aadhaar.png", aadhaar("Rahul Verma", "Dinesh Verma", "02/06/1991", "Male", "3678 9012 5678", ADDR)),
         save("T08-different-person", "pan.png", pan("Sanjay Singh", "Harpal Singh", "02/06/1991", "GHJSS3304T"))]
    entry("T08-different-person", "A card of someone else", "Name and parent: conflict, different_name (critical)", f)

    # T09 similar but different
    f = [save("T09-similar-name", "aadhaar.png", aadhaar("Rahul Verma", "Dinesh Verma", "02/06/1991", "Male", "3678 9012 5678", ADDR)),
         save("T09-similar-name", "pan.png", pan("Rohit Verma", "Dinesh Verma", "02/06/1991", "HJKRV9905U"))]
    entry("T09-similar-name", "High similarity, different person", "Name: conflict, different_name (critical). Must NOT be harmless", f)

    # T10 gender mismatch
    f = [save("T10-gender-mismatch", "aadhaar.png", aadhaar("Kiran Patel", "Bharat Patel", "20/04/1994", "Female", "2789 0123 6789", ADDR)),
         save("T10-gender-mismatch", "aadhaar-second.png", aadhaar("Kiran Patel", "Bharat Patel", "20/04/1994", "Male", "2789 0123 6789", ADDR))]
    entry("T10-gender-mismatch", "Two ID cards, gender differs", "Gender: conflict, gender_difference (high)", f)

    # T11 income, lakh notation and a big gap
    f = [save("T11-income-gap", "income-low.png", income("Meena Yadav", "Shivnath Yadav", "Rs. 60,000 per year", "IC/2026/011208", ADDR, "11/02/2026")),
         save("T11-income-gap", "income-high.png", income("Meena Yadav", "Shivnath Yadav", "Rs. 4,80,000 per year", "IC/2025/030417", ADDR, "04/08/2025"))]
    entry("T11-income-gap", "Income 60,000 against 4,80,000 (lakh notation)", "Income: conflict, income_difference (critical)", f)

    # T12 masked ID and address formatting
    f = [save("T12-masked-id-address-format", "aadhaar.png", aadhaar("Pooja Nair", "Gopalan Nair", "15/08/1995", "Female", "XXXX XXXX 6634", "3 Lake View Colony, Jabalpur, Madhya Pradesh - 482001")),
         save("T12-masked-id-address-format", "aadhaar-second.png", aadhaar("Pooja Nair", "Gopalan Nair", "15/08/1995", "Female", "9876 5432 6634", "3 Lake View Clny, Jabalpur, MP - 482001"))]
    entry("T12-masked-id-address-format", "Masked ID against full ID; abbreviated address",
          "No conflict on ID (masked positions agree); address harmless formatting", f)

    # T13 Hindi against English
    try:
        _font(_DEVA, 20)
        f = [save("T13-hindi-vs-english", "aadhaar-hindi.png",
                  aadhaar("रमेश कुमार शर्मा", "कृष्ण प्रसाद शर्मा", "14/09/1979", "पुरुष", "5512 3456 7890",
                          "18 गांधी चौक, देवास, मध्य प्रदेश - 455001", hindi=True)),
             save("T13-hindi-vs-english", "pan.png", pan("Ramesh Kumar Sharma", "Krishna Prasad Sharma", "14/09/1979", "JKLRS7753V"))]
        entry("T13-hindi-vs-english", "Hindi card against English card", "Name and parent: harmless transliteration", f)
    except SystemExit:
        print("Skipped T13: no Devanagari font found.")

    # T14 same card, scan-quality damage (for guide row 7.8)
    base = aadhaar("Rahul Sharma", "Mohan Sharma", "15/08/1990", "Male", "9101 2233 4455", ADDR)
    f = [save("T14-scan-quality", "clean.png", base),
         save("T14-scan-quality", "rotated-5deg.png", base.rotate(5, expand=True, fillcolor="white")),
         save("T14-scan-quality", "blurred.png", base.filter(ImageFilter.GaussianBlur(2.2))),
         save("T14-scan-quality", "low-resolution.png", base.resize((300, 187)).resize((W, H))),
         save("T14-scan-quality", "jpeg-heavy-compression.jpg", base, "JPEG", quality=12)]
    entry("T14-scan-quality", "One card, five image conditions",
          "NOT DEFINED: upload each alone and record which fields are read. Same values as T01 Aadhaar expected where readable", f)

    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(manifest)} sets, {sum(len(m['documents']) for m in manifest)} files -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(build())
