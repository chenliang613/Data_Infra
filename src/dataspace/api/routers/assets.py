"""Data asset endpoints."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...core.enums import AssetType
from ...core.models import DataAsset, UsagePolicy
from ...db.database import get_session
from ...db.repositories import asset_repo

router = APIRouter(prefix="/assets", tags=["Assets"])


class AssetCreate(BaseModel):
    provider_id: str
    name: str
    description: str = ""
    asset_type: AssetType
    endpoint: str
    sample_size: int = 0
    tags: List[str] = []
    default_policy: Optional[UsagePolicy] = None


@router.post("", response_model=DataAsset, status_code=201)
async def create_asset(data: AssetCreate) -> DataAsset:
    asset = DataAsset(**data.model_dump())
    async with get_session() as session:
        return await asset_repo.create(session, asset)


@router.get("", response_model=List[DataAsset])
async def list_assets(provider_id: Optional[str] = None) -> List[DataAsset]:
    async with get_session() as session:
        if provider_id:
            return await asset_repo.list_by_provider(session, provider_id)
        return await asset_repo.list_all(session)


@router.get("/{asset_id}", response_model=DataAsset)
async def get_asset(asset_id: str) -> DataAsset:
    async with get_session() as session:
        asset = await asset_repo.get(session, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset
