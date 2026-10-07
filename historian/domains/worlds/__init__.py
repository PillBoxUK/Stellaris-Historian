"""Worlds domain: colony parsing, cache ownership, expansion history and journal helpers."""

CACHE_COMPONENT_NAME = "worlds"
CACHE_COMPONENT_VERSION = 2

from .models import WorldSnapshot, WorldState
from .parser import extract_world_snapshot, planet_display_name, world_location_display_name
from .history import derive_full_world_history, world_transition_data

__all__ = [
    "CACHE_COMPONENT_NAME",
    "CACHE_COMPONENT_VERSION",
    "WorldSnapshot",
    "WorldState",
    "extract_world_snapshot",
    "planet_display_name",
    "world_location_display_name",
    "derive_full_world_history",
    "world_transition_data",
]
