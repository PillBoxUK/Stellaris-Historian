from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from html import escape
import json
from pathlib import Path
import os
import re
import tempfile

from .db import Database
from .historical_events import HistoricalEvent
from .presentation_history import build_presentation_history
from .story_text import game_description
from .research_history import read_observations, research_events
from .founding_chapter import extract_founding_profile, founding_chapter
from .native_milestones import capture_native_milestones, milestone_events
from .narrative_clean import clean_game_description
from .civic_frontier import read_observations as read_civic_frontier, timeline_events as civic_frontier_events
from .annual_census import annual_censuses, census_prose
from .verified_milestones import service_milestones, classify_milestone
from .publication_names import usable_name, ship_subject
from .annals_editorial import reading_importance, date_label, month_groups, period_extract
from functools import lru_cache


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
    evidence: str = ""
    date_kind: str = "first_observed"
    source: str = ""
    war_id: int | None = None


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


from .core.name_display import clean_stellaris_name as _clean_stellaris_name


def _clean_legacy_names(events: list[TimelineEvent], leaders: dict[int, object]) -> list[TimelineEvent]:
    """Presentation-only repair for previously indexed names; no data rewrite."""
    from dataclasses import replace
    replacements = []
    for row in leaders.values():
        try:
            raw = str(row["name"] or "")
            gender = str(row["gender"] or "")
        except (KeyError, IndexError, TypeError):
            continue
        clean = _clean_stellaris_name(raw, gender)
        if raw and raw != clean:
            replacements.append((raw, clean))
    replacements.sort(key=lambda pair: -len(pair[0]))
    result = []
    for event in events:
        title, body = event.title, event.body
        for raw, clean in replacements:
            title = title.replace(raw, clean)
            body = body.replace(raw, clean)
        # Fallback for name strings no longer present in the leader registry.
        title = _clean_embedded_gender_grammar(title)
        body = _clean_embedded_gender_grammar(body)
        result.append(replace(event, title=title, body=body))
    return result


def _clean_embedded_gender_grammar(text: str) -> str:
    """As a fallback, publish the unambiguous forename, never literal grammar."""
    return re.sub(
        r"([\w'’-]+)&!masc\s+\$1\$\s+[^,.;:()]+?\|\|\|masc:\$1\$\s+[^,.;:()\s]+",
        lambda m: m.group(1), str(text), flags=re.I)


def _deduplicate_semantic_events(events: list[TimelineEvent]) -> list[TimelineEvent]:
    """Collapse duplicate project and noncombat ship arrivals on the same date.

    An identical subject independently reported by two historical domains is
    one event, not two chapters. Different dates remain distinct.
    """
    from dataclasses import replace
    merged = {}
    for ev in events:
        title = ev.title.strip()
        simplified = re.sub(r":\s*research project recorded$", "", title, flags=re.I)
        kind = ""
        if ev.category == "Story":
            kind = "story:" + simplified.casefold()
        m = re.fullmatch(r"(.+?) (?:commissioned|enters service|enters the naval rolls)$", title, re.I)
        if m and ev.category in ("Navy", "Exploration") and usable_name(m.group(1)) and not m.group(1).casefold().startswith('a '):
            kind = "ship:" + m.group(1).casefold()
        # Unknown names can legitimately describe *different* commissioned
        # vessels on the same date. Do not collapse them merely because both
        # are displayed as "A science ship enters service".
        anonymous = ev.category in ('Navy', 'Exploration') and re.match(r'^A (?:science|construction|colony) ship enters service$', ev.title)
        key = ((ev.game_date, ev.category, ev.title, ev.evidence) if anonymous else
               (ev.game_date, kind) if kind else (ev.game_date, ev.category, ev.title))
        previous = merged.get(key)
        if previous is None:
            merged[key] = ev
            continue
        # Prefer the information-rich event with meaningful source context.
        score = lambda item: (bool(item.body and len(item.body) > 75), len(item.body), item.importance)
        if score(ev) > score(previous):
            merged[key] = replace(ev, evidence=ev.evidence + " Related source: " + previous.evidence)
        else:
            merged[key] = replace(previous, evidence=previous.evidence + " Related source: " + ev.evidence)
    return list(merged.values())


def _clean_public_text(value: str | None) -> str:
    """Keep polished chronology free of game/debug voice."""
    text = " ".join(str(value or "").split())
    text = re.sub(r"\bStellaris records\b", "The surviving record identifies", text, flags=re.I)
    text = re.sub(r"\bplayer fleets?\b", "recorded fleets", text, flags=re.I)
    text = re.sub(r"\bplayer loss(?:es)?\b", "recorded losses", text, flags=re.I)
    text = text.replace("planet Station", "an unresolved station")
    return text


def _chronicle_voice(text: str, as_of: str = "") -> str:
    """Polished timeline voice without game/player/auditor narration.

    Date bounds remain cautious: a first archived sighting isn't an exact
    founding, disappearance, victory, or discovery date.
    """
    value = " ".join(str(text or "").split())
    # Retain only established service details; discard speculative shipyard attribution.
    value = re.sub(r"[^.]*\bprobable build location\.", "", value, flags=re.I)
    value = value.replace("TRANS_FLEET_NAME", "an unnamed transport formation")
    value = re.sub(r"\bStellaris records\b", "", value, flags=re.I)
    value = re.sub(r"The (?:colony|construction|science) ship (.+?) entered service on (\d{4}\.\d{2}\.\d{2}), assigned to \1\.",
                   lambda m: f"{m[1]} entered service on {m[2]}.", value, flags=re.I)
    value = re.sub(r"\bThe record identifies (.+?) as no longer present in the archived leader record by (\d{4}\.\d{2}\.\d{2})\.",
                   lambda m: f"{m[1]} was no longer among the serving officials by {m[2]}.", value, flags=re.I)
    value = re.sub(r"\b(.+?) first enters the archaeological record at (.+?)\.",
                   lambda m: f"{m[1]} was known at {m[2]} by {as_of}." if as_of else m[0], value, flags=re.I)
    value = re.sub(r"\bThe record identifies\s+(.+?)\s+as entering service as a ([^,]+?) on (\d{4}\.\d{2}\.\d{2})\.",
                   lambda m: f"{m[1]} entered service as a {m[2]} on {m[3]}.", value, flags=re.I)
    value = re.sub(r"\bThe record identifies the colony of (.+?) as founded on (\d{4}\.\d{2}\.\d{2})\.",
                   lambda m: f"A founding date of {m[2]} is associated with the colony of {m[1]}; sovereignty at founding is not established.", value, flags=re.I)
    value = re.sub(r"\bThe record identifies\s+", "", value, flags=re.I)
    value = re.sub(r"\bThe first surviving archived state containing (?:this|the) (?:leader|colony) is dated\s+(\d{4}\.\d{2}\.\d{2})\.",
                   lambda m: f"Present by {m[1]}.", value, flags=re.I)
    value = re.sub(r"\bThe learned register first records (.+?) by this preserved date\.",
                   lambda m: f"{m[1]} was known by this date.", value, flags=re.I)
    value = re.sub(r"\bFormal battle results remain under review; no player victory or defeat is established\.",
                   "Outcome unconfirmed.", value, flags=re.I)
    value = re.sub(r"\bno player victory or defeat is established\b", "the outcome is unknown", value, flags=re.I)
    value = re.sub(r"\bplayer\b", "imperial", value, flags=re.I)
    value = re.sub(r"\b(game|Historian)\b", "", value, flags=re.I)
    value = re.sub(r"\bThe surviving combat record spans\b", "Combat activity is dated", value, flags=re.I)
    value = re.sub(r"\bThe surviving record\b", "The chronicle", value, flags=re.I)
    value = re.sub(r"\bThe latest surviving roll records\b", "At the present frontier of the chronicle stand", value, flags=re.I)
    value = re.sub(r"\bThe surviving retained fleet tallies record\b", "Fleet-loss tallies show", value, flags=re.I)
    value = re.sub(r"\bRecorded formations:\s*", "Forces: ", value, flags=re.I)
    value = re.sub(r"\bThe archive does not establish why\.", "The cause remains unknown.", value, flags=re.I)
    value = re.sub(r"\bthe archive\b", "the chronicles", value, flags=re.I)
    value = value.replace("The chronicle reaches the present day", "The chronicle continues")
    value = value.replace("Combat episode preserved", "Combat activity recorded")
    return " ".join(value.split())


def _long_date(value: str) -> str:
    """Readable dates in the native Stellaris calendar, without real-world conversion."""
    parts = str(value).split('.')
    if len(parts) != 3 or not all(bit.isdigit() for bit in parts):
        return str(value)
    year, month, day = (int(x) for x in parts)
    names = ('January', 'February', 'March', 'April', 'May', 'June',
             'July', 'August', 'September', 'October', 'November', 'December')
    if not 1 <= month <= 12 or not 1 <= day <= 31:
        return str(value)
    return f'{day} {names[month-1]} {year}'


def _good_name(value: str) -> bool:
    x = str(value or '').strip()
    return usable_name(x) and not x.casefold().startswith(('unnamed', 'unknown', 'none', 'null', 'ship ', 'fleet ', 'leader ')) and not re.search(r'^(?:TRANS_|NAME_|SHIP_|FLEET_|LEADER_)[A-Z_]+$', x)


@lru_cache(maxsize=24)
def _cached_founding_profile(start_path: str, source_path: str, digest: str) -> dict:
    return extract_founding_profile(Path(start_path), Path(source_path))


def _founding_prologue(db: Database, campaign_id: int) -> tuple[str, str] | None:
    try:
        if not hasattr(db,'all_snapshots'):return None
        rows=list(db.all_snapshots(campaign_id))
        if not rows:return None
        start=rows[0]
        path=Path(str(start['archive_path']))
        campaign=db.campaign(campaign_id)
        if not path.is_file():path=Path(campaign['archive_dir'])/str(start['archive_filename'])
        if not path.is_file():return None
        record=_cached_founding_profile(str(path),str(campaign['source_save']),str(start['sha256']))
        story=founding_chapter(record)
        return story,('Founding species and government read directly from the opening archived save; '
                      'origin background, if available, comes from installed Stellaris localisation. '
                      'Trait descriptions are interpretive background, not individually dated events. '
                      'Founding itself is not dated by the campaign opening.')
    except (OSError,ValueError,KeyError,IndexError,TypeError):
        return None


def _native_milestones(db: Database, campaign_id: int, empire: str) -> list[TimelineEvent]:
    try:
        if not hasattr(db,'all_snapshots'):return []
        rows=list(db.all_snapshots(campaign_id))
        if not rows:return []
        last=next((r for r in reversed(rows) if int(r['processed'])), None)
        if last is None:return []
        campaign=db.campaign(campaign_id)
        save=Path(str(last['archive_path']))
        if not save.is_file():save=Path(str(campaign['archive_dir']))/str(last['archive_filename'])
        if not save.is_file():return []
        data=capture_native_milestones(Path(str(campaign['archive_dir'])),save,str(last['sha256']))
        return [TimelineEvent(r['date'],r['title'],r['body'],r['category'],85,
                              evidence=r['evidence'],date_kind='exact_native_timeline',
                              source='player_country.timeline_events')
                for r in milestone_events(data,empire)]
    except (OSError,ValueError,KeyError,IndexError,TypeError):
        return []


