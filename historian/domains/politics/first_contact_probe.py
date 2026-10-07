from __future__ import annotations

from pathlib import Path
import re
from typing import Callable

from ...db import Database
from ...save_reader import read_save_texts
from ...snapshot_cache import campaign_cache_dir, load_or_parse_snapshot
from ...core.stellaris_text import _extract_braced_after, _find_named_block
from .history import _publishable_diplomatic_actor


ProgressCallback = Callable[[int, int, dict], None]

_MAX_RAW_SAMPLES = 48
_RECENT_EDGE = 12
_CONTEXT_LIMIT = 18
_FIRST_CONTACT_KEY = re.compile(
    r"(?mi)^\s*([A-Za-z0-9_.:-]*first_contact[A-Za-z0-9_.:-]*)\s*="
)
_CONTACTISH_KEY = re.compile(
    r"(?mi)^\s*([A-Za-z0-9_.:-]*(?:contact|communication)[A-Za-z0-9_.:-]*)\s*="
)


def _collapse(value: str | None, limit: int = 900) -> str:
    if not value:
        return "None"
    compact = re.sub(r"\s+", " ", value).strip()
    if len(compact) > limit:
        return compact[: limit - 3] + "..."
    return compact or "None"


def _relation_scalar(relation, token: str) -> tuple[str, str] | None:
    for key, value in relation.scalars:
        if token in key.casefold():
            return key, value
    return None


def _communication_candidates(before, after) -> list[dict]:
    if before is None or after is None:
        return []

    result: list[dict] = []
    before_relations = before.relations
    after_relations = after.relations

    for country_id in sorted(set(after_relations) - set(before_relations)):
        relation = after_relations[country_id]
        if not _publishable_diplomatic_actor(relation):
            continue
        result.append({
            "kind": "relation_record_appeared",
            "country_id": int(country_id),
            "country_name": relation.country_name,
            "raw_field": None,
            "before": "<absent>",
            "after": "present",
        })

    for country_id in sorted(set(before_relations) & set(after_relations)):
        old_relation = before_relations[country_id]
        new_relation = after_relations[country_id]
        if not _publishable_diplomatic_actor(new_relation):
            continue

        old_comm = _relation_scalar(old_relation, "communicat")
        new_comm = _relation_scalar(new_relation, "communicat")
        if old_comm == new_comm:
            continue
        if old_comm is None and new_comm is None:
            continue

        result.append({
            "kind": "communications_changed",
            "country_id": int(country_id),
            "country_name": new_relation.country_name,
            "raw_field": (new_comm or old_comm)[0],
            "before": old_comm[1] if old_comm else "<absent>",
            "after": new_comm[1] if new_comm else "<absent>",
        })

    return result


def _assignment_rows(rows: list[dict], leader_snapshots: list, politics_snapshots: list) -> list[dict]:
    transitions: list[dict] = []

    for index in range(1, len(rows)):
        before_row = rows[index - 1]
        after_row = rows[index]
        before = leader_snapshots[index - 1]
        after = leader_snapshots[index]

        leader_ids = sorted(set(before.leaders) | set(after.leaders))
        interval_candidates = _communication_candidates(
            politics_snapshots[index - 1],
            politics_snapshots[index],
        )

        for leader_id in leader_ids:
            before_leader = before.leaders.get(leader_id)
            after_leader = after.leaders.get(leader_id)
            was_fc = bool(before_leader and before_leader.location_type == "first_contact_system")
            is_fc = bool(after_leader and after_leader.location_type == "first_contact_system")
            if was_fc == is_fc:
                continue

            leader = after_leader or before_leader
            transitions.append({
                "index": index,
                "kind": "assignment_started" if is_fc else "assignment_ended",
                "leader_id": int(leader_id),
                "leader_name": leader.name if leader is not None else f"Leader {leader_id}",
                "before_date": str(before_row["game_date"]),
                "after_date": str(after_row["game_date"]),
                "location_id_before": before_leader.location_id if before_leader is not None else None,
                "location_id_after": after_leader.location_id if after_leader is not None else None,
                "diplomatic_candidates": list(interval_candidates),
            })

    return transitions


