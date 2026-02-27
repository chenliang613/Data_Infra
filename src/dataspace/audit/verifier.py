"""Audit chain integrity verifier."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List

from ..core.crypto import sha256_hex
from ..db.database import get_session
from ..db.repositories import audit_repo


@dataclass
class VerificationResult:
    valid: bool
    total_entries: int
    broken_at_sequence: int | None = None
    error: str = ""


async def verify_chain() -> VerificationResult:
    """
    Walk the audit chain from beginning, re-computing each entry's hash
    and verifying prev_hash links.
    """
    async with get_session() as session:
        rows = await audit_repo.list_all_ordered(session)

    if not rows:
        return VerificationResult(valid=True, total_entries=0)

    prev_hash = ""
    for row in rows:
        # Re-compute expected hash (must match logger's canonical format)
        import json as _json
        payload = _json.loads(row.payload_json)
        # Use consistent naive UTC format
        ts_str = row.timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f")
        canonical = json.dumps(
            {
                "sequence": row.sequence,
                "event_type": row.event_type,
                "actor_id": row.actor_id,
                "subject_id": row.subject_id,
                "payload": payload,
                "timestamp": ts_str,
                "prev_hash": row.prev_hash,
            },
            sort_keys=True,
            default=str,
        ).encode()
        expected_hash = sha256_hex(canonical)

        if row.entry_hash != expected_hash:
            return VerificationResult(
                valid=False,
                total_entries=len(rows),
                broken_at_sequence=row.sequence,
                error=f"Hash mismatch at sequence {row.sequence}: stored={row.entry_hash[:12]}... expected={expected_hash[:12]}...",
            )

        if row.prev_hash != prev_hash:
            return VerificationResult(
                valid=False,
                total_entries=len(rows),
                broken_at_sequence=row.sequence,
                error=f"Chain broken at sequence {row.sequence}: prev_hash mismatch",
            )

        prev_hash = row.entry_hash

    return VerificationResult(valid=True, total_entries=len(rows))
