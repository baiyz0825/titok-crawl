"""
Automatic slider CAPTCHA solver for Douyin.

Uses image processing to detect the slider target position and
simulates human-like drag behavior via Playwright.
"""

import asyncio
import io
import logging
import math
import random
import struct
import time
import zlib
from typing import Optional

from playwright.async_api import Page, ElementHandle

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Douyin captcha selectors (commonly seen variants)
# ---------------------------------------------------------------------------
# Outer captcha container
CAPTCHA_CONTAINER_SELECTORS = [
    "[class*='captcha-verify']",
    "[class*='secsdk-captcha']",
    "#captcha_container",
    "[class*='captcha_verify']",
    "div[id*='captcha']",
]

# The background image (puzzle board)
BG_IMAGE_SELECTORS = [
    "[class*='captcha-verify'] img[class*='bg']",
    "[class*='captcha'] img:not([class*='piece']):not([class*='slider'])",
    "img[class*='captcha-verify-image']",
    ".captcha-verify-image img",
    "[class*='verify-image'] img",
]

# The puzzle piece (slider block)
PIECE_IMAGE_SELECTORS = [
    "[class*='captcha-verify'] img[class*='piece']",
    "img[class*='captcha_verify_img_slide']",
    "[class*='verify-sub-block'] img",
    "img[class*='piece']",
]

# The draggable slider button
SLIDER_BUTTON_SELECTORS = [
    "[class*='secsdk-captcha-drag-icon']",
    "[class*='captcha-slider-btn']",
    "[class*='slider-btn']",
    "[class*='captcha_verify_slide--btn']",
    "[class*='verify-drag-btn']",
    "[class*='drag-btn']",
]

# The slider track bar
SLIDER_TRACK_SELECTORS = [
    "[class*='captcha-slider-bar']",
    "[class*='slider-track']",
    "[class*='verify-bar']",
    "[class*='captcha_verify_bar']",
]


# ---------------------------------------------------------------------------
# Image processing (pure Python / PIL)
# ---------------------------------------------------------------------------

def _try_import_cv2():
    """Try to import OpenCV; return None if unavailable."""
    try:
        import cv2
        import numpy as np
        return cv2, np
    except ImportError:
        return None, None


def find_slider_offset_cv2(bg_bytes: bytes, piece_bytes: bytes) -> Optional[int]:
    """Use OpenCV template matching to find the x-offset of the slider gap."""
    cv2, np = _try_import_cv2()
    if cv2 is None:
        return None

    bg_arr = np.frombuffer(bg_bytes, dtype=np.uint8)
    piece_arr = np.frombuffer(piece_bytes, dtype=np.uint8)

    bg_img = cv2.imdecode(bg_arr, cv2.IMREAD_COLOR)
    piece_img = cv2.imdecode(piece_arr, cv2.IMREAD_COLOR)

    if bg_img is None or piece_img is None:
        logger.warning("cv2: failed to decode captcha images")
        return None

    # Convert to grayscale
    bg_gray = cv2.cvtColor(bg_img, cv2.COLOR_BGR2GRAY)
    piece_gray = cv2.cvtColor(piece_img, cv2.COLOR_BGR2GRAY)

    # Edge detection makes matching more robust
    bg_edges = cv2.Canny(bg_gray, 100, 200)
    piece_edges = cv2.Canny(piece_gray, 100, 200)

    result = cv2.matchTemplate(bg_edges, piece_edges, cv2.TM_CCOEFF_NORMED)
    _, _, _, max_loc = cv2.minMaxLoc(result)

    x_offset = max_loc[0]
    logger.debug("cv2 template match offset: %d", x_offset)
    return x_offset


def find_slider_offset_pil(bg_bytes: bytes, piece_bytes: bytes) -> Optional[int]:
    """Fallback: use PIL edge-difference scanning to find the gap x-offset."""
    try:
        from PIL import Image, ImageFilter
    except ImportError:
        logger.error("Neither opencv-python nor Pillow is available")
        return None

    bg = Image.open(io.BytesIO(bg_bytes)).convert("L")
    piece = Image.open(io.BytesIO(piece_bytes)).convert("L")

    # Apply edge detection
    bg_edges = bg.filter(ImageFilter.FIND_EDGES)
    piece_edges = piece.filter(ImageFilter.FIND_EDGES)

    bg_w, bg_h = bg_edges.size
    p_w, p_h = piece_edges.size

    bg_px = list(bg_edges.getdata())
    piece_px = list(piece_edges.getdata())

    best_x = 0
    best_score = -1

    # Slide piece across bg horizontally
    step = 2  # speed up by scanning every 2 pixels
    for x in range(0, bg_w - p_w, step):
        score = 0
        sampled = 0
        for py in range(0, p_h, 3):
            for px in range(0, p_w, 3):
                p_val = piece_px[py * p_w + px]
                if p_val < 30:
                    continue  # skip non-edge pixels in piece
                b_val = bg_px[(py) * bg_w + (x + px)]
                score += min(p_val, b_val)
                sampled += 1
        if sampled > 0 and score > best_score:
            best_score = score
            best_x = x

    logger.debug("PIL edge-scan offset: %d (score=%d)", best_x, best_score)
    return best_x


