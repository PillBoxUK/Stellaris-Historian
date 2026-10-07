from __future__ import annotations

from html import escape
from pathlib import Path
import json

from ...db import Database
from ...localisation import resolve_localisation_key


def _e(value) -> str:
    return escape("" if value is None else str(value))


def _fallback_humanise(value: str | None) -> str:
    if not value:
        return "Not retained"
    result = str(value)
    for prefix in ("gov_", "auth_", "ethic_", "civic_", "tr_", "agenda_"):
        if result.startswith(prefix):
            result = result[len(prefix):]
            break
    return result.replace("_", " ").strip().title()


def _display_key(source_save: Path | None, value: str | None) -> str:
    if not value:
        return "Not retained"
    if source_save is not None:
        resolved = resolve_localisation_key(source_save, str(value))
        if resolved:
            return resolved
    return _fallback_humanise(str(value))


def _event_evidence(row) -> str:
    date_kind = str(row["date_kind"] or "first_observed")
    labels = {
        "archive_opening": "Present in opening archive",
        "first_observed": "First observed / changed in archive",
        "between_snapshots": "Between archived states",
    }
    label = labels.get(date_kind, date_kind.replace("_", " ").title())
    return (
        f"<span><strong>Date:</strong> {_e(label)}"
        f" - {_e(str(row['confidence'] or 'high').title())} confidence</span>"
    )


def _latest_state(db: Database, campaign_id: int) -> dict:
    rows = db.politics_states(campaign_id)
    if not rows:
        return {}
    try:
        value = json.loads(rows[-1]["state_json"] or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _list_text(values, source_save: Path | None = None) -> str:
    if not isinstance(values, list):
        return "None retained"
    cleaned = [
        _display_key(source_save, str(value))
        for value in values
        if value not in (None, "")
    ]
    return ", ".join(cleaned) if cleaned else "None retained"


def render_politics_section(db: Database, campaign_id: int) -> str:
    states = db.politics_states(campaign_id)
    if not states:
        return ""

    campaign = db.campaign(campaign_id)
    source_save = (
        Path(campaign["source_save"])
        if campaign is not None and campaign["source_save"]
        else None
    )

    events = db.politics_events(campaign_id, visible_only=False)
    visible_events = db.politics_events(campaign_id, visible_only=True)
    latest = _latest_state(db, campaign_id)

    ruler = latest.get("ruler_name") or (
        f"Leader {latest.get('ruler_id')}"
        if latest.get("ruler_id") is not None
        else "Not resolved"
    )
    agendas = latest.get("agenda_fields") or []
    agenda_parts: list[str] = []
    for item in agendas:
        if not (isinstance(item, list) and len(item) == 2):
            continue
        key, value = str(item[0]), str(item[1])
        if "progress" in key.casefold():
            continue
        label = (
            "Council Agenda"
            if key.casefold() == "council_agenda"
            else _fallback_humanise(key)
        )
        agenda_parts.append(f"{label}: {_display_key(source_save, value)}")
    agenda_text = ", ".join(agenda_parts) or "None retained"
    relations = latest.get("relations") or {}
    relation_count = len(relations) if isinstance(relations, dict) else 0

    event_html = "".join(
        f"""
        <article class="chronicle-event politics-event">
          <div class="date">{_e(row['game_date'])}</div>
          <h3>{_e(row['title'])}</h3>
          <p>{_e(row['body'])}</p>
          <div class="evidence evidence-stack">
            {_event_evidence(row)}
          </div>
        </article>
        """
        for row in visible_events
    )

    return f"""
        <section>
          <h2>Politics &amp; Diplomacy</h2>
          <p class="note">
            This v0.0.48 section is evidence-first. It records retained government,
            ruler, agenda, tradition and diplomatic relation-state evidence without
            inventing elections, treaties, motives, alliances, rivalries or causes.
            The People domain remains authoritative for public ruler career events.
            Historian currently retains {len(events)} structured Politics/Diplomacy
            event(s), of which {len(visible_events)} are published below.
          </p>

          <div class="facts">
            <div><span>Government</span><strong>{_e(_display_key(source_save, latest.get('government_type')))}</strong></div>
            <div><span>Authority</span><strong>{_e(_display_key(source_save, latest.get('authority')))}</strong></div>
            <div><span>Ruler</span><strong>{_e(ruler)}</strong></div>
            <div><span>Ethics</span><strong>{_e(_list_text(latest.get('ethics'), source_save))}</strong></div>
            <div><span>Civics</span><strong>{_e(_list_text(latest.get('civics'), source_save))}</strong></div>
            <div><span>Traditions</span><strong>{_e(_list_text(latest.get('traditions'), source_save))}</strong></div>
            <div><span>Agenda evidence</span><strong>{_e(agenda_text)}</strong></div>
            <div><span>Raw relation records</span><strong>{relation_count}</strong></div>
          </div>

          {
            f'''<h3>Political &amp; Diplomatic Chronicle</h3>
            <div class="chronicle-events">{event_html}</div>'''
            if event_html
            else '<p class="note">No publishable Politics/Diplomacy transitions have been observed yet.</p>'
          }
        </section>
    """
