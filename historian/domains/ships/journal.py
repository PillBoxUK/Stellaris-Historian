from __future__ import annotations

from html import escape

from ...db import Database


def _e(value) -> str:
    return escape("" if value is None else str(value))


def _fleet_class_name(raw: str | None) -> str:
    mapping = {
        "shipclass_military": "Military Fleet",
        "shipclass_science_ship": "Science Vessel",
        "shipclass_constructor": "Construction Vessel",
        "shipclass_colonizer": "Colony Vessel",
        "shipclass_transport": "Transport Fleet",
    }
    if raw in mapping:
        return mapping[raw]
    value = (raw or "Fleet").replace("shipclass_", "").replace("_", " ").strip()
    return value.title() or "Fleet"


def _build_evidence_name(raw: str | None) -> str:
    mapping = {
        "direct_shipyard_queue": "Direct shipyard queue",
        "first_observed_fleet_home_base": "First-observed fleet home base",
        "unique_player_shipyard": "Only identifiable player shipyard",
    }
    return mapping.get(raw, raw.replace("_", " ").title() if raw else "")


def _ship_event_evidence(row) -> str:
    date_text = (
        f"<span><strong>Date:</strong> "
        f"{_e(row['date_kind'].replace('_', ' ').title())}"
        f" - {_e(row['confidence'].title())} confidence</span>"
    )
    build_text = ""
    if (
        row["event_type"] in {"ship_commissioned", "ship_first_observed"}
        and row["build_location"]
        and row["build_location_evidence"]
        and row["build_location_confidence"]
    ):
        build_text = (
            f"<span><strong>Build site:</strong> "
            f"{_e(_build_evidence_name(row['build_location_evidence']))}"
            f" - {_e(row['build_location_confidence'].title())} confidence"
            f"</span>"
        )
    parts = [date_text]
    if build_text:
        parts.append(build_text)
    return "<br>".join(parts)


def render_ships_section(db: Database, campaign_id: int) -> str:
    ship_registry = db.ship_registry(campaign_id)
    fleet_registry = db.fleet_registry(campaign_id)
    ship_fleet_events = db.ship_fleet_events(campaign_id, visible_only=True)

    baseline_ships = [row for row in ship_registry if row["baseline_present"]]
    baseline_fleets = [row for row in fleet_registry if row["baseline_present"]]

    fleet_rows_html = "".join(
        f"""
        <tr>
          <td>{_e(row['opening_name'] or 'Name not established')}</td>
          <td>{_e(_fleet_class_name(row['opening_ship_class']))}</td>
          <td>{_e(row['opening_ship_count'] if row['opening_ship_count'] is not None else 'Not recorded')}</td>
          <td>{_e(row['opening_home_base'] or 'Not recorded')}</td>
          <td>{_e(row['opening_commander_name'] or 'None recorded')}</td>
        </tr>
        """
        for row in baseline_fleets
    )

    ship_rows_html = "".join(
        f"""
        <tr>
          <td>{_e(row['opening_name'] or 'Name not established')}</td>
          <td>{_e(row['opening_ship_type'] or 'Not recorded')}</td>
          <td>{_e(row['opening_fleet_name'] or 'Unassigned')}</td>
          <td>{_e(row['opening_commander_name'] or 'None recorded')}</td>
          <td>{_e(row['opening_construction_date'] or row['construction_date'] or 'Not recorded')}</td>
          <td>{_e(row['build_location'] or 'Not established')}</td>
        </tr>
        """
        for row in baseline_ships
    )

    ship_event_html = "".join(
        f"""
        <article class="chronicle-event">
          <div class="date">{_e(row['game_date'])}</div>
          <h3>{_e(row['title'])}</h3>
          <p>{_e(row['body'])}</p>
          <div class="evidence evidence-stack">
            {_ship_event_evidence(row)}
          </div>
        </article>
        """
        for row in ship_fleet_events
    )

    if not (baseline_ships or baseline_fleets or ship_fleet_events):
        return ""

    fleet_table = ""
    if baseline_fleets:
        fleet_table = f"""
            <h3>Fleet Register at the Opening of the Record</h3>
            <p class="note">
              These fleets were present in the first archived state. Every field
              in this register is frozen to opening-state evidence; later
              commanders, home bases, renames or fleet composition changes are
              never projected backwards. Historian does not treat presence at
              the opening date as proof that a fleet was created on that date.
            </p>

            <table>
              <thead>
                <tr>
                  <th>Fleet</th>
                  <th>Class</th>
                  <th>Ships</th>
                  <th>Home base</th>
                  <th>Commander</th>
                </tr>
              </thead>
              <tbody>
                {fleet_rows_html}
              </tbody>
            </table>
            """

    ship_table = ""
    if baseline_ships:
        ship_table = f"""
            <h3>Ships Present at the Opening of the Record</h3>
            <p class="note">
              Names, types, fleet assignments and commanders in this register
              come only from the first archived state. Later relationships are
              never projected backwards. Recorded vessel dates are preserved
              where Stellaris provides them; living/event vessels can carry
              age- or origin-like values. Build locations are shown only where
              Historian has supporting archive evidence.
            </p>

            <table>
              <thead>
                <tr>
                  <th>Ship</th>
                  <th>Type</th>
                  <th>Fleet</th>
                  <th>Commander</th>
                  <th>Recorded construction date</th>
                  <th>Build location</th>
                </tr>
              </thead>
              <tbody>
                {ship_rows_html}
              </tbody>
            </table>
            """

    event_section = ""
    if ship_fleet_events:
        event_section = f"""
            <h3>Ship and Fleet Chronicle</h3>
            <p class="note">
              Refit evidence is collected for every stable vessel whose
              recorded ship design changes between adjacent archived states.
              The published chronicle is deliberately selective: broad naval
              modernisation waves, substantial same-fleet refits, support-fleet
              refit waves and isolated major-warship refits may appear here,
              while routine single-vessel design churn remains preserved
              internally. Historian does not yet claim which weapons, armour or
              other components changed.
            </p>
            <div class="chronicle-events">
              {ship_event_html}
            </div>
            """

    return f"""
        <section>
          <h2>Ships and Fleets</h2>
          {fleet_table}
          {ship_table}
          {event_section}
        </section>
        """
