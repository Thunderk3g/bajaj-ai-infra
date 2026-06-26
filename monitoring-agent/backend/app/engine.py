"""
monitoring-agent/backend/app/engine.py

Read-only adapter over the Docker-compatible REST API exposed by the
tecnativa/docker-socket-proxy in front of the rootful Podman socket.

ONLY read calls are ever issued:
  * client.containers.list(all=True)
  * container.stats(stream=False)
  * container.logs(...)
There is deliberately NO start/stop/restart/exec anywhere in this module — and
the socket-proxy is configured with POST=0 so writes are rejected at the proxy
even if code tried.

The concrete `DockerEngine` is constructed lazily (so importing this module does
NOT open a socket) and is swappable: `set_engine()` / `get_engine()` let tests
inject a fake engine, and `main.py` depends on `get_engine()` so the FastAPI
TestClient never touches a real socket.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Iterator, List, Optional, Protocol

from . import grouping, stats as stats_mod


class EngineUnreachable(Exception):
    """Raised when the engine/socket-proxy cannot be reached. -> 502."""


class ContainerNotFound(Exception):
    """Raised when a named container does not exist. -> 404."""


class MonitorEngine(Protocol):
    """The minimal read-only surface main.py depends on (real or fake)."""

    def health(self) -> Dict[str, Any]: ...
    def list_containers(self) -> List[Dict[str, Any]]: ...
    def stats_for(self, agent_id: str) -> List[Dict[str, Any]]: ...
    def logs(self, name: str, tail: int) -> List[Dict[str, Any]]: ...
    def follow_logs(self, name: str, tail: int) -> Iterator[Dict[str, Any]]: ...


# ── RFC3339 log-stamp splitting ────────────────────────────────────────────
def split_log_line(raw: str) -> Dict[str, Optional[str]]:
    """Split the leading RFC3339 timestamp (logs are requested with timestamps).

    Docker/Podman prefix each line with an RFC3339Nano stamp + a single space,
    e.g. ``2026-06-26T12:04:01.123456789Z INFO started``. We peel the stamp into
    `ts` and keep the remainder as `text`. Lines without a parseable stamp keep
    `ts=None`.
    """
    line = raw.rstrip("\n").rstrip("\r")
    if not line:
        return {"ts": None, "text": ""}
    head, sep, rest = line.partition(" ")
    if sep and _looks_like_rfc3339(head):
        return {"ts": head, "text": rest}
    return {"ts": None, "text": line}


def _looks_like_rfc3339(token: str) -> bool:
    # Cheap structural check; avoids a full parser on the hot path.
    # e.g. 2026-06-26T12:04:01.123456789Z  /  2026-06-26T12:04:01Z  /  ...+05:30
    if len(token) < 20 or token[4] != "-" or token[7] != "-" or token[10] != "T":
        return False
    return token[13] == ":" and token[16] == ":"


def _decode(chunk: Any) -> str:
    if isinstance(chunk, bytes):
        return chunk.decode("utf-8", "replace")
    return str(chunk)


# ── Concrete engine (talks to the socket-proxy via the docker SDK) ──────────
class DockerEngine:
    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = base_url or os.environ.get(
            "SOCKET_PROXY_URL", "tcp://socket-proxy:2375"
        )
        self._client = None  # lazy — do not open a socket at import/construct.

    def _client_or_raise(self):
        if self._client is None:
            try:
                import docker  # imported lazily so tests need not install it

                self._client = docker.DockerClient(base_url=self.base_url)
            except Exception as exc:  # noqa: BLE001 - never leak raw engine errors
                raise EngineUnreachable(str(exc)) from exc
        return self._client

    def _list_raw(self):
        try:
            return self._client_or_raise().containers.list(all=True)
        except EngineUnreachable:
            raise
        except Exception as exc:  # noqa: BLE001
            raise EngineUnreachable(str(exc)) from exc

    # -- health -------------------------------------------------------------
    def health(self) -> Dict[str, Any]:
        containers = self._list_raw()
        return {
            "status": "ok",
            "engine": "podman",
            "containersVisible": len(containers),
        }

    # -- list / inspect -----------------------------------------------------
    def list_containers(self) -> List[Dict[str, Any]]:
        """Return normalised §3 ContainerInfo dicts for every container."""
        out: List[Dict[str, Any]] = []
        for c in self._list_raw():
            out.append(self._to_container_info(c))
        return out

    @staticmethod
    def _to_container_info(c: Any) -> Dict[str, Any]:
        attrs = getattr(c, "attrs", {}) or {}
        state = attrs.get("State", {}) or {}
        config = attrs.get("Config", {}) or {}

        health = "none"
        health_obj = state.get("Health")
        if isinstance(health_obj, dict) and health_obj.get("Status"):
            health = health_obj["Status"]

        image = ""
        tags = getattr(getattr(c, "image", None), "tags", None)
        if tags:
            image = tags[0]
        else:
            image = config.get("Image") or attrs.get("Image") or ""

        return {
            "id": getattr(c, "id", "")[:12],
            "name": (getattr(c, "name", "") or "").lstrip("/"),
            "image": image,
            "state": state.get("Status") or getattr(c, "status", "") or "",
            "status": _status_text(c, attrs),
            "startedAt": _clean_ts(state.get("StartedAt")),
            "restartCount": int(state.get("RestartCount", 0) or 0),
            "health": health,
            "memLimitBytes": int(((attrs.get("HostConfig") or {}).get("Memory") or 0)),
            "ports": _port_list(attrs),
        }

    # -- stats --------------------------------------------------------------
    def stats_for(self, agent_id: str) -> List[Dict[str, Any]]:
        """Bulk snapshot for every container in `agent_id` (one poll)."""
        results: List[Dict[str, Any]] = []
        for c in self._list_raw():
            name = (getattr(c, "name", "") or "").lstrip("/")
            if grouping.classify(name).id != agent_id:
                continue
            state = (getattr(c, "attrs", {}) or {}).get("State", {}) or {}
            running = (state.get("Status") or getattr(c, "status", "")) == "running"
            if not running:
                results.append(stats_mod.offline_stats(name))
                continue
            try:
                raw = c.stats(stream=False)
            except Exception:  # noqa: BLE001 - a flapping container -> offline sample
                results.append(stats_mod.offline_stats(name))
                continue
            results.append(stats_mod.normalise_stats(name, raw))
        return results

    # -- logs ---------------------------------------------------------------
    def _find(self, name: str):
        for c in self._list_raw():
            if (getattr(c, "name", "") or "").lstrip("/") == name:
                return c
        raise ContainerNotFound(name)

    def logs(self, name: str, tail: int) -> List[Dict[str, Any]]:
        c = self._find(name)
        try:
            raw = c.logs(tail=tail, timestamps=True, stream=False)
        except Exception as exc:  # noqa: BLE001
            raise EngineUnreachable(str(exc)) from exc
        text = _decode(raw)
        lines = [ln for ln in text.split("\n") if ln != ""]
        return [split_log_line(ln) for ln in lines]

    def follow_logs(self, name: str, tail: int) -> Iterator[Dict[str, Any]]:
        """Blocking generator: yields parsed lines as they arrive (for SSE)."""
        c = self._find(name)
        try:
            stream = c.logs(
                tail=tail, timestamps=True, stream=True, follow=True
            )
        except Exception as exc:  # noqa: BLE001
            raise EngineUnreachable(str(exc)) from exc
        buffer = ""
        for chunk in stream:
            buffer += _decode(chunk)
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if line:
                    yield split_log_line(line)


# ── helpers for inspect normalisation ──────────────────────────────────────
def _clean_ts(ts: Optional[str]) -> Optional[str]:
    """Podman/Docker StartedAt; treat the zero-time as 'never started'."""
    if not ts or ts.startswith("0001-01-01"):
        return None
    return ts


def _status_text(c: Any, attrs: Dict[str, Any]) -> str:
    status = getattr(c, "status", None)
    if status and status not in ("running", "exited", "created"):
        return status
    # docker SDK exposes the human "Up 6 hours" string under attrs in some
    # backends; fall back to the bare state word.
    st = (attrs.get("State") or {})
    return st.get("Status") or status or ""


def _port_list(attrs: Dict[str, Any]) -> List[str]:
    ports = ((attrs.get("Config") or {}).get("ExposedPorts")) or {}
    if isinstance(ports, dict) and ports:
        return sorted(ports.keys())
    # Fall back to runtime NetworkSettings.Ports keys (e.g. "8000/tcp").
    net_ports = ((attrs.get("NetworkSettings") or {}).get("Ports")) or {}
    if isinstance(net_ports, dict) and net_ports:
        return sorted(net_ports.keys())
    return []


# ── injectable singleton ───────────────────────────────────────────────────
_engine: Optional[MonitorEngine] = None


def get_engine() -> MonitorEngine:
    """Return the process engine, constructing the real one on first use."""
    global _engine
    if _engine is None:
        _engine = DockerEngine()
    return _engine


def set_engine(engine: Optional[MonitorEngine]) -> None:
    """Swap the engine (tests inject a fake; pass None to reset)."""
    global _engine
    _engine = engine
