"""Provider (Party A) Connector Agent."""
from __future__ import annotations

import json
from typing import List

from ..core.models import DataAsset, UsagePolicy
from .base_agent import BaseConnectorAgent
from .prompts.provider_system import PROVIDER_SYSTEM_PROMPT
from .tools.provider_tools import PROVIDER_TOOLS


class ProviderConnectorAgent(BaseConnectorAgent):
    def __init__(self, assets: List[DataAsset], default_policy: UsagePolicy):
        self.assets = assets
        self.default_policy = default_policy

        catalog_text = "\n".join(
            f"- {a.asset_id}: {a.name} ({a.asset_type.value}) — {a.description}"
            for a in assets
        )
        policy_text = json.dumps(default_policy.model_dump(), ensure_ascii=False, indent=2)

        system = PROVIDER_SYSTEM_PROMPT.format(
            asset_catalog=catalog_text or "（暂无资产）",
            default_policy=policy_text,
        )

        handlers = {
            "review_catalog": self._handle_review_catalog,
            "check_policy": self._handle_check_policy,
            "accept_contract": lambda inp: "已接受合约。",
            "reject_negotiation": lambda inp: "已拒绝协商。",
            "counter_propose": lambda inp: "反提案已提交。",
        }

        super().__init__(system_prompt=system, tools=PROVIDER_TOOLS, tool_handlers=handlers)

    def _handle_review_catalog(self, inp: dict) -> str:
        asset_id = inp.get("asset_id")
        if asset_id:
            asset = next((a for a in self.assets if a.asset_id == asset_id), None)
            if not asset:
                return json.dumps({"error": f"资产 '{asset_id}' 不存在"}, ensure_ascii=False)
            d = asset.model_dump(mode="json")
            d["default_policy"] = self.default_policy.model_dump()
            return json.dumps(d, ensure_ascii=False, default=str)
        return json.dumps(
            {
                "assets": [
                    {
                        "asset_id": a.asset_id,
                        "name": a.name,
                        "type": a.asset_type.value,
                        "description": a.description,
                    }
                    for a in self.assets
                ],
                "default_policy": self.default_policy.model_dump(),
            },
            ensure_ascii=False,
        )

    def _handle_check_policy(self, inp: dict) -> str:
        proposed = inp.get("proposed_policy", {})
        reasons = []
        ok = True

        if proposed.get("max_requests_per_day", 0) > self.default_policy.max_requests_per_day:
            ok = False
            reasons.append(
                f"每日请求次数 {proposed['max_requests_per_day']} 超过上限 {self.default_policy.max_requests_per_day}"
            )
        if proposed.get("max_records_per_request", 0) > self.default_policy.max_records_per_request:
            ok = False
            reasons.append(
                f"单次记录数 {proposed['max_records_per_request']} 超过上限 {self.default_policy.max_records_per_request}"
            )
        if proposed.get("duration_days", 0) > self.default_policy.duration_days:
            ok = False
            reasons.append(
                f"有效期 {proposed['duration_days']} 天超过上限 {self.default_policy.duration_days} 天"
            )

        return json.dumps(
            {
                "acceptable": ok,
                "reasons": reasons if reasons else ["策略检查通过"],
                "max_allowed": self.default_policy.model_dump(),
            },
            ensure_ascii=False,
        )
