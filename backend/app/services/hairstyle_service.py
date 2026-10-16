"""
StyleVision — Virtual Hairstyle Studio Service
=============================================
Uses MediaPipe FaceMesh / FaceDetection to estimate head orientation (yaw, roll),
forehead anchor, and cranial scale, then overlays and color-tints hairstyle assets.

Key landmarks used:
  #10  — Forehead top / hairline center anchor
  #234 — Left ear / tragus
  #454 — Right ear / tragus
  #152 — Chin bottom
  #1   — Nose tip center
"""
import os
import uuid
import logging
import math
from typing import Tuple, Optional, Dict

import numpy as np
from PIL import Image, ImageOps
import cv2
import mediapipe as mp

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

mp_face_detection = mp.solutions.face_detection
mp_face_mesh = mp.solutions.face_mesh

HAIRSTYLE_ASSET_MAP = {
    "item-hair-1": "beach_waves.png",
    "item-hair-2": "classic_french_bob.png",
    "item-hair-3": "sleek_high_ponytail.png",
    "item-hair-4": "soft_curls.png",
    "item-hair-5": "platinum_blonde_shag.png",
    "long": "beach_waves.png",
    "short": "classic_french_bob.png",
    "updo": "sleek_high_ponytail.png",
    "medium": "soft_curls.png",
}


def _detect_landmarks_two_stage(np_rgb: np.ndarray) -> Optional[Dict[int, np.ndarray]]:
    """Detect 478 face landmarks on image with two-stage detector."""
    h, w, _ = np_rgb.shape

    with mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.3) as detector:
        det_res = detector.process(np_rgb)

    if not det_res.detections:
        with mp_face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1, refine_landmarks=True) as mesh:
            mesh_res = mesh.process(np_rgb)
            if mesh_res.multi_face_landmarks:
                pts = {}
                for idx, lm in enumerate(mesh_res.multi_face_landmarks[0].landmark):
                    pts[idx] = np.array([lm.x * w, lm.y * h])
                return pts
        return None

    bb = det_res.detections[0].location_data.relative_bounding_box
    pad_x = int(bb.width * w * 0.35)
    pad_y = int(bb.height * h * 0.45)
    bx1 = max(0, int(bb.xmin * w) - pad_x)
    by1 = max(0, int(bb.ymin * h) - pad_y)
    bx2 = min(w, int((bb.xmin + bb.width) * w) + pad_x)
    by2 = min(h, int((bb.ymin + bb.height) * h) + pad_y)

    crop = np_rgb[by1:by2, bx1:bx2]
    ch, cw, _ = crop.shape
    if ch < 20 or cw < 20:
        return None

    with mp_face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1, refine_landmarks=True) as mesh:
        mesh_res = mesh.process(crop)

    if not mesh_res.multi_face_landmarks:
        return None

    pts = {}
    for idx, lm in enumerate(mesh_res.multi_face_landmarks[0].landmark):
        pts[idx] = np.array([lm.x * cw + bx1, lm.y * ch + by1])
    return pts


def _get_or_create_hair_asset(style_item_id: str, subcategory: Optional[str] = None) -> Image.Image:
    """Retrieve hairstyle PNG asset or generate a procedural hairstyle alpha silhouette."""
    filename = (
        HAIRSTYLE_ASSET_MAP.get(style_item_id)
        or (HAIRSTYLE_ASSET_MAP.get(subcategory.lower()) if subcategory else None)
        or "beach_waves.png"
    )

    for base in [settings.catalogue_dir, os.path.join("backend", "catalogue")]:
        asset_path = os.path.join(base, "hairstyles", filename)
        if os.path.exists(asset_path):
            try:
                return Image.open(asset_path).convert("RGBA")
            except Exception as e:
                logger.warning("Could not read hair asset %s: %s", asset_path, e)

    # If no file on disk, create procedural hairstyle template
    return _generate_procedural_hair(filename)


