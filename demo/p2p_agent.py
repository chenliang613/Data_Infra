#!/usr/bin/env python3
"""
P2P Agent Node — 点对点数据共享节点
=====================================
用法:
  python demo/p2p_agent.py --port 8026 --name "Agent-1"
  python demo/p2p_agent.py --port 8025 --name "Agent-2"
"""
from __future__ import annotations

import argparse
import mimetypes
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, unquote

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

# ── CLI 参数 ──────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="P2P Agent Node")
parser.add_argument("--port", type=int, default=8026)
parser.add_argument("--name", type=str, default=None)
args = parser.parse_args()

PORT: int = args.port
AGENT_NAME: str = args.name or f"Agent-{PORT}"
AGENT_ID: str = f"agent-{PORT}"
ENDPOINT: str = f"http://localhost:{PORT}"

DATA_DIR = Path(f"data/p2p/agent-{PORT}")
SHARED_DIR = DATA_DIR / "shared"
RECEIVED_DIR = DATA_DIR / "received"
SHARED_DIR.mkdir(parents=True, exist_ok=True)
RECEIVED_DIR.mkdir(parents=True, exist_ok=True)

# ── 内存状态 ──────────────────────────────────────────────────────────────────
shared_files: dict[str, dict] = {}
received_files: list[dict] = []
peers: dict[str, dict] = {}
access_log: list[dict] = []


def _log_access(event: str, file_name: str, file_id: str, actor: str) -> None:
    access_log.append({
        "time": datetime.now().isoformat(),
        "event": event,
        "file_name": file_name,
        "file_id": file_id,
        "actor": actor,
    })
    if len(access_log) > 500:
        del access_log[0]


app = FastAPI(title=AGENT_NAME)


# ── Pydantic 模型 ─────────────────────────────────────────────────────────────
class ConnectRequest(BaseModel):
    endpoint: str
    trust_level: str = "high"   # "high" | "normal"
    message: str = ""


class TrustPayload(BaseModel):
    agent_id: str
    name: str
    endpoint: str
    trust_level: str = "high"
    message: str = ""


# ── 用户侧 API ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(_build_html())


@app.get("/api/info")
async def get_info():
    return {"agent_id": AGENT_ID, "name": AGENT_NAME, "port": PORT, "endpoint": ENDPOINT}


# ── 共享文件 ──────────────────────────────────────────────────────────────────

@app.get("/api/shared")
async def list_shared():
    return list(shared_files.values())


@app.post("/api/shared/upload")
async def upload_shared(file: UploadFile = File(...)):
    file_id = uuid.uuid4().hex[:8]
    content = await file.read()
    dest = SHARED_DIR / file.filename
    dest.write_bytes(content)
    shared_files[file_id] = {
        "id": file_id,
        "name": file.filename,
        "size": len(content),
        "path": str(dest),
        "created_at": datetime.now().isoformat(),
    }
    return shared_files[file_id]


@app.get("/api/shared/{file_id}/raw")
async def raw_shared(file_id: str):
    """内联返回文件（用于预览）。"""
    if file_id not in shared_files:
        raise HTTPException(404, "文件不存在")
    info = shared_files[file_id]
    _log_access("local_preview", info["name"], file_id, "local")
    mime, _ = mimetypes.guess_type(info["name"])
    return FileResponse(info["path"], media_type=mime or "application/octet-stream")


@app.get("/api/shared/{file_id}/download")
async def download_shared(file_id: str):
    """以附件方式下载共享文件。"""
    if file_id not in shared_files:
        raise HTTPException(404, "文件不存在")
    info = shared_files[file_id]
    _log_access("local_download", info["name"], file_id, "local")
    return FileResponse(
        info["path"],
        filename=info["name"],
        media_type="application/octet-stream",
    )


@app.delete("/api/shared/{file_id}")
async def delete_shared(file_id: str):
    if file_id not in shared_files:
        raise HTTPException(404, "文件不存在")
    shared_files.pop(file_id)
    return {"ok": True}


# ── 已接收文件 ────────────────────────────────────────────────────────────────

@app.get("/api/received")
async def list_received():
    return received_files


@app.get("/api/received/{file_id}/raw")
async def raw_received(file_id: str):
    """内联返回已接收文件（用于预览）。"""
    entry = next((f for f in received_files if f["id"] == file_id), None)
    if not entry:
        raise HTTPException(404, "文件不存在")
    mime, _ = mimetypes.guess_type(entry["name"])
    return FileResponse(entry["path"], media_type=mime or "application/octet-stream")


@app.get("/api/received/{file_id}/download")
async def download_received(file_id: str):
    """以附件方式下载已接收文件。"""
    entry = next((f for f in received_files if f["id"] == file_id), None)
    if not entry:
        raise HTTPException(404, "文件不存在")
    return FileResponse(
        entry["path"],
        filename=entry["name"],
        media_type="application/octet-stream",
    )


@app.delete("/api/received/{file_id}")
async def delete_received(file_id: str):
    global received_files
    entry = next((f for f in received_files if f["id"] == file_id), None)
    if not entry:
        raise HTTPException(404, "文件不存在")
    Path(entry["path"]).unlink(missing_ok=True)
    received_files = [f for f in received_files if f["id"] != file_id]
    return {"ok": True}


# ── 互信管理 ──────────────────────────────────────────────────────────────────

@app.get("/api/peers")
async def list_peers():
    return list(peers.values())


