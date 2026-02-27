"""Data transfer endpoints."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...audit.logger import audit_logger
from ...core.enums import AuditEventType, TransferStatus
from ...core.models import TransferRequest, TransferResult
from ...data.transfer_service import TransferService

router = APIRouter(prefix="/transfer", tags=["Transfer"])
transfer_service = TransferService()


class TransferRequestBody(BaseModel):
    contract_id: str
    requester_id: str
    operation: str = "read"
    requested_records: int = 100
    purpose: str = ""
    filters: Dict[str, Any] = {}


@router.post("")
async def request_transfer(body: TransferRequestBody) -> dict:
    request = TransferRequest(**body.model_dump())

    # Audit: transfer requested
    await audit_logger.log(
        AuditEventType.TRANSFER_REQUESTED,
        actor_id=request.requester_id,
        subject_id=request.contract_id,
        payload={"transfer_id": request.transfer_id, "requested_records": request.requested_records},
    )

    result = await transfer_service.transfer(request)

    # Audit: outcome
    if result.status == TransferStatus.COMPLETED:
        await audit_logger.log(
            AuditEventType.TRANSFER_COMPLETED,
            actor_id=request.requester_id,
            subject_id=request.contract_id,
            payload={"transfer_id": request.transfer_id, "records_returned": result.records_returned},
        )
    elif result.status == TransferStatus.BLOCKED:
        await audit_logger.log(
            AuditEventType.TRANSFER_POLICY_BLOCKED,
            actor_id=request.requester_id,
            subject_id=request.contract_id,
            payload={"transfer_id": request.transfer_id, "reason": result.blocked_reason},
        )
    else:
        await audit_logger.log(
            AuditEventType.TRANSFER_FAILED,
            actor_id=request.requester_id,
            subject_id=request.contract_id,
            payload={"transfer_id": request.transfer_id, "reason": result.blocked_reason},
        )

    return {
        "transfer_id": result.transfer_id,
        "status": result.status.value,
        "records_returned": result.records_returned,
        "data": result.data,
        "blocked_reason": result.blocked_reason,
    }
