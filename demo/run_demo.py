#!/usr/bin/env python3
"""
DataSpace 端到端演示
===================
演示完整流程：
1. 初始化数据库 + 示例数据
2. 注册双方 (Party A 提供方 / Party B 请求方)
3. 注册数据资产
4. 通过 Claude Agent 协商数据交换合约
5. 双方 RSA 签名，合约激活
6. 按合约条款传输数据（含策略执行验证）
7. 验证审计链完整性
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


async def main() -> None:
    os.makedirs("data/keys", exist_ok=True)
    os.makedirs("data/assets", exist_ok=True)

    # ---------------------------------------------------------------
    # 0. Setup
    # ---------------------------------------------------------------
    console.print(Rule("[bold blue]DataSpace 可信可控可管数据交换平台 — 演示[/bold blue]"))

    # Generate sample data
    console.print("\n[dim]生成示例数据...[/dim]")
    sys.path.insert(0, str(Path(__file__).parent))
    from seed_data import generate_user_behavior_csv
    generate_user_behavior_csv()

    # Init DB
    from dataspace.db.database import init_db
    await init_db()
    console.print("[green]✅ 数据库初始化完成[/green]")

    # ---------------------------------------------------------------
    # 1. Generate key pairs
    # ---------------------------------------------------------------
    console.print(Rule("Step 1: 生成 RSA 密钥对"))
    from dataspace.core.crypto import save_key_pair, load_key_pair

    keys_dir = Path("data/keys")
    prov_priv, prov_pub = save_key_pair("provider_corp", keys_dir)
    req_priv, req_pub = save_key_pair("requester_inc", keys_dir)
    console.print("[green]✅ 双方 RSA-2048 密钥对已生成[/green]")

    # ---------------------------------------------------------------
    # 2. Register parties
    # ---------------------------------------------------------------
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

    # ---------------------------------------------------------------
    # 3. Register data asset
    # ---------------------------------------------------------------
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
    console.print(f"   类型: {asset.asset_type.value}")
    console.print(f"   端点: {csv_path}")
    console.print(f"   默认策略: {json.dumps(provider_policy.model_dump(), ensure_ascii=False)}")

    # ---------------------------------------------------------------
    # 4. Agent Negotiation
    # ---------------------------------------------------------------
    console.print(Rule("Step 4: Claude Agent 合约协商"))
    console.print(
        Panel(
            "[yellow]提供方 Agent[/yellow] 和 [cyan]请求方 Agent[/cyan] 将通过多轮对话协商数据访问合约。\n"
            "请稍候，协商过程将实时显示...",
            title="协商开始",
        )
    )

    from dataspace.negotiation.session import NegotiationSession

    consumer_acceptable = UsagePolicy(
        max_requests_per_day=10000,   # Consumer wants more, will negotiate
        max_records_per_request=1000,
        allowed_operations=["read"],
        masked_columns=[],            # Consumer prefers no masking (will be overridden)
        duration_days=90,             # Wants 90 days
        purpose="analytics",
        no_third_party_transfer=True,
    )

    consumer_need = (
        "我方需要访问用户行为数据用于构建用户画像分析模型。"
        "希望每日可查询 10000 次，每次最多 1000 条记录，有效期 90 天。"
        "数据格式为 CSV，用途为内部数据分析，不对外转让。"
    )

    neg_session = NegotiationSession(
        provider=provider,
        consumer=consumer,
        asset=asset,
        provider_policy=provider_policy,
        consumer_need=consumer_need,
        consumer_acceptable_policy=consumer_acceptable,
        max_turns=15,
    )

    neg_model = neg_session.negotiate()

    if neg_model.status.value != "agreed":
        console.print(f"[red]❌ 协商失败，状态: {neg_model.status.value}[/red]")
        return

    console.print(f"\n[green]✅ 协商成功！共进行 {neg_model.turns} 轮对话[/green]")
    console.print(f"   最终条款: {json.dumps(neg_model.agreed_policy.model_dump(), ensure_ascii=False, indent=4)}")

    # ---------------------------------------------------------------
    # 5. Sign & Activate Contract
    # ---------------------------------------------------------------
    console.print(Rule("Step 5: 合约签名与激活"))
    from dataspace.contract.registry import ContractRegistry
    from dataspace.contract.signer import sign_contract, verify_all_signatures

    contract = neg_session.build_contract()
    console.print(f"[blue]📝 合约已生成: {contract.contract_id}[/blue]")
    console.print(f"   有效期至: {contract.valid_until.strftime('%Y-%m-%d') if contract.valid_until else 'N/A'}")

    # Sign by both parties
    contract = sign_contract(contract, "provider_corp", prov_priv)
    console.print("[green]✅ 提供方 RSA 签名完成[/green]")
    contract = sign_contract(contract, "requester_inc", req_priv)
    console.print("[green]✅ 请求方 RSA 签名完成[/green]")

    # Verify signatures
    verify_all_signatures(contract)
    console.print("[green]✅ 双方签名验证通过[/green]")

    # Save & activate
    registry = ContractRegistry()
    contract = await registry.save(contract)
    contract = await registry.activate(contract.contract_id)
    console.print(f"[green]✅ 合约已激活，状态: {contract.status.value}[/green]")

    # Save negotiation contract_id
    from dataspace.db.repositories import negotiation_repo
    neg_model.contract_id = contract.contract_id
    async with get_session() as session:
        await negotiation_repo.create(session, neg_model)

    # ---------------------------------------------------------------
    # 6. Data Transfer (with policy enforcement)
    # ---------------------------------------------------------------
    console.print(Rule("Step 6: 数据传输（策略执行验证）"))
    from dataspace.core.models import TransferRequest
    from dataspace.data.transfer_service import TransferService

    svc = TransferService(registry)

    # 6a. Legal transfer
    console.print("\n[cyan]测试 1: 合规数据请求（50条记录）[/cyan]")
    req1 = TransferRequest(
        contract_id=contract.contract_id,
        requester_id="requester_inc",
        operation="read",
        requested_records=50,
        purpose="analytics",
    )
    result1 = await svc.transfer(req1)
    _print_transfer_result(result1, "合规请求")

    # 6b. Exceeds per-request limit
    console.print("\n[cyan]测试 2: 超出单次记录限制（请求 1000 条，限额 500）[/cyan]")
    req2 = TransferRequest(
        contract_id=contract.contract_id,
        requester_id="requester_inc",
        operation="read",
        requested_records=1000,
        purpose="analytics",
    )
    result2 = await svc.transfer(req2)
    _print_transfer_result(result2, "超限请求")

    # 6c. Wrong requester
    console.print("\n[cyan]测试 3: 错误的请求方身份[/cyan]")
    req3 = TransferRequest(
        contract_id=contract.contract_id,
        requester_id="malicious_party",
        operation="read",
        requested_records=10,
        purpose="analytics",
    )
    result3 = await svc.transfer(req3)
    _print_transfer_result(result3, "身份错误请求")

    # 6d. Check masking in result
    if result1.data:
        console.print("\n[cyan]数据脱敏验证：[/cyan]")
        sample = result1.data[:3]
        for row in sample:
            console.print(f"  {json.dumps(row, ensure_ascii=False)}")
        email_values = set(r.get("email") for r in result1.data)
        if "***MASKED***" in email_values:
            console.print("[green]✅ email 字段已脱敏[/green]")
        phone_values = set(r.get("phone") for r in result1.data)
        if "***MASKED***" in phone_values:
            console.print("[green]✅ phone 字段已脱敏[/green]")

    # ---------------------------------------------------------------
    # 7. Audit log & chain verification
    # ---------------------------------------------------------------
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
            e["actor_id"][:20] if e["actor_id"] else "-",
            e["subject_id"][:20] if e["subject_id"] else "-",
            e["timestamp"][:19],
            e["entry_hash"][:12] + "...",
        )
    console.print(table)

    # Verify chain
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

    console.print(Rule("[bold green]演示完成！[/bold green]"))
    console.print(
        "\n启动 API 服务:\n"
        "  [bold]uvicorn dataspace.api.app:app --reload[/bold]\n\n"
        "查看 API 文档:\n"
        "  [bold]http://localhost:8000/docs[/bold]"
    )


def _print_transfer_result(result, label: str) -> None:
    from dataspace.core.enums import TransferStatus
    if result.status == TransferStatus.COMPLETED:
        console.print(
            f"  [green]✅ {label}: 成功传输 {result.records_returned} 条记录[/green]"
        )
    elif result.status == TransferStatus.BLOCKED:
        console.print(
            f"  [yellow]🚫 {label}: 策略阻止 — {result.blocked_reason}[/yellow]"
        )
    else:
        console.print(
            f"  [red]❌ {label}: 失败 — {result.blocked_reason}[/red]"
        )


if __name__ == "__main__":
    asyncio.run(main())