@app.post("/api/peers/connect")
async def connect_to_peer(body: ConnectRequest):
    body.endpoint = body.endpoint.rstrip("/")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{body.endpoint}/internal/trust-request",
                json={"agent_id": AGENT_ID, "name": AGENT_NAME,
                      "endpoint": ENDPOINT, "trust_level": body.trust_level,
                      "message": body.message},
                timeout=5,
            )
            resp.raise_for_status()
            peer_info = resp.json()
        except Exception as e:
            raise HTTPException(400, f"连接失败: {e}")

    peer_id = peer_info["agent_id"]
    if peer_id in peers and peers[peer_id]["status"] == "trusted":
        raise HTTPException(400, "已经是互信节点")
    peers[peer_id] = {
        "id": peer_id,
        "name": peer_info["name"],
        "endpoint": body.endpoint,
        "status": "pending_out",
        "trust_level": body.trust_level,
    }
    return peers[peer_id]


@app.post("/api/peers/{peer_id}/accept")
async def accept_peer(peer_id: str):
    if peer_id not in peers or peers[peer_id]["status"] != "pending_in":
        raise HTTPException(400, "无此待处理请求")
    peer = peers[peer_id]
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"{peer['endpoint']}/internal/trust-accepted",
                json={"agent_id": AGENT_ID, "name": AGENT_NAME,
                      "endpoint": ENDPOINT, "trust_level": peer.get("trust_level", "high")},
                timeout=5,
            )
        except Exception as e:
            raise HTTPException(400, f"通知对方失败: {e}")
    peers[peer_id]["status"] = "trusted"
    return peers[peer_id]


@app.post("/api/peers/{peer_id}/reject")
async def reject_peer(peer_id: str):
    if peer_id not in peers:
        raise HTTPException(404, "节点不存在")
    peer = peers.pop(peer_id)
    # 通知对方已拒绝
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"{peer['endpoint']}/internal/trust-rejected",
                json={"agent_id": AGENT_ID, "name": AGENT_NAME, "endpoint": ENDPOINT},
                timeout=5,
            )
        except Exception:
            pass  # 通知失败不影响本方操作
    return {"ok": True}


@app.delete("/api/peers/{peer_id}")
async def remove_peer(peer_id: str):
    peers.pop(peer_id, None)
    return {"ok": True}


@app.get("/api/peers/{peer_id}/proxy/{file_id}")
async def proxy_peer_preview(peer_id: str, file_id: str):
    """代理预览对方节点的共享文件 — 任意互信等级均可。"""
    if peer_id not in peers or peers[peer_id]["status"] != "trusted":
        raise HTTPException(403, "该节点未建立互信")
    peer = peers[peer_id]
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{peer['endpoint']}/internal/preview/{file_id}",
                params={"from_id": AGENT_ID},
                timeout=30,
            )
            resp.raise_for_status()
        except Exception as e:
            raise HTTPException(400, f"预览失败: {e}")
    from fastapi.responses import Response
    mime = resp.headers.get("content-type", "application/octet-stream")
    return Response(content=resp.content, media_type=mime)


@app.get("/api/peers/{peer_id}/files")
async def browse_peer_files(peer_id: str):
    if peer_id not in peers or peers[peer_id]["status"] != "trusted":
        raise HTTPException(403, "该节点未建立互信")
    peer = peers[peer_id]
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{peer['endpoint']}/internal/shared-files",
                params={"from_id": AGENT_ID},
                timeout=5,
            )
            resp.raise_for_status()
        except Exception as e:
            raise HTTPException(400, f"获取文件列表失败: {e}")
    return resp.json()


@app.post("/api/peers/{peer_id}/fetch/{file_id}")
async def fetch_file(peer_id: str, file_id: str):
    if peer_id not in peers or peers[peer_id]["status"] != "trusted":
        raise HTTPException(403, "该节点未建立互信")
    if peers[peer_id].get("trust_level", "high") != "high":
        raise HTTPException(403, "仅高互信节点可下载文件")
    peer = peers[peer_id]
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{peer['endpoint']}/internal/files/{file_id}",
                params={"from_id": AGENT_ID},
                timeout=30,
            )
            resp.raise_for_status()
        except Exception as e:
            raise HTTPException(400, f"获取文件失败: {e}")

    filename = unquote(resp.headers.get("x-filename", file_id))
    dest = RECEIVED_DIR / filename
    if dest.exists():
        stem, suffix = dest.stem, dest.suffix
        dest = RECEIVED_DIR / f"{stem}_{uuid.uuid4().hex[:4]}{suffix}"
    dest.write_bytes(resp.content)
    entry = {
        "id": uuid.uuid4().hex[:8],
        "name": dest.name,
        "size": len(resp.content),
        "from_agent": peer_id,
        "from_name": peer["name"],
        "path": str(dest),
        "received_at": datetime.now().isoformat(),
    }
    received_files.append(entry)
    return entry


# ── 节点间内部 API ─────────────────────────────────────────────────────────────

@app.post("/internal/trust-request")
async def receive_trust_request(body: TrustPayload):
    peers[body.agent_id] = {
        "id": body.agent_id,
        "name": body.name,
        "endpoint": body.endpoint,
        "status": "pending_in",
        "trust_level": body.trust_level,
        "message": body.message,
    }
    return {"agent_id": AGENT_ID, "name": AGENT_NAME, "endpoint": ENDPOINT}


@app.post("/internal/trust-rejected")
async def receive_trust_rejected(body: TrustPayload):
    """接收对方的拒绝通知，将其标记为 rejected。"""
    if body.agent_id in peers:
        peers[body.agent_id]["status"] = "rejected"
    return {"ok": True}


@app.post("/internal/trust-accepted")
async def receive_trust_accepted(body: TrustPayload):
    peers[body.agent_id] = {
        "id": body.agent_id,
        "name": body.name,
        "endpoint": body.endpoint,
        "status": "trusted",
        "trust_level": body.trust_level,
    }
    return {"ok": True}


