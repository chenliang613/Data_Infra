"""Contract digital signing and verification."""
from __future__ import annotations

from ..core.crypto import load_private_key, load_public_key, sign, verify
from ..core.exceptions import SignatureError
from ..core.models import Contract


def sign_contract(contract: Contract, party_id: str, private_key_pem: str) -> Contract:
    """Add a digital signature from `party_id` to the contract."""
    payload = contract.canonical_bytes()
    sig = sign(payload, load_private_key(private_key_pem))
    updated_sigs = {**contract.signatures, party_id: sig}
    return contract.model_copy(update={"signatures": updated_sigs})


def verify_contract_signature(contract: Contract, party_id: str, public_key_pem: str) -> bool:
    """Verify signature for `party_id`. Raises SignatureError on failure."""
    sig = contract.signatures.get(party_id)
    if not sig:
        raise SignatureError(f"No signature found for party '{party_id}'")
    payload = contract.canonical_bytes()
    return verify(payload, sig, load_public_key(public_key_pem))


def verify_all_signatures(contract: Contract) -> bool:
    """Verify both provider and consumer signatures."""
    for party_info in [contract.provider, contract.consumer]:
        if not party_info.public_key_pem:
            raise SignatureError(f"No public key for party '{party_info.party_id}'")
        verify_contract_signature(contract, party_info.party_id, party_info.public_key_pem)
    return True
