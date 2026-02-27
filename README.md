# DataSpace — 可信可控可管数据交换平台

两个数据交换方通过 **Claude LLM Agent（数据连接器）** 进行多轮对话协商数据交换合约，合约签署后按约定条款安全交换数据，全程哈希链审计。

## 核心特性

| 特性 | 实现方式 |
|------|----------|
| **可信** | RSA-2048 数字签名，双方签名验证合约真实性 |
| **可控** | 策略引擎 8 阶段检查，逐笔数据传输前强制执行合约条款 |
| **可管** | SHA-256 哈希链审计日志，防篡改，可追溯全部操作 |

## 系统架构

```
Party A (数据提供方)                    Party B (数据请求方)
       │                                        │
[Provider Agent]  ←─── 多轮协商对话 ───→  [Requester Agent]
  (Claude LLM)                               (Claude LLM)
       │                                        │
       └──────────── 合约协商结果 ──────────────┘
                            │
                    [Contract Builder]
                    生成标准合约 JSON
                            │
              ┌─────────────┴──────────────┐
              │        双方 RSA 签名         │
              │       合约激活 (ACTIVE)      │
              └─────────────┬──────────────┘
                            │
              ┌─────────────┴──────────────┐
              │       Policy Enforcer       │  ← 每次传输前 8 阶段检查
              │  1. 合约 ACTIVE 状态         │
              │  2. 双方签名验证             │
              │  3. 有效期检查              │
              │  4. 允许操作类型            │
              │  5. 每日请求次数限制         │
              │  6. 单次记录数限制          │
              │  7. 请求方身份验证          │
              │  8. 数据用途合规性          │
              └─────────────┬──────────────┘
                            │
              ┌─────────────┴──────────────┐
              │       Data Adapters         │
              │  CSV / JSON / DB / Stream   │
              │    + 字段脱敏过滤           │
              └─────────────┬──────────────┘
                            │
              ┌─────────────┴──────────────┐
              │     Audit Logger (哈希链)   │
              │  每条记录包含上一条哈希值    │
              │  防篡改，可验证完整性        │
              └────────────────────────────┘
```

## 快速开始

### 1. 安装依赖

```bash
pip install -e ".[dev]"
```

### 2. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env，填入 ANTHROPIC_API_KEY=sk-ant-...
```

### 3. 运行端到端演示

```bash
python demo/run_demo.py
```

演示将展示：
1. 生成 RSA 密钥对
2. 注册双方身份
3. 注册数据资产（用户行为 CSV）
4. **Claude Agent 多轮协商**（实时显示对话）
5. 双方签名，合约激活
6. 数据传输（含 3 种策略执行场景验证）
7. 哈希链审计完整性验证

### 4. 启动 API 服务

```bash
uvicorn dataspace.api.app:app --reload
# 访问 http://localhost:8000/docs
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/parties` | 注册数据交换方 |
| POST | `/assets` | 注册数据资产 |
| POST | `/negotiations` | 发起合约协商（自动运行 Agent 对话） |
| GET  | `/negotiations/{id}` | 查询协商状态及消息历史 |
| GET  | `/contracts` | 查看活跃合约列表 |
| POST | `/contracts/{id}/revoke` | 撤销合约 |
| POST | `/transfer` | 请求数据传输 |
| GET  | `/audit` | 查看审计日志 |
| POST | `/audit/verify` | 验证审计链完整性 |

## Agent 协商示例对话

```
[请求方 Agent]: 我方需要访问用户行为数据集，用于用户画像分析。
               请求每日最多 10000 次，有效期 90 天。

[提供方 Agent]: 已查看数据目录。根据本方安全策略：
               最高可授权 5000次/天，有效期不超过 60 天，
               且 email/phone 字段必须脱敏。

[请求方 Agent]: 接受每日 5000 次限制，有效期能否考虑 75 天？

[提供方 Agent]: 有效期上限 60 天，这是不可变条款。
               是否接受：5000次/天，60天，脱敏email/phone？

[请求方 Agent]: ✅ 接受全部条款。[调用 accept_contract 工具]

→ 系统自动生成合约，双方 RSA 签名，合约激活。
```

## 项目结构

```
src/dataspace/
├── core/          # 核心模型、RSA 加密、枚举、异常
├── agent/         # Claude Connector Agent（工具 + 提示词 + 基础循环）
├── negotiation/   # 协商引擎（状态机 + Session + 合约构建）
├── contract/      # 合约签名、注册表、策略执行器
├── data/          # 数据适配器（CSV/JSON/DB/Stream）+ 传输服务
├── audit/         # 哈希链审计日志 + 完整性验证
├── db/            # SQLAlchemy ORM + 仓储层
└── api/           # FastAPI 路由 + 应用工厂
demo/              # 端到端演示脚本
scripts/           # 密钥生成工具
```
