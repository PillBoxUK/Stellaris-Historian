from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from pathlib import Path
import os
import tempfile
import re

from .db import Database
from .presentation_history import PresentationHistory, build_presentation_history


@dataclass
class FormalWarRecord:
    war_id: int
    name: str
    start_date: str | None
    first_observed: str
    last_observed: str
    player_side: str
    attacker_war_goal: str | None
    defender_war_goal: str | None
    attacker_war_exhaustion: float | None = None
    defender_war_exhaustion: float | None = None
    battles: dict[str, object] = field(default_factory=dict)
    battle_first_seen: dict[str, str] = field(default_factory=dict)
    first_absent_after_last: str | None = None
    attacker_country_ids: tuple[int, ...] = ()
    defender_country_ids: tuple[int, ...] = ()


def war_journal_path(db: Database, campaign_id: int) -> Path:
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist.")
    return Path(campaign["archive_dir"]) / "War_Journal.html"


def _e(value: object) -> str:
    return escape("" if value is None else str(value))


def _date_key(value: str | None) -> tuple[int, int, int]:
    try:
        year, month, day = str(value).split(".")[:3]
        return int(year), int(month), int(day)
    except (TypeError, ValueError, AttributeError):
        return (999999, 99, 99)


def _join(values: tuple[str, ...] | list[str], empty: str = "Not established") -> str:
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    if not cleaned:
        return empty
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return ", ".join(cleaned[:-1]) + f", and {cleaned[-1]}"


def _period(start: str, end: str) -> str:
    return start if start == end else f"{start} to {end}"


def _outcome_label(value: str | None) -> str:
    if value == "victory":
        return "Formal victory retained"
    if value == "defeat":
        return "Formal defeat retained"
    return "Outcome not established"


def _float_percent(value: float | None) -> str:
    if value is None:
        return "Not retained"
    # Stellaris values may be stored either as a 0..1 fraction or as a direct
    # percentage-like number depending on the field/version. Avoid silently
    # rescaling unknown engine semantics here; preserve the decoded numeric value.
    return f"{value:g}"


def _aggregate_formal_wars(history: PresentationHistory) -> list[FormalWarRecord]:
    records: dict[int, FormalWarRecord] = {}
    snapshots = sorted(history.combat_snapshots, key=lambda row: _date_key(row.game_date))

    for snapshot in snapshots:
        for war_id, state in snapshot.wars.items():
            record = records.get(war_id)
            if record is None:
                record = FormalWarRecord(
                    war_id=war_id,
                    name=state.name,
                    start_date=state.start_date,
                    first_observed=snapshot.game_date,
                    last_observed=snapshot.game_date,
                    player_side=state.player_side,
                    attacker_war_goal=state.attacker_war_goal,
                    defender_war_goal=state.defender_war_goal,
                    attacker_war_exhaustion=getattr(state,"attacker_war_exhaustion",None),
                    defender_war_exhaustion=getattr(state,"defender_war_exhaustion",None),
                    attacker_country_ids=tuple(state.attacker_country_ids),
                    defender_country_ids=tuple(state.defender_country_ids),
                )
                records[war_id] = record
            else:
                record.last_observed = snapshot.game_date
                record.name = state.name or record.name
                record.start_date = state.start_date or record.start_date
                record.player_side = state.player_side or record.player_side
                record.attacker_war_goal = state.attacker_war_goal or record.attacker_war_goal
                record.defender_war_goal = state.defender_war_goal or record.defender_war_goal
                record.attacker_country_ids = tuple(state.attacker_country_ids) or record.attacker_country_ids
                record.defender_country_ids = tuple(state.defender_country_ids) or record.defender_country_ids
                # Cache v4+ supplies verified direct war-child fields. Older
                # caches will be invalidated by their component version.
                if getattr(state,'attacker_war_exhaustion',None) is not None:
                    record.attacker_war_exhaustion=state.attacker_war_exhaustion
                if getattr(state,'defender_war_exhaustion',None) is not None:
                    record.defender_war_exhaustion=state.defender_war_exhaustion

            for battle in state.battles:
                record.battles[battle.battle_key] = battle
                record.battle_first_seen.setdefault(battle.battle_key, snapshot.game_date)

    # A later combat snapshot without the war bounds the ending; it does not
    # establish the exact peace date, terms or territorial changes.
    for record in records.values():
        record.first_absent_after_last = next(
            (snap.game_date for snap in snapshots
             if _date_key(snap.game_date) > _date_key(record.last_observed)
             and record.war_id not in snap.wars),
            None,
        )

    return sorted(
        records.values(),
        key=lambda row: _date_key(row.start_date or row.first_observed),
    )


def _war_display_title(record: FormalWarRecord, empire_name: str, country_names: dict[int, str] | None = None) -> tuple[str, str]:
    """Build titles from native war fields and cached country identities only.

    Neither manually supplied names nor screenshots may influence the journal.
    Unresolved opposing parties remain explicitly unnamed.
    """
    native = str(record.name or "").strip()
    if native and not re.fullmatch(r"War\s+\d+", native, flags=re.IGNORECASE):
        return native, "Name retained from parsed Stellaris war record"
    if record.attacker_war_goal:
        goal = str(record.attacker_war_goal).replace("_", " ").strip().title()
        opponent_ids = (record.defender_country_ids if record.player_side == "attacker"
                        else record.attacker_country_ids)
        named = [(cid, (country_names or {}).get(cid, "")) for cid in opponent_ids]
        named = [(cid, label) for cid, label in named
                 if label and not re.fullmatch(r"Country\s+\d+", label, flags=re.I)]
        if len(opponent_ids) == 1 and len(named) == 1:
            return (f"War of {goal} against {named[0][1]}",
                    "Historian-generated title: retained war goal and country identity "
                    "resolved from archived diplomatic/combat evidence")
        if named:
            return (f"War of {goal} against " + _join([name for _id, name in named]),
                    "Historian-generated title: known opposing war participants from cached save evidence; "
                    "unresolved participants not guessed")
        return f"War of {goal}", ("Descriptive title from recorded war goal; "
                                  "opposing party name not established from saved evidence")
    return f"War {record.war_id}", "Native war name unavailable"


def _war_victory_annotation(record: FormalWarRecord, empire_name: str) -> None:
    """Compatibility shim: external claims are never imported as canonical war facts.

    Historical results require direct decoded save evidence. Existing manual
    annotation JSON files are not read, modified or deleted by this policy.
    """
    return None


def _war_anchor(war_id: int) -> str:
    """Stable URL fragment; never generated from mutable/localized war names."""
    return f"war-{int(war_id)}"


def _war_nav_html(wars: list[FormalWarRecord], position: int, empire_name: str,
                  country_names: dict[int, str] | None = None, *, at_bottom: bool = False) -> str:
    """Chronological, evidence-safe previous/next links used above and below a war."""
    if not (0 <= position < len(wars)):
        raise IndexError("War navigation index is outside the known war list")

    def neighbour(index: int, label: str, arrow: str) -> str:
        if index < 0 or index >= len(wars):
            return f'<span class="war-step disabled" aria-disabled="true">{_e(arrow)} {_e(label)}<small>None</small></span>'
        row = wars[index]
        title, _ = _war_display_title(row, empire_name, country_names)
        return (f'<a class="war-step" href="#{_war_anchor(row.war_id)}" title="{_e(title)}" '
                f'aria-label="{_e(label)}: {_e(title)}">'
                f'{_e(arrow)} {_e(label)}<small>{_e(title)}</small></a>')

    previous = neighbour(position - 1, 'Previous war', '←')
    following = neighbour(position + 1, 'Next war', '→')
    loc = 'bottom' if at_bottom else 'top'
    return (f'<div class="war-pager {loc}" role="navigation" aria-label="War {position + 1} of {len(wars)}, '
            f'{loc} navigation">{previous}'
            f'<a class="war-index-return" href="#war-index" aria-label="Return to the war index">'
            f'War {position + 1} of {len(wars)}<small>↑ All wars</small></a>{following}</div>')


