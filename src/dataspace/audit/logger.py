"""Tamper-evident audit logger with hash-chain integrity."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..core.crypto import sha256_hex
from ..core.enums import AuditEventType
from ..db.database import get_session
from ..db.repositories import audit_repo
from .models import AuditEntry


class AuditLogger:
    """
    Thread-safe audit logger that maintains a cryptographic hash chain.
    Each entry includes the hash of the previous entry, making tampering detectable.
    """

    _lock = asyncio.Lock()
    _sequence: int = 0
    _last_hash: str = ""
    _initialized: bool = False

    async def _init(self) -> None:
        if not self._initialized:
            async with get_session() as session:
                seq, last_hash = await audit_repo.get_latest_hash(session)
                self._sequence = seq
                self._last_hash = last_hash
                self._initialized = True

    async def log(
        self,
        event_type: AuditEventType,
        actor_id: str = "",
        subject_id: str = "",
        payload: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        await self._init()

        async with self._lock:
            self._sequence += 1
            seq = self._sequence
            prev_hash = self._last_hash

            entry = AuditEntry(
                sequence=seq,
                event_type=event_type,
                actor_id=actor_id,
                subject_id=subject_id,
                payload=payload or {},
                prev_hash=prev_hash,
            )

            # Compute hash over canonical representation
            # Use a consistent timestamp format (naive UTC microseconds)
            ts_str = entry.timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f")
            canonical = json.dumps(
                {
                    "sequence": entry.sequence,
                    "event_type": entry.event_type.value,
                    "actor_id": entry.actor_id,
                    "subject_id": entry.subject_id,
                    "payload": entry.payload,
                    "timestamp": ts_str,
                    "prev_hash": entry.prev_hash,
                },
                sort_keys=True,
                default=str,
            ).encode()
            entry_hash = sha256_hex(canonical)
            entry = entry.model_copy(update={"entry_hash": entry_hash})
            self._last_hash = entry_hash

            # Persist
            async with get_session() as session:
                await audit_repo.insert(session, entry.model_dump(mode="json"))

            return entry


# Singleton
audit_logger = AuditLogger()
