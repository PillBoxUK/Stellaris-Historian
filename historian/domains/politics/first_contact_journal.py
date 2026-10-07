from __future__ import annotations

from html import escape

from ...db import Database
from .first_contact_history import load_first_contact_history


def _e(value) -> str:
    return escape("" if value is None else str(value))


def _evidence_label(event: dict) -> str:
    date_kind = str(event.get("date_kind") or "first_observed")
    labels = {
        "retained_first_contact_record_date": "Retained First Contact record date",
        "between_snapshots": "Completed between archived states",
        "exact_save_field": "Exact retained save field",
        "first_observed": "First observed in archive",
    }
    return labels.get(date_kind, date_kind.replace("_", " ").title())


def render_first_contact_section(db: Database, campaign_id: int) -> str:
    history = load_first_contact_history(db, campaign_id)
    cases = history.get("cases") or []
    events = history.get("events") or []
    if not cases and not events:
        return ""

    visible = [event for event in events if event.get("visible")]
    completed = sum(bool(case.get("completion_confirmed")) for case in cases)
    active = sum(case.get("assignment_end_interval") is None for case in cases)
    named = sorted({
        str(case.get("counterpart_country_name"))
        for case in cases
        if case.get("publishable_counterpart") and case.get("counterpart_country_name")
    })

    event_html = "".join(
        f"""
        <article class="chronicle-event politics-event">
          <div class="date">{_e(event.get('game_date'))}</div>
          <h3>{_e(event.get('title'))}</h3>
          <p>{_e(event.get('body'))}</p>
          <div class="evidence evidence-stack">
            <span><strong>Date:</strong> {_e(_evidence_label(event))} - {_e(str(event.get('confidence') or 'high').title())} confidence</span>
            <span><strong>Contact case:</strong> {_e(event.get('contact_id'))}</span>
          </div>
        </article>
        """
        for event in visible
    )

    named_text = ", ".join(named) if named else "No publishable counterpart names resolved yet"

    return f"""
        <section>
          <h2>First Contact</h2>
          <p class="note">
            This v0.0.50.4 section decodes retained <code>first_contacts.contacts</code>
            records by matching them to leader <code>first_contact_system</code>
            assignment ids. Counterpart identity is published only when the raw
            contact record supplies a country id whose generated or later diplomatic
            identity resolves to a real actor after Stellaris adjective grammar is applied and technical script labels are rejected. Completion checks both player-side and reciprocal
            counterpart-side retained completion markers across the same archived interval. Response
            choices remain unpublished unless a direct retained selection field is proven.
          </p>

          <div class="facts">
            <div><span>Decoded cases</span><strong>{len(cases)}</strong></div>
            <div><span>Confirmed completions</span><strong>{completed}</strong></div>
            <div><span>Active investigations</span><strong>{active}</strong></div>
            <div><span>Published events</span><strong>{len(visible)}</strong></div>
            <div><span>Resolved counterparts</span><strong>{_e(named_text)}</strong></div>
          </div>

          {
            ('<h3>First Contact Chronicle</h3>'
             f'<div class="chronicle-events">{event_html}</div>')
            if event_html
            else '<p class="note">Structured First Contact cases were decoded, but none yet met the publication rules.</p>'
          }
        </section>
    """
