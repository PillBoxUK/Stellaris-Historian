from __future__ import annotations

from html import escape
import json

from ...db import Database


def _e(value) -> str:
    return escape("" if value is None else str(value))


def _event_evidence(row) -> str:
    date_kind = row["date_kind"]
    label_map = {
        "exact_save_field": "Recorded recruitment date",
        "first_observed": "First observed in archive",
        "between_snapshots": "Between archived states",
    }
    date_label = label_map.get(
        date_kind,
        date_kind.replace("_", " ").title(),
    )
    return (
        f"<span><strong>Date:</strong> {_e(date_label)}"
        f" - {_e(row['confidence'].title())} confidence</span>"
    )


def _leader_class_name(raw: str | None) -> str:
    mapping = {
        "official": "Official",
        "scientist": "Scientist",
        "commander": "Commander",
        "envoy": "Envoy",
        "governor": "Governor",
        "admiral": "Admiral",
        "general": "General",
    }
    if raw in mapping:
        return mapping[raw]
    return (raw or "Leader").replace("_", " ").title()


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed if item] if isinstance(parsed, list) else []


def _leader_role(row) -> str:
    if row["latest_is_ruler"]:
        return "Ruler"
    if row["latest_is_heir"]:
        return "Heir"
    if row["ever_ruler"]:
        return "Former Ruler"
    if row["ever_heir"]:
        return "Former Heir"
    if row["latest_council_role"]:
        return row["latest_council_role"]
    return _leader_class_name(row["leader_class"])


def _leader_status(row) -> str:
    if row["status"] == "present":
        return "Present in latest archive"
    return "No longer present - cause unconfirmed"


def render_people_section(db: Database, campaign_id: int) -> str:
    leader_registry = db.leader_registry(campaign_id)

    if not leader_registry:
        return ""

    leader_career_events = db.leader_career_events(
        campaign_id,
        visible_only=False,
    )
    visible_leader_career_events = db.leader_career_events(
        campaign_id,
        visible_only=True,
    )

    leader_register_rows = "".join(
        f"""
        <tr>
          <td>{_e(row['name'])}</td>
          <td>{_e(_leader_role(row))}</td>
          <td>{_e(_leader_class_name(row['leader_class']))}</td>
          <td>{'Yes' if row['baseline_present'] else 'No'}</td>
          <td>{_e(row['recruitment_date'] or 'Not recorded')}</td>
          <td>{_e(row['first_seen_date'])}</td>
          <td>{_e(row['last_seen_date'])}</td>
          <td>{_e(row['latest_level'] if row['latest_level'] is not None else 'Not recorded')}</td>
          <td>{_e(row['latest_assignment'] or 'Unassigned / not recorded')}</td>
          <td>{_e(row['latest_council_role'] or 'None recorded')}</td>
          <td>{_e(', '.join(_json_list(row['trait_names'])) or 'None recorded')}</td>
          <td>{_e(_leader_status(row))}</td>
        </tr>
        """
        for row in leader_registry
    )

    leader_event_html = "".join(
        f"""
        <article class="chronicle-event people-event">
          <div class="date">{_e(row['game_date'])}</div>
          <h3>{_e(row['title'])}</h3>
          <p>{_e(row['body'])}</p>
          <div class="evidence evidence-stack">
            {_event_evidence(row)}
          </div>
        </article>
        """
        for row in visible_leader_career_events
    )

    return f"""
        <section>
          <h2>People and Political History</h2>

          <h3>Leader Career Register</h3>
          <p class="note">
            Historian tracks stable leader identity, class, level, recorded
            recruitment date, assignments, council service, ruler/heir status,
            traits, first observation and last confirmed appearance. "Present at
            opening" means only that the leader existed in the first archived
            state; latest/last-known fields may describe a later point in that
            leader's career. A leader who disappears is not automatically recorded
            as dead. The archive currently contains {len(leader_career_events)}
            structured career change record(s). Historian publishes
            {len(visible_leader_career_events)} historically meaningful career
            event(s) below; routine level progression and other low-value
            bookkeeping remain preserved internally.
          </p>

          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Latest / last role</th>
                  <th>Class</th>
                  <th>Present at opening</th>
                  <th>Recorded recruitment</th>
                  <th>First observed</th>
                  <th>Last confirmed</th>
                  <th>Latest level</th>
                  <th>Latest assignment</th>
                  <th>Council role</th>
                  <th>Latest traits</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {leader_register_rows}
              </tbody>
            </table>
          </div>

          {
            f"""
            <h3>Career Chronicle</h3>
            <p class="note">
              This published chronicle is selective. Recruitment, appointments,
              assignments, council changes, ruler/heir changes, newly observed
              traits and unexplained departures can appear here. Routine level
              changes remain in Historian's structured record but are not
              published as separate narrative events.
            </p>
            <div class="chronicle-events">
              {leader_event_html}
            </div>
            """
            if leader_event_html
            else ""
          }
        </section>
        """
