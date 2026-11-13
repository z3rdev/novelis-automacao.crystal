import io
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytesseract
from PIL import Image

from app.config.settings import get_settings


@dataclass
class OcrMatch:
    x: int
    y: int
    text: str
    confidence: float


def _known_tesseract_paths() -> list[Path]:
    local_app_data = os.environ.get("LOCALAPPDATA")
    program_files = os.environ.get("PROGRAMFILES")
    candidates = []
    if local_app_data:
        candidates.append(Path(local_app_data) / "Programs" / "Tesseract-OCR" / "tesseract.exe")
    if program_files:
        candidates.append(Path(program_files) / "Tesseract-OCR" / "tesseract.exe")
    return candidates


def _configure_tesseract() -> None:
    settings = get_settings()
    if settings.tesseract_path and settings.tesseract_path.is_file():
        pytesseract.pytesseract.tesseract_cmd = str(settings.tesseract_path)
        return
    on_path = shutil.which("tesseract")
    if on_path:
        pytesseract.pytesseract.tesseract_cmd = on_path
        return
    for candidate in _known_tesseract_paths():
        if candidate.is_file():
            pytesseract.pytesseract.tesseract_cmd = str(candidate)
            return


_configure_tesseract()


def find_text_prefix(
    screenshot_bytes: bytes,
    prefix: str,
    region: tuple[int, int, int, int] | None = None,
    min_confidence: float = 40.0,
) -> OcrMatch | None:
    prefix_normalized = prefix.strip().lower()
    if not prefix_normalized:
        return None

    best: OcrMatch | None = None
    for match in _detected_lines(screenshot_bytes, region):
        if not match.text.lower().startswith(prefix_normalized):
            continue
        if match.confidence < min_confidence:
            continue
        if best is None or match.confidence > best.confidence:
            best = match
    return best


def list_detected_lines(
    screenshot_bytes: bytes,
    region: tuple[int, int, int, int] | None = None,
    min_confidence: float = 30.0,
    limit: int = 6,
) -> list[str]:
    """Diagnostic helper: what text OCR actually read, regardless of any prefix match."""
    lines = [
        match.text
        for match in sorted(_detected_lines(screenshot_bytes, region), key=lambda item: item.y)
        if match.confidence >= min_confidence
    ]
    return lines[:limit]


def _detected_lines(
    screenshot_bytes: bytes,
    region: tuple[int, int, int, int] | None,
) -> list[OcrMatch]:
    image = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
    offset_x = offset_y = 0
    if region is not None:
        left, top, width, height = region
        left = max(0, left)
        top = max(0, top)
        right = min(image.width, left + width)
        bottom = min(image.height, top + height)
        if right <= left or bottom <= top:
            return []
        image = image.crop((left, top, right, bottom))
        offset_x, offset_y = left, top

    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    words = data["text"]

    lines: dict[tuple[int, int, int], list[int]] = {}
    for i in range(len(words)):
        if not words[i].strip():
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append(i)

    results: list[OcrMatch] = []
    for indices in lines.values():
        indices.sort(key=lambda i: data["left"][i])
        line_text = " ".join(words[i].strip() for i in indices)
        confidences = [float(data["conf"][i]) for i in indices if float(data["conf"][i]) >= 0]
        confidence = sum(confidences) / len(confidences) if confidences else 0.0
        left = min(data["left"][i] for i in indices)
        top = min(data["top"][i] for i in indices)
        right = max(data["left"][i] + data["width"][i] for i in indices)
        bottom = max(data["top"][i] + data["height"][i] for i in indices)
        center_x = offset_x + (left + right) // 2
        center_y = offset_y + (top + bottom) // 2
        results.append(OcrMatch(x=center_x, y=center_y, text=line_text, confidence=confidence))
    return results
