from __future__ import annotations

from pathlib import Path
import hashlib
import json
import re

from ...db import Database

from .cache import snapshot_to_dict
from .models import DiplomaticRelationState, PoliticsSnapshot


def _humanise(value: str | None) -> str:
    if not value:
        return "None"
    result = str(value)
    for prefix in ("gov_", "auth_", "ethic_", "civic_", "tr_", "agenda_"):
        if result.startswith(prefix):
            result = result[len(prefix):]
            break
    return result.replace("_", " ").strip().title()


def _event(
    *,
    current: PoliticsSnapshot,
    event_type: str,
    category: str,
    title: str,
    body: str,
    subject_id: int | None = None,
    subject_name: str | None = None,
    visible: bool = True,
    confidence: str = "high",
    date_kind: str = "first_observed",
    attributes: dict[str, object] | None = None,
) -> dict:
    subject_key = str(subject_id) if subject_id is not None else (subject_name or "state")
    clean_attributes = {
        str(key): str(value)
        for key, value in (attributes or {}).items()
        if value is not None
    }
    identity = "|".join(
        f"{key}={clean_attributes[key]}"
        for key in sorted(clean_attributes)
    )
    discriminator = (
        hashlib.sha1(identity.encode("utf-8", errors="replace")).hexdigest()[:12]
        if identity
        else "base"
    )
    return {
        "event_key": (
            f"politics:{event_type}:{subject_key}:{current.game_date}:"
            f"{current.snapshot_id}:{discriminator}"
        ),
        "snapshot_id": current.snapshot_id,
        "game_date": current.game_date,
        "category": category,
        "event_type": event_type,
        "subject_id": subject_id,
        "subject_name": subject_name,
        "title": title,
        "body": body,
        "visible": int(visible),
        "confidence": confidence,
        "date_kind": date_kind,
        "attributes": clean_attributes,
    }


def _relation_field_class(key: str) -> str | None:
    low = key.casefold()
    if "communicat" in low:
        return "communications"
    if "hostil" in low:
        return "hostility"
    if "neutral" in low:
        return "neutral"
    if low == "value" or low == "relation_value" or (
        low.endswith("_value") and ("relation" in low or "opinion" in low)
    ):
        return "relation_value"
    return None


_NON_DIPLOMATIC_NAME_TOKENS = (
    "gateway_system",
    "incoming asteroid",
    "mining drone",
    "mineral extraction operation",
    "cracked crystalline shard",
    "space amoeba",
    "spaceborne organics",
    "voidwyrm",
    "leviathan",
    "locust swarm",
)


def _publishable_diplomatic_actor(relation: DiplomaticRelationState) -> bool:
    """Return whether a raw relations_manager counterpart belongs in public diplomacy history.

    Stellaris uses country-like records for event objects, wildlife and transient
    systems as well as actual diplomatic actors.  v0.0.48 keeps every raw relation
    in structured state/diagnostics, but only publishes counterparts that do not
    match the strongest pseudo-country indicators observed in campaign evidence.
    """
    name = (relation.country_name or "").strip()
    folded = name.casefold()

    if not name:
        return False
    if relation.country_id >= 10_000_000:
        return False
    if re.fullmatch(r"country\s+\d+", folded):
        return False
    return not any(token in folded for token in _NON_DIPLOMATIC_NAME_TOKENS)


