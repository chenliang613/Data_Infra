"""
Tests for the P2P Agent node API.

We patch sys.argv before importing the module so that argparse does not
try to parse pytest's own command-line arguments.
"""
from __future__ import annotations

import io
import sys
import importlib
from pathlib import Path

import pytest
from starlette.testclient import TestClient

# ---------------------------------------------------------------------------
# Module-level setup: isolate the agent module with a fixed port/name
# ---------------------------------------------------------------------------

# Patch argv so argparse inside p2p_agent.py gets predictable defaults.
sys.argv = ["p2p_agent.py", "--port", "9999", "--name", "TestAgent"]

# Ensure the demo package is importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import demo.p2p_agent as agent_mod  # noqa: E402

client = TestClient(agent_mod.app)


@pytest.fixture(autouse=True)
def reset_state():
    """Clear in-memory state between tests."""
    agent_mod.shared_files.clear()
    agent_mod.received_files.clear()
    agent_mod.peers.clear()
    agent_mod.access_log.clear()
    agent_mod.market_offers.clear()
    agent_mod.market_wants.clear()
    # Remove any files created during a test
    for d in (agent_mod.SHARED_DIR, agent_mod.RECEIVED_DIR):
        if d.exists():
            for f in d.iterdir():
                f.unlink(missing_ok=True)
    yield


# ---------------------------------------------------------------------------
# /api/info
# ---------------------------------------------------------------------------

def test_info():
    resp = client.get("/api/info")
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_id"] == "agent-9999"
    assert data["name"] == "TestAgent"
    assert data["port"] == 9999


# ---------------------------------------------------------------------------
# Shared files
# ---------------------------------------------------------------------------

def test_list_shared_empty():
    resp = client.get("/api/shared")
    assert resp.status_code == 200
    assert resp.json() == []


