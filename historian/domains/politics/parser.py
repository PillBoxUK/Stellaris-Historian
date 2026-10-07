from __future__ import annotations

import re
from pathlib import Path

from ...core.stellaris_text import _find_named_block, _numeric_record
from ...save_reader import EmpireProfile
from ..people.models import LeaderSnapshot
from .models import DiplomaticRelationState, PoliticsSnapshot
from .probe import (
    _named_blocks,
    _relation_snapshot,
    _top_level_items,
)


def _agenda_fields(
    government_scalars: dict[str, str],
    political_scalars: dict[str, str],
    political_blocks: tuple[str, ...],
) -> tuple[tuple[str, str], ...]:
    result: dict[str, str] = {}

    for source in (government_scalars, political_scalars):
        for key, value in source.items():
            if "agenda" in key.casefold():
                result[key] = value

    for key in political_blocks:
        if "agenda" in key.casefold():
            result.setdefault(key, "<block-present>")

    return tuple(sorted(result.items()))


def _tradition_tokens(player_record: str | None) -> tuple[str, ...]:
    if not player_record:
        return ()

    values: set[str] = set()

    for key, scalar, is_block in _top_level_items(player_record):
        if "tradition" not in key.casefold():
            continue

        if not is_block:
            if scalar and scalar.casefold().startswith("tr_"):
                values.add(scalar)
            continue

        for block in _named_blocks(player_record, key):
            for token in re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"|([A-Za-z0-9_.:\-]+)', block):
                raw = token[0] or token[1]
                if not raw:
                    continue
                low = raw.casefold()
                if low.startswith("tr_"):
                    values.add(raw.replace('\\"', '"'))

    return tuple(sorted(values))


def extract_politics_snapshot(
    *,
    gamestate: str,
    profile: EmpireProfile,
    source_save: Path,
    snapshot_id: int,
    leader_snapshot: LeaderSnapshot,
) -> PoliticsSnapshot:
    relations: dict[int, DiplomaticRelationState] = {}
    agenda_fields: tuple[tuple[str, str], ...] = ()
    traditions: tuple[str, ...] = ()

    if profile.player_country_id is not None:
        (
            relation_rows,
            _political_keys,
            political_scalars,
            political_blocks,
            government_scalars,
            _marker_counts,
        ) = _relation_snapshot(
            gamestate=gamestate,
            player_country_id=profile.player_country_id,
            source_save=source_save,
        )

        agenda_fields = _agenda_fields(
            government_scalars,
            political_scalars,
            political_blocks,
        )

        countries = _find_named_block(gamestate, "country")
        player_record = _numeric_record(countries, profile.player_country_id)
        traditions = _tradition_tokens(player_record)

        for country_id, row in relation_rows.items():
            relations[int(country_id)] = DiplomaticRelationState(
                country_id=int(country_id),
                country_name=str(row.get("name") or f"Country {country_id}"),
                scalars=tuple(sorted(
                    (str(key), str(value))
                    for key, value in (row.get("scalars") or {}).items()
                )),
                blocks=tuple(sorted(str(value) for value in (row.get("blocks") or ()))),
            )

    rulers = sorted(
        (
            leader
            for leader in leader_snapshot.leaders.values()
            if leader.is_ruler
        ),
        key=lambda leader: leader.leader_id,
    )
    ruler = rulers[0] if len(rulers) == 1 else None

    return PoliticsSnapshot(
        snapshot_id=snapshot_id,
        game_date=profile.game_date,
        player_country_id=profile.player_country_id,
        government_type=profile.government_type,
        authority=profile.authority,
        ethics=tuple(profile.ethics),
        civics=tuple(profile.civics),
        ruler_id=(ruler.leader_id if ruler is not None else None),
        ruler_name=(ruler.name if ruler is not None else None),
        agenda_fields=agenda_fields,
        traditions=traditions,
        relations=relations,
    )
