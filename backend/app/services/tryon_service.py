"""
StyleVision — Virtual Try-On Image Synthesis Service
Generates clothing try-on composites for both personal wardrobe dresses and catalogue items.
- If TRYON_MODE=catvton and CATVTON_ENDPOINT is set: connects to CatVTON diffusion pipeline on Cloud GPU
- If CPU (Prototype Mode): executes background removal, anatomical torso scaling, and clear labelling
"""
from datetime import datetime, timezone
import io
import logging
import os
import uuid
from typing import Tuple, Optional
import httpx
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from app.config import get_settings
from app.database import get_database
from app.models.tryon import TryOnStatus, TryOnMode

logger = logging.getLogger(__name__)
settings = get_settings()
TRYON_OUTPUT_DIR = os.path.join(settings.upload_dir, "tryon")


def _determine_cloth_type(
    garment_category: Optional[str] = None,
    garment_name: Optional[str] = None,
    garment_id: Optional[str] = None,
    explicit_cloth_type: Optional[str] = None,
) -> str:
    """
    Classify garment into CatVTON categories: 'upper', 'lower', or 'overall'.
    Supported categories:
    - top: shirts, tops, t-shirts, kurtis, blouses -> 'upper'
    - bottom: pants, jeans, skirts, trousers, shorts -> 'lower'
    - outerwear: jackets, coats, blazers, cardigans -> 'upper'
    - overall: full outfits, jumpsuits, gowns, dresses, lehengas -> 'overall'
    """
    if explicit_cloth_type in ("upper", "lower", "overall"):
        return explicit_cloth_type

    cat = (garment_category or "").lower().strip()
    if cat in ("top", "tops", "shirt", "t-shirt", "kurti", "blouse", "upper"):
        return "upper"
    if cat in ("bottom", "bottoms", "pant", "pants", "jeans", "skirt", "trouser", "shorts", "lower"):
        return "lower"
    if cat in ("outerwear", "jacket", "coat", "blazer", "hoodie", "cardigan"):
        return "upper"
    if cat in ("overall", "overalls", "dress", "ethnic", "gown", "saree", "suit", "jumpsuit", "lehenga"):
        return "overall"

    # Fallback to inspecting garment_name and garment_id only if category was not provided
    name = f"{garment_name or ''} {garment_id or ''}".lower()
    if any(k in name for k in ["pant", "skirt", "jean", "trouser", "palazzo", "bottom", "shorts", "legging"]):
        return "lower"
    if any(k in name for k in ["top", "shirt", "kurti", "t-shirt", "tee", "blouse", "jacket", "coat", "hoodie", "sweater", "blazer", "outerwear"]):
        return "upper"
    if any(k in name for k in ["saree", "sari", "gown", "dress", "lehenga", "anarkali", "suit", "jumpsuit", "maxi", "overall"]):
        return "overall"

    return "upper"


