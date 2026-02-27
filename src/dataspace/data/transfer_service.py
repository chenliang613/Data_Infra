"""Data transfer service: orchestrates contract-gated data access."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from ..contract.enforcer import PolicyEnforcer
from ..contract.registry import ContractRegistry
from ..core.enums import AssetType, TransferStatus
from ..core.exceptions import AdapterError, ContractNotFoundError, PolicyViolationError
from ..core.models import TransferRequest, TransferResult
from .adapters.base import AbstractDataAdapter
from .adapters.db_adapter import DbTableAdapter
from .adapters.file_adapter import FileAdapter
from .adapters.json_adapter import JsonApiAdapter
from .adapters.stream_adapter import StreamAdapter


_ADAPTERS: Dict[AssetType, AbstractDataAdapter] = {
    AssetType.JSON_API: JsonApiAdapter(),
    AssetType.CSV_FILE: FileAdapter(),
    AssetType.PARQUET_FILE: FileAdapter(),
    AssetType.DB_TABLE: DbTableAdapter(),
    AssetType.STREAM: StreamAdapter(),
}


class TransferService:
    def __init__(self, registry: ContractRegistry | None = None):
        self.registry = registry or ContractRegistry()
        self.enforcer = PolicyEnforcer()

    async def transfer(self, request: TransferRequest) -> TransferResult:
        """
        Execute a data transfer:
        1. Load and auto-expire contract
        2. Enforce policy (8 stages)
        3. Select adapter and fetch data
        4. Return TransferResult
        """
        # Load contract
        try:
            contract = await self.registry.expire_if_needed(request.contract_id)
        except ContractNotFoundError as exc:
            return TransferResult(
                transfer_id=request.transfer_id,
                contract_id=request.contract_id,
                status=TransferStatus.FAILED,
                blocked_reason=str(exc),
            )

        # Policy enforcement
        try:
            self.enforcer.enforce(contract, request)
        except PolicyViolationError as exc:
            return TransferResult(
                transfer_id=request.transfer_id,
                contract_id=request.contract_id,
                status=TransferStatus.BLOCKED,
                blocked_reason=exc.reason,
            )

        # Fetch data
        adapter = _ADAPTERS.get(contract.data_asset.asset_type)
        if not adapter:
            return TransferResult(
                transfer_id=request.transfer_id,
                contract_id=request.contract_id,
                status=TransferStatus.FAILED,
                blocked_reason=f"No adapter for asset type '{contract.data_asset.asset_type}'",
            )

        try:
            records = await adapter.read(
                endpoint=contract.data_asset.endpoint,
                limit=request.requested_records,
                filters=request.filters or {},
                masked_columns=contract.usage_policy.masked_columns,
            )
        except AdapterError as exc:
            return TransferResult(
                transfer_id=request.transfer_id,
                contract_id=request.contract_id,
                status=TransferStatus.FAILED,
                blocked_reason=str(exc),
            )

        return TransferResult(
            transfer_id=request.transfer_id,
            contract_id=request.contract_id,
            status=TransferStatus.COMPLETED,
            records_returned=len(records),
            data=records,
            completed_at=datetime.now(timezone.utc),
        )
