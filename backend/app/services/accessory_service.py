"""
StyleVision — Virtual Accessory & Jewelry Fitting Service
Uses MediaPipe Face Detection (model_selection=1 for full-body range)
+ MediaPipe Face Mesh (478 landmarks with iris refinement)
+ OpenCV affine transformations for high-precision placement of:
- Glasses & Sunglasses (Eye bridge #168, eye corners #33, #263)
- Earrings (Left earlobe #234, Right earlobe #454)
- Necklaces (Suprasternal notch / neck below chin #152)
- Nose Pins (Nostril ala #278 / #48)
"""
import os
import math
import uuid
import logging
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
mp_pose = mp.solutions.pose

ACCESSORY_ASSET_MAP = {
    # Glasses & Sunglasses
    "item-acc-1": "aviator_sunglasses.png",
    "glasses_aviator": "aviator_sunglasses.png",
    "glasses_wayfarer": "wayfarer_glasses.png",
    "glasses": "aviator_sunglasses.png",
    "sunglasses": "aviator_sunglasses.png",
    # Earrings
    "item-acc-2": "chandelier_earring.png",
    "earrings_chandelier": "chandelier_earring.png",
    "earrings_hoop": "gold_hoop.png",
    "earrings": "chandelier_earring.png",
    "earring": "chandelier_earring.png",
    # Necklace
    "item-acc-3": "gold_necklace.png",
    "necklace_gold": "gold_necklace.png",
    "necklace": "gold_necklace.png",
    # Nose Pin
    "item-acc-4": "diamond_nose_pin.png",
    "nose_pin": "diamond_nose_pin.png",
    "nosepin": "diamond_nose_pin.png",
    # Bangles & Bracelets
    "item-acc-5": "gold_bangles.png",
    "bangles": "gold_bangles.png",
    "bangle": "gold_bangles.png",
    "bracelet": "gold_bangles.png",
    "rings": "gold_bangles.png",
    # Handbag
    "item-acc-7": "leather_handbag.png",
    "handbag": "leather_handbag.png",
    "bags": "leather_handbag.png",
    "bag": "leather_handbag.png",
    # Watch
    "item-acc-8": "luxury_watch.png",
    "watch": "luxury_watch.png",
    "wrist_watch": "luxury_watch.png",
}


def _clean_accessory_background(img: Image.Image) -> Image.Image:
    """If image is not already transparent RGBA, remove white/solid background."""
    img_rgba = img.convert("RGBA")
    arr = np.array(img_rgba, dtype=np.float32)
    h, w = arr.shape[:2]
    # Sample 4 corners
    corners = [arr[0, 0, :3], arr[0, w - 1, :3], arr[h - 1, 0, :3], arr[h - 1, w - 1, :3]]
    bg = np.median(corners, axis=0)
    diff = np.sqrt(np.sum((arr[:, :, :3] - bg) ** 2, axis=-1))
    mask = diff > 28.0
    arr[:, :, 3] = np.where(mask, 255.0, 0.0)
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def _get_accessory_image(
    style_item_id: str,
    subcategory: str,
    custom_image_url: Optional[str] = None,
) -> Optional[Image.Image]:
    """Retrieve or load the accessory RGBA transparent PNG from catalogue or user upload."""
    # 1. Custom image url provided directly
    if custom_image_url:
        clean_path = custom_image_url.lstrip("/").replace("/", os.sep)
        for cand in [
            clean_path,
            os.path.join(settings.upload_dir, os.path.basename(clean_path)),
            os.path.join(settings.upload_dir, "accessories", os.path.basename(clean_path)),
        ]:
            if os.path.exists(cand):
                try:
                    img = Image.open(cand)
                    return _clean_accessory_background(img)
                except Exception as exc:
                    logger.warning("Failed to open custom accessory %s: %s", cand, exc)

    # 2. Check if style_item_id is in uploads/accessories
    acc_upload_dir = os.path.join(settings.upload_dir, "accessories")
    if os.path.exists(acc_upload_dir):
        for f in os.listdir(acc_upload_dir):
            if style_item_id in f:
                try:
                    img = Image.open(os.path.join(acc_upload_dir, f))
                    return _clean_accessory_background(img)
                except Exception:
                    pass

    # 3. Check catalogue assets
    filename = (
        ACCESSORY_ASSET_MAP.get(style_item_id)
        or ACCESSORY_ASSET_MAP.get(subcategory.lower())
    )
    if not filename:
        sub = subcategory.lower()
        if "glass" in sub:
            filename = "aviator_sunglasses.png"
        elif "ear" in sub:
            filename = "chandelier_earring.png"
        elif "neck" in sub:
            filename = "gold_necklace.png"
        elif "nose" in sub:
            filename = "diamond_nose_pin.png"
        elif "bag" in sub or "handbag" in sub:
            filename = "leather_handbag.png"
        elif "bangle" in sub or "bracelet" in sub or "ring" in sub:
            filename = "gold_bangles.png"
        elif "watch" in sub:
            filename = "luxury_watch.png"

    if filename:
        for base in [settings.catalogue_dir, os.path.join("backend", "catalogue")]:
            asset_path = os.path.join(base, "accessories", filename)
            if os.path.exists(asset_path):
                return Image.open(asset_path).convert("RGBA")

    logger.warning("Accessory asset '%s' not found for subcategory '%s'.", filename, subcategory)
    return None