def find_slider_offset(bg_bytes: bytes, piece_bytes: bytes) -> Optional[int]:
    """Find x-offset using the best available method."""
    # Try OpenCV first (more accurate)
    offset = find_slider_offset_cv2(bg_bytes, piece_bytes)
    if offset is not None:
        return offset
    # Fallback to PIL
    return find_slider_offset_pil(bg_bytes, piece_bytes)


# ---------------------------------------------------------------------------
# Human-like trajectory generation
# ---------------------------------------------------------------------------

def generate_slide_track(distance: int, duration_ms: int = None) -> list[dict]:
    """
    Generate a human-like mouse trajectory for sliding.

    Returns list of {x, y, dt} dicts where x/y are offsets from start
    and dt is the time delta in ms for that step.

    Uses an ease-in-out curve with random jitter to mimic real drag.
    """
    if duration_ms is None:
        duration_ms = random.randint(500, 1200)

    track = []
    current_x = 0.0
    current_t = 0

    # Number of discrete steps
    num_steps = random.randint(30, 60)
    step_time = duration_ms / num_steps

    for i in range(num_steps):
        progress = (i + 1) / num_steps

        # Ease-in-out cubic
        if progress < 0.5:
            ease = 4 * progress * progress * progress
        else:
            p = -2 * progress + 2
            ease = 1 - (p * p * p) / 2

        target_x = distance * ease

        # Add slight overshoot near the end
        if progress > 0.85:
            overshoot = distance * random.uniform(0.0, 0.03)
            target_x += overshoot * (1 - progress) / 0.15

        # Small random jitter
        jitter_x = random.uniform(-1.5, 1.5)
        jitter_y = random.uniform(-2.0, 2.0)

        dt = int(step_time + random.uniform(-step_time * 0.3, step_time * 0.3))
        dt = max(dt, 5)

        current_t += dt
        current_x = target_x + jitter_x

        track.append({
            "x": round(current_x),
            "y": round(jitter_y),
            "dt": dt,
        })

    # Ensure final position is exactly on target
    track[-1]["x"] = distance
    track[-1]["y"] = 0

    # Add a few micro-adjustments at the end (human settle)
    for _ in range(random.randint(1, 3)):
        track.append({
            "x": distance + random.choice([-1, 0, 1]),
            "y": random.choice([-1, 0, 1]),
            "dt": random.randint(30, 80),
        })
    track.append({"x": distance, "y": 0, "dt": random.randint(50, 120)})

    return track


# ---------------------------------------------------------------------------
# Playwright slider execution
# ---------------------------------------------------------------------------

async def _query_first(page: Page, selectors: list[str]) -> Optional[ElementHandle]:
    """Try a list of CSS selectors and return the first match."""
    for sel in selectors:
        try:
            el = await page.query_selector(sel)
            if el:
                return el
        except Exception:
            continue
    return None


async def _get_image_bytes(page: Page, el: ElementHandle) -> Optional[bytes]:
    """Download image bytes from an <img> element's src."""
    src = await el.get_attribute("src")
    if not src:
        return None

    # If it's a data URI
    if src.startswith("data:image"):
        import base64
        # data:image/png;base64,xxxx
        header, encoded = src.split(",", 1)
        return base64.b64decode(encoded)

    # Otherwise fetch via page context
    try:
        resp = await page.context.request.get(src)
        return await resp.body()
    except Exception as e:
        logger.warning("Failed to fetch image %s: %s", src[:80], e)
        return None


async def _detect_slider_elements(page: Page) -> dict:
    """Detect captcha elements on the page. Returns dict with found elements."""
    container = await _query_first(page, CAPTCHA_CONTAINER_SELECTORS)
    if not container:
        return {}

    bg_img = await _query_first(page, BG_IMAGE_SELECTORS)
    piece_img = await _query_first(page, PIECE_IMAGE_SELECTORS)
    slider_btn = await _query_first(page, SLIDER_BUTTON_SELECTORS)

    result = {"container": container}
    if bg_img:
        result["bg_img"] = bg_img
    if piece_img:
        result["piece_img"] = piece_img
    if slider_btn:
        result["slider_btn"] = slider_btn

    return result


