"""
How often do the image-forensics checks catch tampering, and how often do they
cry wolf? (AIML_Deep_Analysis.md listed this as unmeasured: the sample
documents held no tampered, image-bearing page.)

Bases are real card pages of the synthetic identity bundles, made to look like
scans (sensor noise, uneven light, JPEG) and embedded as one raster image per
PDF page, so ELA applies. Each base is then:

    clean         left alone                                (control)
    resaved       the whole scan re-saved once more         (control: no edit)
    copy_move     a block of writing copied elsewhere on the page
    splice        a patch from a different scan pasted in
    retype        a value wiped and typed over, then re-saved

and the final file goes through the same render + `run_ela_check` +
`run_copy_move_check` the tampering task uses.

    python -m scripts.forensics_sensitivity [--per-kind N] [--json FILE]
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import cv2
import numpy as np
import pymupdf

from app.services.forensics.copy_move import run_copy_move_check
from app.services.forensics.ela import run_ela_check
from app.services.forensics.pdf_render import render_pdf_pages

BUNDLES = Path(__file__).resolve().parents[2] / "sample-documents" / "identity-bundles"
KINDS = ("clean", "resaved", "copy_move", "splice", "retype")


def _bases() -> list[np.ndarray]:
    """Card pages as BGR images at 200 dpi."""
    out = []
    for path in sorted(BUNDLES.glob("*/*.pdf")):
        with pymupdf.open(path) as doc:
            pix = doc[0].get_pixmap(dpi=200, alpha=False)
        out.append(cv2.cvtColor(np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3), cv2.COLOR_RGB2BGR))
    return out


def _scan(image: np.ndarray, rng: np.random.Generator, quality: int = 85) -> np.ndarray:
    """Make a clean render look like a scanned page: uneven light, sensor noise, JPEG."""
    h, w = image.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    light = 1.0 - 0.10 * (((xx / w - 0.5) ** 2 + (yy / h - 0.5) ** 2))
    noisy = image.astype(np.float32) * light[..., None] + rng.normal(0, 3.0, image.shape)
    page = np.clip(noisy, 0, 255).astype(np.uint8)
    return cv2.imdecode(cv2.imencode(".jpg", page, [cv2.IMWRITE_JPEG_QUALITY, quality])[1], cv2.IMREAD_COLOR)


def _jpeg(image: np.ndarray, quality: int = 85) -> np.ndarray:
    return cv2.imdecode(cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])[1], cv2.IMREAD_COLOR)


def _text_box(image: np.ndarray, rng: random.Random) -> tuple[int, int, int, int]:
    """A region that holds ink (a row of text), found by the dark pixels."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    ys, xs = np.where(gray < 120)
    pick = rng.randrange(len(ys))
    cx, cy = int(xs[pick]), int(ys[pick])
    return cx, cy, 300, 70


def make(kind: str, base: np.ndarray, other: np.ndarray, seed: int) -> np.ndarray:
    nrng, rng = np.random.default_rng(seed), random.Random(seed)
    scan = _scan(base, nrng)
    h, w = scan.shape[:2]
    if kind == "clean":
        return scan
    if kind == "resaved":
        return _jpeg(scan, 85)
    img = scan.copy()
    if kind == "copy_move":
        bw, bh = int(w * 0.30), int(h * 0.22)
        gray = cv2.cvtColor(scan, cv2.COLOR_BGR2GRAY)
        for _ in range(40):  # copying blank paper hides nothing: the source holds writing
            sx, sy = rng.randrange(0, w - bw), rng.randrange(0, h - bh)
            if (gray[sy: sy + bh, sx: sx + bw] < 120).mean() >= 0.03:
                break
        dx, dy = (sx + w // 2) % (w - bw), (sy + h // 2) % (h - bh)
        img[dy: dy + bh, dx: dx + bw] = scan[sy: sy + bh, sx: sx + bw]
    elif kind == "splice":
        donor = _jpeg(_scan(other, np.random.default_rng(seed + 1), 95), 95)
        bw, bh = int(w * 0.28), int(h * 0.18)
        sx, sy = rng.randrange(0, donor.shape[1] - bw), rng.randrange(0, donor.shape[0] - bh)
        dx, dy = rng.randrange(0, w - bw), rng.randrange(0, h - bh)
        img[dy: dy + bh, dx: dx + bw] = cv2.resize(donor[sy: sy + bh, sx: sx + bw], (bw, bh))
    elif kind == "retype":
        x, y, bw, bh = _text_box(img, rng)
        x, y = min(x, w - bw - 1), min(max(y - 40, 0), h - bh - 1)
        paper = np.median(img[y: y + bh, x: x + bw].reshape(-1, 3), axis=0)
        img[y: y + bh, x: x + bw] = paper
        cv2.putText(img, f"{rng.randrange(10**6, 10**7)}", (x + 4, y + bh - 20), cv2.FONT_HERSHEY_DUPLEX, 1.4, (20, 20, 20), 2)
    return _jpeg(img, 85)


def to_pdf(image: np.ndarray) -> bytes:
    jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tobytes()
    doc = pymupdf.open()
    h, w = image.shape[:2]
    page = doc.new_page(width=w * 72 / 200, height=h * 72 / 200)
    page.insert_image(page.rect, stream=jpeg)
    return doc.tobytes()


def evaluate(per_kind: int) -> dict:
    bases = _bases()
    rows = {k: {"n": 0, "ela": 0, "copy_move": 0, "either": 0, "ela_applicable": 0} for k in KINDS}
    for kind in KINDS:
        for i in range(per_kind):
            base, other = bases[i % len(bases)], bases[(i * 7 + 3) % len(bases)]
            pages = render_pdf_pages(to_pdf(make(kind, base, other, seed=1000 + i)))
            ela, cm = run_ela_check(pages), run_copy_move_check(pages)
            row = rows[kind]
            row["n"] += 1
            row["ela_applicable"] += ela["result"] != "not_applicable"
            row["ela"] += ela["result"] == "flag"
            row["copy_move"] += cm["result"] == "flag"
            row["either"] += ela["result"] == "flag" or cm["result"] == "flag"
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--per-kind", type=int, default=24)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    rows = evaluate(args.per_kind)
    print(f"{'kind':<11}{'n':>4}{'ELA flags':>11}{'copy-move':>11}{'either':>9}   (ELA applied to {{}} pages)")
    for kind, r in rows.items():
        print(f"{kind:<11}{r['n']:>4}{r['ela']:>8}/{r['n']:<2}{r['copy_move']:>8}/{r['n']:<2}{r['either']:>6}/{r['n']:<2}   {r['ela_applicable']}")
    if args.json:
        args.json.write_text(json.dumps(rows, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
