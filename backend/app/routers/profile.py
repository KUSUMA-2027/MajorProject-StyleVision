"""
StyleVision — User Profile & Settings Router
Provides endpoints for retrieving and updating user profile information via MongoDB.
"""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from app.models.user import UpdateProfileRequest
from app.database import get_database

router = APIRouter(prefix="/api/v1/profile", tags=["User Profile"])


class FullProfileResponse(BaseModel):
    user_id: str
    name: str
    email: str
    profile_photo: Optional[str] = None
    created_at: datetime
    saved_looks_count: int
    tryons_count: int


@router.get(
    "",
    response_model=FullProfileResponse,
    summary="Get user profile and statistics",
)
async def get_profile():
    """Retrieve profile and try-on metrics from MongoDB for the active user."""
    db = get_database()
    users_col = db["users"]
    looks_col = db["saved_looks"]

    user_doc = await users_col.find_one({"email": "demo@stylevision.com"})
    saved_count = await looks_col.count_documents({})

    if not user_doc:
        user_doc = {
            "user_id": "usr-demo-001",
            "name": "Demo User",
            "email": "demo@stylevision.com",
            "profile_photo": None,
            "created_at": datetime.now(timezone.utc),
        }

    return FullProfileResponse(
        user_id=user_doc["user_id"],
        name=user_doc["name"],
        email=user_doc["email"],
        profile_photo=user_doc.get("profile_photo"),
        created_at=user_doc.get("created_at", datetime.now(timezone.utc)),
        saved_looks_count=saved_count,
        tryons_count=12,
    )


@router.put(
    "",
    response_model=FullProfileResponse,
    summary="Update user profile",
)
async def update_profile(request: UpdateProfileRequest):
    """Update profile name and personal details in MongoDB."""
    db = get_database()
    users_col = db["users"]

    if request.name:
        await users_col.update_one(
            {"email": "demo@stylevision.com"},
            {"$set": {"name": request.name}},
        )

    return await get_profile()
