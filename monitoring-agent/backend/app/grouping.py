"""
monitoring-agent/backend/app/grouping.py

The container-name-prefix -> agent group table (§3) and the classifier that maps
a container name to its agent id. The backend owns this table; the frontend maps
ids to friendly icons/names via its own registry, falling back to `label`.

Containers whose name matches no known prefix fall into the synthetic `other`
group (prefix "").
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class AgentGroup:
    id: str
    label: str
    prefix: str


# Ordered: longest/most-specific prefixes are unambiguous here, but order is kept
# stable so /agents output is deterministic. `other` is synthetic (empty prefix)
# and is never matched by `classify` — it only collects the leftovers.
GROUPS: List[AgentGroup] = [
    AgentGroup("compliance", "Regulatory Compliance", "compliance-"),
    AgentGroup("seo", "SEO & GEO Intelligence", "seo-"),
    AgentGroup("shared", "Shared Infrastructure", "shared-"),
    AgentGroup("landing", "Platform Home", "landing-"),
    AgentGroup("monitoring", "Monitoring", "monitoring-"),
]

OTHER = AgentGroup("other", "Other", "")

# Fast lookup by id, including the synthetic `other` group.
GROUPS_BY_ID: Dict[str, AgentGroup] = {g.id: g for g in GROUPS}
GROUPS_BY_ID[OTHER.id] = OTHER


def known_agent_ids() -> List[str]:
    """All valid agent ids (real groups + synthetic `other`)."""
    return [g.id for g in GROUPS] + [OTHER.id]


def is_known_agent(agent_id: str) -> bool:
    return agent_id in GROUPS_BY_ID


def get_group(agent_id: str) -> Optional[AgentGroup]:
    return GROUPS_BY_ID.get(agent_id)


def classify(container_name: str) -> AgentGroup:
    """Map a container name to its agent group by name prefix.

    Anything not matching a known prefix lands in the synthetic `other` group.
    """
    name = container_name or ""
    for group in GROUPS:
        if name.startswith(group.prefix):
            return group
    return OTHER
