# DataSpace — 可信可控可管数据交换平台

本项目包含两个独立演示：

- **P2P 可视化演示**（推荐）— 两个 Agent 节点各自拥有 Web 管理界面，可互信握手、共享与获取文件
- **合约协商演示** — 通过 Claude LLM Agent 多轮对话协商数据交换合约，全程哈希链审计

---

## 一、P2P 可视化演示

### 概览

在同一台机器上运行两个独立的 Agent 节点，每个节点提供一个 Web 管理页面，支持：

| 功能模块 | 说明 |
|----------|------|
| **共享文件** | 上传文件对外共享，支持预览、下载、删除 |
| **已接收文件** | 查看从其他节点获取的文件，支持预览、下载、删除 |
| **互信管理** | 向其他节点发起互信请求，接受 / 拒绝传入请求，已互信节点可浏览并获取对方共享文件 |

### 快速启动

```bash
# 安装依赖
pip install -e ".[dev]"

# 一键启动（自动打开两个浏览器标签）
python demo/start_p2p.py
```

启动后自动打开：
- **Agent-1** → http://localhost:8026
- **Agent-2** → http://localhost:8025

> 脚本会在启动前自动清理占用这两个端口的进程。

也可分窗口手动启动：

```bash
python demo/p2p_agent.py --port 8026 --name "Agent-1"
python demo/p2p_agent.py --port 8025 --name "Agent-2"
```

### 演示流程

```
1. 在 Agent-1「共享文件」Tab 上传任意文件
2. 在 Agent-1「互信管理」Tab 输入 http://localhost:8025 → 点「发起互信」
3. 切换到 Agent-2，「互信管理」Tab 出现角标 → 点「接受」
4. 双方状态变为绿色「已互信」
5. 在 Agent-2 点击「浏览文件」→ 看到 Agent-1 共享的文件 → 点「获取」
6. Agent-2「已接收文件」Tab 出现角标，文件可预览 / 下载
```

### 系统架构

```
Agent-1 (:8026)                     Agent-2 (:8025)
┌─────────────────────┐             ┌─────────────────────┐
│  Web UI (浏览器)     │             │  Web UI (浏览器)     │
│  ┌───────────────┐  │             │  ┌───────────────┐  │
│  │ 共享文件       │  │             │  │ 共享文件       │  │
│  │ 已接收文件     │  │             │  │ 已接收文件     │  │
│  │ 互信管理       │  │             │  │ 互信管理       │  │
│  └───────────────┘  │             │  └───────────────┘  │
│                     │             │                     │
│  FastAPI Server     │◄────────────►  FastAPI Server     │
│  /api/*  (用户侧)   │  互信握手    │  /api/*  (用户侧)   │
│  /internal/* (P2P)  │  文件传输    │  /internal/* (P2P)  │
└─────────────────────┘             └─────────────────────┘
        │                                     │
   data/p2p/agent-8026/               data/p2p/agent-8025/
   ├── shared/                        ├── shared/
   └── received/                      └── received/
```

### 互信状态机

```
未连接  ──发起互信──►  pending_out  (等待对方确认)
                            │
未连接  ◄──收到请求──  pending_in   (待本方接受)
                            │ 接受
                            ▼
                         trusted  ✓
```

### API 端点（每个节点）