def _opening_narrative(db: Database, campaign_id: int, empire: str, date: str) -> str:
    """Historian's opening chapter based strictly on the original government row."""
    opening = next((r for r in db.history_entries(campaign_id) if r['entry_type'] == 'founding'), None)
    if opening is None:
        return f'The earliest surviving history of {empire} dates to {_long_date(date)}.'
    def label(v):
        return re.sub(r'^(?:gov|auth|ethic|civic|origin)[_ ]+', '', str(v or '').strip(), flags=re.I).replace('_',' ').strip().title()
    govt = label(opening['government_type'])
    authority = label(opening['authority'])
    ethics = [label(v) for v in str(opening['ethics'] or '').split(',') if v.strip()]
    civics = [label(v) for v in str(opening['civics'] or '').split(',') if v.strip()]
    origin = label(opening['origin'])
    if empire.casefold() == 'commonwealth of man' and 'military' in govt.casefold():
        clauses = [f'The surviving history of the Commonwealth of Man begins on {_long_date(date)}. '
                   'Humanity’s distant colony had grown into an independent military state, governed through a powerful central authority.']
        if 'militarist' in ' '.join(ethics).casefold():
            clauses.append('Military service and armed strength lay at the heart of its political identity.')
        if 'xenophobe' in ' '.join(ethics).casefold():
            clauses.append('Its outlook on alien civilisations was fiercely guarded, with human interests placed first.')
        if any('nationalistic zeal' in c.casefold() for c in civics):
            clauses.append('Nationalistic zeal reinforced a powerful sense of collective purpose.')
        if any('distinguished admiralty' in c.casefold() for c in civics):
            clauses.append('A distinguished admiralty stood at the head of its naval tradition.')
        if 'lost colony' in origin.casefold():
            clauses.append('The legacy of a lost colony shaped its independent identity among the stars.')
        return ' '.join(clauses)
    if 'machine' in govt.casefold() or 'machine' in authority.casefold():
        clauses = [f'The history of {empire} opens on {_long_date(date)} as a machine civilisation, '
                   'its individual systems linked through a shared intelligence.']
        if 'gestalt' in ' '.join(ethics).casefold():
            clauses.append('Its decisions flowed through a collective consciousness rather than a conventional political electorate.')
        if 'built to last' in ' '.join(civics).casefold():
            clauses.append('Its design placed a premium on endurance and continuity.')
        if 'chosen' in ' '.join(civics).casefold():
            clauses.append('The idea of a special purpose lay at the centre of its identity.')
        if 'treasure' in origin.casefold():
            clauses.append('The pursuit of relics and lost discoveries shaped its earliest ambitions.')
        return ' '.join(clauses)
    if 'gestalt' in ' '.join(ethics).casefold():
        return (f'By {_long_date(date)}, {empire} was guided by a shared, biological consciousness. '
                'Its many members took part in a single collective purpose, unlike independent political societies.')
    clauses=[f'On {_long_date(date)}, the earliest surviving account of {empire} opens.']
    if govt:
        clauses.append(f'Its government took the form of a {govt.lower()}.')
    elif authority:
        clauses.append(f'Authority was {authority.lower()}.')
    if ethics:
        clauses.append(f'Its political outlook reflected {_join_words(ethics)}.')
    if civics:
        clauses.append(f'{_join_words(civics)} shaped its institutions.')
    if origin:
        clauses.append(f'Its origins were bound to {origin.lower()}.')
    return ' '.join(clauses)


def _story_prose(event: HistoricalEvent, empire: str = "") -> TimelineEvent:
    """Never substitute a named project with the meaningless 'underway'."""
    attrs=_attrs(event)
    key=attrs.get('project_key') or attrs.get('situation_key') or attrs.get('site_type')
    description,source=game_description(key)
    title=event.title.strip()
    # Dynamic scripted targets are meaningful only with their scope resolved.
    # Don't print raw '[Target.GetName]' or invent a planet when the save
    # didn't retain that target.
    title=re.sub(r'\s+(?:on|at|near)\s+\[(?:Target|This|Root|From|Prev)[^]]+\]', '', title, flags=re.I)
    title=re.sub(r'\[(?:Target|Get|Root|This)[^]]+\]', '', title, flags=re.I).strip()
    title=re.sub(r'^(The )\1', r'\1', title, flags=re.I)
    where=attrs.get('locations') or attrs.get('location') or ''
    people=attrs.get('scientists') or ''
    place=f' near {where}' if where and 'unresolved' not in where.lower() else ''
    if event.event_type=='archaeology_site_observed':
        body=f'{title} drew the attention of scientific expeditions{place}.'
        cat='Exploration'
    elif event.event_type=='situation_observed':
        body=f'By {_long_date(event.game_date)}, {title} had become an active concern for the empire.'
        cat='Story'
    else:
        body=f'By {_long_date(event.game_date)}, {title} was under investigation{place}.'
        cat='Story'
    if people:
        body += f' Scientists associated with the inquiry included {people}.'
    explanation=clean_game_description(description,empire)
    if explanation:
        body += ' ' + explanation
    evidence=(f'{event.source} · {event.event_type} · {event.date_kind}. '
              f'Underlying identifier: {key or "unavailable"}. '
              f'First preserved observation: {event.game_date}. '
              'Narrative premise from installed game text describes the type of project, not the chosen option or campaign outcome. '
              f'Associated scientists: {people or "not identified"}. ' + source + '. Original observation: '+event.summary)
    if not explanation:
        evidence += ' Full script description has not been located. No plot, decision or outcome has been invented.'
    return TimelineEvent(event.game_date,title,body,cat,event.importance,
                         evidence=evidence,date_kind=event.date_kind,source=event.source)


def _realm_name(empire: str) -> str:
    """A readable state name, without assuming that every campaign is human."""
    if empire.casefold() == 'commonwealth of man':
        return 'the Commonwealth'
    return empire if empire.casefold().startswith('the ') else 'the ' + empire


def _leader_prose(event: HistoricalEvent, empire: str, states: list[tuple[str,str,str]]) -> list[TimelineEvent]:
    """Write independent history entries for service and later observed appointments.

    The exact service date may come from a native field, while assignment is a
    different observation (often the next quarterly archive). Never backdate it.
    """
    title, raw, date = event.title, event.summary, event.game_date
    lid = _leader_id(event)
    evidence = (f'{event.source} · {event.event_type} · {event.date_kind} · {event.confidence}. '
                f'Source description: {raw}')
    name = re.sub(r'\s+(?:Entered Service|Entered the Record|Recorded Dead|Died|Became Ruler|Left Rulership|Left the Surviving Record|Left the Active Leader Record|Left The chronicle)$', '', title, flags=re.I).strip()
    out=[]
    realm = _realm_name(empire)
    if event.event_type == 'leader_entered_service':
        rank = re.search(r'entering service as a[n]?\s+([\w -]+?)\s+on\s+\d{4}\.\d{2}\.\d{2}', raw, re.I)
        klass=(rank.group(1).strip().lower() if rank else 'official')
        known=[row for row in states if row[0] <= date]
        regime=' '.join(known[-1][1:]) if known else ''
        if klass in ('scientist', 'researcher'):
            text=f'{name} entered {realm}’s scientific service.'
        elif klass in ('commander','admiral','general'):
            text=(f'{name} joined {realm}’s military command.' if 'militarist' in regime or 'military' in regime
                  else f'{name} began service as a commander in {realm}.')
        elif klass in ('envoy',):
            text=f'{name} entered {realm}’s diplomatic service.'
        else:
            text=f'{name} entered public service in {realm}.'
        out.append(TimelineEvent(date, f'{name} enters service', text, 'People',event.importance,lid,evidence,'exact_save_field',event.source))
        # First retained assignment is NOT necessarily simultaneous with recruitment.
        first = re.search(r'first surviving archived state containing this leader is dated\s+(\d{4}\.\d{2}\.\d{2})', raw, re.I)
        seen=first.group(1) if first else None
        if seen and _date_key(seen) >= _date_key(date):
            after = raw.split(seen,1)[-1]
            fleet = re.search(rf'By {re.escape(seen)},\s*{re.escape(name)}\s+(?:was recorded in command of|took command of)\s+([^.]*)\.',after,re.I)
            ship = re.search(rf'By {re.escape(seen)},\s*{re.escape(name)}\s+was assigned to (?:the )?science ship\s+([^.]*)\.',after,re.I)
            person = re.search(rf'By {re.escape(seen)},\s*{re.escape(name)}(?:\'s recorded assignment was| was assigned to)\s+([^.]*)\.',after,re.I)
            council = re.search(rf'By {re.escape(seen)},\s*{re.escape(name)}\s+held the council role\s+([^.]*)\.',after,re.I)
            ruler = re.search(rf'By {re.escape(seen)},\s*{re.escape(name)}\s+was also recorded as the ruler',after,re.I)
            if fleet and _good_name(fleet.group(1)):
                dest=fleet.group(1).strip()
                assignment=(f'{name} commands {dest}',f'By this date, {name} held command of {dest}.','Command')
            elif ship and _good_name(ship.group(1)):
                dest=ship.group(1).strip()
                assignment=(f'{name} aboard {dest}',f'{name} began serving aboard the science ship {dest} no later than this date.','Exploration')
            elif council and _good_name(council.group(1)):
                dest=council.group(1).strip()
                assignment=(f'{name} holds the office of {dest}',f'{name} held the council position of {dest}.','Politics')
            elif ruler:
                assignment=(f'{name} leads {empire}',f'By this date, {name} held power as ruler of {realm}.','Politics')
            elif person and _good_name(person.group(1)):
                dest=person.group(1).strip()
                assignment=(f'{name} assigned to {dest}',f'{name} served in the {dest} assignment.','People')
            else:
                assignment=None
            if assignment:
                a_title,a_body,a_cat=assignment
                out.append(TimelineEvent(seen,a_title,a_body,a_cat,event.importance-2,lid,
                    evidence+f' First retained assignment observation {seen}; actual appointment date unestablished.',
                    'first_observed',event.source))
        return out
    if event.event_type in ('leader_missing_unconfirmed','leader_tombstone_unconfirmed'):
        return [TimelineEvent(date,f'{name} disappears from the service rolls',
                 f'{name} was no longer listed among {realm}’s active leaders. Their later fate is unknown.',
                 'People',event.importance,lid,evidence,'first_observed',event.source)]
    if event.event_type == 'leader_death_recorded':
        attrs=_attrs(event); age=attrs.get('recorded_age'); years=attrs.get('recorded_service'); reason=attrs.get('death_reason','')
        body=f'{name} died'
        if age and age.isdigit():body+=f' aged {age}'
        if years and re.search(r'\d', years):body+=f', after {years} years of service' if years.isdigit() else f', after {years} of service'
        body+='.'
        if reason and not re.search(r'^[A-Z_0-9]+$', reason):body+=f' {reason.rstrip(".")}.'
        return [TimelineEvent(date,f'{name} dies',body,'People',event.importance,lid,evidence,event.date_kind,event.source)]
    if event.event_type == 'leader_became_ruler':
        return [TimelineEvent(date,f'{name} assumes the leadership', f'By this date, {name} ruled {realm}.',
            'Politics',event.importance,lid,evidence,'first_observed',event.source)]
    if event.event_type == 'leader_assignment_changed':
        match=re.match(r'(.+?) Took Command of (.+)$',title,re.I)
        if match:
            name,dest=match.groups()
            return [TimelineEvent(date,f'{name} takes command of {dest}',f'{name} held command of {dest} by this date.',
                'Command',event.importance,lid,evidence,'first_observed',event.source)]
    if event.event_type == 'leader_left_rulership':
        return [TimelineEvent(date,f'{name} leaves the leadership',f'{name} no longer occupied the office of ruler by this date.',
            'Politics',event.importance,lid,evidence,'first_observed',event.source)]
    return [TimelineEvent(date,_chronicle_voice(title,date),_chronicle_voice(raw,date), 'People',
            event.importance,lid,evidence,event.date_kind,event.source)]


def _expansion_prose(event: HistoricalEvent, empire_name: str = 'Commonwealth of Man') -> TimelineEvent:
    raw=event.summary
    evidence=f'{event.source} · {event.event_type} · {event.date_kind}. Source: {raw}'
    founding=re.search(r'colony of (.+?) in the (.+?) system as founded on (\d{4}\.\d{2}\.\d{2})',raw,re.I)
    first=re.search(r'(.+?) in the (.+?) system first appears among the empire',raw,re.I)
    if founding:
        world,system,date=founding.groups()
        return TimelineEvent(event.game_date,f'{world} founded',
            f'A new settlement took shape on {world}, in the {system} system.',
            'Expansion',event.importance,evidence=evidence+' A native founding date does not independently prove that the current empire was the original founder.',
            date_kind=event.date_kind,source=event.source)
    if first:
        world,system=first.groups();world=world.split('of ')[-1]
        return TimelineEvent(event.game_date,f'{world} enters imperial territory',
            f'{world}, in the {system} system, had come under the authority of {_realm_name(empire_name)} by this date.',
            'Expansion',event.importance,evidence=evidence+' Exact transfer date and cause not necessarily preserved.',
            date_kind='first_observed',source=event.source)
    return TimelineEvent(event.game_date,_chronicle_voice(event.title,event.game_date),
        _narrative_fallback(raw,date=event.game_date,category='Expansion',empire_name=empire_name),'Expansion',event.importance,
        evidence=evidence,date_kind=event.date_kind,source=event.source)


