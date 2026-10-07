from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DeadLeaderState:
    leader_id: int
    name: str
    leader_class: str | None
    country_id: int | None
    death_date: str | None
    death_date_key: str | None
    death_reason_key: str | None
    death_reason_value: str | None
    raw_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class LeaderState:
    leader_id: int
    name: str
    leader_class: str
    level: int | None
    experience: float | None
    recruitment_date: str | None
    gender: str | None
    traits: tuple[str, ...]
    trait_names: tuple[str, ...]
    location_type: str | None
    location_id: int | None
    assignment_key: str | None
    assignment_name: str | None
    council_role_key: str | None
    council_role_name: str | None
    is_ruler: bool
    is_heir: bool

    # v0.0.42 - deeper raw character evidence. These values are intentionally
    # recorded conservatively. Fields such as recorded_date/raw_age are not
    # interpreted as birth information unless Stellaris explicitly says so.
    species_id: int | None = None
    species_name: str | None = None
    portrait: str | None = None
    creator_country_id: int | None = None
    tier_key: str | None = None
    tier_name: str | None = None
    recorded_date: str | None = None
    date_added: str | None = None
    raw_age: int | None = None
    ethic_key: str | None = None
    ethic_name: str | None = None
    job_key: str | None = None
    job_name: str | None = None
    background_planet_id: int | None = None
    background_planet_name: str | None = None
    custom_description_key: str | None = None
    custom_description_name: str | None = None
    bonus_skill_level: int | None = None
    raw_keys: tuple[str, ...] = ()
    flag_values: tuple[tuple[str, str], ...] = ()
    variable_values: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class LeaderSnapshot:
    snapshot_id: int
    game_date: str
    leaders: dict[int, LeaderState]
    dead_leaders: dict[int, DeadLeaderState] = field(default_factory=dict)
    active_record_keys: tuple[str, ...] = ()
    active_flag_keys: tuple[str, ...] = ()
    active_variable_keys: tuple[str, ...] = ()
    dead_record_keys: tuple[str, ...] = ()
    last_notification_id: int | None = None
    last_event_id: int | None = None
    selected_player_event_count: int = 0
    tombstoned_leader_ids: tuple[int, ...] = ()
    saved_event_target_names: dict[int, tuple[str, ...]] = field(default_factory=dict)
