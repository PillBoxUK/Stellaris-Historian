from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from html import escape
from pathlib import Path
import os
import re
import tempfile

from .db import Database
from .historical_events import HistoricalEvent
from .presentation_history import build_presentation_history


_RED_GIANT_PROJECT_KEYS = {
    "INF_ORIGIN_RED_GIANT_TRIANGULATION",
    "INF_ORIGIN_RED_GIANT_PROTECT_HOMEWORLD",
    "INF_ORIGIN_RED_GIANT_PARLAY",
    "INF_ORIGIN_RED_GIANT_BOARD_STATION",
}

_TECH_MILESTONE_TERMS = (
    "fusion power",
    "cold fusion",
    "antimatter power",
    "laser",
    "torpedo",
    "missile",
    "disruptor",
    "plasma",
    "shield",
    "armor",
    "armour",
    "destroyer",
    "cruiser",
    "battleship",
    "cloaking",
    "hyperlane",
    "dyson",
    "arc furnace",
    "terraform",
    "administrative ai",
    "archaeostudies",
    "stellar expansion",
    "colonial centralization",
    "fleet traditions",
    "fleet support",
    "interstellar warfare",
    "interstellar logistics",
    "combat computers",
    "orbital maneuvers",
    "starbase",
)


@dataclass(frozen=True)
class TimelineEvent:
    game_date: str
    title: str
    body: str
    category: str
    importance: int = 50
    leader_id: int | None = None


def timeline_path(db: Database, campaign_id: int) -> Path:
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist.")
    return Path(campaign["archive_dir"]) / "Empire_Timeline.html"


def _e(value) -> str:
    return escape("" if value is None else str(value))


def _date_key(value: str | None) -> tuple[int, int, int]:
    try:
        year, month, day = str(value).split(".")[:3]
        return int(year), int(month), int(day)
    except (ValueError, AttributeError):
        return (999999, 99, 99)


def _year(value: str | None) -> str:
    if not value:
        return "Unknown"
    return str(value).split(".", 1)[0]


def _short_date(value: str | None) -> str:
    if not value:
        return "Date uncertain"
    bits = str(value).split(".")
    if len(bits) != 3:
        return str(value)
    _year_value, month, day = bits
    try:
        month_i = int(month)
        day_i = int(day)
    except ValueError:
        return str(value)
    months = (
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    )
    if 1 <= month_i <= 12:
        return f"{day_i:02d} {months[month_i - 1]}"
    return str(value)


def _attrs(event: HistoricalEvent) -> dict[str, str]:
    return {key: value for key, value in event.attributes}


def _csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _int(value: str | None) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _plural(value: int, singular: str, plural: str | None = None) -> str:
    return singular if value == 1 else (plural or singular + "s")


def _join_words(values: list[str]) -> str:
    values = [value for value in values if value]
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return ", ".join(values[:-1]) + f", and {values[-1]}"


def _clean_public_text(value: str | None) -> str:
    """Keep polished chronology free of game/debug voice."""
    text = " ".join(str(value or "").split())
    text = re.sub(r"\bStellaris records\b", "The surviving record identifies", text, flags=re.I)
    text = re.sub(r"\bplayer fleets?\b", "recorded fleets", text, flags=re.I)
    text = re.sub(r"\bplayer loss(?:es)?\b", "recorded losses", text, flags=re.I)
    text = text.replace("planet Station", "an unresolved station")
    return text


def _leader_id(event: HistoricalEvent) -> int | None:
    return _int(_attrs(event).get("leader_id"))


def _leader_is_notable(event: HistoricalEvent, leaders: dict[int, object]) -> bool:
    event_type = event.event_type
    if event_type in {
        "leader_became_ruler",
        "leader_left_rulership",
        "leader_death_recorded",
        "leader_missing_unconfirmed",
    }:
        return True
    leader_id = _leader_id(event)
    leader = leaders.get(leader_id) if leader_id is not None else None
    if event_type == "leader_entered_service":
        if leader is None:
            return event.importance >= 74
        return bool(leader["ever_ruler"]) or str(leader["leader_class"]) in {"commander", "scientist"}
    if event_type == "leader_assignment_changed":
        return "Took Command" in event.title and "Unnamed" not in event.title and "Unnamed" not in event.summary
    return False