def _war_technology_html(record: FormalWarRecord, tech_events: tuple[object, ...],
                         *, snapshots_available: bool = False,
                         technology_dates: tuple[str, ...] = ()) -> str:
    """War research evidence from completed technology only; no raw-save reads.

    An event's first-observed archive is not proof that its acquisition happened
    after the war began, even when its first-observed date falls inside a war.
    The previous-day bound and archive coverage are displayed separately.
    """
    from .domains.technology.history import technology_window_label
    if not snapshots_available:
        return ('<details class="wartime-tech"><summary>Technology during this conflict — archive coverage unavailable</summary>'
                '<p class="evidence-note">There are no comparable cached technology snapshots. '
                'This is not evidence that research stopped.</p></details>')

    lower = _date_key(record.first_observed)
    upper = _date_key(record.last_observed)
    dates = sorted({_date_key(date): date for date in technology_dates
                    if _date_key(date)[0] < 999999}.items())
    inside = [(key, date) for key, date in dates if lower <= key <= upper]
    before = [date for key, date in dates if key < lower]
    # If the caller hasn't supplied coverage dates (older tests/integrations),
    # don't pretend that there are zero within-war archives.
    if technology_dates and not inside:
        return ('<details class="wartime-tech"><summary>Technology during this conflict — no within-war archive coverage</summary>'
                '<p class="evidence-note research-coverage">No completed-technology cache has a date between '
                f'{_e(record.first_observed)} and {_e(record.last_observed)}. '
                'Research cannot be assessed for this war from these caches; '
                'this does not mean research stopped.</p></details>')

    observed = [t for t in tech_events if lower <= _date_key(t.game_date) <= upper]
    observed.sort(key=lambda t: (_date_key(t.game_date), str(t.name)))
    rows = []
    overlaps = 0
    for item in observed:
        # An appearance inside the war can be bounded by an earlier archive
        # outside the war. It must not be called research completed during war.
        previous = _date_key(item.previous_game_date)
        straddles = bool(item.previous_game_date and previous < lower)
        if straddles:
            overlaps += 1
        linkage = ('Window begins before the first archived war observation; may predate war'
                   if straddles else 'First seen while war archived; connection to war unverified')
        level = f'Level {item.level}' if item.level > 1 else 'First observed'
        rows.append(f'<tr><td>{_e(item.game_date)}</td><td>{_e(item.name)}</td>'
                    f'<td>{_e(level)}</td><td>{_e(technology_window_label(item))}</td>'
                    f'<td>{_e(linkage)}</td></tr>')
    detail = ('<div class="table-wrap"><table><thead><tr><th>First observed</th><th>Technology</th>'
              '<th>Recorded status</th><th>Acquisition window</th><th>War relationship</th>'
              '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>') if rows else (
              '<p class="evidence-note">No additional completed technology was observed in these comparable '
              'cached snapshots during the war observation window. This does not establish that research stopped.</p>')
    if technology_dates:
        coverage = (f'{len(inside)} distinct technology archive date(s) within the war observation window '
                    f'({_e(inside[0][1])} to {_e(inside[-1][1])}). ' if inside else '')
        coverage += ('A technology archive also precedes the first war observation. ' if before else
                     'No earlier cached technology date is available to establish the opening boundary. ')
    else:
        coverage = 'Detailed technology snapshot-date coverage was not provided to this renderer. '
    if overlaps:
        coverage += f'{overlaps} observation window(s) cross the first war archive boundary; those advances could predate the war. '
    return (f'<details class="wartime-tech"><summary>Research advances first observed while war archived '
            f'({len(observed)})</summary>'
            f'<p class="evidence-note research-coverage">{coverage}</p>{detail}'
            '<p class="evidence-note">Source: already-cached completed technologies, never queued research. '
            'First observed is not an exact acquisition day, nor proof the conflict caused the research. '
            'Opening archive knowledge is not counted as a new discovery; gaps in coverage may hide advances.</p></details>')


def _research_audit_html(technology_history: dict) -> str:
    """Read-only archive-coverage card for a source-transparent military journal."""
    coverage = technology_history.get('coverage', {})
    dates = int(coverage.get('distinct_dates', 0))
    if not dates:
        return ('<section id="research-audit"><h2>Technology Archive Audit</h2>'
                '<p class="evidence-note">No valid dated completed-technology snapshots were found in the '
                'processed evidence cache. This does not mean the empire stopped researching.</p></section>')
    events = technology_history.get('events', ())
    return (f'<section id="research-audit"><h2>Technology Archive Audit</h2>'
            '<p class="evidence-note">Independent research-cache quality check. These observations are '
            'not battle outcomes and cannot establish that a war caused a technological advance.</p>'
            '<div class="facts">'
            f'<div><span>Completed-technology archive snapshots</span><strong>{int(coverage.get("snapshots", 0))}</strong></div>'
            f'<div><span>Distinct dated observations</span><strong>{dates}</strong></div>'
            f'<div><span>Additional saves on existing dates</span><strong>{int(coverage.get("same_date_additional_snapshots", 0))}</strong></div>'
            f'<div><span>Same-day states differing</span><strong>{int(coverage.get("same_date_disagreement_days", 0))}</strong></div>'
            f'<div><span>Invalid dated caches excluded</span><strong>{int(coverage.get("invalid_date_snapshots", 0))}</strong></div>'
            f'<div><span>New observed advances/levels</span><strong>{len(events)}</strong></div>'
            '</div>'
            f'<p class="evidence-note">Research coverage runs from {_e(coverage.get("first_date"))} '
            f'to {_e(coverage.get("last_date"))} (archive observation dates, not exact completion days). '
            'Multiple saved states dated the same day are not ordered as though the game retained a time of day. '
            'Missing or lower later cache values cannot manufacture a new completion. '
            'Detailed acquisition windows appear within each formal war report only where the war and '
            'research archive windows overlap.</p></section>')


def _war_chronology_html(record: FormalWarRecord, victory: dict | None = None, *, empire_name: str = "the civilisation") -> str:
    """Timeline grounded only in decoded war records and cached battles.

    The optional second argument is ignored for backward API compatibility.
    No external testimony, screenshots or annotated outcomes enter the report.
    """
    battles = sorted(record.battles.values(), key=lambda b: (_date_key(b.date), str(b.battle_key)))
    dated = [b for b in battles if _date_key(b.date)[0] < 999999 and _date_key(b.date) != (0, 1, 1)]
    years: dict[str, list[object]] = {}
    for battle in dated:
        years.setdefault(str(battle.date).split('.')[0], []).append(battle)
    rows = []
    for year, group in sorted(years.items(), key=lambda item: int(item[0])):
        places = sorted({str(b.system_name or b.planet_name) for b in group if b.system_name or b.planet_name})
        player_losses = [b.player_losses for b in group]
        opposing_losses = [b.enemy_losses for b in group]
        p = str(sum(player_losses)) if all(v is not None for v in player_losses) else 'Incomplete'
        o = str(sum(opposing_losses)) if all(v is not None for v in opposing_losses) else 'Incomplete'
        ranges = str(group[0].date) if len(group)==1 else f'{group[0].date} → {group[-1].date}'
        location_text = ', '.join(places[:7]) + (f' +{len(places) - 7} more' if len(places) > 7 else '')
        rows.append(f'<tr><td>{_e(year)}</td><td>{len(group)}</td><td>{_e(ranges)}</td>'
                    f'<td>{_e(location_text or "Unknown")}</td><td>{_e(p)}</td><td>{_e(o)}</td></tr>')
    if record.start_date:
        start = f'<li><strong>{_e(record.start_date)}</strong> — Recorded war start date (native war field)</li>'
    else:
        start = f'<li><strong>{_e(record.first_observed)}</strong> — War first visible in the archive; actual start not established</li>'
    first = (f'<li><strong>{_e(dated[0].date)}</strong> — First dated player-involved battle retained '
             f'({_e(dated[0].system_name or dated[0].planet_name or "location not established")})</li>') if dated else ''
    last = (f'<li><strong>{_e(dated[-1].date)}</strong> — Last dated player-involved battle retained '
            f'({_e(dated[-1].system_name or dated[-1].planet_name or "location not established")})</li>') if len(dated)>1 else ''
    seen = f'<li><strong>{_e(record.last_observed)}</strong> — Last archive observation retaining the war</li>'
    absence = (f'<li><strong>{_e(record.first_absent_after_last)}</strong> — '
               'First later archive without this war</li>') if record.first_absent_after_last else ''
    notable = sorted((b for b in dated if b.player_losses is not None),
                     key=lambda b: (-b.player_losses, _date_key(b.date), str(b.battle_key)))[:3]
    highlights = ''.join(
        f'<li><strong>{_e(b.date)}</strong> — {_e(b.system_name or b.planet_name or "Unresolved location")}: '
        f'{_e(b.player_losses)} recorded {_e(empire_name)} ship losses (formal battle tally; no cause inferred)</li>'
        for b in notable if b.player_losses > 0
    )
    year_table = ('<div class="table-wrap"><table><thead><tr><th>Year</th><th>Battles</th><th>Observed dates</th>'
                  f'<th>Recorded battle locations</th><th>{_e(empire_name)} losses</th><th>Opposing losses</th>'
                  '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>') if rows else '<p class="muted">No dated player-involved formal battles recovered.</p>'
    return (f'<section class="war-chronicle" aria-label="War chronology">'
            '<h4>War chronicle — verified observation sequence</h4>'
            f'<ol class="chronicle-milestones">{start}{first}{last}{seen}{absence}</ol>'
            '<p class="evidence-note">The milestones combine native war and battle dates, quarterly save observations, '
            'only. They are not proof of war outcomes or a full day-by-day war diary.</p>'
            '<details class="chronicle-years"><summary>Year-by-year battle chronology '
            f'({len(dated)} dated player-involved battles across {len(years)} years)</summary>{year_table}'
            '<p class="evidence-note">Casualties are recorded per formal battle. Incomplete means at least one '
            'battle has no complete count; no missing values are guessed.</p></details>'
            + (f'<details class="chronicle-highlights"><summary>Largest recorded {_e(empire_name)} ship-loss events</summary>'
               f'<ol>{highlights}</ol><p class="evidence-note">Not a ranking of war importance or proof of starbase '
               'damage. Station involvement requires separate evidence.</p></details>' if highlights else '')
            + '</section>')


