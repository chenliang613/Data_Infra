"""SQLAlchemy ORM table definitions."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class PartyRow(Base):
    __tablename__ = "parties"

    party_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    role: Mapped[str] = mapped_column(String, nullable=False)
    public_key_pem: Mapped[str] = mapped_column(Text, default="")
    endpoint: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")


class DataAssetRow(Base):
    __tablename__ = "data_assets"

    asset_id: Mapped[str] = mapped_column(String, primary_key=True)
    provider_id: Mapped[str] = mapped_column(String, ForeignKey("parties.party_id"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    asset_type: Mapped[str] = mapped_column(String, nullable=False)
    endpoint: Mapped[str] = mapped_column(String, default="")
    schema_json: Mapped[str] = mapped_column(Text, default="{}")
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    default_policy_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class ContractRow(Base):
    __tablename__ = "contracts"

    contract_id: Mapped[str] = mapped_column(String, primary_key=True)
    version: Mapped[str] = mapped_column(String, default="1.0")
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    valid_from: Mapped[datetime] = mapped_column(DateTime)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    provider_json: Mapped[str] = mapped_column(Text)
    consumer_json: Mapped[str] = mapped_column(Text)
    data_asset_json: Mapped[str] = mapped_column(Text)
    usage_policy_json: Mapped[str] = mapped_column(Text)
    negotiation_id: Mapped[str] = mapped_column(String, default="")
    signatures_json: Mapped[str] = mapped_column(Text, default="{}")
    revocation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class NegotiationRow(Base):
    __tablename__ = "negotiations"

    negotiation_id: Mapped[str] = mapped_column(String, primary_key=True)
    provider_id: Mapped[str] = mapped_column(String)
    requester_id: Mapped[str] = mapped_column(String)
    asset_id: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False)
    messages_json: Mapped[str] = mapped_column(Text, default="[]")
    agreed_policy_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contract_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    concluded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    turns: Mapped[int] = mapped_column(Integer, default=0)


class TransferRow(Base):
    __tablename__ = "transfers"

    transfer_id: Mapped[str] = mapped_column(String, primary_key=True)
    contract_id: Mapped[str] = mapped_column(String, ForeignKey("contracts.contract_id"))
    requester_id: Mapped[str] = mapped_column(String)
    operation: Mapped[str] = mapped_column(String, default="read")
    requested_records: Mapped[int] = mapped_column(Integer, default=100)
    records_returned: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, nullable=False)
    blocked_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class AuditEntryRow(Base):
    __tablename__ = "audit_entries"

    entry_id: Mapped[str] = mapped_column(String, primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    actor_id: Mapped[str] = mapped_column(String, default="")
    subject_id: Mapped[str] = mapped_column(String, default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    prev_hash: Mapped[str] = mapped_column(String, default="")
    entry_hash: Mapped[str] = mapped_column(String, nullable=False)


# Sentinel for import-triggered table registration
_all_tables = [PartyRow, DataAssetRow, ContractRow, NegotiationRow, TransferRow, AuditEntryRow]
