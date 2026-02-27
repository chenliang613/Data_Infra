"""Contract registry: lifecycle management."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from ..core.enums import ContractStatus
from ..core.exceptions import ContractNotFoundError, ContractStatusError
from ..core.models import Contract
from ..db.database import get_session
from ..db.repositories import contract_repo


class ContractRegistry:
    """Manages contract CRUD and state transitions."""

    async def save(self, contract: Contract) -> Contract:
        async with get_session() as session:
            existing = await contract_repo.get(session, contract.contract_id)
            if existing:
                return await contract_repo.update(session, contract)
            return await contract_repo.create(session, contract)

    async def get(self, contract_id: str) -> Contract:
        async with get_session() as session:
            contract = await contract_repo.get(session, contract_id)
        if not contract:
            raise ContractNotFoundError(f"Contract '{contract_id}' not found")
        return contract

    async def list_by_party(self, party_id: str) -> List[Contract]:
        async with get_session() as session:
            return await contract_repo.list_by_party(session, party_id)

    async def list_active(self) -> List[Contract]:
        async with get_session() as session:
            return await contract_repo.list_active(session)

    async def activate(self, contract_id: str) -> Contract:
        contract = await self.get(contract_id)
        if contract.status != ContractStatus.PENDING_SIGNATURES:
            raise ContractStatusError(
                f"Cannot activate contract in status '{contract.status}'"
            )
        updated = contract.model_copy(update={"status": ContractStatus.ACTIVE})
        return await self.save(updated)

    async def revoke(self, contract_id: str, reason: str) -> Contract:
        contract = await self.get(contract_id)
        if contract.status not in (ContractStatus.ACTIVE, ContractStatus.SUSPENDED):
            raise ContractStatusError(
                f"Cannot revoke contract in status '{contract.status}'"
            )
        updated = contract.model_copy(update={
            "status": ContractStatus.REVOKED,
            "revocation_reason": reason,
        })
        return await self.save(updated)

    async def expire_if_needed(self, contract_id: str) -> Contract:
        contract = await self.get(contract_id)
        now = datetime.now(timezone.utc)
        valid_until = contract.valid_until
        if valid_until is not None and valid_until.tzinfo is None:
            valid_until = valid_until.replace(tzinfo=timezone.utc)
        if (
            contract.status == ContractStatus.ACTIVE
            and valid_until
            and now > valid_until
        ):
            updated = contract.model_copy(update={"status": ContractStatus.EXPIRED})
            return await self.save(updated)
        return contract
