"""Domain-specific exceptions."""


class DataSpaceError(Exception):
    """Base exception for all DataSpace errors."""


class PartyNotFoundError(DataSpaceError):
    pass


class AssetNotFoundError(DataSpaceError):
    pass


class ContractNotFoundError(DataSpaceError):
    pass


class ContractStatusError(DataSpaceError):
    """Raised when a contract operation is invalid for the current status."""


class PolicyViolationError(DataSpaceError):
    """Raised when a data transfer violates a contract policy."""
    def __init__(self, reason: str, details: dict | None = None):
        super().__init__(reason)
        self.reason = reason
        self.details = details or {}


class SignatureError(DataSpaceError):
    """Raised when digital signature verification fails."""


class NegotiationError(DataSpaceError):
    """Raised when negotiation encounters an unrecoverable error."""


class NegotiationTimeoutError(NegotiationError):
    pass


class AdapterError(DataSpaceError):
    """Raised by data adapters."""


class AuditIntegrityError(DataSpaceError):
    """Raised when audit chain integrity check fails."""
