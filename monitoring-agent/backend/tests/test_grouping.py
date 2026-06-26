"""Tests for app.grouping — the name-prefix -> agent classifier (§3)."""
from app import grouping


def test_known_prefixes_map_to_their_group():
    cases = {
        "compliance-backend": "compliance",
        "compliance-frontend": "compliance",
        "seo-backend": "seo",
        "shared-postgres": "shared",
        "shared-nginx": "shared",
        "landing-frontend": "landing",
        "monitoring-backend": "monitoring",
    }
    for name, expected_id in cases.items():
        assert grouping.classify(name).id == expected_id


def test_unknown_prefix_falls_into_other():
    assert grouping.classify("random-thing").id == "other"
    assert grouping.classify("postgres").id == "other"
    assert grouping.classify("").id == "other"


def test_group_carries_label_and_prefix():
    g = grouping.classify("compliance-backend")
    assert g.label == "Regulatory Compliance"
    assert g.prefix == "compliance-"


def test_socket_proxy_is_not_misclassified_as_an_agent():
    # `socket-proxy` shares no agent prefix -> other (not seo/shared/etc.)
    assert grouping.classify("socket-proxy").id == "other"


def test_is_known_agent_includes_other_but_not_garbage():
    assert grouping.is_known_agent("compliance")
    assert grouping.is_known_agent("monitoring")
    assert grouping.is_known_agent("other")
    assert not grouping.is_known_agent("nope")
    assert not grouping.is_known_agent("")


def test_known_agent_ids_cover_the_table_plus_other():
    ids = set(grouping.known_agent_ids())
    assert {"compliance", "seo", "shared", "landing", "monitoring", "other"} <= ids


def test_get_group_returns_none_for_unknown():
    assert grouping.get_group("compliance") is not None
    assert grouping.get_group("nope") is None
