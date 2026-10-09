"""
Photographs of people on the documents of an identity bundle, and whether
two documents show the same person.

Two small pre-trained models run on this machine through OpenCV (no cloud
call, no training, nothing leaves the server):

* YuNet finds the faces on a page,
* SFace turns each face into a 128-number description.

Two faces are the same person when their descriptions point the same way
(cosine similarity). The thresholds below were chosen on printed-card-quality
photographs, not on clean portraits (docs/FACE_CHECK.md): a photograph on an
identity card is small, printed and often years old, so a score in between is
reported as "please look", never as a different person.

What is stored per document (`extracted_fields["faces"]`) is the place of each
face on the page and its description. The description is a biometric
template: it is removed from every API response (`public_extracted_fields`)
and used only by the comparison.

The model files are not part of the repository: `python -m
app.services.face_models` downloads them (about 39 MB). Without them the
check reports "unavailable" rather than guessing.
"""
from __future__ import annotations

import io
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import settings

logger = logging.getLogger("fddt.face")

DETECTOR_FILE = "face_detection_yunet_2023mar.onnx"
RECOGNIZER_FILE = "face_recognition_sface_2021dec.onnx"

# A page is looked at this sharply; a photo on a card is ~25 mm wide, so about
# 200 px at this resolution.
RENDER_DPI = 250
_MAX_PIXELS = 36_000_000
_MIN_IMAGE_SIDE = 900  # smaller images (a phone crop of a card) are enlarged
_MAX_PAGES = 12  # pages / frames read per document
_UPSCALE_BELOW = 2600  # when nothing is found, look again at twice the size if the image is smaller than this
_DETECTION_SCORE = 0.75
_MIN_FACE_PIXELS = 36  # a face narrower than this is a logo, a stamp, or too small to compare
_MAX_FACES_PER_DOCUMENT = 6

# Cosine similarity of two SFace descriptions. OpenCV publishes 0.363 as the
# same-person cut-off on clean portraits, but on card-quality photographs
# (400 tiny grey photos of 40 people, placed on a card and JPEG-compressed)
# 4% of different-person pairs scored above it. Measured on that set:
#
#     similarity >= 0.45:  99.4% of same-person pairs,  0.55% of different pairs
#     similarity <  0.25:   0.0% of same-person pairs, 75.5% of different pairs
#
# So a pair is "the same person" from 0.45, "different people" below 0.25, and
# in between a human looks: the cautious direction for a fraud check. The
# measurement has no age gap between photographs, so a real old/new pair can
# score lower; that lands in "please look", not in "different person".
MATCH_THRESHOLD = 0.45
DIFFERENT_THRESHOLD = 0.25

STATUS_OK = "ok"
STATUS_UNAVAILABLE = "unavailable"
STATUS_FAILED = "failed"

# Keys that never leave the server.
_PRIVATE_FACE_KEYS = ("embedding",)


class FaceModelsUnavailable(RuntimeError):
    """The model files are not installed (python -m app.services.face_models)."""


@dataclass(frozen=True)
class Face:
    page: int
    x: float
    y: float
    width: float
    height: float
    score: float
    pixels: int
    embedding: tuple[float, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "bounding_box": {
                "page": self.page,
                "x": round(self.x, 4),
                "y": round(self.y, 4),
                "width": round(self.width, 4),
                "height": round(self.height, 4),
            },
            "score": round(self.score, 3),
            "pixels": self.pixels,
            "embedding": [round(v, 5) for v in self.embedding],
        }


def model_dir() -> Path:
    return Path(settings.face_model_dir)


def models_installed() -> bool:
    folder = model_dir()
    return (folder / DETECTOR_FILE).is_file() and (folder / RECOGNIZER_FILE).is_file()


_models: tuple[Any, Any] | None = None
# The detector keeps its input size between calls and the workers may run
# several documents in threads (Celery's thread pool, used on Windows): one
# document at a time goes through the models.
_models_lock = threading.Lock()