def _war_index_html(wars: list[FormalWarRecord], empire_name: str,
                    country_names: dict[int, str] | None = None) -> str:
    if not wars:
        return ''
    cards = []
    for number, war in enumerate(wars, 1):
        title, _ = _war_display_title(war, empire_name, country_names)
        state = (f'Ending bounded by {war.first_absent_after_last}' if war.first_absent_after_last
                 else 'No ending boundary established')
        cards.append(f'<a class="war-index-card" href="#{_war_anchor(war.war_id)}" '
                     f'title="Read {_e(title)}">'
                     f'<span class="war-index-number">{number:02d}</span>'
                     f'<span><strong>{_e(title)}</strong>'
                     f'<small>Started {_e(war.start_date or "Unknown")} · {len(war.battles)} formal battle records</small>'
                     f'<small>{_e(state)}</small></span><span aria-hidden="true">→</span></a>')
    return ('<div id="war-index" class="war-index" aria-label="Chronological war index">'
            '<h3>Jump to a war</h3><p class="evidence-note">Chronological order. '
            'Each link opens that war directly and can be bookmarked or shared.</p>'
            '<div class="war-index-grid">' + ''.join(cards) + '</div></div>')


def _fleet_display_labels(episode, known_commanders: set[str] | None = None) -> tuple[str, ...]:
    """Avoid showing identified commander labels as fleet names; keep source unchanged."""
    commanders = {str(x).strip().casefold() for x in episode.commander_names if str(x).strip()}
    commanders.update(known_commanders or ())
    return tuple(name for name in episode.fleet_names if str(name).strip().casefold() not in commanders)


def _episode_title(episode) -> str:
    systems = _join(episode.system_names, empty="")
    enemies = _join(episode.enemy_country_names, empty="")
    if episode.has_direct_evidence and systems:
        title = f"Battle of {systems}"
    elif systems:
        title = f"Combat episode at {systems}"
    elif enemies:
        title = f"Combat with {enemies}"
    else:
        title = "Combat episode"
    if enemies and enemies not in title:
        title += f" — {enemies}"
    return title


def _episode_html(episode, empire_name: str) -> str:
    # Retained fleet names can be contaminated by a temporary leader label.
    # Only suppress labels already independently identified as commanders.
    display_fleets = _fleet_display_labels(episode)
    first = episode.initial_loss_observation
    latest = episode.latest_loss_observation
    evidence = "Direct retained combat telemetry" if episode.has_direct_evidence else "Correlated combat activity"

    loss_html = "<p class='muted'>No complete direct loss tally is retained for this episode.</p>"
    if first is not None and latest is not None:
        if episode.telemetry_evolved:
            loss_html = (
                "<div class='loss-grid'>"
                f"<div><span>Earliest complete tally</span><strong>{_e(first.player_ships_lost)} / {_e(first.enemy_ships_lost)}</strong>"
                f"<small>{_e(empire_name)} / opposing losses · observed {_e(first.observed_date)}</small></div>"
                f"<div><span>Latest complete tally</span><strong>{_e(latest.player_ships_lost)} / {_e(latest.enemy_ships_lost)}</strong>"
                f"<small>{_e(empire_name)} / opposing losses · observed {_e(latest.observed_date)}</small></div>"
                "</div>"
                "<p class='evidence-note'>These are evolving retained telemetry states, not separate loss events to be added together.</p>"
            )
        else:
            loss_html = (
                "<div class='loss-grid one'>"
                f"<div><span>Retained loss tally</span><strong>{_e(latest.player_ships_lost)} / {_e(latest.enemy_ships_lost)}</strong>"
                f"<small>{_e(empire_name)} / opposing losses · observed {_e(latest.observed_date)}</small></div>"
                "</div>"
            )

    possible = ""
    if episode.possible_loss_names:
        possible = (
            "<div class='possible-losses'><strong>Possible loss identities — not confirmed:</strong> "
            + _e(_join(episode.possible_loss_names))
            + "</div>"
        )

    return f"""
      <article class="episode-card">
        <div class="episode-head">
          <div>
            <div class="date">{_e(_period(episode.start_date, episode.end_date))}</div>
            <h3>{_e(_episode_title(episode))}</h3>
          </div>
          <div class="badge {'direct' if episode.has_direct_evidence else 'correlated'}">{_e(evidence)}</div>
        </div>
        <div class="facts">
          <div><span>Systems</span><strong>{_e(_join(episode.system_names))}</strong></div>
          <div><span>Opposing force</span><strong>{_e(_join(episode.enemy_country_names))}</strong></div>
          <div><span>Recorded fleets</span><strong>{_e(_join(display_fleets))}</strong></div>
          <div><span>Commanders</span><strong>{_e(_join(episode.commander_names))}</strong></div>
          <div><span>Formal outcome</span><strong>{_e("Under review (raw formal battle outcome retained)" if episode.formal_outcome else "Not established")}</strong></div>
          <div><span>Confidence</span><strong>{_e(str(episode.confidence).title())}</strong></div>
        </div>
        {loss_html}
        {possible}
        <div class="evidence-note">Activity dates retained: {_e(_join(episode.activity_dates, empty='None retained'))}. This episode is not automatically classified as a formal war unless a retained formal war record exists.</div>
      </article>
    """