def _aux_ship_prose(event: HistoricalEvent, empire: str) -> TimelineEvent:
    m=re.match(r'(Science|Construction|Colony) Ship (.+?) Commissioned$',event.title,re.I)
    if m:
        vessel,name=m.groups()
        found_yard = re.search(r', at ([^,.]+? Starbase),', event.summary, re.I)
        yard_context = (f' Early construction evidence associates the vessel with {found_yard.group(1)}, '
                        'but does not establish that it was built there.' if found_yard else '')
        heading, subject = ship_subject(name, vessel)
        return TimelineEvent(event.game_date,heading,
          (f'{subject[0].upper() + subject[1:]} entered service with {_realm_name(empire)}. ' +
           ("As a construction vessel, it joined the ships responsible for establishing stations and expanding the empire's infrastructure." if vessel.lower()=='construction' else
            "As a science vessel, it strengthened the expeditions charting and investigating distant star systems." if vessel.lower()=='science' else
            "As a colony ship, it was commissioned for the difficult work of carrying settlers to new worlds.")
           + yard_context),'Exploration',event.importance,
          evidence=f'{event.source} · {event.event_type} · {event.date_kind}. Original: {event.summary} '
                   'Fleet and shipyard statements in the original record are not promoted into commissioning-day facts.',
          date_kind=event.date_kind,source=event.source)
    return TimelineEvent(event.game_date,_chronicle_voice(event.title,event.game_date),
        _narrative_fallback(event.summary,date=event.game_date,category='Military',empire_name=empire),'Military',event.importance,
        evidence=f'{event.source} · {event.event_type} · {event.date_kind}: {event.summary}',
        date_kind=event.date_kind,source=event.source)


def _narrative_fallback(text: str, *, date: str, category: str, empire_name: str = "") -> str:
    """Last-resort neutral clean-up for domain statements we cannot parse semantically."""
    value=_chronicle_voice(text,date)
    value=re.sub(r'\bPresent by \d{4}\.\d{2}\.\d{2}\.', '', value, flags=re.I)
    value=re.sub(r'\bThe record identifies\b', '', value, flags=re.I)
    value=re.sub(r'\bThe chronicle\b', _realm_name(empire_name) if empire_name else 'the realm', value, flags=re.I)
    value=re.sub(r'\bOutcome unconfirmed\.', '', value, flags=re.I)
    value=re.sub(r'\bFormal battle results remain under review[^.]*\.', '', value, flags=re.I)
    value=re.sub(r'\b(?:Historian|Stellaris|player)\b', '', value, flags=re.I)
    value=re.sub(r'\bBy (\d{4}\.\d{2}\.\d{2}),\s*', 'By that date, ', value)
    value=re.sub(r'\bThe learned register first records\b', (f'Scholars of {empire_name} first documented' if empire_name else 'Scholars first documented'), value, flags=re.I)
    return ' '.join(value.split())


def _war_spans(presentation, empire_name: str) -> list[dict[str, str | int | bool]]:
    """Only native war dates and observed save bounds; no outside annotations."""
    from .war_journal import _aggregate_formal_wars, _war_display_title

    names: dict[int, str] = {}
    for snapshot in presentation.combat_snapshots:
        for rel in snapshot.relation_kill_counters.values():
            if rel.other_country_name and not re.fullmatch(r"Country\s+\d+", rel.other_country_name, re.I):
                names[rel.other_country_id] = rel.other_country_name
        for stat in snapshot.fleet_combat_stats.values():
            for enemy in stat.enemy_fleets:
                if enemy.country_id is not None and enemy.country_name and not re.fullmatch(r"Country\s+\d+", enemy.country_name, re.I):
                    names[enemy.country_id] = enemy.country_name
    result = []
    for war in _aggregate_formal_wars(presentation):
        title, _origin = _war_display_title(war, empire_name, names)
        start = war.start_date or war.first_observed
        if _date_key(start)[0] == 999999:
            continue
        last = war.last_observed
        if _date_key(last) < _date_key(start):
            last = start
        end_desc = (
            f"Last observed {last}; no longer present by {war.first_absent_after_last}. Exact ending unknown."
            if war.first_absent_after_last else f"Still recorded on {last}; outcome not established."
        )
        result.append({"id": war.war_id, "title": title, "start": start,
                       "last": last, "first_observed": war.first_observed,
                       "first_absent": war.first_absent_after_last or "",
                       "details": end_desc, "side": war.player_side,
                       "goal": war.attacker_war_goal or "Unknown",
                       "attacker_ids":list(war.attacker_country_ids),
                       "defender_ids":list(war.defender_country_ids)})
    return result


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
    """Battle narrative anchored to recorded event span, not simulated victory."""
    attrs=_attrs(event)
    systems=[x for x in _csv(attrs.get('systems')) if _good_name(x)]
    enemies=[x for x in _csv(attrs.get('opposing_countries')) if _good_name(x)]
    fleets=[x for x in _csv(attrs.get('player_fleets')) if _good_name(x)]
    commanders=[x for x in _csv(attrs.get('commanders')) if _good_name(x)]
    end=attrs.get('end_date') or event.game_date
    place=_join_words(systems)
    title=f'The fighting at {place}' if place else f'Clashes with {_join_words(enemies)}' if enemies else 'A military engagement'
    parts=[f'On the {_long_date(event.game_date)}, fighting broke out' +
           (f' around {place}' if place else '') +
           (f' between {_realm_name(empire_name)} and {_join_words(enemies)}' if enemies else f' involving forces of {_realm_name(empire_name)}') + '.']
    if fleets:
        parts.append(f'{_join_words(fleets)} ' + ('were' if len(fleets)>1 else 'was') + ' involved.')
    if commanders:
        parts.append(('Commanders included ' if len(commanders)>1 else 'Command was held by ') + _join_words(commanders) + '.')
    if end!=event.game_date and _date_key(end)>=_date_key(event.game_date):
        parts.append(f'The fighting continued into {_long_date(end)}.')
    us=_int(attrs.get('latest_player_losses'))
    them=_int(attrs.get('latest_opposing_losses'))
    if us is None:us=_int(attrs.get('initial_player_losses'))
    if them is None:them=_int(attrs.get('initial_opposing_losses'))
    direct=attrs.get('evidence_kind')=='direct_anchored'
    if direct and (us or them):
        figures=[]
        if us:figures.append(f'{us} {empire_name} {_plural(us,"ship")} lost')
        if them:figures.append(f'{them} opposing {_plural(them,"ship")} lost')
        parts.append('The surviving fleet tallies list '+_join_words(figures)+'.')
    evidence=(f'{event.source} · {event.event_type} · {event.date_kind} · {event.confidence}. '
              f'Archived combat window: {event.game_date} to {end}. Raw aggregates are not a list of named ship casualties. '
              'Disengagement, emergency withdrawal, destruction and subsequent return must be independently proven from ship identities; none is inferred from a missing vessel. '
              f'Raw source: {event.summary}')
    return TimelineEvent(event.game_date,title,' '.join(parts),'Combat',event.importance,
                         evidence=evidence,date_kind=event.date_kind,source=event.source)


def _technology_timeline_events(events: list[HistoricalEvent], empire_name: str = "Commonwealth of Man") -> list[TimelineEvent]:
    """One dated historical entry per acquired technology, not a vague bundle."""
    realm=_realm_name(empire_name)
    result=[]
    for row in events:
        if row.category != 'technology':
            continue
        title=row.title
        detail=''
        low=title.casefold()
        # These are conservative thematic contexts derived from the named
        # subject, not claims about bonuses, choices or proven completion days.
        if 'fleet support' in low or 'interstellar logistics' in low:
            detail=' The doctrine strengthened the organisation of fleets operating far from their home ports.'
        elif 'shield' in low:
            detail=' The advances expanded the defensive technologies available to the navy.'
        elif 'cloaking' in low:
            detail=' The advance opened new possibilities for keeping vessels concealed.'
        elif 'power plant' in low:
            detail=' The breakthrough added to the engineering knowledge behind the empire’s energy infrastructure.'
        elif 'cruiser' in low or 'battleship' in low or 'destroyer' in low:
            detail=' This development contributed to the design and construction of the empire’s warships.'
        elif 'terraform' in low:
            detail=' The advance expanded the techniques available for reshaping planetary environments.'
        body=(f'By {_long_date(row.game_date)}, {realm} had mastered {title} through its scientific establishment.' + detail)
        result.append(TimelineEvent(row.game_date,title,body,'Technology',row.importance,
             evidence='First seen in the completed-technology list on '+row.game_date +
                      '. The archive date need not be the day the research finished.',
             date_kind='first_observed',source='technology_history'))
    return result


def _research_queue_timeline_events(db: Database, campaign_id: int, empire_name: str, historical: list[HistoricalEvent]) -> list[TimelineEvent]:
    """Active queue observations; never declare a technology abandoned or completed from a change."""
    campaign=db.campaign(campaign_id)
    if campaign is None:return []
    if not hasattr(db, 'all_snapshots') or not hasattr(campaign, '__getitem__'):
        return []
    try:
        archive_dir=campaign['archive_dir']
    except (KeyError, IndexError, TypeError):
        return []
    if not archive_dir:
        return []
    archived=list(db.all_snapshots(campaign_id))
    observations=read_observations(Path(archive_dir),archived)
    queue_events=research_events(observations)
    if not queue_events:return []
    keys={}
    for h in historical:
        if h.category=='technology':
            attrs=_attrs(h)
            key=attrs.get('technology_key') or attrs.get('tech_key') or attrs.get('key')
            if key:keys[key]=h.title
    from .localisation import resolve_localisation_key
    from .domains.technology.parser import _humanise_technology_key
    source=Path(campaign['source_save'])
    names={}
    from .story_text import game_description
    descriptions={}
    def context(key):
        if key not in descriptions:
            detail,source=game_description(key)
            # Printed historical prose cannot address the player or contain
            # unresolved scripted variables. Such material stays unpublished.
            descriptions[key]=(detail if detail and not re.search(r"\b(?:you|your|player|click)\b",detail,re.I) else None)
        return descriptions[key]
    def name(key):
        if key not in names:
            names[key]=keys.get(key) or resolve_localisation_key(source,key) or _humanise_technology_key(key)
        return names[key]
    realm=_realm_name(empire_name)
    rows=[]
    is_machine = ('machine' in _opening_narrative(db,campaign_id,empire_name,str(campaign['first_game_date'])).casefold()
                  and empire_name.casefold() != 'commonwealth of man')
    for ev in queue_events:
        field=ev['discipline'].capitalize()
        current=name(ev['key'])
        when=ev['date']; observed=ev['observed_date']; original=ev['queue_date']
        progress=ev['progress']
        is_switch=bool(ev['previous_key'])
        prior=name(ev['previous_key']) if is_switch else ''
        researchers = 'research networks' if is_machine else 'researchers'
        if ev['precision']=='native_queue_date':
            text=(f"On {_long_date(when)}, {realm} began pursuing {current} "
                  f"through its {field.lower()} {researchers}.")
        elif is_switch:
            text=(f"By {_long_date(observed)}, {realm} had shifted its {field.lower()} research "
                  f"from {prior} to {current}.")
        else:
            text=(f"By {_long_date(observed)}, {current} was an active {field.lower()} project within {realm}.")
        if ev['kind']=='resumed_observed':
            text += f' The {field.lower()} division was returning to a line of inquiry it had pursued before.'
        detail=context(ev['key'])
        if detail:
            text += ' ' + detail
        title=(f"{field}: {current} returns to the research programme" if ev['kind']=='resumed_observed' else
               f"{field}: research turns to {current}" if is_switch else f"{field}: {current} enters research")
        evidence=(f"Read from player-country {field.lower()}_queue; technology ID {ev['key']}; "
                  f"first observed {observed}; stored queue date {original or 'not retained'}; "
                  f"progress {progress if progress is not None else 'not recorded'}. "
                  f"A queue date is not proof of uninterrupted work; an observed change does not prove cancellation, completion, or a player decision.")
        rows.append(TimelineEvent(when,title,text,'Technology',72,evidence=evidence,
                    date_kind=ev['precision'],source='save_research_queue'))
    return rows


