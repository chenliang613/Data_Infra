"""Domain enumerations for the DataSpace system."""
from enum import Enum


class PartyRole(str, Enum):
    PROVIDER = "provider"    # Party A: data owner
    REQUESTER = "requester"  # Party B: data consumer


class AssetType(str, Enum):
    JSON_API = "json_api"
    CSV_FILE = "csv_file"
    PARQUET_FILE = "parquet_file"
    DB_TABLE = "db_table"
    STREAM = "stream"


class ContractStatus(str, Enum):
    DRAFT = "draft"
    PENDING_SIGNATURES = "pending_signatures"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPENDED = "suspended"


class NegotiationStatus(str, Enum):
    INITIATED = "initiated"
    IN_PROGRESS = "in_progress"
    AGREED = "agreed"
    REJECTED = "rejected"
    FAILED = "failed"


class NegotiationRole(str, Enum):
    PROVIDER = "provider"
    REQUESTER = "requester"


class TransferStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class AuditEventType(str, Enum):
    PARTY_REGISTERED = "party_registered"
    ASSET_REGISTERED = "asset_registered"
    NEGOTIATION_STARTED = "negotiation_started"
    NEGOTIATION_MESSAGE = "negotiation_message"
    NEGOTIATION_AGREED = "negotiation_agreed"
    NEGOTIATION_REJECTED = "negotiation_rejected"
    CONTRACT_GENERATED = "contract_generated"
    CONTRACT_SIGNED = "contract_signed"
    CONTRACT_ACTIVATED = "contract_activated"
    CONTRACT_REVOKED = "contract_revoked"
    TRANSFER_REQUESTED = "transfer_requested"
    TRANSFER_POLICY_PASSED = "transfer_policy_passed"
    TRANSFER_POLICY_BLOCKED = "transfer_policy_blocked"
    TRANSFER_COMPLETED = "transfer_completed"
    TRANSFER_FAILED = "transfer_failed"
    AUDIT_CHAIN_VERIFIED = "audit_chain_verified"
