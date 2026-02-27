#!/usr/bin/env python3
"""
一键启动 P2P 演示 — 同时运行 Agent-1 (8026) 和 Agent-2 (8025)
================================================================
用法:
  python demo/start_p2p.py

Ctrl+C 停止全部节点。
"""
from __future__ import annotations

import subprocess
import sys
import time
import webbrowser
from pathlib import Path

AGENTS = [
    {"port": 8026, "name": "Agent-1"},
    {"port": 8025, "name": "Agent-2"},
]

SCRIPT = Path(__file__).parent / "p2p_agent.py"


def kill_port(port: int) -> None:
    """Kill any process occupying the given port."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True
        )
        pids = result.stdout.strip().split()
        for pid in pids:
            if pid:
                subprocess.run(["kill", "-9", pid], check=False)
                print(f"  已终止占用 {port} 端口的进程 (PID {pid})")
    except Exception:
        pass


def main() -> None:
    procs: list[subprocess.Popen] = []

    print("=" * 52)
    print("  DataSpace P2P Demo")
    print("=" * 52)

    # 释放端口
    print("\n清理端口…")
    for a in AGENTS:
        kill_port(a["port"])
    time.sleep(0.5)

    for a in AGENTS:
        cmd = [sys.executable, str(SCRIPT), "--port", str(a["port"]), "--name", a["name"]]
        p = subprocess.Popen(cmd)
        procs.append(p)
        print(f"  启动 {a['name']}  →  http://localhost:{a['port']}")

    print()
    time.sleep(1.5)

    for a in AGENTS:
        webbrowser.open(f"http://localhost:{a['port']}")

    print("两个节点已就绪，浏览器标签已自动打开。")
    print()
    print("演示步骤：")
    print("  1. 在任意节点的「共享文件」Tab 上传文件")
    print("  2. 在「互信管理」Tab 输入对方地址发起互信")
    print("     Agent-1 → http://localhost:8025")
    print("     Agent-2 → http://localhost:8026")
    print("  3. 对方页面出现角标，点击「接受」")
    print("  4. 互信建立后点击「浏览文件」→「获取」")
    print()
    print("按 Ctrl+C 停止所有节点")
    print()

    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        print("\n正在停止节点…")
        for p in procs:
            p.terminate()
        for p in procs:
            p.wait()
        print("已停止。")


if __name__ == "__main__":
    main()
