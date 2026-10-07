from __future__ import annotations

from html import escape
from pathlib import Path
import os
import tempfile

from .db import Database
from .domains.people.journal import render_people_section
from .domains.ships.journal import render_ships_section
from .domains.science.journal import render_science_section
from .localisation import resolve_origin_lore
from .save_reader import read_empire_profile
from .domains.worlds.journal import format_population_units


def journal_path(
    db: Database,
    campaign_id: int,
) -> Path:
    campaign = db.campaign(
        campaign_id
    )

    if campaign is None:
        raise ValueError(
            "Campaign does not exist."
        )

    return (
        Path(campaign["archive_dir"])
        / "Historical_Journal.html"
    )


def _e(value) -> str:
    return escape(
        ""
        if value is None
        else str(value)
    )


def _paragraphs(
    text: str,
) -> str:
    parts = [
        part.strip()
        for part in text.split("\n")
        if part.strip()
    ]

    return "".join(
        f"<p>{_e(part)}</p>"
        for part in parts
    )










def _world_event_evidence(row) -> str:
    date_kind = row["date_kind"]

    label_map = {
        "exact_save_field": "Exact save field",
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


def _world_status(row) -> str:
    if row["status"] == "present":
        return "Present in latest archive"

    return "No longer recorded as owned"


def _world_foundation_text(row) -> str:
    if row["baseline_present"]:
        return "Present at opening"

    return row["colonize_date"] or "Date not established"


def _founding_origin_lore(
    db: Database,
    campaign_id: int,
) -> dict | None:
    campaign = db.campaign(
        campaign_id
    )

    snapshots = db.all_snapshots(
        campaign_id
    )

    if campaign is None or not snapshots:
        return None

    start_snapshot = None

    for snapshot in snapshots:
        if snapshot["kind"] == "start":
            start_snapshot = snapshot
            break

    if start_snapshot is None:
        start_snapshot = snapshots[0]

    archive_path = Path(
        start_snapshot["archive_path"]
    )

    try:
        profile = read_empire_profile(
            archive_path
        )
    except Exception:
        return None

    # The founding profile comes from the preserved archive, but localisation
    # discovery must use the ORIGINAL Stellaris save path so Historian can walk
    # upward to the Steam folder and find vanilla/DLC/Workshop localisation.
    source_save = Path(
        campaign["source_save"]
    )

    return resolve_origin_lore(
        source_save,
        profile.origin,
    )


def render_journal(
    db: Database,
    campaign_id: int,
) -> Path:
    campaign = db.campaign(
        campaign_id
    )

    if campaign is None:
        raise ValueError(
            "Campaign does not exist."
        )

    entries = db.history_entries(
        campaign_id
    )

    processed_count = db.processed_count(
        campaign_id
    )

    target = journal_path(
        db,
        campaign_id,
    )

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    world_registry = db.world_registry(
        campaign_id
    )

    world_events = db.world_history_events(
        campaign_id,
        visible_only=False,
    )

    visible_world_events = db.world_history_events(
        campaign_id,
        visible_only=True,
    )


    founding = [
        entry
        for entry in entries
        if entry["entry_type"] == "founding"
    ]

    checkpoints = [
        entry
        for entry in entries
        if entry["entry_type"] == "checkpoint"
    ]

    origin_lore = _founding_origin_lore(
        db,
        campaign_id,
    )

    founding_html = ""

    for entry in founding:
        facts = []

        if entry["government_type"]:
            facts.append(
                f"<div><span>Government</span><strong>{_e(entry['government_type'])}</strong></div>"
            )

        if entry["authority"]:
            facts.append(
                f"<div><span>Authority</span><strong>{_e(entry['authority'])}</strong></div>"
            )

        if entry["origin"]:
            facts.append(
                f"<div><span>Origin</span><strong>{_e(entry['origin'])}</strong></div>"
            )

        if entry["ethics"]:
            facts.append(
                f"<div><span>Ethics</span><strong>{_e(entry['ethics'])}</strong></div>"
            )

        if entry["civics"]:
            facts.append(
                f"<div><span>Civics</span><strong>{_e(entry['civics'])}</strong></div>"
            )

        lore_html = ""

        if origin_lore:
            lore_title = (
                origin_lore.get("title")
                or entry["origin"]
                or "Origin"
            )

            lore_html = f"""
            <section class="origin-lore">
              <div class="origin-kicker">
                Origin Chronicle
              </div>

              <h3>
                {_e(lore_title)}
              </h3>

              <div class="origin-story">
                {_paragraphs(origin_lore['description'])}
              </div>

              <div class="origin-source">
                Canonical origin lore resolved from the locally installed
                Stellaris or mod localisation files.
              </div>
            </section>
            """

        founding_html += f"""
        <article class="founding">
          <div class="date">
            {_e(entry['game_date'])}
          </div>

          <h2>
            {_e(entry['title'])}
          </h2>

          <p>
            {_e(entry['body'])}
          </p>

          <div class="facts">
            {''.join(facts)}
          </div>

          {lore_html}
        </article>
        """

    people_html = render_people_section(
        db,
        campaign_id,
    )

    world_register_rows = "".join(
        f"""
        <tr>
          <td>{_e(row['name'])}</td>
          <td>{_e('Yes' if row['latest_is_capital'] else ('Former capital' if row['ever_capital'] else 'No'))}</td>
          <td>{_e(row['system_name'] or 'Not resolved')}</td>
          <td>{_e(row['planet_class_name'] or 'Not resolved')}</td>
          <td>{_e(_world_foundation_text(row))}</td>
          <td>{_e(row['first_seen_date'])}</td>
          <td>{_e((format_population_units(row['latest_population']) + ' pops') if row['latest_population'] is not None else 'Not recorded')}</td>
          <td>{_e(row['latest_designation_name'] or 'Not recorded')}</td>
          <td>{_e(row['latest_governor_name'] or 'None recorded')}</td>
          <td>{_e(row['latest_ascension_tier'] if row['latest_ascension_tier'] is not None else 'Not recorded')}</td>
          <td>{_e(_world_status(row))}</td>
        </tr>
        """
        for row in world_registry
    )

    world_event_html = "".join(
        f"""
        <article class="chronicle-event world-event">
          <div class="date">{_e(row['game_date'])}</div>
          <h3>{_e(row['title'])}</h3>
          <p>{_e(row['body'])}</p>
          <div class="evidence evidence-stack">
            {_world_event_evidence(row)}
          </div>
        </article>
        """
        for row in visible_world_events
    )

    worlds_html = ""

    if world_registry:
        worlds_html = f"""
        <section id="worlds-expansion" class="journal-anchor">
          <h2>Worlds and Expansion</h2>

          <h3>Colonial World Register</h3>
          <p class="note">
            Historian tracks stable planet identity, colony founding evidence,
            system, planet class, population, designation, governor, capital
            status and ownership over time. Population, buildings and districts
            are being collected in the snapshot cache now; this first Worlds
            stage publishes only the strongest expansion events so routine
            development does not overwhelm the journal. The archive currently
            contains {len(world_events)} structured world change record(s), with
            {len(visible_world_events)} selected for publication below.
          </p>

          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>World</th>
                  <th>Capital</th>
                  <th>System</th>
                  <th>Class</th>
                  <th>Founded / known</th>
                  <th>First observed</th>
                  <th>Latest population</th>
                  <th>Designation</th>
                  <th>Governor</th>
                  <th>Ascension tier</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {world_register_rows}
              </tbody>
            </table>
          </div>

          {
            f"""
            <h3>Colonial Chronicle</h3>
            <p class="note">
              Founding dates are treated as exact only when Stellaris retains a
              usable colonization date that fits the surviving chronology.
              Acquisitions, losses, renames and capital changes use the first
              archived state that proves the new condition when an exact day is
              unavailable.
            </p>
            <div class="chronicle-events">
              {world_event_html}
            </div>
            """
            if world_event_html
            else ""
          }
        </section>
        """

    science_html = render_science_section(
        db,
        campaign_id,
    )

    ship_fleet_html = render_ships_section(
        db,
        campaign_id,
    )

    checkpoint_rows = "".join(
        f"""
        <tr>
          <td>{_e(entry['game_date'])}</td>
          <td>{_e(entry['archive_filename'])}</td>
          <td>{
            'Processed'
            if entry['snapshot_processed']
            else 'Waiting for history'
          }</td>
        </tr>
        """
        for entry in checkpoints
    )

    nav_links = [
        '<a href="#opening-record">Opening Record</a>',
    ]

    if worlds_html:
        nav_links.append(
            '<a href="#worlds-expansion">Worlds &amp; Expansion</a>'
        )

    if people_html.strip():
        nav_links.append(
            '<a href="#people-history">People &amp; Politics</a>'
        )

    if science_html.strip():
        nav_links.append(
            '<a href="#science-exploration">Science &amp; Exploration</a>'
        )

    if ship_fleet_html.strip():
        nav_links.append(
            '<a href="#ships-fleets">Ships &amp; Fleets</a>'
        )

    nav_links.append(
        '<a href="#archive-checkpoints">Archive</a>'
    )

    navigation_html = "".join(nav_links)

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(campaign['empire_name'])} - Historical Journal</title>

