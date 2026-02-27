"""Tool schemas for the Provider agent."""
from .shared_tools import ACCEPT_CONTRACT_TOOL, REJECT_NEGOTIATION_TOOL, COUNTER_PROPOSE_TOOL

REVIEW_CATALOG_TOOL = {
    "name": "review_catalog",
    "description": "查询本方数据资产目录，了解可提供的数据集信息。",
    "input_schema": {
        "type": "object",
        "properties": {
            "asset_id": {"type": "string", "description": "数据资产ID（可选，不填则列出所有）"},
        },
    },
}

CHECK_POLICY_TOOL = {
    "name": "check_policy",
    "description": "检查某项策略提案是否符合本方安全基线，返回是否可接受及原因。",
    "input_schema": {
        "type": "object",
        "properties": {
            "proposed_policy": {
                "type": "object",
                "description": "要检查的 UsagePolicy",
                "properties": {
                    "max_requests_per_day": {"type": "integer"},
                    "max_records_per_request": {"type": "integer"},
                    "duration_days": {"type": "integer"},
                    "purpose": {"type": "string"},
                },
            },
        },
        "required": ["proposed_policy"],
    },
}

PROVIDER_TOOLS = [REVIEW_CATALOG_TOOL, CHECK_POLICY_TOOL, ACCEPT_CONTRACT_TOOL, REJECT_NEGOTIATION_TOOL, COUNTER_PROPOSE_TOOL]
