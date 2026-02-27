"""DataAsset repository."""
from __future__ import annotations

import json
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.models import DataAsset, UsagePolicy
from ...core.enums import AssetType
from ..tables import DataAssetRow


def _row_to_model(row: DataAssetRow) -> DataAsset:
    policy = None
    if row.default_policy_json:
        policy = UsagePolicy(**json.loads(row.default_policy_json))
    return DataAsset(
        asset_id=row.asset_id,
        provider_id=row.provider_id,
        name=row.name,
        description=row.description,
        asset_type=AssetType(row.asset_type),
        endpoint=row.endpoint,
        schema_info=json.loads(row.schema_json or "{}"),
        sample_size=row.sample_size,
        tags=json.loads(row.tags_json or "[]"),
        created_at=row.created_at,
        default_policy=policy,
    )


def _model_to_row(asset: DataAsset) -> DataAssetRow:
    return DataAssetRow(
        asset_id=asset.asset_id,
        provider_id=asset.provider_id,
        name=asset.name,
        description=asset.description,
        asset_type=asset.asset_type.value,
        endpoint=asset.endpoint,
        schema_json=json.dumps(asset.schema_info),
        sample_size=asset.sample_size,
        tags_json=json.dumps(asset.tags),
        default_policy_json=json.dumps(asset.default_policy.model_dump()) if asset.default_policy else None,
        created_at=asset.created_at,
    )


async def create(session: AsyncSession, asset: DataAsset) -> DataAsset:
    row = _model_to_row(asset)
    session.add(row)
    await session.commit()
    return asset


async def get(session: AsyncSession, asset_id: str) -> Optional[DataAsset]:
    row = await session.get(DataAssetRow, asset_id)
    return _row_to_model(row) if row else None


async def list_by_provider(session: AsyncSession, provider_id: str) -> List[DataAsset]:
    result = await session.execute(
        select(DataAssetRow).where(DataAssetRow.provider_id == provider_id)
    )
    return [_row_to_model(r) for r in result.scalars()]


async def list_all(session: AsyncSession) -> List[DataAsset]:
    result = await session.execute(select(DataAssetRow))
    return [_row_to_model(r) for r in result.scalars()]
