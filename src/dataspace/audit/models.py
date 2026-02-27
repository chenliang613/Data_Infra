"""Audit log models."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from pydantic import BaseModel, Field

from ..core.enums import AuditEventType


class AuditEntry(BaseModel):
    entry_id: str = Field(default_factory=lambda: str(uuid4()))
    sequence: int
    event_type: AuditEventType
    actor_id: str = ""      # Who triggered the event
    subject_id: str = ""    # The primary entity affected (contract_id, negotiation_id, etc.)
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    prev_hash: str = ""     # Hash of previous entry (chain link)
    entry_hash: str = ""    # SHA-256 of this entry's canonical bytes
