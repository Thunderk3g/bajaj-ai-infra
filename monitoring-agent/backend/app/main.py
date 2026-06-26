"""
monitoring-agent/backend/app/main.py

FastAPI app + routes for the read-only agent monitoring service. Served at
/monitoring/api/ via shared-nginx (which strips the prefix), so routes here live
at the root. CORS is off on purpose — everything is same-origin through nginx.

Endpoints and JSON shapes are frozen by §3 of the design spec. The engine is
obtained via `engine.get_engine()` so tests can inject a fake with
`engine.set_engine(...)` and never touch a real socket.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import anyio
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from . import engine as engine_mod
from . import grouping
from .models import (
    AgentsResponse,
    ContainersResponse,
    HealthResponse,
    LogsResponse,
    StatsResponse,
)

app = FastAPI(title="Bajaj AI Monitoring", docs_url="/docs", redoc_url=None)

DEFAULT_TAIL = 500
MAX_TAIL = 2000
HEARTBEAT_SECS = 20.0


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clamp_tail(tail: int) -> int:
    if tail < 1:
        return 1
    return min(tail, MAX_TAIL)


# ── error helpers (never leak raw engine errors — §3 "Errors") ─────────────
def _err(status: int, code: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


@app.exception_handler(engine_mod.EngineUnreachable)
async def _engine_unreachable_handler(_req: Request, _exc: Exception):
    return _err(502, "engine_unreachable")


@app.exception_handler(engine_mod.ContainerNotFound)
async def _container_not_found_handler(_req: Request, _exc: Exception):
    return _err(404, "container_not_found")


# ── routes ─────────────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse)
def health() -> Dict[str, Any]:
    return engine_mod.get_engine().health()


@app.get("/agents", response_model=AgentsResponse)
def agents() -> Dict[str, Any]:
    containers = engine_mod.get_engine().list_containers()

    # Seed every real group so empty agents still appear; `other` only if used.
    buckets: Dict[str, Dict[str, Any]] = {
        g.id: {"group": g, "containers": 0, "running": 0, "mem": 0}
        for g in grouping.GROUPS
    }
    for c in containers:
        group = grouping.classify(c["name"])
        if group.id not in buckets:
            buckets[group.id] = {"group": group, "containers": 0, "running": 0, "mem": 0}
        b = buckets[group.id]
        b["containers"] += 1
        if c["state"] == "running":
            b["running"] += 1
        b["mem"] += int(c.get("memLimitBytes", 0) or 0)

    # aggCpuPct comes from a one-shot stats poll per group with containers.
    agg_cpu: Dict[str, float] = {}
    eng = engine_mod.get_engine()
    for agent_id, b in buckets.items():
        if b["running"] == 0:
            agg_cpu[agent_id] = 0.0
            continue
        try:
            snap = eng.stats_for(agent_id)
        except engine_mod.EngineUnreachable:
            snap = []
        agg_cpu[agent_id] = round(sum(s.get("cpuPct", 0.0) for s in snap), 1)

    out: List[Dict[str, Any]] = []
    for agent_id, b in buckets.items():
        g = b["group"]
        out.append(
            {
                "id": g.id,
                "label": g.label,
                "prefix": g.prefix,
                "containers": b["containers"],
                "running": b["running"],
                "totalMemBytes": b["mem"],
                "aggCpuPct": agg_cpu.get(agent_id, 0.0),
            }
        )
    return {"generatedAt": _now(), "agents": out}


@app.get("/containers", response_model=ContainersResponse)
def containers(agent: str = Query(...)):
    if not grouping.is_known_agent(agent):
        return _err(400, "unknown_agent")
    all_containers = engine_mod.get_engine().list_containers()
    matched = [c for c in all_containers if grouping.classify(c["name"]).id == agent]
    return {"agent": agent, "containers": matched}


@app.get("/stats", response_model=StatsResponse)
def stats(agent: str = Query(...)):
    if not grouping.is_known_agent(agent):
        return _err(400, "unknown_agent")
    snap = engine_mod.get_engine().stats_for(agent)
    return {"agent": agent, "generatedAt": _now(), "stats": snap}


@app.get("/containers/{name}/logs", response_model=LogsResponse)
def container_logs(name: str, tail: int = Query(DEFAULT_TAIL)):
    lines = engine_mod.get_engine().logs(name, _clamp_tail(tail))
    return {"name": name, "lines": lines}


@app.get("/containers/{name}/logs/stream")
async def container_logs_stream(name: str, request: Request, tail: int = Query(DEFAULT_TAIL)):
    """SSE stream: wraps the blocking follow generator in a threadpool, emits
    `: ping` heartbeats ~every 20s, and tolerates client disconnect."""
    eng = engine_mod.get_engine()
    clamped = _clamp_tail(tail)

    async def event_source():
        # Bridge the blocking generator into async via a thread + queue so the
        # event loop stays free for heartbeats and disconnect detection.
        queue: "asyncio.Queue[Any]" = asyncio.Queue(maxsize=1000)
        loop = asyncio.get_running_loop()
        _SENTINEL = object()

        def producer():
            try:
                for line in eng.follow_logs(name, clamped):
                    loop.call_soon_threadsafe(queue.put_nowait, line)
            except engine_mod.ContainerNotFound:
                loop.call_soon_threadsafe(
                    queue.put_nowait, {"__error__": "container_not_found"}
                )
            except engine_mod.EngineUnreachable:
                loop.call_soon_threadsafe(
                    queue.put_nowait, {"__error__": "engine_unreachable"}
                )
            except Exception:  # noqa: BLE001 - never leak raw engine errors
                loop.call_soon_threadsafe(
                    queue.put_nowait, {"__error__": "engine_unreachable"}
                )
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, _SENTINEL)

        producer_task = asyncio.ensure_future(anyio.to_thread.run_sync(producer))
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECS)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"  # comment heartbeat
                    continue
                if item is _SENTINEL:
                    break
                if isinstance(item, dict) and "__error__" in item:
                    yield "event: error\n" + "data: " + json.dumps(
                        {"error": item["__error__"]}
                    ) + "\n\n"
                    break
                yield "data: " + json.dumps(item) + "\n\n"
        finally:
            producer_task.cancel()

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
