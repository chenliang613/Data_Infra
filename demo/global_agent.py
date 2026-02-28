#!/usr/bin/env python3
"""
Agent-ALL — 全局监控节点
=========================
汇总展示所有 P2P 节点的文件共享、互信关系和访问记录。
"""
from __future__ import annotations

import argparse
import asyncio

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=8020)
parser.add_argument("--name", type=str, default="Agent-ALL")
args = parser.parse_args()
PORT = args.port

WATCHED_AGENTS = [
    {"port": 8021, "name": "数据共享方Agent-A", "id": "agent-8021"},
    {"port": 8023, "name": "数据共享方Agent-B", "id": "agent-8023"},
    {"port": 8025, "name": "数据接收方Agent-C", "id": "agent-8025"},
    {"port": 8027, "name": "数据接收方Agent-D", "id": "agent-8027"},
]

app = FastAPI(title="Agent-ALL")


async def _fetch_one(client: httpx.AsyncClient, agent: dict) -> dict:
    base = f"http://localhost:{agent['port']}"
    entry = {**agent, "online": False, "shared": [], "received": [], "peers": [], "access_log": []}
    try:
        rs = await asyncio.gather(
            client.get(f"{base}/api/shared"),
            client.get(f"{base}/api/received"),
            client.get(f"{base}/api/peers"),
            client.get(f"{base}/api/access-log"),
            return_exceptions=True,
        )
        if not isinstance(rs[0], Exception):
            entry["online"] = True
            entry["shared"] = rs[0].json()
        if not isinstance(rs[1], Exception): entry["received"]   = rs[1].json()
        if not isinstance(rs[2], Exception): entry["peers"]      = rs[2].json()
        if not isinstance(rs[3], Exception): entry["access_log"] = rs[3].json()
    except Exception:
        pass
    return entry


@app.get("/api/status")
async def get_status():
    async with httpx.AsyncClient(timeout=3.0) as client:
        results = await asyncio.gather(*[_fetch_one(client, a) for a in WATCHED_AGENTS])
    return list(results)


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(_build_html())


