from __future__ import annotations

from collections import Counter
from pathlib import Path
import re

from ...core.stellaris_text import _extract_braced_after, _find_named_block
from ...db import Database
from ...save_reader import read_save_texts


_EXIT_EVENT_TYPES = {
    "leader_death_recorded",
    "leader_tombstone_unconfirmed",
    "leader_missing_unconfirmed",
}

_TYPED_LEADER_KEYS = (
    "leader",
    "governor",
    "ruler",
    "heir",
    "commander",
    "admiral",
    "scientist",
    "official",
)



def _collapse(value: str | None, limit: int = 1200) -> str:
    if not value:
        return "None"
    compact = re.sub(r"\s+", " ", value).strip()
    if len(compact) > limit:
        return compact[: limit - 3] + "..."
    return compact or "None"



def _scalar(block: str | None, key: str) -> str | None:
    if not block:
        return None
    match = re.search(
        rf'(?m)^\s*{re.escape(key)}\s*=\s*(?:"([^"]*)"|([^\s{{}}]+))',
        block,
    )
    if not match:
        return None
    return match.group(1) if match.group(1) is not None else match.group(2)



def _int_scalar(block: str | None, key: str) -> int | None:
    raw = _scalar(block, key)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None



def _all_braced_blocks(text: str, key: str) -> list[str]:
    blocks: list[str] = []
    pattern = re.compile(rf'(?m)^\s*{re.escape(key)}\s*=\s*\{{')
    for match in pattern.finditer(text):
        block = _extract_braced_after(text, match.start())
        if block is not None:
            blocks.append(block)
    return blocks



def _message_blocks(gamestate: str) -> dict[int, str]:
    result: dict[int, str] = {}
    for block in _all_braced_blocks(gamestate, "message"):
        notification_id = _int_scalar(block, "notification")
        if notification_id is None:
            continue
        result[notification_id] = block
    return result



def _message_variables(block: str) -> tuple[tuple[str, str], ...]:
    variables = _find_named_block(block, "variables")
    if not variables:
        return ()

    result: list[tuple[str, str]] = []
    for item in re.finditer(r'(?m)^\s*\{', variables):
        child = _extract_braced_after(variables, item.start())
        if not child:
            continue
        key = _scalar(child, "key")
        value = _scalar(child, "value")
        if key and value is not None:
            pair = (key, value)
            if pair not in result:
                result.append(pair)
    return tuple(result)



def _message_targets(block: str) -> tuple[tuple[str, str], ...]:
    targets: list[tuple[str, str]] = []
    for match in re.finditer(
        r'(?m)^\s*(target_[A-Za-z0-9_]+|leader|governor|ruler|heir|commander|admiral|scientist|official)\s*=\s*(?:"([^"]*)"|([^\s{}]+))',
        block,
    ):
        key = match.group(1)
        value = match.group(2) if match.group(2) is not None else match.group(3)
        pair = (key, value)
        if pair not in targets:
            targets.append(pair)
    return tuple(targets)



def _typed_leader_references(block: str, leader_id: int) -> tuple[str, ...]:
    refs: list[str] = []
    for key in _TYPED_LEADER_KEYS:
        if re.search(
            rf'(?m)^\s*{re.escape(key)}\s*=\s*{leader_id}(?:\s|$)',
            block,
        ):
            refs.append(f"{key}={leader_id}")

    # Also accept an explicit typed reference such as:
    #   type=leader
    #   id=110
    typed_patterns = (
        rf'type\s*=\s*"?leader"?.{{0,260}}?id\s*=\s*{leader_id}(?:\s|$)',
        rf'id\s*=\s*{leader_id}(?:\s|$).{{0,260}}?type\s*=\s*"?leader"?',
    )
    for pattern in typed_patterns:
        if re.search(pattern, block, flags=re.IGNORECASE | re.DOTALL):
            refs.append(f"type=leader,id={leader_id}")
            break

    return tuple(dict.fromkeys(refs))



