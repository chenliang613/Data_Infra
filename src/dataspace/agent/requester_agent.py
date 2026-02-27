"""Requester (Party B) Connector Agent."""
from __future__ import annotations

import json

from ..core.models import UsagePolicy
from .base_agent import BaseConnectorAgent
from .prompts.requester_system import REQUESTER_SYSTEM_PROMPT
from .tools.requester_tools import REQUESTER_TOOLS


class RequesterConnectorAgent(BaseConnectorAgent):
    def __init__(self, data_need: str, acceptable_policy: UsagePolicy):
        self.data_need = data_need
        self.acceptable_policy = acceptable_policy

        policy_text = json.dumps(acceptable_policy.model_dump(), ensure_ascii=False, indent=2)
        system = REQUESTER_SYSTEM_PROMPT.format(
            data_need=data_need,
            acceptable_policy=policy_text,
        )

        handlers = {
            "describe_need": lambda inp: "需求描述已发送，等待提供方回应。",
            "accept_contract": lambda inp: "已接受合约。",
            "reject_negotiation": lambda inp: "已拒绝协商。",
            "counter_propose": lambda inp: "反提案已提交。",
        }

        super().__init__(system_prompt=system, tools=REQUESTER_TOOLS, tool_handlers=handlers)
