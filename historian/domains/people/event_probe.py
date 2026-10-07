from __future__ import annotations

from collections import Counter
from pathlib import Path
import re

from ...db import Database
from ...save_reader import read_save_texts
from ...snapshot_cache import campaign_cache_dir, load_or_parse_snapshot
from ...core.stellaris_text import (
    _extract_braced_after,
    _find_named_block,
    _int_scalar,
    _numeric_record,
    _scalar,
)
from .history import derive_full_leader_history
from .models import LeaderSnapshot


_EXIT_EVENT_TYPES = {
    "leader_death_recorded",
    "leader_tombstone_unconfirmed",
    "leader_missing_unconfirmed",
}

_EVENTISH_TOKENS = (
    "event",
    "notification",
    "message",
    "history",
    "target",
    "death",
    "dead",
    "died",
    "kill",
    "execut",
    "retir",
    "dismiss",
)


def _collapse(value: str | None, limit: int = 700) -> str:
    if not value:
        return "None"
    compact = re.sub(r"\s+", " ", value).strip()
    if len(compact) > limit:
        return compact[: limit - 3] + "..."
    return compact or "None"


def _event_selection_ids(gamestate: str) -> tuple[int, ...]:
    block = _find_named_block(gamestate, "open_player_event_selection_history")
    if not block:
        return ()
    return tuple(
        int(value)
        for value in re.findall(
            r"(?m)^\s*player_event\s*=\s*(\d+)",
            block,
        )
    )


def _leader_record(gamestate: str, leader_id: int) -> str | None:
    leaders = _find_named_block(gamestate, "leaders")
    return _numeric_record(leaders, leader_id)


def _top_level_pairs(text: str | None) -> tuple[tuple[str, str], ...]:
    if not text:
        return ()

    result: list[tuple[str, str]] = []
    depth = 0
    in_quote = False
    escaped = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if depth == 0 and line:
            match = re.match(
                r'([A-Za-z0-9_.:-]+)\s*=\s*(?:"([^"]*)"|([^\s{}]+))\s*$',
                line,
            )
            if match:
                result.append((match.group(1), match.group(2) or match.group(3) or ""))

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


def _find_top_level_block(text: str | None, key: str) -> str | None:
    if not text:
        return None

    depth = 0
    in_quote = False
    escaped = False
    offset = 0

    for raw_line in text.splitlines(keepends=True):
        line = raw_line.strip()
        if depth == 0 and re.match(rf"{re.escape(key)}\s*=", line):
            return _extract_braced_after(text, offset)

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
        offset += len(raw_line)

    return None


def _leader_unmapped_field_evidence(gamestate: str, leader_id: int) -> dict[str, tuple[str, ...]]:
    record = _leader_record(gamestate, leader_id)
    if not record:
        return {}

    pairs = _top_level_pairs(record)
    result: dict[str, tuple[str, ...]] = {}

    for key in ("available_trait", "cooldown", "delayed_event"):
        values = [value for pair_key, value in pairs if pair_key == key]
        block = _find_top_level_block(record, key)
        if block:
            values.append("{" + _collapse(block, limit=900) + "}")
        if values:
            result[key] = tuple(values)

    return result


def _saved_event_target_blocks(gamestate: str, leader_id: int) -> tuple[str, ...]:
    blocks: list[str] = []
    pattern = re.compile(r"(?m)^\s*saved_event_target\s*=\s*\{")

    for match in pattern.finditer(gamestate):
        block = _extract_braced_after(gamestate, match.start())
        if not block:
            continue
        if _scalar(block, "type") != "leader":
            continue
        if _int_scalar(block, "id") != leader_id:
            continue
        blocks.append(_collapse(block, limit=900))

    return tuple(dict.fromkeys(blocks))


