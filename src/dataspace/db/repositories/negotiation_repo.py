"""Negotiation repository."""
from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.models import NegotiationSession, NegotiationMessage, UsagePolicy
from ...core.enums import NegotiationStatus
from ..tables import NegotiationRow


def _row_to_model(row: NegotiationRow) -> NegotiationSession:
    messages_data = json.loads(row.messages_json or "[]")
    messages = [NegotiationMessage(**m) for m in messages_data]
    agreed_policy = None
    if row.agreed_policy_json:
        agreed_policy = UsagePolicy(**json.loads(row.agreed_policy_json))
    return NegotiationSession(
        negotiation_id=row.negotiation_id,
        provider_id=row.provider_id,
        requester_id=row.requester_id,
        asset_id=row.asset_id,
        status=NegotiationStatus(row.status),
        messages=messages,
        agreed_policy=agreed_policy,
        contract_id=row.contract_id,
        started_at=row.started_at,
        concluded_at=row.concluded_at,
        turns=row.turns,
    )


def _model_to_row(s: NegotiationSession) -> NegotiationRow:
    return NegotiationRow(
        negotiation_id=s.negotiation_id,
        provider_id=s.provider_id,
        requester_id=s.requester_id,
        asset_id=s.asset_id,
        status=s.status.value,
        messages_json=json.dumps([m.model_dump(mode="json") for m in s.messages]),
        agreed_policy_json=json.dumps(s.agreed_policy.model_dump()) if s.agreed_policy else None,
        contract_id=s.contract_id,
        started_at=s.started_at,
        concluded_at=s.concluded_at,
        turns=s.turns,
    )


async def create(session: AsyncSession, neg: NegotiationSession) -> NegotiationSession:
    row = _model_to_row(neg)
    session.add(row)
    await session.commit()
    return neg


async def get(session: AsyncSession, negotiation_id: str) -> Optional[NegotiationSession]:
    row = await session.get(NegotiationRow, negotiation_id)
    return _row_to_model(row) if row else None


async def update(session: AsyncSession, neg: NegotiationSession) -> NegotiationSession:
    row = await session.get(NegotiationRow, neg.negotiation_id)
    if row:
        row.status = neg.status.value
        row.messages_json = json.dumps([m.model_dump(mode="json") for m in neg.messages])
        row.agreed_policy_json = json.dumps(neg.agreed_policy.model_dump()) if neg.agreed_policy else None
        row.contract_id = neg.contract_id
        row.concluded_at = neg.concluded_at
        row.turns = neg.turns
        await session.commit()
    return neg
