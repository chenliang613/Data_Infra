"""Audit trail endpoints."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter

from ...audit.verifier import VerificationResult, verify_chain
from ...db.database import get_session
from ...db.repositories import audit_repo

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("")
async def list_audit_log(
    offset: int = 0,
    limit: int = 50,
    subject_id: Optional[str] = None,
) -> List[dict]:
    async with get_session() as session:
        return await audit_repo.list_entries(session, offset=offset, limit=limit, subject_id=subject_id)


@router.post("/verify")
async def verify_audit_chain() -> dict:
    result: VerificationResult = await verify_chain()
    return {
        "valid": result.valid,
        "total_entries": result.total_entries,
        "broken_at_sequence": result.broken_at_sequence,
        "error": result.error,
        "message": "审计链完整性验证通过 ✅" if result.valid else f"审计链已被篡改 ❌: {result.error}",
    }
