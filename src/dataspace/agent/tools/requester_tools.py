"""Tool schemas for the Requester agent."""
from .shared_tools import ACCEPT_CONTRACT_TOOL, REJECT_NEGOTIATION_TOOL, COUNTER_PROPOSE_TOOL

DESCRIBE_NEED_TOOL = {
    "name": "describe_need",
    "description": "描述本方的数据访问需求，开始协商。",
    "input_schema": {
        "type": "object",
        "properties": {
            "asset_id": {"type": "string", "description": "请求访问的数据资产ID"},
            "purpose": {"type": "string", "description": "数据用途"},
            "proposed_policy": {
                "type": "object",
                "description": "初始提案的 UsagePolicy",
                "properties": {
                    "max_requests_per_day": {"type": "integer"},
                    "max_records_per_request": {"type": "integer"},
                    "duration_days": {"type": "integer"},
                    "purpose": {"type": "string"},
                    "allowed_operations": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["max_requests_per_day", "max_records_per_request", "duration_days", "purpose"],
            },
        },
        "required": ["asset_id", "purpose", "proposed_policy"],
    },
}

REQUESTER_TOOLS = [DESCRIBE_NEED_TOOL, ACCEPT_CONTRACT_TOOL, REJECT_NEGOTIATION_TOOL, COUNTER_PROPOSE_TOOL]