def _formal_war_html(record: FormalWarRecord, latest_combat_date: str | None, empire_name: str = "", country_names: dict[int, str] | None = None,
                     *, navigator_top: str = "", navigator_bottom: str = "",
                     technology_events: tuple[object, ...] = (), technology_available: bool = False,
                     technology_dates: tuple[str, ...] = ()) -> str:
    title, title_provenance = _war_display_title(record, empire_name, country_names)
    battles = sorted(record.battles.values(), key=lambda row: _date_key(row.date))
    rows: list[str] = []
    player_attacker = sum(b.player_side == "attacker" for b in battles)
    player_defender = sum(b.player_side == "defender" for b in battles)
    flag_yes = sum(b.attacker_victory is True for b in battles)
    flag_no = sum(b.attacker_victory is False for b in battles)
    flag_missing = len(battles) - flag_yes - flag_no
    player_loss_known = [b.player_losses for b in battles if b.player_losses is not None]
    enemy_loss_known = [b.enemy_losses for b in battles if b.enemy_losses is not None]
    player_loss_text = str(sum(player_loss_known)) if len(player_loss_known) == len(battles) else "Incomplete"
    enemy_loss_text = str(sum(enemy_loss_known)) if len(enemy_loss_known) == len(battles) else "Incomplete"
    locations = sorted({str(b.system_name or b.planet_name) for b in battles if b.system_name or b.planet_name})
    # Location summaries only group explicitly retained battle records. These do not
    # infer conquest, permanent ownership, victory or peace settlement.
    by_location: dict[str, list[object]] = {}
    for battle in battles:
        name = str(battle.system_name or battle.planet_name or "Location not established")
        by_location.setdefault(name, []).append(battle)
    theatre_rows = []
    for name, group in sorted(by_location.items(), key=lambda item: (-len(item[1]), item[0].casefold())):
        ordered = sorted(group, key=lambda b: _date_key(b.date))
        pa = [b.player_losses for b in group]
        ea = [b.enemy_losses for b in group]
        pa_text = str(sum(pa)) if all(v is not None for v in pa) else "Incomplete"
        ea_text = str(sum(ea)) if all(v is not None for v in ea) else "Incomplete"
        theatre_rows.append(
            f"<tr><td>{_e(name)}</td><td>{len(group)}</td>"
            f"<td>{_e(ordered[0].date)} – {_e(ordered[-1].date)}</td>"
            f"<td>{_e(pa_text)}</td><td>{_e(ea_text)}</td>"
            f"<td><button type='button' class='theatre-filter' data-location='{_e(name)}' "
            f"aria-label='Show battles at {_e(name)}'>View battles</button></td></tr>"
        )
    theatre_html = (
        "<details class='theatre-breakdown'><summary>Battle theatres — group by recorded location</summary>"
        "<p class='evidence-note'>Records are grouped by retained location name. Ship losses are formal-record totals only. "
        "A battle occurring in a system does not establish occupation, ownership or an outcome.</p>"
        "<div class='table-wrap'><table><thead><tr><th>Recorded location</th><th>Battles</th>"
        "<th>First – last date</th><th>Player losses</th><th>Opposing losses</th><th>Jump to records</th></tr></thead><tbody>"
        + "".join(theatre_rows) + "</tbody></table></div></details>"
    )
    # These are sums across distinct retained formal battle records, NOT fleet losses
    # reconstructed from ship-activity telemetry.
    for battle in battles:
        # v0.0.55: The tactical attacker_victory flag is retained, but its
        # interpretation against the player's war occupation has not been
        # independently validated. Do not claim an established player result.
        outcome = "Unverified (raw flag retained)" if battle.attacker_victory is not None else "Not recorded"
        location = battle.system_name or battle.planet_name or "Not established"
        rows.append(
            f"<tr class='battle-row' data-role='{_e(battle.player_side)}' data-flag='{_e('yes' if battle.attacker_victory is True else 'no' if battle.attacker_victory is False else 'missing')}' data-search='{_e(' '.join([str(battle.date), str(location), str(battle.battle_type), str(battle.player_side)]).casefold())}'>"
            f"<td>{_e(battle.date)}</td>"
            f"<td>{_e(str(battle.battle_type).replace('_', ' ').title())}</td>"
            f"<td>{_e(location)}</td>"
            f"<td>{_e(outcome)}<small style='display:block'>Tactical player role: {_e(battle.player_side)}; attacker_victory: {_e('yes' if battle.attacker_victory is True else 'no' if battle.attacker_victory is False else 'missing')}</small></td>"
            f"<td><strong>{_e(', '.join(map(str,battle.attacker_country_ids)) or '—')}</strong><small style='display:block'>Defender IDs: {_e(', '.join(map(str,battle.defender_country_ids)) or '—')}</small></td>"
            f"<td>{_e(record.battle_first_seen.get(battle.battle_key, 'Not recorded'))}<small style='display:block'>Battle index: {_e(battle.battle_index)}</small></td>"
            f"<td>{_e(battle.player_losses if battle.player_losses is not None else '—')}</td>"
            f"<td>{_e(battle.enemy_losses if battle.enemy_losses is not None else '—')}</td>"
            "</tr>"
        )

    status = "Present in latest retained combat snapshot"
    if record.first_absent_after_last:
        status = (
            f"Ending observed between {record.last_observed} and "
            f"{record.first_absent_after_last} (first later snapshot without this war). "
            "Exact day and peace terms unverified; analyze territorial control below"
        )
    elif latest_combat_date and _date_key(record.last_observed) < _date_key(latest_combat_date):
        status = (
            f"Last observed {record.last_observed}; no confirmed ending interval. "
            "Current status unverified"
        )

    battle_table = (
        "<p class='muted'>No direct player battle rows are retained for this war.</p>"
        if not rows
        else """
          <div class="battle-tools" aria-label="Filter retained battle records">
            <label>Search date / system <input class="battle-search" type="search" placeholder="e.g. Hiamit or 2264" aria-label="Search battles"></label>
            <label>Tactical player role <select class="battle-role"><option value="all">All roles</option><option value="attacker">Attacker</option><option value="defender">Defender</option></select></label>
            <label>Raw attacker_victory flag <select class="battle-flag"><option value="all">All flags</option><option value="yes">Yes</option><option value="no">No</option><option value="missing">Missing</option></select></label>
            <button type="button" class="battle-reset">Reset filters</button><span class="battle-shown" role="status" aria-live="polite"></span>
          </div>
          <div class="table-wrap"><table>
            <thead><tr><th>Date</th><th>Type</th><th>Location</th><th>Player result</th><th>Tactical country IDs</th><th>First archive containing record</th><th>Player losses</th><th>Opposing losses</th></tr></thead>
            <tbody>""" + "".join(rows) + "</tbody></table></div>"
    )

    return f"""
      <article class="war-card" id="{_war_anchor(record.war_id)}" tabindex="-1" data-war-id="{_e(record.war_id)}">
        {navigator_top}
        <div class="date">War ID: {_e(record.war_id)}</div>
        <h3>{_e(title)}</h3>
        <p class="evidence-note">{_e(title_provenance)}</p>
        <div class="facts">
          <div><span>Recorded start</span><strong>{_e(record.start_date or 'Not retained')}</strong></div>
          <div><span>Archive observation</span><strong>{_e(record.first_observed)} → {_e(record.last_observed)}</strong></div>
          <div><span>Player war coalition</span><strong>{_e(record.player_side.title())}</strong></div>
          <div><span>Status</span><strong>{_e(status)}</strong></div>
          <div><span>Attacker war goal</span><strong>{_e(record.attacker_war_goal or 'Not retained')}</strong></div>
          <div><span>Defender war goal</span><strong>{_e(record.defender_war_goal or 'Not retained')}</strong></div>
          <div><span>Attacker exhaustion (raw fraction)</span><strong>{_e(_float_percent(record.attacker_war_exhaustion) if record.attacker_war_exhaustion is not None else 'Not verified from archived war')}</strong></div>
          <div><span>Defender exhaustion (raw fraction)</span><strong>{_e(_float_percent(record.defender_war_exhaustion) if record.defender_war_exhaustion is not None else 'Not verified from archived war')}</strong></div>
        </div>
        {_war_chronology_html(record, empire_name=empire_name)}
        {_war_technology_html(record, technology_events, snapshots_available=technology_available,
                              technology_dates=technology_dates)}
        <div class="war-actions"><button type="button" class="copy-war-brief" aria-label="Copy this war's evidence brief">Copy war brief</button><button type="button" class="download-war-brief" aria-label="Download this war's evidence brief">Save war brief (.txt)</button><span class="war-copy-feedback" role="status" aria-live="polite"></span></div>
        <div class="evidence-audit">
          <h4>Retained war and battle evidence</h4>
          <div class="audit-grid">
            <div><span>Player tactical attacker</span><strong>{player_attacker}</strong></div>
            <div><span>Player tactical defender</span><strong>{player_defender}</strong></div>
            <div><span>Raw flag: yes / no / missing</span><strong>{flag_yes} / {flag_no} / {flag_missing}</strong></div>
            <div><span>Distinct battle locations</span><strong>{len(locations)}</strong></div>
            <div><span>Recorded player ship losses (battle totals)</span><strong>{_e(player_loss_text)}</strong></div>
            <div><span>Recorded opposing ship losses (battle totals)</span><strong>{_e(enemy_loss_text)}</strong></div>
          </div>
          <p class="evidence-note">These are descriptive counts from unique retained player-involved formal battle records. Tactical roles and raw flags do not establish who won. Loss totals include only records with complete loss fields and must not be combined with correlated combat markers.</p>
          <details class="participant-evidence"><summary>War coalition identifiers (raw save IDs, not verified names)</summary>
            <p>Attacker country IDs: {_e(', '.join(map(str,record.attacker_country_ids)) or 'Not retained')} · Defender country IDs: {_e(', '.join(map(str,record.defender_country_ids)) or 'Not retained')}</p>
          </details>
        </div>
        {(
          "<section class='aftermath' data-war-id='" + _e(record.war_id) + "'>"
          "<h4>Territorial aftermath — archived control comparison</h4>"
          "<p class='evidence-note'>Compare the last processed snapshot containing this war with the first processed snapshot in which it is absent. This is a read-only, on-demand analysis of starbase control. The first analysis may take a few seconds.</p>"
          "<button class='aftermath-run' type='button' data-war-id='" + _e(record.war_id) + "'>Analyze territorial changes</button>"
          "<div class='aftermath-result' role='status' aria-live='polite'></div>"
          "</section>"
          if record.first_absent_after_last else ""
        )}
        <section class="aftermath military-intel" data-war-id="{_e(record.war_id)}">
          <h4>Ground warfare, occupations &amp; enemy starbases</h4>
          <p class="evidence-note">Read-only background investigation of army battles, occupation, opposing starbase activity, and battle-local exhaustion evidence. Progress appears while each archive is checked. It never guesses war-wide exhaustion or ship-loss causes.</p>
          <button class="aftermath-run military-run" type="button" data-war-id="{_e(record.war_id)}">Investigate ground and starbase evidence</button>
          <div class="military-result" role="status" aria-live="polite"></div>
        </section>
        <p class="evidence-note"><strong>Exhaustion evidence:</strong> The values above come from the war record’s direct attacker_war_exhaustion and defender_war_exhaustion children in its last observed save, where available. Raw fractions are shown without assuming their exact on-screen percentage display or converting nested battle-local fields into war-wide totals.</p>
        <p class="evidence-note"><strong>Outcome verification pending:</strong> the tactical battle attacker/defender roles and raw attacker_victory field are shown separately. Their mapping to player victory/defeat is under review against war coalition and occupation evidence; no result is reversed automatically.</p>
        {theatre_html}
        <details class="battle-dossier"><summary>Direct player battle records ({len(battles)}) — expand detailed tables and filters</summary>
          {battle_table}
        </details>
        {navigator_bottom}
      </article>
    """