def _relation_changes(
    before: DiplomaticRelationState,
    after: DiplomaticRelationState,
    *,
    current: PoliticsSnapshot,
) -> list[dict]:
    events: list[dict] = []
    prev_scalars = before.scalar_map
    cur_scalars = after.scalar_map
    actor_visible = _publishable_diplomatic_actor(after)

    for key in sorted(set(prev_scalars) | set(cur_scalars)):
        old = prev_scalars.get(key)
        new = cur_scalars.get(key)
        if old == new:
            continue

        field_class = _relation_field_class(key)
        if field_class is None:
            continue

        if field_class == "communications":
            event_type = "communications_state_changed"
            title = f"Communications State Changed: {after.country_name}"
            visible = True
            importance_note = "communications"
        elif field_class == "hostility":
            event_type = "hostility_state_changed"
            title = f"Hostility State Changed: {after.country_name}"
            visible = True
            importance_note = "hostility"
        elif field_class == "neutral":
            event_type = "neutral_state_changed"
            title = f"Neutral-State Evidence Changed: {after.country_name}"
            visible = True
            importance_note = "neutral-state"
        else:
            event_type = "relation_value_changed"
            title = f"Relation Value Changed: {after.country_name}"
            visible = False
            importance_note = "relation-value"

        events.append(_event(
            current=current,
            event_type=event_type,
            category="diplomacy",
            title=title,
            body=(
                f"By {current.game_date}, the retained relation record for "
                f"{after.country_name} changed raw field `{key}` from "
                f"{old if old is not None else '<absent>'} to "
                f"{new if new is not None else '<absent>'}. "
                "This records the saved-state transition without inferring an unrecorded cause."
            ),
            subject_id=after.country_id,
            subject_name=after.country_name,
            visible=(visible and actor_visible),
            attributes={
                "raw_field": key,
                "before": old if old is not None else "<absent>",
                "after": new if new is not None else "<absent>",
                "evidence_class": importance_note,
                "actor_publication": "public" if actor_visible else "diagnostic_only",
            },
        ))

    prev_blocks = set(before.blocks)
    cur_blocks = set(after.blocks)
    for key in sorted(prev_blocks ^ cur_blocks):
        field_class = _relation_field_class(key)
        if field_class not in {"communications", "hostility", "neutral"}:
            continue
        appeared = key in cur_blocks
        events.append(_event(
            current=current,
            event_type=f"{field_class}_block_changed",
            category="diplomacy",
            title=f"{field_class.replace('_', ' ').title()} Evidence Changed: {after.country_name}",
            body=(
                f"By {current.game_date}, raw relation block `{key}` for "
                f"{after.country_name} {'appeared' if appeared else 'disappeared'} in the retained save state. "
                "No additional diplomatic meaning is inferred beyond that saved-state change."
            ),
            subject_id=after.country_id,
            subject_name=after.country_name,
            visible=actor_visible,
            attributes={
                "raw_block": key,
                "state": "present" if appeared else "absent",
                "actor_publication": "public" if actor_visible else "diagnostic_only",
            },
        ))

    return events