def _generate_procedural_hair(style_name: str) -> Image.Image:
    """Generates an aesthetic stylized hairstyle overlay with alpha transparency."""
    width, height = 600, 650
    img = np.zeros((height, width, 4), dtype=np.uint8)

    # Center crown at (300, 260)
    # Hair silhouette drawing based on style
    if "bob" in style_name or "short" in style_name:
        # Chic bob: rounded cap over head + sleek jawline sides
        cv2.ellipse(img, (300, 250), (220, 200), 0, 0, 360, (40, 35, 35, 240), -1)
        cv2.rectangle(img, (80, 220), (520, 390), (40, 35, 35, 240), -1)
        # Soften edges
        cv2.circle(img, (140, 390), 50, (40, 35, 35, 240), -1)
        cv2.circle(img, (460, 390), 50, (40, 35, 35, 240), -1)
        # Hollow out face window
        face_pts = np.array([
            [170, 210], [430, 210], [400, 420], [300, 470], [200, 420]
        ], np.int32)
        cv2.fillPoly(img, [face_pts], (0, 0, 0, 0))
    elif "updo" in style_name or "ponytail" in style_name:
        # Sleek high ponytail: high bun/tail + sleek pulled back crown
        cv2.circle(img, (300, 110), 90, (30, 28, 28, 250), -1)  # Ponytail bulb
        cv2.ellipse(img, (300, 240), (200, 160), 0, 0, 360, (35, 30, 30, 245), -1)
        # Face cutout
        face_pts = np.array([
            [175, 200], [425, 200], [390, 400], [300, 440], [210, 400]
        ], np.int32)
        cv2.fillPoly(img, [face_pts], (0, 0, 0, 0))
    elif "curls" in style_name or "medium" in style_name:
        # Voluminous curls
        cv2.ellipse(img, (300, 250), (240, 210), 0, 0, 360, (55, 42, 38, 245), -1)
        cv2.rectangle(img, (70, 220), (530, 480), (55, 42, 38, 245), -1)
        for cx in range(80, 530, 45):
            cv2.circle(img, (cx, 470), 38, (55, 42, 38, 245), -1)
        # Face cutout
        face_pts = np.array([
            [175, 205], [425, 205], [395, 410], [300, 460], [205, 410]
        ], np.int32)
        cv2.fillPoly(img, [face_pts], (0, 0, 0, 0))
    else:
        # Beach waves (long cascading waves)
        cv2.ellipse(img, (300, 240), (235, 195), 0, 0, 360, (48, 38, 32, 245), -1)
        cv2.rectangle(img, (65, 220), (535, 590), (48, 38, 32, 245), -1)
        # Bottom strand waves
        for cx in range(80, 530, 50):
            cv2.circle(img, (cx, 580), 45, (48, 38, 32, 245), -1)
        # Face cutout
        face_pts = np.array([
            [180, 210], [420, 210], [390, 420], [300, 470], [210, 420]
        ], np.int32)
        cv2.fillPoly(img, [face_pts], (0, 0, 0, 0))

    # Apply soft Gaussian blur to smooth the hair silhouette
    alpha = img[:, :, 3]
    alpha_blurred = cv2.GaussianBlur(alpha, (9, 9), 3)
    img[:, :, 3] = alpha_blurred

    return Image.fromarray(img, mode="RGBA")