def _investigation_html(wars: list[FormalWarRecord], episodes: list[object], direct_episode_lookup: dict | None = None) -> str:
    """A comparison index: contextual overlap is never promoted into a battle identity."""
    def ordinal(value: str | None) -> int | None:
        # Stellaris uses 12 30-day months, not Gregorian calendar dates.
        try:
            y, m, d = (int(x) for x in str(value).split(".")[:3])
            if not (1 <= m <= 12 and 1 <= d <= 30):
                return None
            return y * 360 + (m - 1) * 30 + d
        except (TypeError, ValueError, OverflowError):
            return None

    direct_episode_lookup = direct_episode_lookup or {}
    formal = [(war, b) for war in wars for b in war.battles.values()]
    known_commanders = {str(name).strip().casefold() for ep in episodes for name in ep.commander_names if str(name).strip()}
    rows = []
    for episode in sorted(episodes, key=lambda ep: _date_key(ep.start_date)):
        if not episode.has_direct_evidence:
            continue
        ep_date = ordinal(episode.start_date)
        ep_systems = {str(system).strip().casefold() for system in episode.system_names if str(system).strip()}
        possible = []
        for war, battle in formal:
            battle_date = ordinal(battle.date)
            battle_system = str(battle.system_name or battle.planet_name or "").strip().casefold()
            if (ep_date is None or battle_date is None or not battle_system
                    or battle_system not in ep_systems):
                continue
            gap = abs(ep_date - battle_date)
            if gap <= 45:
                possible.append((gap, war.war_id, str(battle.date), str(battle.system_name or battle.planet_name)))
        possible.sort()
        candidates = (
            "; ".join(f"{_e(dt)} · war {_e(wid)} · {_e(location)} · {gap} day(s) apart"
                      for gap, wid, dt, location in possible[:6])
            if possible else "None within 45 days at the same named location"
        )
        loss = episode.latest_loss_observation
        loss_label = (f"{loss.player_ships_lost} / {loss.enemy_ships_lost}"
                      if loss is not None else "Not retained")
        display_fleets = _fleet_display_labels(episode, known_commanders)
        direct_record = direct_episode_lookup.get(episode.episode_key)
        if direct_record is not None:
            fleet_ids = tuple(sorted({p.player_fleet_id for p in direct_record.player_fleets}))
            fleet_ids_label = ", ".join(str(fid) for fid in fleet_ids)
            combat_start_label = _join(tuple(sorted({p.start_date for p in direct_record.player_fleets})))
        else:
            fleet_ids_label = "Not retained"
            combat_start_label = "Not retained"
        mixed_locations = len(ep_systems) > 1
        system_label = _join(episode.system_names) + (" (multiple context locations; exact combat system not verified)" if mixed_locations else "")
        if mixed_locations and possible:
            candidates = "Context-only, location ambiguous: " + candidates
        rows.append(
            f"<tr class='probe-row' data-direct='yes' data-search='{_e(' '.join([str(episode.start_date), ' '.join(episode.system_names), ' '.join(episode.fleet_names), ' '.join(episode.enemy_country_names)]).casefold())}'>"
            f"<td>{_e(episode.start_date)}</td><td>{_e(system_label)}</td>"
            f"<td>{_e(_join(display_fleets))}<small style='display:block'>Native player fleet ID(s): {_e(fleet_ids_label)}</small><small style='display:block'>Retained commander(s): {_e(_join(episode.commander_names))}</small></td>"
            f"<td>{_e(_join(episode.enemy_country_names))}</td>"
            f"<td>{_e(loss_label)}</td><td>{candidates}</td></tr>"
        )
    if not rows:
        return "<p class='muted'>No direct fleet-telemetry episodes retained.</p>"
    return ("<div class='investigator-tools'><label>Find direct telemetry <input class='investigator-search' type='search' placeholder='System, fleet, opponent, date'></label>"
            "<button class='investigator-clear' type='button'>Clear</button>"
            "<span class='investigator-count' role='status' aria-live='polite'></span></div>"
            "<div class='table-wrap'><table id='telemetry-table'><thead><tr><th>Exact combat date</th><th>System</th><th>Player fleets</th>"
            "<th>Opponent</th><th>Player / opposing losses</th><th>Nearby formal battle (candidate only)</th></tr></thead>"
            "<tbody>" + "".join(rows) + "</tbody></table></div>"
            "<p class='evidence-note'>A candidate requires the same retained system name and a date within 45 days. "
            "It is a search lead, not proof that the two records refer to the same engagement. "
            "Multiple retained context locations are not proof of an exact combat system. "
            "Commander-name labels are excluded from the fleet display when separately identified as commanders. "
            "Only direct telemetry loss tallies appear here; they must not be added to formal battle totals.</p>")