def politics_transition_data(
    previous: PoliticsSnapshot | None,
    current: PoliticsSnapshot,
    *,
    baseline: bool,
) -> dict:
    events: list[dict] = []

    if baseline or previous is None:
        if current.ruler_id is not None:
            events.append(_event(
                current=current,
                event_type="ruler_identity_observed",
                category="politics",
                title=f"Opening Ruler Recorded: {current.ruler_name or current.ruler_id}",
                body=(
                    f"The opening archived political state records "
                    f"{current.ruler_name or f'leader {current.ruler_id}'} as ruler."
                ),
                subject_id=current.ruler_id,
                subject_name=current.ruler_name,
                visible=False,
                date_kind="archive_opening",
            ))

        for tradition in current.traditions:
            events.append(_event(
                current=current,
                event_type="tradition_first_observed",
                category="politics",
                title=f"Tradition Present at Opening: {_humanise(tradition)}",
                body=(
                    f"Tradition key `{tradition}` is already present in the opening archived "
                    "player-country tradition structure. Its adoption date is not established."
                ),
                date_kind="archive_opening",
                attributes={"tradition_key": tradition},
            ))

        for country_id, relation in sorted(current.relations.items()):
            events.append(_event(
                current=current,
                event_type="diplomatic_contact_first_observed",
                category="diplomacy",
                title=f"Diplomatic Contact Record Present at Opening: {relation.country_name}",
                body=(
                    f"A player relations_manager record for {relation.country_name} is present in "
                    "the opening archived state. This establishes only that the relation record "
                    "already existed when the surviving archive begins."
                ),
                subject_id=country_id,
                subject_name=relation.country_name,
                visible=_publishable_diplomatic_actor(relation),
                date_kind="archive_opening",
                attributes={
                    "country_id": country_id,
                    "actor_publication": (
                        "public" if _publishable_diplomatic_actor(relation)
                        else "diagnostic_only"
                    ),
                },
            ))

        return {
            "state": snapshot_to_dict(current),
            "events": events,
        }

    government_changes: list[str] = []
    if previous.government_type != current.government_type:
        government_changes.append(
            f"government {_humanise(previous.government_type)} -> {_humanise(current.government_type)}"
        )
    if previous.authority != current.authority:
        government_changes.append(
            f"authority {_humanise(previous.authority)} -> {_humanise(current.authority)}"
        )
    if previous.ethics != current.ethics:
        government_changes.append(
            "ethics " + ", ".join(_humanise(value) for value in previous.ethics)
            + " -> " + ", ".join(_humanise(value) for value in current.ethics)
        )
    if previous.civics != current.civics:
        government_changes.append(
            "civics " + ", ".join(_humanise(value) for value in previous.civics)
            + " -> " + ", ".join(_humanise(value) for value in current.civics)
        )

    if government_changes:
        events.append(_event(
            current=current,
            event_type="government_state_changed",
            category="politics",
            title="Government State Changed",
            body=(
                f"By {current.game_date}, the archived government profile changed: "
                + "; ".join(government_changes)
                + "."
            ),
            attributes={"changes": " | ".join(government_changes)},
        ))

    if (
        previous.ruler_id != current.ruler_id
        or previous.ruler_name != current.ruler_name
    ):
        events.append(_event(
            current=current,
            event_type="ruler_identity_changed",
            category="politics",
            title="Ruler Identity Changed",
            body=(
                f"By {current.game_date}, the Politics/Diplomacy snapshot records ruler identity changing from "
                f"{previous.ruler_name or previous.ruler_id or 'unresolved'} to "
                f"{current.ruler_name or current.ruler_id or 'unresolved'}. "
                "The People domain remains authoritative for the corresponding ruler career milestone."
            ),
            subject_id=current.ruler_id,
            subject_name=current.ruler_name,
            visible=False,
            attributes={
                "previous_ruler_id": previous.ruler_id,
                "previous_ruler_name": previous.ruler_name,
                "current_ruler_id": current.ruler_id,
                "current_ruler_name": current.ruler_name,
            },
        ))

    previous_agendas = dict(previous.agenda_fields)
    current_agendas = dict(current.agenda_fields)
    for key in sorted(set(previous_agendas) | set(current_agendas)):
        old = previous_agendas.get(key)
        new = current_agendas.get(key)
        if old == new:
            continue

        low_key = key.casefold()
        progress_only = "progress" in low_key
        agenda_identity = low_key == "council_agenda"

        if agenda_identity:
            title = (
                "Council Agenda Changed: "
                f"{_humanise(old)} -> {_humanise(new)}"
            )
            body = (
                f"By {current.game_date}, the retained council agenda changed from "
                f"{_humanise(old)} to {_humanise(new)}. "
                f"Raw values: `{old if old is not None else '<absent>'}` -> "
                f"`{new if new is not None else '<absent>'}`. "
                "No unrecorded completion reason or political cause is inferred."
            )
            event_type = "council_agenda_state_changed"
        elif progress_only:
            title = "Council Agenda Progress Changed"
            body = (
                f"By {current.game_date}, retained agenda progress field `{key}` changed from "
                f"{old if old is not None else '<absent>'} to "
                f"{new if new is not None else '<absent>'}. "
                "This telemetry is retained for diagnostics but is not public historical narrative."
            )
            event_type = "council_agenda_progress_changed"
        else:
            title = "Council Agenda State Changed"
            body = (
                f"By {current.game_date}, retained agenda field `{key}` changed from "
                f"{old if old is not None else '<absent>'} to "
                f"{new if new is not None else '<absent>'}. "
                "The transition is recorded literally without assigning an unrecorded cause or completion state."
            )
            event_type = "council_agenda_state_changed"

        events.append(_event(
            current=current,
            event_type=event_type,
            category="politics",
            title=title,
            body=body,
            visible=not progress_only,
            attributes={
                "raw_field": key,
                "before": old if old is not None else "<absent>",
                "after": new if new is not None else "<absent>",
                "publication": "diagnostic_only" if progress_only else "public",
            },
        ))

    previous_traditions = set(previous.traditions)
    current_traditions = set(current.traditions)
    for tradition in sorted(current_traditions - previous_traditions):
        events.append(_event(
            current=current,
            event_type="tradition_first_observed",
            category="politics",
            title=f"Tradition First Observed: {_humanise(tradition)}",
            body=(
                f"Tradition key `{tradition}` first appears in the retained player-country tradition structure by "
                f"{current.game_date}. This is a first archived observation, not an exact adoption timestamp."
            ),
            attributes={"tradition_key": tradition},
        ))

    previous_relations = previous.relations
    current_relations = current.relations

    for country_id in sorted(set(current_relations) - set(previous_relations)):
        relation = current_relations[country_id]
        events.append(_event(
            current=current,
            event_type="diplomatic_contact_first_observed",
            category="diplomacy",
            title=f"Diplomatic Contact Record First Observed: {relation.country_name}",
            body=(
                f"A player relations_manager record for {relation.country_name} first appears in archived evidence by "
                f"{current.game_date}. This establishes first archived appearance of the relation record, not the exact date or cause of contact."
            ),
            subject_id=country_id,
            subject_name=relation.country_name,
            visible=_publishable_diplomatic_actor(relation),
            attributes={
                "country_id": country_id,
                "actor_publication": (
                    "public" if _publishable_diplomatic_actor(relation)
                    else "diagnostic_only"
                ),
            },
        ))

    for country_id in sorted(set(previous_relations) & set(current_relations)):
        events.extend(_relation_changes(
            previous_relations[country_id],
            current_relations[country_id],
            current=current,
        ))

    return {
        "state": snapshot_to_dict(current),
        "events": events,
    }


