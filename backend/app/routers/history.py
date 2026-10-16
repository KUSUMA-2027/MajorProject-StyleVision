"""
StyleVision — Saved Looks / History Router
Saves, retrieves, and deletes virtual try-on styling results for users via MongoDB.
"""
from datetime import datetime, timezone
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.models.history import (
    SaveLookRequest,
    SavedLookResponse,
    HistoryListResponse,
    DeleteResponse,
)
from app.models.catalogue import TryOnCategory
from app.database import get_database

router = APIRouter(prefix="/api/v1/history", tags=["Saved Looks & History"])


@router.get(
    "",
    response_model=HistoryListResponse,
    summary="List saved styling looks",
)
async def list_saved_looks(
    category: Optional[TryOnCategory] = Query(None, description="Filter by category"),
):
    """Retrieve all saved looks from MongoDB with optional category filtering."""
    db = get_database()
    col = db["saved_looks"]

    query = {}
    if category:
        query["category"] = category.value

    cursor = col.find(query).sort("created_at", -1)
    results = []
    async for doc in cursor:
        results.append(
            SavedLookResponse(
                look_id=doc["look_id"],
                user_id=doc.get("user_id", "usr-demo"),
                title=doc.get("title", "Untitled Look"),
                category=TryOnCategory(doc["category"]),
                original_image_url=doc.get("original_image_url", "/uploads/person_sample.jpg"),
                result_image_url=doc.get("result_image_url", ""),
                style_item_name=doc.get("style_item_name", "Custom Style"),
                created_at=doc.get("created_at", datetime.now(timezone.utc)),
            )
        )

    # If database is fresh and empty, provide default seed looks
    if not results and not category:
        default_seed = [
            {
                "look_id": "look-1",
                "user_id": "usr-demo-001",
                "title": "Formal Navy Blazer Look",
                "category": "outfit",
                "original_image_url": "/uploads/person_sample.jpg",
                "result_image_url": "/uploads/tryon/blazer_result.jpg",
                "style_item_name": "Slim-Fit Velvet Blazer",
                "created_at": datetime.now(timezone.utc),
            },
            {
                "look_id": "look-2",
                "user_id": "usr-demo-001",
                "title": "Aviator Sunglasses Look",
                "category": "accessories",
                "original_image_url": "/uploads/person_sample.jpg",
                "result_image_url": "/uploads/tryon/aviator_result.jpg",
                "style_item_name": "Aviator Dark Tint Sunglasses",
                "created_at": datetime.now(timezone.utc),
            },
            {
                "look_id": "look-3",
                "user_id": "usr-demo-001",
                "title": "Ruby Velvet Lipstick",
                "category": "makeup",
                "original_image_url": "/uploads/person_sample.jpg",
                "result_image_url": "/uploads/tryon/makeup_result.jpg",
                "style_item_name": "Ruby Velvet Lipstick",
                "created_at": datetime.now(timezone.utc),
            },
        ]
        await col.insert_many(default_seed)
        for s in default_seed:
            results.append(
                SavedLookResponse(
                    look_id=s["look_id"],
                    user_id=s["user_id"],
                    title=s["title"],
                    category=TryOnCategory(s["category"]),
                    original_image_url=s["original_image_url"],
                    result_image_url=s["result_image_url"],
                    style_item_name=s["style_item_name"],
                    created_at=s["created_at"],
                )
            )

    return HistoryListResponse(
        looks=results,
        total=len(results),
    )


@router.post(
    "/save",
    response_model=SavedLookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a try-on result to history",
)
async def save_look(request: SaveLookRequest):
    """Save a generated virtual styling try-on to the MongoDB lookbook."""
    from app.routers.tryon import TRYON_JOBS_DB
    
    db = get_database()
    col = db["saved_looks"]

    look_id = f"look-{uuid.uuid4().hex[:10]}"
    title = request.title or "My Virtual Style"
    now = datetime.now(timezone.utc)

    job = TRYON_JOBS_DB.get(request.tryon_id, {})
    cat_val = job.get("category")
    if not cat_val:
        if "acc" in request.tryon_id:
            cat_val = "accessories"
        elif "mu" in request.tryon_id:
            cat_val = "makeup"
        elif "hair" in request.tryon_id:
            cat_val = "hairstyle"
        else:
            cat_val = "outfit"

    orig_url = job.get("original_image_url") or "/uploads/person_sample.jpg"
    res_url = job.get("result_image_url") or f"/uploads/tryon/{request.tryon_id}.png"
    style_name = job.get("subcategory") or job.get("garment_name") or title

    record = {
        "look_id": look_id,
        "user_id": "usr-demo-001",
        "title": title,
        "category": cat_val,
        "original_image_url": orig_url,
        "result_image_url": res_url,
        "style_item_name": str(style_name).title(),
        "created_at": now,
    }
    await col.insert_one(record)

    return SavedLookResponse(
        look_id=look_id,
        user_id=record["user_id"],
        title=record["title"],
        category=TryOnCategory(record["category"]),
        original_image_url=record["original_image_url"],
        result_image_url=record["result_image_url"],
        style_item_name=record["style_item_name"],
        created_at=now,
    )


@router.delete(
    "/{look_id}",
    response_model=DeleteResponse,
    summary="Delete a saved look",
)
async def delete_look(look_id: str):
    """Remove a styling result document from MongoDB."""
    db = get_database()
    col = db["saved_looks"]

    result = await col.delete_one({"look_id": look_id})
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Saved look '{look_id}' not found.",
        )

    return DeleteResponse(
        message="Look successfully removed from history.",
        deleted_id=look_id,
    )
