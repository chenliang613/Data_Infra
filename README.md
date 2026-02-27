# DataSpace P2P — 点对点文件共享演示

在同一台机器上运行两个独立的 Agent 节点，每个节点提供 Web 管理界面，支持文件共享、互信握手与文件获取。

---

## 快速启动

```bash
# 安装依赖
pip install -e ".[dev]"

# 一键启动（自动打开两个浏览器标签）
python demo/start_p2p.py
```

| 节点 | 地址 |
|------|------|
| Agent-1 | http://localhost:8026 |
| Agent-2 | http://localhost:8025 |

> 启动前会自动 kill 占用 8025 / 8026 端口的进程。

也可分窗口手动启动：

```bash
python demo/p2p_agent.py --port 8026 --name "Agent-1"
python demo/p2p_agent.py --port 8025 --name "Agent-2"
```

---

## 功能

### 共享文件
- 点击或拖拽上传文件（支持任意类型、多选）
- 对已共享文件执行预览、下载、删除

### 已接收文件
- 查看从其他节点获取的所有文件
- 对已接收文件执行预览、下载、删除

### 互信管理
- 输入对方节点地址，发起互信请求
- 接受或拒绝传入的互信请求
- 对已互信节点浏览其共享文件并一键获取

---

## 演示流程

```
1. 在 Agent-1「共享文件」上传一个文件
2. 在 Agent-1「互信管理」输入 http://localhost:8025 → 发起互信
3. 切换到 Agent-2，「互信管理」Tab 出现角标 → 接受
4. 双方状态变为绿色「已互信」
5. 在 Agent-2 点击「浏览文件」→ 选中文件 → 获取
6. Agent-2「已接收文件」出现该文件，可预览 / 下载
```

---

## 文件预览支持

| 类型 | 扩展名 |
|------|--------|
| 图片 | jpg · png · gif · svg · webp · bmp |
| PDF | pdf |
| 视频 | mp4 · webm · mov |
| 音频 | mp3 · wav · ogg · flac · aac |
| 文本 / 代码 | txt · md · json · csv · py · js · ts · html · css · yaml · … |
| 其他 | 显示下载按钮 |

---

## 架构

```
Agent-1 (:8026)                    Agent-2 (:8025)
┌──────────────────┐               ┌──────────────────┐
│  共享文件         │               │  共享文件         │
│  已接收文件       │◄─── P2P ─────►│  已接收文件       │
│  互信管理         │               │  互信管理         │
└──────────────────┘               └──────────────────┘
data/p2p/agent-8026/               data/p2p/agent-8025/
├── shared/                        ├── shared/
└── received/                      └── received/
```

---

## 项目结构

```
demo/
├── p2p_agent.py    # Agent 节点服务（FastAPI + 内嵌 Web UI）
└── start_p2p.py    # 一键启动脚本
```