**用户侧：**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/info` | 节点信息 |
| GET | `/api/shared` | 列出共享文件 |
| POST | `/api/shared/upload` | 上传文件到共享目录 |
| GET | `/api/shared/{id}/raw` | 内联预览文件 |
| GET | `/api/shared/{id}/download` | 下载文件 |
| DELETE | `/api/shared/{id}` | 删除共享文件 |
| GET | `/api/received` | 列出已接收文件 |
| GET | `/api/received/{id}/raw` | 内联预览已接收文件 |
| GET | `/api/received/{id}/download` | 下载已接收文件 |
| DELETE | `/api/received/{id}` | 删除已接收文件 |
| GET | `/api/peers` | 列出所有对等节点 |
| POST | `/api/peers/connect` | 向另一节点发起互信 |
| POST | `/api/peers/{id}/accept` | 接受互信请求 |
| POST | `/api/peers/{id}/reject` | 拒绝互信请求 |
| GET | `/api/peers/{id}/files` | 浏览已互信节点的共享文件 |
| POST | `/api/peers/{id}/fetch/{file_id}` | 从已互信节点获取文件 |

**节点间内部（P2P）：**

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/internal/trust-request` | 接收互信请求 |
| POST | `/internal/trust-accepted` | 接收互信确认 |
| GET | `/internal/shared-files` | 向已互信节点暴露文件列表 |
| GET | `/internal/files/{id}` | 向已互信节点提供文件下载 |

### 文件预览支持

| 类型 | 扩展名示例 | 预览方式 |
|------|-----------|---------|
| 图片 | jpg / png / gif / svg / webp | `<img>` 内联渲染 |
| PDF | pdf | `<iframe>` 嵌入 |
| 视频 | mp4 / webm / mov | `<video>` 播放器 |
| 音频 | mp3 / wav / ogg / flac | `<audio>` 播放器 |
| 文本 / 代码 | txt / md / json / csv / py / js / … | `<pre>` 文本显示 |
| 其他 | 任意 | 提示不支持 + 下载按钮 |

---

## 二、合约协商演示

两个数据交换方通过 **Claude LLM Agent** 进行多轮对话协商数据交换合约，合约签署后按约定条款安全交换数据，全程哈希链审计。

### 核心特性

| 特性 | 实现方式 |
|------|----------|
| **可信** | RSA-2048 数字签名，双方签名验证合约真实性 |
| **可控** | 策略引擎 8 阶段检查，逐笔数据传输前强制执行合约条款 |
| **可管** | SHA-256 哈希链审计日志，防篡改，可追溯全部操作 |

### 快速启动

```bash
# 配置 API Key
cp .env.example .env
# 编辑 .env，填入 ANTHROPIC_API_KEY=sk-ant-...

# 运行端到端演示
python demo/run_demo.py
```

演示步骤：

1. 生成 RSA 密钥对
2. 注册双方身份
3. 注册数据资产（用户行为 CSV）
4. **Claude Agent 多轮协商**（实时显示对话）
5. 双方签名，合约激活
6. 数据传输（含 3 种策略执行场景验证）
7. 哈希链审计完整性验证

### 启动 API 服务

```bash
uvicorn dataspace.api.app:app --reload
# 访问 http://localhost:8000/docs
```

### API 端点

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

### Agent 协商示例

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

---

## 项目结构

```
demo/
├── p2p_agent.py       # P2P 节点服务（FastAPI + 内嵌 Web UI）
├── start_p2p.py       # 一键启动两个 P2P 节点
├── run_demo.py        # 合约协商端到端演示
├── run_demo_mock.py   # Mock 模式演示（无需 API Key）
└── seed_data.py       # 生成示例数据

src/dataspace/
├── core/              # 核心模型、RSA 加密、枚举、异常
├── agent/             # Claude Connector Agent（工具 + 提示词）
├── negotiation/       # 协商引擎（状态机 + Session + 合约构建）
├── contract/          # 合约签名、注册表、策略执行器
├── data/              # 数据适配器（CSV/JSON/DB/Stream）+ 传输服务
├── audit/             # 哈希链审计日志 + 完整性验证
├── db/                # SQLAlchemy ORM + 仓储层
└── api/               # FastAPI 路由 + 应用工厂

data/
├── p2p/               # P2P 演示数据（各节点独立目录）
│   ├── agent-8026/shared/
│   ├── agent-8026/received/
│   ├── agent-8025/shared/
│   └── agent-8025/received/
└── assets/            # 合约演示用数据资产

scripts/               # 密钥生成工具
```