@app.get("/internal/shared-files")
async def internal_list_shared(from_id: str):
    if from_id not in peers or peers[from_id]["status"] != "trusted":
        raise HTTPException(403, "未建立互信")
    return list(shared_files.values())


@app.get("/internal/preview/{file_id}")
async def internal_preview_file(file_id: str, from_id: str):
    """内联预览文件 — 任意互信等级均可访问。"""
    if from_id not in peers or peers[from_id]["status"] != "trusted":
        raise HTTPException(403, "未建立互信")
    if file_id not in shared_files:
        raise HTTPException(404, "文件不存在")
    info = shared_files[file_id]
    _log_access("peer_preview", info["name"], file_id, from_id)
    mime, _ = mimetypes.guess_type(info["name"])
    return FileResponse(info["path"], media_type=mime or "application/octet-stream")


@app.get("/internal/files/{file_id}")
async def internal_download_file(file_id: str, from_id: str):
    if from_id not in peers or peers[from_id]["status"] != "trusted":
        raise HTTPException(403, "未建立互信")
    if peers[from_id].get("trust_level", "high") != "high":
        raise HTTPException(403, "仅高互信节点可下载文件")
    if file_id not in shared_files:
        raise HTTPException(404, "文件不存在")
    info = shared_files[file_id]
    _log_access("peer_download", info["name"], file_id, from_id)
    return FileResponse(
        info["path"],
        media_type="application/octet-stream",
        headers={"x-filename": quote(info["name"])},
    )


@app.get("/api/access-log")
async def get_access_log():
    return list(reversed(access_log))


# ── HTML 模板 ──────────────────────────────────────────────────────────────────

