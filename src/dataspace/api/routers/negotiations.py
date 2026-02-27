"""Negotiation endpoints."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from ...core.enums import NegotiationStatus
from ...core.exceptions import NegotiationError
from ...core.models import NegotiationSession, UsagePolicy
from ...db.database import get_session
from ...db.repositories import asset_repo, negotiation_repo, party_repo
from ...negotiation.session import NegotiationSession as NegSession

router = APIRouter(prefix="/negotiations", tags=["Negotiations"])


class NegotiationStart(BaseModel):
    provider_id: str
    requester_id: str
    asset_id: str
    consumer_need: str
    consumer_acceptable_policy: UsagePolicy
    max_turns: int = 15


@router.post("", status_code=201)
async def start_negotiation(data: NegotiationStart) -> dict:
    """
    Start a negotiation between two parties.
    This runs the full multi-turn Agent dialogue synchronously.
    For production use, consider running asynchronously via a task queue.
    """
    async with get_session() as session:
        provider = await party_repo.get(session, data.provider_id)
        consumer = await party_repo.get(session, data.requester_id)
        asset = await asset_repo.get(session, data.asset_id)

    if not provider:
        raise HTTPException(404, f"Provider '{data.provider_id}' not found")
    if not consumer:
        raise HTTPException(404, f"Consumer '{data.requester_id}' not found")
    if not asset:
        raise HTTPException(404, f"Asset '{data.asset_id}' not found")

    provider_policy = asset.default_policy or UsagePolicy()

    session_runner = NegSession(
        provider=provider,
        consumer=consumer,
        asset=asset,
        provider_policy=provider_policy,
        consumer_need=data.consumer_need,
        consumer_acceptable_policy=data.consumer_acceptable_policy,
        max_turns=data.max_turns,
    )

    try:
        neg_model = session_runner.negotiate()
    except NegotiationError as exc:
        raise HTTPException(500, detail=str(exc))

    # Persist negotiation
    async with get_session() as db_session:
        await negotiation_repo.create(db_session, neg_model)

    result: dict = {
        "negotiation_id": neg_model.negotiation_id,
        "status": neg_model.status.value,
        "turns": neg_model.turns,
        "agreed_policy": neg_model.agreed_policy.model_dump() if neg_model.agreed_policy else None,
        "contract_id": neg_model.contract_id,
    }

    # If agreed, build and activate contract
    if neg_model.status == NegotiationStatus.AGREED:
        from ...contract.registry import ContractRegistry
        from ...contract.signer import sign_contract
        from ...core.crypto import load_key_pair, load_private_key
        import os

        keys_dir = os.getenv("KEYS_DIR", "./data/keys")
        contract = session_runner.build_contract()

        # Sign with provider key
        try:
            priv_pem, _ = load_key_pair(provider.party_id, keys_dir)
            contract = sign_contract(contract, provider.party_id, priv_pem)
        except FileNotFoundError:
            pass  # Keys not found, skip signing in demo mode

        # Sign with consumer key
        try:
            priv_pem, _ = load_key_pair(consumer.party_id, keys_dir)
            contract = sign_contract(contract, consumer.party_id, priv_pem)
        except FileNotFoundError:
            pass

        registry = ContractRegistry()
        contract = await registry.save(contract)

        if len(contract.signatures) >= 2:
            contract = await registry.activate(contract.contract_id)

        neg_model.contract_id = contract.contract_id
        async with get_session() as db_session:
            await negotiation_repo.update(db_session, neg_model)

        result["contract_id"] = contract.contract_id
        result["contract_status"] = contract.status.value

    return result


@router.get("/{negotiation_id}")
async def get_negotiation(negotiation_id: str) -> dict:
    async with get_session() as session:
        neg = await negotiation_repo.get(session, negotiation_id)
    if not neg:
        raise HTTPException(404, "Negotiation not found")
    return neg.model_dump(mode="json")