def _detect_landmarks_two_stage(np_rgb: np.ndarray) -> Optional[Dict[int, np.ndarray]]:
    """
    Detects face landmarks on both close-up and full-body images using two stages:
    1. Full-range FaceDetection (range up to 5m) to locate the head bbox.
    2. FaceMesh on the cropped head to get 478 precise landmarks, projected back to full image.
    """
    h, w, _ = np_rgb.shape
    
    # Stage 1: Detect head bounding box
    with mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.3) as detector:
        det_res = detector.process(np_rgb)
        
    if not det_res.detections:
        # Fallback to direct FaceMesh on entire image
        with mp_face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1, refine_landmarks=True) as mesh:
            mesh_res = mesh.process(np_rgb)
            if mesh_res.multi_face_landmarks:
                pts = {}
                for idx, lm in enumerate(mesh_res.multi_face_landmarks[0].landmark):
                    pts[idx] = np.array([lm.x * w, lm.y * h])
                return pts
        return None

    # Get primary face bbox with padding
    bbox = det_res.detections[0].location_data.relative_bounding_box
    pad_x = bbox.width * 0.35
    pad_y = bbox.height * 0.45
    
    x1 = max(0, int((bbox.xmin - pad_x) * w))
    y1 = max(0, int((bbox.ymin - pad_y) * h))
    x2 = min(w, int((bbox.xmin + bbox.width + pad_x) * w))
    y2 = min(h, int((bbox.ymin + bbox.height + pad_y) * h))
    
    crop = np_rgb[y1:y2, x1:x2]
    crop_h, crop_w, _ = crop.shape
    if crop_h < 10 or crop_w < 10:
        return None

    # Stage 2: FaceMesh on cropped head
    with mp_face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1, refine_landmarks=True) as mesh:
        mesh_res = mesh.process(crop)
        if not mesh_res.multi_face_landmarks:
            return None
            
        pts = {}
        for idx, lm in enumerate(mesh_res.multi_face_landmarks[0].landmark):
            # Map back to original image coordinate space
            global_x = x1 + (lm.x * crop_w)
            global_y = y1 + (lm.y * crop_h)
            pts[idx] = np.array([global_x, global_y])
        return pts


