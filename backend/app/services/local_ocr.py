"""
Reading documents on this machine instead of with Azure Document
Intelligence (`OCR_PROVIDER=local`). For development and demonstrations
without a cloud account.

* A PDF page that already carries text is read directly from the PDF: exact
  words and positions, no recognition involved.
* A scanned page or an image is recognised with the Tesseract program
  (`TESSERACT_CMD`, or found on PATH). That needs its language files
  (`TESSDATA_DIR`), one per language in `OCR_LANGUAGES` (for example
  `eng+hin`).

Returns the same `OCRResult` as the Azure service, without tables, key-value
pairs or font estimates.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pymupdf

from app.core.config import settings
from app.services.ocr_service import OCRConfigurationError, OCROperationError, OCRPage, OCRResult, OCRWord

# A page with fewer words of its own than this is treated as a scan.
_MIN_TEXT_WORDS = 3
_OCR_DPI = 300


def _tesseract_command() -> str | None:
    configured = settings.tesseract_cmd
    if configured:
        return configured if Path(configured).is_file() else None
    found = shutil.which("tesseract")
    if found:
        return found
    default = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")
    return str(default) if default.is_file() else None


class LocalOCRService:
    def __init__(self, tessdata_dir: str | None, languages: str):
        # Look for tessdata in configured path, TESSDATA_PREFIX env, or standard Linux paths
        candidates = [
            tessdata_dir,
            os.environ.get("TESSDATA_PREFIX"),
            "/usr/share/tesseract-ocr/5/tessdata",
            "/usr/share/tesseract-ocr/4.00/tessdata",
            "/usr/share/tesseract-ocr/tessdata",
            "/usr/share/tessdata",
        ]
        found_dir = None
        for cand in candidates:
            if cand and Path(cand).is_dir():
                found_dir = cand
                break
        self._tessdata = found_dir
        self._languages = languages

    def _recognise(self, page: pymupdf.Page) -> list[tuple]:
        """Words of a scanned page, in the shape of PyMuPDF's own word list:
        (x0, y0, x1, y1, text, block, line, word), in page coordinates."""
        if not self._tessdata or not Path(self._tessdata).is_dir():
            raise OCRConfigurationError(
                "This page is a scan or an image and needs Tesseract. Set TESSDATA_DIR in backend/.env "
                "to the folder holding the .traineddata language files."
            )
        available = [
            lang for lang in self._languages.split("+")
            if (Path(self._tessdata) / f"{lang}.traineddata").is_file()
        ]
        if not available:
            # Fall back to any traineddata found in directory
            all_trained = [f.stem for f in Path(self._tessdata).glob("*.traineddata")]
            if all_trained:
                available = [all_trained[0]]
            else:
                raise OCRConfigurationError(
                    f"TESSDATA_DIR ({self._tessdata}) has no .traineddata language files."
                )
        active_languages = "+".join(available)
        command = _tesseract_command()
        if command is None:
            raise OCRConfigurationError(
                "Tesseract was not found. Install it, or set TESSERACT_CMD in backend/.env to tesseract.exe."
            )
        pixmap = page.get_pixmap(dpi=_OCR_DPI, alpha=False)
        scale_x, scale_y = page.rect.width / pixmap.width, page.rect.height / pixmap.height
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "page.png"
            pixmap.save(image)
            try:
                done = subprocess.run(
                    [command, str(image), "stdout", "--tessdata-dir", str(Path(self._tessdata).resolve()),
                     "-l", active_languages, "--psm", "6",
                     # Asked for by setting, not by the "tsv" config file: a
                     # language folder of our own has no configs folder.
                     "-c", "tessedit_create_tsv=1"],
                    capture_output=True, timeout=120, check=True,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                raise OCROperationError(f"Text recognition failed: {exc}") from exc
        words: list[tuple] = []
        for row in done.stdout.decode("utf-8", errors="replace").splitlines()[1:]:
            cells = row.split(chr(9))  # tab-separated
            if len(cells) < 12 or cells[0] != "5" or not cells[11].strip():
                continue
            left, top, width, height = (int(v) for v in cells[6:10])
            # One running line number per (block, paragraph, line).
            line_key = int(cells[2]) * 10_000 + int(cells[3]) * 100 + int(cells[4])
            words.append((left * scale_x, top * scale_y, (left + width) * scale_x, (top + height) * scale_y,
                          cells[11].strip(), 0, line_key, int(cells[5])))
        return words

    def analyze_bytes(self, content: bytes) -> OCRResult:
        try:
            # If content is a PNG, JPEG or TIFF image, convert to a single-page PDF document in PyMuPDF
            if content.startswith(b"\x89PNG\r\n\x1a\n"):
                document = pymupdf.open(stream=content, filetype="png")
            elif content.startswith(b"\xff\xd8\xff"):
                document = pymupdf.open(stream=content, filetype="jpeg")
            elif content.startswith((b"II*\x00", b"MM\x00*")):
                document = pymupdf.open(stream=content, filetype="tiff")
            else:
                document = pymupdf.open(stream=content)
        except Exception as exc:  # noqa: BLE001
            raise OCROperationError(f"The file could not be opened for reading: {exc}") from exc
        pages: list[OCRPage] = []
        text_lines: list[str] = []
        try:
            for index, page in enumerate(document):
                words = page.get_text("words")
                if len(words) < _MIN_TEXT_WORDS:
                    words = self._recognise(page)
                width, height = page.rect.width or 1.0, page.rect.height or 1.0

                def box(x0: float, y0: float, x1: float, y1: float) -> tuple[float, float, float, float]:
                    return (round(x0 / width, 4), round(y0 / height, 4),
                            round((x1 - x0) / width, 4), round((y1 - y0) / height, 4))

                ocr_page = OCRPage(page_number=index + 1)
                lines: dict[tuple[int, int], list[tuple]] = {}
                for word in sorted(words, key=lambda w: (w[5], w[6], w[7])):
                    if not str(word[4]).strip():
                        continue
                    ocr_page.words.append(OCRWord(str(word[4]), *box(*word[:4])))
                    lines.setdefault((word[5], word[6]), []).append(word)
                for line_words in lines.values():
                    line_text = " ".join(str(w[4]) for w in line_words)
                    ocr_page.lines.append(
                        OCRWord(
                            line_text,
                            *box(
                                min(w[0] for w in line_words), min(w[1] for w in line_words),
                                max(w[2] for w in line_words), max(w[3] for w in line_words),
                            ),
                        )
                    )
                    text_lines.append(line_text)
                pages.append(ocr_page)
        finally:
            document.close()
        return OCRResult(text="\n".join(text_lines), pages=pages)

    def read_image(self, image_bytes: bytes) -> tuple[str, float]:
        """Plain text of a small image. No confidence is available: 0.5."""
        return self.analyze_bytes(image_bytes).text.strip(), 0.5


def build_local_ocr_service() -> LocalOCRService:
    return LocalOCRService(settings.tessdata_dir, settings.ocr_languages)