def render_war_journal(db: Database, campaign_id: int) -> Path:
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist.")

    history = build_presentation_history(db, campaign_id)
    formal_wars = _aggregate_formal_wars(history)
    episodes = [
        episode
        for episode in history.combat_episodes
        if episode.has_direct_evidence
        or episode.system_names
        or episode.fleet_names
        or episode.formal_outcome
    ]
    episodes.sort(key=lambda row: _date_key(row.start_date))

    commander_lookup = {name.casefold() for episode in episodes for name in episode.commander_names if name}
    fleets = sorted({name for episode in episodes for name in episode.fleet_names if name and name.casefold() not in commander_lookup})
    commanders = sorted({name for episode in episodes for name in episode.commander_names if name})
    enemies = sorted({name for episode in episodes for name in episode.enemy_country_names if name})
    systems = sorted({name for episode in episodes for name in episode.system_names if name})
    formal_battle_count = sum(len(record.battles) for record in formal_wars)
    direct_episode_count = sum(1 for episode in episodes if episode.has_direct_evidence)
    unverified_battle_count = formal_battle_count  # All formal player results are unverified until mapping is validated.
    latest_combat_date = None
    if history.combat_snapshots:
        latest_combat_date = max(
            (snapshot.game_date for snapshot in history.combat_snapshots),
            key=_date_key,
        )

    # Resolve names from combat snapshots already in the shared presentation
    # cache. No raw archive is opened while rendering the War Journal.
    country_names: dict[int, str] = {}
    for snapshot in history.combat_snapshots:
        for rel in snapshot.relation_kill_counters.values():
            if rel.other_country_name and not re.fullmatch(r"Country\s+\d+", rel.other_country_name, re.I):
                country_names[rel.other_country_id] = rel.other_country_name
        for stat in snapshot.fleet_combat_stats.values():
            for enemy in stat.enemy_fleets:
                if enemy.country_id is not None and enemy.country_name and not re.fullmatch(r"Country\s+\d+", enemy.country_name, re.I):
                    country_names[enemy.country_id] = enemy.country_name
    empire_label = str(campaign["empire_name"])
    war_index_html = _war_index_html(formal_wars, empire_label, country_names)
    # Cached technology snapshots were already loaded by the shared presentation
    # layer. Research summaries do not touch saves, SQL or Live History.
    from .domains.technology.history import derive_technology_history
    technology_history = derive_technology_history(list(history.technology_snapshots))
    technology_events = tuple(technology_history["events"])
    research_audit_html = _research_audit_html(technology_history)
    technology_dates = tuple(snapshot.game_date for snapshot in history.technology_snapshots)
    war_html = "".join(
        _formal_war_html(record, latest_combat_date, empire_label, country_names,
            navigator_top=_war_nav_html(formal_wars, i, empire_label, country_names),
            navigator_bottom=_war_nav_html(formal_wars, i, empire_label, country_names, at_bottom=True),
            technology_events=technology_events, technology_available=bool(history.technology_snapshots),
            technology_dates=technology_dates)
        for i, record in enumerate(formal_wars)
    )
    if not war_html:
        war_html = """
          <div class="empty-state">
            <strong>No formal war records are retained for the tracked empire in the current archive.</strong>
            <p>Combat against fauna, guardians or other forces can still appear below as combat episodes. Historian does not promote those episodes into formal wars without a retained war object.</p>
          </div>
        """

    episode_html = "".join(_episode_html(episode, str(campaign["empire_name"])) for episode in episodes)
    if not episode_html:
        episode_html = """
          <div class="empty-state">
            <strong>No publishable combat episodes are currently reconstructable from retained evidence.</strong>
          </div>
        """

    from .domains.combat.correlation import derive_direct_combat_episodes
    direct_lookup = {
        f"episode:{direct.episode_key}": direct
        for direct in derive_direct_combat_episodes(list(history.combat_snapshots))
    }
    investigation_html = _investigation_html(formal_wars, episodes, direct_lookup)
    title = f"{campaign['empire_name']} - War Journal"
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(title)}</title>
<style>
:root{{--ink:#e8f0f7;--muted:#adc0d1;--paper:#111c2a;--paper2:#203247;--line:#38516b;--dark:#0c1520;--red:#c65c51;--gold:#d9b47e;--blue:#69a6d9;}}
*{{box-sizing:border-box}} html{{scroll-behavior:smooth}} body{{margin:0;background:#0b1420;color:var(--ink);font-family:Georgia,"Times New Roman",serif}}
header{{background:linear-gradient(180deg,#0f1215,#20252a);color:#f5ead8;border-bottom:5px solid var(--red);padding:38px 24px 30px}}
.wrap{{width:min(94vw,2200px);margin:auto}} .kicker{{font:700 11px Arial,sans-serif;letter-spacing:.18em;text-transform:uppercase;color:#d6b47c}} h1{{font-size:clamp(38px,6vw,68px);font-weight:500;margin:8px 0}} .sub{{color:#d1c7ba;font-size:17px;line-height:1.5}}
nav{{position:sticky;top:0;z-index:20;background:rgba(18,21,24,.96);border-bottom:1px solid #4f4940;padding:8px 0}} nav .wrap{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}} nav a{{font:700 12px Arial,sans-serif;color:#f1e3cf;text-decoration:none;border:1px solid #5c544a;border-radius:5px;padding:8px 11px}} nav a:hover{{background:#2e3337}}
main{{width:min(94vw,2200px);margin:auto;background:var(--paper);min-height:100vh;padding:30px clamp(20px,3vw,52px) 70px}} .summary{{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px;margin-bottom:26px}} .stat{{background:var(--paper2);border-top:4px solid var(--red);padding:14px}} .stat span,.facts span,.loss-grid span{{display:block;color:var(--muted);font:700 10px Arial,sans-serif;text-transform:uppercase;letter-spacing:.07em}} .stat strong{{display:block;margin-top:5px;font-size:20px}} section{{margin-top:34px}} section>h2{{font-size:30px;font-weight:500;border-bottom:2px solid #456078;padding-bottom:8px}} .principles{{border-left:5px solid var(--gold);background:#26374a;padding:18px 20px;line-height:1.6}}
.war-card,.episode-card{{background:#19293a;border:1px solid #3a536b;border-left:5px solid var(--red);padding:19px 21px;margin:14px 0}} .episode-card{{border-left-color:var(--blue)}} .date{{font:700 11px Arial,sans-serif;color:#e7bc85;text-transform:uppercase;letter-spacing:.06em}} h3{{font-size:24px;font-weight:500;margin:5px 0 13px}} h4{{font-size:18px;margin:20px 0 8px}} .episode-head{{display:flex;gap:16px;justify-content:space-between;align-items:flex-start}} .badge{{font:700 10px Arial,sans-serif;text-transform:uppercase;letter-spacing:.06em;border:1px solid #aaa;border-radius:999px;padding:6px 9px;white-space:nowrap}} .badge.direct{{background:#223f36;border-color:#528c77}} .badge.correlated{{background:#363229;border-color:#947b55}}
.facts{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:12px}} .facts div,.loss-grid div{{background:#25374a;border:1px solid #3f5871;padding:11px}} .facts strong,.loss-grid strong{{display:block;margin-top:4px;line-height:1.35}} .loss-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:12px}} .loss-grid.one{{grid-template-columns:minmax(0,480px)}} .loss-grid strong{{font-size:24px}} .loss-grid small{{display:block;margin-top:3px;color:var(--muted)}} .evidence-note,.possible-losses,.muted{{color:var(--muted);font-size:13px;line-height:1.55;margin-top:10px}} .possible-losses{{border-left:3px solid #9e8157;padding-left:10px}}
.empty-state{{padding:20px;border:1px dashed #a89170;background:#233347;line-height:1.55}} .table-wrap{{overflow-x:auto}} table{{width:100%;border-collapse:collapse;font:14px Arial,sans-serif}} th,td{{padding:9px;border-bottom:1px solid #40566b;text-align:left}} th{{background:#2c4157;font-size:11px;text-transform:uppercase;letter-spacing:.05em}} footer{{margin-top:45px;padding-top:18px;border-top:1px solid #456078;color:var(--muted);font-size:12px;line-height:1.55}}
.investigator-tools{{display:flex;gap:12px;align-items:end;flex-wrap:wrap;padding:12px;background:#21354a;border:1px solid #3f5871}} .investigator-tools label{{display:flex;flex-direction:column;gap:5px;font:12px Arial,sans-serif}} .investigator-tools input,.investigator-tools button{{padding:9px;background:#0c1826;border:1px solid #6885a0;color:#fff;border-radius:4px}} .investigator-count{{font:12px Arial,sans-serif;color:#bdd1e4}} .battle-tools{{display:flex;flex-wrap:wrap;gap:12px;align-items:end;padding:13px;background:#21354a;margin:10px 0;border:1px solid var(--line);font:12px Arial,sans-serif}} .battle-tools label{{display:flex;flex-direction:column;gap:5px}} .battle-tools input,.battle-tools select{{background:#0c1826;border:1px solid #6885a0;border-radius:4px;padding:9px;color:#f2f6ff;min-width:165px}} .battle-shown{{color:#bdd1e4;padding-bottom:6px}} .audit-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}} .audit-grid div{{padding:10px;background:#233a50;border:1px solid #47617b}} .audit-grid span{{display:block;color:#bad0e3;text-transform:uppercase;font:10px Arial,sans-serif}} .audit-grid strong{{display:block;margin-top:5px}} .evidence-audit{{padding:12px 0}} .participant-evidence{{margin-top:10px;padding:10px;border:1px solid #456078}} .participant-evidence summary,.theatre-breakdown summary{{cursor:pointer;color:#b9dafa}} .theatre-breakdown{{border:1px solid #456078;padding:12px;margin:16px 0;background:#203247}} tr[hidden]{{display:none}} 
.aftermath{{border:1px solid #477087;background:#192f41;padding:12px 16px;margin:20px 0}} .aftermath-run{{background:#2c6382;border:1px solid #8cbedb;color:#fff;font:700 13px Arial,sans-serif;padding:10px 14px;border-radius:5px;cursor:pointer}} .aftermath-run:disabled{{opacity:.55;cursor:wait}} .aftermath-stats{{font:bold 15px Arial,sans-serif;color:#cbebd8}} .aftermath-result{{margin-top:10px}}
.war-card{{scroll-margin-top:72px;outline:none}} .war-card:target{{border-color:#89bade;box-shadow:0 0 0 2px #5c90bc}} #war-index{{scroll-margin-top:74px}} .war-index{{background:#17293b;border:1px solid #46617d;border-radius:7px;padding:14px;margin:18px 0 24px}} .war-index h3{{margin:0 0 5px}} .war-index-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:9px}} .war-index-card{{text-decoration:none;display:flex;align-items:flex-start;gap:11px;background:#22374d;border:1px solid #4e6b85;border-radius:6px;padding:12px;color:#f1f6fc;font:13px Arial,sans-serif;line-height:1.45}} .war-index-card:hover,.war-index-card:focus-visible,.war-step:hover,.war-step:focus-visible{{background:#315474;outline:2px solid #8cc2ec;outline-offset:2px}} .war-index-card span:nth-child(2){{flex:1;min-width:0}} .war-index-card strong,.war-index-card small,.war-step small{{display:block}} .war-index-card small,.war-step small{{margin-top:5px;color:#c6d6e7;font-weight:400}} .war-index-number{{font:700 15px Arial,sans-serif;color:#e9bd85}} .war-pager{{display:grid;grid-template-columns:1fr auto 1fr;gap:9px;align-items:stretch;margin:1px 0 20px;font:700 13px Arial,sans-serif}} .war-pager.bottom{{margin:24px 0 0}} .war-step,.war-index-return{{text-decoration:none;background:#233e55;color:#eef7ff;border:1px solid #6185a0;padding:10px 12px;border-radius:5px;min-width:0;line-height:1.4}} .war-index-return{{text-align:center;white-space:nowrap}} .war-step:last-child{{text-align:right}} .war-step.disabled{{opacity:.45;background:#172636;border-color:#415769}} .war-step small{{overflow-wrap:anywhere}} .war-chronicle{{border:1px solid #4b6880;background:#172c3e;padding:12px 15px;margin:18px 0}} .war-chronicle h4{{margin-top:3px}} .chronicle-milestones{{margin:10px 0;padding-left:25px;line-height:1.65}} .chronicle-milestones li{{padding:3px 0}} .chronicle-years,.chronicle-highlights,.battle-dossier,.wartime-tech{{margin:12px 0;padding:12px;background:#21374b;border:1px solid #496b86}} .chronicle-years summary,.chronicle-highlights summary,.battle-dossier summary,.wartime-tech summary{{cursor:pointer;color:#cae7fb;font:700 14px Arial,sans-serif}} .forensic-table{{border:1px solid #456078;background:#20374a;padding:12px;margin:11px 0}} .forensic-table summary{{cursor:pointer;font:700 14px Arial,sans-serif;color:#c8e5fa}} .forensic-table .table-wrap{{margin-top:10px}} .battle-reset,.theatre-filter{{border:1px solid #86acc6;border-radius:4px;background:#275676;color:white;font:700 12px Arial,sans-serif;padding:6px 8px;cursor:pointer}} .battle-dossier{{scroll-margin-top:75px}} .war-actions{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:15px 0}} .war-actions button{{background:#2c6382;border:1px solid #8cbedb;border-radius:5px;padding:9px 12px;color:#fff;font:700 12px Arial,sans-serif;cursor:pointer}} .war-actions button:hover{{background:#347fa6}} .war-copy-feedback{{color:#c9e5d4;font:12px Arial,sans-serif}}
@media(max-width:1200px){{.audit-grid{{grid-template-columns:repeat(2,1fr)}}.summary{{grid-template-columns:repeat(3,1fr)}}.facts{{grid-template-columns:repeat(2,1fr)}}}} @media(max-width:720px){{.war-pager{{grid-template-columns:1fr 1fr}} .war-index-return{{grid-column:1 / -1;grid-row:1}} .war-step{{font-size:12px}} .audit-grid{{grid-template-columns:1fr}}.summary,.facts,.loss-grid{{grid-template-columns:1fr}}.episode-head{{display:block}}.badge{{display:inline-block;margin-top:6px}}}}
@media print{{.war-pager,.war-actions,.war-index{{display:none}} nav{{display:none}} body{{background:white}} main{{width:100%;padding:15mm;background:white}} header{{background:white;color:black;border-bottom:2px solid #555}} .sub,.kicker{{color:#444}} .war-card,.episode-card{{break-inside:avoid}}}}
</style>
<script src="/static/historian-favicon.js?v=058" defer></script>
<script>
document.addEventListener('DOMContentLoaded', function () {{
  document.querySelectorAll('.war-card').forEach(function(card) {{
    const rows = Array.from(card.querySelectorAll('.battle-row'));
    const search = card.querySelector('.battle-search');
    const role = card.querySelector('.battle-role');
    const flag = card.querySelector('.battle-flag');
    const status = card.querySelector('.battle-shown');
    if (!search || !role || !flag || !status) return;
    function update() {{
      const q = search.value.toLocaleLowerCase().trim();
      let shown = 0;
      rows.forEach(function(row) {{
        const match = (!q || row.dataset.search.includes(q))
          && (role.value === 'all' || row.dataset.role === role.value)
          && (flag.value === 'all' || row.dataset.flag === flag.value);
        row.hidden = !match;
        if (match) shown++;
      }});
      status.textContent = shown + ' of ' + rows.length + ' battles shown';
    }}
    [search, role, flag].forEach(function(control) {{ control.addEventListener('input', update); }});
    card.querySelector('.battle-reset')?.addEventListener('click', function() {{
      search.value = ''; role.value = 'all'; flag.value = 'all'; update();
    }});
    card.querySelectorAll('.theatre-filter').forEach(function(button) {{
      button.addEventListener('click', function() {{
        const dossier = card.querySelector('.battle-dossier');
        if (dossier) dossier.open = true;
        search.value = button.dataset.location;
        role.value = 'all'; flag.value = 'all'; update();
        dossier?.scrollIntoView({{behavior:'smooth', block:'start'}});
      }});
    }});
    update();
  }});
  document.querySelectorAll('.aftermath-run:not(.military-run)').forEach(function(button) {{
    button.addEventListener('click', async function() {{
      const target = button.closest('.aftermath').querySelector('.aftermath-result');
      button.disabled = true;
      target.textContent = 'Comparing archived control evidence…';
      try {{
        const response = await fetch('/api/war-aftermath?war_id=' + encodeURIComponent(button.dataset.warId), {{cache:'no-store'}});
        const data = await response.json();
        if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Analysis failed');
        target.replaceChildren();
        const stats = document.createElement('p');
        stats.className = 'aftermath-stats';
        stats.textContent = data.before_date + ' → ' + data.after_date + ' · ' + data.player_gained + ' gains for this civilisation · ' + data.player_lost + ' losses · ' + data.changed_count + ' total controller changes';
        target.appendChild(stats);
        const summary = document.createElement('p');
        summary.className = 'evidence-note';
        summary.textContent = data.disclaimer;
        target.appendChild(summary);
        if (data.changes.length) {{
          const wrapper = document.createElement('div');
          wrapper.className = 'table-wrap';
          const table = document.createElement('table');
          const head = document.createElement('thead');
          const hrow = document.createElement('tr');
          ['System','Previous controller (ID)','Later controller (ID)','Same station fleet','War-party pair'].forEach(function(title) {{
            const th = document.createElement('th'); th.textContent = title; hrow.appendChild(th);
          }});
          head.appendChild(hrow); table.appendChild(head);
          const body = document.createElement('tbody');
          data.changes.forEach(function(item) {{
            const tr = document.createElement('tr');
            [item.system_name, String(item.previous_owner_id), String(item.later_owner_id), item.same_station_fleet ? 'Yes' : 'Not established', item.war_participant_pair ? 'Yes' : 'No'].forEach(function(value) {{
              const td = document.createElement('td'); td.textContent = value; tr.appendChild(td);
            }});
            body.appendChild(tr);
          }});
          table.appendChild(body); wrapper.appendChild(table); target.appendChild(wrapper);
        }} else {{
          const p = document.createElement('p'); p.textContent = 'No changes among systems with unique, comparable starbase controllers in both snapshots.'; target.appendChild(p);
        }}
      }} catch (err) {{ target.textContent = 'Unable to compare archives: ' + err.message; }}
      finally {{ button.disabled = false; }}
    }});
  }});
  document.querySelectorAll('.military-run').forEach(function(button) {{
    button.addEventListener('click', async function() {{
      const target = button.closest('.military-intel').querySelector('.military-result');
      button.disabled = true;
      target.textContent = 'Examining archived planetary and station evidence (first run may take a while)…';
      try {{
        const startResponse = await fetch('/api/war-intelligence/start?war_id=' + encodeURIComponent(button.dataset.warId), {{cache:'no-store'}});
        const started = await startResponse.json();
        if (!startResponse.ok) throw new Error(started.detail || 'Could not start investigation');
        let data;
        while (true) {{
          const statusResponse = await fetch('/api/war-intelligence/status?war_id=' + encodeURIComponent(button.dataset.warId), {{cache:'no-store'}});
          const progress = await statusResponse.json();
          if (!statusResponse.ok) throw new Error(progress.detail || 'Unable to read investigation progress');
          if (progress.status === 'failed') throw new Error(progress.error || 'Investigation failed');
          if (progress.status === 'done') {{ data = progress.result; break; }}
          target.textContent = 'Archive investigation: ' + (progress.processed || 0) + ' / ' + (progress.total || '?') +
              ' saves checked · ' + (progress.current_date || 'Preparing') +
              ' · cache hits ' + (progress.cache_hits || 0) + ' · v0.0.68 reused ' + (progress.legacy_reused || 0) + ' · raw reads ' + (progress.raw_reads || 0);
          await new Promise(resolve => setTimeout(resolve, 750));
        }}
        target.replaceChildren();
        function paragraph(message) {{ const p=document.createElement('p');p.className='evidence-note';p.textContent=message;target.appendChild(p); }}
        function grid(title, headers, records, cells) {{
          const details=document.createElement('details'); details.className='forensic-table';
          const summary=document.createElement('summary');summary.textContent=title+' ('+records.length+')';
          details.appendChild(summary); details.open = records.length <= 6;
          target.appendChild(details);
          if (!records.length) {{
            const p=document.createElement('p');p.className='evidence-note';
            p.textContent='No qualifying evidence found in the examined archives.';
            details.appendChild(p);return;
          }}
          const wrap=document.createElement('div');wrap.className='table-wrap';
          const table=document.createElement('table');const head=document.createElement('thead');const hr=document.createElement('tr');
          headers.forEach(function(label) {{ const th=document.createElement('th');th.textContent=label;hr.appendChild(th); }});
          head.appendChild(hr);table.appendChild(head);const body=document.createElement('tbody');
          records.forEach(function(rec) {{ const tr=document.createElement('tr');cells(rec).forEach(function(value) {{ const td=document.createElement('td');td.textContent=String(value ?? '—');tr.appendChild(td); }});body.appendChild(tr); }});
          table.appendChild(body);wrap.appendChild(table);details.appendChild(wrap);
        }}
        paragraph('Examined '+data.snapshots_examined+' archives: '+data.first_archive+' → '+data.last_archive+(data.partial_window?' (most recent 48 only; earlier evidence not examined)':''));
        paragraph(data.disclaimer);
        grid('Retained ground battle records', ['First seen', 'Planet', 'Native battle date', 'Tactical role', 'Raw losses (attacker / defender)', 'Flag'], data.ground_battles,
            b => [b.first_archive, b.planet_name, b.date || 'Undated in save', b.player_tactical_side, b.attacker_losses_raw+' / '+b.defender_losses_raw, b.attacker_victory_raw || 'Missing']);
        grid('Planetary controller changes', ['Planet', 'Observation interval', 'Owner ID', 'Controller before → after', 'Occupation'], data.planetary_controller_changes,
            b => [b.planet_name, b.before_date+' → '+b.after_date, b.owner_id, b.previous_controller_id+' → '+b.later_controller_id, b.occupation_observed?'Observed':'Not established']);
        grid('Opposing starbase combat markers', ['System', 'Starbase ID', 'Controller ID', 'Combat activity date', 'First archived'], data.enemy_starbase_activity,
            b => [b.system_name, b.starbase_id, b.controller_id, b.combat_activity_date, b.first_observed]);
        grid('Formal-battle exhaustion fields — NOT current war-wide totals',
            ['First archived', 'Battle date', 'Type', 'Tactical IDs (attack/defence)', 'Battle attacker exhaustion', 'Battle defender exhaustion'],
            data.battle_exhaustion_evidence || [],
            b => [b.first_archive, b.date || 'Undated', b.type, b.attackers.join(',')+' / '+b.defenders.join(','), b.attacker_exhaustion_raw ?? 'Missing', b.defender_exhaustion_raw ?? 'Missing']);
      }} catch(err) {{ target.textContent='Unable to investigate military archives: '+err.message; }}
      finally {{ button.disabled=false; }}
    }});
  }});
  function warBrief(card) {{
    const title = card.querySelector('h3')?.textContent?.trim() || 'Untitled war';
    const lines = ['STELLARIS HISTORIAN — WAR EVIDENCE BRIEF', title, 'War ID: ' + card.dataset.warId, ''];
    card.querySelectorAll('.facts > div').forEach(function(field) {{
      lines.push((field.querySelector('span')?.textContent || 'Field').trim() + ': ' +
                 (field.querySelector('strong')?.textContent || '').trim());
    }});
    const timeline = card.querySelector('.chronicle-milestones');
    if (timeline) {{
      lines.push('', 'EVIDENCE CHRONOLOGY');
      timeline.querySelectorAll('li').forEach(li => lines.push('- ' + li.textContent.trim()));
    }}
    const research = card.querySelector('.wartime-tech');
    if (research) {{
      lines.push('', 'RESEARCH EVIDENCE AND ARCHIVE COVERAGE');
      const coverage = research.querySelector('.research-coverage');
      if (coverage) lines.push(coverage.textContent.trim());
      research.querySelectorAll('tbody tr').forEach(function(row) {{
        lines.push('- ' + Array.from(row.querySelectorAll('td')).map(td => td.textContent.trim()).join(' · '));
      }});
    }}
    const audit = card.querySelector('.audit-grid');
    if (audit) {{
      lines.push('', 'RETAINED BATTLE RECORDS');
      audit.querySelectorAll('div').forEach(div => lines.push(
        (div.querySelector('span')?.textContent || '').trim() + ': ' +
        (div.querySelector('strong')?.textContent || '').trim()));
    }}
    lines.push('', 'EVIDENCE RULE: Formal battle outcome flags remain unverified. ' +
      'Loss totals are native battle records, not proof of specific ship destruction. ' +
      'War-ending windows are bounded by archived saves; exact peace terms and outcomes remain unverified unless decoded from native game evidence.');
    return lines.join('\\n');
  }}
  document.querySelectorAll('.war-card').forEach(function(card) {{
    const copy = card.querySelector('.copy-war-brief');
    const download = card.querySelector('.download-war-brief');
    const feedback = card.querySelector('.war-copy-feedback');
    copy?.addEventListener('click', async function() {{
      try {{ await navigator.clipboard.writeText(warBrief(card)); feedback.textContent = 'War evidence brief copied.'; }}
      catch(err) {{ feedback.textContent = 'Clipboard unavailable; use Save war brief instead.'; }}
    }});
    download?.addEventListener('click', function() {{
      const blob = new Blob([warBrief(card)], {{type:'text/plain;charset=utf-8'}});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a'); link.href = url;
      link.download = 'Stellaris_War_' + card.dataset.warId + '_Brief.txt';
      document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
      feedback.textContent = 'War evidence brief prepared.';
    }});
  }});
  // Shortcuts work only when no text field, button or other widget owns focus.
  document.addEventListener('keydown', function(event) {{
    if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey ||
        event.target.closest('input, select, textarea, button, [contenteditable="true"]')) return;
    if (event.key !== '[' && event.key !== ']') return;
    const wars = Array.from(document.querySelectorAll('.war-card'));
    if (!wars.length) return;
    let current = wars.findIndex(w => '#' + w.id === location.hash);
    if (current < 0) {{
      // On a long page, choose the last war whose heading is above the sticky nav.
      current = 0;
      wars.forEach((w, i) => {{ if (w.getBoundingClientRect().top <= 135) current = i; }});
    }}
    const to = current + (event.key === ']' ? 1 : -1);
    if (to >= 0 && to < wars.length) {{ event.preventDefault(); location.hash = wars[to].id; }}
  }});
  const probeSearch = document.querySelector('.investigator-search');
  if (probeSearch) {{
    const probeRows = Array.from(document.querySelectorAll('.probe-row'));
    const probeCount = document.querySelector('.investigator-count');
    function filterProbes() {{
      const term = probeSearch.value.trim().toLocaleLowerCase();
      let visible = 0;
      probeRows.forEach(function(row) {{
        const show = !term || row.dataset.search.includes(term);
        row.hidden = !show;
        if (show) visible++;
      }});
      probeCount.textContent = visible + ' of ' + probeRows.length + ' telemetry episodes';
    }}
    probeSearch.addEventListener('input', filterProbes);
    document.querySelector('.investigator-clear').addEventListener('click', function() {{probeSearch.value='';filterProbes();}});
    filterProbes();
  }}
}});
</script>

<link rel="stylesheet" href="/static/historian-theme.css?v=087">
<script src="/static/historian-theme.js?v=087"></script>
</head>
<body>
<header><div class="wrap"><div class="kicker">Stellaris Historian · Evidence-led military record</div><h1>War Journal</h1><div class="sub">{_e(campaign['empire_name'])} · archive through {_e(campaign['latest_game_date'])}</div></div></header>
<nav><div class="wrap"><a href="#overview">Overview</a><a href="#formal-wars">Formal Wars</a><a href="#research-audit">Research Audit</a><a href="#combat-episodes">Combat Episodes</a><a href="#investigation">Combat Investigation</a><a href="/journal">Historical Journal</a><a href="/campaign">Campaign Dashboard</a></div></nav>
<main>
<section id="overview">
  <h2>Military Record Overview</h2>
  <div class="summary">
    <div class="stat"><span>Formal wars</span><strong>{len(formal_wars)}</strong></div>
    <div class="stat"><span>Formal battles</span><strong>{formal_battle_count}</strong></div>
    <div class="stat"><span>Results under review</span><strong>{unverified_battle_count}</strong></div>
    <div class="stat"><span>Combat episodes</span><strong>{len(episodes)}</strong></div>
    <div class="stat"><span>Direct-telemetry episodes</span><strong>{direct_episode_count}</strong></div>
    <div class="stat"><span>Recorded fleets</span><strong>{len(fleets)}</strong></div>
    <div class="stat"><span>Recorded commanders</span><strong>{len(commanders)}</strong></div>
  </div>
  <div class="principles"><strong>Save-only history:</strong> war titles, names, dates, endings and results originate exclusively from decoded save records or their processed caches. External screenshot notes and manually entered annotations are not consulted. Unknown outcomes and names remain unknown.</div>
  <div class="principles"><strong>Evidence rule:</strong> this journal separates formal wars from reconstructed combat episodes. A combat marker, disappearing ship or loss counter does not by itself prove a battle result, a war, or an individual ship's destruction. Formal battle result interpretation remains under review: the raw tactical attacker_victory field is retained and shown without presenting unverified player victories or defeats.</div>
  <div class="facts">
    <div><span>Systems appearing in combat evidence</span><strong>{_e(_join(systems))}</strong></div>
    <div><span>Named opposing forces</span><strong>{_e(_join(enemies))}</strong></div>
    <div><span>Recorded fleets</span><strong>{_e(_join(fleets))}</strong></div>
    <div><span>Recorded commanders</span><strong>{_e(_join(commanders))}</strong></div>
  </div>
</section>
<section id="formal-wars"><h2>Formal Wars</h2><p class="evidence-note">Select a war below or use Previous / Next War inside a report. Keyboard: [ previous war, ] next war (outside form controls). Shareable links use stable war IDs.</p>{war_index_html}{war_html}</section>
{research_audit_html}
<section id="combat-episodes"><h2>Combat Episodes</h2>{episode_html}</section>
<section id="investigation"><h2>Combat Investigation</h2><p class="evidence-note">Compare independently retained direct fleet-combat telemetry against nearby formal battle records. Player fleet IDs come from the native telemetry, independently of ambiguous fleet-name labels. No outcome is inferred.</p>{investigation_html}</section>
<footer>
  <strong>War Journal evidence audit — v0.0.71.1.</strong> This view is derived from the existing reviewed combat cache and shared presentation layer; it does not reparse Ironman saves. War-linked commissioning, refits, technology, diplomatic consequences and aftermath are deliberately not attributed to a specific conflict yet unless later evidence rules can make that linkage safely.
</footer>
</main>
</body>
</html>"""

    target = war_journal_path(db, campaign_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="war_journal_", suffix=".html", dir=str(target.parent))
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