def _message_summary(block: str, leader_id: int | None = None) -> dict:
    variables = _message_variables(block)
    targets = _message_targets(block)
    typed_refs = (
        _typed_leader_references(block, leader_id)
        if leader_id is not None
        else ()
    )
    return {
        "notification": _int_scalar(block, "notification"),
        "type": _scalar(block, "type"),
        "localization": _scalar(block, "localization"),
        "message_type": _scalar(block, "message_type"),
        "date": _scalar(block, "date"),
        "end": _scalar(block, "end"),
        "receiver": _scalar(block, "receiver"),
        "custom_message_text": _scalar(block, "custom_message_text"),
        "variables": variables,
        "targets": targets,
        "typed_leader_refs": typed_refs,
        "raw": _collapse(block),
    }



def _event_selection_records(gamestate: str) -> dict[int, dict[str, str | int | None]]:
    history = _find_named_block(gamestate, "open_player_event_selection_history")
    selected = _find_named_block(history or "", "selected")
    if not selected:
        return {}

    result: dict[int, dict[str, str | int | None]] = {}
    for match in re.finditer(r'(?m)^\s*\{', selected):
        child = _extract_braced_after(selected, match.start())
        if not child:
            continue
        event_id = _int_scalar(child, "player_event")
        if event_id is None:
            continue
        result[event_id] = {
            "human": _int_scalar(child, "human"),
            "option": _int_scalar(child, "option"),
            "raw": _collapse(child, 500),
        }
    return result



def _script_event_ids(gamestate: str) -> Counter[str]:
    result: Counter[str] = Counter()
    for match in re.finditer(
        r'(?m)^\s*event_id\s*=\s*(?:"([^"]+)"|([^\s{}]+))',
        gamestate,
    ):
        value = match.group(1) if match.group(1) is not None else match.group(2)
        if value:
            result[value] += 1
    return result



def _scalar_occurrences(gamestate: str, key: str) -> Counter[str]:
    result: Counter[str] = Counter()
    for match in re.finditer(
        rf'(?m)^\s*{re.escape(key)}\s*=\s*(?:"([^"]*)"|([^\s{{}}]+))',
        gamestate,
    ):
        value = match.group(1) if match.group(1) is not None else match.group(2)
        if value is not None:
            result[value] += 1
    return result



def _counter_added(before: Counter[str], after: Counter[str]) -> list[tuple[str, int]]:
    added: list[tuple[str, int]] = []
    for key in sorted(set(before) | set(after)):
        delta = after.get(key, 0) - before.get(key, 0)
        if delta > 0:
            added.append((key, delta))
    return added



def _leader_exit_rows(db: Database, campaign_id: int) -> tuple[list[dict], dict[int, dict]]:
    exits = [
        dict(row)
        for row in db.leader_career_events(campaign_id)
        if row["event_type"] in _EXIT_EVENT_TYPES
    ]
    leaders = {
        int(row["leader_id"]): dict(row)
        for row in db.leader_registry(campaign_id)
    }
    return exits, leaders


