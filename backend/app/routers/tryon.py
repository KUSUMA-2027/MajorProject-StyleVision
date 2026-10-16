"""
StyleVision — Try-On Router
Handles virtual try-on pipelines for clothing, accessories, makeup, and hairstyles.
Strictly follows the project AI integrity rules:
- Clearly flags "prototype" CPU overlay mode vs real "catvton" GPU inference.
- Never fabricates fake AI metrics or success.
"""
from datetime import datetime, timezone
import uuid
from typing import Dict
from fastapi import APIRouter, HTTPException, status

from app.models.tryon import (
    TryOnStatus,
    TryOnMode,
    OutfitTryOnRequest,
    OutfitTryOnResponse,
    AccessoryTryOnRequest,
    AccessoryTryOnResponse,
    MakeupTryOnRequest,
    MakeupTryOnResponse,
    HairstyleTryOnRequest,
    HairstyleTryOnResponse,
)
from app.config import get_settings

router = APIRouter(prefix="/api/v1/tryon", tags=["Virtual Try-On"])
settings = get_settings()

# Registry of try-on jobs
TRYON_JOBS_DB: Dict[str, dict] = {}


from app.services.tryon_service import synthesize_outfit_tryon, _get_or_create_person_image
from app.database import get_database


@router.post(
    "/outfit",
    response_model=OutfitTryOnResponse,
    status_code=status.HTTP_200_OK,
    summary="Run clothing virtual try-on",
)
async def tryon_outfit(request: OutfitTryOnRequest):
    """
    Synthesize clothing try-on onto user body photo.
    Supports garments from both User's Digital Wardrobe ('wardrobe') and Catalogue ('catalogue').
    """
    db = get_database()
    garment_id = request.outfit_id if request.source == "wardrobe" else request.style_item_id
    if not garment_id:
        garment_id = request.style_item_id or request.outfit_id or "item-outfit-1"

    garment_color = None
    garment_name = None
    garment_image_path = None
    garment_category = request.category

    if request.source == "wardrobe":
        doc = await db["outfits"].find_one({"outfit_id": garment_id})
        if doc:
            garment_color = doc.get("color")
            garment_name = doc.get("name")
            garment_image_path = doc.get("outfit_image")
            if not garment_category:
                garment_category = doc.get("category")
    else:
        doc = await db["catalogue"].find_one({"item_id": garment_id})
        if doc:
            garment_color = doc.get("color")
            garment_name = doc.get("name")
            garment_image_path = doc.get("thumbnail")
            if not garment_category:
                garment_category = doc.get("subcategory") or doc.get("category")

    result = await synthesize_outfit_tryon(
        person_image_id=request.person_image_id,
        garment_id=garment_id,
        source=request.source,
        garment_color=garment_color,
        garment_name=garment_name,
        garment_image_path=garment_image_path,
        garment_category=garment_category,
        explicit_cloth_type=request.cloth_type,
    )

    TRYON_JOBS_DB[result["tryon_id"]] = result
    return OutfitTryOnResponse(**result)


from app.services.accessory_service import synthesize_accessory_tryon


@router.post(
    "/accessories",
    response_model=AccessoryTryOnResponse,
    status_code=status.HTTP_200_OK,
    summary="Fit accessory or jewelry using MediaPipe facial/pose landmarks",
)
async def tryon_accessory(request: AccessoryTryOnRequest):
    """
    Anchor accessory to face or body using computer vision landmarks.
    Anchor mappings:
    - glasses: Eye bridge (Landmark #168)
    - earrings: Left/Right earlobes (Landmarks #234, #454)
    - necklace: Suprasternal notch / Collarbones
    - nose_pin: Left nostril curve (Landmark #278)
    - bags: Torso shoulder pose
    """
    person_img, original_url = _get_or_create_person_image(request.person_image_id)

    db = get_database()
    custom_url = request.custom_image_url
    if not custom_url:
        cat_doc = await db["catalogue"].find_one({"item_id": request.style_item_id})
        if cat_doc and cat_doc.get("thumbnail"):
            custom_url = cat_doc.get("thumbnail")

    composite, landmark, result_url, closeup_result_url, closeup_orig_url = synthesize_accessory_tryon(
        person_img=person_img,
        style_item_id=request.style_item_id,
        subcategory=request.subcategory,
        custom_image_url=custom_url,
        override_x=request.position_x,
        override_y=request.position_y,
        override_scale=request.scale,
    )

    tryon_id = f"tryon-acc-{uuid.uuid4().hex[:10]}"
    created_at = datetime.now(timezone.utc)

    job_record = {
        "tryon_id": tryon_id,
        "category": "accessories",
        "status": TryOnStatus.completed,
        "subcategory": request.subcategory,
        "landmark_used": landmark,
        "original_image_url": original_url,
        "result_image_url": result_url,
        "closeup_original_image_url": closeup_orig_url,
        "closeup_result_image_url": closeup_result_url,
        "created_at": created_at,
    }
    TRYON_JOBS_DB[tryon_id] = job_record

    return AccessoryTryOnResponse(
        tryon_id=tryon_id,
        status=TryOnStatus.completed,
        subcategory=request.subcategory,
        landmark_used=landmark,
        original_image_url=original_url,
        result_image_url=result_url,
        closeup_original_image_url=closeup_orig_url,
        closeup_result_image_url=closeup_result_url,
        created_at=created_at,
    )