def _empire_voice_states(db: Database, campaign_id: int) -> list[tuple[str, str, str]]:
    """Archive-dated government/ethics observations: never use a future state for an earlier event."""
    result = []
    for row in db.politics_states(campaign_id):
        try:
            state = json.loads(row["state_json"] or "{}")
        except (ValueError, TypeError):
            continue
        if not isinstance(state, dict):
            continue
        govt = str(state.get("government_type") or "").casefold()
        authority = str(state.get("authority") or "").casefold()
        ethics = ",".join(str(x) for x in state.get("ethics") or []).casefold()
        result.append((str(row["game_date"]), govt + " " + authority, ethics))
    return sorted(result, key=lambda r: r[0])


def _service_narrative(body: str, game_date: str, states: list[tuple[str, str, str]], empire_name: str = "the state") -> str:
    """Change *tone*, never fabricate voluntary enlistment, appointments or recruitment motives."""
    known = [row for row in states if row[0] <= game_date]
    if not known:
        return body
    _, government, ethics = known[-1]
    match = re.fullmatch(r"(.+?) entered service as a ([^.]+?) on (\d{4}\.\d{2}\.\d{2})\.(.*)", body)
    if not match:
        return body
    name, rank, dated, after = match.groups()
    rank = rank.strip()
    if 'commander' in rank.casefold() and any(x in government + ethics for x in ('military_dictatorship','military dictatorship','militarist')):
        return f"{name} joined the command ranks of {empire_name} on {dated}.{after}".strip()
    if 'democratic' in government or 'democracy' in government:
        return f"{name} entered public service as a {rank} on {dated}.{after}".strip()
    if any(x in government for x in ('imperial','dictatorial','autocratic')):
        return f"{name} began service as a {rank} on {dated}.{after}".strip()
    return body


def _ship_milestones(db: Database, campaign_id: int) -> list[TimelineEvent]:
    """Separate native construction dates from first observed assignments, for all named major hulls."""
    from .domains.ships.provenance import _usable_exact_construction_date
    rows=db.ship_registry(campaign_id)
    campaign=db.campaign(campaign_id)
    origin=str(campaign['first_game_date'] or '') if campaign else ''
    focus=('battlecruiser','battleship','titan','juggernaut','cruiser','destroyer','colossus','dreadnought','flagship')
    result=[]
    for row in rows:
        size=str(row['opening_ship_type'] or row['ship_type'] or '').strip()
        if not any(k in size.casefold() for k in focus):continue
        name=str(row['opening_name'] or row['name'] or '').strip()
        if not _good_name(name):continue
        seen=str(row['first_seen_date'] or '')
        construction=str(row['opening_construction_date'] or row['construction_date'] or '')
        exact=_usable_exact_construction_date(construction,record_start_date=origin,observed_date=seen)
        when=construction if exact else seen
        if _date_key(when)[0]==999999:continue
        fleet=str(row['opening_fleet_name'] or '').strip()
        commander=str(row['opening_commander_name'] or '').strip()
        identity=f'the {size.lower()} {name}'
        realm=_realm_name(str(campaign['empire_name'])) if campaign and 'empire_name' in campaign.keys() else 'the empire'
        evidence=f'Ship registry ID {row["ship_id"]} · first observed {seen} · stored construction date {construction or "not available"}.'
        if exact:
            result.append(TimelineEvent(when,f'{name} commissioned',
               f'{name}, a {size.lower()}, entered {realm}’s naval service.',
               'Navy',58,evidence=evidence+' Exact construction date validated against save provenance.',date_kind='exact_save_field',source='ship_registry'))
        else:
            result.append(TimelineEvent(seen,f'{name} enters the naval rolls',
                f'By this date, {identity} was in service to {realm}.',
                'Navy',56,evidence=evidence+' First observed; actual commissioning date not established.',source='ship_registry'))
        if _date_key(seen)[0]!=999999 and _good_name(fleet) and fleet.casefold() != name.casefold():
            sentence=f'By {_long_date(seen)}, {name} had joined {fleet}' + (f' under {commander}' if _good_name(commander) else '') + '.'
            result.append(TimelineEvent(seen,f'{name} joins {fleet}',sentence,'Navy',55,
                evidence=evidence+' Fleet and commander present in the first surviving ship observation, not necessarily assigned that day.',
                date_kind='first_observed',source='ship_registry'))
    return result




def _people_government_milestones(db: Database, campaign_id: int, leaders: dict[int, object], empire_name: str) -> list[TimelineEvent]:
    """Expose already-preserved leader traits, council changes and proven deaths.

    No future/latest trait is back-projected to recruitment. Confirmation of a
    death requires a dead-leader record or notification, never just absence.
    """
    result: list[TimelineEvent] = []
    for row in db.leader_career_events(campaign_id, visible_only=False):
        kind = str(row['event_type'] or '')
        if kind not in {'leader_traits_gained','leader_council_changed','leader_death_recorded','leader_level_changed'}:
            continue
        lid=int(row['leader_id'])
        leader=leaders.get(lid)
        name=_clean_stellaris_name(str(leader['name']),str(leader['gender'] or '')) if leader else 'A serving leader'
        date=str(row['game_date'])
        evidence=f"leader_career_events · {kind} · {row['date_kind']} · {row['confidence']}. {row['body']}"
        original=str(row['body'] or '')
        if kind=='leader_traits_gained':
            match=re.search(r'newly observed traits?:\s*(.+?)\.?$',original,re.I)
            if not match:continue
            traits=match.group(1).rstrip('.').strip()
            if not traits:continue
            title=f'{name} develops new expertise'
            individually = [x.strip() for x in traits.split(',') if x.strip()]
            clauses = [f'the skill of {item}' if re.search(r'\s+[IVX]+$', item) else f'the trait of {item}' for item in individually]
            body=f'By {_long_date(date)}, {name} had acquired ' + _join_words(clauses) + '.'
            category,importance='People',66
        elif kind=='leader_level_changed':
            level_match = re.search(r'leader level changed from (\d+) to (\d+)', original, re.I)
            if not level_match or int(level_match.group(2)) <= int(level_match.group(1)):
                continue
            level = int(level_match.group(2))
            title = f'{name} reaches professional level {level}'
            body = f'By {_long_date(date)}, {name} had advanced to level {level} in {empire_name}’s service.'
            category, importance = 'People', 61
        elif kind=='leader_council_changed':
            match=re.search(r'council role (.+?)\.$',original,re.I)
            if not match:continue
            office=match.group(1).strip()
            title=f'{name} joins the council as {office}'
            body=f'By {_long_date(date)}, {name} had taken a seat on the governing council as {office}.'
            category,importance='Politics',78
        else:
            notification = str(row['date_kind']) in ('exact_notification_date','exact_save_field')
            title=f'{name} dies' if notification else f'The death of {name} becomes known'
            # The historic death notification has its own date, role, age and
            # sometimes a recorded cause, which are distinct from last appearance.
            person_role=re.search(r'identifies (.+?) as dead\.',original,re.I)
            descriptor=person_role.group(1).strip() if person_role else name
            age=re.search(r'records age (\d+)',original,re.I)
            cause=re.search(r'The retained notice states:\s*"([^"]+)"',original,re.I)
            if notification:
                body=f'On {_long_date(date)}, {descriptor} died'
                if age:body+=f' aged {age.group(1)}'
                body+='.'
            else:
                body=f'By {_long_date(date)}, the death of {name} was confirmed, although its exact date remains unknown.'
            if cause and not re.match(r'(?i)^died at the age of',cause.group(1)):
                body+=' The recorded circumstances state: '+cause.group(1).rstrip('.')+'.'
            category,importance='People',94
        result.append(TimelineEvent(date,title,body,category,importance,lid,evidence,
                                    str(row['date_kind']), 'leader_career_events'))
    return result

def _collect_events(db: Database, campaign_id: int, *, presentation=None) -> tuple[list[TimelineEvent], dict[int, object]]:
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist.")

    if presentation is None:
        presentation = build_presentation_history(db, campaign_id)
    historical = list(presentation.events)
    leaders = {int(row["leader_id"]): row for row in db.leader_registry(campaign_id)}
    events: list[TimelineEvent] = []
    states = _empire_voice_states(db, campaign_id)
    empire_name = str(campaign["empire_name"])

    for event in historical:
        if event.category == "technology":
            continue  # grouped below into milestone rows

        if event.event_type == "record_opening":
            founding = _founding_prologue(db, campaign_id)
            events.append(TimelineEvent(
                event.game_date,
                f"The Origins of {empire_name}",
                founding[0] if founding else _opening_narrative(db,campaign_id,empire_name,event.game_date),
                "Empire",event.importance,
                evidence=founding[1] if founding else 'Opening empire state; no founding date is inferred.',
                date_kind='archive_opening',source='opening_save'
            ))
            continue

        if event.category == "expansion" and event.importance >= 85:
            events.append(_expansion_prose(event, empire_name))
            continue

        if event.category == "people" and _leader_is_notable(event, leaders):
            events.extend(_leader_prose(event, empire_name, states))
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
                events.append(_aux_ship_prose(event, empire_name))
            continue

        if event.category == "science":
            attrs = _attrs(event)
            technical = (attrs.get('project_key') or attrs.get('situation_key') or '').lower()
            include = (event.event_type == 'archaeology_site_observed' or
                       (event.event_type in {'special_project_observed','situation_observed'}
                        and not technical.endswith('_deficit') and technical != 'situation_observation_insight'))
            if include:
                events.append(_story_prose(event, empire_name))
            continue

        if event.category == "combat" and event.event_type == "combat_episode":
            attrs = _attrs(event)
            direct = attrs.get("evidence_kind") == "direct_anchored"
            meaningful = bool(attrs.get("systems") or attrs.get("opposing_countries") or attrs.get("player_fleets"))
            if direct or (event.confidence == "high" and event.importance >= 88 and meaningful):
                events.append(_combat_timeline_event(event, str(campaign["empire_name"])))

    # Keep ALL exact annual records for the detailed government register and
    # service-span verification. The public Annals deliberately condense census
    # chapters to a four-year cycle plus source-supported leadership upheavals.
    censuses = []
    if 'archive_dir' in campaign.keys():
        try:
            censuses = annual_censuses(db.path, campaign_id, Path(str(campaign['archive_dir'])))
        except (OSError, ValueError, KeyError):
            censuses = []
        dramatic = {str(row['game_date']) for row in db.leader_career_events(campaign_id, visible_only=False)
                    if str(row['event_type']) == 'leader_death_recorded'}
        dramatic.update(e.game_date for e in events
                        if e.category == 'Politics' and any(token in e.title.lower() for token in (
                            'government reorganised', 'authority reformed', 'change in the leadership')))
        published = _four_year_census_dates(censuses, dramatic)
        for census in censuses:
            if not census['available'] or census['date'] not in published:
                continue
            label = ('Opening Government Census' if census['opening']
                     else 'Extraordinary Government Census' if (int(census['year']) - int(censuses[0]['year'])) % 4
                     else 'Four-year Government Census')
            source = census['source'] or {}
            note = (f"Exact archived census date {census['date']}; snapshot #{source.get('snapshot_id')}; "
                    f"save SHA-256 {source.get('sha256')}. Every name, position and trait "
                    'comes from that dated leader snapshot; changes between saves are unknown. '
                    'Full yearly records remain available in Government Census.')
            events.append(TimelineEvent(census['date'], label,
                census_prose(census, empire_name), 'Politics', 98,
                evidence=note, date_kind='exact_snapshot_state',
                source='annual_government_census'))

    events.extend(_group_service_anniversaries(service_milestones(censuses), empire_name))

    events.extend(_people_government_milestones(db,campaign_id,leaders,empire_name))
    events.extend(_technology_timeline_events(historical, empire_name))
    events.extend(_research_queue_timeline_events(db,campaign_id,empire_name,historical))
    events.extend(_ship_milestones(db, campaign_id))
    events.extend(_native_milestones(db,campaign_id,empire_name))

    # The optional civic sidecar is hashed and independent of the main DB.
    # Older scripted test fixtures don't carry archive_dir or snapshots.
    if 'archive_dir' in campaign.keys() and hasattr(db, 'all_snapshots'):
        try:
            civic_rows=read_civic_frontier(Path(str(campaign['archive_dir'])), db.all_snapshots(campaign_id))
            for item in civic_frontier_events(civic_rows):
                events.append(TimelineEvent(item['date'],item['title'],item['body'],
                    item['category'],item['importance'],evidence=item['evidence'],
                    date_kind=item['date_kind'],source=item['source']))
        except (OSError,ValueError,TypeError,KeyError):
            pass  # Optional evidence may never prevent the main timeline.

    # Publishing observed planetary administration changes was previously
    # suppressed even though the world history database retained them.
    if hasattr(db,'world_history_events'):
        names={int(r['planet_id']):str(r['name']) for r in db.world_registry(campaign_id)}
        for row in db.world_history_events(campaign_id, visible_only=False):
            kind=str(row['event_type'] or '')
            if kind not in ('governor_changed','designation_changed'):
                continue
            date=str(row['game_date'])
            name=names.get(int(row['planet_id']), 'the colony')
            if kind=='governor_changed':
                title='A change in the government of '+name
                identifier=str(row['event_key'] or '').rsplit(':',1)[-1]
                governor=leaders.get(int(identifier)) if identifier.isdigit() else None
                if governor is not None:
                    person=_clean_stellaris_name(str(governor['name']),str(governor['gender'] or ''))
                    body=f'By {_long_date(date)}, {person} had taken responsibility for the government of {name}.'
                elif identifier in ('None','4294967295','none'):
                    body=f'By {_long_date(date)}, the government of {name} no longer had its previously recorded governor.'
                else:
                    body=f'By {_long_date(date)}, the government of {name} had changed its appointed leadership.'
            else:
                title=name+' adopts a new planetary role'
                original=str(row['body'] or '')
                designation=re.search(r'designation\s+([^.;]+)',original,re.I)
                value=designation.group(1).strip() if designation else ''
                body=(f'By {_long_date(date)}, {name} had been designated {value}, reflecting a new administrative direction.'
                      if value and value.casefold()!='not resolved'
                      else f'By {_long_date(date)}, the administration of {name} had revised its planetary role.')
            events.append(TimelineEvent(date,title,body,'Politics',69,
                evidence='Native world-history observation: '+kind+'; exact action date not established.',
                date_kind='first_observed',source='world_history_events'))

    # Give the active campaign a clear present edge without pretending it ended.
    latest_date = str(campaign["latest_game_date"] or "")
    # The source of the summary must be the most recently *processed* save,
    # not merely the save watcher’s latest archived date. The two can diverge
    # during Live History catch-up, particularly on a busy campaign.
    if hasattr(db, 'all_snapshots'):
        processed_dates = [str(r['game_date']) for r in db.all_snapshots(campaign_id)
                           if int(r['processed'] or 0)]
        latest_date = max(processed_dates) if processed_dates else ''
    if latest_date:
        present_worlds = sum(1 for row in db.world_registry(campaign_id) if str(row["status"] or "") == "present")
        present_ships = sum(1 for row in db.ship_registry(campaign_id) if str(row["status"] or "") == "present")
        present_leaders = sum(1 for row in db.leader_registry(campaign_id) if str(row["status"] or "") == "present")
        events.append(TimelineEvent(
            latest_date,
            "The chronicle continues",
            (
                f"By this date, the realm encompassed {present_worlds} inhabited {_plural(present_worlds, 'world')}, "
                f"{present_ships} vessels, and {present_leaders} serving leaders. Its history continues."
            ),
            "Empire",
            100,
            evidence=(f'Counts from the active registries after processing the last completed archive on {latest_date}; '
                      'this is a dated summary, not an independently exact census of the galactic population.'),
            date_kind='processed_snapshot_state', source='registries_summary',
        ))

    events = _deduplicate_semantic_events(_clean_legacy_names(events, leaders))

    # De-duplicate presentation rows. If two domain sources describe the same
    # title on the same day, keep the higher-importance version.
    deduped: dict[tuple[str, str], TimelineEvent] = {}
    for event in events:
        anonymous = event.category in ('Navy', 'Exploration') and re.match(r'^A (?:science|construction|colony) ship enters service$', event.title)
        key = (event.game_date, event.title, event.evidence) if anonymous else (event.game_date, event.title)
        old = deduped.get(key)
        if old is None or event.importance > old.importance:
            deduped[key] = event

    return sorted(deduped.values(),
        key=lambda event: (_date_key(event.game_date), -event.importance, event.category, event.title),
    ), leaders


