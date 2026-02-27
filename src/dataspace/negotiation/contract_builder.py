"""Build a Contract from agreed negotiation terms."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..core.enums import ContractStatus
from ..core.models import (
    Contract,
    ContractPartyInfo,
    DataAsset,
    NegotiationSession,
    Party,
    UsagePolicy,
)


def build_contract(
    negotiation: NegotiationSession,
    provider: Party,
    consumer: Party,
    asset: DataAsset,
    agreed_policy: UsagePolicy,
) -> Contract:
    now = datetime.now(timezone.utc)
    valid_until = now + timedelta(days=agreed_policy.duration_days)

    provider_info = ContractPartyInfo(
        party_id=provider.party_id,
        name=provider.name,
        public_key_pem=provider.public_key_pem,
    )
    consumer_info = ContractPartyInfo(
        party_id=consumer.party_id,
        name=consumer.name,
        public_key_pem=consumer.public_key_pem,
    )

    return Contract(
        status=ContractStatus.PENDING_SIGNATURES,
        valid_from=now,
        valid_until=valid_until,
        provider=provider_info,
        consumer=consumer_info,
        data_asset=asset,
        usage_policy=agreed_policy,
        negotiation_id=negotiation.negotiation_id,
    )
