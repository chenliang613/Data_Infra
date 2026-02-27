"""Contract management endpoints."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...contract.registry import ContractRegistry
from ...core.exceptions import ContractNotFoundError, ContractStatusError
from ...core.models import Contract

router = APIRouter(prefix="/contracts", tags=["Contracts"])
registry = ContractRegistry()


@router.get("", response_model=List[Contract])
async def list_contracts(party_id: Optional[str] = None) -> List[Contract]:
    if party_id:
        return await registry.list_by_party(party_id)
    return await registry.list_active()


@router.get("/{contract_id}", response_model=Contract)
async def get_contract(contract_id: str) -> Contract:
    try:
        return await registry.get(contract_id)
    except ContractNotFoundError as exc:
        raise HTTPException(404, str(exc))


class RevokeRequest(BaseModel):
    reason: str


@router.post("/{contract_id}/revoke")
async def revoke_contract(contract_id: str, body: RevokeRequest) -> dict:
    try:
        contract = await registry.revoke(contract_id, body.reason)
        return {"contract_id": contract.contract_id, "status": contract.status.value}
    except ContractNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except ContractStatusError as exc:
        raise HTTPException(400, str(exc))
