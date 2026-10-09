"""
Downloads the two pre-trained face models (about 39 MB) into FACE_MODEL_DIR.

    python -m app.services.face_models

Both come from the OpenCV Zoo (Apache-2.0) and are checked against a pinned
SHA-256 so a changed or truncated download is rejected. The application never
downloads anything by itself.
"""
from __future__ import annotations

import hashlib
import sys
import urllib.request

from app.services.face_service import DETECTOR_FILE, RECOGNIZER_FILE, model_dir

_BASE = "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models"
MODELS = {
    DETECTOR_FILE: (
        f"{_BASE}/face_detection_yunet/{DETECTOR_FILE}",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    ),
    RECOGNIZER_FILE: (
        f"{_BASE}/face_recognition_sface/{RECOGNIZER_FILE}",
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
    ),
}


def _sha256(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(force: bool = False) -> int:
    folder = model_dir()
    folder.mkdir(parents=True, exist_ok=True)
    for name, (url, expected) in MODELS.items():
        target = folder / name
        if target.is_file() and not force and (expected is None or _sha256(target) == expected):
            print(f"{name}: already present")
            continue
        print(f"{name}: downloading {url}")
        partial = target.with_suffix(".part")
        urllib.request.urlretrieve(url, partial)
        if partial.stat().st_size < 100_000:
            partial.unlink()
            print(f"{name}: download looks wrong (too small)", file=sys.stderr)
            return 1
        if expected is not None and _sha256(partial) != expected:
            partial.unlink()
            print(f"{name}: SHA-256 mismatch", file=sys.stderr)
            return 1
        partial.replace(target)
        print(f"{name}: ok  sha256={_sha256(target)}")
    return 0


if __name__ == "__main__":
    sys.exit(download(force="--force" in sys.argv))
