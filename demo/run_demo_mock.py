#!/usr/bin/env python3
"""
DataSpace 端到端演示（Mock 模式）
===================================
无需真实 Anthropic API Key，使用脚本化预设对话模拟 Agent 协商。
测试除 LLM 调用外的全部系统功能：RSA 签名、策略引擎、数据传输、审计链。

协商流程（3轮）：
  Turn 0: 请求方发起 → describe_need (每日10000次, 90天)
  Turn 1: 提供方反提案 → counter_propose (每日5000次, 60天, 脱敏)
  Turn 2: 请求方接受 → accept_contract (按提供方条款)
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Load .env if present
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path)

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

console = Console()

# ---------------------------------------------------------------------------
# Mock Agent — 脚本化预设对话，不调用真实 API
# ---------------------------------------------------------------------------
from dataspace.agent.base_agent import AgentTurnResult


class MockRequesterAgent:
    """
    请求方 Mock Agent：
      call 1 → describe_need（发起需求）
      call 2+ → accept_contract（接受对方条款）
    """

    def __init__(self):
        self._call_count = 0

    def reset(self):
        self._call_count = 0

    def respond(self, incoming_message: str) -> AgentTurnResult:
        self._call_count += 1

        if self._call_count == 1:
            # 发起需求
            console.print(
                Panel(
                    "[Mock] 请求方描述需求：每日10000次，90天，用于用户画像分析",
                    title="[cyan][请求方 Agent - Mock][/cyan]",
                    border_style="cyan",
                )
            )
            return AgentTurnResult(
                text="我方需要访问用户行为数据用于构建用户画像分析模型。希望每日可查询 10000 次，有效期 90 天。",
                tool_name="describe_need",
                tool_input={
                    "purpose": "用户画像分析",
                    "proposed_policy": {
                        "max_requests_per_day": 10000,
                        "max_records_per_request": 1000,
                        "allowed_operations": ["read"],
                        "masked_columns": [],
                        "duration_days": 90,
                        "purpose": "analytics",
                        "no_third_party_transfer": True,
                    },
                },
                stop_reason="tool_use",
            )
        else:
            # 接受提供方条款
            console.print(
                Panel(
                    "[Mock] 请求方接受提供方条款：每日5000次, 500条/次, 60天, email/phone脱敏",
                    title="[cyan][请求方 Agent - Mock][/cyan]",
                    border_style="cyan",
                )
            )
            return AgentTurnResult(
                text="✅ 接受全部条款。每日5000次、60天有效期、email/phone脱敏，符合我方要求。",
                tool_name="accept_contract",
                tool_input={
                    "agreed_policy": {
                        "max_requests_per_day": 5000,
                        "max_records_per_request": 500,
                        "allowed_operations": ["read"],
                        "masked_columns": ["email", "phone"],
                        "duration_days": 60,
                        "purpose": "analytics",
                        "no_third_party_transfer": True,
                    },
                },
                stop_reason="tool_use",
            )


class MockProviderAgent:
    """
    提供方 Mock Agent：
      call 1 → counter_propose（按本方策略上限反提案）
      call 2+ → accept_contract（若请求方接受则不会被调用）
    """

    def __init__(self):
        self._call_count = 0

    def reset(self):
        self._call_count = 0

    def respond(self, incoming_message: str) -> AgentTurnResult:
        self._call_count += 1

        console.print(
            Panel(
                "[Mock] 提供方反提案：最高5000次/天，500条/次，60天，email/phone必须脱敏",
                title="[yellow][提供方 Agent - Mock][/yellow]",
                border_style="yellow",
            )
        )
        return AgentTurnResult(
            text=(
                "已审阅数据资产目录。根据本方安全策略：\n"
                "最高可授权 5000次/天，单次 500条，有效期不超过 60 天，\n"
                "且 email/phone 字段必须脱敏。是否接受？"
            ),
            tool_name="counter_propose",
            tool_input={
                "explanation": "根据安全策略，最高授权 5000次/天，60天，脱敏 email/phone。",
                "proposed_policy": {
                    "max_requests_per_day": 5000,
                    "max_records_per_request": 500,
                    "allowed_operations": ["read"],
                    "masked_columns": ["email", "phone"],
                    "duration_days": 60,
                    "purpose": "analytics",
                    "no_third_party_transfer": True,
                },
            },
            stop_reason="tool_use",
        )


# ---------------------------------------------------------------------------
# 猴子补丁：将 NegotiationSession 中的真实 Agent 替换为 Mock Agent
# ---------------------------------------------------------------------------
import dataspace.negotiation.session as _neg_session_mod

_OriginalNegotiationSession = _neg_session_mod.NegotiationSession


class MockNegotiationSession(_OriginalNegotiationSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 替换真实 Agent
        self.provider_agent = MockProviderAgent()
        self.requester_agent = MockRequesterAgent()


_neg_session_mod.NegotiationSession = MockNegotiationSession


# ---------------------------------------------------------------------------
# 主演示流程（与 run_demo.py 完全一致，仅 Agent 被 Mock 替换）
# ---------------------------------------------------------------------------

async def main() -> None:
    os.makedirs("data/keys", exist_ok=True)
    os.makedirs("data/assets", exist_ok=True)

    console.print(Rule("[bold blue]DataSpace 可信可控可管数据交换平台 — Mock 演示[/bold blue]"))
    console.print(
        Panel(
            "[yellow]Mock 模式[/yellow]：Agent 协商使用脚本化预设对话，不调用真实 Anthropic API。\n"
            "其余模块（RSA签名、策略引擎、数据传输、审计链）均为真实代码。",
            border_style="yellow",
        )
    )

    # 0. Setup
    console.print("\n[dim]生成示例数据...[/dim]")
    sys.path.insert(0, str(Path(__file__).parent))
    from seed_data import generate_user_behavior_csv
    generate_user_behavior_csv()

    # 清除旧数据库，避免 UNIQUE 冲突
    db_path = Path("data/dataspace.db")
    if db_path.exists():
        db_path.unlink()
        console.print("[dim]已清除旧数据库[/dim]")

    from dataspace.db.database import init_db
    await init_db()
    console.print("[green]✅ 数据库初始化完成[/green]")

    # 1. Generate key pairs
    console.print(Rule("Step 1: 生成 RSA 密钥对"))
    from dataspace.core.crypto import save_key_pair

    keys_dir = Path("data/keys")
    prov_priv, prov_pub = save_key_pair("provider_corp", keys_dir)
    req_priv, req_pub = save_key_pair("requester_inc", keys_dir)
    console.print("[green]✅ 双方 RSA-2048 密钥对已生成[/green]")

    # 2. Register parties
    console.print(Rule("Step 2: 注册双方身份"))
    from dataspace.core.enums import PartyRole
    from dataspace.core.models import Party
    from dataspace.db.database import get_session
    from dataspace.db.repositories import party_repo

    provider = Party(
        party_id="provider_corp",
        name="数据科技有限公司 (Provider Corp)",
        description="提供用户行为数据的数据供应商",
        role=PartyRole.PROVIDER,
        public_key_pem=prov_pub,
        endpoint="http://provider.example.com",
    )
    consumer = Party(
        party_id="requester_inc",
        name="智析分析科技 (Requester Inc)",
        description="用于用户画像分析的数据消费方",
        role=PartyRole.REQUESTER,
        public_key_pem=req_pub,
        endpoint="http://requester.example.com",
    )

    async with get_session() as session:
        await party_repo.create(session, provider)
        await party_repo.create(session, consumer)
    console.print(f"[green]✅ 注册提供方: {provider.name}[/green]")
    console.print(f"[green]✅ 注册请求方: {consumer.name}[/green]")

    # 3. Register data asset
    console.print(Rule("Step 3: 注册数据资产"))
    from dataspace.core.enums import AssetType
    from dataspace.core.models import DataAsset, UsagePolicy
    from dataspace.db.repositories import asset_repo

    csv_path = str(Path("data/assets/user_behavior.csv").resolve())
    provider_policy = UsagePolicy(
        max_requests_per_day=5000,
        max_records_per_request=500,
        allowed_operations=["read"],
        masked_columns=["email", "phone"],
        duration_days=60,
        purpose="analytics",
        no_third_party_transfer=True,
    )
    asset = DataAsset(
        asset_id="user_behavior_v1",
        provider_id="provider_corp",
        name="用户行为数据集 v1",
        description="包含用户页面访问、点击、购买等行为事件数据，已脱敏处理",
        asset_type=AssetType.CSV_FILE,
        endpoint=csv_path,
        schema_info={
            "columns": ["user_id", "email", "phone", "page", "duration_sec", "event", "timestamp"],
            "row_count": 5000,
        },
        sample_size=5000,
        tags=["用户行为", "电商", "分析"],
        default_policy=provider_policy,
    )

    async with get_session() as session:
        await asset_repo.create(session, asset)
    console.print(f"[green]✅ 注册数据资产: {asset.name}[/green]")
    console.print(f"   默认策略: {json.dumps(provider_policy.model_dump(), ensure_ascii=False)}")

    # 4. Mock Agent Negotiation
    console.print(Rule("Step 4: Agent 合约协商（Mock 模式）"))
    console.print(
        Panel(
            "使用预设脚本模拟 3 轮协商：\n"
            "  请求方发起 → 提供方反提案 → 请求方接受",
            title="Mock 协商",
            border_style="yellow",
        )
    )

    from dataspace.negotiation.session import NegotiationSession

    consumer_acceptable = UsagePolicy(
        max_requests_per_day=10000,
        max_records_per_request=1000,
        allowed_operations=["read"],
        masked_columns=[],
        duration_days=90,
        purpose="analytics",
        no_third_party_transfer=True,
    )

    neg_session = NegotiationSession(
        provider=provider,
        consumer=consumer,
        asset=asset,
        provider_policy=provider_policy,
        consumer_need="我方需要访问用户行为数据用于构建用户画像分析模型。",
        consumer_acceptable_policy=consumer_acceptable,
        max_turns=15,
    )

    neg_model = neg_session.negotiate()

    if neg_model.status.value != "agreed":
        console.print(f"[red]❌ 协商失败，状态: {neg_model.status.value}[/red]")
        return

    console.print(f"\n[green]✅ 协商成功！共进行 {neg_model.turns} 轮对话[/green]")
    console.print(f"   最终条款: {json.dumps(neg_model.agreed_policy.model_dump(), ensure_ascii=False, indent=4)}")

    # 5. Sign & Activate Contract
    console.print(Rule("Step 5: 合约签名与激活"))
    from dataspace.contract.registry import ContractRegistry
    from dataspace.contract.signer import sign_contract, verify_all_signatures

    contract = neg_session.build_contract()
    console.print(f"[blue]📝 合约已生成: {contract.contract_id}[/blue]")

    contract = sign_contract(contract, "provider_corp", prov_priv)
    console.print("[green]✅ 提供方 RSA 签名完成[/green]")
    contract = sign_contract(contract, "requester_inc", req_priv)
    console.print("[green]✅ 请求方 RSA 签名完成[/green]")

    verify_all_signatures(contract)
    console.print("[green]✅ 双方签名验证通过[/green]")

    registry = ContractRegistry()
    contract = await registry.save(contract)
    contract = await registry.activate(contract.contract_id)
    console.print(f"[green]✅ 合约已激活，状态: {contract.status.value}[/green]")

    from dataspace.db.repositories import negotiation_repo
    neg_model.contract_id = contract.contract_id
    async with get_session() as session:
        await negotiation_repo.create(session, neg_model)

    # 6. Data Transfer
    console.print(Rule("Step 6: 数据传输（策略执行验证）"))
    from dataspace.core.models import TransferRequest
    from dataspace.data.transfer_service import TransferService

    svc = TransferService(registry)

    console.print("\n[cyan]测试 1: 合规请求（50条记录）[/cyan]")
    result1 = await svc.transfer(TransferRequest(
        contract_id=contract.contract_id,
        requester_id="requester_inc",
        operation="read",
        requested_records=50,
        purpose="analytics",
    ))
    _print_transfer_result(result1, "合规请求")

    console.print("\n[cyan]测试 2: 超出单次限制（请求1000条，限额500）[/cyan]")
    result2 = await svc.transfer(TransferRequest(
        contract_id=contract.contract_id,
        requester_id="requester_inc",
        operation="read",
        requested_records=1000,
        purpose="analytics",
    ))
    _print_transfer_result(result2, "超限请求")

    console.print("\n[cyan]测试 3: 错误的请求方身份[/cyan]")
    result3 = await svc.transfer(TransferRequest(
        contract_id=contract.contract_id,
        requester_id="malicious_party",
        operation="read",
        requested_records=10,
        purpose="analytics",
    ))
    _print_transfer_result(result3, "身份错误请求")

    if result1.data:
        console.print("\n[cyan]数据脱敏验证：[/cyan]")
        for row in result1.data[:3]:
            console.print(f"  {json.dumps(row, ensure_ascii=False)}")
        if any(r.get("email") == "***MASKED***" for r in result1.data):
            console.print("[green]✅ email 字段已脱敏[/green]")
        if any(r.get("phone") == "***MASKED***" for r in result1.data):
            console.print("[green]✅ phone 字段已脱敏[/green]")

    # 7. Audit chain verification
    console.print(Rule("Step 7: 审计日志与链完整性验证"))
    from dataspace.audit.verifier import verify_chain
    from dataspace.db.repositories import audit_repo

    async with get_session() as session:
        entries = await audit_repo.list_entries(session, limit=20)

    table = Table(title="审计日志（最近20条）", show_lines=True)
    table.add_column("序号", style="dim", width=5)
    table.add_column("事件类型", style="cyan")
    table.add_column("操作方", style="green")
    table.add_column("对象", style="yellow")
    table.add_column("时间", style="dim")
    table.add_column("哈希前缀", style="dim")

    for e in entries:
        table.add_row(
            str(e["sequence"]),
            e["event_type"],
            (e["actor_id"] or "-")[:20],
            (e["subject_id"] or "-")[:20],
            e["timestamp"][:19],
            e["entry_hash"][:12] + "...",
        )
    console.print(table)

    verification = await verify_chain()
    if verification.valid:
        console.print(
            Panel(
                f"[bold green]✅ 审计链完整性验证通过[/bold green]\n"
                f"共 {verification.total_entries} 条审计记录，哈希链完整，未发现篡改。",
                title="审计验证结果",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                f"[bold red]❌ 审计链已被篡改！[/bold red]\n{verification.error}",
                title="审计验证结果",
                border_style="red",
            )
        )

    console.print(Rule("[bold green]Mock 演示完成！[/bold green]"))
    console.print(
        "\n[dim]真实 Agent 模式（需要 ANTHROPIC_API_KEY）：[/dim]\n"
        "  [bold]python demo/run_demo.py[/bold]\n\n"
        "启动 API 服务：\n"
        "  [bold]uvicorn dataspace.api.app:app --reload --port 8026[/bold]"
    )


def _print_transfer_result(result, label: str) -> None:
    from dataspace.core.enums import TransferStatus
    if result.status == TransferStatus.COMPLETED:
        console.print(f"  [green]✅ {label}: 成功传输 {result.records_returned} 条记录[/green]")
    elif result.status == TransferStatus.BLOCKED:
        console.print(f"  [yellow]🚫 {label}: 策略阻止 — {result.blocked_reason}[/yellow]")
    else:
        console.print(f"  [red]❌ {label}: 失败 — {result.blocked_reason}[/red]")


if __name__ == "__main__":
    asyncio.run(main())
