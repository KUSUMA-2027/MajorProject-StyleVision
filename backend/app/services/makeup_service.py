"""
StyleVision — Virtual Makeup Studio Service
============================================
Uses MediaPipe FaceMesh 478 landmarks + OpenCV colour-space alpha blending
to apply cosmetics onto user portrait photos.

Supported makeup types:
  lipstick  — lips polygon fill  (landmarks #61, #291, #0, #17 + inner lip ring)
  eyeshadow — upper eyelid area  (per-eye: #33,#133,#362,#263 + brow / orbital zone)
  blush     — cheek polygon      (medial cheek cluster per side)

Finish modes modulate final blend opacity and saturation:
  matte   → lower alpha, fully desaturated overlay (flat pigment)
  satin   → medium alpha, slight saturation boost
  glossy  → higher alpha, strong saturation, additive specular highlight

Output is always saved to:
  <uploads_dir>/tryon/tryon-mu-<id>.png
"""
import os
import uuid
import logging
import math
from typing import Tuple, Optional, List

import numpy as np
from PIL import Image
import cv2
import mediapipe as mp

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ── MediaPipe initialisation ───────────────────────────────────────────────────
mp_face_detection = mp.solutions.face_detection
mp_face_mesh = mp.solutions.face_mesh

# ── FaceMesh landmark index groups ────────────────────────────────────────────
# Outer lip ring  (clockwise from left corner)
OUTER_LIP = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 375, 321, 405,
              314, 17, 84, 181, 91, 146, 61]
# Inner lip ring  (used to make lips hollow = only colour the visible surface)
INNER_LIP = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308, 324, 318,
             402, 317, 14, 87, 178, 88, 95, 78]

# Upper eyelid / eyeshadow zone — left eye
LEFT_EYE_SHADOW = [226, 247, 30, 29, 27, 28, 56, 190,  # above crease
                   243, 112, 26, 22, 23, 24, 110, 25]
# Upper eyelid / eyeshadow zone — right eye
RIGHT_EYE_SHADOW = [463, 414, 286, 258, 257, 259, 260, 467,
                    446, 255, 339, 254, 253, 252, 256, 341]

# Blush regions — left cheek (medial) and right cheek
LEFT_CHEEK = [116, 123, 147, 213, 192, 214, 212, 202, 210, 169, 136, 135, 192]
RIGHT_CHEEK = [340, 349, 376, 433, 434, 416, 432, 422, 430, 394, 365, 364, 416]


# ── Two-stage MediaPipe face detection (same approach as accessory_service) ───

def _detect_face_region(img_rgb: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """Return (x, y, w, h) of the face bounding box in img_rgb, or None."""
    h, w = img_rgb.shape[:2]
    with mp_face_detection.FaceDetection(
        model_selection=1, min_detection_confidence=0.4
    ) as detector:
        res = detector.process(img_rgb)
    if not res.detections:
        return None
    det = res.detections[0]
    bb = det.location_data.relative_bounding_box
    x = max(0, int(bb.xmin * w) - 20)
    y = max(0, int(bb.ymin * h) - 30)
    bw = min(w - x, int(bb.width * w) + 40)
    bh = min(h - y, int(bb.height * h) + 60)
    return (x, y, bw, bh)


def _get_landmarks_on_full_image(
    img_rgb: np.ndarray,
) -> Optional[List[Tuple[int, int]]]:
    """
    Two-stage landmark detection:
    1. FaceDetection on full image → face crop
    2. FaceMesh on crop (higher confidence)
    3. Project landmarks back to full-image pixel coordinates.
    Returns list of (px, py) for all 478 landmarks, or None on failure.
    """
    h_full, w_full = img_rgb.shape[:2]
    box = _detect_face_region(img_rgb)
    if box is None:
        logger.warning("[Makeup] Face not detected on full image. Trying FaceMesh directly.")
        bx, by, bw, bh = 0, 0, w_full, h_full
    else:
        bx, by, bw, bh = box

    crop = img_rgb[by : by + bh, bx : bx + bw]
    hc, wc = crop.shape[:2]

    with mp_face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.4,
        min_tracking_confidence=0.4,
    ) as mesh:
        res = mesh.process(crop)

    if not res.multi_face_landmarks:
        logger.warning("[Makeup] FaceMesh found no face in crop.")
        return None

    lm = res.multi_face_landmarks[0].landmark
    pts: List[Tuple[int, int]] = []
    for p in lm:
        px = int(p.x * wc) + bx
        py = int(p.y * hc) + by
        pts.append((px, py))
    return pts