def _combat_timeline_event(event: HistoricalEvent, empire_name: str) -> TimelineEvent:
    attrs = _attrs(event)
    systems = _csv(attrs.get("systems"))
    enemies = _csv(attrs.get("opposing_countries"))
    fleets = _csv(attrs.get("player_fleets"))
    commanders = _csv(attrs.get("commanders"))
    end_date = attrs.get("end_date") or event.game_date
    direct = attrs.get("evidence_kind") == "direct_anchored"

    if systems:
        title = f"The Fighting at {_join_words(systems)}" if direct else f"Fighting at {_join_words(systems)}"
    elif enemies:
        title = f"Combat with {_join_words(enemies)}"
    else:
        title = "Combat episode preserved"

    parts: list[str] = []
    if end_date != event.game_date:
        parts.append(f"The surviving combat record spans {event.game_date} to {end_date}.")
    if fleets:
        parts.append(f"Recorded formations: {_join_words(fleets)}.")
    if enemies:
        parts.append(f"Opposing force: {_join_words(enemies)}.")
    if commanders:
        parts.append(f"Command: {_join_words(commanders)}.")

    initial_side = _int(attrs.get("initial_player_losses"))
    initial_opp = _int(attrs.get("initial_opposing_losses"))
    latest_side = _int(attrs.get("latest_player_losses"))
    latest_opp = _int(attrs.get("latest_opposing_losses"))
    evolved = attrs.get("telemetry_evolved") == "true"
    initial_observed = attrs.get("initial_observed_date")
    latest_observed = attrs.get("latest_observed_date")

    force_name = "Convocation" if "convocation" in empire_name.casefold() else empire_name
    if direct and initial_side is not None and initial_opp is not None:
        if evolved and latest_side is not None and latest_opp is not None:
            parts.append(
                f"The earliest complete retained tally{f' by {initial_observed}' if initial_observed else ''} recorded "
                f"{initial_side} {force_name} {_plural(initial_side, 'vessel')} lost and "
                f"{initial_opp} opposing {_plural(initial_opp, 'vessel')} lost. "
                f"Later retained fleet records{f' by {latest_observed}' if latest_observed else ''} raised the known tally to "
                f"{latest_side} {force_name} {_plural(latest_side, 'vessel')} lost and "
                f"{latest_opp} opposing {_plural(latest_opp, 'vessel')} lost; these are evolving observations of the same retained combat state, not separate casualty totals."
            )
        elif initial_side or initial_opp:
            parts.append(
                f"Retained battle tallies record {initial_side} {force_name} {_plural(initial_side, 'vessel')} lost and "
                f"{initial_opp} opposing {_plural(initial_opp, 'vessel')} lost."
            )
        else:
            parts.append("The surviving retained fleet tallies record no vessel losses for either side.")

    outcome = attrs.get("formal_outcome")
    if outcome == "victory":
        parts.append(f"A surviving formal battle record establishes a {force_name} victory.")
    elif outcome == "defeat":
        parts.append(f"A surviving formal battle record establishes a {force_name} defeat.")
    else:
        parts.append("No surviving record establishes victory or defeat.")

    return TimelineEvent(
        game_date=event.game_date,
        title=title,
        body=" ".join(parts),
        category="Combat",
        importance=event.importance,
    )


def _technology_timeline_events(events: list[HistoricalEvent]) -> list[TimelineEvent]:
    grouped: dict[str, list[HistoricalEvent]] = defaultdict(list)
    for event in events:
        if event.category != "technology":
            continue
        title_low = event.title.casefold()
        if not any(term in title_low for term in _TECH_MILESTONE_TERMS):
            continue
        grouped[event.game_date].append(event)

    result: list[TimelineEvent] = []
    for game_date, rows in grouped.items():
        names = list(dict.fromkeys(row.title for row in rows))
        result.append(TimelineEvent(
            game_date=game_date,
            title="Technology milestone" if len(names) == 1 else "Technology milestones",
            body=f"The learned register first records {_join_words(names)} by this preserved date.",
            category="Technology",
            importance=max(row.importance for row in rows),
        ))
    return result