def _four_year_census_dates(censuses: list[dict], leadership_dates: set[str] | None = None) -> set[str]:
    """Display one opening census and a four-year rhythm, plus leadership crises.

    The yearly source snapshots remain intact in SQLite and in the detailed
    census explorer. An extraordinary census uses ONLY an exact saved January
    roster; a death or a ruler change in a different month does not manufacture
    a state snapshot for that month. The qualifying dramatic event appears on
    its independently supported date in the Annals.
    """
    valid = [c for c in censuses if c.get('available') and str(c.get('date','')).endswith('.01.01')]
    if not valid:
        return {str(c['date']) for c in censuses if c.get('available') and c.get('opening')}
    foundation = min(int(c['year']) for c in valid)
    chosen = {str(c['date']) for c in censuses if c.get('available') and (
        c.get('opening') or ((int(c['year']) - foundation) % 4 == 0))}
    # A dramatic change warrants the *next available* source-dated census.
    # It is not a new claim about the exact date of the change.
    for event_date in leadership_dates or ():
        after = next((c for c in valid if c['date'] >= event_date), None)
        if after:
            chosen.add(str(after['date']))
    return chosen


def _group_service_anniversaries(anniversaries: list[dict], empire_name: str) -> list[TimelineEvent]:
    """One readable event per identical anniversary date and service span.

    Keep the original leader IDs and every individual proof in event evidence;
    only group the *presentation*. The census register remains fully detailed.
    """
    groups: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for entry in anniversaries:
        if entry['years'] == 1 and entry['group'] not in ('Ruler', 'Council'):
            continue
        groups[(entry['date'], entry['years'])].append(entry)
    output = []
    for (date, years), members in sorted(groups.items()):
        people = sorted(members, key=lambda e:(e['name'].casefold(), e['leader_id']))
        lines = []
        for person in people:
            office = person['office']
            role = office if office else person['role'].lower()
            lines.append(f"{person['name']} ({role})")
        if years == 1:
            introduction = (f'At the January census of {date[:4]}, '
                f'{len(people)} {_plural(len(people), "officeholder")} appeared again, '
                'a year after their first preserved January roster. '
                'The records establish both observations, not uninterrupted service between them.')
        else:
            introduction = (f'The January census of {date[:4]} marked {years} years between '
                'the first and latest preserved yearly appearances of these officials. '
                'Every intervening January roster records the same individual identities, '
                'although continuous service between archive dates cannot be proved.')
        body = introduction + '\n\n' + '; '.join(lines) + '.'
        evidence = '\n'.join(str(p['evidence']) for p in people)
        output.append(TimelineEvent(date, f'{years}-year service milestones — {len(people)} {_plural(len(people), "person", "people")}',
            body, 'People', 82 if years > 1 else 73, evidence=evidence,
            date_kind='attested_annual_census_span', source='annual_verified_service'))
    return output


def _people_of_note(events: list[TimelineEvent], leaders: dict[int, object]) -> list[tuple[str, str, str]]:
    result: list[tuple[str, str, str]] = []
    seen: set[int] = set()
    for event in events:
        if event.leader_id is None or event.leader_id in seen:
            continue
        leader = leaders.get(event.leader_id)
        if leader is None:
            continue
        seen.add(event.leader_id)
        role = str(leader["leader_class"] or "leader").title()
        # A later ruler or later fleet assignment cannot be projected back
        # onto an earlier event. Details remain in the dated career entries.
        summary = event.body.strip()
        # This description belongs to the event *in this year*. Never borrow
        # later leader-registry traits, positions or fates.
        summary = summary[:250].rsplit(' ', 1)[0] + '…' if len(summary) > 250 else summary
        result.append((_clean_stellaris_name(str(leader["name"]), str(leader["gender"] or "")), role, summary))
    return result[:4]


def render_timeline(db: Database, campaign_id: int) -> Path:
    """The canonical vertical historical timeline, with war-spanning rail and cards."""
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist.")
    presentation = build_presentation_history(db, campaign_id)
    events, leaders = _collect_events(db, campaign_id, presentation=presentation)
    events = list(events)  # add war milestones without mutating presentation history
    wars = _war_spans(presentation, str(campaign["empire_name"]))
    for war in wars:
        title = str(war['title'])
        game_date = str(war['start'])
        action = 'declared' if 'Conquest' in title else 'began'
        events.append(TimelineEvent(
            game_date, f'{title} begins',
            f'On the {_long_date(game_date)}, {_realm_name(str(campaign["empire_name"]))} entered the conflict known as {title}.',
            'War', 100,
            evidence=f'Native war #{war["id"]}; recorded start {game_date}. Last war-presence observation {war["last"]}. '
                     f'First later absence {war["first_absent"] or "not available"}. These are not peace dates.',
            date_kind='exact_save_field', source='formal_war', war_id=int(war['id'])))

    # Connect a native victory to a formal war only when its opponent is
    # explicitly typed and there is ONE matching war ending in this observation
    # interval. Matching merely by enemy name or by the oldest war is unsafe.
    # Date rules are Stellaris's native 360-day calendar, sorted lexically.
    from dataclasses import replace
    linked=[]
    player_id=(getattr(presentation.combat_snapshots[-1],'player_country_id',None)
               if getattr(presentation,'combat_snapshots',()) else None)
    native_data=None
    try:
        archive=Path(str(campaign['archive_dir']))
        if (archive/'Native_Timeline_Milestones.json').is_file():
            native_data=json.loads((archive/'Native_Timeline_Milestones.json').read_text('utf-8'))
    except (OSError,ValueError):pass
    for event in events:
        if not (event.source=='player_country.timeline_events' and event.title in ('First wartime victory','Victory in war')):
            linked.append(event);continue
        source_event=next((r for r in (native_data or {}).get('events',[])
                           if r.get('date')==event.game_date and
                              r.get('definition') in ('timeline_first_war_won','timeline_war_won')),None)
        other=[]
        if source_event:
            other=[id_ for typ,id_ in zip(source_event.get('reference_types',[]),source_event.get('reference_ids',[]))
                   if typ=='country' and id_!=player_id]
        matches=[w for w in wars
                 if other and w.get('first_absent') and
                    _date_key(w['last']) < _date_key(event.game_date) <= _date_key(w['first_absent']) and
                    _date_key(w['start']) <= _date_key(event.game_date) and
                    any(x in (w['defender_ids'] if w['side']=='attacker' else w['attacker_ids']) for x in other)]
        if len(matches)==1:
            w=matches[0]
            label=str(w['title'])
            event=replace(event, title='Victory in '+label,
                          body=f'On {_long_date(event.game_date)}, {_realm_name(str(campaign["empire_name"]))} secured victory in {label}.',
                          war_id=int(w['id']),
                          evidence=event.evidence + f' Unique formal war match #{w["id"]} based on typed counterpart and last-active/first-absent archive window. No unsupported treaty terms are assumed.')
        linked.append(event)
    events=linked

    # Native war starts were appended after presentation sorting: re-sort every
    # domain together, so February does not appear below November.
    events.sort(key=lambda e: (_date_key(e.game_date),-e.importance,e.category,e.title))
    by_year: dict[str, list[TimelineEvent]] = defaultdict(list)
    for event in events:
        by_year[_year(event.game_date)].append(event)
    # A war crossing an otherwise quiet year must still have a track to cross.
    for war in wars:
        for year in range(int(war["start"][:4]), int(war["last"][:4]) + 1):
            by_year.setdefault(str(year), [])

    payload = []
    year_blocks = []
    for year in sorted(by_year, key=lambda val: int(val) if val.isdigit() else 999999):
        entries = by_year[year]
        html_events = []
        for event in entries:
            idx = len(payload)
            info = {"date": event.game_date, "title": event.title, "body": event.body,
                    "category": event.category, "leader": event.leader_id,
                    "evidence": (event.evidence or ("Dated occurrence" if event.category == "People" and " dies" in event.title.lower()
                                 else "Source observation: event may have occurred earlier than this retained date.")),
                    "date_kind": event.date_kind, "source":event.source,"war_id":event.war_id}
            milestone = classify_milestone(
                title=event.title, category=event.category, source=event.source,
                importance=event.importance, leader_id=event.leader_id)
            info['milestone'] = milestone
            info['importance'] = reading_importance(event)
            info['date_label'], info['date_explanation'] = date_label(event.date_kind, event.evidence)
            payload.append(info)
            html_events.append(f'''<article class="event" data-event-index="{idx}" data-category="{_e(event.category)}" data-importance="{reading_importance(event)}" data-milestone="{str(milestone).lower()}" data-date="{_e(event.game_date)}">
                <div class="date">{_e(_short_date(event.game_date))}</div>
                <div class="event-main"><span class="tag">{_e(event.category)}</span>{'<span class="tag milestone-tag">✦ MILESTONE</span>' if milestone else ''}<span class="pin-indicator" hidden>★ PINNED</span>
                  <button class="event-open" data-event="{idx}" type="button" aria-label="Open details: {_e(event.title)}">
                    <strong>{_e(event.title)}</strong><span class="event-summary">{_e(event.body)}</span>
                    <small>Read its story ↗</small></button></div></article>''')
        # Monthly editorial leads quote existing narrative text only.
        month_html = []
        card_position = 0
        for month_key, month_name, month_events in month_groups(entries):
            extracts = period_extract(month_events, limit=2)
            month_html.append(f'<div class="month-heading" data-month="{_e(month_key)}"><h3>{_e(month_name)}</h3>'
                              f'<div class="month-lead">{"".join("<p>" + _e(sentence) + "</p>" for sentence in extracts)}</div></div>')
            month_html.extend(html_events[card_position:card_position+len(month_events)])
            card_position += len(month_events)
        html_events = month_html
        year_extracts = period_extract(entries, limit=2)
        year_overview = '<div class="year-overview">' + ''.join('<p>' + _e(sentence) + '</p>' for sentence in year_extracts) + '</div>' if year_extracts else ''
        people = _people_of_note(entries, leaders)
        people_html = ''
        if people:
            people_html = '<aside class="people-note"><div class="people-heading">People of Note</div>' + ''.join(
                f'<div><strong>{_e(name)}</strong><span>{_e(role)}</span><p>{_e(summary)}</p></div>' for name, role, summary in people
            ) + '</aside>'
        quiet = '<div class="quiet">&nbsp;</div>' if not entries else ''
        year_blocks.append(f'''<section class="year" id="year-{_e(year)}" data-year="{_e(year)}">
          <div class="year-heading"><span>{_e(year)}</span><button class="chapter-title" type="button" data-chapter-year="{_e(year)}" title="Give this year a personal chapter title (not evidence)">+ Chapter title</button></div>
          {year_overview}<div class="events">{''.join(html_events) or quiet}</div>{people_html}</section>''')

    json_data = json.dumps({"events": payload, "wars": wars, "campaign_id": campaign_id, "first_date": str(campaign['first_game_date'] or ''), "latest_date": str(campaign['latest_game_date'] or '')}, ensure_ascii=False, separators=(',', ':'))
    json_data = (json_data.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
                       .replace('\\u2028', '\\\\u2028').replace('\\u2029', '\\\\u2029'))
    name = _e(campaign['empire_name'])
    html = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>''' + name + ''' — Historical Timeline</title>