def _load_models():
    """(detector, recognizer), created once per process."""
    global _models
    with _models_lock:
        if _models is None:
            if not models_installed():
                raise FaceModelsUnavailable(
                    f"Face models not found in {model_dir()}. Run: python -m app.services.face_models"
                )
            import cv2

            detector = cv2.FaceDetectorYN.create(
                str(model_dir() / DETECTOR_FILE), "", (320, 320), _DETECTION_SCORE, 0.3, 5000
            )
            recognizer = cv2.FaceRecognizerSF.create(str(model_dir() / RECOGNIZER_FILE), "")
            _models = (detector, recognizer)
        return _models


# ---------------------------------------------------------------------------
# Reading the pages of a document as images
# ---------------------------------------------------------------------------

def _page_images(content: bytes) -> list[np.ndarray]:
    """Each page of a PDF, or the image itself, as a BGR array."""
    import cv2

    if content[:5] == b"%PDF-":
        import pymupdf

        images = []
        with pymupdf.open(stream=content, filetype="pdf") as document:
            for index, page in enumerate(document):
                if index >= _MAX_PAGES:
                    break
                scale = RENDER_DPI / 72
                while page.rect.width * page.rect.height * scale * scale > _MAX_PIXELS:
                    scale *= 0.85
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
                array = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, 3)
                images.append(cv2.cvtColor(array, cv2.COLOR_RGB2BGR))
        return images

    return [_fit(image) for image in _decode_frames(content)]


def _fit(image: np.ndarray) -> np.ndarray:
    """Very large images are reduced (memory), small ones enlarged (faces)."""
    import cv2

    height, width = image.shape[:2]
    if height * width > _MAX_PIXELS:
        factor = (_MAX_PIXELS / (height * width)) ** 0.5
        return cv2.resize(image, None, fx=factor, fy=factor, interpolation=cv2.INTER_AREA)
    shortest = min(height, width)
    if shortest < _MIN_IMAGE_SIDE:
        factor = _MIN_IMAGE_SIDE / shortest
        return cv2.resize(image, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)
    return image


def _decode_frames(content: bytes) -> list[np.ndarray]:
    """Every frame of an image file as BGR. A phone photo is turned upright
    by its EXIF orientation; a multi-page TIFF gives one frame per page."""
    import cv2

    try:
        from PIL import Image, ImageOps

        frames = []
        with Image.open(io.BytesIO(content)) as image:
            for index in range(min(getattr(image, "n_frames", 1), _MAX_PAGES)):
                image.seek(index)
                upright = ImageOps.exif_transpose(image.convert("RGB"))
                frames.append(cv2.cvtColor(np.asarray(upright, dtype=np.uint8), cv2.COLOR_RGB2BGR))
        return frames
    except Exception:  # noqa: BLE001 - fall back to OpenCV's own decoder
        decoded = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
        return [] if decoded is None else [decoded]


def _faces_on_image(image: np.ndarray, page: int, detector, recognizer) -> list[Face]:
    height, width = image.shape[:2]
    detector.setInputSize((width, height))
    _, found = detector.detect(image)
    if found is None:
        return []
    faces = []
    for row in found:
        x, y, w, h = (float(v) for v in row[:4])
        score = float(row[-1])
        if min(w, h) < _MIN_FACE_PIXELS or score < _DETECTION_SCORE:
            continue
        aligned = recognizer.alignCrop(image, row)
        feature = recognizer.feature(aligned).flatten().astype(np.float64)
        norm = float(np.linalg.norm(feature))
        if norm == 0:
            continue
        x0, y0 = max(0.0, x), max(0.0, y)
        x1, y1 = min(float(width), x + w), min(float(height), y + h)
        faces.append(
            Face(
                page=page,
                x=x0 / width,
                y=y0 / height,
                width=(x1 - x0) / width,
                height=(y1 - y0) / height,
                score=score,
                pixels=int(min(w, h)),
                embedding=tuple((feature / norm).tolist()),
            )
        )
    return faces


def _unrotate(face: Face, code: int | None) -> Face:
    """A face found on a rotated copy of the page, placed back on the page as
    the reader sees it."""
    import cv2

    if code is None:
        return face
    x, y, w, h = face.x, face.y, face.width, face.height
    if code == cv2.ROTATE_90_CLOCKWISE:
        x, y, w, h = y, 1 - (x + w), h, w
    elif code == cv2.ROTATE_90_COUNTERCLOCKWISE:
        x, y, w, h = 1 - (y + h), x, h, w
    else:  # 180 degrees
        x, y = 1 - (x + w), 1 - (y + h)
    return Face(face.page, x, y, w, h, face.score, face.pixels, face.embedding)