def _build_html() -> str:
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Agent-ALL 全局监控</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', sans-serif;
           background: #f0f4f8; color: #1e293b; min-height: 100vh; }

    /* Header */
    .header {
      background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
      color: #fff; padding: 14px 28px;
      display: flex; align-items: center; gap: 14px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    }
    .header-icon { font-size: 28px; }
    .header-title { flex: 1; }
    .header-name { font-size: 18px; font-weight: 700; }
    .header-sub  { font-size: 12px; color: #94a3b8; margin-top: 2px; }
    .update-time { font-size: 12px; color: #64748b; text-align: right; }

    /* Summary bar */
    .summary-bar {
      background: #1e293b; color: #94a3b8;
      padding: 8px 28px; display: flex; gap: 28px; font-size: 13px;
    }
    .summary-item span { color: #f1f5f9; font-weight: 600; margin-left: 4px; }

    /* Tabs */
    .tabs {
      background: #fff; border-bottom: 1px solid #e2e8f0;
      display: flex; padding: 0 24px;
      position: sticky; top: 0; z-index: 10;
    }
    .tab {
      padding: 14px 22px; cursor: pointer;
      border-bottom: 3px solid transparent;
      color: #64748b; font-weight: 500; font-size: 14px;
      transition: color 0.15s, border-color 0.15s;
    }
    .tab.active { color: #4f46e5; border-bottom-color: #4f46e5; }
    .tab:hover:not(.active) { color: #1e293b; }

    /* Content */
    .content { padding: 24px; }
    .tab-panel { display: none; }
    .tab-panel.active { display: block; }

    /* Agent cards grid */
    .cards-grid {
      display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px;
    }
    .agent-card {
      background: #fff; border-radius: 14px; padding: 18px 20px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.04);
      border-left: 4px solid #e2e8f0;
    }
    .agent-card.online  { border-left-color: #22c55e; }
    .agent-card.offline { border-left-color: #ef4444; opacity: 0.7; }
    .card-head { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
    .dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
    .dot-online  { background: #22c55e; box-shadow: 0 0 0 3px rgba(34,197,94,0.2); }
    .dot-offline { background: #ef4444; }
    .card-name { font-weight: 700; font-size: 15px; flex: 1; }
    .card-port { font-size: 12px; color: #94a3b8; }
    .card-stats {
      display: flex; background: #f8fafc; border-radius: 10px;
      overflow: hidden; margin-bottom: 12px;
    }
    .stat { flex: 1; padding: 10px 8px; text-align: center; border-right: 1px solid #e2e8f0; }
    .stat:last-child { border-right: none; }
    .stat-num   { display: block; font-size: 22px; font-weight: 700; color: #1e293b; }
    .stat-label { display: block; font-size: 11px; color: #94a3b8; margin-top: 2px; }
    .file-list  { margin-top: 4px; }
    .file-item  {
      display: flex; align-items: center; gap: 6px;
      padding: 5px 0; border-top: 1px solid #f1f5f9; font-size: 13px;
    }
    .file-name-text { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .file-size { color: #94a3b8; font-size: 12px; flex-shrink: 0; }
    .offline-msg { text-align: center; color: #ef4444; font-size: 13px; margin-top: 8px; }

    /* Trust table */
    .section-card {
      background: #fff; border-radius: 14px; overflow: hidden;
      box-shadow: 0 1px 4px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.04);
    }
    table { width: 100%; border-collapse: collapse; }
    thead th {
      background: #f8fafc; padding: 12px 16px;
      font-size: 12px; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.6px; color: #94a3b8; text-align: left;
      border-bottom: 1px solid #e2e8f0;
    }
    tbody td { padding: 11px 16px; border-bottom: 1px solid #f1f5f9; font-size: 14px; }
    tbody tr:last-child td { border-bottom: none; }
    tbody tr:hover td { background: #f8fafc; }
    .trust-badge {
      display: inline-block; padding: 3px 10px; border-radius: 20px;
      font-size: 12px; font-weight: 600;
    }
    .trust-high   { background: #faf5ff; color: #7c3aed; }
    .trust-normal { background: #f1f5f9; color: #475569; }

    /* Access log */
    .log-time     { color: #94a3b8; white-space: nowrap; font-size: 12px; }
    .log-filename { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .event-badge  {
      display: inline-block; padding: 2px 8px; border-radius: 20px;
      font-size: 11px; font-weight: 600; white-space: nowrap;
    }
    .ev-peer_download { background: #dcfce7; color: #16a34a; }
    .ev-peer_preview  { background: #dbeafe; color: #1d4ed8; }
    .ev-local_preview { background: #f1f5f9; color: #64748b; }
    .ev-local_download{ background: #fef9c3; color: #b45309; }

    .empty {
      text-align: center; padding: 52px; color: #94a3b8; font-size: 15px;
      background: #fff; border-radius: 14px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.04);
    }
    .empty-icon { font-size: 38px; margin-bottom: 10px; }
  </style>
</head>
<body>

<div class="header">
  <div class="header-icon">🌐</div>
  <div class="header-title">
    <div class="header-name">Agent-ALL &nbsp;全局监控</div>
    <div class="header-sub">实时汇总所有节点的共享、互信与访问情况</div>
  </div>
  <div class="update-time" id="updateTime">—</div>
</div>

<div class="summary-bar">
  <div>在线节点 <span id="sum-online">—</span></div>
  <div>共享文件 <span id="sum-shared">—</span></div>
  <div>互信关系 <span id="sum-trust">—</span></div>
  <div>访问记录 <span id="sum-log">—</span></div>
</div>

<div class="tabs">
  <div class="tab active" id="tab-btn-overview" onclick="switchTab('overview')">📊 节点概览</div>
  <div class="tab" id="tab-btn-trust"    onclick="switchTab('trust')">🔐 互信关系</div>
  <div class="tab" id="tab-btn-log"      onclick="switchTab('log')">📋 访问日志</div>
</div>

<div class="content">
  <div id="tab-overview" class="tab-panel active">
    <div class="cards-grid" id="cards-grid">
      <div class="empty" style="grid-column:1/-1"><div class="empty-icon">⏳</div>加载中…</div>
    </div>
  </div>
  <div id="tab-trust" class="tab-panel">
    <div id="trust-container"><div class="empty"><div class="empty-icon">⏳</div>加载中…</div></div>
  </div>
  <div id="tab-log" class="tab-panel">
    <div id="log-container"><div class="empty"><div class="empty-icon">⏳</div>加载中…</div></div>
  </div>
</div>

<script>
  const TABS = ['overview', 'trust', 'log'];
  let agentNames = {};

  function switchTab(name) {
    TABS.forEach(n => {
      document.getElementById('tab-btn-' + n).classList.toggle('active', n === name);
      document.getElementById('tab-' + n).classList.toggle('active', n === name);
    });
  }

  async function refresh() {
    try {
      const resp = await fetch('/api/status');
      const data = await resp.json();
      agentNames = {};
      for (const a of data) agentNames[a.id] = a.name;
      renderOverview(data);
      renderTrust(data);
      renderLog(data);
      renderSummary(data);
      document.getElementById('updateTime').textContent =
        '最后更新 ' + new Date().toLocaleTimeString('zh-CN');
    } catch(e) { console.error(e); }
  }

  function renderSummary(data) {
    const online  = data.filter(a => a.online).length;
    const shared  = data.reduce((s, a) => s + a.shared.length, 0);
    const trusts  = data.reduce((s, a) => s + a.peers.filter(p => p.status === 'trusted').length, 0);
    const logs    = data.reduce((s, a) => s + a.access_log.length, 0);
    document.getElementById('sum-online').textContent = online + ' / ' + data.length;
    document.getElementById('sum-shared').textContent = shared;
    document.getElementById('sum-trust').textContent  = trusts;
    document.getElementById('sum-log').textContent    = logs;
  }

  function renderOverview(data) {
    const grid = document.getElementById('cards-grid');
    grid.innerHTML = data.map(a => {
      const trusted = a.peers.filter(p => p.status === 'trusted').length;
      const files = a.shared.map(f => `
        <div class="file-item">
          <span>${fileIcon(f.name)}</span>
          <span class="file-name-text" title="${esc(f.name)}">${esc(f.name)}</span>
          <span class="file-size">${fmtSize(f.size)}</span>
        </div>`).join('');
      return `
        <div class="agent-card ${a.online ? 'online' : 'offline'}">
          <div class="card-head">
            <div class="dot ${a.online ? 'dot-online' : 'dot-offline'}"></div>
            <div class="card-name">${esc(a.name)}</div>
            <div class="card-port">:${a.port}</div>
          </div>
          <div class="card-stats">
            <div class="stat"><span class="stat-num">${a.shared.length}</span><span class="stat-label">共享文件</span></div>
            <div class="stat"><span class="stat-num">${a.received.length}</span><span class="stat-label">已接收</span></div>
            <div class="stat"><span class="stat-num">${trusted}</span><span class="stat-label">互信节点</span></div>
          </div>
          ${a.shared.length ? '<div class="file-list">' + files + '</div>' : ''}
          ${!a.online ? '<div class="offline-msg">● 节点离线</div>' : ''}
        </div>`;
    }).join('');
  }

  function renderTrust(data) {
    const trusts = [];
    for (const agent of data) {
      for (const peer of agent.peers) {
        if (peer.status === 'trusted') {
          trusts.push({
            from_name: agent.name,
            to_name: agentNames[peer.id] || peer.name || peer.id,
            trust_level: peer.trust_level || 'high',
          });
        }
      }
    }
    const el = document.getElementById('trust-container');
    if (!trusts.length) {
      el.innerHTML = '<div class="empty"><div class="empty-icon">🔒</div>暂无互信关系</div>';
      return;
    }
    el.innerHTML = `
      <div class="section-card">
        <table>
          <thead><tr><th>发起方</th><th>接受方</th><th>互信等级</th></tr></thead>
          <tbody>${trusts.map(t => `
            <tr>
              <td>${esc(t.from_name)}</td>
              <td>→ ${esc(t.to_name)}</td>
              <td><span class="trust-badge ${t.trust_level === 'high' ? 'trust-high' : 'trust-normal'}">
                ${t.trust_level === 'high' ? '🔐 高互信（浏览+下载）' : '👁 一般互信（仅浏览）'}
              </span></td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
  }

  function renderLog(data) {
    const eventLabel = {
      peer_download:  '获取',
      peer_preview:   '预览',
      local_preview:  '本地预览',
      local_download: '本地下载',
    };
    const allLogs = [];
    for (const agent of data) {
      for (const entry of agent.access_log || []) {
        allLogs.push({...entry, _agent_name: agent.name});
      }
    }
    allLogs.sort((a, b) => b.time.localeCompare(a.time));

    const el = document.getElementById('log-container');
    if (!allLogs.length) {
      el.innerHTML = '<div class="empty"><div class="empty-icon">📋</div>暂无访问记录</div>';
      return;
    }
    const rows = allLogs.slice(0, 200).map(e => {
      const actor = e.actor === 'local'
        ? esc(e._agent_name) + '（本节点）'
        : esc(agentNames[e.actor] || e.actor);
      const cls = 'ev-' + e.event;
      return `
        <tr>
          <td class="log-time">${fmtTime(e.time)}</td>
          <td>${esc(e._agent_name)}</td>
          <td><span class="event-badge ${cls}">${eventLabel[e.event] || e.event}</span></td>
          <td class="log-filename" title="${esc(e.file_name)}">${esc(e.file_name)}</td>
          <td>${actor}</td>
        </tr>`;
    }).join('');
    el.innerHTML = `
      <div class="section-card">
        <table>
          <thead><tr><th>时间</th><th>文件所在节点</th><th>事件</th><th>文件名</th><th>操作方</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
  }

  function fileIcon(name) {
    const ext = (name.split('.').pop() || '').toLowerCase();
    if (['jpg','jpeg','png','gif','webp','svg','bmp'].includes(ext)) return '🖼';
    if (ext === 'pdf') return '📑';
    if (['mp4','webm','mov','avi'].includes(ext)) return '🎬';
    if (['mp3','wav','ogg','aac','flac'].includes(ext)) return '🎵';
    if (['txt','md','json','csv','py','js','ts','html','css','yaml'].includes(ext)) return '📝';
    return '📄';
  }

  function fmtSize(b) {
    if (b < 1024)    return b + ' B';
    if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
    return (b / 1048576).toFixed(1) + ' MB';
  }

  function fmtTime(iso) {
    if (!iso) return '';
    return new Date(iso).toLocaleString('zh-CN', {
      month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  }

  function esc(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  refresh();
  setInterval(refresh, 3000);
</script>
</body>
</html>"""


if __name__ == "__main__":
    print(f"启动 Agent-ALL  →  http://localhost:{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
