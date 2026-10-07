"""Science domain: evidence, interpretation and selective journal publication."""

CACHE_COMPONENT_NAME = "science"
CACHE_COMPONENT_VERSION = 1

from .models import (
    ArchaeologySiteState,
    ScienceSnapshot,
    SituationState,
    SpecialProjectState,
)
from .parser import extract_science_snapshot
from .history import (
    ArchaeologyInterpretation,
    ProjectFamilyInterpretation,
    ScienceInterpretation,
    SituationInterpretation,
    derive_science_interpretation,
)
from .journal import render_science_section
from .diagnostic import (
    science_evidence_summary,
    write_science_diagnostic,
    write_science_interpretation_diagnostic,
)

__all__ = [
    "CACHE_COMPONENT_NAME",
    "CACHE_COMPONENT_VERSION",
    "ArchaeologySiteState",
    "ScienceSnapshot",
    "SituationState",
    "SpecialProjectState",
    "ArchaeologyInterpretation",
    "ProjectFamilyInterpretation",
    "ScienceInterpretation",
    "SituationInterpretation",
    "extract_science_snapshot",
    "derive_science_interpretation",
    "science_evidence_summary",
    "write_science_diagnostic",
    "write_science_interpretation_diagnostic",
    "render_science_section",
]
