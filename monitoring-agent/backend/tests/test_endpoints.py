"""Endpoint tests via FastAPI TestClient with a FAKE engine injected.

No real socket is ever opened: `engine.set_engine(FakeEngine())` swaps the
read-only adapter for an in-memory fake. This is the contract guard for §3.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app import engine as engine_mod
from app.main import app


# ── Fake engine implementing the MonitorEngine read-only surface ───────────
class FakeEngine:
    def __init__(self):
        self._containers = [
            {
                "id": "abc123def456",
                "name": "compliance-backend",
                "image": "localhost/compliance-backend:latest",
                "state": "running",
                "status": "Up 6 hours",
                "startedAt": "2026-06-26T06:00:00Z",
                "restartCount": 0,
                "health": "healthy",
                "memLimitBytes": 2147483648,
                "ports": ["8000/tcp"],
            },
            {
                "id": "def789aaa111",
                "name": "compliance-frontend",
                "image": "localhost/compliance-frontend:latest",
                "state": "exited",
                "status": "Exited (0)",
                "startedAt": None,
                "restartCount": 1,
                "health": "none",
                "memLimitBytes": 0,
                "ports": ["3000/tcp"],
            },
            {
                "id": "seo000seo000",
                "name": "seo-backend",
                "image": "localhost/seo-backend:latest",
                "state": "running",
                "status": "Up 1 hour",
                "startedAt": "2026-06-26T11:00:00Z",
                "restartCount": 0,
                "health": "starting",
                "memLimitBytes": 1073741824,
                "ports": ["8001/tcp"],
            },
        ]

    def health(self):
        return {"status": "ok", "engine": "podman", "containersVisible": len(self._containers)}

    def list_containers(self):
        return [dict(c) for c in self._containers]

    def stats_for(self, agent_id):
        out = []
        for c in self._containers:
            from app import grouping
            if grouping.classify(c["name"]).id != agent_id:
                continue
            if c["state"] != "running":
                out.append({
                    "name": c["name"], "online": False, "cpuPct": 0.0,
                    "memUsedBytes": 0, "memLimitBytes": 0, "memPct": 0.0,
                    "netRxBytes": 0, "netTxBytes": 0, "pids": 0,
                })
            else:
                out.append({
                    "name": c["name"], "online": True, "cpuPct": 38.4,
                    "memUsedBytes": 1503238553, "memLimitBytes": c["memLimitBytes"],
                    "memPct": 70.0, "netRxBytes": 12345, "netTxBytes": 6789, "pids": 24,
                })
        return out

    def logs(self, name, tail):
        if not any(c["name"] == name for c in self._containers):
            raise engine_mod.ContainerNotFound(name)
        return [
            {"ts": "2026-06-26T12:04:01Z", "text": "INFO started"},
            {"ts": "2026-06-26T12:04:02Z", "text": "INFO ready"},
        ][-tail:]

    def follow_logs(self, name, tail):
        if not any(c["name"] == name for c in self._containers):
            raise engine_mod.ContainerNotFound(name)
        yield {"ts": "2026-06-26T12:04:03Z", "text": "INFO tick"}


class UnreachableEngine:
    def health(self):
        raise engine_mod.EngineUnreachable("boom")

    def list_containers(self):
        raise engine_mod.EngineUnreachable("boom")

    def stats_for(self, agent_id):
        raise engine_mod.EngineUnreachable("boom")

    def logs(self, name, tail):
        raise engine_mod.EngineUnreachable("boom")

    def follow_logs(self, name, tail):
        raise engine_mod.EngineUnreachable("boom")
        yield  # pragma: no cover


@pytest.fixture
def client():
    engine_mod.set_engine(FakeEngine())
    with TestClient(app) as c:
        yield c
    engine_mod.set_engine(None)


# ── /health ────────────────────────────────────────────────────────────────
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "engine": "podman", "containersVisible": 3}


# ── /agents ─────────────────────────────────────────────────────────────────
def test_agents_shape_and_aggregation(client):
    r = client.get("/agents")
    assert r.status_code == 200
    body = r.json()
    assert "generatedAt" in body
    agents = {a["id"]: a for a in body["agents"]}
    # every real group present even if empty
    assert {"compliance", "seo", "shared", "landing", "monitoring"} <= set(agents)
    comp = agents["compliance"]
    assert comp["label"] == "Regulatory Compliance"
    assert comp["prefix"] == "compliance-"
    assert comp["containers"] == 2
    assert comp["running"] == 1
    assert comp["totalMemBytes"] == 2147483648  # frontend has 0 limit
    assert comp["aggCpuPct"] == 38.4
    # empty group has zeroed aggregates
    assert agents["landing"]["containers"] == 0
    assert agents["landing"]["aggCpuPct"] == 0.0


# ── /containers ─────────────────────────────────────────────────────────────
def test_containers_filtered_by_agent(client):
    r = client.get("/containers", params={"agent": "compliance"})
    assert r.status_code == 200
    body = r.json()
    assert body["agent"] == "compliance"
    names = [c["name"] for c in body["containers"]]
    assert names == ["compliance-backend", "compliance-frontend"]
    first = body["containers"][0]
    # §3 field contract
    for key in ("id", "name", "image", "state", "status", "startedAt",
                "restartCount", "health", "memLimitBytes", "ports"):
        assert key in first


def test_containers_unknown_agent_400(client):
    r = client.get("/containers", params={"agent": "bogus"})
    assert r.status_code == 400
    assert r.json() == {"error": "unknown_agent"}


# ── /stats ──────────────────────────────────────────────────────────────────
def test_stats_shape(client):
    r = client.get("/stats", params={"agent": "compliance"})
    assert r.status_code == 200
    body = r.json()
    assert body["agent"] == "compliance"
    assert "generatedAt" in body
    by_name = {s["name"]: s for s in body["stats"]}
    assert by_name["compliance-backend"]["online"] is True
    assert by_name["compliance-backend"]["cpuPct"] == 38.4
    assert by_name["compliance-frontend"]["online"] is False
    assert by_name["compliance-frontend"]["cpuPct"] == 0.0


def test_stats_unknown_agent_400(client):
    r = client.get("/stats", params={"agent": "bogus"})
    assert r.status_code == 400
    assert r.json() == {"error": "unknown_agent"}


# ── /containers/{name}/logs ─────────────────────────────────────────────────
def test_logs_ok(client):
    r = client.get("/containers/compliance-backend/logs")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "compliance-backend"
    assert body["lines"][0] == {"ts": "2026-06-26T12:04:01Z", "text": "INFO started"}


def test_logs_tail_clamped(client):
    r = client.get("/containers/compliance-backend/logs", params={"tail": 1})
    assert r.status_code == 200
    assert len(r.json()["lines"]) == 1


def test_logs_container_not_found_404(client):
    r = client.get("/containers/nope/logs")
    assert r.status_code == 404
    assert r.json() == {"error": "container_not_found"}


# ── SSE stream ──────────────────────────────────────────────────────────────
def test_logs_stream_sse(client):
    with client.stream("GET", "/containers/compliance-backend/logs/stream") as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        body = "".join(chunk for chunk in r.iter_text())
    assert 'data: ' in body
    # the single fake line is delivered before the stream closes
    assert '"text": "INFO tick"' in body or '"text":"INFO tick"' in body


def test_logs_stream_container_not_found_emits_error_event(client):
    with client.stream("GET", "/containers/nope/logs/stream") as r:
        assert r.status_code == 200
        body = "".join(chunk for chunk in r.iter_text())
    assert "event: error" in body
    assert "container_not_found" in body


# ── engine unreachable -> 502 ───────────────────────────────────────────────
def test_engine_unreachable_502():
    engine_mod.set_engine(UnreachableEngine())
    with TestClient(app) as c:
        r = c.get("/health")
        assert r.status_code == 502
        assert r.json() == {"error": "engine_unreachable"}
    engine_mod.set_engine(None)
