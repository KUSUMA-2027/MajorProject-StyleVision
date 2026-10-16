"""
StyleVision — Photo Upload Router
Handles secure multipart image uploads with validation, image suitability checks,
safe storage, and MongoDB tracking.
"""
from datetime import datetime, timezone
import io
from typing import Optional
from PIL import Image
from fastapi import APIRouter, UploadFile, File, HTTPException, status

from app.models.history import UploadedImageResponse
from app.utils.file_utils import (
    validate_and_read_upload,
    generate_safe_filename,
    save_upload_to_disk,
)
from app.config import get_settings
from app.database import get_database

router = APIRouter(prefix="/api/v1/upload", tags=["Photo Upload"])
settings = get_settings()

MIN_DIMENSION_PX = 256
RECOMMENDED_DIMENSION_PX = 512


@router.post(
    "/photo",
    response_model=UploadedImageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and validate a person photograph",
)
async def upload_photo(file: UploadFile = File(...)):
    """
    Upload a user portrait photograph for virtual try-on:
    - Validates file type (JPEG, PNG, WebP)
    - Validates file size (1 KB to 10 MB)
    - Verifies real image data and decodes via Pillow
    - Validates portrait suitability (min 256x256 resolution & aspect ratio)
    - Saves with a safe randomized UUID filename (never exposing user's client filename or disk path)
    - Records upload metadata in MongoDB
    - Returns URL, dimensions, and suitability analysis
    """
    raw_bytes, extension = await validate_and_read_upload(file)

    # Read and inspect image using Pillow
    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            width, height = img.size
            format_name = img.format or extension.upper()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image decoding failed: {exc}",
        ) from exc

    # Resolution suitability validation
    if width < MIN_DIMENSION_PX or height < MIN_DIMENSION_PX:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Image resolution too low ({width}x{height} px). "
                f"A minimum of {MIN_DIMENSION_PX}x{MIN_DIMENSION_PX} pixels is required "
                f"for accurate landmark alignment and clothing fitting."
            ),
        )

    # Aspect ratio check
    ratio = width / height
    if ratio < 0.35 or ratio > 2.8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported image proportions (aspect ratio {ratio:.2f}). "
                "Please upload a standard portrait or upper-body photograph."
            ),
        )

    # Quality classification
    if width >= RECOMMENDED_DIMENSION_PX and height >= RECOMMENDED_DIMENSION_PX:
        quality_score = "high"
        suitability_note = f"High-resolution {format_name} portrait ({width}x{height} px) suitable for all AI studios."
    else:
        quality_score = "medium"
        suitability_note = f"Standard resolution ({width}x{height} px) detected. Suitable for prototype styling."

    # Generate safe random filename
    safe_filename = generate_safe_filename(
        user_id="user",
        prefix="person",
        extension=extension,
    )

    # Save to uploads directory
    save_upload_to_disk(
        raw_bytes=raw_bytes,
        directory=settings.upload_dir,
        filename=safe_filename,
    )

    image_id = f"img-{safe_filename.split('.')[0]}"
    image_url = f"/uploads/{safe_filename}"
    now = datetime.now(timezone.utc)

    # Persist record in MongoDB
    db = get_database()
    upload_doc = {
        "image_id": image_id,
        "filename": safe_filename,
        "size_bytes": len(raw_bytes),
        "width": width,
        "height": height,
        "url": image_url,
        "quality_score": quality_score,
        "suitability_note": suitability_note,
        "uploaded_at": now,
    }
    await db["uploads"].insert_one(upload_doc)

    return UploadedImageResponse(
        image_id=image_id,
        filename=safe_filename,
        size_bytes=len(raw_bytes),
        width=width,
        height=height,
        url=image_url,
        uploaded_at=now,
        quality_score=quality_score,
        suitability_note=suitability_note,
    )


@router.get(
    "/latest",
    response_model=Optional[UploadedImageResponse],
    summary="Get user's most recent uploaded portrait",
)
async def get_latest_upload():
    """Retrieve metadata of the most recent user portrait uploaded to the system."""
    db = get_database()
    col = db["uploads"]
    doc = await col.find_one(sort=[("uploaded_at", -1)])
    if not doc:
        return None
    return UploadedImageResponse(
        image_id=doc["image_id"],
        filename=doc["filename"],
        size_bytes=doc.get("size_bytes", 0),
        width=doc.get("width"),
        height=doc.get("height"),
        url=doc["url"],
        uploaded_at=doc["uploaded_at"],
        quality_score=doc.get("quality_score", "good"),
        suitability_note=doc.get("suitability_note"),
    )
