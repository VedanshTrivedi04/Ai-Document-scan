"""
Handwritten signatures on the documents of an identity bundle, and whether two
documents carry the same one. Local and classical: OpenCV and NumPy only, no
trained model, no cloud call (Groq and the other text-only providers cannot
look at images).

1. Finding the signature. A signature sits next to its printed label
   ("Signature", "हस्ताक्षर"). The OCR word boxes locate the label; the ink
   just above it, or just to its right, is the signature. A document with no
   such label has no signature found: it is reported as "not found", never as
   a mismatch.
2. Describing it. The ink is cropped, binarised and fitted into a 64 x 128
   box (aspect ratio kept), so size, position and pen width stop mattering.
3. Comparing two. Three measures on the fitted ink are averaged: how far the
   strokes of one lie from the strokes of the other (chamfer), how much the two
   overlap once slightly thickened, and how alike their stroke directions are.

What this is NOT: signature verification in the forensic sense. One person's
signature differs from one signing to the next, a printed or photographed one
is small and soft, and a forger who copies the shape scores high. The result is
advice for a reviewer ("clearly alike", "please look", "clearly different"),
and the thresholds are provisional until measured on real signatures
(docs/SIGNATURE_CHECK.md). The stored description is a small picture of the
ink; it is removed from every API response (`public_signatures`).
"""
from __future__ import annotations

import base64
import logging
import zlib
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger("fddt.signature")

TEMPLATE_W, TEMPLATE_H = 128, 64
_MAX_SIGNATURES_PER_PAGE = 2
_LABEL_PREFIXES = ("signa", "sinatur", "signt", "हस्ता", "हस्त", "sign.")
_MIN_INK_PIXELS = 60
_MIN_STROKES = 1  # a connected cursive signature is a single stroke

# Verdict lines on the combined score (0..1). Provisional: see the module note.
MATCH_THRESHOLD = 0.55
DIFFERENT_THRESHOLD = 0.40

STATUS_OK, STATUS_FAILED = "ok", "failed"
_PRIVATE_KEYS = ("template",)


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------

def _is_label(text: str) -> bool:
    folded = text.strip().casefold().strip(":;|/()[]")
    return len(folded) >= 4 and any(folded.startswith(p) for p in _LABEL_PREFIXES)