# ── Colour helpers ─────────────────────────────────────────────────────────────

def _hex_to_bgr(hex_color: str) -> Tuple[int, int, int]:
    """Convert #RRGGBB → (B, G, R) for OpenCV."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return (b, g, r)


def _adjust_saturation(bgr: np.ndarray, factor: float) -> np.ndarray:
    """Multiply saturation channel of a BGR image by factor (HSV space)."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * factor, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


# ── Per-makeup-type blend functions ───────────────────────────────────────────

def _apply_lipstick(
    canvas: np.ndarray,
    pts: List[Tuple[int, int]],
    bgr_color: Tuple[int, int, int],
    intensity: float,
    finish: str,
) -> np.ndarray:
    """Fill the lip polygon with colour. Returns modified canvas (BGR uint8)."""
    outer = np.array([pts[i] for i in OUTER_LIP], dtype=np.int32)
    inner = np.array([pts[i] for i in INNER_LIP], dtype=np.int32)

    lip_mask = np.zeros(canvas.shape[:2], dtype=np.uint8)
    cv2.fillPoly(lip_mask, [outer], 255)
    # Hollow out inner cavity (teeth / tongue area)
    cv2.fillPoly(lip_mask, [inner], 0)

    # Slight Gaussian blur to soften the polygon edge
    lip_mask = cv2.GaussianBlur(lip_mask, (7, 7), 4)

    overlay = canvas.copy()
    overlay[lip_mask > 0] = bgr_color

    # Finish modifiers
    if finish == "matte":
        alpha = 0.55 * intensity
        overlay = _adjust_saturation(overlay, 0.8)
    elif finish == "glossy":
        alpha = 0.75 * intensity
        overlay = _adjust_saturation(overlay, 1.3)
        # Additive specular highlight on upper lip centre
        ctr_idx = OUTER_LIP[5]  # landmark #0 ≈ upper lip midpoint
        cx, cy = pts[ctr_idx]
        cv2.circle(overlay, (cx, cy), 6, (200, 200, 200), -1)
    else:  # satin
        alpha = 0.65 * intensity
        overlay = _adjust_saturation(overlay, 1.1)

    # Blend using soft alpha mask
    alpha_mask = (lip_mask / 255.0 * alpha).astype(np.float32)
    result = canvas.copy().astype(np.float32)
    for c in range(3):
        result[:, :, c] = (
            canvas[:, :, c].astype(np.float32) * (1 - alpha_mask)
            + overlay[:, :, c].astype(np.float32) * alpha_mask
        )
    return np.clip(result, 0, 255).astype(np.uint8)


def _apply_eyeshadow(
    canvas: np.ndarray,
    pts: List[Tuple[int, int]],
    bgr_color: Tuple[int, int, int],
    intensity: float,
    finish: str,
) -> np.ndarray:
    """Apply eyeshadow to upper eyelid region on both eyes."""
    for eye_indices in [LEFT_EYE_SHADOW, RIGHT_EYE_SHADOW]:
        eye_pts = np.array([pts[i] for i in eye_indices], dtype=np.int32)

        eye_mask = np.zeros(canvas.shape[:2], dtype=np.uint8)
        cv2.fillConvexPoly(eye_mask, cv2.convexHull(eye_pts), 255)
        eye_mask = cv2.GaussianBlur(eye_mask, (11, 11), 6)

        overlay = canvas.copy()
        overlay[eye_mask > 0] = bgr_color

        if finish == "matte":
            alpha = 0.40 * intensity
        elif finish == "glossy":
            alpha = 0.60 * intensity
            overlay = _adjust_saturation(overlay, 1.2)
        else:
            alpha = 0.50 * intensity

        alpha_mask = (eye_mask / 255.0 * alpha).astype(np.float32)
        result = canvas.copy().astype(np.float32)
        for c in range(3):
            result[:, :, c] = (
                canvas[:, :, c].astype(np.float32) * (1 - alpha_mask)
                + overlay[:, :, c].astype(np.float32) * alpha_mask
            )
        canvas = np.clip(result, 0, 255).astype(np.uint8)

    return canvas