<style>''' + _TIMELINE_STYLE + '''</style>
<link rel="stylesheet" href="/static/historian-theme.css?v=090">
<script src="/static/historian-theme.js?v=090"></script>
</head><body>
<nav class="topbar"><a href="/campaign">Campaign</a><a href="/time-machine">Time Machine</a>
<a href="/empire-archive">Empire Archive</a><a href="/research-history">Research History</a><a href="/war-journal">War Journal</a>
<a href="/scribes">Scribes Chronicle</a><a href="/civic-frontier-history">Civic History</a><a href="/intelligence-history">Intelligence</a><a href="/government-people">Government & People</a><a href="/government-census">Annual Census</a><span class="spacer"></span>
<label for="jump-year" style="font:650 12px system-ui;color:#4d5e6c">Jump to</label><input id="jump-year" class="jump-year" inputmode="numeric" type="number" min="2200" max="3000" aria-label="Jump to year">
<button id="year-go" type="button">Go</button><button id="print" type="button">Print / PDF</button></nav>
<header class="hero"><span class="kicker">THE IMPERIAL ANNALS · A CIVILISATION REMEMBERED</span><h1>''' + name + '''</h1>
<p class="subtitle">A chronological history · ''' + _e(campaign['first_game_date']) + ''' — ''' + _e(campaign['latest_game_date']) + '''</p>
<p>Careers, discoveries, conflicts and the making of new worlds. Milestones mark achievements and documented spans of service supported by the Ironman archives.</p></header>
<div class="filterbar" aria-label="Historical subjects"><span>SHOW</span>''' + ''.join(
    f'<button type="button" data-filter="{_e(k)}" class="{("active" if k=="All" else "")}">{_e(k)}</button>'
    for k in ('All','Milestones','War','Combat','People','Command','Politics','Diplomacy','Navy','Military','Expansion','Technology','Science','Story','Exploration','Infrastructure')
) + '''<button id="war-toggle" type="button" aria-pressed="true" title="Toggle war periods">War periods ✓</button></div>
<div class="reading-bar" aria-label="Reading and personalisation controls"><label for="reading-level">Reading level</label>
<select id="reading-level"><option value="highlights">Highlights</option><option value="standard" selected>Standard</option><option value="complete">Complete</option></select>
<span id="reading-count" aria-live="polite"></span><label for="export-start">Export years</label>
<input id="export-start" type="number" min="1" max="99999" aria-label="Export from year" placeholder="From">
<span>to</span><input id="export-end" type="number" min="1" max="99999" aria-label="Export through year" placeholder="To">
<button type="button" id="export-html">Export chapter HTML</button><small>Notes and pinned events are personal, not historical evidence.</small></div>
<div class="chronicle ''' + ('no-wars' if not wars else '') + '''" id="chronicle"><div class="war-track" id="war-track" aria-label="Long-running wars"></div>
<main class="timeline" id="timeline">''' + ''.join(year_blocks) + '''</main></div>
<footer class="historian-footer" aria-label="Project and source information">
  <div><strong>Stellaris Historian</strong> · The Imperial Annals<br>
    A locally generated chronicle of evidence preserved from archived Stellaris Ironman saves.</div>
  <div><span>Developed by PillBoxUK</span> · <a href="https://github.com/PillBoxUK/Stellaris-Historian" target="_blank" rel="noopener noreferrer">Source repository ↗</a>
    · <a href="https://github.com/PillBoxUK" target="_blank" rel="noopener noreferrer">PillBoxUK on GitHub ↗</a><br>
    Unofficial fan project. Not affiliated with Paradox Interactive.</div>
  <small>For PDF exports, disable your browser’s “Headers and footers” option to remove the browser’s separate date, URL and title lines.</small>
</footer>
<div class="floating" id="floating" role="dialog" aria-label="Historical detail" aria-modal="false" hidden>
  <div class="floating-header" id="floating-header"><button type="button" id="card-close" aria-label="Close card">×</button>
    <span>ARCHIVE DETAIL · DRAG TO MOVE</span><button id="card-flip" type="button">Flip ↻</button></div>
  <div class="floating-content" id="floating-content"></div>
  <div id="personal-notes" class="personal-notes" hidden><label for="note-text">My annotation (not historical evidence)</label>
    <textarea id="note-text" rows="3" maxlength="4000" placeholder="Personal thoughts or chapter notes"></textarea>
    <div class="note-actions"><button id="note-save" type="button">Save note locally</button><button id="note-pin" type="button">Pin event</button></div>
    <small>Stored in this browser only. Export HTML to retain a portable copy.</small></div>
