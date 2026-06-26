"""Tests for app.stats — CPU%/mem math against captured Docker-format blobs."""
from app import stats


# A realistic Docker/Podman `stats(stream=False)` snapshot.
#   cpuDelta    = 100_000_000 - 90_000_000   = 10_000_000
#   systemDelta = 1_000_000_000 - 900_000_000 = 100_000_000
#   onlineCPUs  = 2
#   cpu%        = 10_000_000/100_000_000 * 2 * 100 = 20.0
#   memUsed     = 1_610_612_736 - 107_374_182 = 1_503_238_554
#   memPct      = 1_503_238_554 / 2_147_483_648 = 70.0
SAMPLE = {
    "cpu_stats": {
        "cpu_usage": {"total_usage": 100_000_000, "percpu_usage": [5, 5]},
        "system_cpu_usage": 1_000_000_000,
        "online_cpus": 2,
    },
    "precpu_stats": {
        "cpu_usage": {"total_usage": 90_000_000},
        "system_cpu_usage": 900_000_000,
    },
    "memory_stats": {
        "usage": 1_610_612_736,
        "limit": 2_147_483_648,
        "stats": {"cache": 107_374_182},
    },
    "networks": {
        "eth0": {"rx_bytes": 12345, "tx_bytes": 6789},
        "eth1": {"rx_bytes": 1, "tx_bytes": 2},
    },
    "pids_stats": {"current": 24},
}


def test_cpu_pct_standard_delta_formula():
    assert stats.calc_cpu_pct(SAMPLE) == 20.0


def test_cpu_pct_zero_when_precpu_absent():
    # First sample: no precpu -> systemDelta computed against 0 -> guard returns 0
    blob = {
        "cpu_stats": {
            "cpu_usage": {"total_usage": 100_000_000},
            "system_cpu_usage": 1_000_000_000,
            "online_cpus": 2,
        },
        "precpu_stats": {},  # missing
        "memory_stats": {"usage": 1, "limit": 2},
    }
    assert stats.calc_cpu_pct(blob) == 0.0


def test_cpu_pct_uses_percpu_len_when_online_cpus_missing():
    blob = {
        "cpu_stats": {
            "cpu_usage": {
                "total_usage": 100_000_000,
                "percpu_usage": [1, 1, 1, 1],  # 4 CPUs
            },
            "system_cpu_usage": 1_000_000_000,
            # online_cpus omitted on purpose
        },
        "precpu_stats": {
            "cpu_usage": {"total_usage": 90_000_000},
            "system_cpu_usage": 900_000_000,
        },
    }
    # (10M/100M) * 4 * 100 = 40.0
    assert stats.calc_cpu_pct(blob) == 40.0


def test_mem_subtracts_cache_and_computes_pct():
    mem = stats.calc_mem(SAMPLE)
    assert mem["usedBytes"] == 1_503_238_554
    assert mem["limitBytes"] == 2_147_483_648
    assert mem["pct"] == 70.0


def test_mem_unlimited_limit_yields_zero_pct():
    blob = {"memory_stats": {"usage": 1000, "limit": 0}}
    mem = stats.calc_mem(blob)
    assert mem["limitBytes"] == 0
    assert mem["pct"] == 0.0


def test_mem_inactive_file_used_when_no_cache_key():
    blob = {
        "memory_stats": {
            "usage": 1000,
            "limit": 2000,
            "stats": {"inactive_file": 200},
        }
    }
    mem = stats.calc_mem(blob)
    assert mem["usedBytes"] == 800
    assert mem["pct"] == 40.0


def test_net_sums_all_interfaces():
    net = stats.calc_net(SAMPLE)
    assert net["rxBytes"] == 12346
    assert net["txBytes"] == 6791


def test_normalise_produces_full_online_shape():
    out = stats.normalise_stats("compliance-backend", SAMPLE)
    assert out == {
        "name": "compliance-backend",
        "online": True,
        "cpuPct": 20.0,
        "memUsedBytes": 1_503_238_554,
        "memLimitBytes": 2_147_483_648,
        "memPct": 70.0,
        "netRxBytes": 12346,
        "netTxBytes": 6791,
        "pids": 24,
    }


def test_offline_shape_is_all_zero():
    out = stats.offline_stats("seo-backend")
    assert out["online"] is False
    for key in ("cpuPct", "memUsedBytes", "memLimitBytes", "memPct", "netRxBytes", "netTxBytes", "pids"):
        assert out[key] == 0