def _apply_blush(
    canvas: np.ndarray,
    pts: List[Tuple[int, int]],
    bgr_color: Tuple[int, int, int],
    intensity: float,
    finish: str,
) -> np.ndarray:
    """Apply blush to cheek polygons on both sides."""
    for cheek_indices in [LEFT_CHEEK, RIGHT_CHEEK]:
        cheek_pts = np.array([pts[i] for i in cheek_indices], dtype=np.int32)

        ck_mask = np.zeros(canvas.shape[:2], dtype=np.uint8)
        cv2.fillConvexPoly(ck_mask, cv2.convexHull(cheek_pts), 255)
        # Very soft blur for a natural flush
        ck_mask = cv2.GaussianBlur(ck_mask, (31, 31), 18)

        overlay = canvas.copy()
        overlay[ck_mask > 0] = bgr_color

        if finish == "matte":
            alpha = 0.30 * intensity
        elif finish == "glossy":
            alpha = 0.45 * intensity
        else:
            alpha = 0.35 * intensity

        alpha_mask = (ck_mask / 255.0 * alpha).astype(np.float32)
        result = canvas.copy().astype(np.float32)
        for c in range(3):
            result[:, :, c] = (
                canvas[:, :, c].astype(np.float32) * (1 - alpha_mask)
                + overlay[:, :, c].astype(np.float32) * alpha_mask
            )
        canvas = np.clip(result, 0, 255).astype(np.uint8)

    return canvas


# ── Main public function ───────────────────────────────────────────────────────

def synthesize_makeup_tryon(
    person_img: Image.Image,
    makeup_type: str,
    color_hex: str,
    intensity: float,
    finish: str,
) -> Tuple[Image.Image, str, str]:
    """
    Apply virtual makeup to person_img.

    Args:
        person_img  : PIL Image (RGB) of the person.
        makeup_type : 'lipstick' | 'eyeshadow' | 'blush'
        color_hex   : '#RRGGBB'
        intensity   : 0.0 – 1.0 (blend strength multiplier)
        finish      : 'matte' | 'satin' | 'glossy'

    Returns:
        (result_pil, landmark_summary, result_url)
    """
    # ── 1. Prepare BGR canvas ────────────────────────────────────────
    img_rgb = np.array(person_img.convert("RGB"))
    canvas_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)

    # ── 2. Detect landmarks ─────────────────────────────────────────
    pts = _get_landmarks_on_full_image(img_rgb)
    if pts is None:
        raise ValueError(
            "No face detected in the uploaded photo. "
            "Please use a well-lit, front-facing portrait."
        )

    # ── 3. Apply makeup ─────────────────────────────────────────────
    bgr_color = _hex_to_bgr(color_hex)
    makeup_type_lower = makeup_type.lower()

    if makeup_type_lower == "lipstick":
        result_bgr = _apply_lipstick(canvas_bgr, pts, bgr_color, intensity, finish)
        landmark_summary = f"Lips mesh ({len(OUTER_LIP)}-pt polygon, landmark #0 centroid)"
    elif makeup_type_lower == "eyeshadow":
        result_bgr = _apply_eyeshadow(canvas_bgr, pts, bgr_color, intensity, finish)
        landmark_summary = "Upper eyelid convex hull (L: #33–#133, R: #362–#263)"
    elif makeup_type_lower == "blush":
        result_bgr = _apply_blush(canvas_bgr, pts, bgr_color, intensity, finish)
        landmark_summary = "Medial cheek clusters (L: #116–#213, R: #340–#433)"
    else:
        raise ValueError(f"Unknown makeup_type: '{makeup_type}'. Use lipstick|eyeshadow|blush.")

    # ── 4. Save result ──────────────────────────────────────────────
    result_rgb = cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)
    result_pil = Image.fromarray(result_rgb)

    tryon_id = f"tryon-mu-{uuid.uuid4().hex[:10]}"
    out_dir = os.path.join(settings.upload_dir, "tryon")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{tryon_id}.png")
    result_pil.save(out_path, "PNG")

    result_url = f"/uploads/tryon/{tryon_id}.png"
    logger.info(
        "[Makeup] %s applied (%s, intensity=%.2f, finish=%s) → %s",
        makeup_type, color_hex, intensity, finish, result_url,
    )
    return result_pil, landmark_summary, result_url