</div>
<script type="application/json" id="chronicle-data">''' + json_data + '''</script>
<script>''' + _TIMELINE_JS + '''</script></body></html>'''
    target = timeline_path(db, campaign_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.timeline_', suffix='.html', dir=target.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(html)
        os.replace(tmp, target)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return target


_TIMELINE_STYLE = r"""
:root{--ink:#253342;--muted:#687987;--gold:#ad8050;--navy:#142438;--paper:#f8f4eb;--panel:#fffdfa;--line:#dbcfbd;--rail:240px}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.6 Georgia,'Times New Roman',serif}
button,input{font:inherit}button{cursor:pointer}button:focus-visible,a:focus-visible,input:focus-visible{outline:3px solid #b99a61;outline-offset:2px}
.topbar{position:sticky;top:0;z-index:15;background:#fffcf5f5;backdrop-filter:blur(12px);border-bottom:1px solid var(--line);display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:10px max(16px,calc((100vw - 1330px)/2));font-family:system-ui,sans-serif}
.topbar a,.topbar button{padding:7px 12px;border:1px solid #c9b9a3;border-radius:5px;background:var(--panel);color:#344b5d;text-decoration:none;font:650 12px system-ui}.topbar .spacer{flex:1}.topbar a:hover,.topbar button:hover{background:#ecdfc9}
.topbar .jump-year{width:77px;padding:7px 9px;border:1px solid #c9b9a3;border-radius:5px;background:#fffdfa;font:650 12px system-ui;color:#263d4f}
.hero{position:relative;overflow:hidden;background:radial-gradient(ellipse at 75% -25%,#35546b 0%,transparent 40%),radial-gradient(ellipse at 10% 120%,#26394b 0%,transparent 39%),#111d2a;color:#f8eedb;padding:46px max(22px,calc((100vw - 1300px)/2)) 48px;max-width:none;margin:0}
.hero:before{content:'';position:absolute;inset:0;opacity:.21;background-image:radial-gradient(#ffffff93 .7px,transparent .8px);background-size:37px 35px;pointer-events:none}
.hero>*{position:relative}.kicker{font:700 12px system-ui;letter-spacing:.23em;color:#e6bd82}h1{font:normal clamp(39px,5.4vw,71px)/1.05 Georgia,serif;margin:14px 0 11px;color:#fff2d9;letter-spacing:-.035em}
.hero p{max-width:810px;color:#d3dfe3;margin:9px 0;font-size:17px}.hero .subtitle{color:#e9c68f;font-size:18px}
.filterbar{position:sticky;top:58px;z-index:12;display:flex;align-items:center;flex-wrap:wrap;gap:7px;background:#fbf6ecf3;border-bottom:1px solid var(--line);padding:12px max(15px,calc((100vw - 1320px)/2));font-family:system-ui,sans-serif;backdrop-filter:blur(10px)}.filterbar span{letter-spacing:.15em;font:750 10px system-ui;color:#906543;margin-right:6px}.filterbar button{border:1px solid #cbbba7;background:#fffcf7;color:#4a5d6c;border-radius:5px;padding:7px 12px;font:650 12px system-ui}.filterbar button:hover{background:#efe3d2}.filterbar button.active{background:#233b50;color:white;border-color:#233b50}.filterbar #war-toggle{margin-left:auto;color:#875934;border-color:#bd9e77}
.chronicle{display:grid;grid-template-columns:var(--rail) minmax(0,1fr);gap:26px;position:relative;max-width:1320px;margin:auto;padding:28px 20px 100px;min-height:560px;align-items:stretch}
.chronicle.no-wars{grid-template-columns:minmax(0,1fr);max-width:970px}.chronicle.no-wars .war-track{display:none}.war-track{position:relative;border-right:1px solid #cfbea4;min-height:100%}.war-track:before{content:'WARS ACROSS THE YEARS';position:sticky;top:128px;display:block;color:#9b7148;padding:0 13px 8px;border-bottom:1px solid #d6c4a8;font:750 10px system-ui;letter-spacing:.1em;margin-bottom:10px}.war-period{position:absolute;left:6px;right:12px;display:flex;flex-direction:column;text-align:left;align-items:stretch;border:1px solid #c3a47c;border-left:5px solid #9f7048;border-radius:5px;min-height:35px;background:linear-gradient(90deg,#e6d2b2e8,#f3eadbde);color:#493a31;padding:13px 11px;overflow:hidden;box-shadow:inset 0 0 0 1px #fff8e6;z-index:3}.war-period:hover{background:#e5cba5;outline:2px solid #a47943;outline-offset:1px}.war-period .war-label{font:700 14px/1.4 Georgia,serif}.war-period .war-dates{color:#7e654e;font:650 10px/1.4 system-ui;margin:7px 0}.war-period .war-duration{font:750 10px system-ui;letter-spacing:.16em;text-transform:uppercase;color:#94724e;writing-mode:vertical-rl;margin:24px auto;opacity:.7}.war-period.compact .war-duration{display:none}.war-period.short .war-label{font-size:11px}
.timeline{min-width:0}.year{position:relative;scroll-margin-top:150px;margin:0;padding:9px 0 16px;border-bottom:1px solid #ebdfcf;min-height:58px}.year-heading{display:flex;align-items:center;gap:14px;margin:0 0 10px}.year-heading span{font:normal 30px Georgia,serif;color:#936b46}.year-heading:after{content:'';height:1px;flex:1;background:linear-gradient(90deg,#cbb392,#e8dfd2)}
.events{border-left:2px solid #72818a;margin:0 0 0 16px;padding:0 0 0 25px;min-height:26px;display:grid;gap:12px}.event{position:relative;display:block;padding:0}.event:before{content:'';position:absolute;left:-34px;top:19px;width:13px;height:13px;border-radius:50%;background:#d5ac72;border:3px solid var(--paper);box-shadow:0 0 0 1px #ae8350;z-index:2}.event-main{position:relative;padding:13px 17px;background:#fffdfa;border:1px solid #d9cebd;border-radius:5px;box-shadow:0 4px 14px #493a250b;transition:transform .17s,box-shadow .17s,border-color .17s}.milestone-tag{margin-left:7px;color:#7c5824;border-color:#b58c4c;background:#fdf0d1}.event[data-milestone="true"]:before{background:#af7f26;box-shadow:0 0 0 1px #a37c34,0 0 0 4px #efd8a6}
.event-main:hover{transform:translateX(3px);box-shadow:0 9px 23px #493a2516;border-color:#b99d78}.event .date{color:#956b42;font:750 11px system-ui;margin-bottom:2px}.tag{display:inline-block;border:1px solid #cbbb9e;border-radius:17px;color:#736652;font:750 9px/1.5 system-ui;letter-spacing:.11em;text-transform:uppercase;padding:1px 7px;margin-bottom:4px}.event-open{display:block;width:100%;color:var(--ink);background:transparent;border:0;text-align:left;padding:0}.event-open strong{display:block;font:700 clamp(16px,2vw,20px)/1.3 Georgia,serif;color:#233448}.event-open:hover strong{color:#8f5933}.event-summary{display:block;white-space:pre-line;margin-top:6px;font:14px/1.65 Georgia,serif;color:#4c5964}.event-open small{display:block;color:#a36f43;font:750 11px system-ui;margin-top:8px}.quiet{height:16px;color:#c2b8a6}.people-note{background:#f4eadb;border:1px solid #d0bba0;border-radius:5px;margin:13px 0 2px 0;padding:13px 16px}.people-note .people-heading{color:#976d44;font:750 10px system-ui;letter-spacing:.16em;text-transform:uppercase}.people-note div:not(.people-heading){margin:4px 0}.people-note strong{display:inline;font:700 14px Georgia,serif;color:#65482f;margin-right:9px}.people-note span{color:#846e55;font:12px system-ui}
.historian-footer{background:#182838;color:#e2e8ee;padding:25px max(22px,calc((100vw - 1210px)/2));display:flex;justify-content:space-between;gap:18px 42px;flex-wrap:wrap;font:12px/1.75 system-ui,sans-serif;border-top:3px solid #b68a51}.historian-footer strong{font:normal 22px Georgia,serif;color:#f9e6be}.historian-footer a{color:#f4cf91}.historian-footer small{color:#b5c5ce;flex-basis:100%}
.floating{position:fixed;z-index:100;left:50%;top:17%;width:min(520px,calc(100vw - 26px));max-height:min(720px,82vh);background:#fffaf1;border:1px solid #bca37e;box-shadow:0 24px 70px #111c2977;border-radius:10px;display:flex;flex-direction:column;overflow:hidden;color:#213240}.floating[hidden]{display:none}.floating-header{display:flex;align-items:center;gap:10px;padding:10px 11px;background:#172c40;color:#f4e8d2;border-bottom:1px solid #9d825d;cursor:grab;touch-action:none;user-select:none}.floating-header:active{cursor:grabbing}.floating-header span{font:700 10px system-ui;letter-spacing:.13em;color:#debf91;flex:1}.floating-header button{font:700 12px system-ui;border:1px solid #758ba0;background:#253c4e;color:#fff1d9;border-radius:5px;padding:6px 10px}.floating-content{overflow:auto;padding:22px 25px 26px}.floating-content h2{font:normal 28px/1.2 Georgia,serif;color:#1f3649;margin:9px 0 15px}.floating-content p{font:15px/1.7 Georgia,serif;color:#40525d}.floating-content .tag{color:#886442}.floating-content .detail-link{display:inline-block;border:1px solid #bd9f72;border-radius:5px;color:#6b4f32;background:#f8efdf;text-decoration:none;padding:8px 12px;margin:10px 10px 0 0;font:700 12px system-ui}.floating-content .detail-link:hover{background:#e7d3b3}.floating-content .back{font:13px/1.7 system-ui;color:#4f5d66}.floating-content .back p{font:13px/1.6 system-ui;color:#4f5d66;overflow-wrap:anywhere}
[hidden]{display:none!important}
@media(max-width:820px){:root{--rail:120px}.chronicle{gap:9px;padding:16px 9px 65px}.war-track:before{font-size:8px;padding:5px}.war-period{left:0;right:3px;padding:7px 4px}.war-period .war-label{font-size:11px}.war-period .war-dates{font-size:9px}.war-period .war-duration{font-size:8px}.event-main{padding:11px}.events{padding-left:16px}.event:before{left:-25px}.topbar{position:static}.filterbar{top:0}.floating{left:14px;top:9%;width:calc(100vw - 28px)}.hero{padding:35px 17px}.people-note{padding:10px}.historian-footer{padding:20px 17px}}

.reading-bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;background:#f2ebde;padding:12px max(15px,calc((100vw - 1320px)/2));font:600 12px system-ui;color:#253b48;border-bottom:1px solid var(--line)}
.reading-bar select,.reading-bar input,.reading-bar button{background:#fffdfa;color:#253b48;border:1px solid #b8a88e;padding:7px;border-radius:5px;font:600 12px system-ui}.reading-bar input{width:80px}.reading-bar small{font-size:11px;color:#74695d}.reading-bar #reading-count{margin-right:auto;color:#416472}
.month-heading{padding:12px 3px 0;margin-top:8px}.month-heading h3{font:normal 20px Georgia,serif;color:#7b5c3e;margin:0 0 5px}.month-lead,.year-overview{display:none;background:#f3ebdf;padding:12px 18px;border-left:3px solid #bd945f;margin:7px 0 9px;color:#354954}.month-lead p,.year-overview p{margin:0 0 8px}.month-lead p:last-child,.year-overview p:last-child{margin:0}
body[data-reading="highlights"] .month-lead,body[data-reading="highlights"] .year-overview{display:block}body[data-reading="standard"] .month-lead{display:block}
.chapter-title{padding:4px 9px;border:1px dashed #bd9d75;border-radius:5px;background:transparent;color:#755639;font:600 11px system-ui;max-width:65%;overflow-wrap:anywhere}.pin-indicator{display:inline-block;border-radius:12px;color:#72502a;background:#fff3d0;padding:2px 6px;font:700 10px system-ui;margin-left:7px}.date-evidence{font:700 12px system-ui;color:#227b77}
.personal-notes{padding:0 25px 20px;border-top:1px solid #cfbaa3}.personal-notes label{display:block;font:700 12px system-ui;margin:10px 0;color:#65472d}.personal-notes textarea{width:100%;padding:8px;background:#fff;color:#253b48;border:1px solid #ab967a;border-radius:4px;font:13px/1.6 system-ui}.personal-notes .note-actions{display:flex;gap:9px;margin:8px 0}.personal-notes button{border:1px solid #a59174;background:#f5ecd9;color:#3c4b50;padding:7px;border-radius:5px}.personal-notes small{font:11px system-ui;color:#52636d}
@media(max-width:820px){.reading-bar{padding:10px 15px}.reading-bar #reading-count{flex-basis:100%}}
@media print{.reading-bar,.chapter-title,.pin-indicator,.personal-notes{display:none!important}.month-lead,.year-overview{background:#fff!important;color:#222!important}.month-heading h3{color:#444!important}}
@media print{@page{size:A4 portrait;margin:14mm 14mm 18mm;@top-left{content:none}@top-right{content:none}@bottom-left{content:none}@bottom-center{content:"Stellaris Historian · PillBoxUK · github.com/PillBoxUK/Stellaris-Historian";font:8pt Georgia,serif;color:#777}@bottom-right{content:none}}.topbar,.filterbar,.floating,.event-open small{display:none!important}body{background:#fff;color:#222}.hero{background:none;color:#222;padding:8px 0 17px}.hero:before{display:none}.hero h1{color:#252525}.hero p,.hero .subtitle,.kicker{color:#555}.chronicle{grid-template-columns:95px 1fr;padding:0;gap:9px}.war-track{border-right-color:#aaa}.war-period{background:#faf1dd;color:#443025;border-color:#a08055;box-shadow:none}.year{break-inside:auto}.year-heading{break-after:avoid-page}.event{break-inside:avoid-page}.year-heading span{color:#7e5d3f}.event-main{box-shadow:none;background:#fff;border-color:#bbb}.event-open strong{color:#222}.event-summary{color:#555}.date{color:#7e5d3f}.historian-footer{color:#333;background:#fff;border-top:1px solid #b69c74;padding:12px 0;break-inside:avoid-page}.historian-footer strong{color:#333}.historian-footer a{color:#55402b}.historian-footer small{color:#666}.milestone-tag{border-color:#c4ad80}.people-note{display:none!important}.event-open{color:#222!important}.event-summary{color:#333!important}.event-main{background:#fff!important;color:#222!important}.event .date{color:#70502b!important}.tag{background:#fff!important;color:#574d45!important}.milestone-tag{background:#fff!important;color:#755022!important}.event{break-inside:avoid;page-break-inside:avoid}.hero h1{color:#1c3141!important}.hero{background:#fff!important}}
"""

_TIMELINE_JS = r"""
(() => {
'use strict';
const dataset = JSON.parse(document.getElementById('chronicle-data').textContent);
const q = id => document.getElementById(id);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pad = v => String(v).padStart(2,'0');
const dateParts = d => d.split('.').map(Number);
const years = [...document.querySelectorAll('.year')];
const entries = [...document.querySelectorAll('.event')];
const buttons = [...document.querySelectorAll('[data-filter]')];
const popup = q('floating');
const noteBox=q('personal-notes');
const storageKey='historian.annals.personal.v090.'+String(dataset.campaign_id);
let personal={notes:{},pins:{},chapters:{},level:'standard'};
try { const saved=JSON.parse(localStorage.getItem(storageKey)||'null');
  if(saved && typeof saved==='object') personal={...personal,...saved}; } catch (_) { /* no browser storage: view still works */ }
function persist(){try{localStorage.setItem(storageKey,JSON.stringify(personal));}catch(_){q('note-save').textContent='Storage unavailable — export notes';}}
const eventKey=d=>[d.date,d.category,d.title,d.leader??'',d.war_id??''].join('|');
const isPinned=d=>Boolean(personal.pins?.[eventKey(d)]);
let readLevel=['highlights','standard','complete'].includes(personal.level)?personal.level:'standard';
q('reading-level').value=readLevel;
let selected = null, back = false, lastFocus = null, offsetX = 0, offsetY = 0, dragging = false, railOn = true;
function renderCard(){
  if (!selected) return;
  const d = selected.item;
  if (selected.type === 'war') {
    const related=dataset.events.filter(ev=>ev.war_id!=null && String(ev.war_id)===String(d.id));
    const chronology=related.length ? `<h3>Related dated developments</h3><ol>${related.map(ev=>`<li><strong>${esc(ev.date)}</strong> — ${esc(ev.title)} <small>(${esc(ev.date_label)})</small></li>`).join('')}</ol>` : '<p>No matching dated entries could be linked safely to this conflict.</p>';
    q('floating-content').innerHTML = back ? `<div class="back"><h2>War chronology</h2><p>War #${esc(d.id)}</p><p>First observed: ${esc(d.first_observed)}<br>Native start: ${esc(d.start)}<br>Last observed: ${esc(d.last)}<br>First absent: ${esc(d.first_absent||'Not observed')}</p><p>No unverified outcome or peace date is asserted.</p></div>` : `<span class="tag">War period</span><h2>${esc(d.title)}</h2><p>${esc(d.start)} — ${esc(d.last)}</p>${chronology}<a class="detail-link" href="/war-journal#war-${encodeURIComponent(d.id)}">Open War Journal ↗</a>`;
  } else {
    const link = d.war_id != null ? `/war-journal#war-${encodeURIComponent(d.war_id)}` : d.leader != null ? `/empire-archive?record=people:${encodeURIComponent(d.leader)}` : `/empire-archive?tab=${encodeURIComponent(d.category==='Expansion'?'worlds':['Military','Navy'].includes(d.category)?'ships':d.category==='Technology'?'research':'timeline')}&search=${encodeURIComponent(d.title)}`;
    const target = d.source==='annual_government_census' ? '/government-census#census-'+encodeURIComponent(d.date.slice(0,4)) : d.category==='Technology' ? '/research-history' : link;
    // Use the actual saved leader identifier, never a same-name guess, to
    // assemble related dated entries already present in this chronology.
    const related=(d.leader!=null ? dataset.events.filter(x=>x.leader!=null && String(x.leader)===String(d.leader) && x!==d) : []);
    const relatedHtml=related.length ? `<details><summary>Other dated entries for this person (${related.length})</summary><ol>${related.slice(0,80).map(x=>`<li>${esc(x.date)} — ${esc(x.title)}</li>`).join('')}</ol></details>` : '';
    q('floating-content').innerHTML = back ? `<div class="back"><h2>Dating and evidence</h2><p>${esc(d.evidence)}</p><p>Date: ${esc(d.date)}<br>Category: ${esc(d.category)}</p><p>${esc(d.date_explanation)}</p><p>These notes document the source and its dating limitations; personal annotations never alter the archival evidence.</p></div>` : `<span class="tag">${esc(d.category)}</span><h2>${esc(d.title)}</h2><p><span class="date-evidence">${esc(d.date_label)}: ${esc(d.date)}</span></p><p>${esc(d.body)}</p>${relatedHtml}<a class="detail-link" href="${target}">Related archive ↗</a>`;
  }
  q('card-flip').textContent = back ? 'Front ↻' : 'Flip ↻';
}
function show(type,item,origin){selected={type,item};back=false;lastFocus=origin||document.activeElement;popup.hidden=false;popup.style.left='';popup.style.top='';
  noteBox.hidden=type!=='event'; if(type==='event'){q('note-text').value=String(personal.notes?.[eventKey(item)]||'');q('note-pin').textContent=isPinned(item)?'Unpin event':'Pin event';}
  renderCard();q('card-close').focus()}
function close(){popup.hidden=true;selected=null;if(lastFocus?.isConnected)lastFocus.focus()}
q('card-close').addEventListener('click',close);
q('card-flip').addEventListener('click',()=>{back=!back;renderCard()});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!popup.hidden)close()});
entries.forEach(el=>el.querySelector('[data-event]')?.addEventListener('click',e=>show('event',dataset.events[Number(e.currentTarget.dataset.event)],e.currentTarget)));
q('note-save').addEventListener('click',()=>{if(selected?.type!=='event')return;const key=eventKey(selected.item),value=q('note-text').value.trim();
  if(value)personal.notes[key]=value;else delete personal.notes[key];persist();q('note-save').textContent='Saved in browser';});
q('note-pin').addEventListener('click',()=>{if(selected?.type!=='event')return;const key=eventKey(selected.item);
  if(isPinned(selected.item))delete personal.pins[key];else personal.pins[key]=true;
  persist();q('note-pin').textContent=isPinned(selected.item)?'Unpin event':'Pin event';apply(document.querySelector('[data-filter].active')?.dataset.filter||'All');});
document.querySelectorAll('[data-chapter-year]').forEach(b=>{
  const year=b.dataset.chapterYear;
  function redraw(){b.textContent=personal.chapters?.[year]?'✎ '+personal.chapters[year]:'+ Chapter title';}
  redraw();b.addEventListener('click',()=>{const title=window.prompt('Your chapter title for '+year+' (personal note, not historical evidence):',personal.chapters?.[year]||'');
    if(title===null)return;const value=title.trim().slice(0,120);if(value)personal.chapters[year]=value;else delete personal.chapters[year];persist();redraw();});
});
function pos(date,ending=false){
 const [year,month,day]=dateParts(date);const sec=q('year-'+year);if(!sec)return null;
 const markers=[...sec.querySelectorAll('.event')].filter(e=>!e.hidden);
 const matching=markers.find(e=>e.dataset.date >= date);
 const heading=sec.querySelector('.year-heading');
 const railRect=q('war-track').getBoundingClientRect();
 const node = matching || (ending && markers.length ? markers[markers.length-1] : heading);
 return node.getBoundingClientRect().top - railRect.top + (node===heading?32:12);
}
function renderWars(){
 const rail=q('war-track');rail.innerHTML='';rail.hidden=!railOn;
 if(!railOn)return;
 // Greedy non-overlap: shorter conflicts are moved right only when possible.
 dataset.wars.forEach(w=>{
   const top=pos(w.start),end=pos(w.last,true);
   if(top==null||end==null)return;
   const span=Math.max(35,end-top+18);
   const el=document.createElement('button');el.type='button';el.className='war-period'+(span<150?' compact':'')+(span<80?' short':'');
   el.style.top=top+'px';el.style.height=span+'px';
   el.setAttribute('aria-label',w.title+' '+w.start+' to '+w.last);
   el.innerHTML=`<span class="war-label">${esc(w.title)}</span><span class="war-dates">${esc(w.start)} → ${esc(w.last)}</span>${span>170?'<span class="war-duration">Conflict continued</span>':''}`;
   el.addEventListener('click',()=>show('war',w,el));rail.append(el)
 });
}
function apply(filter){
 buttons.forEach(b=>b.classList.toggle('active',b.dataset.filter===filter));
 let displayed=0;
 document.body.dataset.reading=readLevel;
 entries.forEach(e=>{const ev=dataset.events[Number(e.dataset.eventIndex)];
  const categoryOK=filter==='All'||(filter==='Milestones'?e.dataset.milestone==='true':e.dataset.category===filter);
  const importance=Number(e.dataset.importance);
  const levelOK=readLevel==='complete'||isPinned(ev)||e.dataset.milestone==='true'||importance>=(readLevel==='highlights'?80:40);
  e.hidden=!(categoryOK && levelOK);
  if(!e.hidden)displayed++;
  const mark=e.querySelector('.pin-indicator');if(mark)mark.hidden=!isPinned(ev);
 });
 years.forEach(y=>{const hasEvents=[...y.querySelectorAll('.event')].some(e=>!e.hidden);
  const year=Number(y.dataset.year),warYear=railOn&&dataset.wars.some(w=>Number(w.start.slice(0,4))<=year&&Number(w.last.slice(0,4))>=year);
  y.hidden=!hasEvents&&!warYear;
  y.querySelectorAll('.month-heading').forEach(h=>{let sib=h.nextElementSibling,visible=false;
    while(sib&&!sib.classList.contains('month-heading')){if(sib.classList.contains('event')&&!sib.hidden)visible=true;sib=sib.nextElementSibling;}
    h.hidden=!visible;});
 });
 q('reading-count').textContent=displayed+' of '+entries.length+' entries shown';
 renderWars();
}
buttons.forEach(b=>b.addEventListener('click',()=>apply(b.dataset.filter)));
q('reading-level').addEventListener('change',()=>{readLevel=q('reading-level').value;personal.level=readLevel;persist();apply(document.querySelector('[data-filter].active')?.dataset.filter||'All');});
function exportChapters(){
 const validYear=v=>/^\d{1,5}$/.test(String(v));
 const first=String(q('export-start').value||dataset.first_date.slice(0,4));
 const last=String(q('export-end').value||dataset.latest_date.slice(0,4));
 if(!validYear(first)||!validYear(last)||Number(first)>Number(last)){alert('Choose a valid beginning and ending year.');return;}
 const inRange=dataset.events.filter(d=>{const year=Number(d.date.slice(0,4));return year>=Number(first)&&year<=Number(last);});
 if(!inRange.length){alert('There are no dated entries for the selected years.');return;}
 const yearSet=[...new Set(inRange.map(d=>d.date.slice(0,4)))];
 const chapters=yearSet.map(y=>{const evs=inRange.filter(d=>d.date.startsWith(y+'.'));
  return `<section><h2>${esc(y)}${personal.chapters?.[y]?' — '+esc(personal.chapters[y]):''}</h2>${evs.map(d=>`<article><h3>${esc(d.title)}</h3><small>${esc(d.date)} · ${esc(d.category)} · ${esc(d.date_label)}</small><p>${esc(d.body)}</p>${personal.notes?.[eventKey(d)]?`<aside><strong>PERSONAL ANNOTATION — NOT SOURCE EVIDENCE</strong><p>${esc(personal.notes[eventKey(d)])}</p></aside>`:''}</article>`).join('')}</section>`;}).join('');
 const out=`<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Stellaris Historian — ${esc(first)}–${esc(last)}</title><style>body{font:17px/1.6 Georgia,serif;max-width:830px;margin:40px auto;padding:0 18px;color:#162b3b;background:#fff}h1,h2{color:#175a65}h2{border-bottom:1px solid #aaa;margin-top:42px}article{margin:20px 0;break-inside:avoid}small{color:#54636a}aside{background:#fff6e6;border-left:4px solid #a77b37;padding:10px 16px}footer{border-top:1px solid #999;margin-top:40px;font-size:12px}@media print{body{margin:0;max-width:none}}</style></head><body><h1>Historical chapters · ${esc(first)}–${esc(last)}</h1><p>Source: Stellaris Historian's archived Ironman evidence. Event dating labels preserve source limitations. Personal annotations, if any, are clearly separate.</p>${chapters}<footer>Unofficial fan project by PillBoxUK. Exported from the local Imperial Annals. Not affiliated with Paradox Interactive.</footer></body></html>`;
 const blob=new Blob([out],{type:'text/html;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='Historian_Chapters_'+first+'-'+last+'.html';a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);
}
q('export-html').addEventListener('click',exportChapters);
q('war-toggle').addEventListener('click',()=>{railOn=!railOn;q('war-toggle').setAttribute('aria-pressed',String(railOn));q('war-toggle').textContent='War periods '+(railOn?'✓':'—');apply(document.querySelector('[data-filter].active')?.dataset.filter||'All')});
q('print').addEventListener('click',()=>{renderWars();window.print()});
q('year-go').addEventListener('click',()=>{const y=Number(q('jump-year').value);if(Number.isInteger(y)){q('year-'+y)?.scrollIntoView({behavior:'smooth',block:'start'});}});
q('jump-year').addEventListener('keydown',e=>{if(e.key==='Enter')q('year-go').click()});
window.addEventListener('resize',()=>renderWars());
window.addEventListener('beforeprint',()=>renderWars());
const head=q('floating-header');
head.addEventListener('pointerdown',e=>{if(e.target.closest('button')||e.button!==0)return;const rect=popup.getBoundingClientRect();dragging=true;offsetX=e.clientX-rect.left;offsetY=e.clientY-rect.top;head.setPointerCapture(e.pointerId);e.preventDefault()});
head.addEventListener('pointermove',e=>{if(!dragging)return;popup.style.left=Math.max(0,Math.min(innerWidth-popup.offsetWidth,e.clientX-offsetX))+'px';popup.style.top=Math.max(0,Math.min(innerHeight-70,e.clientY-offsetY))+'px'});
head.addEventListener('pointerup',()=>{dragging=false});head.addEventListener('pointercancel',()=>{dragging=false});
requestAnimationFrame(()=>apply(location.hash==='#milestones'?'Milestones':'All')); 
})();
"""