def _collect_events(db: Database, campaign_id: int) -> tuple[list[TimelineEvent], dict[int, object]]:
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist.")

    presentation = build_presentation_history(db, campaign_id)
    historical = list(presentation.events)
    leaders = {int(row["leader_id"]): row for row in db.leader_registry(campaign_id)}
    events: list[TimelineEvent] = []

    for event in historical:
        if event.category == "technology":
            continue  # grouped below into milestone rows

        if event.event_type == "record_opening":
            events.append(TimelineEvent(
                event.game_date,
                "The surviving historical record opens",
                _clean_public_text(event.summary),
                "Empire",
                event.importance,
            ))
            continue

        if event.category == "expansion" and event.importance >= 85:
            events.append(TimelineEvent(
                event.game_date,
                event.title,
                _clean_public_text(event.summary),
                "Expansion",
                event.importance,
            ))
            continue

        if event.category == "people" and _leader_is_notable(event, leaders):
            events.append(TimelineEvent(
                event.game_date,
                event.title,
                _clean_public_text(event.summary),
                "People",
                event.importance,
                _leader_id(event),
            ))
            continue

        if event.category == "military":
            include = False
            category = "Military"
            if event.event_type == "fleet_first_observed":
                include = "Unnamed" not in event.title
            elif event.event_type == "ship_commissioned":
                include = event.title.startswith(("Science Ship ", "Construction Ship ", "Colony Ship "))
                if include:
                    category = "Exploration"
            if include:
                events.append(TimelineEvent(
                    event.game_date,
                    event.title,
                    _clean_public_text(event.summary),
                    category,
                    event.importance,
                ))
            continue

        if event.category == "science":
            attrs = _attrs(event)
            project_key = attrs.get("project_key")
            situation_key = attrs.get("situation_key")
            include = (
                event.event_type == "archaeology_site_observed"
                or project_key in _RED_GIANT_PROJECT_KEYS
                or situation_key in {"situation_red_giant_expansion", "situation_pre_ftl_nwo", "situation_pre_ftl_singularity"}
            )
            if include:
                if event.event_type == "archaeology_site_observed":
                    location = attrs.get("location")
                    body = f"{event.title} first enters the archaeological record{f' at {location}' if location else ''}."
                    category = "Exploration"
                elif event.event_type == "special_project_observed":
                    body = f"The research project {event.title} first enters the surviving scientific record."
                    category = "Science"
                else:
                    body = _clean_public_text(event.summary)
                    category = "Science"
                events.append(TimelineEvent(
                    event.game_date,
                    event.title,
                    body,
                    category,
                    event.importance,
                ))
            continue

        if event.category == "combat" and event.event_type == "combat_episode":
            attrs = _attrs(event)
            direct = attrs.get("evidence_kind") == "direct_anchored"
            meaningful = bool(attrs.get("systems") or attrs.get("opposing_countries") or attrs.get("player_fleets"))
            if direct or (event.confidence == "high" and event.importance >= 88 and meaningful):
                events.append(_combat_timeline_event(event, str(campaign["empire_name"])))

    events.extend(_technology_timeline_events(historical))

    # Give the active campaign a clear present edge without pretending it ended.
    latest_date = str(campaign["latest_game_date"] or "")
    if latest_date:
        present_worlds = sum(1 for row in db.world_registry(campaign_id) if str(row["status"] or "") == "present")
        present_ships = sum(1 for row in db.ship_registry(campaign_id) if str(row["status"] or "") == "present")
        present_leaders = sum(1 for row in db.leader_registry(campaign_id) if str(row["status"] or "") == "present")
        events.append(TimelineEvent(
            latest_date,
            "The surviving record reaches its present edge",
            (
                f"The latest surviving roll records {present_worlds} inhabited {_plural(present_worlds, 'world')}, "
                f"{present_ships} mobile {_plural(present_ships, 'ship')}, and "
                f"{present_leaders} named {_plural(present_leaders, 'leader')} still present. "
                "The chronicle remains open."
            ),
            "Empire",
            100,
        ))

    # De-duplicate presentation rows. If two domain sources describe the same
    # title on the same day, keep the higher-importance version.
    deduped: dict[tuple[str, str], TimelineEvent] = {}
    for event in events:
        key = (event.game_date, event.title)
        old = deduped.get(key)
        if old is None or event.importance > old.importance:
            deduped[key] = event

    return sorted(
        deduped.values(),
        key=lambda event: (_date_key(event.game_date), -event.importance, event.category, event.title),
    ), leaders


def _people_of_note(events: list[TimelineEvent], leaders: dict[int, object]) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    seen: set[int] = set()
    for event in events:
        if event.leader_id is None or event.leader_id in seen:
            continue
        leader = leaders.get(event.leader_id)
        if leader is None:
            continue
        seen.add(event.leader_id)
        role = str(leader["leader_class"] or "leader").title()
        assignment = str(leader["latest_assignment"] or "").replace("Fleet: ", "")
        if leader["ever_ruler"]:
            role = "Ruler"
        elif assignment and "Unnamed" not in assignment:
            role = f"{role} - {assignment}"
        result.append((str(leader["name"]), role))
    return result[:4]