def _eventish_key_counts(gamestate: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for match in re.finditer(r"(?m)^\s*([A-Za-z0-9_.:-]+)\s*=", gamestate):
        key = match.group(1)
        folded = key.casefold()
        if any(token in folded for token in _EVENTISH_TOKENS):
            counts[key] += 1
    return counts


def _changed_eventish_keys(before: Counter[str], after: Counter[str], limit: int = 30) -> list[tuple[str, int, int]]:
    changed = [
        (key, before.get(key, 0), after.get(key, 0))
        for key in (set(before) | set(after))
        if before.get(key, 0) != after.get(key, 0)
    ]
    changed.sort(key=lambda item: (-abs(item[2] - item[1]), item[0]))
    return changed[:limit]


def _leader_reference_contexts(gamestate: str, leader_id: int, limit: int = 16) -> tuple[str, ...]:
    contexts: list[str] = []
    pattern = re.compile(rf"(?<!\d){leader_id}(?!\d)")

    for match in pattern.finditer(gamestate):
        start = max(0, match.start() - 220)
        end = min(len(gamestate), match.end() + 220)
        raw = gamestate[start:end]
        folded = raw.casefold()
        if not any(token in folded for token in _EVENTISH_TOKENS):
            continue
        compact = _collapse(raw, limit=520)
        if compact not in contexts:
            contexts.append(compact)
        if len(contexts) >= limit:
            break

    return tuple(contexts)


def _counter_delta(before: int | None, after: int | None) -> str:
    if before is None and after is None:
        return "Not observed"
    if before is None:
        return f"Not observed -> {after}"
    if after is None:
        return f"{before} -> Not observed"
    delta = after - before
    return f"{before} -> {after} (delta {delta:+d})"


def _load_leader_snapshots(db: Database, campaign_id: int) -> tuple[list, list[LeaderSnapshot], dict[int, LeaderSnapshot]]:
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist.")

    rows = list(db.all_snapshots(campaign_id))
    source_save = Path(campaign["source_save"])
    cache_dir = campaign_cache_dir(Path(campaign["archive_dir"]))

    leader_snapshots: list[LeaderSnapshot] = []
    by_snapshot_id: dict[int, LeaderSnapshot] = {}

    for row in rows:
        (
            _,
            _ship_snapshot,
            leader_snapshot,
            _world_snapshot,
            _science_snapshot,
            _combat_snapshot,
            _technology_snapshot,
            _politics_snapshot,
            _cache_status,
        ) = load_or_parse_snapshot(
            archive_path=Path(row["archive_path"]),
            source_save=source_save,
            source_sha256=row["sha256"],
            snapshot_id=int(row["id"]),
            cache_dir=cache_dir,
        )
        leader_snapshots.append(leader_snapshot)
        by_snapshot_id[int(row["id"])] = leader_snapshot

    return rows, leader_snapshots, by_snapshot_id


def write_event_character_probe(db: Database, campaign_id: int) -> Path:
    """Write a targeted event/character diagnostic around leader exit windows.

    The campaign is read from the existing parsed cache to locate exits. Raw
    archived saves are opened only for previous/current/next windows around
    those exits, avoiding another full raw-save reparse solely for this probe.
    """
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist.")

    rows, leader_snapshots, leader_by_snapshot_id = _load_leader_snapshots(db, campaign_id)
    leader_history = derive_full_leader_history(leader_snapshots)

    exit_events = [
        event
        for event in leader_history.get("events", [])
        if event.get("event_type") in _EXIT_EVENT_TYPES
    ]
    leader_rows = {
        int(row["leader_id"]): row
        for row in leader_history.get("leaders", [])
    }
    row_index = {int(row["id"]): index for index, row in enumerate(rows)}

    raw_cache: dict[str, str] = {}
    raw_errors: dict[str, str] = {}

    def gamestate_for(row) -> str | None:
        path = str(row["archive_path"])
        if path in raw_cache:
            return raw_cache[path]
        if path in raw_errors:
            return None
        try:
            _meta, gamestate = read_save_texts(Path(path))
        except Exception as exc:
            raw_errors[path] = str(exc)
            return None
        raw_cache[path] = gamestate
        return gamestate

    lines = [
        "STELLARIS HISTORIAN - EVENT / CHARACTER DEEP PROBE",
        "",
        "Purpose: investigate event, notification and unresolved leader-exit evidence without inventing death, dismissal, retirement or execution.",
        "This diagnostic uses the existing People v5 cache to locate exit transitions, then opens raw saves only in the previous/current/next window around each exit.",
        "A counter increase, event-selection ID, saved-event-target block or raw ID reference is correlation evidence only. It does NOT by itself establish the cause of a leader exit.",
        "",
        f"Campaign: {campaign['empire_name']}",
        f"Snapshots available: {len(rows)}",
        f"Leader exits selected for deep probe: {len(exit_events)}",
        "",
        "CAMPAIGN EVENT / NOTIFICATION COUNTER SUMMARY",
        "=============================================",
    ]

    counter_changes = []
    for before, after in zip(leader_snapshots, leader_snapshots[1:]):
        if (
            before.last_notification_id != after.last_notification_id
            or before.last_event_id != after.last_event_id
            or before.selected_player_event_count != after.selected_player_event_count
        ):
            counter_changes.append((before, after))

    lines.extend([
        f"Snapshot intervals with any tracked counter change: {len(counter_changes)}",
        (
            "Latest counters: "
            f"notification={leader_snapshots[-1].last_notification_id if leader_snapshots else 'Not observed'}, "
            f"event={leader_snapshots[-1].last_event_id if leader_snapshots else 'Not observed'}, "
            f"player-event selections={leader_snapshots[-1].selected_player_event_count if leader_snapshots else 0}"
        ),
        "",
        "LEADER EXIT WINDOWS",
        "===================",
        "",
    ])

    if not exit_events:
        lines.append("No leader exit transitions were found in the cached campaign history.")

    for event in exit_events:
        snapshot_id = int(event["snapshot_id"])
        current_index = row_index.get(snapshot_id)
        if current_index is None:
            continue

        leader_id = int(event["leader_id"])
        leader_row = leader_rows.get(leader_id, {})
        current_row = rows[current_index]
        before_row = rows[current_index - 1] if current_index > 0 else None
        next_row = rows[current_index + 1] if current_index + 1 < len(rows) else None

        current_snapshot = leader_by_snapshot_id.get(snapshot_id)
        before_snapshot = (
            leader_by_snapshot_id.get(int(before_row["id"]))
            if before_row is not None else None
        )
        next_snapshot = (
            leader_by_snapshot_id.get(int(next_row["id"]))
            if next_row is not None else None
        )
        before_state = (
            before_snapshot.leaders.get(leader_id)
            if before_snapshot else None
        )

        lines.extend([
            f"{event.get('game_date') or current_row['game_date']} | {leader_row.get('name') or event.get('title') or f'Leader {leader_id}'}",
            f"  Leader ID: {leader_id}",
            f"  Exit evidence type: {event.get('event_type')}",
            f"  Historian status: {leader_row.get('status') or 'Unknown'}",
            f"  Last confirmed present: {leader_row.get('last_seen_date') or (before_row['game_date'] if before_row is not None else 'Unknown')}",
            f"  First archive state after exit: {current_row['game_date']} ({current_row['archive_filename']})",
            f"  Previous archive state: {(before_row['game_date'] + ' (' + before_row['archive_filename'] + ')') if before_row is not None else 'None'}",
            f"  Following archive state: {(next_row['game_date'] + ' (' + next_row['archive_filename'] + ')') if next_row is not None else 'None'}",
            f"  Last assignment: {leader_row.get('latest_assignment') or 'Not recorded'}",
            f"  Last traits: {', '.join(leader_row.get('trait_names') or ()) or 'None recorded'}",
            "",
        ])

        if before_snapshot and current_snapshot:
            lines.extend([
                "  COUNTER CHANGES ACROSS EXIT WINDOW",
                f"    last_notification_id: {_counter_delta(before_snapshot.last_notification_id, current_snapshot.last_notification_id)}",
                f"    last_event_id: {_counter_delta(before_snapshot.last_event_id, current_snapshot.last_event_id)}",
                (
                    "    open_player_event_selection_history count: "
                    f"{before_snapshot.selected_player_event_count} -> "
                    f"{current_snapshot.selected_player_event_count} "
                    f"(delta {current_snapshot.selected_player_event_count - before_snapshot.selected_player_event_count:+d})"
                ),
                "",
            ])

        before_game = gamestate_for(before_row) if before_row is not None else None
        current_game = gamestate_for(current_row)
        next_game = gamestate_for(next_row) if next_row is not None else None

        if before_game and current_game:
            before_selection = _event_selection_ids(before_game)
            current_selection = _event_selection_ids(current_game)
            before_set = set(before_selection)
            new_selection_ids = [value for value in current_selection if value not in before_set]

            lines.extend([
                "  PLAYER EVENT-SELECTION DIFF",
                (
                    "    New player_event IDs in first post-exit snapshot: "
                    + (", ".join(str(value) for value in new_selection_ids) if new_selection_ids else "None detected")
                ),
                "",
            ])

            changed_keys = _changed_eventish_keys(
                _eventish_key_counts(before_game),
                _eventish_key_counts(current_game),
            )
            lines.append("  EVENT-LIKE SAVE KEY COUNT CHANGES")
            if changed_keys:
                for key, before_count, after_count in changed_keys:
                    lines.append(f"    {key}: {before_count} -> {after_count}")
            else:
                lines.append("    None detected")
            lines.append("")

        lines.append("  LAST ACTIVE LEADER RAW PROBE")
        if before_game:
            unmapped = _leader_unmapped_field_evidence(before_game, leader_id)
            if unmapped:
                for key, values in unmapped.items():
                    lines.append(f"    {key}: {' | '.join(values)}")
            else:
                lines.append("    No available_trait/cooldown/delayed_event value was found on the last active record.")
        else:
            lines.append("    Previous raw save unavailable.")

        if before_state is not None:
            lines.append(
                "    Cached leader flags: "
                + (", ".join(f"{key}={value}" for key, value in before_state.flag_values) or "None")
            )
            lines.append(
                "    Cached leader variables: "
                + (", ".join(f"{key}={value}" for key, value in before_state.variable_values) or "None")
            )
        lines.append("")

        for label, snapshot, game in (
            ("PREVIOUS", before_snapshot, before_game),
            ("FIRST POST-EXIT", current_snapshot, current_game),
            ("FOLLOWING", next_snapshot, next_game),
        ):
            lines.append(f"  {label} SNAPSHOT EVENT-TARGET / ID REFERENCES")
            aliases = snapshot.saved_event_target_names.get(leader_id, ()) if snapshot else ()
            lines.append("    Cached saved_event_target aliases: " + (", ".join(aliases) or "None"))

            if not game:
                lines.append("    Raw save unavailable.")
                continue

            raw_targets = _saved_event_target_blocks(game, leader_id)
            if raw_targets:
                for target in raw_targets:
                    lines.append(f"    Raw saved_event_target: {target}")
            else:
                lines.append("    Raw saved_event_target: None matched by exact leader ID")

            contexts = _leader_reference_contexts(game, leader_id)
            lines.append(f"    Event-adjacent raw ID contexts retained: {len(contexts)}")
            for context in contexts:
                lines.append(f"      - {context}")

        lines.extend([
            "",
            "  INTERPRETATION",
            "    This window is intentionally evidence-only. Correlated event IDs, counter changes, target aliases and raw references are candidates for future decoding; they are not yet promoted to a death or exit cause.",
            "",
        ])

    lines.extend([
        "RAW SAVE READ SUMMARY",
        "=====================",
        f"Unique raw archive saves opened by this targeted probe: {len(raw_cache)}",
        f"Raw archive read failures: {len(raw_errors)}",
    ])
    for path, message in sorted(raw_errors.items()):
        lines.append(f"  {path}: {message}")

    lines.extend([
        "",
        "NEXT-STEP NOTES",
        "===============",
        "1. New player_event IDs around an exit are useful correlation targets, not proof of cause.",
        "2. Any delayed_event / available_trait / cooldown evidence is preserved verbatim until semantics are demonstrated.",
        "3. saved_event_target blocks are matched by exact leader ID; mismatched IDs remain separate objects and are not silently merged.",
        "4. A future decoder can use the candidate event IDs/keys exposed here to resolve localisation or scripted-event definitions.",
        "",
    ])

    diagnostic_dir = Path(campaign["archive_dir"]) / "diagnostics"
    diagnostic_dir.mkdir(parents=True, exist_ok=True)
    path = diagnostic_dir / "Event_Character_Probe_Debug.txt"
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path