def _selected_indices(total: int, transitions: list[dict]) -> list[int]:
    if total <= 0:
        return []

    selected: set[int] = {0, total - 1}
    selected.update(range(max(0, total - _RECENT_EDGE), total))

    for transition in transitions:
        index = int(transition["index"])
        selected.update(
            candidate
            for candidate in (index - 2, index - 1, index, index + 1)
            if 0 <= candidate < total
        )

    ordered = sorted(selected)
    if len(ordered) <= _MAX_RAW_SAMPLES:
        return ordered

    priority: list[int] = []
    transition_indices: set[int] = set()
    for transition in transitions:
        index = int(transition["index"])
        transition_indices.update(
            candidate
            for candidate in (index - 2, index - 1, index, index + 1)
            if 0 <= candidate < total
        )
    priority.extend(sorted(transition_indices))
    priority.extend(range(max(0, total - _RECENT_EDGE), total))
    priority.extend([0, total - 1])
    priority = list(dict.fromkeys(priority))

    if len(priority) >= _MAX_RAW_SAMPLES:
        return sorted(priority[:_MAX_RAW_SAMPLES])

    remaining = [value for value in ordered if value not in set(priority)]
    slots = _MAX_RAW_SAMPLES - len(priority)
    if slots >= len(remaining):
        return sorted(priority + remaining)
    if slots == 1:
        sampled = [remaining[len(remaining) // 2]]
    else:
        sampled = [
            remaining[round(slot * (len(remaining) - 1) / (slots - 1))]
            for slot in range(slots)
        ]
    return sorted(set(priority + sampled))


def _first_contact_contexts(gamestate: str) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    first_keys = tuple(dict.fromkeys(match.group(1) for match in _FIRST_CONTACT_KEY.finditer(gamestate)))
    contactish = tuple(dict.fromkeys(match.group(1) for match in _CONTACTISH_KEY.finditer(gamestate)))

    contexts: list[str] = []
    for match in _FIRST_CONTACT_KEY.finditer(gamestate):
        block = _extract_braced_after(gamestate, match.start())
        if block:
            shown = f"{match.group(1)}={{ {_collapse(block)} }}"
        else:
            start = max(0, match.start() - 260)
            end = min(len(gamestate), match.end() + 520)
            shown = _collapse(gamestate[start:end])
        if shown not in contexts:
            contexts.append(shown)
        if len(contexts) >= _CONTEXT_LIMIT:
            break

    manager = _find_named_block(gamestate, "first_contact_manager")
    if manager:
        shown = "first_contact_manager={ " + _collapse(manager, limit=1400) + " }"
        if shown not in contexts:
            contexts.insert(0, shown)

    return first_keys, contactish, tuple(contexts[:_CONTEXT_LIMIT])


def write_first_contact_probe(
    db: Database,
    campaign_id: int,
    *,
    progress: ProgressCallback | None = None,
) -> Path:
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist.")

    rows = [dict(row) for row in db.all_snapshots(campaign_id)]
    source_save = Path(campaign["source_save"])
    cache_dir = campaign_cache_dir(Path(campaign["archive_dir"]))

    leader_snapshots = []
    politics_snapshots = []
    cache_counts = {"hit": 0, "extend": 0, "miss": 0}

    for row in rows:
        (
            _profile,
            _ship_snapshot,
            leader_snapshot,
            _world_snapshot,
            _science_snapshot,
            _combat_snapshot,
            _technology_snapshot,
            politics_snapshot,
            cache_status,
        ) = load_or_parse_snapshot(
            archive_path=Path(row["archive_path"]),
            source_save=source_save,
            source_sha256=row["sha256"],
            snapshot_id=int(row["id"]),
            cache_dir=cache_dir,
        )
        leader_snapshots.append(leader_snapshot)
        politics_snapshots.append(politics_snapshot)
        cache_counts[cache_status] = cache_counts.get(cache_status, 0) + 1

    transitions = _assignment_rows(rows, leader_snapshots, politics_snapshots)
    selected = _selected_indices(len(rows), transitions)

    raw_rows: list[dict] = []
    failures: list[str] = []
    for position, index in enumerate(selected, start=1):
        row = rows[index]
        if progress is not None:
            progress(position, len(selected), row)
        try:
            _meta, gamestate = read_save_texts(Path(row["archive_path"]))
            first_keys, contactish_keys, contexts = _first_contact_contexts(gamestate)
            raw_rows.append({
                "game_date": str(row["game_date"]),
                "archive_filename": str(row["archive_filename"]),
                "first_contact_keys": first_keys,
                "contactish_keys": contactish_keys,
                "contexts": contexts,
                "literal_first_contact_count": gamestate.casefold().count("first_contact"),
            })
        except Exception as exc:
            failures.append(f"{row['game_date']} | {row['archive_filename']} | {exc}")

    diagnostics = Path(campaign["archive_dir"]) / "diagnostics"
    diagnostics.mkdir(parents=True, exist_ok=True)
    path = diagnostics / "First_Contact_Probe_Debug.txt"

    lines = [
        "STELLARIS HISTORIAN - FIRST CONTACT EVIDENCE PROBE",
        "",
        "v0.0.49 diagnostic foundation.",
        "This probe correlates cached First Contact leader assignments with adjacent Politics/Diplomacy state and targeted raw-save structures.",
        "It does NOT publish an exact First Contact completion date, counterpart, response choice or diplomatic cause unless a future decoder proves those fields directly.",
        "",
        f"Campaign: {campaign['empire_name']}",
        f"Archived snapshots: {len(rows)}",
        f"First Contact assignment transitions: {len(transitions)}",
        f"Targeted raw snapshots: {len(selected)} (maximum {_MAX_RAW_SAMPLES})",
        f"Cache: {cache_counts.get('hit', 0)} hit / {cache_counts.get('extend', 0)} extend / {cache_counts.get('miss', 0)} miss",
        "",
        "FIRST CONTACT ASSIGNMENT WINDOWS",
        "================================",
    ]

    if not transitions:
        lines.append("No leader transition into or out of location.type=first_contact_system was observed in the cached archive.")
    else:
        for item in transitions:
            verb = "STARTED" if item["kind"] == "assignment_started" else "ENDED"
            lines.extend([
                f"{item['before_date']} -> {item['after_date']} | {verb} | {item['leader_name']} (leader {item['leader_id']})",
                f"  location id before: {item['location_id_before']}",
                f"  location id after: {item['location_id_after']}",
                "  Date rule: the assignment transition occurred between these archived states; neither endpoint is automatically the exact in-game event timestamp.",
            ])
            candidates = item["diplomatic_candidates"]
            if not candidates:
                lines.append("  Diplomatic correlation candidates: none in structured Politics/Diplomacy state for the same interval.")
            else:
                lines.append("  Diplomatic correlation candidates (diagnostic only):")
                for candidate in candidates:
                    detail = f"{candidate['kind']} | {candidate['country_name']} (country {candidate['country_id']})"
                    if candidate.get("raw_field"):
                        detail += f" | {candidate['raw_field']}: {candidate['before']} -> {candidate['after']}"
                    lines.append("    - " + detail)
            lines.append("")

    lines.extend([
        "TARGETED RAW FIRST-CONTACT STRUCTURES",
        "====================================",
        "Raw samples are selected around First Contact assignment transitions plus the recent campaign edge. Context is evidence-only and may include implementation keys whose semantics are not yet established.",
        "",
    ])

    if not raw_rows:
        lines.append("No raw samples were successfully read.")
    else:
        for item in raw_rows:
            lines.extend([
                f"{item['game_date']} | {item['archive_filename']}",
                f"  literal 'first_contact' occurrences: {item['literal_first_contact_count']}",
                "  first_contact keys: " + (", ".join(item["first_contact_keys"]) or "None"),
                "  contact/communication keys: " + (", ".join(item["contactish_keys"]) or "None"),
            ])
            if item["contexts"]:
                lines.append("  raw contexts:")
                for context in item["contexts"]:
                    lines.append("    - " + context)
            else:
                lines.append("  raw contexts: None")
            lines.append("")

    lines.extend(["RAW READ FAILURES", "================="])
    if failures:
        lines.extend("- " + value for value in failures)
    else:
        lines.append("None")

    lines.extend([
        "",
        "INTERPRETATION RULE",
        "===================",
        "A First Contact assignment ending and a communications/relation transition in the same archived interval are correlation evidence only. They are not promoted to an exact First Contact event until the retained raw save structure identifies the counterpart and event semantics directly.",
    ])

    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path