def _apply_hair_color(hair_rgba: Image.Image, color_hex: Optional[str]) -> Image.Image:
    """Modulates the hairstyle color using HSV channel replacement while keeping texture/shading."""
    if not color_hex:
        return hair_rgba

    np_rgba = np.array(hair_rgba)
    rgb = np_rgba[:, :, :3]
    alpha = np_rgba[:, :, 3]

    clean_hex = color_hex.lstrip("#")
    tr, tg, tb = int(clean_hex[0:2], 16), int(clean_hex[2:4], 16), int(clean_hex[4:6], 16)

    # Convert target color to HSV
    target_bgr = np.uint8([[[tb, tg, tr]]])
    target_hsv = cv2.cvtColor(target_bgr, cv2.COLOR_BGR2HSV)[0, 0]
    target_h, target_s = target_hsv[0], target_hsv[1]

    # Convert hair rgb to HSV
    hair_bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    hair_hsv = cv2.cvtColor(hair_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)

    # Modulate Hue and Saturation
    hair_hsv[:, :, 0] = target_h
    hair_hsv[:, :, 1] = np.clip(hair_hsv[:, :, 1] * 0.4 + target_s * 0.7, 0, 255)

    tinted_bgr = cv2.cvtColor(hair_hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    tinted_rgb = cv2.cvtColor(tinted_bgr, cv2.COLOR_BGR2RGB)

    np_rgba[:, :, :3] = tinted_rgb
    np_rgba[:, :, 3] = alpha
    return Image.fromarray(np_rgba, mode="RGBA")


def synthesize_hairstyle_tryon(
    person_img: Image.Image,
    style_item_id: str,
    color_hex: Optional[str] = None,
    subcategory: Optional[str] = None,
) -> Tuple[Image.Image, str, str]:
    """
    Fit hairstyle matched to head orientation and forehead anchor.

    Returns:
        (result_pil, landmark_summary, result_url)
    """
    np_rgb = np.array(person_img.convert("RGB"))
    h, w, _ = np_rgb.shape

    pts = _detect_landmarks_two_stage(np_rgb)
    if pts is None or 10 not in pts or 234 not in pts or 454 not in pts:
        # Fallback to center-head estimation if face landmarks unavailable
        logger.warning("[Hairstyle] Landmark detection failed, using proportional head placement.")
        forehead_pt = np.array([w * 0.5, h * 0.28])
        head_width = w * 0.45
        angle_deg = 0.0
        landmark_summary = "Proportional head-crown estimate"
    else:
        # Use key landmarks
        p_forehead = pts[10]   # Top of forehead
        p_left_ear = pts[234]  # Left tragus
        p_right_ear = pts[454] # Right tragus

        head_width = float(np.linalg.norm(p_right_ear - p_left_ear) * 1.55)
        # Orientation angle from ear line
        dx = p_right_ear[0] - p_left_ear[0]
        dy = p_right_ear[1] - p_left_ear[1]
        angle_deg = math.degrees(math.atan2(dy, dx))
        forehead_pt = p_forehead
        landmark_summary = f"Forehead anchor #10, Ear span #234↔#454 (roll={angle_deg:.1f}°)"

    # 1. Load hairstyle asset
    hair_asset = _get_or_create_hair_asset(style_item_id, subcategory)

    # 2. Apply color tint if provided
    hair_asset = _apply_hair_color(hair_asset, color_hex)

    # 3. Scale hairstyle to head dimensions
    hw_orig, hh_orig = hair_asset.size
    aspect = hh_orig / float(hw_orig)
    target_w = max(40, int(head_width))
    target_h = max(40, int(target_w * aspect))
    hair_resized = hair_asset.resize((target_w, target_h), Image.Resampling.LANCZOS)

    # 4. Rotate by head roll angle
    if abs(angle_deg) > 0.5:
        hair_rotated = hair_resized.rotate(-angle_deg, resample=Image.Resampling.BICUBIC, expand=True)
    else:
        hair_rotated = hair_resized

    # 5. Composite hair at crown/forehead anchor
    # Hair template crown point is near (center_x, 26% of height)
    rw, rh = hair_rotated.size
    paste_x = int(forehead_pt[0] - rw * 0.5)
    paste_y = int(forehead_pt[1] - rh * 0.32)

    composite = person_img.convert("RGBA").copy()
    overlay = Image.new("RGBA", composite.size, (0, 0, 0, 0))
    overlay.paste(hair_rotated, (paste_x, paste_y), hair_rotated)

    final_pil = Image.alpha_composite(composite, overlay).convert("RGB")

    # 6. Save output
    tryon_id = f"tryon-hair-{uuid.uuid4().hex[:10]}"
    out_dir = os.path.join(settings.upload_dir, "tryon")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{tryon_id}.png")
    final_pil.save(out_path, "PNG")

    result_url = f"/uploads/tryon/{tryon_id}.png"
    logger.info("[Hairstyle] Try-on completed for %s -> %s", style_item_id, result_url)
    return final_pil, landmark_summary, result_url