def _ink_mask(gray: np.ndarray) -> np.ndarray:
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    block = max(15, (min(gray.shape) // 8) | 1)
    return cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, block, 12
    )


def _clean_ink(mask: np.ndarray) -> np.ndarray:
    """Specks and long ruled lines removed."""
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    height, width = mask.shape
    keep = np.zeros_like(mask)
    for index in range(1, count):
        x, y, w, h, area = stats[index]
        if area < 12:
            continue
        if (w > 0.9 * width and h < 0.12 * height) or (h > 0.9 * height and w < 0.12 * width):
            continue  # a ruled line, a border
        keep[labels == index] = 255
    return keep


def _main_cluster(region: np.ndarray) -> tuple[int, int, int, int] | None:
    """The heaviest group of ink in the region (strokes of one signature run
    together once closed up), so a stray mark at the edge of the window is left out."""
    height, width = region.shape
    closed = cv2.morphologyEx(region, cv2.MORPH_CLOSE, cv2.getStructuringElement(
        cv2.MORPH_RECT, (max(3, width // 14), max(3, height // 8))))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
    best, best_ink = None, 0
    for index in range(1, count):
        x, y, w, h, _ = stats[index]
        ink = int(np.count_nonzero(region[y: y + h, x: x + w]))
        if ink > best_ink:
            best, best_ink = (int(x), int(y), int(w), int(h)), ink
    return best if best_ink >= _MIN_INK_PIXELS else None


def _ink_box(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    """Tight box around the ink, ignoring far-off specks; None if too little."""
    if int(np.count_nonzero(mask)) < _MIN_INK_PIXELS:
        return None
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    largest = max((stats[i][4] for i in range(1, count)), default=0)
    # background specks are tiny next to the strokes of a signature
    parts = [stats[i] for i in range(1, count) if stats[i][4] >= max(8, 0.06 * largest)]
    if len(parts) < 1:
        return None
    x0 = min(p[0] for p in parts)
    y0 = min(p[1] for p in parts)
    x1 = max(p[0] + p[2] for p in parts)
    y1 = max(p[1] + p[3] for p in parts)
    return x0, y0, x1 - x0, y1 - y0


def describe(ink: np.ndarray) -> np.ndarray:
    """A binary ink image fitted into TEMPLATE_H x TEMPLATE_W, aspect kept."""
    box = _ink_box(ink)
    x, y, w, h = box if box else (0, 0, ink.shape[1], ink.shape[0])
    crop = ink[y: y + h, x: x + w]
    scale = min((TEMPLATE_W - 8) / max(w, 1), (TEMPLATE_H - 8) / max(h, 1))
    new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
    resized = cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_AREA)
    resized = (resized > 60).astype(np.uint8) * 255
    canvas = np.zeros((TEMPLATE_H, TEMPLATE_W), np.uint8)
    top, left = (TEMPLATE_H - new_h) // 2, (TEMPLATE_W - new_w) // 2
    canvas[top: top + new_h, left: left + new_w] = resized
    # one pen width, whatever the original: close the gaps, then thin to a stroke of ~2 px
    return cv2.dilate(canvas, np.ones((2, 2), np.uint8))


def _pack(template: np.ndarray) -> str:
    return base64.b64encode(zlib.compress(np.packbits(template > 0).tobytes(), 9)).decode()


def _unpack(text: str) -> np.ndarray:
    bits = np.unpackbits(np.frombuffer(zlib.decompress(base64.b64decode(text)), np.uint8))
    return (bits[: TEMPLATE_W * TEMPLATE_H].reshape(TEMPLATE_H, TEMPLATE_W) * 255).astype(np.uint8)


def _candidates(label: dict[str, float]) -> list[tuple[float, float, float, float]]:
    """Normalised regions (x0, y0, x1, y1) where ink for this label may be:
    above it (cards), to its right (forms), below it (forms)."""
    x, y, w, h = label["x"], label["y"], label["width"], label["height"]
    reach = min(max(h * 6.0, 0.12), 0.2)
    wide = max(w * 3.0, 0.5)
    cx = x + w / 2
    return [
        (cx - wide / 2, y - reach, cx + wide / 2, y - h * 0.15),
        (x + w * 1.02, y - h * 1.2, x + w + wide, y + h * 2.2),
        (cx - wide / 2, y + h * 1.1, cx + wide / 2, y + h + reach),
    ]


def read_labels(image: np.ndarray) -> list[dict[str, Any]]:
    """Signature labels the page's own OCR missed (faint blue print on a card):
    one more Tesseract pass over the enlarged, contrast-levelled page, looking
    only for the label word. [] when Tesseract is not available."""
    import shutil
    import subprocess
    import tempfile
    from pathlib import Path

    from app.core.config import settings

    command = settings.tesseract_cmd or shutil.which("tesseract")
    tessdata = settings.tessdata_dir
    if not command or not tessdata or not Path(tessdata).is_dir():
        return []
    height, width = image.shape[:2]
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    words: list[dict[str, Any]] = []
    # the whole page, then its lower part alone (where a card's label sits) at a larger scale
    for top_fraction, psm in ((0.7, 6), (0.85, 11), (0.0, 6), (0.7, 11)):
        top = int(height * top_fraction)
        part = grey[top:]
        factor = min(3.0, 3000 / max(width, 1))
        big = cv2.createCLAHE(2.0, (8, 8)).apply(
            cv2.resize(part, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "p.png"
            cv2.imwrite(str(path), big)
            try:
                done = subprocess.run(
                    [command, str(path), "stdout", "--tessdata-dir", str(Path(tessdata).resolve()), "-l", "eng+hin",
                     "--psm", str(psm), "-c", "tessedit_create_tsv=1"],
                    capture_output=True, timeout=60, check=True,
                )
            except (OSError, subprocess.SubprocessError):
                continue
        big_h, big_w = big.shape[:2]
        for row in done.stdout.decode("utf-8", errors="replace").splitlines()[1:]:
            cells = row.split("	")
            if len(cells) < 12 or cells[0] != "5" or not _is_label(cells[11]):
                continue
            left, y_top, w, h = (int(v) for v in cells[6:10])
            words.append({
                "text": cells[11].strip(), "x": left / big_w,
                "y": (top + y_top / factor) / height, "width": w / big_w, "height": h / factor / height,
            })
        if words:
            break
    return words


def _without_printed(mask: np.ndarray, words: list[dict[str, Any]], exclude: list[dict[str, float]]) -> np.ndarray:
    """The ink mask with every OCR word and every excluded box (faces) blanked."""
    height, width = mask.shape
    out = mask.copy()
    for box in [*words, *exclude]:
        x0, y0 = int(box["x"] * width) - 2, int(box["y"] * height) - 2
        x1, y1 = int((box["x"] + box["width"]) * width) + 2, int((box["y"] + box["height"]) * height) + 2
        out[max(0, y0): max(0, y1), max(0, x0): max(0, x1)] = 0
    return out


def _handwriting_blob(
    mask: np.ndarray, words: list[dict[str, Any]], exclude: list[dict[str, float]]
) -> tuple[int, int, int, int, np.ndarray] | None:
    """No label found: the most signature-like piece of ink that is not printed
    text, a face, a QR code (dense, square) or a stamp (round). A signature is
    wide, made of a few loose strokes, and fills little of its own box."""
    height, width = mask.shape
    ink = _without_printed(mask, words, exclude)
    closed = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, cv2.getStructuringElement(
        cv2.MORPH_RECT, (max(5, int(width * 0.025)), max(3, int(height * 0.012)))))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
    best = None
    for index in range(1, count):
        x, y, w, h, _area = stats[index]
        if not (0.05 * width <= w <= 0.5 * width and 0.025 * height <= h <= 0.3 * height):
            continue
        if not 1.3 <= w / h <= 10:
            continue
        piece = ink[y: y + h, x: x + w]
        fill = np.count_nonzero(piece) / (w * h)
        strokes = cv2.connectedComponents(piece)[0] - 1
        if not 0.04 <= fill <= 0.42 or strokes < _MIN_STROKES:
            continue
        score = int(np.count_nonzero(piece))
        if best is None or score > best[0]:
            best = (score, x, y, w, h, piece)
    return None if best is None else best[1:]


def find_on_page(
    image: np.ndarray, words: list[dict[str, float | str]], page: int, exclude: list[dict[str, float]] | None = None
) -> list[dict[str, Any]]:
    """Signatures on one page. `words`: OCR words as {text, x, y, width, height}
    in page fractions; `exclude`: boxes that are not signatures (faces).
    Returns [{bounding_box, ink, template}]."""
    exclude = exclude or []
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    mask = _clean_ink(_ink_mask(gray))
    found: list[dict[str, Any]] = []
    labels = [w for w in words if _is_label(str(w["text"]))]
    if not labels:
        labels = read_labels(image)
        words = [*words, *labels]  # so the label's own print is blanked in the fallback
    for label in labels:
        best = None
        for x0, y0, x1, y1 in _candidates(label):
            px0, py0 = max(0, int(x0 * width)), max(0, int(y0 * height))
            px1, py1 = min(width, int(x1 * width)), min(height, int(y1 * height))
            if px1 - px0 < 12 or py1 - py0 < 8:
                continue
            region = mask[py0:py1, px0:px1].copy()
            box = _main_cluster(region)
            if box is None:
                continue
            bx, by, bw, bh = box
            strokes = cv2.connectedComponents(region[by: by + bh, bx: bx + bw])[0] - 1
            ink = int(np.count_nonzero(region[by: by + bh, bx: bx + bw]))
            if strokes < _MIN_STROKES or bw < 0.02 * width or ink < _MIN_INK_PIXELS:
                continue
            if bh > 0.9 * (py1 - py0) and bw > 0.9 * (px1 - px0):
                continue  # ink filling the whole window: a background pattern, not a signature
            # The regions are in order of likelihood (above a card's label, then a form's
            # right and below): the first one with ink wins.
            best = (ink, px0 + bx, py0 + by, bw, bh, region[by: by + bh, bx: bx + bw])
            break
        if best is None:
            continue
        _, bx, by, bw, bh, ink_crop = best
        found.append(_entry(page, width, height, bx, by, bw, bh, ink_crop))
    found.sort(key=lambda s: -s["ink"])
    return found[:_MAX_SIGNATURES_PER_PAGE]


def _entry(page, width, height, bx, by, bw, bh, ink_crop) -> dict[str, Any]:
    return {
        "bounding_box": {
            "page": page,
            "x": round(float(bx) / width, 4), "y": round(float(by) / height, 4),
            "width": round(float(bw) / width, 4), "height": round(float(bh) / height, 4),
        },
        "ink": int(np.count_nonzero(ink_crop)),
        "template": _pack(describe(ink_crop)),
    }


def analyse_document(
    pages: list[tuple[np.ndarray, list[dict[str, Any]]]], exclude_by_page: dict[int, list[dict[str, float]]] | None = None
) -> dict[str, Any]:
    """The `extracted_fields["signatures"]` block: [(page image, OCR words)] ->
    {"status": ok|failed, "items": [...]}. Never raises."""
    try:
        items: list[dict[str, Any]] = []
        for number, (image, words) in enumerate(pages, start=1):
            items.extend(find_on_page(image, words, number, (exclude_by_page or {}).get(number)))
        items.sort(key=lambda s: -s["ink"])
        return {"status": STATUS_OK, "items": items[:3]}
    except Exception as exc:  # noqa: BLE001 - a bad image never fails the document
        logger.warning("signature analysis failed: %s", exc)
        return {"status": STATUS_FAILED, "items": [], "error": str(exc)[:300]}


# ---------------------------------------------------------------------------
# Comparing
# ---------------------------------------------------------------------------

def _chamfer(a: np.ndarray, b: np.ndarray) -> float:
    """1 when every stroke pixel of one lies on a stroke of the other; falls as
    they drift apart. Symmetric."""
    def one_way(src: np.ndarray, dst: np.ndarray) -> float:
        dist = cv2.distanceTransform((dst == 0).astype(np.uint8), cv2.DIST_L2, 3)
        return float(dist[src > 0].mean()) if np.any(src > 0) else 99.0

    mean = (one_way(a, b) + one_way(b, a)) / 2
    return float(np.exp(-mean / 1.5))


def _overlap(a: np.ndarray, b: np.ndarray) -> float:
    kernel = np.ones((5, 5), np.uint8)
    da, db = cv2.dilate(a, kernel) > 0, cv2.dilate(b, kernel) > 0
    union = np.count_nonzero(da | db)
    return float(np.count_nonzero(da & db) / union) if union else 0.0


def _orientation(a: np.ndarray, b: np.ndarray) -> float:
    def histogram(img: np.ndarray) -> np.ndarray:
        blur = cv2.GaussianBlur(img.astype(np.float32), (0, 0), 1.5)
        gx, gy = cv2.Sobel(blur, cv2.CV_32F, 1, 0), cv2.Sobel(blur, cv2.CV_32F, 0, 1)
        magnitude, angle = cv2.cartToPolar(gx, gy, angleInDegrees=True)
        angle = np.mod(angle, 180)
        cells = []
        for row in range(8):
            for column in range(16):
                ys, xs = slice(row * 8, (row + 1) * 8), slice(column * 8, (column + 1) * 8)
                hist, _ = np.histogram(angle[ys, xs], bins=8, range=(0, 180), weights=magnitude[ys, xs])
                cells.append(hist)
        vector = np.concatenate(cells)
        norm = np.linalg.norm(vector)
        return vector / norm if norm else vector

    return float(max(0.0, np.dot(histogram(a), histogram(b))))


def _profile(a: np.ndarray, b: np.ndarray) -> float:
    """Where along the signature the ink sits (column totals), correlated."""
    pa, pb = a.sum(0).astype(np.float64), b.sum(0).astype(np.float64)
    pa -= pa.mean()
    pb -= pb.mean()
    norm = np.linalg.norm(pa) * np.linalg.norm(pb)
    return max(0.0, float(pa @ pb / norm)) if norm else 0.0


def similarity(template_a: str, template_b: str) -> float:
    """0..1 how alike two fitted signatures are. Chamfer, stroke direction and
    ink profile, equally weighted: the three that told typed names apart best
    on synthetic handwriting (area under the ROC curve 0.98, against 0.90 for
    the best single one before)."""
    a, b = _unpack(template_a), _unpack(template_b)
    return round((_chamfer(a, b) + _orientation(a, b) + _profile(a, b)) / 3, 3)


def best_match(
    items_a: list[dict[str, Any]], items_b: list[dict[str, Any]]
) -> tuple[float, dict[str, Any], dict[str, Any]] | None:
    best = None
    for sa in items_a:
        for sb in items_b:
            if not sa.get("template") or not sb.get("template"):
                continue
            score = similarity(sa["template"], sb["template"])
            if best is None or score > best[0]:
                best = (score, sa, sb)
    return best


def public_signatures(extracted_fields: dict[str, Any] | None) -> dict[str, Any] | None:
    """`extracted_fields` as a client may see it: the stored ink pictures removed."""
    if not isinstance(extracted_fields, dict) or not isinstance(extracted_fields.get("signatures"), dict):
        return extracted_fields
    block = dict(extracted_fields["signatures"])
    block["items"] = [
        {k: v for k, v in item.items() if k not in _PRIVATE_KEYS}
        for item in block.get("items") or [] if isinstance(item, dict)
    ]
    return {**extracted_fields, "signatures": block}
