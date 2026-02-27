"""Audit log repository."""
from __future__ import annotations

import json
from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..tables import AuditEntryRow


async def insert(session: AsyncSession, entry_data: dict) -> None:
    from datetime import datetime
    ts = entry_data["timestamp"]
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))

    row = AuditEntryRow(
        entry_id=entry_data["entry_id"],
        sequence=entry_data["sequence"],
        event_type=entry_data["event_type"],
        actor_id=entry_data.get("actor_id", ""),
        subject_id=entry_data.get("subject_id", ""),
        payload_json=json.dumps(entry_data.get("payload", {}), default=str),
        timestamp=ts,
        prev_hash=entry_data.get("prev_hash", ""),
        entry_hash=entry_data["entry_hash"],
    )
    session.add(row)
    await session.commit()


async def get_latest_hash(session: AsyncSession) -> tuple[int, str]:
    """Return (max_sequence, last_entry_hash) or (0, '')."""
    result = await session.execute(
        select(AuditEntryRow).order_by(AuditEntryRow.sequence.desc()).limit(1)
    )
    row = result.scalar_one_or_none()
    if row:
        return row.sequence, row.entry_hash
    return 0, ""


async def list_entries(
    session: AsyncSession,
    offset: int = 0,
    limit: int = 100,
    subject_id: Optional[str] = None,
) -> List[dict]:
    q = select(AuditEntryRow).order_by(AuditEntryRow.sequence)
    if subject_id:
        q = q.where(AuditEntryRow.subject_id == subject_id)
    q = q.offset(offset).limit(limit)
    result = await session.execute(q)
    rows = result.scalars().all()
    return [
        {
            "entry_id": r.entry_id,
            "sequence": r.sequence,
            "event_type": r.event_type,
            "actor_id": r.actor_id,
            "subject_id": r.subject_id,
            "payload": json.loads(r.payload_json),
            "timestamp": r.timestamp.isoformat(),
            "prev_hash": r.prev_hash,
            "entry_hash": r.entry_hash,
        }
        for r in rows
    ]


async def list_all_ordered(session: AsyncSession) -> List[AuditEntryRow]:
    result = await session.execute(select(AuditEntryRow).order_by(AuditEntryRow.sequence))
    return result.scalars().all()
