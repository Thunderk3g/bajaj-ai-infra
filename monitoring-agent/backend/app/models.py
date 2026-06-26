"""
monitoring-agent/backend/app/models.py

Pydantic response models — the backend half of the §3 API contract.
Field names here MUST match the frontend `types.ts` exactly; any drift is a bug.
All timestamps are RFC3339 UTC strings, byte counts are integers, and a `0`
memory limit means "unlimited".
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


# ── GET /agents ────────────────────────────────────────────────────────────
class AgentSummary(BaseModel):
    id: str
    label: str
    prefix: str
    containers: int
    running: int
    totalMemBytes: int
    aggCpuPct: float


class AgentsResponse(BaseModel):
    generatedAt: str
    agents: List[AgentSummary]


# ── GET /containers?agent=<id> ─────────────────────────────────────────────
class ContainerInfo(BaseModel):
    id: str
    name: str
    image: str
    state: str          # running|exited|paused|created|restarting|dead
    status: str
    startedAt: Optional[str] = None
    restartCount: int
    health: str         # healthy|unhealthy|starting|none
    memLimitBytes: int
    ports: List[str]


class ContainersResponse(BaseModel):
    agent: str
    containers: List[ContainerInfo]


# ── GET /stats?agent=<id> ──────────────────────────────────────────────────
class ContainerStats(BaseModel):
    name: str
    online: bool
    cpuPct: float
    memUsedBytes: int
    memLimitBytes: int
    memPct: float
    netRxBytes: int
    netTxBytes: int
    pids: int


class StatsResponse(BaseModel):
    agent: str
    generatedAt: str
    stats: List[ContainerStats]


# ── GET /containers/{name}/logs ────────────────────────────────────────────
class LogLine(BaseModel):
    ts: Optional[str] = None
    text: str


class LogsResponse(BaseModel):
    name: str
    lines: List[LogLine]


# ── GET /health ────────────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str
    engine: str
    containersVisible: int
