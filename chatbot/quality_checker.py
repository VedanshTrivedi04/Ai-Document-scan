"""
quality_checker.py: Pre-flight document image quality and integrity checks for Sarthi Bot.
Detects:
1. Low resolution / extreme small dimensions
2. Image blur (Laplacian edge variance)
3. Severe glare / overexposure
4. Digital editing software signatures in EXIF metadata (Photoshop, Canva, PicsArt, etc.)
"""

import logging
from pathlib import Path
from typing import Dict, Any, List
from PIL import Image, ImageFilter, ImageStat

logger = logging.getLogger(__name__)

# Editing software suspicious keywords
SUSPICIOUS_SOFTWARE = [
    "photoshop", "gimp", "canva", "picsart", "snapseed", "pixlr",
    "lightroom", "paint.net", "corel", "affinity", "illustrator"
]

BLUR_THRESHOLD = 650.0  # Under 650 indicates noticeable blur
MIN_WIDTH = 350
MIN_HEIGHT = 200

def check_document_quality(file_path: Path) -> Dict[str, Any]:
    """
    Performs quick, lightweight quality analysis on the uploaded photo.
    Returns warnings if quality could impede official government verification.
    """
    if not file_path.exists() or file_path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
        return {"is_acceptable": True, "warnings": []}

    warnings: List[str] = []
    blur_score = 0.0
    software_found = None

    try:
        with Image.open(file_path) as img:
            w, h = img.size

            # 1. Dimension Check
            if w < MIN_WIDTH or h < MIN_HEIGHT:
                warnings.append("⚠️ *Resolution Kam Hai:* Photo bohot chhoti hai, text saaf padhne me dikkat aa sakti hai.")

            # 2. Blur / Sharpness Check
            gray = img.convert("L")
            edges = gray.filter(ImageFilter.FIND_EDGES)
            stat = ImageStat.Stat(edges)
            blur_score = float(stat.var[0])

            if blur_score < BLUR_THRESHOLD:
                warnings.append("⚠️ *Dhundhla (Blurry) Dastavej:* Photo dhundhli lag rahi hai. Kripya camera saaf karke achhi roshni me photo lein.")

            # 3. Extreme Brightness / Glare Check
            gray_stat = ImageStat.Stat(gray)
            mean_brightness = gray_stat.mean[0]
            if mean_brightness > 240:
                warnings.append("⚠️ *Chamak (Glare):* Photo par bohot tez roshni/flash pad rahi hai jisse akshar chhip sakte hain.")
            elif mean_brightness < 30:
                warnings.append("⚠️ *Andhera (Too Dark):* Photo bohot andheri hai, thoda roshni me kheechein.")

            # 4. Digital Editing / Tampering Check (EXIF)
            exif = img.getexif()
            if exif:
                # Tag 305 is Software
                software = str(exif.get(305, "")).lower()
                for sw in SUSPICIOUS_SOFTWARE:
                    if sw in software:
                        software_found = sw.capitalize()
                        warnings.append(f"⚠️ *Digital Editing Sandeh:* File me photo editor ({software_found}) ke nishaan mile hain. Kripya bina edit kiya gaya original dastavej hi jama karein.")
                        break

    except Exception as e:
        logger.debug(f"Quality check skipped for {file_path.name}: {e}")

    return {
        "is_acceptable": len(warnings) == 0,
        "warnings": warnings,
        "blur_score": blur_score,
        "software_detected": software_found,
    }
