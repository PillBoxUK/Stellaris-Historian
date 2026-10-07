from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from typing import Iterable

from ...core.stellaris_text import (
    _extract_braced_after,
    _find_named_block,
    _int_scalar,
    _numeric_record,
    _record_name,
    _scalar,
)
from ...db import Database
from ...save_reader import empire_profile_from_text, read_save_texts


# This is an evidence probe, not a semantics layer.  The candidate names below
# are used only to focus output; an unfamiliar key is preserved as raw evidence
# rather than guessed into a treaty/election/faction meaning.
_POLITICAL_WORDS = (
    "authority",
    "civic",
    "council",
    "diplom",
    "election",
    "ethic",
    "faction",
    "federation",
    "first_contact",
    "government",
    "heir",
    "policy",
    "relation",
    "reform",
    "ruler",
    "subject",
    "tradition",
)

_GLOBAL_MARKERS = (
    "federation",
    "federation_manager",
    "pop_faction",
    "faction",
    "first_contact",
    "first_contact_manager",
    "diplomatic_action",
    "galactic_community",
    "galactic_council",
    "election",
    "election_date",
    "ruler",
    "heir",
)

_MAX_RAW_SAMPLES = 64
_LATEST_SAMPLE_COUNT = 24
_EVEN_SAMPLE_COUNT = 12


def _normalise_space(value: object) -> str:
    return " ".join(str(value or "").split())


def _top_level_items(text: str | None) -> tuple[tuple[str, str | None, bool], ...]:
    """Return direct-child key/value evidence from a Stellaris record.

    Each tuple is ``(key, scalar_value, is_block)``.  Nested children are not
    flattened.  The parser is quote-aware and tracks brace depth so this remains
    useful across save-format indentation changes.
    """
    if not text:
        return ()

    result: list[tuple[str, str | None, bool]] = []
    depth = 0
    in_quote = False
    escaped = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if depth == 0 and line and not line.startswith("#"):
            match = re.match(r'([A-Za-z0-9_.:\-]+)\s*=\s*(.*)$', line)
            if match:
                key = match.group(1)
                tail = match.group(2).strip()
                if tail.startswith("{"):
                    result.append((key, None, True))
                else:
                    quoted = re.match(r'^"((?:\\.|[^"])*)"', tail)
                    if quoted:
                        value = quoted.group(1).replace('\\"', '"')
                    else:
                        value_match = re.match(r'^([^\s{}]+)', tail)
                        value = value_match.group(1) if value_match else None
                    result.append((key, value, False))

        for char in raw_line:
            if in_quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_quote = False
                continue
            if char == '"':
                in_quote = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth = max(0, depth - 1)

    return tuple(result)


