"""Party repository: CRUD operations."""
from __future__ import annotations

import json
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.models import Party
from ...core.enums import PartyRole
from ..tables import PartyRow


def _row_to_model(row: PartyRow) -> Party:
    return Party(
        party_id=row.party_id,
        name=row.name,
        description=row.description,
        role=PartyRole(row.role),
        public_key_pem=row.public_key_pem,
        endpoint=row.endpoint,
        created_at=row.created_at,
        metadata=json.loads(row.metadata_json or "{}"),
    )


def _model_to_row(party: Party) -> PartyRow:
    return PartyRow(
        party_id=party.party_id,
        name=party.name,
        description=party.description,
        role=party.role.value,
        public_key_pem=party.public_key_pem,
        endpoint=party.endpoint,
        created_at=party.created_at,
        metadata_json=json.dumps(party.metadata),
    )


async def create(session: AsyncSession, party: Party) -> Party:
    row = _model_to_row(party)
    session.add(row)
    await session.commit()
    return party


async def get(session: AsyncSession, party_id: str) -> Optional[Party]:
    row = await session.get(PartyRow, party_id)
    return _row_to_model(row) if row else None


async def list_all(session: AsyncSession) -> List[Party]:
    result = await session.execute(select(PartyRow))
    return [_row_to_model(r) for r in result.scalars()]


async def update_public_key(session: AsyncSession, party_id: str, public_key_pem: str) -> None:
    row = await session.get(PartyRow, party_id)
    if row:
        row.public_key_pem = public_key_pem
        await session.commit()