def _clean_garment_background(img: Image.Image) -> Image.Image:
    """
    Remove the studio background from a garment photo — works for ANY background color
    (white, light blue, olive, dark green, grey, etc.) by sampling extensively from all edges.
    """
    img_rgba = img.convert("RGBA")
    arr = np.array(img_rgba, dtype=np.float32)
    h, w = arr.shape[:2]

    # Sample densely from all 4 edges to detect background color
    edge_pixels = []
    step_w = max(1, w // 40)
    step_h = max(1, h // 40)
    for x in range(0, w, step_w):
        edge_pixels.extend([arr[0, x, :3], arr[1, x, :3], arr[h - 1, x, :3], arr[h - 2, x, :3]])
    for y in range(0, h, step_h):
        edge_pixels.extend([arr[y, 0, :3], arr[y, 1, :3], arr[y, w - 1, :3], arr[y, w - 2, :3]])

    edge_arr = np.array(edge_pixels)
    # Median is robust — garment edges bleeding into border won't skew it
    bg_color = np.median(edge_arr, axis=0)

    # Pixel-wise distance from background color
    diff = np.sqrt(np.sum((arr[:, :, :3] - bg_color) ** 2, axis=-1))

    # Threshold: tighter for complex backgrounds, wider for clean studio backgrounds
    bg_spread = float(np.std(edge_arr))
    threshold = max(30.0, min(65.0, bg_spread * 1.5 + 28.0))

    result = np.array(img_rgba)
    result[diff < threshold, 3] = 0
    return Image.fromarray(result, "RGBA")


def _get_or_create_person_image(person_id: str) -> Tuple[Image.Image, str]:
    """Load the person portrait or create a graceful demonstration portrait if demo ID."""
    os.makedirs(settings.upload_dir, exist_ok=True)

    # Check if this matches a file in uploads
    clean_id = person_id.replace("img-", "")
    for fname in os.listdir(settings.upload_dir):
        if (clean_id in fname or person_id in fname) and os.path.isfile(os.path.join(settings.upload_dir, fname)):
            path = os.path.join(settings.upload_dir, fname)
            try:
                img = Image.open(path).convert("RGBA")
                return img, f"/uploads/{fname}"
            except Exception:
                pass

    # If demo or not found, automatically use user's most recent uploaded photo if available
    user_photos = [
        f for f in os.listdir(settings.upload_dir)
        if f.startswith("person_user_") and os.path.isfile(os.path.join(settings.upload_dir, f))
    ]
    if user_photos:
        user_photos.sort(key=lambda f: os.path.getmtime(os.path.join(settings.upload_dir, f)), reverse=True)
        selected_photo = user_photos[0]
        try:
            import mediapipe as mp
            mp_fd = mp.solutions.face_detection
            with mp_fd.FaceDetection(model_selection=1, min_detection_confidence=0.2) as fd:
                for candidate in user_photos[:5]:
                    cand_path = os.path.join(settings.upload_dir, candidate)
                    try:
                        c_img = Image.open(cand_path).convert("RGB")
                        res = fd.process(np.array(c_img))
                        if res.detections:
                            selected_photo = candidate
                            break
                    except Exception:
                        pass
        except Exception:
            pass

        path = os.path.join(settings.upload_dir, selected_photo)
        try:
            img = Image.open(path).convert("RGBA")
            return img, f"/uploads/{selected_photo}"
        except Exception:
            pass

    # Create a clean demonstration portrait (full body / torso)
    w, h = 600, 800
    person_img = Image.new("RGBA", (w, h), (26, 18, 48, 255))
    draw = ImageDraw.Draw(person_img)

    # Gradient background
    for y in range(h):
        r = int(26 + (y / h) * 15)
        g = int(18 + (y / h) * 10)
        b = int(48 + (y / h) * 25)
        draw.line([(0, y), (w, y)], fill=(r, g, b, 255))

    # Stylized humanoid mannequin / person silhouette
    center_x = w // 2
    # Head & face
    draw.ellipse([center_x - 55, 120, center_x + 55, 230], fill=(225, 195, 175, 255))
    # Neck
    draw.rectangle([center_x - 22, 225, center_x + 22, 275], fill=(210, 180, 160, 255))
    # Shoulders & Torso base
    torso_coords = [
        (center_x - 130, 280),
        (center_x + 130, 280),
        (center_x + 95, 620),
        (center_x - 95, 620),
    ]
    draw.polygon(torso_coords, fill=(50, 40, 70, 255))
    # Arms
    draw.line([(center_x - 130, 280), (center_x - 170, 520)], fill=(210, 180, 160, 255), width=32)
    draw.line([(center_x + 130, 280), (center_x + 170, 520)], fill=(210, 180, 160, 255), width=32)
    # Legs base
    draw.line([(center_x - 45, 620), (center_x - 50, 790)], fill=(40, 30, 55, 255), width=42)
    draw.line([(center_x + 45, 620), (center_x + 50, 790)], fill=(40, 30, 55, 255), width=42)

    demo_filename = "demo_person_model.png"
    demo_path = os.path.join(settings.upload_dir, demo_filename)
    person_img.save(demo_path)
    return person_img, f"/uploads/{demo_filename}"


def _get_or_create_garment_image(
    garment_id: str,
    source: str,
    garment_color: Optional[str] = None,
    garment_name: Optional[str] = None,
    garment_image_path: Optional[str] = None,
) -> Tuple[Image.Image, str]:
    """Retrieve garment from user's wardrobe or catalogue, or render a tailored garment overlay."""
    if garment_image_path:
        clean_path = garment_image_path.lstrip("/").replace("/", os.sep)
        candidates = [
            clean_path,
            os.path.join(settings.upload_dir, os.path.basename(clean_path)),
            os.path.join(settings.upload_dir, "wardrobe", os.path.basename(clean_path)),
        ]
        for candidate in candidates:
            if os.path.isfile(candidate):
                try:
                    img = Image.open(candidate).convert("RGBA")
                    return _clean_garment_background(img), garment_image_path
                except Exception:
                    pass

    wardrobe_dir = os.path.join(settings.upload_dir, "wardrobe")
    if os.path.exists(wardrobe_dir):
        for fname in os.listdir(wardrobe_dir):
            if garment_id in fname:
                path = os.path.join(wardrobe_dir, fname)
                try:
                    raw_img = Image.open(path).convert("RGBA")
                    return _clean_garment_background(raw_img), f"/uploads/wardrobe/{fname}"
                except Exception:
                    pass

    # Create garment representation
    w, h = 400, 500
    garment_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(garment_img)

    color_hex = garment_color or "#7C4DFF"
    try:
        color_rgb = tuple(int(color_hex.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        color_rgb = (124, 77, 255)

    # Render a dress / top shape with neckline and contour
    cx = w // 2
    dress_shape = [
        (cx - 50, 20),   # Left collar
        (cx - 150, 80),  # Left shoulder
        (cx - 120, 260), # Left waist
        (cx - 160, 480), # Left hem
        (cx + 160, 480), # Right hem
        (cx + 120, 260), # Right waist
        (cx + 150, 80),  # Right shoulder
        (cx + 50, 20),   # Right collar
        (cx, 60),        # Neckline dip
    ]
    draw.polygon(dress_shape, fill=(*color_rgb, 240))
    draw.line(dress_shape + [dress_shape[0]], fill=(255, 255, 255, 60), width=2)

    garment_filename = f"garment_{garment_id}.png"
    garment_path = os.path.join(settings.upload_dir, garment_filename)
    garment_img.save(garment_path)
    return garment_img, f"/uploads/{garment_filename}"


async def _call_catvton_cloud(
    endpoint: str,
    person_img: Image.Image,
    garment_img: Image.Image,
    cloth_type: str = "overall",
    timeout_secs: float = 300.0,
    max_retries: int = 3,
) -> Optional[Image.Image]:
    """
    Call Google Colab/Kaggle CatVTON GPU server via Cloudflare/ngrok HTTPS tunnel.
    Preserves user pose, face, posture, hands, and background completely.
    Retries up to max_retries times on transient DNS/connection failures (common on mobile hotspots).
    """
    import asyncio as _asyncio

    clean_endpoint = endpoint.strip().rstrip("/")
    url = f"{clean_endpoint}/tryon"
    logger.info("Calling CatVTON Cloud GPU endpoint: %s with cloth_type=%s", url, cloth_type)

    p_buf = io.BytesIO()
    person_img.convert("RGB").save(p_buf, format="JPEG", quality=95)
    p_bytes = p_buf.getvalue()

    g_buf = io.BytesIO()
    garment_img.convert("RGB").save(g_buf, format="JPEG", quality=95)
    g_bytes = g_buf.getvalue()

    data = {
        "cloth_type": cloth_type,
        "num_steps": "40",
        "guidance_scale": "2.5",
        "seed": "42",
    }

    last_exc: Exception = RuntimeError("No attempts made")
    for attempt in range(1, max_retries + 1):
        try:
            files = {
                "person_image": ("person.jpg", p_bytes, "image/jpeg"),
                "cloth_image": ("cloth.jpg", g_bytes, "image/jpeg"),
            }
            async with httpx.AsyncClient(timeout=timeout_secs) as client:
                resp = await client.post(url, files=files, data=data)
                if resp.status_code == 200:
                    logger.info("CatVTON success on attempt %d", attempt)
                    return Image.open(io.BytesIO(resp.content)).convert("RGBA")
                else:
                    raise RuntimeError(f"CatVTON server error {resp.status_code}: {resp.text[:300]}")
        except (httpx.ConnectError, httpx.ConnectTimeout, OSError) as exc:
            last_exc = exc
            if attempt < max_retries:
                wait = attempt * 2  # 2s, 4s between retries
                logger.warning("CatVTON attempt %d/%d failed (%s). Retrying in %ds...", attempt, max_retries, repr(exc), wait)
                await _asyncio.sleep(wait)
            else:
                logger.error("CatVTON all %d attempts failed. Last error: %s", max_retries, repr(exc))
                raise last_exc


async def synthesize_outfit_tryon(
    person_image_id: str,
    garment_id: str,
    source: str = "catalogue",
    garment_color: Optional[str] = None,
    garment_name: Optional[str] = None,
    garment_image_path: Optional[str] = None,
    garment_category: Optional[str] = None,
    explicit_cloth_type: Optional[str] = None,
) -> dict:
    """
    Execute virtual clothing try-on pipeline:
    1. Loads person photograph & target garment
    2. If TRYON_MODE=catvton and endpoint set: calls CatVTON diffusion pipeline on GPU
    3. If prototype mode or fallback: performs anatomical torso scaling with keyed garment background
    4. Saves output and persists lookbook record in MongoDB
    """
    os.makedirs(TRYON_OUTPUT_DIR, exist_ok=True)
    tryon_id = f"tryon-outfit-{uuid.uuid4().hex[:10]}"

    # Step 1: Load Person
    person_img, person_url = _get_or_create_person_image(person_image_id)
    pw, ph = person_img.size

    # Step 2: Load Garment
    garment_img, garment_url = _get_or_create_garment_image(
        garment_id=garment_id,
        source=source,
        garment_color=garment_color,
        garment_name=garment_name,
        garment_image_path=garment_image_path,
    )

    composite: Optional[Image.Image] = None
    mode = TryOnMode.prototype
    note = ""

    # Step 3: Determine garment type (used by both CatVTON and prototype)
    cloth_type = _determine_cloth_type(
        garment_category=garment_category,
        garment_name=garment_name,
        garment_id=garment_id,
        explicit_cloth_type=explicit_cloth_type,
    )
    logger.warning("🎯 Try-On cloth_type=%s (from category=%s, name=%s, explicit=%s)", cloth_type, garment_category, garment_name, explicit_cloth_type)

    # Step 4: Try Real CatVTON Neural Diffusion if configured
    if settings.tryon_mode == "catvton" and settings.catvton_endpoint:
        try:
            logger.warning("🚀 CatVTON: Connecting to Cloud GPU at %s (cloth_type=%s)", settings.catvton_endpoint, cloth_type)
            cloud_result = await _call_catvton_cloud(
                endpoint=settings.catvton_endpoint,
                person_img=person_img,
                garment_img=garment_img,
                cloth_type=cloth_type,
            )
            if cloud_result:
                # Resize result to match original photo dimensions
                composite = cloud_result.resize((pw, ph), Image.Resampling.LANCZOS)
                mode = TryOnMode.catvton
                note = (
                    f"CatVTON Neural Diffusion virtual try-on complete. "
                    f"Class: {cloth_type.upper()}. Body posture, hands, and background 100% preserved."
                )
                logger.warning("✅ CatVTON: Success! cloth_type=%s", cloth_type)
        except Exception as exc:
            err_msg = repr(exc)
            logger.warning("❌ CatVTON Cloud GPU failed (%s). Reverting to Prototype mode.", err_msg)
            note = (
                f"Cloud GPU notice: {err_msg[:120]}. "
                "Fell back to local anatomical prototype preview. Verify your GPU notebook is running."
            )

    # Step 5: Prototype Mode Fallback / Default
    if composite is None:
        mode = TryOnMode.prototype
        if not note:
            note = (
                f"Fitted garment from {source.upper()} using anatomical torso mapping. "
                "Running in prototype CPU mode. Real CatVTON diffusion activates with Google Colab GPU."
            )

        # --- Scale garment to cover correct body region based on garment type ---
        if cloth_type == "overall":
            # Full-body (lehenga, gown, dress, saree): cover from neck to ankle
            # Garment fills ~80% of width and ~72% of height, anchored at neck (~22% from top)
            target_width = int(pw * 0.82)
            paste_y = int(ph * 0.22)
            available_h = int(ph * 0.76)   # from neck to ankle
        elif cloth_type == "lower":
            # Skirt / trousers: cover waist to ankle
            target_width = int(pw * 0.75)
            paste_y = int(ph * 0.45)
            available_h = int(ph * 0.50)
        else:
            # Upper body (top / kurti / shirt): cover shoulders to waist
            target_width = int(pw * 0.65)
            paste_y = int(ph * 0.25)
            available_h = int(ph * 0.42)

        aspect = garment_img.height / garment_img.width
        target_height = int(target_width * aspect)

        # If the natural height fits within available space, use it as-is (no cropping)
        # Only scale DOWN if the garment is taller than available space
        if target_height > available_h:
            # Try width-first fit
            target_height = available_h
            target_width = int(target_height / aspect)
        # Never scale UP beyond the image width
        target_width = min(target_width, pw)

        resized_garment = garment_img.resize((target_width, target_height), Image.Resampling.LANCZOS)

        # Center horizontally
        paste_x = (pw - target_width) // 2

        composite = person_img.copy()
        composite.alpha_composite(resized_garment, (paste_x, paste_y))

    # Step 5: Verification Banner (AI Integrity Rule)
    draw = ImageDraw.Draw(composite)
    banner_h = 36
    draw.rectangle([0, ph - banner_h, pw, ph], fill=(13, 8, 24, 215))

    mode_label = (
        "StyleVision AI · CatVTON Neural Diffusion (Cloud GPU)"
        if mode == TryOnMode.catvton
        else "StyleVision AI · Prototype Overlay Mode (CPU)"
    )
    draw.text((16, ph - 26), mode_label, fill=(180, 160, 230, 255))

    # Step 6: Save composite image
    result_filename = f"{tryon_id}.png"
    result_path = os.path.join(TRYON_OUTPUT_DIR, result_filename)
    composite.save(result_path, format="PNG")

    result_url = f"/uploads/tryon/{result_filename}"
    now = datetime.now(timezone.utc)

    # Persist record in MongoDB outfits collection
    db = get_database()
    await db["outfits"].update_one(
        {"outfit_id": garment_id},
        {"$set": {"try_on_result": result_url}},
    )

    return {
        "tryon_id": tryon_id,
        "status": TryOnStatus.completed,
        "mode": mode,
        "source": source,
        "original_image_url": person_url,
        "garment_image_url": garment_url,
        "result_image_url": result_url,
        "processing_note": note,
        "created_at": now,
    }