def _top_level_scalars(text: str | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value, is_block in _top_level_items(text):
        if not is_block and value is not None:
            result[key] = value
    return result


def _top_level_blocks(text: str | None) -> tuple[str, ...]:
    return tuple(
        key
        for key, _value, is_block in _top_level_items(text)
        if is_block
    )


def _named_blocks(text: str | None, key: str) -> tuple[str, ...]:
    if not text:
        return ()
    pattern = re.compile(r"(?m)^\s*" + re.escape(key) + r"\s*=\s*\{")
    result: list[str] = []
    for match in pattern.finditer(text):
        inner = _extract_braced_after(text, match.start())
        if inner is not None:
            result.append(inner)
    return tuple(result)


def _country_name(record: str | None, country_id: int, source_save: Path) -> str:
    if not record:
        return f"Country {country_id}"
    try:
        name = _record_name(record, source_save, fallback=f"Country {country_id}")
    except Exception:
        name = f"Country {country_id}"
    name = _normalise_space(name)
    if not name or "%" in name or "$" in name:
        return f"Country {country_id}"
    return name


_GLOBAL_MARKER_PATTERN = re.compile(
    r"(?m)^\s*(" + "|".join(re.escape(key) for key in _GLOBAL_MARKERS) + r")\s*="
)


def _marker_counts(text: str) -> dict[str, int]:
    counts = {key: 0 for key in _GLOBAL_MARKERS}
    for match in _GLOBAL_MARKER_PATTERN.finditer(text):
        counts[match.group(1)] += 1
    return counts


def _political_keys(record: str | None) -> tuple[str, ...]:
    keys = []
    for key, _value, _is_block in _top_level_items(record):
        low = key.casefold()
        if any(word in low for word in _POLITICAL_WORDS):
            keys.append(key)
    return tuple(dict.fromkeys(keys))


def _relation_snapshot(
    *,
    gamestate: str,
    player_country_id: int,
    source_save: Path,
) -> tuple[dict[int, dict], tuple[str, ...], dict[str, str], tuple[str, ...], dict[str, str], dict[str, int]]:
    countries = _find_named_block(gamestate, "country")
    player_record = _numeric_record(countries, player_country_id)
    if not player_record:
        return {}, (), {}, (), {}, _marker_counts(gamestate)

    government = _find_named_block(player_record, "government")
    government_scalars = _top_level_scalars(government)
    player_political_keys = _political_keys(player_record)
    political_key_set = set(player_political_keys)
    player_political_scalars = {
        key: value
        for key, value, is_block in _top_level_items(player_record)
        if key in political_key_set and not is_block and value is not None
    }
    player_political_blocks = tuple(
        key
        for key, _value, is_block in _top_level_items(player_record)
        if key in political_key_set and is_block
    )

    relation_manager = _find_named_block(player_record, "relations_manager")
    relations: dict[int, dict] = {}
    relation_records = _named_blocks(relation_manager, "relation")

    wanted_ids: set[int] = set()
    raw_relations: list[tuple[int, dict[str, str], tuple[str, ...]]] = []
    for relation in relation_records:
        owner = _int_scalar(relation, "owner")
        other = _int_scalar(relation, "country")
        if owner not in (None, player_country_id):
            continue
        if other is None or other == player_country_id:
            continue
        scalars = _top_level_scalars(relation)
        blocks = _top_level_blocks(relation)
        wanted_ids.add(other)
        raw_relations.append((other, scalars, blocks))

    for other, scalars, blocks in raw_relations:
        other_record = _numeric_record(countries, other)
        relations[other] = {
            "name": _country_name(other_record, other, source_save),
            "scalars": scalars,
            "blocks": blocks,
        }

    marker_counts = _marker_counts(gamestate)
    return (
        relations,
        player_political_keys,
        player_political_scalars,
        player_political_blocks,
        government_scalars,
        marker_counts,
    )


def _entry_profile(entry: dict) -> tuple[str, str, str, str]:
    return tuple(
        _normalise_space(entry.get(key))
        for key in ("government_type", "authority", "ethics", "civics")
    )


def _date_key(value: str | None) -> tuple[int, int, int, str]:
    text = str(value or "")
    bits = text.split(".")
    try:
        if len(bits) == 3:
            return int(bits[0]), int(bits[1]), int(bits[2]), text
    except ValueError:
        pass
    return (10**9, 10**9, 10**9, text)


def _select_raw_snapshots(
    snapshots: list[dict],
    history_entries: list[dict],
    leader_events: list[dict],
) -> list[dict]:
    if len(snapshots) <= _MAX_RAW_SAMPLES:
        return snapshots

    by_id = {int(row["id"]): index for index, row in enumerate(snapshots)}
    selected: set[int] = {0, len(snapshots) - 1}

    # Preserve the recent live edge in detail.
    selected.update(range(max(0, len(snapshots) - _LATEST_SAMPLE_COUNT), len(snapshots)))

    # Spread additional samples across the whole campaign.
    if len(snapshots) > 1:
        for slot in range(_EVEN_SAMPLE_COUNT):
            index = round(slot * (len(snapshots) - 1) / max(1, _EVEN_SAMPLE_COUNT - 1))
            selected.add(index)

    # Always inspect around profile/government changes already known from the
    # database, because these are prime political evidence windows.
    previous_profile = None
    for entry in history_entries:
        profile = _entry_profile(entry)
        if previous_profile is not None and profile != previous_profile:
            sid = entry.get("snapshot_id")
            if sid is not None and int(sid) in by_id:
                index = by_id[int(sid)]
                selected.update(i for i in (index - 1, index, index + 1) if 0 <= i < len(snapshots))
        previous_profile = profile

    # Existing People evidence already knows when rulership changed.  Pull raw
    # politics/diplomacy around those windows too.
    for event in leader_events:
        if event.get("event_type") not in {
            "leader_became_ruler",
            "leader_left_rulership",
            "leader_became_heir",
            "leader_left_heirship",
            "leader_death_recorded",
        }:
            continue
        sid = event.get("snapshot_id")
        if sid is not None and int(sid) in by_id:
            index = by_id[int(sid)]
            selected.update(i for i in (index - 1, index, index + 1) if 0 <= i < len(snapshots))

    # Keep the probe bounded.  Priority samples above are normally far below the
    # cap, but a very turbulent campaign should not turn Review into a raw-save
    # full reconstruction.
    if len(selected) > _MAX_RAW_SAMPLES:
        ordered = sorted(selected)
        keep: set[int] = set(ordered[-_LATEST_SAMPLE_COUNT:])
        keep.add(0)
        keep.add(len(snapshots) - 1)
        remaining_slots = _MAX_RAW_SAMPLES - len(keep)
        candidates = [i for i in ordered if i not in keep]
        if candidates and remaining_slots > 0:
            for slot in range(remaining_slots):
                pos = round(slot * (len(candidates) - 1) / max(1, remaining_slots - 1))
                keep.add(candidates[pos])
        selected = keep

    return [snapshots[index] for index in sorted(selected)]


def _format_scalar_map(values: dict[str, str], *, limit: int = 30) -> list[str]:
    if not values:
        return ["None retained"]
    rows = []
    for index, key in enumerate(sorted(values)):
        if index >= limit:
            rows.append(f"... {len(values) - limit} more scalar key(s)")
            break
        rows.append(f"{key}={values[key]}")
    return rows


def _diff_relation(previous: dict, current: dict) -> list[str]:
    lines: list[str] = []
    prev_scalars = previous.get("scalars", {})
    cur_scalars = current.get("scalars", {})
    for key in sorted(set(prev_scalars) | set(cur_scalars)):
        before = prev_scalars.get(key)
        after = cur_scalars.get(key)
        if before != after:
            lines.append(f"scalar {key}: {before if before is not None else '<absent>'} -> {after if after is not None else '<absent>'}")
    prev_blocks = set(previous.get("blocks", ()))
    cur_blocks = set(current.get("blocks", ()))
    for key in sorted(cur_blocks - prev_blocks):
        lines.append(f"block appeared: {key}")
    for key in sorted(prev_blocks - cur_blocks):
        lines.append(f"block disappeared: {key}")
    return lines


def write_politics_diplomacy_probe(db: Database, campaign_id: int) -> Path:
    campaign_row = db.campaign(campaign_id)
    if campaign_row is None:
        raise ValueError("Campaign does not exist.")

    campaign = dict(campaign_row)
    snapshots = [dict(row) for row in db.all_snapshots(campaign_id)]
    history_entries = [dict(row) for row in db.history_entries(campaign_id)]
    leader_events = [dict(row) for row in db.leader_career_events(campaign_id, visible_only=False)]

    diagnostics = Path(campaign["archive_dir"]) / "diagnostics"
    diagnostics.mkdir(parents=True, exist_ok=True)
    path = diagnostics / "Politics_Diplomacy_Probe_Debug.txt"

    selected = _select_raw_snapshots(snapshots, history_entries, leader_events)
    raw_rows: list[dict] = []
    failures: list[str] = []
    relation_key_frequency: Counter[str] = Counter()
    political_key_frequency: Counter[str] = Counter()
    government_key_frequency: Counter[str] = Counter()

    for snapshot in selected:
        try:
            meta, gamestate = read_save_texts(Path(snapshot["archive_path"]))
            profile = empire_profile_from_text(meta, gamestate)
            if profile.player_country_id is None:
                raise ValueError("player country ID was not retained")
            (
                relations,
                political_keys,
                political_scalars,
                political_blocks,
                government_scalars,
                marker_counts,
            ) = _relation_snapshot(
                gamestate=gamestate,
                player_country_id=profile.player_country_id,
                source_save=Path(campaign["source_save"]),
            )
            for key in political_keys:
                political_key_frequency[key] += 1
            for key in government_scalars:
                government_key_frequency[key] += 1
            for relation in relations.values():
                for key in relation.get("scalars", {}):
                    relation_key_frequency[key] += 1
                for key in relation.get("blocks", ()):
                    relation_key_frequency[f"{key}{{}}"] += 1
            raw_rows.append({
                "snapshot_id": int(snapshot["id"]),
                "game_date": str(snapshot["game_date"]),
                "archive_filename": str(snapshot["archive_filename"]),
                "player_country_id": profile.player_country_id,
                "government_type": profile.government_type,
                "authority": profile.authority,
                "origin": profile.origin,
                "ethics": profile.ethics,
                "civics": profile.civics,
                "relations": relations,
                "political_keys": political_keys,
                "political_scalars": political_scalars,
                "political_blocks": political_blocks,
                "government_scalars": government_scalars,
                "marker_counts": marker_counts,
            })
        except Exception as exc:
            failures.append(f"{snapshot.get('game_date')} | {snapshot.get('archive_filename')} | {exc}")

    lines = [
        "STELLARIS HISTORIAN - POLITICS & DIPLOMACY DEEP PROBE",
        "",
        "v0.0.46 evidence-only forensic probe.",
        "Purpose: learn the retained government, election/faction, first-contact and diplomatic-relation structures before Historian promotes any of them into public history.",
        "Raw keys/flags below are not interpreted beyond their literal retained values. A key name alone does not prove a treaty, election, faction, alliance, rivalry or policy change.",
        "",
        f"Campaign: {campaign.get('empire_name') or 'Unknown'}",
        f"Archived snapshots: {len(snapshots)}",
        f"Raw snapshots selected: {len(selected)} (adaptive maximum {_MAX_RAW_SAMPLES})",
        f"Raw snapshots opened successfully: {len(raw_rows)}",
        f"Raw read failures: {len(failures)}",
        "",
        "PROFILE / GOVERNMENT CHANGES FROM ALL ARCHIVED STATES",
        "====================================================",
    ]

    previous = None
    profile_change_count = 0
    for entry in history_entries:
        current = _entry_profile(entry)
        if previous is None:
            lines.append(
                f"{entry.get('game_date')} | opening profile | government={current[0] or 'None'} | authority={current[1] or 'None'} | ethics={current[2] or 'None'} | civics={current[3] or 'None'}"
            )
        elif current != previous:
            profile_change_count += 1
            labels = ("government", "authority", "ethics", "civics")
            changes = [
                f"{label}: {before or '<none>'} -> {after or '<none>'}"
                for label, before, after in zip(labels, previous, current)
                if before != after
            ]
            lines.append(f"{entry.get('game_date')} | " + " | ".join(changes))
        previous = current
    if not history_entries:
        lines.append("No reviewed history entries are available.")
    elif profile_change_count == 0:
        lines.append("No later profile/government changes were observed in the reviewed archive.")

    lines.extend([
        "",
        "EXISTING PEOPLE-DOMAIN RULER / HEIR / DEATH MILESTONES",
        "=====================================================",
    ])
    ruler_events = [
        event for event in leader_events
        if event.get("event_type") in {
            "leader_became_ruler",
            "leader_left_rulership",
            "leader_became_heir",
            "leader_left_heirship",
            "leader_death_recorded",
        }
    ]
    if ruler_events:
        for event in sorted(ruler_events, key=lambda row: _date_key(row.get("game_date"))):
            lines.append(
                f"{event.get('game_date')} | {event.get('event_type')} | {event.get('title')} | leader_id={event.get('leader_id')} | date_kind={event.get('date_kind')}"
            )
    else:
        lines.append("No ruler/heir/death milestones are currently present in People evidence.")

    lines.extend([
        "",
        "SELECTED RAW-SAVE POLITICAL / DIPLOMATIC SAMPLES",
        "================================================",
    ])

    for row in raw_rows:
        lines.extend([
            "",
            f"{row['game_date']} | {row['archive_filename']}",
            f"  Player country ID: {row['player_country_id']}",
            f"  Government type: {row['government_type'] or 'Not retained'}",
            f"  Authority: {row['authority'] or 'Not retained'}",
            f"  Origin: {row['origin'] or 'Not retained'}",
            f"  Ethics: {', '.join(row['ethics']) if row['ethics'] else 'None retained'}",
            f"  Civics: {', '.join(row['civics']) if row['civics'] else 'None retained'}",
            f"  Player-country political candidate keys: {', '.join(row['political_keys']) if row['political_keys'] else 'None found'}",
            "  Player-country political direct scalars:",
        ])
        lines.extend(f"    {value}" for value in _format_scalar_map(row["political_scalars"]))
        lines.append(
            f"  Player-country political direct blocks: {', '.join(row['political_blocks']) if row['political_blocks'] else 'None'}"
        )
        lines.append("  Government direct scalars:")
        lines.extend(f"    {value}" for value in _format_scalar_map(row["government_scalars"]))
        marker_text = ", ".join(
            f"{key}={count}"
            for key, count in row["marker_counts"].items()
            if count
        )
        lines.append(f"  Global raw marker counts: {marker_text or 'None of the probe marker names found'}")
        lines.append(f"  Player relation records: {len(row['relations'])}")
        for other_id, relation in sorted(row["relations"].items()):
            lines.append(f"    Country {other_id} | {relation['name']}")
            scalar_rows = _format_scalar_map(relation.get("scalars", {}), limit=24)
            for value in scalar_rows:
                lines.append(f"      scalar: {value}")
            blocks = relation.get("blocks", ())
            lines.append(f"      direct blocks: {', '.join(blocks) if blocks else 'None'}")

    lines.extend([
        "",
        "RELATION CHANGES BETWEEN SELECTED RAW SAMPLES",
        "=============================================",
        "These are sampled intervals. A change first visible here is not automatically an exact event date unless adjacent archived saves were selected.",
    ])
    transition_count = 0
    for previous_row, current_row in zip(raw_rows, raw_rows[1:]):
        prev_rel = previous_row["relations"]
        cur_rel = current_row["relations"]
        changes_for_interval: list[str] = []
        for other_id in sorted(set(prev_rel) | set(cur_rel)):
            if other_id not in prev_rel:
                changes_for_interval.append(
                    f"Country {other_id} ({cur_rel[other_id]['name']}): relation record appeared"
                )
                continue
            if other_id not in cur_rel:
                changes_for_interval.append(
                    f"Country {other_id} ({prev_rel[other_id]['name']}): relation record disappeared"
                )
                continue
            detail = _diff_relation(prev_rel[other_id], cur_rel[other_id])
            if detail:
                name = cur_rel[other_id].get("name") or prev_rel[other_id].get("name")
                shown = detail[:12]
                suffix = f"; ... {len(detail) - 12} more change(s)" if len(detail) > 12 else ""
                changes_for_interval.append(
                    f"Country {other_id} ({name}): " + "; ".join(shown) + suffix
                )
        if changes_for_interval:
            transition_count += len(changes_for_interval)
            lines.append(
                f"{previous_row['game_date']} -> {current_row['game_date']}"
            )
            lines.extend(f"  {value}" for value in changes_for_interval)
    if transition_count == 0:
        lines.append("No relation-record changes were found between the selected raw samples.")

    lines.extend([
        "",
        "RAW KEY FREQUENCIES ACROSS SELECTED SAMPLES",
        "==========================================",
        "Player-country political candidate keys:",
    ])
    if political_key_frequency:
        lines.extend(
            f"  {key}: {count}/{len(raw_rows)} sample(s)"
            for key, count in political_key_frequency.most_common()
        )
    else:
        lines.append("  None found")
    lines.append("Government direct scalar keys:")
    if government_key_frequency:
        lines.extend(
            f"  {key}: {count}/{len(raw_rows)} sample(s)"
            for key, count in government_key_frequency.most_common()
        )
    else:
        lines.append("  None found")
    lines.append("Relation direct scalar/block keys:")
    if relation_key_frequency:
        lines.extend(
            f"  {key}: {count} occurrence(s)"
            for key, count in relation_key_frequency.most_common(80)
        )
    else:
        lines.append("  None found")

    lines.extend([
        "",
        "RAW READ FAILURES",
        "=================",
    ])
    if failures:
        lines.extend(f"- {value}" for value in failures)
    else:
        lines.append("None")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path
