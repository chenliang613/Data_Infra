"""NegotiationSession: orchestrates multi-turn dialogue between two Agents."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Callable, Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from ..core.enums import NegotiationStatus
from ..core.exceptions import NegotiationError, NegotiationTimeoutError
from ..core.models import (
    DataAsset,
    NegotiationMessage,
    NegotiationSession as NegotiationSessionModel,
    Party,
    UsagePolicy,
)
from ..agent.provider_agent import ProviderConnectorAgent
from ..agent.requester_agent import RequesterConnectorAgent
from .contract_builder import build_contract
from .protocol import NegotiationProtocol, ProtocolState

console = Console()


class NegotiationSession:
    """
    Drives a multi-turn negotiation between ProviderAgent and RequesterAgent.
    Each "turn" = one agent responds to the other's last message.
    """

    def __init__(
        self,
        provider: Party,
        consumer: Party,
        asset: DataAsset,
        provider_policy: UsagePolicy,
        consumer_need: str,
        consumer_acceptable_policy: UsagePolicy,
        max_turns: int = 20,
        on_message: Optional[Callable[[str, str], None]] = None,
    ):
        self.provider = provider
        self.consumer = consumer
        self.asset = asset
        self.max_turns = max_turns
        self.on_message = on_message

        self.protocol = NegotiationProtocol()
        self.session_model = NegotiationSessionModel(
            provider_id=provider.party_id,
            requester_id=consumer.party_id,
            asset_id=asset.asset_id,
        )

        self.provider_agent = ProviderConnectorAgent(
            assets=[asset],
            default_policy=provider_policy,
        )
        self.requester_agent = RequesterConnectorAgent(
            data_need=consumer_need,
            acceptable_policy=consumer_acceptable_policy,
        )

    def _log(self, role: str, text: str, tool: Optional[str] = None) -> None:
        color = "cyan" if role == "provider" else "green"
        label = f"[{color}][{'提供方' if role == 'provider' else '请求方'} Agent][/{color}]"
        suffix = f" 🔧 {tool}" if tool else ""
        console.print(Panel(f"{label}{suffix}\n{text}", border_style=color))
        if self.on_message:
            self.on_message(role, text)

    def _add_message(self, role: str, content: str, policy: Optional[UsagePolicy] = None) -> None:
        msg = NegotiationMessage(
            negotiation_id=self.session_model.negotiation_id,
            sender_role=role,
            content=content,
            proposed_terms=policy,
        )
        self.session_model.messages.append(msg)

    def negotiate(self) -> NegotiationSessionModel:
        """
        Run negotiation to completion.
        Returns the updated NegotiationSession with result.
        """
        self.session_model.status = NegotiationStatus.IN_PROGRESS
        self.protocol.transition(ProtocolState.REQUESTER_OPENING)

        # --- Turn 0: Requester opens ---
        opening_prompt = (
            f"请开始协商。我方需要访问数据资产 '{self.asset.asset_id}'（{self.asset.name}）。"
            f"请先调用 describe_need 工具描述具体需求和初始提案。"
        )
        req_result = self.requester_agent.respond(opening_prompt)
        self._add_message("requester", req_result.text)
        self._log("requester", req_result.text, req_result.tool_name)

        last_message_for_provider = self._format_for_other_party(
            "requester", req_result
        )

        self.protocol.transition(ProtocolState.PROVIDER_REVIEWING)

        turn = 1
        current_turn_role = "provider"  # provider responds next

        while not self.protocol.is_terminal and turn <= self.max_turns:
            self.session_model.turns = turn

            if current_turn_role == "provider":
                result = self.provider_agent.respond(last_message_for_provider)
                self._add_message("provider", result.text)
                self._log("provider", result.text, result.tool_name)

                if result.accepted:
                    policy = self._extract_policy(result.tool_input)
                    self._conclude_agreed(policy)
                    return self.session_model
                elif result.rejected:
                    self._conclude_rejected("provider", result.tool_input.get("reason", ""))
                    return self.session_model
                else:
                    # counter_propose or text response
                    last_message_for_provider = self._format_for_other_party("provider", result)
                    self.protocol.transition(ProtocolState.REQUESTER_RESPONDING)
                    current_turn_role = "requester"

            else:  # requester
                result = self.requester_agent.respond(last_message_for_provider)
                self._add_message("requester", result.text)
                self._log("requester", result.text, result.tool_name)

                if result.accepted:
                    policy = self._extract_policy(result.tool_input)
                    self._conclude_agreed(policy)
                    return self.session_model
                elif result.rejected:
                    self._conclude_rejected("requester", result.tool_input.get("reason", ""))
                    return self.session_model
                else:
                    last_message_for_provider = self._format_for_other_party("requester", result)
                    self.protocol.transition(ProtocolState.PROVIDER_REVIEWING)
                    current_turn_role = "provider"

            turn += 1

        if not self.protocol.is_terminal:
            self.session_model.status = NegotiationStatus.FAILED
            self.session_model.concluded_at = datetime.now(timezone.utc)
            raise NegotiationTimeoutError(
                f"Negotiation exceeded {self.max_turns} turns without conclusion."
            )

        return self.session_model

    def _format_for_other_party(self, sender_role: str, result) -> str:
        if result.tool_name == "counter_propose" and result.tool_input:
            policy = result.tool_input.get("proposed_policy", {})
            explanation = result.tool_input.get("explanation", result.text)
            return (
                f"对方（{'提供方' if sender_role == 'provider' else '请求方'}）提出反提案：\n"
                f"{explanation}\n\n提案条款：{json.dumps(policy, ensure_ascii=False)}"
            )
        elif result.tool_name == "describe_need" and result.tool_input:
            policy = result.tool_input.get("proposed_policy", {})
            purpose = result.tool_input.get("purpose", "")
            return (
                f"请求方发起数据访问请求：\n"
                f"目的：{purpose}\n"
                f"初始提案：{json.dumps(policy, ensure_ascii=False)}"
            )
        return result.text or "（无文字内容）"

    def _extract_policy(self, tool_input: Optional[dict]) -> Optional[UsagePolicy]:
        if not tool_input:
            return None
        policy_data = tool_input.get("agreed_policy") or tool_input.get("proposed_policy")
        if not policy_data:
            return None
        try:
            return UsagePolicy(**policy_data)
        except Exception:
            return None

    def _conclude_agreed(self, policy: Optional[UsagePolicy]) -> None:
        self.protocol.state = ProtocolState.AGREED
        self.session_model.status = NegotiationStatus.AGREED
        self.session_model.agreed_policy = policy
        self.session_model.concluded_at = datetime.now(timezone.utc)
        console.print(
            Panel(
                f"[bold green]✅ 协商成功！双方已就合约条款达成一致。[/bold green]\n"
                f"条款：{json.dumps(policy.model_dump() if policy else {}, ensure_ascii=False, indent=2)}",
                title="协商结果",
                border_style="green",
            )
        )

    def _conclude_rejected(self, rejecting_role: str, reason: str) -> None:
        self.protocol.state = ProtocolState.REJECTED
        self.session_model.status = NegotiationStatus.REJECTED
        self.session_model.concluded_at = datetime.now(timezone.utc)
        console.print(
            Panel(
                f"[bold red]❌ 协商失败。{rejecting_role} 拒绝了协商。\n原因：{reason}[/bold red]",
                title="协商结果",
                border_style="red",
            )
        )

    def build_contract(self):
        """Build a Contract from agreed negotiation. Call after negotiate() succeeds."""
        if self.session_model.status != NegotiationStatus.AGREED:
            raise NegotiationError("Cannot build contract: negotiation not agreed")
        if not self.session_model.agreed_policy:
            raise NegotiationError("No agreed policy to build contract from")
        return build_contract(
            negotiation=self.session_model,
            provider=self.provider,
            consumer=self.consumer,
            asset=self.asset,
            agreed_policy=self.session_model.agreed_policy,
        )
