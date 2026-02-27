"""Tool schemas shared by both provider and requester agents."""

ACCEPT_CONTRACT_TOOL = {
    "name": "accept_contract",
    "description": "接受当前协商条款，同意签署合约。调用此工具表示本方正式接受所有条款。",
    "input_schema": {
        "type": "object",
        "properties": {
            "agreed_policy": {
                "type": "object",
                "description": "双方最终同意的 UsagePolicy（完整字段）",
                "properties": {
                    "max_requests_per_day": {"type": "integer"},
                    "max_records_per_request": {"type": "integer"},
                    "allowed_operations": {"type": "array", "items": {"type": "string"}},
                    "masked_columns": {"type": "array", "items": {"type": "string"}},
                    "duration_days": {"type": "integer"},
                    "purpose": {"type": "string"},
                    "no_third_party_transfer": {"type": "boolean"},
                },
                "required": ["max_requests_per_day", "max_records_per_request", "duration_days", "purpose"],
            },
            "message": {"type": "string", "description": "接受说明（可选）"},
        },
        "required": ["agreed_policy"],
    },
}

REJECT_NEGOTIATION_TOOL = {
    "name": "reject_negotiation",
    "description": "拒绝协商，宣告协商失败。仅在无法达成任何共识时使用。",
    "input_schema": {
        "type": "object",
        "properties": {
            "reason": {"type": "string", "description": "拒绝原因"},
        },
        "required": ["reason"],
    },
}

COUNTER_PROPOSE_TOOL = {
    "name": "counter_propose",
    "description": "提出反提案，修改部分条款后继续协商。",
    "input_schema": {
        "type": "object",
        "properties": {
            "proposed_policy": {
                "type": "object",
                "description": "本方提案的 UsagePolicy",
                "properties": {
                    "max_requests_per_day": {"type": "integer"},
                    "max_records_per_request": {"type": "integer"},
                    "allowed_operations": {"type": "array", "items": {"type": "string"}},
                    "masked_columns": {"type": "array", "items": {"type": "string"}},
                    "duration_days": {"type": "integer"},
                    "purpose": {"type": "string"},
                    "no_third_party_transfer": {"type": "boolean"},
                },
                "required": ["max_requests_per_day", "max_records_per_request", "duration_days", "purpose"],
            },
            "explanation": {"type": "string", "description": "反提案说明"},
        },
        "required": ["proposed_policy", "explanation"],
    },
}
