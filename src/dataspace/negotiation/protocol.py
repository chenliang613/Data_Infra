"""Negotiation protocol state machine."""
from __future__ import annotations

from enum import Enum


class ProtocolState(str, Enum):
    IDLE = "idle"
    REQUESTER_OPENING = "requester_opening"   # Requester sends first proposal
    PROVIDER_REVIEWING = "provider_reviewing" # Provider reviews and responds
    REQUESTER_RESPONDING = "requester_responding"
    AGREED = "agreed"
    REJECTED = "rejected"
    FAILED = "failed"


# Valid state transitions: {current_state: [allowed_next_states]}
TRANSITIONS: dict[ProtocolState, list[ProtocolState]] = {
    ProtocolState.IDLE: [ProtocolState.REQUESTER_OPENING],
    ProtocolState.REQUESTER_OPENING: [ProtocolState.PROVIDER_REVIEWING, ProtocolState.FAILED],
    ProtocolState.PROVIDER_REVIEWING: [
        ProtocolState.AGREED,
        ProtocolState.REJECTED,
        ProtocolState.REQUESTER_RESPONDING,
    ],
    ProtocolState.REQUESTER_RESPONDING: [
        ProtocolState.AGREED,
        ProtocolState.REJECTED,
        ProtocolState.PROVIDER_REVIEWING,
    ],
    ProtocolState.AGREED: [],
    ProtocolState.REJECTED: [],
    ProtocolState.FAILED: [],
}


class NegotiationProtocol:
    def __init__(self) -> None:
        self.state = ProtocolState.IDLE

    def transition(self, next_state: ProtocolState) -> None:
        allowed = TRANSITIONS.get(self.state, [])
        if next_state not in allowed:
            raise ValueError(
                f"Invalid transition: {self.state} → {next_state} "
                f"(allowed: {[s.value for s in allowed]})"
            )
        self.state = next_state

    @property
    def is_terminal(self) -> bool:
        return self.state in (ProtocolState.AGREED, ProtocolState.REJECTED, ProtocolState.FAILED)

    @property
    def succeeded(self) -> bool:
        return self.state == ProtocolState.AGREED