def synthesize_accessory_tryon(
    person_img: Image.Image,
    style_item_id: str,
    subcategory: str,
    custom_image_url: Optional[str] = None,
    override_x: Optional[float] = None,
    override_y: Optional[float] = None,
    override_scale: Optional[float] = None,
) -> Tuple[Image.Image, str, str, Optional[str], Optional[str]]:
    """
    Fits glasses, earrings, necklace, or nose pin to person image using MediaPipe landmarks.
    Returns: (final_rgb, landmark_desc, result_url, closeup_result_url, closeup_orig_url)
    """
    pw, ph = person_img.size
    np_img = np.array(person_img.convert("RGB"))
    subcat = subcategory.lower()
    canvas = person_img.convert("RGBA")
    
    acc_img = _get_accessory_image(style_item_id, subcat, custom_image_url)
    if acc_img is None:
        tryon_id = f"tryon-acc-{uuid.uuid4().hex[:10]}"
        return canvas.convert("RGB"), "Fallback", f"/uploads/tryon/{tryon_id}.png", None, None

    landmarks = _detect_landmarks_two_stage(np_img)
    landmark_desc = "Facial Landmark Anchor"

    if landmarks:
        def pt(idx):
            return landmarks[idx]

        # ── 1. GLASSES & SUNGLASSES ──────────────────────────────────────────
        if "glass" in subcat or subcat == "glasses":
            # Landmarks: #33 (left outer eye), #263 (right outer eye), #168 (eye bridge / nasion)
            p_left = pt(33)
            p_right = pt(263)
            p_bridge = pt(168)
            
            dx = p_right[0] - p_left[0]
            dy = p_right[1] - p_left[1]
            angle_deg = -math.degrees(math.atan2(dy, dx))
            eye_dist = math.hypot(dx, dy)
            
            scale_factor = override_scale if override_scale else 1.0
            # Width spans across both temples (~2.35x outer eye span)
            target_w = int(eye_dist * 2.35 * scale_factor)
            target_h = int(target_w * (acc_img.height / acc_img.width))
            
            resized = acc_img.resize((max(10, target_w), max(10, target_h)), Image.Resampling.LANCZOS)
            rotated = resized.rotate(angle_deg, resample=Image.Resampling.BICUBIC, expand=True)
            
            cx = p_bridge[0]
            cy = p_bridge[1] + (eye_dist * 0.04)
            if override_x is not None:
                cx = override_x * pw
            if override_y is not None:
                cy = override_y * ph
                
            paste_x = int(cx - (rotated.width / 2))
            paste_y = int(cy - (rotated.height / 2))
            canvas.alpha_composite(rotated, (paste_x, paste_y))
            landmark_desc = f"Eye Bridge (Mesh #168, angle {angle_deg:.1f}°)"

        # ── 2. EARRINGS ──────────────────────────────────────────────────────
        elif "earring" in subcat or subcat == "earrings":
            # Landmarks: #234 (left earlobe), #454 (right earlobe), #152 (chin bottom), #10 (forehead)
            p_left_ear = pt(234)
            p_right_ear = pt(454)
            p_chin = pt(152)
            p_forehead = pt(10)
            
            face_h = math.hypot(p_chin[0] - p_forehead[0], p_chin[1] - p_forehead[1])
            scale_factor = override_scale if override_scale else 1.0
            earring_h = int(face_h * 0.32 * scale_factor)
            earring_w = int(earring_h * (acc_img.width / acc_img.height))
            
            resized_earring = acc_img.resize((max(8, earring_w), max(8, earring_h)), Image.Resampling.LANCZOS)
            
            # Left Earring
            lx = int(p_left_ear[0] - (resized_earring.width / 2))
            ly = int(p_left_ear[1] - 4)
            canvas.alpha_composite(resized_earring, (lx, ly))
            
            # Right Earring (Mirrored for natural 3D symmetry)
            right_earring = ImageOps.mirror(resized_earring)
            rx = int(p_right_ear[0] - (right_earring.width / 2))
            ry = int(p_right_ear[1] - 4)
            canvas.alpha_composite(right_earring, (rx, ry))
            
            landmark_desc = "Earlobes (Mesh #234 & #454)"

        # ── 3. NECKLACE ──────────────────────────────────────────────────────
        elif "necklace" in subcat:
            # Landmarks: #152 (chin bottom), #1 (nose tip), #234 (left jaw), #454 (right jaw)
            p_chin = pt(152)
            p_nose = pt(1)
            p_left_jaw = pt(234)
            p_right_jaw = pt(454)
            
            jaw_w = math.hypot(p_right_jaw[0] - p_left_jaw[0], p_right_jaw[1] - p_left_jaw[1])
            nose_to_chin = abs(p_chin[1] - p_nose[1])
            
            scale_factor = override_scale if override_scale else 1.0
            target_w = int(jaw_w * 1.55 * scale_factor)
            target_h = int(target_w * (acc_img.height / acc_img.width))
            
            resized_neck = acc_img.resize((max(20, target_w), max(20, target_h)), Image.Resampling.LANCZOS)
            
            dx = p_right_jaw[0] - p_left_jaw[0]
            dy = p_right_jaw[1] - p_left_jaw[1]
            angle_deg = -math.degrees(math.atan2(dy, dx))
            rotated_neck = resized_neck.rotate(angle_deg, resample=Image.Resampling.BICUBIC, expand=True)
            
            cx = p_chin[0]
            cy = p_chin[1] + (nose_to_chin * 0.45)
            if override_x is not None:
                cx = override_x * pw
            if override_y is not None:
                cy = override_y * ph
                
            paste_x = int(cx - (rotated_neck.width / 2))
            paste_y = int(cy)
            canvas.alpha_composite(rotated_neck, (paste_x, paste_y))
            landmark_desc = f"Collarbones / Neck Base (Mesh #152, angle {angle_deg:.1f}°)"

        # ── 4. NOSE PIN ──────────────────────────────────────────────────────
        elif "nose" in subcat:
            p_nostril = pt(278)
            p_bridge = pt(168)
            p_tip = pt(1)
            
            nose_len = math.hypot(p_tip[0] - p_bridge[0], p_tip[1] - p_bridge[1])
            scale_factor = override_scale if override_scale else 1.0
            pin_size = int(nose_len * 0.18 * scale_factor)
            
            resized_pin = acc_img.resize((max(6, pin_size), max(6, pin_size)), Image.Resampling.LANCZOS)
            paste_x = int(p_nostril[0] - (resized_pin.width / 2))
            paste_y = int(p_nostril[1] - (resized_pin.height / 2))
            canvas.alpha_composite(resized_pin, (paste_x, paste_y))
            landmark_desc = "Left Nostril Ala (Mesh #278)"

        # ── 5. HANDBAG ───────────────────────────────────────────────────────
        elif "bag" in subcat or "handbag" in subcat:
            scale_factor = override_scale if override_scale else 1.0
            p_chin = pt(152)
            p_left_ear = pt(234)
            p_right_ear = pt(454)
            face_w = math.hypot(p_right_ear[0] - p_left_ear[0], p_right_ear[1] - p_left_ear[1])

            # Try MediaPipe Pose for hip / shoulder placement
            placed = False
            try:
                with mp_pose.Pose(static_image_mode=True, min_detection_confidence=0.3) as pose_detector:
                    pose_res = pose_detector.process(np_img)
                if pose_res.pose_landmarks:
                    pl = pose_res.pose_landmarks.landmark
                    # Check hip (#23 left, #24 right)
                    if pl[23].visibility > 0.35 or pl[24].visibility > 0.35:
                        hip = pl[23] if pl[23].visibility >= pl[24].visibility else pl[24]
                        hx, hy = hip.x * pw, hip.y * ph
                        target_w = int(pw * 0.36 * scale_factor)
                        target_h = int(target_w * (acc_img.height / acc_img.width))
                        resized_bag = acc_img.resize((max(20, target_w), max(20, target_h)), Image.Resampling.LANCZOS)
                        paste_x = int(hx - resized_bag.width * 0.5)
                        paste_y = int(hy - resized_bag.height * 0.25)
                        canvas.alpha_composite(resized_bag, (max(0, paste_x), max(0, paste_y)))
                        landmark_desc = "Hip Line Anchor (Pose #23/#24)"
                        placed = True
            except Exception as pe:
                logger.debug("Pose detection fallback for handbag: %s", pe)

            if not placed:
                # Proportional torso / side placement
                target_w = int(max(face_w * 2.2, pw * 0.34) * scale_factor)
                target_h = int(target_w * (acc_img.height / acc_img.width))
                resized_bag = acc_img.resize((max(20, target_w), max(20, target_h)), Image.Resampling.LANCZOS)
                cx = override_x * pw if override_x is not None else pw * 0.64
                cy = override_y * ph if override_y is not None else max(p_chin[1] + face_w * 1.5, ph * 0.52)
                paste_x = int(cx - (resized_bag.width / 2))
                paste_y = int(cy)
                canvas.alpha_composite(resized_bag, (max(0, min(pw - resized_bag.width, paste_x)), max(0, min(ph - resized_bag.height, paste_y))))
                landmark_desc = "Side-Torso Placement (Proportional)"

        # ── 6. BANGLES & BRACELET ───────────────────────────────────────────
        elif "bangle" in subcat or "bracelet" in subcat:
            scale_factor = override_scale if override_scale else 1.0
            p_chin = pt(152)
            p_left_ear = pt(234)
            p_right_ear = pt(454)
            face_w = math.hypot(p_right_ear[0] - p_left_ear[0], p_right_ear[1] - p_left_ear[1])

            placed = False
            try:
                with mp_pose.Pose(static_image_mode=True, min_detection_confidence=0.3) as pose_detector:
                    pose_res = pose_detector.process(np_img)
                if pose_res.pose_landmarks:
                    pl = pose_res.pose_landmarks.landmark
                    if pl[15].visibility > 0.35 or pl[16].visibility > 0.35:
                        wrist = pl[15] if pl[15].visibility >= pl[16].visibility else pl[16]
                        wx, wy = wrist.x * pw, wrist.y * ph
                        target_w = int(pw * 0.22 * scale_factor)
                        target_h = int(target_w * (acc_img.height / acc_img.width))
                        resized_bangle = acc_img.resize((max(15, target_w), max(15, target_h)), Image.Resampling.LANCZOS)
                        paste_x = int(wx - resized_bangle.width / 2)
                        paste_y = int(wy - resized_bangle.height / 2)
                        canvas.alpha_composite(resized_bangle, (max(0, min(pw - resized_bangle.width, paste_x)), max(0, min(ph - resized_bangle.height, paste_y))))
                        landmark_desc = f"Wrist Bangle Anchor (Pose #{15 if wrist == pl[15] else 16})"
                        placed = True
            except Exception as pe:
                logger.debug("Pose detection fallback for bangles: %s", pe)

            if not placed:
                target_w = int(max(face_w * 1.3, pw * 0.24) * scale_factor)
                target_h = int(target_w * (acc_img.height / acc_img.width))
                resized_bangle = acc_img.resize((max(15, target_w), max(15, target_h)), Image.Resampling.LANCZOS)
                cx = override_x * pw if override_x is not None else pw * 0.72
                cy = override_y * ph if override_y is not None else max(p_chin[1] + face_w * 1.8, ph * 0.68)
                paste_x = int(cx - (resized_bangle.width / 2))
                paste_y = int(cy)
                canvas.alpha_composite(resized_bangle, (max(0, min(pw - resized_bangle.width, paste_x)), max(0, min(ph - resized_bangle.height, paste_y))))
                landmark_desc = "Wrist / Forearm Level Placement"

        # ── 7. WRIST WATCH ───────────────────────────────────────────────────
        elif "watch" in subcat:
            scale_factor = override_scale if override_scale else 1.0
            p_chin = pt(152)
            p_left_ear = pt(234)
            p_right_ear = pt(454)
            face_w = math.hypot(p_right_ear[0] - p_left_ear[0], p_right_ear[1] - p_left_ear[1])

            placed = False
            try:
                with mp_pose.Pose(static_image_mode=True, min_detection_confidence=0.3) as pose_detector:
                    pose_res = pose_detector.process(np_img)
                if pose_res.pose_landmarks:
                    pl = pose_res.pose_landmarks.landmark
                    if pl[15].visibility > 0.35 or pl[16].visibility > 0.35:
                        wrist = pl[15] if pl[15].visibility >= pl[16].visibility else pl[16]
                        elbow = pl[13] if wrist == pl[15] else pl[14]
                        wx, wy = wrist.x * pw, wrist.y * ph
                        ex, ey = elbow.x * pw, elbow.y * ph
                        angle_deg = -math.degrees(math.atan2(wy - ey, wx - ex)) + 90

                        target_w = int(pw * 0.18 * scale_factor)
                        target_h = int(target_w * (acc_img.height / acc_img.width))
                        resized_watch = acc_img.resize((max(15, target_w), max(15, target_h)), Image.Resampling.LANCZOS)
                        rotated_watch = resized_watch.rotate(angle_deg, resample=Image.Resampling.BICUBIC, expand=True)

                        paste_x = int(wx - (rotated_watch.width / 2))
                        paste_y = int(wy - (rotated_watch.height / 2))
                        canvas.alpha_composite(rotated_watch, (max(0, min(pw - rotated_watch.width, paste_x)), max(0, min(ph - rotated_watch.height, paste_y))))
                        landmark_desc = f"Wrist Chronometer Anchor (Pose #{15 if wrist == pl[15] else 16}, angle {angle_deg:.1f}°)"
                        placed = True
            except Exception as pe:
                logger.debug("Pose detection fallback for watch: %s", pe)

            if not placed:
                target_w = int(max(face_w * 1.1, pw * 0.19) * scale_factor)
                target_h = int(target_w * (acc_img.height / acc_img.width))
                resized_watch = acc_img.resize((max(15, target_w), max(15, target_h)), Image.Resampling.LANCZOS)
                cx = override_x * pw if override_x is not None else pw * 0.18
                cy = override_y * ph if override_y is not None else max(p_chin[1] + face_w * 1.8, ph * 0.68)
                paste_x = int(cx - (resized_watch.width / 2))
                paste_y = int(cy)
                canvas.alpha_composite(resized_watch, (max(0, min(pw - resized_watch.width, paste_x)), max(0, min(ph - resized_watch.height, paste_y))))
                landmark_desc = "Wrist Level Anchor (Proportional)"

        else:
            # General accessory fallback
            target_w = int(pw * 0.35)
            target_h = int(target_w * (acc_img.height / acc_img.width))
            resized_acc = acc_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
            canvas.alpha_composite(resized_acc, (int(pw * 0.65), int(ph * 0.55)))
            landmark_desc = "Torso / Hip Anchor"

    else:
        logger.warning("No face detected by two-stage MediaPipe. Using anatomical estimate.")
        target_w = int(pw * 0.45)
        target_h = int(target_w * (acc_img.height / acc_img.width))
        resized = acc_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        canvas.alpha_composite(resized, (int(pw * 0.28), int(ph * 0.22)))
        landmark_desc = "Anatomical Head Estimate"

    # Save output
    os.makedirs(os.path.join(settings.upload_dir, "tryon"), exist_ok=True)
    tryon_id = f"tryon-acc-{uuid.uuid4().hex[:10]}"
    output_filename = f"{tryon_id}.png"
    output_path = os.path.join(settings.upload_dir, "tryon", output_filename)
    
    final_rgb = canvas.convert("RGB")
    final_rgb.save(output_path, format="PNG")
    result_url = f"/uploads/tryon/{output_filename}"

    # Generate Close-up Portrait Crop (Head & Neck Zoom)
    closeup_result_url = None
    closeup_orig_url = None
    if landmarks:
        try:
            p_forehead = pt(10)
            p_chin = pt(152)
            p_left_ear = pt(234)
            p_right_ear = pt(454)

            face_w = max(40, int(abs(p_right_ear[0] - p_left_ear[0])))
            face_h = max(50, int(abs(p_chin[1] - p_forehead[1])))
            cx = (p_left_ear[0] + p_right_ear[0]) / 2.0

            # Crop width covers beyond both ears (~2.4x face width)
            crop_w = int(face_w * 2.4)
            # Crop height covers hair top down through collarbones (~2.8x face height)
            crop_h = int(face_h * 2.8)

            x1 = max(0, int(cx - crop_w / 2))
            x2 = min(pw, int(cx + crop_w / 2))
            y1 = max(0, int(p_forehead[1] - face_h * 0.45))
            y2 = min(ph, int(y1 + crop_h))

            if (x2 - x1) > 40 and (y2 - y1) > 40:
                crop_res = final_rgb.crop((x1, y1, x2, y2))
                crop_orig = person_img.convert("RGB").crop((x1, y1, x2, y2))

                closeup_filename = f"{tryon_id}_closeup.png"
                closeup_orig_filename = f"{tryon_id}_orig_closeup.png"

                crop_res.save(os.path.join(settings.upload_dir, "tryon", closeup_filename), format="PNG")
                crop_orig.save(os.path.join(settings.upload_dir, "tryon", closeup_orig_filename), format="PNG")

                closeup_result_url = f"/uploads/tryon/{closeup_filename}"
                closeup_orig_url = f"/uploads/tryon/{closeup_orig_filename}"
        except Exception as e:
            logger.warning("Failed to generate closeup crop: %s", e)
    
    logger.info("Accessory try-on completed: %s -> %s (closeup: %s)", landmark_desc, result_url, closeup_result_url)
    return final_rgb, landmark_desc, result_url, closeup_result_url, closeup_orig_url