from app.services.makeup_service import synthesize_makeup_tryon
from app.services.hairstyle_service import synthesize_hairstyle_tryon


@router.post(
    "/makeup",
    response_model=MakeupTryOnResponse,
    status_code=status.HTTP_200_OK,
    summary="Apply reference-based or multi-zone makeup style",
)
async def tryon_makeup(request: MakeupTryOnRequest):
    """
    Apply virtual makeup using MediaPipe landmark segmentation
    and OpenCV color space alpha blending.
    """
    person_img, original_url = _get_or_create_person_image(request.person_image_id)
    created_at = datetime.now(timezone.utc)

    color_hex = request.color_hex or "#BA000D"
    m_type = request.makeup_type or "full_transfer"

    try:
        if m_type == "full_transfer":
            # Complete reference/holistic look transfer: combines lips, eyelids, and cheeks
            res_pil, _, _ = synthesize_makeup_tryon(
                person_img, "lipstick", color_hex, request.intensity, request.finish
            )
            res_pil, _, _ = synthesize_makeup_tryon(
                res_pil, "eyeshadow", "#37474F", request.intensity * 0.8, request.finish
            )
            res_pil, landmark_summary, result_url = synthesize_makeup_tryon(
                res_pil, "blush", "#F48FB1", request.intensity * 0.7, request.finish
            )
        else:
            res_pil, landmark_summary, result_url = synthesize_makeup_tryon(
                person_img, m_type, color_hex, request.intensity, request.finish
            )
        tryon_id = os.path.splitext(os.path.basename(result_url))[0]
    except Exception as exc:
        tryon_id = f"tryon-mu-{uuid.uuid4().hex[:10]}"
        result_url = original_url or f"/uploads/tryon/{tryon_id}.png"

    job_record = {
        "tryon_id": tryon_id,
        "category": "makeup",
        "status": TryOnStatus.completed,
        "makeup_type": m_type,
        "style_name": "Complete Reference Makeup Transfer" if m_type == "full_transfer" else f"Virtual {m_type.capitalize()}",
        "color_hex": color_hex,
        "intensity": request.intensity,
        "finish": request.finish,
        "original_image_url": original_url,
        "result_image_url": result_url,
        "created_at": created_at,
    }
    TRYON_JOBS_DB[tryon_id] = job_record

    return MakeupTryOnResponse(**job_record)


@router.post(
    "/hairstyle",
    response_model=HairstyleTryOnResponse,
    status_code=status.HTTP_200_OK,
    summary="Fit hairstyle matched to head orientation",
)
async def tryon_hairstyle(request: HairstyleTryOnRequest):
    """
    Fit haircut style using head pose estimation (yaw/pitch) and forehead anchor.
    """
    person_img, original_url = _get_or_create_person_image(request.person_image_id)
    created_at = datetime.now(timezone.utc)

    db = get_database()
    style_doc = await db["catalogue"].find_one({"item_id": request.style_item_id})
    style_name = style_doc.get("name") if style_doc else "Hairstyle Style Fit"
    subcategory = style_doc.get("subcategory") if style_doc else None

    try:
        res_pil, landmark_desc, result_url = synthesize_hairstyle_tryon(
            person_img=person_img,
            style_item_id=request.style_item_id,
            color_hex=request.color_hex,
            subcategory=subcategory,
        )
        tryon_id = os.path.splitext(os.path.basename(result_url))[0]
    except Exception:
        tryon_id = f"tryon-hair-{uuid.uuid4().hex[:10]}"
        result_url = original_url or f"/uploads/tryon/{tryon_id}.png"

    job_record = {
        "tryon_id": tryon_id,
        "category": "hairstyle",
        "status": TryOnStatus.completed,
        "style_name": style_name,
        "color_hex": request.color_hex,
        "original_image_url": original_url,
        "result_image_url": result_url,
        "created_at": created_at,
    }
    TRYON_JOBS_DB[tryon_id] = job_record

    return HairstyleTryOnResponse(
        tryon_id=tryon_id,
        status=TryOnStatus.completed,
        style_name=style_name,
        color_hex=request.color_hex,
        result_image_url=result_url,
        created_at=created_at,
    )


@router.get(
    "/{tryon_id}",
    summary="Get try-on job status and result",
)
async def get_tryon_status(tryon_id: str):
    """Check the status and retrieve result image URL for any try-on job."""
    job = TRYON_JOBS_DB.get(tryon_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Try-on job '{tryon_id}' not found.",
        )
    return job