def test_upload_and_list_shared():
    content = b"hello world"
    resp = client.post(
        "/api/shared/upload",
        files={"file": ("test.txt", io.BytesIO(content), "text/plain")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "test.txt"
    assert data["size"] == len(content)
    assert "id" in data

    listed = client.get("/api/shared").json()
    assert len(listed) == 1
    assert listed[0]["id"] == data["id"]


def test_delete_shared_removes_file():
    content = b"delete me"
    upload_resp = client.post(
        "/api/shared/upload",
        files={"file": ("todelete.txt", io.BytesIO(content), "text/plain")},
    )
    assert upload_resp.status_code == 200
    file_id = upload_resp.json()["id"]
    file_path = Path(upload_resp.json()["path"])

    # File should exist on disk after upload
    assert file_path.exists()

    del_resp = client.delete(f"/api/shared/{file_id}")
    assert del_resp.status_code == 200
    assert del_resp.json() == {"ok": True}

    # File must be removed from disk
    assert not file_path.exists()

    # File must be removed from the in-memory list
    assert client.get("/api/shared").json() == []


def test_delete_shared_not_found():
    resp = client.delete("/api/shared/nonexistent")
    assert resp.status_code == 404


def test_raw_shared_preview():
    content = b"preview content"
    upload_resp = client.post(
        "/api/shared/upload",
        files={"file": ("preview.txt", io.BytesIO(content), "text/plain")},
    )
    file_id = upload_resp.json()["id"]

    resp = client.get(f"/api/shared/{file_id}/raw")
    assert resp.status_code == 200
    assert resp.content == content


def test_download_shared():
    content = b"download content"
    upload_resp = client.post(
        "/api/shared/upload",
        files={"file": ("dl.txt", io.BytesIO(content), "text/plain")},
    )
    file_id = upload_resp.json()["id"]

    resp = client.get(f"/api/shared/{file_id}/download")
    assert resp.status_code == 200
    assert resp.content == content


# ---------------------------------------------------------------------------
# Received files
# ---------------------------------------------------------------------------

def test_list_received_empty():
    resp = client.get("/api/received")
    assert resp.status_code == 200
    assert resp.json() == []


def test_delete_received_not_found():
    resp = client.delete("/api/received/nonexistent")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Peers
# ---------------------------------------------------------------------------

def test_list_peers_empty():
    resp = client.get("/api/peers")
    assert resp.status_code == 200
    assert resp.json() == []


def test_accept_peer_no_pending_request():
    resp = client.post("/api/peers/ghost/accept")
    assert resp.status_code == 400


def test_reject_peer_not_found():
    resp = client.post("/api/peers/ghost/reject")
    assert resp.status_code == 404


def test_remove_peer_noop():
    resp = client.delete("/api/peers/ghost")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


# ---------------------------------------------------------------------------
# Internal trust endpoints
# ---------------------------------------------------------------------------

def test_internal_trust_request():
    payload = {
        "agent_id": "agent-1111",
        "name": "Peer1",
        "endpoint": "http://localhost:1111",
        "trust_level": "high",
        "message": "hi",
    }
    resp = client.post("/internal/trust-request", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_id"] == agent_mod.AGENT_ID

    peer = agent_mod.peers["agent-1111"]
    assert peer["status"] == "pending_in"
    assert peer["trust_level"] == "high"


def test_internal_trust_accepted():
    payload = {
        "agent_id": "agent-2222",
        "name": "Peer2",
        "endpoint": "http://localhost:2222",
        "trust_level": "normal",
        "message": "",
    }
    resp = client.post("/internal/trust-accepted", json=payload)
    assert resp.status_code == 200
    assert agent_mod.peers["agent-2222"]["status"] == "trusted"


def test_internal_trust_rejected():
    # Seed a peer first
    _seed_peer("agent-3333", 3333, status="pending_out")
    payload = {
        "agent_id": "agent-3333",
        "name": "Peer3",
        "endpoint": "http://localhost:3333",
        "trust_level": "high",
        "message": "",
    }
    resp = client.post("/internal/trust-rejected", json=payload)
    assert resp.status_code == 200
    assert agent_mod.peers["agent-3333"]["status"] == "rejected"


def test_internal_shared_files_untrusted():
    resp = client.get("/internal/shared-files", params={"from_id": "unknown"})
    assert resp.status_code == 403


def test_internal_shared_files_trusted():
    _seed_peer("agent-4444", 4444)
    resp = client.get("/internal/shared-files", params={"from_id": "agent-4444"})
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Access log
# ---------------------------------------------------------------------------

def test_access_log_empty():
    resp = client.get("/api/access-log")
    assert resp.status_code == 200
    assert resp.json() == []


def test_access_log_records_preview():
    content = b"log test"
    upload_resp = client.post(
        "/api/shared/upload",
        files={"file": ("logtest.txt", io.BytesIO(content), "text/plain")},
    )
    file_id = upload_resp.json()["id"]
    client.get(f"/api/shared/{file_id}/raw")

    log = client.get("/api/access-log").json()
    assert len(log) >= 1
    assert log[0]["event"] == "local_preview"
    assert log[0]["file_id"] == file_id


# ---------------------------------------------------------------------------
# Data market
# ---------------------------------------------------------------------------

def test_market_empty():
    resp = client.get("/api/market")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"offers": [], "wants": []}


def test_publish_and_remove_offer():
    content = b"market file"
    upload_resp = client.post(
        "/api/shared/upload",
        files={"file": ("market.txt", io.BytesIO(content), "text/plain")},
    )
    file_id = upload_resp.json()["id"]

    offer_resp = client.post(
        "/api/market/offers",
        json={"file_id": file_id, "description": "great data"},
    )
    assert offer_resp.status_code == 200
    offer = offer_resp.json()
    assert offer["name"] == "market.txt"

    market = client.get("/api/market").json()
    assert len(market["offers"]) == 1

    del_resp = client.delete(f"/api/market/offers/{offer['id']}")
    assert del_resp.status_code == 200
    assert client.get("/api/market").json()["offers"] == []


def test_publish_offer_missing_file():
    resp = client.post(
        "/api/market/offers",
        json={"file_id": "does-not-exist", "description": ""},
    )
    assert resp.status_code == 404


def test_publish_and_remove_want():
    want_resp = client.post(
        "/api/market/wants",
        json={"title": "Need CSV data", "description": "any format"},
    )
    assert want_resp.status_code == 200
    want = want_resp.json()
    assert want["title"] == "Need CSV data"

    market = client.get("/api/market").json()
    assert len(market["wants"]) == 1

    del_resp = client.delete(f"/api/market/wants/{want['id']}")
    assert del_resp.status_code == 200
    assert client.get("/api/market").json()["wants"] == []


def test_remove_want_not_found():
    resp = client.delete("/api/market/wants/nonexistent")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_peer(agent_id: str, port: int, status: str = "trusted", trust_level: str = "high"):
    """Insert a peer entry directly into the in-memory peers dict."""
    agent_mod.peers[agent_id] = {
        "id": agent_id,
        "name": f"Peer-{port}",
        "endpoint": f"http://localhost:{port}",
        "status": status,
        "trust_level": trust_level,
    }



def test_index_returns_html():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "TestAgent" in resp.text
