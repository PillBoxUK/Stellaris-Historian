from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import re

from ...save_reader import read_save_texts
from .notification_decoder import _int_scalar, _message_blocks, _message_summary


_UNRESOLVED_EXIT_TYPES = {
    "leader_tombstone_unconfirmed",
    "leader_missing_unconfirmed",
}

_DEATH_MESSAGE_TYPE = "LEADER_DEATH"
_DEATH_LOCALISATION = "MESSAGE_LEADER_LOST_DESC"


def _clean_display(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    # Stellaris colour/highlight wrapper, e.g. \x11H71\x11! Years.
    text = re.sub(r"\x11[A-Za-z](.*?)\x11!", r"\1", text)
    text = "".join(ch if ord(ch) >= 32 else " " for ch in text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _normalise_name(value: object | None) -> str:
    cleaned = _clean_display(value) or ""
    return cleaned.casefold()


def _stellaris_ordinal(value: str | None) -> int | None:
    if not value:
        return None
    try:
        year, month, day = (int(part) for part in str(value).split("."))
    except (TypeError, ValueError):
        return None
    if month < 1 or month > 12 or day < 1 or day > 30:
        return None
    return year * 360 + (month - 1) * 30 + (day - 1)


def _date_inside_exit_interval(
    *,
    last_seen: str | None,
    death_date: str | None,
    first_absent: str | None,
) -> bool:
    last = _stellaris_ordinal(last_seen)
    death = _stellaris_ordinal(death_date)
    absent = _stellaris_ordinal(first_absent)
    if last is None or death is None or absent is None:
        return False
    return last < death <= absent


def _variable_map(message: dict) -> dict[str, str]:
    return {
        str(key): str(value)
        for key, value in message.get("variables", ())
    }


def _death_body(
    *,
    name: str,
    leader_class: str | None,
    death_date: str,
    notification_id: int,
    age: str | None,
    time_served: str | None,
    reason: str | None,
) -> str:
    class_text = _clean_display(leader_class)
    subject = f"{class_text} {name}" if class_text else name
    parts = [
        f"A retained leader-death notification dated {death_date} identifies {subject} as dead."
    ]
    if time_served:
        parts.append(f"The notification records {time_served} of service.")
    if age:
        parts.append(f"It records age {age}.")
    if reason:
        parts.append(f'The retained notice states: "{reason}"')
    parts.append(f"Source notification: #{notification_id}.")
    return " ".join(parts)


def _discover_notification_deaths(
    snapshot_rows,
    leader_history: dict,
) -> dict:
    """Return conservative notification-derived death promotions.

    A promotion is accepted only when a newly allocated retained message is a
    LEADER_DEATH / MESSAGE_LEADER_LOST_DESC notification, its LEADER variable
    uniquely matches one known player leader, that same leader has an
    unresolved exit in the first post-exit snapshot, and the message date lies
    strictly after the last confirmed presence and no later than that first
    absent snapshot.
    """
    rows = list(snapshot_rows)
    row_index = {int(row["id"]): index for index, row in enumerate(rows)}

    leaders = {
        int(row["leader_id"]): row
        for row in leader_history.get("leaders", [])
    }

    name_to_ids: dict[str, set[int]] = defaultdict(set)
    for leader_id, row in leaders.items():
        key = _normalise_name(row.get("name"))
        if key:
            name_to_ids[key].add(leader_id)

    exits_by_snapshot: dict[int, list[dict]] = defaultdict(list)
    for event in leader_history.get("events", []):
        if event.get("event_type") not in _UNRESOLVED_EXIT_TYPES:
            continue
        snapshot_id = event.get("snapshot_id")
        if snapshot_id is None:
            continue
        exits_by_snapshot[int(snapshot_id)].append(event)

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
        except Exception as exc:
            raw_errors[path] = str(exc)
            return None
        raw_cache[path] = gamestate
        return gamestate

    promotions: list[dict] = []
    rejected: list[dict] = []
    promoted_ids: set[int] = set()

    for snapshot_id, exit_events in sorted(exits_by_snapshot.items()):
        index = row_index.get(snapshot_id)
        if index is None or index <= 0:
            continue

        current_row = rows[index]
        before_row = rows[index - 1]
        next_row = rows[index + 1] if index + 1 < len(rows) else None

        before_game = gamestate_for(before_row)
        current_game = gamestate_for(current_row)
        next_game = gamestate_for(next_row)
        if not before_game or not current_game:
            continue

        before_last = _int_scalar(before_game, "last_notification_id")
        current_last = _int_scalar(current_game, "last_notification_id")
        if before_last is None or current_last is None or current_last < before_last:
            continue

        allocated_ids = range(before_last + 1, current_last + 1)
        current_messages = _message_blocks(current_game)
        next_messages = _message_blocks(next_game) if next_game else {}
        exiting_ids = {int(event["leader_id"]) for event in exit_events}

        for notification_id in allocated_ids:
            block = current_messages.get(notification_id) or next_messages.get(notification_id)
            if not block:
                continue

            message = _message_summary(block)
            if message.get("type") != _DEATH_MESSAGE_TYPE:
                continue
            if message.get("localization") != _DEATH_LOCALISATION:
                rejected.append({
                    "notification_id": notification_id,
                    "reason": "LEADER_DEATH message used an unexpected localisation key",
                    "localization": message.get("localization"),
                })
                continue

            variables = _variable_map(message)
            retained_name = _clean_display(variables.get("LEADER"))
            if not retained_name:
                rejected.append({
                    "notification_id": notification_id,
                    "reason": "LEADER_DEATH message had no LEADER variable",
                })
                continue

            matching_ids = name_to_ids.get(_normalise_name(retained_name), set())
            if len(matching_ids) != 1:
                rejected.append({
                    "notification_id": notification_id,
                    "leader_name": retained_name,
                    "reason": (
                        "LEADER variable did not uniquely identify one known player leader"
                    ),
                    "matching_ids": tuple(sorted(matching_ids)),
                })
                continue

            leader_id = next(iter(matching_ids))
            if leader_id not in exiting_ids:
                rejected.append({
                    "notification_id": notification_id,
                    "leader_id": leader_id,
                    "leader_name": retained_name,
                    "reason": "named leader did not have an unresolved exit in this snapshot",
                })
                continue

            if leader_id in promoted_ids:
                continue

            leader = leaders.get(leader_id, {})
            death_date = _clean_display(message.get("date"))
            if not _date_inside_exit_interval(
                last_seen=leader.get("last_seen_date"),
                death_date=death_date,
                first_absent=str(current_row["game_date"]),
            ):
                rejected.append({
                    "notification_id": notification_id,
                    "leader_id": leader_id,
                    "leader_name": retained_name,
                    "reason": "notification date did not fall inside the leader exit interval",
                    "last_seen": leader.get("last_seen_date"),
                    "death_date": death_date,
                    "first_absent": str(current_row["game_date"]),
                })
                continue

            age = _clean_display(variables.get("AGE"))
            time_served = _clean_display(variables.get("TIME_SERVED"))
            leader_class = _clean_display(variables.get("CLASS")) or _clean_display(
                leader.get("leader_class")
            )
            reason = _clean_display(message.get("custom_message_text"))

            promotions.append({
                "leader_id": leader_id,
                "leader_name": str(leader.get("name") or retained_name),
                "snapshot_id": snapshot_id,
                "first_absent_date": str(current_row["game_date"]),
                "notification_id": notification_id,
                "death_date": death_date,
                "recorded_age": age,
                "time_served": time_served,
                "recorded_class": leader_class,
                "reason": reason,
                "evidence_kind": "notification_leader_death_named",
                "message_type": message.get("type"),
                "localization": message.get("localization"),
                "body": _death_body(
                    name=str(leader.get("name") or retained_name),
                    leader_class=leader_class,
                    death_date=death_date or str(current_row["game_date"]),
                    notification_id=notification_id,
                    age=age,
                    time_served=time_served,
                    reason=reason,
                ),
            })
            promoted_ids.add(leader_id)

    return {
        "promotions": promotions,
        "rejected": rejected,
        "raw_reads": len(raw_cache),
        "raw_errors": raw_errors,
    }


def apply_notification_deaths(
    snapshot_rows,
    leader_history: dict,
) -> dict:
    """Promote validated retained LEADER_DEATH messages into leader history."""
    result = _discover_notification_deaths(snapshot_rows, leader_history)
    promotions = result["promotions"]
    if not promotions:
        result["confirmed"] = 0
        return result

    leaders = {
        int(row["leader_id"]): row
        for row in leader_history.get("leaders", [])
    }
    promotion_by_key = {
        (int(row["leader_id"]), int(row["snapshot_id"])): row
        for row in promotions
    }

    kept_events: list[dict] = []
    for event in leader_history.get("events", []):
        key = (int(event.get("leader_id", -1)), int(event.get("snapshot_id", -1)))
        if key in promotion_by_key and event.get("event_type") in _UNRESOLVED_EXIT_TYPES:
            continue
        kept_events.append(event)

    for promotion in promotions:
        leader_id = int(promotion["leader_id"])
        leader = leaders.get(leader_id)
        if leader is not None:
            leader.update({
                "status": "dead_confirmed",
                "death_date": promotion["death_date"],
                "death_reason_key": (
                    "custom_message_text" if promotion.get("reason") else None
                ),
                "death_reason_value": promotion.get("reason"),
                "death_evidence_kind": promotion["evidence_kind"],
                "death_first_observed_date": promotion["first_absent_date"],
            })

        death_date = str(promotion["death_date"])
        snapshot_id = int(promotion["snapshot_id"])
        kept_events.append({
            "event_key": (
                f"leader:{leader_id}:leader_death_recorded:{death_date}:{snapshot_id}"
            ),
            "snapshot_id": snapshot_id,
            "game_date": death_date,
            "event_type": "leader_death_recorded",
            "leader_id": leader_id,
            "title": f"{promotion['leader_name']} Died",
            "body": promotion["body"],
            "visible": 1,
            "confidence": "high",
            "date_kind": "exact_notification_date",
            "notification_id": promotion["notification_id"],
            "death_evidence_kind": promotion["evidence_kind"],
            "recorded_age": promotion.get("recorded_age"),
            "time_served": promotion.get("time_served"),
            "death_reason": promotion.get("reason"),
        })

    leader_history["events"] = sorted(
        kept_events,
        key=lambda event: (
            str(event.get("game_date") or ""),
            str(event.get("event_type") or ""),
            int(event.get("leader_id") or -1),
        ),
    )
    result["confirmed"] = len(promotions)
    return result


def promote_notification_deaths_in_database(db, campaign_id: int) -> dict:
    """Apply the same promotion after incremental Update History processing."""
    snapshot_rows = list(db.all_snapshots(campaign_id))
    leader_history = {
        "leaders": [dict(row) for row in db.leader_registry(campaign_id)],
        "events": [dict(row) for row in db.leader_career_events(campaign_id, visible_only=False)],
    }
    result = apply_notification_deaths(snapshot_rows, leader_history)
    promotions = result.get("promotions", [])
    if not promotions:
        return result

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db.connect() as con:
        for promotion in promotions:
            leader_id = int(promotion["leader_id"])
            snapshot_id = int(promotion["snapshot_id"])
            death_date = str(promotion["death_date"])
            reason = promotion.get("reason")

            con.execute(
                """
                DELETE FROM leader_career_events
                WHERE campaign_id=? AND leader_id=? AND snapshot_id=?
                  AND event_type IN ('leader_tombstone_unconfirmed','leader_missing_unconfirmed')
                """,
                (campaign_id, leader_id, snapshot_id),
            )
            con.execute(
                """
                INSERT OR REPLACE INTO leader_career_events(
                    campaign_id, event_key, snapshot_id, game_date,
                    event_type, leader_id, title, body, visible, confidence,
                    date_kind, created_utc
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    campaign_id,
                    f"leader:{leader_id}:leader_death_recorded:{death_date}:{snapshot_id}",
                    snapshot_id,
                    death_date,
                    "leader_death_recorded",
                    leader_id,
                    f"{promotion['leader_name']} Died",
                    promotion["body"],
                    1,
                    "high",
                    "exact_notification_date",
                    now,
                ),
            )
            con.execute(
                """
                UPDATE leader_registry
                SET status='dead_confirmed', latest_is_ruler=0, latest_is_heir=0
                WHERE campaign_id=? AND leader_id=?
                """,
                (campaign_id, leader_id),
            )
            con.execute(
                """
                UPDATE leader_deep_evidence
                SET death_date=?, death_reason_key=?, death_reason_value=?,
                    death_evidence_kind=?, death_first_observed_date=?, updated_utc=?
                WHERE campaign_id=? AND leader_id=?
                """,
                (
                    death_date,
                    "custom_message_text" if reason else None,
                    reason,
                    promotion["evidence_kind"],
                    promotion["first_absent_date"],
                    now,
                    campaign_id,
                    leader_id,
                ),
            )

    return result


def write_notification_death_diagnostic(
    archive_dir: Path,
    result: dict,
) -> Path:
    path = Path(archive_dir) / "Notification_Death_Evidence_Debug.txt"
    path.parent.mkdir(parents=True, exist_ok=True)

    promotions = result.get("promotions", [])
    rejected = result.get("rejected", [])
    raw_errors = result.get("raw_errors", {})

    lines = [
        "STELLARIS HISTORIAN - NOTIFICATION-DERIVED LEADER DEATH EVIDENCE",
        "",
        "Purpose: promote only validated retained LEADER_DEATH notifications into confirmed leader history.",
        "A named death is accepted only when the retained message is LEADER_DEATH / MESSAGE_LEADER_LOST_DESC, the LEADER variable uniquely matches one known player leader, that leader exits in the same archive interval, and the notification date lies inside that exit interval.",
        "",
        f"Confirmed notification-derived deaths: {len(promotions)}",
        f"Rejected/ambiguous death-message candidates: {len(rejected)}",
        f"Unique raw archive saves opened: {result.get('raw_reads', 0)}",
        f"Raw archive read failures: {len(raw_errors)}",
        "",
        "CONFIRMED",
        "=========",
    ]

    if not promotions:
        lines.append("None")
    for item in promotions:
        lines.extend([
            f"{item['death_date']} | {item['leader_name']} | Leader ID {item['leader_id']}",
            f"  Notification: #{item['notification_id']}",
            f"  Message type: {item['message_type']}",
            f"  Localisation: {item['localization']}",
            f"  Recorded class: {item.get('recorded_class') or 'Not recorded'}",
            f"  Recorded age: {item.get('recorded_age') or 'Not recorded'}",
            f"  Recorded service: {item.get('time_served') or 'Not recorded'}",
            f"  Reason/custom text: {item.get('reason') or 'Not recorded'}",
            f"  Evidence kind: {item['evidence_kind']}",
            f"  First archived state after death: {item['first_absent_date']}",
            "",
        ])

    lines.extend(["REJECTED / AMBIGUOUS", "===================="])
    if not rejected:
        lines.append("None")
    for item in rejected:
        lines.append(
            f"Notification #{item.get('notification_id', '?')}: {item.get('reason', 'Rejected')}"
        )
        for key in ("leader_name", "leader_id", "matching_ids", "last_seen", "death_date", "first_absent", "localization"):
            if item.get(key) not in (None, (), []):
                lines.append(f"  {key}: {item[key]}")

    if raw_errors:
        lines.extend(["", "RAW READ ERRORS", "==============="])
        for raw_path, message in sorted(raw_errors.items()):
            lines.append(f"{raw_path}: {message}")

    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path