def derive_full_politics_history(snapshots: list[PoliticsSnapshot]) -> dict:
    states: list[dict] = []
    events: list[dict] = []
    previous: PoliticsSnapshot | None = None

    for index, current in enumerate(snapshots):
        delta = politics_transition_data(
            previous,
            current,
            baseline=(index == 0),
        )
        states.append({
            "snapshot_id": current.snapshot_id,
            "game_date": current.game_date,
            "state": delta["state"],
        })
        events.extend(delta["events"])
        previous = current

    return {"states": states, "events": events}


def write_politics_history_diagnostic(
    archive_dir: Path,
    history: dict,
) -> Path:
    path = Path(archive_dir) / "Politics_History_Debug.txt"
    states = history.get("states", [])
    events = history.get("events", [])

    lines = [
        "STELLARIS HISTORIAN - STRUCTURED POLITICS / DIPLOMACY HISTORY",
        "",
        "v0.0.48 structured evidence domain.",
        "Government, ruler, agenda, tradition and relation state is retained literally. Events use first-observed / saved-state transitions and do not invent elections, treaties, motives or causes.",
        "",
        f"Structured states: {len(states)}",
        f"Structured events: {len(events)}",
        f"Published events: {sum(int(event.get('visible', 0)) for event in events)}",
        f"Diagnostic-only events: {sum(not int(event.get('visible', 0)) for event in events)}",
        "",
        "EVENTS",
        "======",
    ]

    if not events:
        lines.append("No Politics/Diplomacy transitions observed.")
    else:
        for event in events:
            lines.extend([
                f"{event['game_date']} | {event['category'].upper()} | {event['event_type']} | {event['title']}",
                f"  Visible: {event.get('visible', 0)}",
                f"  Confidence: {event.get('confidence', 'high')}",
                f"  Date kind: {event.get('date_kind', 'first_observed')}",
                f"  Body: {event['body']}",
            ])
            attributes = event.get("attributes") or {}
            for key, value in sorted(attributes.items()):
                lines.append(f"  {key}: {value}")
            lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def write_politics_database_diagnostic(
    db: Database,
    campaign_id: int,
) -> Path:
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist.")

    states: list[dict] = []
    for row in db.politics_states(campaign_id):
        try:
            state = json.loads(row["state_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            state = {}
        states.append({
            "snapshot_id": int(row["snapshot_id"]),
            "game_date": str(row["game_date"]),
            "state": state if isinstance(state, dict) else {},
        })

    events: list[dict] = []
    for row in db.politics_events(campaign_id, visible_only=False):
        item = dict(row)
        try:
            attributes = json.loads(item.get("attributes_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            attributes = {}
        item["attributes"] = attributes if isinstance(attributes, dict) else {}
        events.append(item)

    diagnostics = Path(campaign["archive_dir"]) / "diagnostics"
    diagnostics.mkdir(parents=True, exist_ok=True)
    return write_politics_history_diagnostic(
        diagnostics,
        {"states": states, "events": events},
    )
