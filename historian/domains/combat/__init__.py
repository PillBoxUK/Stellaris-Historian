"""Combat domain: evidence-first war, battle and exact combat-activity reconstruction."""

CACHE_COMPONENT_NAME = "combat"
CACHE_COMPONENT_VERSION = 3

from .models import (
    BattleState,
    CombatSnapshot,
    EnemyFleetCombatState,
    FleetCombatStatsState,
    RelationKillCounterState,
    ShipCombatActivityState,
    StarbaseCombatActivityState,
    WarState,
)
from .parser import extract_combat_snapshot
from .diagnostic import combat_evidence_summary, write_combat_diagnostic
from .correlation import (
    CorrelatedEngagement,
    DirectCombatEpisode,
    PossibleLoss,
    RelationCounterDelta,
    correlation_summary,
    derive_correlated_engagements,
    derive_direct_combat_episodes,
)
from .correlation_diagnostic import write_combat_correlation_diagnostic
from .episodes import (
    CombatEpisode,
    CombatLossObservation,
    combat_episode_summary,
    derive_combat_episodes,
    write_combat_episode_diagnostic,
)

__all__ = [
    "CACHE_COMPONENT_NAME",
    "CACHE_COMPONENT_VERSION",
    "BattleState",
    "CombatSnapshot",
    "EnemyFleetCombatState",
    "FleetCombatStatsState",
    "RelationKillCounterState",
    "ShipCombatActivityState",
    "StarbaseCombatActivityState",
    "WarState",
    "CorrelatedEngagement",
    "DirectCombatEpisode",
    "PossibleLoss",
    "RelationCounterDelta",
    "extract_combat_snapshot",
    "combat_evidence_summary",
    "write_combat_diagnostic",
    "derive_correlated_engagements",
    "derive_direct_combat_episodes",
    "correlation_summary",
    "write_combat_correlation_diagnostic",
    "CombatEpisode",
    "CombatLossObservation",
    "derive_combat_episodes",
    "combat_episode_summary",
    "write_combat_episode_diagnostic",
]