def write_notification_event_decoder(
    db: Database,
    campaign_id: int,
) -> Path:
    """Decode retained message/notification objects around leader exits.

    This is evidence discovery only. Leader exits are read from the already
    rebuilt database, then only the narrow raw-save windows around those exits
    are opened. A message is linked to a leader only when a typed leader
    reference is retained in the message itself. Timing alone is never
    promoted to causation.
    """
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist.")

    rows = list(db.all_snapshots(campaign_id))
    exit_events, leader_rows = _leader_exit_rows(db, campaign_id)
    row_index = {int(row["id"]): index for index, row in enumerate(rows)}

    raw_cache: dict[str, str] = {}
    raw_errors: dict[str, str] = {}

    def gamestate_for(row) -> str | None:
        if row is None:
            return None
        path = str(row["archive_path"])
        if path in raw_cache:
            return raw_cache[path]
        if path in raw_errors:
            return None
        try:
            _meta, gamestate = read_save_texts(Path(path))
        except Exception as exc:  # diagnostic must not break review
            raw_errors[path] = str(exc)
            return None
        raw_cache[path] = gamestate
        return gamestate

    lines = [
        "STELLARIS HISTORIAN - NOTIFICATION / EVENT OBJECT DECODER",
        "",
        "Purpose: decode retained Stellaris message/notification objects around unresolved leader exits.",
        "A notification-ID increase proves that notifications were allocated in an interval, but a missing retained message object means its original payload may already have expired from the save.",
        "A message is linked to a leader only when an explicit typed leader reference survives inside that message object. Timing alone is correlation, not causation.",
        "The generic save_on_death field is NOT treated as leader-death evidence; Stellaris also stores it on unrelated objects such as countries and planets.",
        "",
        f"Campaign: {campaign['empire_name']}",
        f"Snapshots available: {len(rows)}",
        f"Leader exits decoded: {len(exit_events)}",
        "",
        "LEADER EXIT NOTIFICATION WINDOWS",
        "================================",
        "",
    ]

    for event in exit_events:
        snapshot_id = int(event["snapshot_id"])
        index = row_index.get(snapshot_id)
        if index is None:
            continue

        leader_id = int(event["leader_id"])
        leader_row = leader_rows.get(leader_id, {})
        current_row = rows[index]
        before_row = rows[index - 1] if index > 0 else None
        next_row = rows[index + 1] if index + 1 < len(rows) else None

        before_game = gamestate_for(before_row)
        current_game = gamestate_for(current_row)
        next_game = gamestate_for(next_row)

        lines.extend([
            f"{event.get('game_date') or current_row['game_date']} | {leader_row.get('name') or f'Leader {leader_id}'}",
            f"  Leader ID: {leader_id}",
            f"  Exit evidence: {event.get('event_type')}",
            f"  Last confirmed present: {leader_row.get('last_seen_date') or (before_row['game_date'] if before_row is not None else 'Unknown')}",
            f"  First archived state after exit: {current_row['game_date']} ({current_row['archive_filename']})",
            "",
        ])

        before_last_notification = _int_scalar(before_game, "last_notification_id")
        current_last_notification = _int_scalar(current_game, "last_notification_id")

        allocated_ids: list[int] = []
        if (
            before_last_notification is not None
            and current_last_notification is not None
            and current_last_notification >= before_last_notification
        ):
            allocated_ids = list(
                range(before_last_notification + 1, current_last_notification + 1)
            )

        lines.append("  NOTIFICATION ID ALLOCATION")
        lines.append(
            f"    last_notification_id: {before_last_notification if before_last_notification is not None else 'Not observed'} -> {current_last_notification if current_last_notification is not None else 'Not observed'}"
        )
        lines.append(
            "    IDs allocated in interval: "
            + (", ".join(str(value) for value in allocated_ids) if allocated_ids else "None detected")
        )

        if before_game and current_game:
            before_messages = _message_blocks(before_game)
            current_messages = _message_blocks(current_game)
            next_messages = _message_blocks(next_game) if next_game else {}

            lines.append(
                "    Retained message IDs before exit: "
                + (", ".join(str(v) for v in sorted(before_messages)) or "None")
            )
            lines.append(
                "    Retained message IDs first post-exit: "
                + (", ".join(str(v) for v in sorted(current_messages)) or "None")
            )

            newly_retained = sorted(set(current_messages) - set(before_messages))
            expired = sorted(set(before_messages) - set(current_messages))
            lines.append(
                "    Newly retained message objects: "
                + (", ".join(str(v) for v in newly_retained) or "None")
            )
            lines.append(
                "    Previously retained message objects now absent: "
                + (", ".join(str(v) for v in expired) or "None")
            )
            lines.append("")

            lines.append("  ALLOCATED NOTIFICATION OBJECTS")
            if not allocated_ids:
                lines.append("    No new notification IDs were allocated in this archive interval.")

            for notification_id in allocated_ids:
                block = current_messages.get(notification_id)
                later_block = next_messages.get(notification_id)
                if block is None and later_block is None:
                    lines.append(
                        f"    #{notification_id}: allocated in this interval, but no message object is retained in the first post-exit or following archived state."
                    )
                    continue

                source_label = "first post-exit snapshot" if block is not None else "following snapshot"
                message = _message_summary(block or later_block or "", leader_id)
                lines.append(f"    #{notification_id}: retained in {source_label}")
                lines.append(f"      type: {message['type'] or 'Not recorded'}")
                lines.append(f"      localization: {message['localization'] or 'Not recorded'}")
                lines.append(f"      message_type: {message['message_type'] or 'Not recorded'}")
                lines.append(f"      date: {message['date'] or 'Not recorded'}")
                lines.append(f"      end: {message['end'] or 'Not recorded'}")
                lines.append(f"      receiver: {message['receiver'] or 'Not recorded'}")
                if message["variables"]:
                    lines.append(
                        "      variables: "
                        + "; ".join(f"{key}={value}" for key, value in message["variables"])
                    )
                else:
                    lines.append("      variables: None")
                if message["targets"]:
                    lines.append(
                        "      targets: "
                        + "; ".join(f"{key}={value}" for key, value in message["targets"])
                    )
                else:
                    lines.append("      targets: None")
                lines.append(
                    "      custom_message_text: "
                    + (message["custom_message_text"] or "None")
                )
                if message["typed_leader_refs"]:
                    lines.append(
                        "      EXACT TYPED LEADER LINK: "
                        + ", ".join(message["typed_leader_refs"])
                    )
                else:
                    lines.append("      Exact typed leader link: None")
                lines.append(f"      raw: {message['raw']}")

            lines.append("")
            lines.append("  PLAYER EVENT-SELECTION RECORDS")
            before_events = _event_selection_records(before_game)
            current_events = _event_selection_records(current_game)
            new_player_events = sorted(set(current_events) - set(before_events))
            if new_player_events:
                for event_id in new_player_events:
                    item = current_events[event_id]
                    lines.append(
                        f"    player_event={event_id} | human={item.get('human')} | option={item.get('option')} | raw={item.get('raw')}"
                    )
            else:
                lines.append("    No new player_event selection IDs retained in this interval.")

            lines.append("")
            lines.append("  SCRIPT EVENT-ID CHANGES")
            script_added = _counter_added(
                _script_event_ids(before_game),
                _script_event_ids(current_game),
            )
            if script_added:
                for event_key, count in script_added:
                    lines.append(f"    newly present event_id {event_key} x{count}")
            else:
                lines.append("    No newly present scripted event_id values detected.")

            lines.append("")
            lines.append("  OTHER MESSAGE-TEXT / LIFETIME FLAGS")
            custom_added = _counter_added(
                _scalar_occurrences(before_game, "custom_message_text"),
                _scalar_occurrences(current_game, "custom_message_text"),
            )
            if custom_added:
                for text, count in custom_added:
                    lines.append(f"    new custom_message_text x{count}: {text}")
            else:
                lines.append("    No newly retained custom_message_text scalar detected.")

            before_sod = sum(_scalar_occurrences(before_game, "save_on_death").values())
            current_sod = sum(_scalar_occurrences(current_game, "save_on_death").values())
            lines.append(
                f"    save_on_death occurrences: {before_sod} -> {current_sod} (generic object-lifetime flag; not death evidence)"
            )
        else:
            lines.append("    Raw save data unavailable for one side of this interval.")

        lines.extend([
            "",
            "  INTERPRETATION",
            "    Only an explicit typed leader reference inside a retained message object can directly connect that message to this leader. Counter movement, an allocated-but-expired notification ID, or a new player_event ID remains correlation evidence only.",
            "",
        ])

    lines.extend([
        "RAW SAVE READ SUMMARY",
        "=====================",
        f"Unique raw archive saves opened: {len(raw_cache)}",
        f"Raw archive read failures: {len(raw_errors)}",
    ])
    for path, message in sorted(raw_errors.items()):
        lines.append(f"  {path}: {message}")

    lines.extend([
        "",
        "DECODER RULES",
        "=============",
        "- Retained message fields such as type/localization/date/variables/targets are raw save evidence.",
        "- Missing message objects are reported as expired/not retained; their payload is not invented.",
        "- Notification-ID gaps are preserved because ephemeral messages can disappear before the next quarterly archive.",
        "- player_event IDs are not equated with scripted event keys unless a later parser proves that mapping.",
        "- save_on_death is not interpreted as proof that a leader died.",
        "",
    ])

    diagnostic_dir = Path(campaign["archive_dir"]) / "diagnostics"
    diagnostic_dir.mkdir(parents=True, exist_ok=True)
    path = diagnostic_dir / "Notification_Event_Decoder_Debug.txt"
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path
