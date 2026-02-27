"""Contract repository."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.models import Contract, ContractPartyInfo, DataAsset, UsagePolicy
from ...core.enums import ContractStatus, AssetType
from ..tables import ContractRow


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """Ensure datetime is timezone-aware (UTC). SQLite strips tzinfo on read."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _row_to_model(row: ContractRow) -> Contract:
    provider = ContractPartyInfo(**json.loads(row.provider_json))
    consumer = ContractPartyInfo(**json.loads(row.consumer_json))
    asset_data = json.loads(row.data_asset_json)
    asset = DataAsset(**asset_data)
    policy = UsagePolicy(**json.loads(row.usage_policy_json))
    return Contract(
        contract_id=row.contract_id,
        version=row.version,
        status=ContractStatus(row.status),
        created_at=_ensure_utc(row.created_at),
        valid_from=_ensure_utc(row.valid_from),
        valid_until=_ensure_utc(row.valid_until),
        provider=provider,
        consumer=consumer,
        data_asset=asset,
        usage_policy=policy,
        negotiation_id=row.negotiation_id,
        signatures=json.loads(row.signatures_json or "{}"),
        revocation_reason=row.revocation_reason,
    )


def _model_to_row(c: Contract) -> ContractRow:
    asset_dict = c.data_asset.model_dump()
    return ContractRow(
        contract_id=c.contract_id,
        version=c.version,
        status=c.status.value,
        created_at=c.created_at,
        valid_from=c.valid_from,
        valid_until=c.valid_until,
        provider_json=json.dumps(c.provider.model_dump()),
        consumer_json=json.dumps(c.consumer.model_dump()),
        data_asset_json=json.dumps(asset_dict, default=str),
        usage_policy_json=json.dumps(c.usage_policy.model_dump()),
        negotiation_id=c.negotiation_id,
        signatures_json=json.dumps(c.signatures),
        revocation_reason=c.revocation_reason,
    )


async def create(session: AsyncSession, contract: Contract) -> Contract:
    row = _model_to_row(contract)
    session.add(row)
    await session.commit()
    return contract


async def get(session: AsyncSession, contract_id: str) -> Optional[Contract]:
    row = await session.get(ContractRow, contract_id)
    return _row_to_model(row) if row else None


async def update(session: AsyncSession, contract: Contract) -> Contract:
    row = await session.get(ContractRow, contract.contract_id)
    if row:
        row.status = contract.status.value
        row.signatures_json = json.dumps(contract.signatures)
        row.revocation_reason = contract.revocation_reason
        await session.commit()
    return contract


async def list_by_party(session: AsyncSession, party_id: str) -> List[Contract]:
    result = await session.execute(select(ContractRow))
    contracts = []
    for row in result.scalars():
        p = json.loads(row.provider_json)
        c = json.loads(row.consumer_json)
        if p["party_id"] == party_id or c["party_id"] == party_id:
            contracts.append(_row_to_model(row))
    return contracts


async def list_active(session: AsyncSession) -> List[Contract]:
    result = await session.execute(
        select(ContractRow).where(ContractRow.status == ContractStatus.ACTIVE.value)
    )
    return [_row_to_model(r) for r in result.scalars()]