<style>
:root{{
  --ink:#30261b;
  --muted:#786954;
  --paper:#f4ecd9;
  --paper2:#eadcc1;
  --line:#b89d72;
  --gold:#96703a;
  --dark:#1a140f;
  --journal-width:min(92vw,3000px);
  --reading-width:1600px;
  --nav-height:54px;
}}

*{{
  box-sizing:border-box;
}}

html{{
  scroll-behavior:smooth;
}}

body{{
  margin:0;
  background:#d7c9ad;
  color:var(--ink);
  font-family:Georgia,"Times New Roman",serif;
}}

header{{
  padding:42px 24px 36px;
  color:#f7ecd8;
  background:linear-gradient(180deg,#17120e,#2a1e14);
  border-bottom:5px solid var(--gold);
}}

.journal-nav{{
  position:sticky;
  top:0;
  z-index:50;
  min-height:var(--nav-height);
  background:rgba(26,20,15,.97);
  border-bottom:1px solid #604b32;
  box-shadow:0 4px 14px rgba(0,0,0,.18);
  backdrop-filter:blur(8px);
}}

.journal-nav-inner{{
  width:var(--journal-width);
  min-height:var(--nav-height);
  margin:auto;
  display:flex;
  align-items:center;
  gap:18px;
  padding:7px clamp(18px,2vw,40px);
}}

.journal-nav .brand{{
  flex:0 0 auto;
  color:#e3c68d;
  font:700 11px Arial,sans-serif;
  text-transform:uppercase;
  letter-spacing:.12em;
  text-decoration:none;
}}

.journal-nav-links{{
  display:flex;
  align-items:center;
  gap:5px;
  min-width:0;
  overflow-x:auto;
  scrollbar-width:thin;
  white-space:nowrap;
}}

.journal-nav-links a,
.journal-nav .scribes-button,
.journal-nav .timeline-button,
.journal-nav button{{
  flex:0 0 auto;
  border:1px solid transparent;
  border-radius:5px;
  padding:8px 10px;
  color:#f1e4cd;
  background:transparent;
  font:600 12px Arial,sans-serif;
  text-decoration:none;
  cursor:pointer;
}}

.journal-nav-links a:hover,
.journal-nav-links a:focus-visible,
.journal-nav .scribes-button:hover,
.journal-nav .scribes-button:focus-visible,
.journal-nav .timeline-button:hover,
.journal-nav .timeline-button:focus-visible,
.journal-nav button:hover,
.journal-nav button:focus-visible{{
  border-color:#80623b;
  background:#34271c;
  outline:none;
}}

.journal-nav .timeline-button{{
  margin-left:auto;
  border-color:#52718a;
  background:#1d3040;
  color:#dcecf7;
  font-weight:700;
}}

.journal-nav .scribes-button{{
  margin-left:0;
  border-color:#b38a4f;
  background:#4a3421;
  color:#ffe8bd;
  font-weight:700;
}}

.journal-nav button{{
  margin-left:0;
  border-color:#80623b;
  background:#34271c;
}}

.journal-anchor{{
  scroll-margin-top:calc(var(--nav-height) + 14px);
}}

.back-to-top{{
  position:fixed;
  right:22px;
  bottom:22px;
  z-index:45;
  padding:9px 12px;
  border:1px solid #80623b;
  border-radius:6px;
  color:#f1e4cd;
  background:rgba(26,20,15,.92);
  box-shadow:0 4px 12px rgba(0,0,0,.18);
  font:700 12px Arial,sans-serif;
  text-decoration:none;
}}

.back-to-top:hover,
.back-to-top:focus-visible{{
  background:#34271c;
  outline:none;
}}

.wrap{{
  width:var(--journal-width);
  max-width:none;
  margin:auto;
}}

.kicker{{
  font:700 11px Arial,sans-serif;
  letter-spacing:.2em;
  color:#d8bc84;
  text-transform:uppercase;
}}

h1{{
  margin:9px 0 8px;
  font-size:clamp(38px,7vw,70px);
  line-height:.98;
  font-weight:500;
}}

.sub{{
  color:#dacbb5;
  font-size:17px;
}}

main{{
  width:var(--journal-width);
  max-width:none;
  min-height:100vh;
  margin:auto;
  padding:34px clamp(24px,2vw,56px) 70px;
  background:var(--paper);
}}

.summary{{
  display:grid;
  grid-template-columns:repeat(3,1fr);
  gap:12px;
  margin-bottom:32px;
}}

.stat{{
  padding:15px;
  background:var(--paper2);
  border-top:4px solid var(--gold);
}}

.stat span{{
  display:block;
  color:var(--muted);
  font:11px Arial,sans-serif;
  text-transform:uppercase;
  letter-spacing:.08em;
}}

.stat strong{{
  display:block;
  margin-top:6px;
  font-size:20px;
}}

.founding{{
  position:relative;
  max-width:1800px;
  margin-left:auto;
  margin-right:auto;
  padding:27px;
  border:1px solid #c9b18a;
  background:linear-gradient(135deg,#faf2e2,#ead8b8);
}}

.founding .date{{
  font:700 12px Arial,sans-serif;
  color:#75552f;
}}

.founding h2{{
  margin:7px 0 10px;
  font-size:29px;
  font-weight:500;
}}

.founding > p{{
  margin:0;
  font-size:18px;
  line-height:1.7;
}}

.facts{{
  display:grid;
  grid-template-columns:repeat(2,1fr);
  gap:10px;
  margin-top:22px;
}}

.facts div{{
  padding:12px;
  background:rgba(255,255,255,.35);
  border:1px solid #d6c09c;
}}

.facts span{{
  display:block;
  color:var(--muted);
  font:10px Arial,sans-serif;
  text-transform:uppercase;
  letter-spacing:.08em;
}}

.facts strong{{
  display:block;
  margin-top:4px;
}}

.origin-lore{{
  margin-top:25px;
  padding:20px 22px;
  border-left:5px solid var(--gold);
  background:rgba(112,85,53,.08);
}}

.origin-kicker{{
  color:#75552f;
  font:700 10px Arial,sans-serif;
  text-transform:uppercase;
  letter-spacing:.12em;
}}

.origin-lore h3{{
  margin:5px 0 10px;
  font-size:25px;
  font-weight:500;
}}

.origin-story p{{
  margin:0 0 10px;
  font-size:17px;
  line-height:1.65;
}}

.origin-story p:last-child{{
  margin-bottom:0;
}}

.origin-source{{
  margin-top:13px;
  color:var(--muted);
  font:11px Arial,sans-serif;
}}


section h3{{
  margin:26px 0 10px;
  color:#50391f;
  font-size:21px;
  font-weight:500;
}}

.chronicle-events{{
  display:grid;
  width:100%;
  max-width:var(--reading-width);
  gap:12px;
  margin:12px auto 0;
}}

.chronicle-event{{
  padding:16px 18px;
  background:#f9f1e2;
  border-left:4px solid var(--gold);
  border-top:1px solid #d6c3a2;
  border-right:1px solid #d6c3a2;
  border-bottom:1px solid #d6c3a2;
}}

.chronicle-event .date{{
  color:#75552f;
  font:700 11px Arial,sans-serif;
}}

.chronicle-event h3{{
  margin:4px 0 7px;
  font-size:20px;
}}

.chronicle-event p{{
  margin:0;
  line-height:1.55;
}}

.evidence{{
  margin-top:8px;
  color:var(--muted);
  font:10px Arial,sans-serif;
  text-transform:uppercase;
  letter-spacing:.06em;
}}

.evidence-stack span{{
  display:block;
  margin-top:2px;
}}

.people-event{{
  border-left-color:#705535;
}}

.world-event{{
  border-left-color:#6f7f4f;
}}

.science-event{{
  border-left-color:#486d78;
}}

.story-arc{{
  background:linear-gradient(135deg,#f9f1e2,#e8e3d3);
}}

.science-event p + p{{
  margin-top:8px;
}}

section h2{{
  margin:38px 0 14px;
  padding-bottom:7px;
  border-bottom:2px solid #705535;
  font-size:27px;
  font-weight:500;
}}

table{{
  width:100%;
  border-collapse:collapse;
  background:#f9f1e2;
}}

.table-scroll{{
  width:100%;
  overflow-x:auto;
  scrollbar-gutter:stable;
}}

th,
td{{
  padding:10px 12px;
  border-bottom:1px solid #d6c3a2;
  text-align:left;
  vertical-align:top;
}}

th{{
  background:#e8d9bc;
  font:700 11px Arial,sans-serif;
  text-transform:uppercase;
  letter-spacing:.07em;
}}

.note{{
  max-width:var(--reading-width);
  margin-left:auto;
  margin-right:auto;
  color:var(--muted);
  line-height:1.6;
}}

@media(min-width:1800px){{
  th,
  td{{
    padding:12px 14px;
  }}
}}

@media(max-width:1100px){{
  :root{{
    --journal-width:100%;
  }}

  main{{
    padding-left:20px;
    padding-right:20px;
  }}
}}

@media(max-width:700px){{
  .summary,
  .facts{{
    grid-template-columns:1fr;
  }}

  .journal-nav-inner{{
    gap:8px;
    padding-left:10px;
    padding-right:10px;
  }}

  .journal-nav .brand{{
    display:none;
  }}

  .journal-nav button{{
    padding-left:8px;
    padding-right:8px;
  }}

  .back-to-top{{
    right:12px;
    bottom:12px;
  }}

  main{{
    padding-left:14px;
    padding-right:14px;
  }}
}}

@page{{
  size:A4 landscape;
  margin:10mm;
}}

@media print{{
  html,
  body{{
    width:auto !important;
    min-width:0 !important;
    background:#fff !important;
  }}

  body{{
    font-size:9pt;
    -webkit-print-color-adjust:exact;
    print-color-adjust:exact;
  }}

  header{{
    padding:7mm 0 5mm;
    color:var(--ink);
    background:#fff;
    border-bottom:2pt solid var(--gold);
  }}

  .wrap,
  main{{
    width:100% !important;
    max-width:none !important;
    margin:0 !important;
  }}

  .journal-nav,
  .back-to-top{{
    display:none !important;
  }}

  h1{{
    margin:2mm 0 1mm;
    font-size:28pt;
    line-height:1;
  }}

  .kicker{{
    font-size:8pt;
  }}

  .sub{{
    color:var(--muted);
    font-size:10pt;
  }}

  main{{
    min-height:0;
    padding:6mm 0 0;
    background:#fff;
  }}

  .summary{{
    gap:3mm;
    margin-bottom:6mm;
  }}

  .stat{{
    padding:3mm;
  }}

  .stat span{{
    font-size:7pt;
  }}

  .stat strong{{
    margin-top:1mm;
    font-size:12pt;
  }}

  .founding{{
    max-width:none;
    padding:5mm;
  }}

  .founding h2{{
    font-size:18pt;
  }}

  .founding > p,
  .origin-story p{{
    font-size:10pt;
    line-height:1.45;
  }}

  .origin-lore{{
    margin-top:5mm;
    padding:4mm;
  }}

  .origin-lore h3{{
    font-size:15pt;
  }}

  .facts{{
    gap:2mm;
    margin-top:4mm;
  }}

  .facts div{{
    padding:2.5mm;
  }}

  .journal-anchor:not(#opening-record){{
    break-before:page;
    page-break-before:always;
  }}

  section h2{{
    margin:0 0 4mm;
    padding-bottom:2mm;
    font-size:18pt;
    break-after:avoid-page;
    page-break-after:avoid;
  }}

  section h3{{
    margin:5mm 0 2mm;
    font-size:13pt;
    break-after:avoid-page;
    page-break-after:avoid;
  }}

  .chronicle-events,
  .note,
  .founding{{
    width:100%;
    max-width:none;
  }}

  .note{{
    font-size:9pt;
    line-height:1.4;
  }}

  .chronicle-events{{
    display:block;
    margin-top:3mm;
  }}

  .chronicle-event{{
    margin:0 0 3mm;
    padding:3mm 4mm;
    break-inside:avoid-page;
    page-break-inside:avoid;
  }}

  .chronicle-event h3{{
    margin:1mm 0 1.5mm;
    font-size:12pt;
  }}

  .chronicle-event p{{
    font-size:9pt;
    line-height:1.35;
  }}

  .evidence{{
    margin-top:1.5mm;
    font-size:7pt;
  }}

  .table-scroll{{
    width:100% !important;
    max-width:100% !important;
    overflow:visible !important;
  }}

  table{{
    width:100% !important;
    max-width:100% !important;
    table-layout:auto;
    font-size:7.2pt;
  }}

  thead{{
    display:table-header-group;
  }}

  tr{{
    break-inside:avoid-page;
    page-break-inside:avoid;
  }}

  th,
  td{{
    padding:1.8mm 1.5mm;
    overflow-wrap:anywhere;
  }}

  th{{
    font-size:6.4pt;
    letter-spacing:.035em;
  }}

  .founding,
  .origin-lore{{
    break-inside:avoid-page;
    page-break-inside:avoid;
  }}
}}
</style>
</head>

<body id="top">
<header>
  <div class="wrap">
    <div class="kicker">
      Stellaris Historian
    </div>

    <h1>
      {_e(campaign['empire_name'])}
    </h1>

    <div class="sub">
      Historical record from {_e(campaign['first_game_date'])}
      to {_e(campaign['latest_game_date'])}
    </div>
  </div>
</header>

<nav class="journal-nav" aria-label="Journal sections">
  <div class="journal-nav-inner">
    <a class="brand" href="#top">Historian</a>

    <div class="journal-nav-links">
      {navigation_html}
    </div>

    <a class="timeline-button" href="/timeline" title="Read the important events as a simple chronological timeline">
      Empire Timeline
    </a>

    <a class="scribes-button" href="/scribes" title="Read the campaign as a flowing historical chronicle">
      As the Scribes Saw It
    </a>

    <button type="button" onclick="window.print()" title="Open the browser print dialog for a paginated PDF">
      Print / PDF
    </button>
  </div>
</nav>

<main>
  <section class="summary">
    <div class="stat">
      <span>First observed</span>
      <strong>{_e(campaign['first_game_date'])}</strong>
    </div>

    <div class="stat">
      <span>Latest archived date</span>
      <strong>{_e(campaign['latest_game_date'])}</strong>
    </div>

    <div class="stat">
      <span>Processed saves</span>
      <strong>{processed_count}</strong>
    </div>
  </section>

  <div id="opening-record" class="journal-anchor">
    {
      founding_html
      if founding_html
      else '<p class="note">The founding snapshot has not yet been processed.</p>'
    }
  </div>

  {worlds_html}

  {
    f'<div id="people-history" class="journal-anchor">{people_html}</div>'
    if people_html.strip()
    else ''
  }

  {
    f'<div id="science-exploration" class="journal-anchor">{science_html}</div>'
    if science_html.strip()
    else ''
  }

  {
    f'<div id="ships-fleets" class="journal-anchor">{ship_fleet_html}</div>'
    if ship_fleet_html.strip()
    else ''
  }

  <section id="archive-checkpoints" class="journal-anchor">
    <h2>
      Archive Checkpoints
    </h2>

    <p class="note">
      These are the archived campaign states currently available to Historian.
      Review Campaign can inspect a save before Update History marks it as
      processed, so the status shown here reflects the database processing flag.
    </p>

    <table>
      <thead>
        <tr>
          <th>Game date</th>
          <th>Archived save</th>
          <th>Status</th>
        </tr>
      </thead>

      <tbody>
        {
          checkpoint_rows
          if checkpoint_rows
          else '<tr><td colspan="3">No later checkpoints processed yet.</td></tr>'
        }
      </tbody>
    </table>
  </section>
</main>

<a class="back-to-top" href="#top" aria-label="Back to top">Top</a>
</body>
</html>
"""

    fd, temp_name = tempfile.mkstemp(
        prefix="historian_journal_",
        suffix=".html",
        dir=str(target.parent),
    )

    try:
        with os.fdopen(
            fd,
            "w",
            encoding="utf-8",
            newline="\n",
        ) as handle:
            handle.write(
                html
            )

        os.replace(
            temp_name,
            target,
        )

    finally:
        if os.path.exists(
            temp_name
        ):
            os.unlink(
                temp_name
            )

    return target