def _faces_on_page(image: np.ndarray, page: int, detector, recognizer) -> list[Face]:
    """Faces on one page. A card photographed sideways or upside down, or a
    page where nothing is found at first, is looked at again: turned by 90,
    180 and 270 degrees, then at twice the size."""
    import cv2

    found = _faces_on_image(image, page, detector, recognizer)
    if found:
        return found
    for code in (cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_180, cv2.ROTATE_90_COUNTERCLOCKWISE):
        found = _faces_on_image(cv2.rotate(image, code), page, detector, recognizer)
        if found:
            return [_unrotate(face, code) for face in found]
    if max(image.shape[:2]) < _UPSCALE_BELOW:
        bigger = cv2.resize(image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        return _faces_on_image(bigger, page, detector, recognizer)
    return []


def detect_faces(content: bytes) -> list[Face]:
    """Every face on the pages of one document (a PDF or an image), largest
    first. Raises FaceModelsUnavailable when the models are not installed."""
    detector, recognizer = _load_models()
    faces: list[Face] = []
    with _models_lock:
        for page_number, image in enumerate(_page_images(content), start=1):  # pages are numbered from 1, like OCR boxes
            faces.extend(_faces_on_page(image, page_number, detector, recognizer))
    faces.sort(key=lambda f: f.width * f.height, reverse=True)
    return faces[:_MAX_FACES_PER_DOCUMENT]


def analyse_document(content: bytes) -> dict[str, Any]:
    """The `extracted_fields["faces"]` block for one document:
    {"status": ok|unavailable|failed, "items": [Face.as_dict()], "error"?}.
    Never raises: a document whose photographs cannot be read must not fail
    its extraction."""
    try:
        faces = detect_faces(content)
    except FaceModelsUnavailable as exc:
        return {"status": STATUS_UNAVAILABLE, "items": [], "error": str(exc)}
    except Exception as exc:  # noqa: BLE001 - a bad image never fails the document
        logger.warning("face analysis failed: %s", exc)
        return {"status": STATUS_FAILED, "items": [], "error": str(exc)[:300]}
    return {"status": STATUS_OK, "items": [f.as_dict() for f in faces]}


# ---------------------------------------------------------------------------
# Comparing
# ---------------------------------------------------------------------------

def similarity(a: list[float] | tuple[float, ...], b: list[float] | tuple[float, ...]) -> float:
    """Cosine similarity of two descriptions (stored already length-1)."""
    va, vb = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def best_match(
    faces_a: list[dict[str, Any]], faces_b: list[dict[str, Any]]
) -> tuple[float, dict[str, Any], dict[str, Any]] | None:
    """The most alike pair of faces between two documents: (similarity, face
    of a, face of b). Using the best pair keeps a small repeated "ghost"
    photograph or a second person on a family document from raising a
    conflict. None if either document has no usable face."""
    best: tuple[float, dict[str, Any], dict[str, Any]] | None = None
    for fa in faces_a:
        for fb in faces_b:
            if not fa.get("embedding") or not fb.get("embedding"):
                continue
            score = similarity(fa["embedding"], fb["embedding"])
            if best is None or score > best[0]:
                best = (score, fa, fb)
    return best


def public_extracted_fields(extracted_fields: dict[str, Any] | None) -> dict[str, Any] | None:
    """`extracted_fields` as an API client may see it: the face descriptions
    (biometric templates) removed, everything else untouched."""
    if not isinstance(extracted_fields, dict) or not isinstance(extracted_fields.get("faces"), dict):
        return extracted_fields
    faces = dict(extracted_fields["faces"])
    faces["items"] = [
        {k: v for k, v in item.items() if k not in _PRIVATE_FACE_KEYS}
        for item in faces.get("items") or []
        if isinstance(item, dict)
    ]
    return {**extracted_fields, "faces": faces}
