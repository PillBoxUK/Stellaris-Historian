"""Technology domain: researched-technology evidence and first-observed acquisition history."""

CACHE_COMPONENT_NAME = "technology"
CACHE_COMPONENT_VERSION = 1

from .models import TechnologySnapshot, TechnologyState, TechnologyEvent
from .parser import extract_technology_snapshot
from .history import derive_technology_history, technology_evidence_summary
from .diagnostic import write_technology_diagnostic

__all__ = [
    "CACHE_COMPONENT_NAME",
    "CACHE_COMPONENT_VERSION",
    "TechnologySnapshot",
    "TechnologyState",
    "TechnologyEvent",
    "extract_technology_snapshot",
    "derive_technology_history",
    "technology_evidence_summary",
    "write_technology_diagnostic",
]