def _build_html() -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{AGENT_NAME}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', sans-serif;
            background: #f0f4f8; color: #1e293b; min-height: 100vh; }}

    /* Header */
    .header {{
      background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
      color: #fff;
      padding: 14px 28px;
      display: flex;
      align-items: center;
      gap: 14px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    }}
    .agent-avatar {{
      width: 44px; height: 44px;
      background: #4f46e5;
      border-radius: 12px;
      display: flex; align-items: center; justify-content: center;
      font-size: 22px; flex-shrink: 0;
    }}
    .agent-title {{ flex: 1; }}
    .agent-name {{ font-size: 17px; font-weight: 700; }}
    .agent-sub  {{ font-size: 12px; color: #94a3b8; margin-top: 2px; }}
    .online-dot {{
      width: 10px; height: 10px; background: #22c55e;
      border-radius: 50%; box-shadow: 0 0 0 3px rgba(34,197,94,0.25);
    }}

    /* Tabs */
    .tabs {{
      background: #fff; border-bottom: 1px solid #e2e8f0;
      display: flex; padding: 0 24px;
      position: sticky; top: 0; z-index: 10;
    }}
    .tab {{
      padding: 14px 22px; cursor: pointer;
      border-bottom: 3px solid transparent;
      color: #64748b; font-weight: 500; font-size: 14px;
      transition: color 0.15s, border-color 0.15s;
      display: flex; align-items: center; gap: 6px; user-select: none;
    }}
    .tab.active {{ color: #4f46e5; border-bottom-color: #4f46e5; }}
    .tab:hover:not(.active) {{ color: #1e293b; }}
    .badge {{
      background: #ef4444; color: #fff; font-size: 11px; font-weight: 600;
      min-width: 18px; height: 18px; padding: 0 5px; border-radius: 9px;
      display: inline-flex; align-items: center; justify-content: center;
    }}

    /* Content */
    .content {{ padding: 24px; max-width: 900px; }}
    .tab-panel {{ display: none; }}
    .tab-panel.active {{ display: block; }}

    /* Card */
    .card {{
      background: #fff; border-radius: 14px; padding: 20px 22px;
      margin-bottom: 18px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.04);
    }}
    .card-title {{
      font-size: 12px; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.6px; color: #94a3b8; margin-bottom: 16px;
    }}

    /* Upload */
    .upload-area {{
      border: 2px dashed #cbd5e1; border-radius: 12px;
      padding: 36px 20px; text-align: center; cursor: pointer;
      transition: border-color 0.2s, background 0.2s;
    }}
    .upload-area:hover, .upload-area.over {{ border-color: #4f46e5; background: #f5f3ff; }}
    .upload-icon {{ font-size: 36px; margin-bottom: 10px; }}
    .upload-text {{ font-size: 14px; color: #475569; }}
    .upload-hint {{ font-size: 12px; color: #94a3b8; margin-top: 4px; }}

    /* List items */
    .list-item {{
      display: flex; align-items: center; gap: 12px;
      padding: 11px 0; border-bottom: 1px solid #f1f5f9;
    }}
    .list-item:last-child {{ border-bottom: none; }}
    .item-icon {{
      width: 38px; height: 38px; border-radius: 10px;
      display: flex; align-items: center; justify-content: center;
      font-size: 19px; flex-shrink: 0;
    }}
    .icon-file {{ background: #eff6ff; }}
    .icon-recv {{ background: #f0fdf4; }}
    .icon-peer {{ background: #faf5ff; }}
    .item-info {{ flex: 1; min-width: 0; }}
    .item-name {{
      font-weight: 500; font-size: 14px;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }}
    .item-meta {{ font-size: 12px; color: #94a3b8; margin-top: 2px; }}
    .item-actions {{ display: flex; gap: 5px; flex-shrink: 0; }}

    /* Buttons */
    .btn {{
      padding: 7px 14px; border-radius: 8px; border: none;
      cursor: pointer; font-size: 13px; font-weight: 500;
      transition: all 0.15s; white-space: nowrap;
      text-decoration: none; display: inline-flex; align-items: center;
    }}
    .btn:disabled {{ opacity: 0.5; cursor: default; }}
    .btn-primary {{ background: #4f46e5; color: #fff; }}
    .btn-primary:hover:not(:disabled) {{ background: #4338ca; }}
    .btn-success {{ background: #22c55e; color: #fff; }}
    .btn-success:hover:not(:disabled) {{ background: #16a34a; }}
    .btn-danger  {{ background: #fee2e2; color: #dc2626; }}
    .btn-danger:hover:not(:disabled)  {{ background: #fecaca; }}
    .btn-ghost   {{ background: #f1f5f9; color: #475569; }}
    .btn-ghost:hover:not(:disabled)   {{ background: #e2e8f0; }}
    .btn-sm {{ padding: 5px 10px; font-size: 12px; }}

    /* Status badges */
    .status {{
      font-size: 12px; font-weight: 600; padding: 3px 10px;
      border-radius: 20px; white-space: nowrap;
    }}
    .status-trusted     {{ background: #dcfce7; color: #16a34a; }}
    .status-pending-in  {{ background: #fef9c3; color: #b45309; }}
    .status-pending-out {{ background: #dbeafe; color: #1d4ed8; }}
    .status-rejected    {{ background: #fee2e2; color: #dc2626; }}
    .trust-high   {{ background: #faf5ff; color: #7c3aed; font-size:11px; font-weight:600;
                     padding: 2px 8px; border-radius: 20px; white-space:nowrap; }}
    .trust-normal {{ background: #f1f5f9; color: #475569; font-size:11px; font-weight:600;
                     padding: 2px 8px; border-radius: 20px; white-space:nowrap; }}

    /* Connect form */
    .connect-row {{ display: flex; gap: 8px; align-items: center; }}
    .connect-row input {{
      flex: 1; padding: 9px 13px; border: 1px solid #e2e8f0;
      border-radius: 8px; font-size: 14px; outline: none;
      transition: border-color 0.15s;
    }}
    .connect-row input:focus {{ border-color: #4f46e5; }}
    .connect-row select {{
      padding: 9px 10px; border: 1px solid #e2e8f0;
      border-radius: 8px; font-size: 13px; outline: none;
      background: #fff; color: #1e293b; cursor: pointer;
      transition: border-color 0.15s;
    }}
    .connect-row select:focus {{ border-color: #4f46e5; }}

    /* Empty */
    .empty {{ text-align: center; padding: 36px 20px; color: #94a3b8; }}
    .empty-icon {{ font-size: 38px; margin-bottom: 8px; }}
    .empty-text {{ font-size: 14px; }}

    /* Toast */
    .toasts {{
      position: fixed; top: 20px; right: 20px; z-index: 9999;
      display: flex; flex-direction: column; gap: 8px; pointer-events: none;
    }}
    .toast {{
      padding: 11px 16px; border-radius: 10px; color: #fff;
      font-size: 14px; font-weight: 500;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      animation: toastIn 0.25s ease; pointer-events: auto;
    }}
    .toast-ok  {{ background: #22c55e; }}
    .toast-err {{ background: #ef4444; }}
    @keyframes toastIn {{
      from {{ opacity: 0; transform: translateX(60px); }}
      to   {{ opacity: 1; transform: translateX(0); }}
    }}

    /* Modals */
    .overlay {{
      display: none; position: fixed; inset: 0;
      background: rgba(0,0,0,0.5); z-index: 200;
      align-items: center; justify-content: center;
    }}
    .overlay.open {{ display: flex; }}
    .modal {{
      background: #fff; border-radius: 16px; padding: 24px;
      width: 540px; max-width: 94vw; max-height: 85vh; overflow-y: auto;
      box-shadow: 0 20px 60px rgba(0,0,0,0.2);
    }}
    .modal-lg {{
      width: 820px; max-width: 96vw; max-height: 90vh;
    }}
    .modal-header {{
      display: flex; justify-content: space-between; align-items: center;
      margin-bottom: 18px; gap: 12px;
    }}
    .modal-title {{ font-size: 16px; font-weight: 700; flex: 1; min-width: 0;
                    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .modal-actions {{ display: flex; gap: 8px; align-items: center; flex-shrink: 0; }}
    .modal-close {{
      background: none; border: none; font-size: 20px;
      cursor: pointer; color: #94a3b8; line-height: 1; padding: 2px;
    }}
    .modal-close:hover {{ color: #1e293b; }}

    /* Preview content */
    .preview-img {{
      max-width: 100%; max-height: 68vh;
      display: block; margin: 0 auto; border-radius: 8px;
    }}
    .preview-iframe {{
      width: 100%; height: 66vh; border: none; border-radius: 8px;
      background: #f8fafc;
    }}
    .preview-pre {{
      background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
      padding: 16px; overflow: auto; max-height: 66vh;
      font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
      font-size: 13px; line-height: 1.65;
      white-space: pre-wrap; word-break: break-all; color: #1e293b;
    }}
    .preview-video {{ width: 100%; border-radius: 8px; max-height: 66vh; }}
    .preview-audio {{ width: 100%; margin-top: 20px; }}
    .preview-unsupported {{
      text-align: center; padding: 48px 20px; color: #94a3b8;
    }}
    .preview-unsupported .big-icon {{ font-size: 52px; margin-bottom: 14px; }}
    .preview-unsupported p {{ font-size: 15px; color: #475569; margin-bottom: 20px; }}
  </style>
</head>
<body>

<div class="toasts" id="toasts"></div>

<!-- ── 文件浏览 Modal（互信节点） ── -->
<div class="overlay" id="browseModal">
  <div class="modal">
    <div class="modal-header">
      <span class="modal-title">📂 浏览文件 &mdash; <span id="browseModalPeerName">-</span></span>
      <button class="modal-close" onclick="closeBrowse()">&#x2715;</button>
    </div>
    <div id="browseBody">
      <div class="empty"><div class="empty-icon">⏳</div><div class="empty-text">加载中…</div></div>
    </div>
  </div>
</div>

<!-- ── 文件预览 Modal ── -->
<div class="overlay" id="previewModal">
  <div class="modal modal-lg">
    <div class="modal-header">
      <span class="modal-title" id="previewTitle">预览</span>
      <div class="modal-actions">
        <a id="previewDownloadBtn" class="btn btn-ghost btn-sm" href="#" download>⬇ 下载</a>
        <button class="modal-close" onclick="closePreview()">&#x2715;</button>
      </div>
    </div>
    <div id="previewBody"></div>
  </div>
</div>

<div class="header">
  <div class="agent-avatar">🤖</div>
  <div class="agent-title">
    <div class="agent-name" id="agentName">…</div>
    <div class="agent-sub" id="agentSub">…</div>
  </div>
  <div class="online-dot" title="运行中"></div>
</div>

<div class="tabs">
  <div class="tab active" id="tab-btn-shared" onclick="switchTab('shared')">
    📤 共享文件
  </div>
  <div class="tab" id="tab-btn-received" onclick="switchTab('received')">
    📥 已接收文件
    <span class="badge" id="recv-badge" style="display:none">0</span>
  </div>
  <div class="tab" id="tab-btn-trust" onclick="switchTab('trust')">
    🔐 互信管理
    <span class="badge" id="trust-badge" style="display:none">0</span>
  </div>
</div>

<div class="content">

  <!-- ── Tab: 共享文件 ── -->
  <div id="tab-shared" class="tab-panel active">
    <div class="card">
      <div class="card-title">添加共享文件</div>
      <div class="upload-area" id="uploadArea" onclick="document.getElementById('fileInput').click()">
        <input type="file" id="fileInput" multiple style="display:none" onchange="uploadFiles(this.files)">
        <div class="upload-icon">📁</div>
        <div class="upload-text">点击选择文件，或拖拽到此处</div>
        <div class="upload-hint">支持任意类型，可多选</div>
      </div>
    </div>
    <div class="card">
      <div class="card-title">正在共享的文件</div>
      <div id="sharedList">
        <div class="empty"><div class="empty-icon">📭</div><div class="empty-text">暂无共享文件</div></div>
      </div>
    </div>
  </div>

  <!-- ── Tab: 已接收文件 ── -->
  <div id="tab-received" class="tab-panel">
    <div class="card">
      <div class="card-title">已接收的文件</div>
      <div id="receivedList">
        <div class="empty"><div class="empty-icon">📭</div><div class="empty-text">暂无接收文件</div></div>
      </div>
    </div>
  </div>

  <!-- ── Tab: 互信管理 ── -->
  <div id="tab-trust" class="tab-panel">
    <div class="card">
      <div class="card-title">连接新节点</div>
      <div class="connect-row">
        <input type="text" id="connectInput" placeholder="节点地址，例如 http://localhost:8021"
               onkeydown="if(event.key==='Enter') connectPeer()">
        <select id="trustLevelSelect">
          <option value="high">🔐 高互信（可浏览+下载）</option>
          <option value="normal">👁 一般互信（仅浏览）</option>
        </select>
        <button class="btn btn-primary" onclick="connectPeer()">发起互信</button>
      </div>
      <textarea id="connectMessage" placeholder="描述信息（选填）：说明身份、用途或请求原因，帮助对方判断是否接受互信…"
        style="margin-top:10px;width:100%;padding:9px 13px;border:1px solid #e2e8f0;border-radius:8px;
               font-size:13px;color:#1e293b;resize:vertical;min-height:68px;outline:none;
               font-family:inherit;transition:border-color 0.15s;"
        onfocus="this.style.borderColor='#4f46e5'" onblur="this.style.borderColor='#e2e8f0'"></textarea>
    </div>
    <div class="card">
      <div class="card-title">已互信节点</div>
      <div id="trustedList">
        <div class="empty"><div class="empty-icon">🔒</div><div class="empty-text">暂无已互信节点</div></div>
      </div>
    </div>
    <div class="card">
      <div class="card-title">待建立互信</div>
      <div id="pendingList">
        <div class="empty"><div class="empty-icon">⏳</div><div class="empty-text">暂无待处理请求</div></div>
      </div>
    </div>
  </div>

</div><!-- /content -->

<script>
  let browsingPeerId = null;
  const tabNames = ['shared', 'received', 'trust'];

  // ── 初始化 ────────────────────────────────────────────────────────────────
  async function init() {{
    const info = await get('/api/info');
    document.getElementById('agentName').textContent = info.name;
    document.getElementById('agentSub').textContent  = `${{info.agent_id}}  ·  ${{info.endpoint}}`;
    document.title = `${{info.name}} :${{info.port}}`;
    await refresh();
    setInterval(refresh, 3000);
  }}

  async function refresh() {{
    await Promise.all([loadShared(), loadReceived(), loadPeers()]);
  }}

  // ── HTTP helpers ──────────────────────────────────────────────────────────
  async function get(url) {{
    const r = await fetch(url);
    if (!r.ok) throw new Error((await r.json().catch(()=>({{}}))).detail || r.statusText);
    return r.json();
  }}
  async function post(url, body) {{
    const r = await fetch(url, {{
      method: 'POST',
      headers: {{'Content-Type':'application/json'}},
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }});
    if (!r.ok) throw new Error((await r.json().catch(()=>({{}}))).detail || r.statusText);
    return r.json();
  }}
  async function del(url) {{
    const r = await fetch(url, {{method:'DELETE'}});
    if (!r.ok) throw new Error((await r.json().catch(()=>({{}}))).detail || r.statusText);
    return r.json();
  }}

  function toast(msg, type='ok') {{
    const el = document.createElement('div');
    el.className = `toast toast-${{type}}`;
    el.textContent = msg;
    document.getElementById('toasts').appendChild(el);
    setTimeout(() => el.remove(), 3500);
  }}

  // ── Tab 切换 ──────────────────────────────────────────────────────────────
  function switchTab(name) {{
    tabNames.forEach(n => {{
      document.getElementById(`tab-btn-${{n}}`).classList.toggle('active', n===name);
      document.getElementById(`tab-${{n}}`).classList.toggle('active', n===name);
    }});
  }}

  // ── 文件类型检测 ──────────────────────────────────────────────────────────
  function fileCategory(name) {{
    const ext = (name.split('.').pop() || '').toLowerCase();
    if (['jpg','jpeg','png','gif','webp','svg','bmp','ico','avif'].includes(ext)) return 'image';
    if (ext === 'pdf') return 'pdf';
    if (['mp4','webm','mov','avi','mkv','m4v'].includes(ext)) return 'video';
    if (['mp3','wav','ogg','aac','flac','m4a','opus'].includes(ext)) return 'audio';
    if (['txt','md','json','csv','xml','yaml','yml','log','py','js','ts','jsx','tsx',
         'html','css','sh','bash','conf','ini','toml','env','sql','rs','go','java',
         'c','cpp','h','hpp','rb','php','swift','kt','vue','scss','less'].includes(ext))
      return 'text';
    return 'unknown';
  }}

  function fileIcon(name) {{
    const c = fileCategory(name);
    return {{ image:'🖼', pdf:'📑', video:'🎬', audio:'🎵', text:'📝', unknown:'📄' }}[c] || '📄';
  }}

  // ── 预览 Modal ────────────────────────────────────────────────────────────
  async function openPreview(rawUrl, fileName, downloadUrl) {{
    document.getElementById('previewTitle').textContent = `👁 ${{fileName}}`;
    const dlBtn = document.getElementById('previewDownloadBtn');
    if (downloadUrl) {{
      dlBtn.href = downloadUrl;
      dlBtn.download = fileName;
      dlBtn.style.display = 'inline-flex';
    }} else {{
      dlBtn.style.display = 'none';
    }}
    document.getElementById('previewModal').classList.add('open');

    const body = document.getElementById('previewBody');
    const cat = fileCategory(fileName);

    if (cat === 'image') {{
      body.innerHTML = `<img class="preview-img" src="${{rawUrl}}" alt="${{fileName}}">`;
    }} else if (cat === 'pdf') {{
      body.innerHTML = `<iframe class="preview-iframe" src="${{rawUrl}}"></iframe>`;
    }} else if (cat === 'video') {{
      body.innerHTML = `<video class="preview-video" controls src="${{rawUrl}}"></video>`;
    }} else if (cat === 'audio') {{
      body.innerHTML = `<div style="padding:32px 0"><audio class="preview-audio" controls src="${{rawUrl}}"></audio></div>`;
    }} else if (cat === 'text') {{
      body.innerHTML = '<div class="empty"><div class="empty-icon">⏳</div><div class="empty-text">加载中…</div></div>';
      try {{
        const r = await fetch(rawUrl);
        const text = await r.text();
        const pre = document.createElement('pre');
        pre.className = 'preview-pre';
        pre.textContent = text;
        body.innerHTML = '';
        body.appendChild(pre);
      }} catch(e) {{
        body.innerHTML = `<div class="preview-unsupported"><div class="big-icon">❌</div><p>加载失败: ${{e.message}}</p></div>`;
      }}
    }} else {{
      body.innerHTML = `
        <div class="preview-unsupported">
          <div class="big-icon">📄</div>
          <p>此文件类型暂不支持预览</p>
          <a class="btn btn-primary" href="${{downloadUrl}}" download="${{fileName}}">⬇ 下载文件</a>
        </div>`;
    }}
  }}

  function closePreview() {{
    document.getElementById('previewModal').classList.remove('open');
    document.getElementById('previewBody').innerHTML = '';
  }}
  document.getElementById('previewModal').addEventListener('click', e => {{
    if (e.target === document.getElementById('previewModal')) closePreview();
  }});

  // ── 共享文件 ──────────────────────────────────────────────────────────────
  async function loadShared() {{
    const files = await get('/api/shared').catch(()=>[]);
    const el = document.getElementById('sharedList');
    if (!files.length) {{
      el.innerHTML = '<div class="empty"><div class="empty-icon">📭</div><div class="empty-text">暂无共享文件</div></div>';
      return;
    }}
    el.innerHTML = files.map(f => `
      <div class="list-item">
        <div class="item-icon icon-file">${{fileIcon(f.name)}}</div>
        <div class="item-info">
          <div class="item-name" title="${{f.name}}">${{f.name}}</div>
          <div class="item-meta">${{fmtSize(f.size)}} &nbsp;·&nbsp; ${{fmtTime(f.created_at)}}</div>
        </div>
        <div class="item-actions">
          <button class="btn btn-ghost btn-sm"
            onclick="openPreview('/api/shared/${{f.id}}/raw','${{f.name}}','/api/shared/${{f.id}}/download')">
            👁 预览
          </button>
          <a class="btn btn-ghost btn-sm"
             href="/api/shared/${{f.id}}/download" download="${{f.name}}">⬇ 下载</a>
          <button class="btn btn-danger btn-sm" onclick="deleteShared('${{f.id}}','${{f.name}}')">
            🗑 删除
          </button>
        </div>
      </div>`).join('');
  }}

  async function uploadFiles(files) {{
    for (const file of files) {{
      const fd = new FormData();
      fd.append('file', file);
      const r = await fetch('/api/shared/upload', {{method:'POST', body:fd}});
      if (r.ok) toast(`已共享: ${{file.name}}`);
      else      toast(`上传失败: ${{file.name}}`, 'err');
    }}
    await loadShared();
  }}

  async function deleteShared(id, name) {{
    if (!confirm(`确认删除共享文件 "${{name}}"？`)) return;
    try {{
      await del(`/api/shared/${{id}}`);
      toast('已删除');
      await loadShared();
    }} catch(e) {{ toast(e.message, 'err'); }}
  }}

  // ── 拖拽上传 ──────────────────────────────────────────────────────────────
  const ua = document.getElementById('uploadArea');
  ua.addEventListener('dragover', e => {{ e.preventDefault(); ua.classList.add('over'); }});
  ua.addEventListener('dragleave', () => ua.classList.remove('over'));
  ua.addEventListener('drop', e => {{
    e.preventDefault(); ua.classList.remove('over');
    uploadFiles(e.dataTransfer.files);
  }});

  // ── 已接收文件 ────────────────────────────────────────────────────────────
  async function loadReceived() {{
    const files = await get('/api/received').catch(()=>[]);
    const badge = document.getElementById('recv-badge');
    badge.textContent = files.length;
    badge.style.display = files.length ? 'inline-flex' : 'none';

    const el = document.getElementById('receivedList');
    if (!files.length) {{
      el.innerHTML = '<div class="empty"><div class="empty-icon">📭</div><div class="empty-text">暂无接收文件</div></div>';
      return;
    }}
    el.innerHTML = files.map(f => `
      <div class="list-item">
        <div class="item-icon icon-recv">${{fileIcon(f.name)}}</div>
        <div class="item-info">
          <div class="item-name" title="${{f.name}}">${{f.name}}</div>
          <div class="item-meta">来自 ${{f.from_name}} &nbsp;·&nbsp; ${{fmtSize(f.size)}} &nbsp;·&nbsp; ${{fmtTime(f.received_at)}}</div>
        </div>
        <div class="item-actions">
          <button class="btn btn-ghost btn-sm"
            onclick="openPreview('/api/received/${{f.id}}/raw','${{f.name}}','/api/received/${{f.id}}/download')">
            👁 预览
          </button>
          <a class="btn btn-ghost btn-sm"
             href="/api/received/${{f.id}}/download" download="${{f.name}}">⬇ 下载</a>
          <button class="btn btn-danger btn-sm" onclick="deleteReceived('${{f.id}}','${{f.name}}')">
            🗑 删除
          </button>
        </div>
      </div>`).join('');
  }}

  async function deleteReceived(id, name) {{
    if (!confirm(`确认删除 "${{name}}"？`)) return;
    try {{
      await del(`/api/received/${{id}}`);
      toast('已删除');
      await loadReceived();
    }} catch(e) {{ toast(e.message, 'err'); }}
  }}

  // ── 互信管理 ──────────────────────────────────────────────────────────────
  async function loadPeers() {{
    const peers = await get('/api/peers').catch(()=>[]);
    const trusted = peers.filter(p => p.status === 'trusted');
    const pending = peers.filter(p => p.status !== 'trusted');
    const pendingIn = pending.filter(p => p.status === 'pending_in').length;

    const badge = document.getElementById('trust-badge');
    badge.textContent = pendingIn;
    badge.style.display = pendingIn ? 'inline-flex' : 'none';

    renderTrusted(trusted);
    renderPending(pending);
  }}

  function renderTrusted(peers) {{
    const el = document.getElementById('trustedList');
    if (!peers.length) {{
      el.innerHTML = '<div class="empty"><div class="empty-icon">🔒</div><div class="empty-text">暂无已互信节点</div></div>';
      return;
    }}
    el.innerHTML = peers.map(p => `
      <div class="list-item">
        <div class="item-icon icon-peer">🤖</div>
        <div class="item-info">
          <div class="item-name">${{p.name}}</div>
          <div class="item-meta">${{p.endpoint}}</div>
        </div>
        <span class="status status-trusted">已互信</span>
        <span class="${{p.trust_level === 'high' ? 'trust-high' : 'trust-normal'}}">
          ${{p.trust_level === 'high' ? '🔐 高互信' : '👁 一般互信'}}
        </span>
        <button class="btn btn-ghost btn-sm"
          onclick="openBrowse('${{p.id}}','${{p.name}}','${{p.trust_level}}')">浏览文件</button>
      </div>`).join('');
  }}

  function renderPending(peers) {{
    const el = document.getElementById('pendingList');
    if (!peers.length) {{
      el.innerHTML = '<div class="empty"><div class="empty-icon">⏳</div><div class="empty-text">暂无待处理请求</div></div>';
      return;
    }}
    el.innerHTML = peers.map(p => `
      <div class="list-item">
        <div class="item-icon icon-peer">🤖</div>
        <div class="item-info">
          <div class="item-name">${{p.name}}</div>
          <div class="item-meta">${{p.endpoint}}</div>
          ${{p.status === 'pending_in' && p.message ? `
            <div style="margin-top:6px;padding:7px 10px;background:#f5f3ff;
                 border-left:3px solid #4f46e5;border-radius:4px;
                 font-size:12px;color:#475569;line-height:1.6;">
              ${{p.message}}
            </div>` : ''}}
        </div>
        ${{p.status === 'pending_in' ? `
          <span class="${{p.trust_level === 'high' ? 'trust-high' : 'trust-normal'}}">
            ${{p.trust_level === 'high' ? '🔐 高互信' : '👁 一般互信'}}
          </span>
          <span class="status status-pending-in">待接受</span>
          <button class="btn btn-success btn-sm" onclick="acceptPeer('${{p.id}}')">接受</button>
          <button class="btn btn-danger btn-sm" onclick="rejectPeer('${{p.id}}')">拒绝</button>
        ` : p.status === 'rejected' ? `
          <span class="status status-rejected">对方拒绝建立互信，请重新商量</span>
          <button class="btn btn-ghost btn-sm" onclick="dismissPeer('${{p.id}}')">知道了</button>
        ` : `
          <span class="status status-pending-out">等待确认</span>
        `}}
      </div>`).join('');
  }}

  async function connectPeer() {{
    const endpoint = document.getElementById('connectInput').value.trim();
    const trust_level = document.getElementById('trustLevelSelect').value;
    const message = document.getElementById('connectMessage').value.trim();
    if (!endpoint) return toast('请输入节点地址', 'err');
    try {{
      await post('/api/peers/connect', {{endpoint, trust_level, message}});
      toast('互信请求已发送，等待对方确认');
      document.getElementById('connectInput').value = '';
      document.getElementById('connectMessage').value = '';
      await loadPeers();
    }} catch(e) {{ toast(e.message, 'err'); }}
  }}

  async function acceptPeer(id) {{
    try {{
      await post(`/api/peers/${{id}}/accept`);
      toast('互信已建立！');
      await loadPeers();
    }} catch(e) {{ toast(e.message, 'err'); }}
  }}

  async function rejectPeer(id) {{
    try {{
      await post(`/api/peers/${{id}}/reject`);
      toast('已拒绝请求');
      await loadPeers();
    }} catch(e) {{ toast(e.message, 'err'); }}
  }}

  async function dismissPeer(id) {{
    try {{
      await del(`/api/peers/${{id}}`);
      await loadPeers();
    }} catch(e) {{ toast(e.message, 'err'); }}
  }}

  // ── 浏览节点文件 Modal ────────────────────────────────────────────────────
  async function openBrowse(peerId, peerName, trustLevel) {{
    browsingPeerId = peerId;
    document.getElementById('browseModalPeerName').textContent = peerName;
    document.getElementById('browseModal').classList.add('open');
    document.getElementById('browseBody').innerHTML =
      '<div class="empty"><div class="empty-icon">⏳</div><div class="empty-text">加载中…</div></div>';

    try {{
      const files = await get(`/api/peers/${{peerId}}/files`);
      if (!files.length) {{
        document.getElementById('browseBody').innerHTML =
          '<div class="empty"><div class="empty-icon">📭</div><div class="empty-text">该节点暂无共享文件</div></div>';
        return;
      }}
      const canDownload = trustLevel === 'high';
      document.getElementById('browseBody').innerHTML = files.map(f => `
        <div class="list-item">
          <div class="item-icon icon-file">${{fileIcon(f.name)}}</div>
          <div class="item-info">
            <div class="item-name" title="${{f.name}}">${{f.name}}</div>
            <div class="item-meta">${{fmtSize(f.size)}}</div>
          </div>
          <div class="item-actions">
            <button class="btn btn-ghost btn-sm"
              onclick="openPreview('/api/peers/${{peerId}}/proxy/${{f.id}}','${{f.name}}','')">
              👁 预览
            </button>
            ${{canDownload
              ? `<button class="btn btn-primary btn-sm" id="fetch-${{f.id}}"
                         onclick="fetchFile('${{f.id}}','${{f.name}}',this)">获取</button>`
              : `<span style="font-size:12px;color:#94a3b8;padding:0 4px">仅可浏览</span>`
            }}
          </div>
        </div>`).join('');
    }} catch(e) {{
      document.getElementById('browseBody').innerHTML =
        `<div class="empty"><div class="empty-icon">❌</div><div class="empty-text">${{e.message}}</div></div>`;
    }}
  }}

  async function fetchFile(fileId, fileName, btn) {{
    if (!browsingPeerId) return;
    btn.disabled = true; btn.textContent = '获取中…';
    try {{
      await post(`/api/peers/${{browsingPeerId}}/fetch/${{fileId}}`);
      toast(`已获取: ${{fileName}}`);
      btn.textContent = '✓ 已获取';
      await loadReceived();
    }} catch(e) {{
      toast(e.message, 'err');
      btn.disabled = false; btn.textContent = '获取';
    }}
  }}

  function closeBrowse() {{
    document.getElementById('browseModal').classList.remove('open');
    browsingPeerId = null;
  }}
  document.getElementById('browseModal').addEventListener('click', e => {{
    if (e.target === document.getElementById('browseModal')) closeBrowse();
  }});

  // ── 格式化工具 ────────────────────────────────────────────────────────────
  function fmtSize(b) {{
    if (b < 1024)    return b + ' B';
    if (b < 1048576) return (b/1024).toFixed(1) + ' KB';
    return (b/1048576).toFixed(1) + ' MB';
  }}
  function fmtTime(iso) {{
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleString('zh-CN', {{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}});
  }}

  init();
</script>
</body>
</html>"""


if __name__ == "__main__":
    print(f"启动 {AGENT_NAME}  →  http://localhost:{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
