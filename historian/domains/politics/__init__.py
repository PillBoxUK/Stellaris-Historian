"""Structured Politics and Diplomacy evidence domain.

v0.0.47 promotes only evidence shapes that can be stated conservatively:
government profile changes, ruler identity observations, agenda-field changes,
tradition first-observations and literal player relation-record transitions.
Unknown diplomatic keys remain raw evidence and are not assigned treaty/election
semantics.
"""

CACHE_COMPONENT_NAME = "politics_diplomacy"
CACHE_COMPONENT_VERSION = 1

from .history import (
    derive_full_politics_history,
    politics_transition_data,
    write_politics_database_diagnostic,
    write_politics_history_diagnostic,
)
from .journal import render_politics_section
from .models import DiplomaticRelationState, PoliticsSnapshot
from .parser import extract_politics_snapshot
from .probe import write_politics_diplomacy_probe

__all__ = [
    "CACHE_COMPONENT_NAME",
    "CACHE_COMPONENT_VERSION",
    "DiplomaticRelationState",
    "PoliticsSnapshot",
    "derive_full_politics_history",
    "extract_politics_snapshot",
    "politics_transition_data",
    "render_politics_section",
    "write_politics_database_diagnostic",
    "write_politics_diplomacy_probe",
    "write_politics_history_diagnostic",
]
