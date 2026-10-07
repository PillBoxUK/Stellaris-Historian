"""People domain: leader parsing, cache ownership, career history and journal rendering."""

CACHE_COMPONENT_NAME = "leaders"
CACHE_COMPONENT_VERSION = 5

from .models import DeadLeaderState, LeaderSnapshot, LeaderState
from .parser import extract_leader_snapshot
from .history import derive_full_leader_history, leader_transition_data

__all__ = [
    "CACHE_COMPONENT_NAME",
    "CACHE_COMPONENT_VERSION",
    "DeadLeaderState",
    "LeaderSnapshot",
    "LeaderState",
    "extract_leader_snapshot",
    "derive_full_leader_history",
    "leader_transition_data",
]
