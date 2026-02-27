"""Core domain models (Pydantic v2)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from .enums import AssetType, ContractStatus, NegotiationStatus, PartyRole, TransferStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Party
# ---------------------------------------------------------------------------

class Party(BaseModel):
    party_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    role: PartyRole
    public_key_pem: str = ""          # RSA public key in PEM format
    endpoint: str = ""                # Base URL of this party's API
    created_at: datetime = Field(default_factory=_utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Data Asset
# ---------------------------------------------------------------------------

class DataAsset(BaseModel):
    asset_id: str = Field(default_factory=lambda: str(uuid4()))
    provider_id: str
    name: str
    description: str = ""
    asset_type: AssetType
    endpoint: str                      # URL or file path
    schema_info: Dict[str, Any] = Field(default_factory=dict)  # column info
    sample_size: int = 0
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)
    # Provider's default policy constraints for this asset
    default_policy: "UsagePolicy | None" = None


# ---------------------------------------------------------------------------
# Usage Policy (contract terms)
# ---------------------------------------------------------------------------

class UsagePolicy(BaseModel):
    max_requests_per_day: int = 1000
    max_records_per_request: int = 500
    allowed_operations: List[str] = Field(default_factory=lambda: ["read"])
    masked_columns: List[str] = Field(default_factory=list)
    duration_days: int = 30
    purpose: str = "analytics"
    no_third_party_transfer: bool = True
    allowed_requester_ids: List[str] = Field(default_factory=list)

    def is_compatible_with(self, other: "UsagePolicy") -> bool:
        """Check if `other` (requester proposal) fits within this policy."""
        return (
            other.max_requests_per_day <= self.max_requests_per_day
            and other.max_records_per_request <= self.max_records_per_request
            and other.duration_days <= self.duration_days
            and all(op in self.allowed_operations for op in other.allowed_operations)
        )


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------

class ContractPartyInfo(BaseModel):
    party_id: str
    name: str
    public_key_pem: str


class Contract(BaseModel):
    contract_id: str = Field(default_factory=lambda: str(uuid4()))
    version: str = "1.0"
    status: ContractStatus = ContractStatus.DRAFT
    created_at: datetime = Field(default_factory=_utcnow)
    valid_from: datetime = Field(default_factory=_utcnow)
    valid_until: Optional[datetime] = None
    provider: ContractPartyInfo
    consumer: ContractPartyInfo
    data_asset: DataAsset
    usage_policy: UsagePolicy
    negotiation_id: str = ""
    signatures: Dict[str, str] = Field(default_factory=dict)  # party_id -> base64 sig
    revocation_reason: Optional[str] = None

    def canonical_bytes(self) -> bytes:
        """Deterministic bytes for signing (excludes signatures field)."""
        d = self.model_dump(exclude={"signatures", "status", "revocation_reason"})
        return json.dumps(d, sort_keys=True, default=str).encode()

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Negotiation
# ---------------------------------------------------------------------------

class NegotiationMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    negotiation_id: str
    sender_role: str   # "provider" | "requester"
    content: str
    proposed_terms: Optional[UsagePolicy] = None
    timestamp: datetime = Field(default_factory=_utcnow)


class NegotiationSession(BaseModel):
    negotiation_id: str = Field(default_factory=lambda: str(uuid4()))
    provider_id: str
    requester_id: str
    asset_id: str
    status: NegotiationStatus = NegotiationStatus.INITIATED
    messages: List[NegotiationMessage] = Field(default_factory=list)
    agreed_policy: Optional[UsagePolicy] = None
    contract_id: Optional[str] = None
    started_at: datetime = Field(default_factory=_utcnow)
    concluded_at: Optional[datetime] = None
    turns: int = 0


# ---------------------------------------------------------------------------
# Transfer Record
# ---------------------------------------------------------------------------

class TransferRequest(BaseModel):
    transfer_id: str = Field(default_factory=lambda: str(uuid4()))
    contract_id: str
    requester_id: str
    operation: str = "read"
    requested_records: int = 100
    purpose: str = ""
    filters: Dict[str, Any] = Field(default_factory=dict)
    requested_at: datetime = Field(default_factory=_utcnow)


class TransferResult(BaseModel):
    transfer_id: str
    contract_id: str
    status: TransferStatus
    records_returned: int = 0
    data: Any = None
    blocked_reason: Optional[str] = None
    completed_at: datetime = Field(default_factory=_utcnow)
