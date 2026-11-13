import io
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image


@dataclass
class TemplateMatch:
    x: int
    y: int
    confidence: float


def locate_template(
    screenshot_bytes: bytes,
    template_bytes: bytes,
    center: tuple[int, int] | None = None,
    search_radius: int = 220,
    min_confidence: float = 0.80,
) -> TemplateMatch | None:
    match = best_effort_match(screenshot_bytes, template_bytes, center, search_radius)
    if match is None or match.confidence < min_confidence:
        return None
    return match


def best_effort_match(
    screenshot_bytes: bytes,
    template_bytes: bytes,
    center: tuple[int, int] | None = None,
    search_radius: int = 220,
) -> TemplateMatch | None:
    """Like locate_template, but always returns the best match found, even below the
    acceptance threshold — useful to tell a near-miss (drifted a bit) from a total miss
    (wrong screen state entirely) when diagnosing a failed locate."""
    screenshot = _to_gray_array(screenshot_bytes)
    template = _to_gray_array(template_bytes)
    template_h, template_w = template.shape[:2]
    if template_h == 0 or template_w == 0:
        return None
    if screenshot.shape[0] < template_h or screenshot.shape[1] < template_w:
        return None

    candidates: list[TemplateMatch] = []
    if center is not None:
        nearby = _search_region(screenshot, template, center, search_radius)
        if nearby is not None:
            candidates.append(nearby)
    full = _search_region(screenshot, template, None, 0)
    if full is not None:
        candidates.append(full)
    return max(candidates, key=lambda item: item.confidence) if candidates else None


def _search_region(
    screenshot: np.ndarray,
    template: np.ndarray,
    center: tuple[int, int] | None,
    radius: int,
) -> TemplateMatch | None:
    template_h, template_w = template.shape[:2]
    offset_x = offset_y = 0
    region = screenshot

    if center is not None and radius > 0:
        cx, cy = center
        left = max(0, cx - radius)
        top = max(0, cy - radius)
        right = min(screenshot.shape[1], cx + radius)
        bottom = min(screenshot.shape[0], cy + radius)
        if right - left >= template_w and bottom - top >= template_h:
            region = screenshot[top:bottom, left:right]
            offset_x, offset_y = left, top

    result = cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    match_x = offset_x + max_loc[0] + template_w // 2
    match_y = offset_y + max_loc[1] + template_h // 2
    return TemplateMatch(x=match_x, y=match_y, confidence=float(max_val))


def _to_gray_array(image_bytes: bytes) -> np.ndarray:
    with Image.open(io.BytesIO(image_bytes)) as image:
        return np.array(image.convert("L"))