def render_timeline(db: Database, campaign_id: int) -> Path:
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist.")

    events, leaders = _collect_events(db, campaign_id)
    by_year: dict[str, list[TimelineEvent]] = defaultdict(list)
    for event in events:
        by_year[_year(event.game_date)].append(event)

    year_blocks: list[str] = []
    for year in sorted(by_year, key=lambda value: int(value) if value.isdigit() else 999999):
        year_events = by_year[year]
        event_html = "".join(
            f"""
            <article class="event" data-category="{_e(event.category)}">
              <div class="date">{_e(_short_date(event.game_date))}</div>
              <div class="event-main">
                <div class="event-top"><span class="tag">{_e(event.category)}</span><h3>{_e(event.title)}</h3></div>
                <p>{_e(event.body)}</p>
              </div>
            </article>
            """
            for event in year_events
        )

        people = _people_of_note(year_events, leaders)
        people_html = ""
        if people:
            people_html = """
              <aside class="people-note">
                <div class="people-heading">People of Note</div>
                <div class="people-list">%s</div>
              </aside>
            """ % "".join(
                f'<div><strong>{_e(name)}</strong><span>{_e(role)}</span></div>'
                for name, role in people
            )

        year_blocks.append(
            f"""
            <section class="year" id="year-{_e(year)}">
              <div class="year-heading"><span>{_e(year)}</span></div>
              <div class="events">{event_html}</div>
              {people_html}
            </section>
            """
        )

    target = timeline_path(db, campaign_id)
    target.parent.mkdir(parents=True, exist_ok=True)

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(campaign['empire_name'])} - Empire Timeline</title>
<style>
:root{{
  --bg:#0e141b;--panel:#131d27;--panel2:#182532;--line:#314657;
  --text:#e7edf2;--muted:#91a5b5;--accent:#d7b06a;--width:1040px;
}}
*{{box-sizing:border-box}}
html{{scroll-behavior:smooth}}
body{{margin:0;background:linear-gradient(180deg,#0a0f14,#101821 440px);color:var(--text);font-family:Inter,Segoe UI,Arial,sans-serif}}
.topbar{{position:sticky;top:0;z-index:30;display:flex;gap:8px;align-items:center;padding:9px max(14px,calc((100vw - var(--width))/2));background:rgba(8,12,16,.96);border-bottom:1px solid #293a48}}
.topbar a,.topbar button{{border:1px solid #354a5b;border-radius:6px;background:#14202a;color:#dfe8ef;text-decoration:none;padding:8px 11px;font:600 12px Segoe UI,Arial,sans-serif;cursor:pointer}}
.topbar a:hover,.topbar button:hover{{background:#1d2c38}}
.topbar .primary{{border-color:#856838;background:#302617;color:#ffe5ae}}
.topbar .spacer{{flex:1}}
.hero{{max-width:var(--width);margin:0 auto;padding:54px 22px 38px}}
.kicker{{font-size:11px;font-weight:800;letter-spacing:.18em;text-transform:uppercase;color:var(--accent)}}
h1{{font-family:Georgia,'Times New Roman',serif;font-weight:500;font-size:clamp(42px,7vw,72px);line-height:1;margin:9px 0 12px}}
.hero p{{color:var(--muted);font-size:17px;line-height:1.6;max-width:800px;margin:0}}
.filters{{max-width:var(--width);margin:0 auto 16px;padding:0 22px;display:flex;flex-wrap:wrap;gap:7px}}
.filters button{{border:1px solid #344a5b;border-radius:999px;background:#121d26;color:#cbd7df;padding:7px 11px;cursor:pointer;font-weight:600}}
.filters button.active{{background:#d7b06a;color:#15110b;border-color:#d7b06a}}
.timeline{{width:min(calc(100% - 24px),var(--width));margin:0 auto 90px}}
.year{{margin:0 0 54px;scroll-margin-top:64px}}
.year-heading{{display:flex;align-items:center;gap:18px;margin:0 0 12px}}
.year-heading::before,.year-heading::after{{content:'';height:1px;background:linear-gradient(90deg,transparent,var(--line));flex:1}}
.year-heading::after{{background:linear-gradient(90deg,var(--line),transparent)}}
.year-heading span{{font-family:Georgia,'Times New Roman',serif;font-size:34px;color:#f1d6a4;letter-spacing:.04em}}
.events{{border-left:2px solid #2d4557;margin-left:72px;padding-left:22px}}
.event{{position:relative;display:grid;grid-template-columns:86px 1fr;gap:18px;padding:10px 0 18px}}
.event::before{{content:'';position:absolute;left:-29px;top:17px;width:10px;height:10px;border:2px solid #d7b06a;border-radius:50%;background:#0f1720}}
.date{{color:#d7b06a;font-weight:800;font-size:13px;padding-top:4px;white-space:nowrap}}
.event-main{{background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid #293d4d;border-radius:8px;padding:14px 16px}}
.event-top{{display:flex;gap:9px;align-items:flex-start;flex-wrap:wrap}}
.event h3{{font-family:Georgia,'Times New Roman',serif;font-size:18px;line-height:1.3;margin:0;font-weight:600}}
.event p{{margin:7px 0 0;color:#aebdca;font-size:14px;line-height:1.58}}
.tag{{font-size:10px;line-height:1;border:1px solid #50687a;border-radius:999px;padding:5px 7px;color:#adc0ce;text-transform:uppercase;letter-spacing:.08em}}
.people-note{{margin:13px 0 0 94px;border:1px solid #4d4330;background:#1c1a16;border-radius:8px;padding:13px 15px}}
.people-heading{{font-size:10px;font-weight:800;letter-spacing:.15em;color:#d7b06a;text-transform:uppercase;margin-bottom:8px}}
.people-list{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px 14px}}
.people-list div{{display:flex;flex-direction:column;gap:2px}}
.people-list strong{{font-family:Georgia,'Times New Roman',serif;font-size:16px;color:#f1dfbd}}
.people-list span{{font-size:12px;color:#9eaaaf}}
.empty{{max-width:var(--width);margin:0 auto;padding:30px 22px;color:var(--muted)}}
@media(max-width:700px){{.topbar{{flex-wrap:wrap}}.events{{margin-left:20px;padding-left:18px}}.event{{grid-template-columns:1fr;gap:5px}}.event::before{{left:-25px}}.people-note{{margin-left:38px}}}}
@media print{{@page{{size:A4 portrait;margin:16mm}}.topbar,.filters{{display:none!important}}body{{background:white;color:#222}}.hero{{padding:0 0 18px}}.hero p{{color:#555}}.timeline{{width:auto;margin:0}}.year{{break-inside:avoid-page}}.year-heading span{{color:#6b512b}}.events{{border-left:1px solid #777}}.event-main{{background:white;border:1px solid #bbb}}.event p{{color:#444}}.people-note{{background:#f4efe5;border-color:#aaa}}}}
</style>
</head>
<body>
<nav class="topbar">
  <a href="/journal">Evidence Journal</a>
  <a class="primary" href="/scribes">As the Scribes Saw It</a>
  <a href="/campaign">Campaign</a>
  <div class="spacer"></div>
  <button type="button" onclick="window.print()">Print / PDF</button>
</nav>
<header class="hero">
  <div class="kicker">Stellaris Historian</div>
  <h1>Empire Timeline</h1>
  <p><strong>{_e(campaign['empire_name'])}</strong> — a selective chronology from {_e(campaign['first_game_date'])} to {_e(campaign['latest_game_date'])}. Major expansion, people, discoveries, technology and reconstructed combat episodes are shown here; the deeper evidence remains in the Historical Journal.</p>
</header>
<div class="filters" aria-label="Timeline filters">
  <button class="active" data-filter="All">All</button>
  <button data-filter="Empire">Empire</button>
  <button data-filter="Expansion">Expansion</button>
  <button data-filter="People">People</button>
  <button data-filter="Military">Military</button>
  <button data-filter="Combat">Combat</button>
  <button data-filter="Technology">Technology</button>
  <button data-filter="Science">Science</button>
  <button data-filter="Exploration">Exploration</button>
</div>
<main class="timeline">{''.join(year_blocks) if year_blocks else '<div class="empty">No timeline events are available yet.</div>'}</main>
<script>
(() => {{
  const buttons = [...document.querySelectorAll('.filters button')];
  const events = [...document.querySelectorAll('.event')];
  const years = [...document.querySelectorAll('.year')];
  function apply(filter) {{
    buttons.forEach(b => b.classList.toggle('active', b.dataset.filter === filter));
    events.forEach(event => {{
      event.hidden = filter !== 'All' && event.dataset.category !== filter;
    }});
    years.forEach(year => {{
      const visible = [...year.querySelectorAll('.event')].some(event => !event.hidden);
      year.hidden = !visible;
    }});
  }}
  buttons.forEach(button => button.addEventListener('click', () => apply(button.dataset.filter)));
}})();
</script>
</body>
</html>
"""

    fd, temp_name = tempfile.mkstemp(prefix=".timeline_", suffix=".html", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(html)
        os.replace(temp_name, target)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise

    return target