async def _compute_pixel_offset(page: Page, elements: dict) -> Optional[int]:
    """
    Compute the pixel offset to slide.

    Strategy:
    1. If both bg and piece images are available, use image matching.
    2. Otherwise try to read the gap position from DOM style/transform.
    """
    bg_img = elements.get("bg_img")
    piece_img = elements.get("piece_img")

    if bg_img and piece_img:
        bg_bytes = await _get_image_bytes(page, bg_img)
        piece_bytes = await _get_image_bytes(page, piece_img)

        if bg_bytes and piece_bytes:
            # Get displayed dimensions of the bg image to compute scale
            bg_box = await bg_img.bounding_box()
            if bg_box:
                from PIL import Image
                actual_bg = Image.open(io.BytesIO(bg_bytes))
                actual_w = actual_bg.width
                display_w = bg_box["width"]
                scale = display_w / actual_w if actual_w > 0 else 1.0

                offset = find_slider_offset(bg_bytes, piece_bytes)
                if offset is not None:
                    pixel_offset = int(offset * scale)
                    logger.info(
                        "Image match: raw_offset=%d, scale=%.3f, pixel_offset=%d",
                        offset, scale, pixel_offset,
                    )
                    return pixel_offset

    # Fallback: try to extract gap position from piece element's transform/left style
    if piece_img:
        try:
            left = await page.evaluate(
                """(el) => {
                    const style = window.getComputedStyle(el);
                    const left = parseFloat(style.left);
                    if (!isNaN(left) && left > 0) return left;
                    const transform = style.transform;
                    if (transform && transform !== 'none') {
                        const m = transform.match(/translate[X3d]?\\(([\\d.]+)/);
                        if (m) return parseFloat(m[1]);
                    }
                    return null;
                }""",
                piece_img,
            )
            if left and left > 10:
                logger.info("DOM-based offset: %d", int(left))
                return int(left)
        except Exception:
            pass

    logger.warning("Could not determine slider offset")
    return None


async def _perform_drag(page: Page, slider_btn: ElementHandle, offset_x: int):
    """Execute a human-like drag on the slider button."""
    box = await slider_btn.bounding_box()
    if not box:
        raise RuntimeError("Slider button has no bounding box")

    start_x = box["x"] + box["width"] / 2
    start_y = box["y"] + box["height"] / 2

    track = generate_slide_track(offset_x)

    # Move to start and press
    await page.mouse.move(start_x, start_y)
    await asyncio.sleep(random.uniform(0.1, 0.3))
    await page.mouse.down()
    await asyncio.sleep(random.uniform(0.05, 0.15))

    # Follow the trajectory
    for point in track:
        target_x = start_x + point["x"]
        target_y = start_y + point["y"]
        await page.mouse.move(target_x, target_y)
        await asyncio.sleep(point["dt"] / 1000.0)

    # Brief pause before release (humans do this)
    await asyncio.sleep(random.uniform(0.05, 0.2))
    await page.mouse.up()


async def _check_solved(page: Page, timeout: float = 3.0) -> bool:
    """Check whether the captcha was solved after dragging."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        # Check if captcha container disappeared
        container = await _query_first(page, CAPTCHA_CONTAINER_SELECTORS)
        if not container:
            return True

        # Check for success indicators
        success = await page.query_selector(
            ", ".join([
                "[class*='verify-success']",
                "[class*='captcha-success']",
                "[class*='success']",
            ])
        )
        if success:
            return True

        # Check for visible state change (some captchas hide via display/opacity)
        if container:
            visible = await page.evaluate(
                """(el) => {
                    const s = window.getComputedStyle(el);
                    return s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
                }""",
                container,
            )
            if not visible:
                return True

        await asyncio.sleep(0.3)

    return False


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

async def detect_slider_captcha(page: Page) -> bool:
    """Check if a slider captcha is currently present on the page."""
    elements = await _detect_slider_elements(page)
    return bool(elements.get("container"))


async def solve_slider_captcha(page: Page, max_retries: int = 3) -> bool:
    """
    Attempt to automatically solve a slider CAPTCHA on the given page.

    Args:
        page: Playwright Page with an active slider captcha.
        max_retries: Maximum number of attempts.

    Returns:
        True if the captcha was solved, False otherwise.
    """
    for attempt in range(1, max_retries + 1):
        logger.info("Slider captcha solve attempt %d/%d", attempt, max_retries)

        # Short delay between retries
        if attempt > 1:
            await asyncio.sleep(random.uniform(1.0, 2.5))

        # Detect elements
        elements = await _detect_slider_elements(page)
        if not elements.get("container"):
            logger.info("No captcha container found (may already be solved)")
            return True

        slider_btn = elements.get("slider_btn")
        if not slider_btn:
            logger.warning("Slider button not found on attempt %d", attempt)
            continue

        # Compute offset
        offset = await _compute_pixel_offset(page, elements)
        if offset is None or offset < 10:
            logger.warning("Invalid offset (%s), trying random fallback", offset)
            # Use a reasonable random offset as a last resort
            track_el = await _query_first(page, SLIDER_TRACK_SELECTORS)
            if track_el:
                track_box = await track_el.bounding_box()
                if track_box:
                    offset = random.randint(
                        int(track_box["width"] * 0.2),
                        int(track_box["width"] * 0.8),
                    )
            if offset is None or offset < 10:
                offset = random.randint(80, 220)

        logger.info("Dragging slider by %d pixels", offset)

        try:
            await _perform_drag(page, slider_btn, offset)
        except Exception as e:
            logger.error("Drag failed: %s", e)
            continue

        # Check result
        solved = await _check_solved(page, timeout=3.0)
        if solved:
            logger.info("Slider captcha solved on attempt %d!", attempt)
            return True

        logger.info("Attempt %d did not pass verification", attempt)

    logger.warning("Failed to solve slider captcha after %d attempts", max_retries)
    return False
