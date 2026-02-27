"""Policy enforcer: 8-stage gate before any data transfer."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

from ..core.enums import ContractStatus
from ..core.exceptions import PolicyViolationError, SignatureError
from ..core.models import Contract, TransferRequest
from .signer import verify_all_signatures


class PolicyEnforcer:
    """
    Enforces contract usage policy before each data transfer.
    All 8 stages must pass; the first failure raises PolicyViolationError.
    """

    # In-memory daily request counter: {contract_id: {date_str: count}}
    _daily_counts: Dict[str, Dict[str, int]] = {}

    def enforce(self, contract: Contract, request: TransferRequest) -> None:
        """Run all 8 enforcement stages. Raises PolicyViolationError if any fail."""
        self._stage1_contract_active(contract)
        self._stage2_signatures_valid(contract)
        self._stage3_validity_period(contract)
        self._stage4_allowed_operation(contract, request)
        self._stage5_daily_rate_limit(contract, request)
        self._stage6_record_limit(contract, request)
        self._stage7_requester_identity(contract, request)
        self._stage8_purpose_compliance(contract, request)

    # ------------------------------------------------------------------
    def _stage1_contract_active(self, contract: Contract) -> None:
        if contract.status != ContractStatus.ACTIVE:
            raise PolicyViolationError(
                f"Stage1: Contract is not ACTIVE (status={contract.status})",
                {"contract_id": contract.contract_id, "status": contract.status},
            )

    def _stage2_signatures_valid(self, contract: Contract) -> None:
        try:
            verify_all_signatures(contract)
        except SignatureError as exc:
            raise PolicyViolationError(f"Stage2: {exc}", {"contract_id": contract.contract_id}) from exc

    def _stage3_validity_period(self, contract: Contract) -> None:
        now = datetime.now(timezone.utc)
        if contract.valid_until and now > contract.valid_until:
            raise PolicyViolationError(
                "Stage3: Contract has expired",
                {"valid_until": str(contract.valid_until), "now": str(now)},
            )
        if now < contract.valid_from:
            raise PolicyViolationError(
                "Stage3: Contract is not yet valid",
                {"valid_from": str(contract.valid_from)},
            )

    def _stage4_allowed_operation(self, contract: Contract, request: TransferRequest) -> None:
        if request.operation not in contract.usage_policy.allowed_operations:
            raise PolicyViolationError(
                f"Stage4: Operation '{request.operation}' not in allowed list",
                {"allowed": contract.usage_policy.allowed_operations},
            )

    def _stage5_daily_rate_limit(self, contract: Contract, request: TransferRequest) -> None:
        today = datetime.now(timezone.utc).date().isoformat()
        cid = contract.contract_id
        self._daily_counts.setdefault(cid, {})
        count = self._daily_counts[cid].get(today, 0)
        if count >= contract.usage_policy.max_requests_per_day:
            raise PolicyViolationError(
                f"Stage5: Daily request limit exceeded ({count}/{contract.usage_policy.max_requests_per_day})",
                {"today_count": count, "limit": contract.usage_policy.max_requests_per_day},
            )
        # Increment after pass
        self._daily_counts[cid][today] = count + 1

    def _stage6_record_limit(self, contract: Contract, request: TransferRequest) -> None:
        limit = contract.usage_policy.max_records_per_request
        if request.requested_records > limit:
            raise PolicyViolationError(
                f"Stage6: Requested {request.requested_records} records exceeds limit {limit}",
                {"requested": request.requested_records, "limit": limit},
            )

    def _stage7_requester_identity(self, contract: Contract, request: TransferRequest) -> None:
        if request.requester_id != contract.consumer.party_id:
            raise PolicyViolationError(
                f"Stage7: Requester '{request.requester_id}' != consumer '{contract.consumer.party_id}'",
                {"requester": request.requester_id, "consumer": contract.consumer.party_id},
            )

    def _stage8_purpose_compliance(self, contract: Contract, request: TransferRequest) -> None:
        if request.purpose and contract.usage_policy.purpose:
            if request.purpose.lower() != contract.usage_policy.purpose.lower():
                raise PolicyViolationError(
                    f"Stage8: Purpose mismatch '{request.purpose}' vs '{contract.usage_policy.purpose}'",
                    {"request_purpose": request.purpose, "contract_purpose": contract.usage_policy.purpose},
                )
