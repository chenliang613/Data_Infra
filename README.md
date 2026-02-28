# DataSpace P2P — 点对点文件共享演示

本地同时运行 4 个 Agent 节点，每个节点提供 Web 管理界面，支持文件共享、互信握手与文件获取。

---

## 快速启动

### 1. 安装依赖

```bash
pip install -e .
```

### 2. 启动所有节点

```bash
python demo/start_p2p.py
```

启动后自动打开 5 个浏览器标签：

| 节点 | 地址 | 角色 |
|------|------|------|
| Agent-ALL（全局监控） | http://localhost:8020 | 监控方 |
| 数据共享方 Agent-A | http://localhost:8021 | 共享方 |
| 数据共享方 Agent-B | http://localhost:8023 | 共享方 |
| 数据接收方 Agent-C | http://localhost:8025 | 接收方 |
| 数据接收方 Agent-D | http://localhost:8027 | 接收方 |

> 启动时会自动终止占用以上端口的进程。

### 3. 单独启动某个节点（可选）

```bash
# 单个 P2P 节点
python demo/p2p_agent.py --port 8021 --name "我的节点"

# 全局监控节点
python demo/global_agent.py --port 8020
```

---

## 功能

### 共享文件
- 点击或拖拽上传文件（支持任意类型、可多选）
- 对已共享文件执行预览、下载、移除共享（不删除本地文件）

### 已接收文件
- 查看从其他节点获取的所有文件
- 对已接收文件执行预览、下载、删除

### 互信管理
- 输入对方节点地址，选择互信等级后发起请求
- 接受或拒绝传入的互信请求
- 对已互信节点浏览其共享文件并一键获取

#### 互信等级

| 等级 | 说明 |
|------|------|
| 🔐 高互信 | 可浏览文件列表 + 下载文件 |
| 👁 一般互信 | 仅可浏览文件列表，不能下载 |

---

## 演示流程

```
1. 在共享方 Agent-A「共享文件」Tab 上传文件
2. 在「互信管理」Tab 输入接收方地址，选择互信等级，点击「发起互信」
   例：http://localhost:8025
3. 切换到接收方 Agent-C，「互信管理」Tab 出现角标 → 点击「接受」
4. 双方状态变为绿色「已互信」
5. 在接收方「互信管理」点击对方的「浏览文件」→ 选中文件 → 点击「获取」
6. 「已接收文件」Tab 出现该文件，可预览 / 下载
```

---

## 文件预览支持

| 类型 | 扩展名 |
|------|--------|
| 图片 | jpg · jpeg · png · gif · webp · svg · bmp · ico · avif |
| PDF | pdf |
| 视频 | mp4 · webm · mov · avi · mkv · m4v |
| 音频 | mp3 · wav · ogg · aac · flac · m4a · opus |
| 文本 / 代码 | txt · md · json · csv · xml · yaml · log · py · js · ts · html · css · sh · go · java · sql · … |
| 其他 | 显示下载按钮，不支持在线预览 |

---

## 架构

```
Agent-A (:8021)        Agent-B (:8023)
┌─────────────┐        ┌─────────────┐
│  共享文件    │        │  共享文件    │
│  已接收文件  │        │  已接收文件  │
│  互信管理    │        │  互信管理    │
└──────┬──────┘        └──────┬──────┘
       │         P2P          │
       └──────────┬───────────┘
                  │
       ┌──────────┴───────────┐
┌──────┴──────┐        ┌──────┴──────┐
│  共享文件    │        │  共享文件    │
│  已接收文件  │        │  已接收文件  │
│  互信管理    │        │  互信管理    │
└─────────────┘        └─────────────┘
Agent-C (:8025)        Agent-D (:8027)
```

每个节点数据独立存储：

```
data/p2p/
├── agent-8021/
│   ├── shared/      # 该节点正在共享的文件
│   └── received/    # 该节点已接收的文件
├── agent-8023/
├── agent-8025/
└── agent-8027/
```

---

## 项目结构

```
demo/
├── p2p_agent.py    # Agent 节点服务（FastAPI + 内嵌 Web UI）
└── start_p2p.py    # 一键启动 4 个节点
```

---

## 依赖

- [FastAPI](https://fastapi.tiangolo.com/) — Web 框架
- [Uvicorn](https://www.uvicorn.org/) — ASGI 服务器
- [httpx](https://www.python-httpx.org/) — 节点间异步通信
- [python-multipart](https://github.com/Kludex/python-multipart) — 文件上传支持
