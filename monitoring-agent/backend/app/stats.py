"""
monitoring-agent/backend/app/stats.py

CPU%/memory math and snapshot normalisation. Pure functions over the raw
Docker-format stats JSON (as returned by `container.stats(stream=False)` /
the socket-proxy) so they can be unit-tested against captured blobs without a
socket.

CPU% uses the standard Docker delta formula:

    cpuDelta    = cpu_total_usage      - precpu_total_usage
    systemDelta = cpu_system_usage     - precpu_system_usage
    onlineCPUs  = online_cpus | len(percpu_usage) | 1
    cpu%        = (cpuDelta / systemDelta) * onlineCPUs * 100

If precpu is absent/zero on a snapshot (e.g. the very first sample, or Podman
not emitting it), `systemDelta`/`cpuDelta` are non-positive and we return 0 for
that sample rather than dividing by zero.

Memory: `usage - cache` (when `stats.cache` is present, matching `docker stats`),
clamped to >= 0. A `0` limit means unlimited; memPct is then 0.
"""
from __future__ import annotations

from typing import Any, Dict


def _g(d: Any, *keys: str, default: Any = 0) -> Any:
    """Safe nested getter: _g(stats, "cpu_stats", "cpu_usage", "total_usage")."""
    cur = d
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def calc_cpu_pct(stats: Dict[str, Any]) -> float:
    """Standard Docker CPU% delta formula. Returns 0.0 if precpu is missing."""
    cpu_total = _g(stats, "cpu_stats", "cpu_usage", "total_usage")
    pre_total = _g(stats, "precpu_stats", "cpu_usage", "total_usage")
    cpu_system = _g(stats, "cpu_stats", "system_cpu_usage")
    pre_system = _g(stats, "precpu_stats", "system_cpu_usage")

    # "precpu absent on a snapshot" (§3): Docker/Podman emit precpu_stats with a
    # zero system_cpu_usage on the very first read (no prior baseline). Treat a
    # missing/zero pre_system as no baseline and return 0 for that sample rather
    # than computing a bogus rate off a zero precpu.
    if float(pre_system) <= 0.0:
        return 0.0

    cpu_delta = float(cpu_total) - float(pre_total)
    system_delta = float(cpu_system) - float(pre_system)

    # No usable delta (clock went backwards / identical samples) -> 0.
    if system_delta <= 0.0 or cpu_delta < 0.0:
        return 0.0

    online_cpus = _g(stats, "cpu_stats", "online_cpus", default=0)
    if not online_cpus:
        percpu = _g(stats, "cpu_stats", "cpu_usage", "percpu_usage", default=None)
        online_cpus = len(percpu) if isinstance(percpu, list) and percpu else 1

    pct = (cpu_delta / system_delta) * float(online_cpus) * 100.0
    return round(pct, 1)


def calc_mem(stats: Dict[str, Any]) -> Dict[str, Any]:
    """Return {usedBytes, limitBytes, pct} from a Docker-format stats blob.

    Mirrors `docker stats`: used = usage - cache (cache subtracted when present).
    """
    usage = int(_g(stats, "memory_stats", "usage"))
    limit = int(_g(stats, "memory_stats", "limit"))

    # `docker stats` subtracts the page cache from RSS for the headline figure.
    # Podman exposes it under memory_stats.stats.cache (older) or .inactive_file.
    cache = _g(stats, "memory_stats", "stats", "cache", default=None)
    if cache is None:
        cache = _g(stats, "memory_stats", "stats", "inactive_file", default=0)
    used = usage - int(cache)
    if used < 0:
        used = usage  # cache larger than usage shouldn't happen; fall back to raw

    pct = 0.0
    if limit > 0:
        pct = round((used / limit) * 100.0, 1)

    return {"usedBytes": used, "limitBytes": limit, "pct": pct}


def calc_net(stats: Dict[str, Any]) -> Dict[str, int]:
    """Sum rx/tx bytes across all interfaces in the `networks` map."""
    rx = 0
    tx = 0
    networks = stats.get("networks") if isinstance(stats, dict) else None
    if isinstance(networks, dict):
        for iface in networks.values():
            if isinstance(iface, dict):
                rx += int(iface.get("rx_bytes", 0) or 0)
                tx += int(iface.get("tx_bytes", 0) or 0)
    return {"rxBytes": rx, "txBytes": tx}


def calc_pids(stats: Dict[str, Any]) -> int:
    return int(_g(stats, "pids_stats", "current"))


def normalise_stats(name: str, stats: Dict[str, Any]) -> Dict[str, Any]:
    """Turn a raw stats blob into the §3 ContainerStats shape for an online ctr."""
    mem = calc_mem(stats)
    net = calc_net(stats)
    return {
        "name": name,
        "online": True,
        "cpuPct": calc_cpu_pct(stats),
        "memUsedBytes": mem["usedBytes"],
        "memLimitBytes": mem["limitBytes"],
        "memPct": mem["pct"],
        "netRxBytes": net["rxBytes"],
        "netTxBytes": net["txBytes"],
        "pids": calc_pids(stats),
    }


def offline_stats(name: str) -> Dict[str, Any]:
    """The §3 ContainerStats shape for a stopped container: all numerics 0."""
    return {
        "name": name,
        "online": False,
        "cpuPct": 0.0,
        "memUsedBytes": 0,
        "memLimitBytes": 0,
        "memPct": 0.0,
        "netRxBytes": 0,
        "netTxBytes": 0,
        "pids": 0,
    }
