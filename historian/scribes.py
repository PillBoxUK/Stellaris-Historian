from __future__ import annotations

from html import escape
from pathlib import Path, PureWindowsPath
import json
import os
import re
import tempfile

from .db import Database
from .localisation import resolve_origin_lore
from .save_reader import read_empire_profile
from .domains.science.history import derive_science_interpretation
from .domains.science.journal import _cache_science_snapshots
from .domains.combat import CACHE_COMPONENT_NAME as COMBAT_COMPONENT_NAME, CACHE_COMPONENT_VERSION as COMBAT_COMPONENT_VERSION
from .domains.combat.cache import snapshot_from_dict as combat_snapshot_from_dict
from .domains.ships import CACHE_COMPONENT_NAME as SHIP_COMPONENT_NAME, CACHE_COMPONENT_VERSION as SHIP_COMPONENT_VERSION
from .domains.ships.cache import snapshot_from_dict as ship_snapshot_from_dict
from .domains.technology import (
    CACHE_COMPONENT_NAME as TECHNOLOGY_COMPONENT_NAME,
    CACHE_COMPONENT_VERSION as TECHNOLOGY_COMPONENT_VERSION,
    derive_technology_history,
)
from .domains.technology.cache import snapshot_from_dict as technology_snapshot_from_dict
from .historical_events import HistoricalEvent
from .presentation_history import build_presentation_history


_RED_GIANT_PROJECT_KEYS = {
    "INF_ORIGIN_RED_GIANT_TRIANGULATION",
    "INF_ORIGIN_RED_GIANT_PROTECT_HOMEWORLD",
    "INF_ORIGIN_RED_GIANT_PARLAY",
    "INF_ORIGIN_RED_GIANT_BOARD_STATION",
}
_RED_GIANT_SITUATION_KEY = "situation_red_giant_expansion"


def scribes_path(db: Database, campaign_id: int) -> Path:
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist.")
    return Path(campaign["archive_dir"]) / "Scribes_Chronicle.html"




def scribes_pdf_path(db: Database, campaign_id: int) -> Path:
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist.")
    return Path(campaign["archive_dir"]) / "Scribes_Chronicle.pdf"


def _local_archive_dir(db: Database, campaign) -> Path:
    configured = Path(str(campaign["archive_dir"]))
    if configured.exists():
        return configured
    name = PureWindowsPath(str(campaign["archive_dir"])).name
    fallback = db.path.parent / "campaigns" / name
    return fallback if fallback.exists() else configured


def _cached_component_snapshots(
    db: Database,
    campaign_id: int,
    *,
    component_name: str,
    component_version: int,
    loader,
) -> list:
    """Read one evidence component from persistent snapshot caches.

    Scribes never reparses raw saves silently. If a new component has not yet
    been populated, Review Campaign remains the explicit evidence-building step.
    """
    campaign = db.campaign(campaign_id)
    if campaign is None:
        return []
    cache_dir = _local_archive_dir(db, campaign) / ".historian_cache"
    if not cache_dir.exists():
        return []

    result = []
    for snapshot in db.all_snapshots(campaign_id):
        path = cache_dir / f"{snapshot['sha256']}.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        component = payload.get("components", {}).get(component_name, {})
        if component.get("version") != component_version:
            continue
        data = component.get("data")
        if not isinstance(data, dict):
            continue
        try:
            result.append(loader(data, snapshot_id=int(snapshot["id"])))
        except (KeyError, TypeError, ValueError):
            continue
    return result


def _cached_combat_snapshots(db: Database, campaign_id: int):
    return _cached_component_snapshots(
        db,
        campaign_id,
        component_name=COMBAT_COMPONENT_NAME,
        component_version=COMBAT_COMPONENT_VERSION,
        loader=combat_snapshot_from_dict,
    )


def _cached_technology_snapshots(db: Database, campaign_id: int):
    return _cached_component_snapshots(
        db,
        campaign_id,
        component_name=TECHNOLOGY_COMPONENT_NAME,
        component_version=TECHNOLOGY_COMPONENT_VERSION,
        loader=technology_snapshot_from_dict,
    )


def _cached_ship_snapshots(db: Database, campaign_id: int):
    return _cached_component_snapshots(
        db,
        campaign_id,
        component_name=SHIP_COMPONENT_NAME,
        component_version=SHIP_COMPONENT_VERSION,
        loader=ship_snapshot_from_dict,
    )


def _ruler_observations(db: Database, campaign_id: int) -> list[tuple[str, dict]]:
    """Return dated ruler observations from the parsed leader cache.

    This is deliberately evidence-led: the chapter signatory is the ruler
    recorded in the closest archived state on or before the chapter's anchor
    date. No title, succession cause or personal words are invented.
    """
    campaign = db.campaign(campaign_id)
    if campaign is None:
        return []

    cache_dir = _local_archive_dir(db, campaign) / ".historian_cache"
    observations: list[tuple[str, dict]] = []
    if cache_dir.exists():
        for snapshot in db.all_snapshots(campaign_id):
            path = cache_dir / f"{snapshot['sha256']}.json"
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            data = payload.get("components", {}).get("leaders", {}).get("data", {})
            leaders = data.get("leaders", {})
            if not isinstance(leaders, dict):
                continue
            rulers = [value for value in leaders.values() if isinstance(value, dict) and value.get("is_ruler")]
            if not rulers:
                continue
            ruler = dict(rulers[0])
            ruler["observed_game_date"] = str(snapshot["game_date"])
            observations.append((str(snapshot["game_date"]), ruler))

    if observations:
        return observations

    # Fallback is intentionally limited to the current ruler. This keeps a
    # copied database readable even when its parsed cache is unavailable, but
    # does not project a later ruler backwards through historical chapters.
    latest = next((row for row in db.leader_registry(campaign_id) if row["latest_is_ruler"]), None)
    if latest is not None:
        return [(str(campaign["latest_game_date"]), {
            "leader_id": int(latest["leader_id"]),
            "name": str(latest["name"]),
            "leader_class": str(latest["leader_class"]),
            "observed_game_date": str(campaign["latest_game_date"]),
        })]
    return []


def _ruler_for_date(observations: list[tuple[str, dict]], game_date: str | None) -> dict | None:
    if not observations or not game_date:
        return None
    eligible = [item for item in observations if item[0] <= str(game_date)]
    if eligible:
        return eligible[-1][1]
    return None


def _authority_html(ruler: dict | None, empire_name: str, anchor_date: str | None) -> str:
    if not ruler:
        return ""
    year = _year(anchor_date)
    return f"""
      <div class="authority">
        <div class="authority-kicker">Set down in the Chronicle by</div>
        <div class="authority-name">{_e(ruler.get('name') or 'Unnamed Ruler')}</div>
        <div class="authority-role">Ruler of {_e(empire_name)}</div>
        <div class="authority-date">Signed to the surviving record · {_e(year)}</div>
      </div>
    """


def _sign_chapter(chapter_html: str, authority_html: str) -> str:
    if not authority_html:
        return chapter_html
    return chapter_html.replace("    </section>", authority_html + "\n    </section>", 1)


def _final_note_html(latest_date: str) -> str:
    return f"""
      <div class="final-note">
        <div class="final-note-title">The final page is left unsigned.</div>
        <p>The surviving archive ends on {_e(latest_date)}, but the civilization does not. This is not a declaration of an ending; it is only the present edge of the record. The next hand to sign these pages belongs to history yet unwritten.</p>
      </div>
    """


def _chapter_parts(chapter_html: str) -> tuple[str, str, list[str]]:
    from html import unescape

    title_match = re.search(r"<h2>(.*?)</h2>", chapter_html, flags=re.S)
    subtitle_match = re.search(r'<div class="chapter-subtitle">(.*?)</div>', chapter_html, flags=re.S)
    paragraphs = re.findall(r"<p(?: class=\"lead\")?>(.*?)</p>", chapter_html, flags=re.S)

    def clean(value: str) -> str:
        value = re.sub(r"<[^>]+>", "", value)
        return unescape(value).strip()

    return (
        clean(title_match.group(1)) if title_match else "Chronicle",
        clean(subtitle_match.group(1)) if subtitle_match else "",
        [clean(value) for value in paragraphs],
    )


def _combat_anchor_date(combat_snapshots) -> str | None:
    dates: list[str] = []
    for snapshot in combat_snapshots:
        for war in snapshot.wars.values():
            if war.start_date:
                dates.append(str(war.start_date))
        for battle in snapshot.battles.values():
            if battle.date:
                dates.append(str(battle.date))
        dates.extend(str(row.last_combat_activity) for row in snapshot.ship_activity.values())
        dates.extend(str(row.last_combat_activity) for row in snapshot.starbase_activity.values())
    return max(dates) if dates else None


def _technology_anchor_date(technology_snapshots) -> str | None:
    history = derive_technology_history(technology_snapshots) if technology_snapshots else None
    events = history.get("events", []) if history else []
    if events:
        return max(str(row.game_date) for row in events)
    if technology_snapshots:
        return max(str(row.game_date) for row in technology_snapshots)
    return None


def _chapter_authority_dates(
    campaign,
    worlds,
    leaders,
    ship_events,
    combat_snapshots,
    technology_snapshots,
) -> list[str | None]:
    first = str(campaign["first_game_date"] or "")
    latest = str(campaign["latest_game_date"] or first)
    colony_dates = [
        str(row["colonize_date"] or row["first_seen_date"])
        for row in worlds
        if not row["baseline_present"]
    ]
    expansion = max(colony_dates) if colony_dates else first
    people_dates = [str(row["last_seen_date"]) for row in leaders if row["last_seen_date"]]
    people = max(people_dates) if people_dates else latest
    ship_dates = [str(row["game_date"]) for row in ship_events if row["game_date"]]
    ships = max(ship_dates) if ship_dates else latest
    combat = _combat_anchor_date(combat_snapshots) or latest
    technology = _technology_anchor_date(technology_snapshots) or latest
    return [first, expansion, people, ships, combat, technology, latest, None]


def _e(value) -> str:
    return escape("" if value is None else str(value))


def _year(value: str | None) -> str:
    if not value:
        return "an uncertain year"
    return str(value).split(".", 1)[0]


def _natural_date(value: str | None) -> str:
    if not value:
        return "an uncertain date"
    bits = str(value).split(".")
    if len(bits) != 3:
        return str(value)
    year, month, day = bits
    try:
        month_i = int(month)
        day_i = int(day)
    except ValueError:
        return str(value)
    months = (
        "first", "second", "third", "fourth", "fifth", "sixth",
        "seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth",
    )
    if 1 <= month_i <= 12:
        if 10 <= day_i % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(day_i % 10, "th")
        return f"the {day_i}{suffix} day of the {months[month_i - 1]} month, {year}"
    return str(value)




def _small_number(value: int) -> str:
    words = {
        0: "no", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
        6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
    }
    return words.get(value, str(value))

def _join_words(values: list[str]) -> str:
    values = [value for value in values if value]
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return ", ".join(values[:-1]) + f", and {values[-1]}"


def _clean_traits(raw: str | None) -> list[str]:
    try:
        values = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or "[" in text or "]" in text:
            continue
        if text in {"Advisor", "Official", "Scientist", "Commander"}:
            continue
        text = re.sub(r"\s+II$", "", text)
        text = re.sub(r"\s+2$", "", text)
        if text not in result:
            result.append(text)
    return result


def _opening_origin_lore(db: Database, campaign_id: int) -> dict | None:
    campaign = db.campaign(campaign_id)
    snapshots = db.all_snapshots(campaign_id)
    if campaign is None or not snapshots:
        return None

    start = next((row for row in snapshots if row["kind"] == "start"), snapshots[0])
    try:
        profile = read_empire_profile(Path(start["archive_path"]))
    except Exception:
        return None

    try:
        return resolve_origin_lore(Path(campaign["source_save"]), profile.origin)
    except Exception:
        return None


def _paragraph(text: str, *, lead: bool = False) -> str:
    cls = ' class="lead"' if lead else ""
    return f"<p{cls}>{_e(text)}</p>"


def _chapter(chapter_id: str, number: str, title: str, subtitle: str, paragraphs: list[str]) -> str:
    body = "".join(_paragraph(p, lead=(index == 0)) for index, p in enumerate(paragraphs) if p)
    return f"""
    <section class="chapter" id="{_e(chapter_id)}">
      <div class="chapter-number">{_e(number)}</div>
      <h2>{_e(title)}</h2>
      <div class="chapter-subtitle">{_e(subtitle)}</div>
      <div class="prose">{body}</div>
    </section>
    """


def _opening_chapter(db: Database, campaign_id: int, campaign, founding, worlds, leaders, fleets) -> str:
    first = campaign["first_game_date"] or (founding[0]["game_date"] if founding else "2200.01.01")
    entry = founding[0] if founding else None
    capital = next((row for row in worlds if row["latest_is_capital"]), worlds[0] if worlds else None)
    opening_fleets = [row for row in fleets if row["baseline_present"]]
    opening_leaders = [row for row in leaders if row["baseline_present"]]
    lore = _opening_origin_lore(db, campaign_id)

    paragraphs: list[str] = []
    if entry is not None:
        government = entry["government_type"] or entry["authority"] or "state"
        origin = entry["origin"] or "an origin the surviving record does not name"
        ethics = entry["ethics"]
        civics = entry["civics"]
        seat = f" on {capital['name']} in the {capital['system_name']} system" if capital else ""
        paragraphs.append(
            f"Our surviving chronicle begins in {first}. It does not record a beginning in the mythic sense; it simply opens and finds {campaign['empire_name']} already there{seat}, ordered as a {government}. The oldest record names its origin as {origin}."
        )
        if ethics or civics:
            qualities = []
            if ethics:
                qualities.append(f"its ethic was recorded as {ethics}")
            if civics:
                qualities.append(f"its civic order was recorded as {civics}")
            paragraphs.append(
                "The archive is unusually plain about what the Convocation believed itself to be: " + ", while ".join(qualities) + ". These are dry words, but they are the first surviving shape of the society that followed."
            )
    else:
        paragraphs.append(
            f"The surviving record of {campaign['empire_name']} opens in {first}. What came before is beyond the present archive."
        )

    if lore and lore.get("description"):
        desc = " ".join(part.strip() for part in str(lore["description"]).splitlines() if part.strip())
        paragraphs.append(
            f"The origin tradition gives those first years their urgency. It remembers this: {desc}"
        )

    if opening_fleets:
        military = [row for row in opening_fleets if row["ship_class"] == "shipclass_military"]
        science = [row for row in opening_fleets if row["ship_class"] == "shipclass_science_ship"]
        construction = [row for row in opening_fleets if row["ship_class"] == "shipclass_constructor"]
        pieces = []
        if military:
            pieces.append(f"a military force already stood under the name {military[0]['opening_name'] or military[0]['name']}")
        if science:
            pieces.append("a science vessel was already ranging beyond the homeworld")
        if construction:
            pieces.append("a construction vessel waited to turn surveyed space into possession")
        if pieces:
            paragraphs.append(
                "Nor was the Convocation motionless. At the opening of the rolls, " + _join_words(pieces) + ". The empire's first surviving page is therefore not a still portrait, but the opening frame of movement."
            )

    ruler = next((row for row in opening_leaders if row["ever_ruler"]), None)
    if ruler:
        traits = _clean_traits(ruler["trait_names"])
        if traits:
            paragraphs.append(
                f"At the centre of that early order stood {ruler['name']}. Later service records would attach a striking mixture of qualities to the ruler—{_join_words(traits[:5])}. Whether later generations judged those qualities kindly is not preserved here; only that the record itself remembered them."
            )
        else:
            paragraphs.append(f"At the centre of that early order stood {ruler['name']}, already present when the surviving record begins.")

    return _chapter(
        "chapter-opening",
        "I",
        "Beneath the Old Sun",
        f"The surviving record opens in {first}",
        paragraphs,
    )


def _expansion_chapter(campaign, worlds) -> str:
    paragraphs: list[str] = []
    capital = next((row for row in worlds if row["baseline_present"] and row["latest_is_capital"]), None)
    colonies = sorted(
        [row for row in worlds if not row["baseline_present"]],
        key=lambda row: (row["colonize_date"] or row["first_seen_date"], row["name"]),
    )

    if capital:
        paragraphs.append(
            f"For all the later reach of the Convocation, the record keeps returning to {capital['name']}, the {capital['planet_class_name'] or 'homeworld'} of the {capital['system_name'] or 'home'} system. By {campaign['latest_game_date']}, it was still the capital, governed by {capital['latest_governor_name'] or 'an unnamed office'} and bearing the designation {capital['latest_designation_name'] or 'capital world'}."
        )

    if colonies:
        for index, row in enumerate(colonies):
            founded = row["colonize_date"] or row["first_seen_date"]
            designation = row["latest_designation_name"] or "colony"
            governor = row["latest_governor_name"]
            class_name = row["planet_class_name"] or "world"
            if index == 0:
                text = (
                    f"The first great outward step preserved by the archive came on {_natural_date(founded)}, when {row['name']} was founded in the {row['system_name'] or 'unresolved'} system. It was a {class_name}; in the later record it had become a {designation}."
                )
            else:
                text = (
                    f"Then came {row['name']}. The colonial rolls preserve its founding date as {_natural_date(founded)}, in the {row['system_name'] or 'unresolved'} system. The later rolls call it a {designation} on a world classified as {class_name}."
                )
            if governor:
                text += f" By the end of the surviving record, {governor} was attached to its governance."
            paragraphs.append(text)

        paragraphs.append(
            f"Thus the realm visible to this archive grew from one inhabited world to {_small_number(len(worlds))}. It is a small number on a galactic map, but historical scale is not measured only in stars: each colony meant distance made routine, supply made possible, and another place from which the Convocation could imagine a future."
        )
    else:
        paragraphs.append("The surviving record contains no securely established colonial founding beyond the opening world.")

    return _chapter(
        "chapter-expansion",
        "II",
        "The First Reach",
        "Worlds beyond the home system",
        paragraphs,
    )


def _people_chapter(campaign, leaders, career_events) -> str:
    paragraphs: list[str] = []
    ruler = next((row for row in leaders if row["latest_is_ruler"]), None)
    commanders = sorted(
        [row for row in leaders if row["leader_class"] == "commander"],
        key=lambda row: (row["recruitment_date"] or row["first_seen_date"], row["name"]),
    )
    scientists = sorted(
        [row for row in leaders if row["leader_class"] == "scientist"],
        key=lambda row: (row["recruitment_date"] or row["first_seen_date"], row["name"]),
    )
    officials = [row for row in leaders if row["leader_class"] == "official" and not row["latest_is_ruler"]]
    envoys = [row for row in leaders if row["leader_class"] == "envoy"]
    missing = [row for row in leaders if row["status"] != "present"]

    events_by_leader: dict[int, list] = {}
    for event in career_events:
        events_by_leader.setdefault(int(event["leader_id"]), []).append(event)

    paragraphs.append(
        "Empires are easily reduced to borders and fleets. The surviving rolls resist that temptation. "
        "They preserve names—rulers, commanders, scientists, officials and envoys—appearing again and again across decades. "
        "Some carried armies and fleets; others carried instruments, messages or the burden of administration."
    )

    if ruler:
        traits = _clean_traits(ruler["trait_names"])
        trait_text = _join_words(traits[:6])
        sentence = (
            f"At the head of the surviving record stood {ruler['name']}. The ruler is present from "
            f"{_year(ruler['first_seen_date'])} through {campaign['latest_game_date']}."
        )
        if trait_text:
            sentence += f" The later rolls attach the qualities {trait_text} to that office and name."
        paragraphs.append(sentence)

    if commanders:
        paragraphs.append(
            "The military rolls preserve a smaller circle of commanders, and because their names recur beside fleets and years of fighting, "
            "they form the closest thing this archive has to a remembered general staff."
        )
        for row in commanders:
            service_date = row["recruitment_date"] or row["first_seen_date"]
            if row["baseline_present"]:
                text = f"{row['name']} belonged to the opening generation of command, already present in {_year(row['first_seen_date'])}."
            else:
                text = f"{row['name']} entered the command rolls in {_year(service_date)}."

            assignment = row["latest_assignment"]
            if assignment:
                clean_assignment = assignment.replace("Fleet: ", "").replace("Planet: ", "")
                if "Unnamed" not in clean_assignment:
                    text += f" In the later record, {row['name']} is attached to {clean_assignment}."

            leader_events = events_by_leader.get(int(row["leader_id"]), [])
            command_events = [
                event for event in leader_events
                if event["event_type"] == "leader_assignment_changed"
                and ("Command" in event["title"] or "Assignment Ended" in event["title"])
            ]
            if command_events:
                details = []
                for event in command_events[:4]:
                    title = str(event["title"])
                    title = title.replace(f"{row['name']} ", "")
                    title = title.replace(f"{row['name']}'s ", "")
                    details.append(f"{_year(event['game_date'])}: {title}")
                text += " Its surviving career markers include " + _join_words(details) + "."

            traits = _clean_traits(row["trait_names"])
            if traits:
                text += (
                    f" The qualities eventually attached to the name—{_join_words(traits[:5])}—"
                    "are enough to suggest a reputation, though not enough to invent a private character."
                )
            paragraphs.append(text)

    if scientists:
        paragraphs.append(
            "The scientific service was broader and, in places, more enduring. Its officers are followed not through legend but through vessels, excavations and long-running investigations."
        )
        for row in scientists:
            service_date = row["recruitment_date"] or row["first_seen_date"]
            if row["baseline_present"]:
                text = f"{row['name']} is already present when the archive opens in {_year(row['first_seen_date'])}."
            else:
                text = f"{row['name']} entered service in {_year(service_date)}."
            assignment = row["latest_assignment"]
            if assignment:
                text += f" The later rolls place {row['name']} with {assignment.replace('Science Ship: ', '').replace('Planet: ', '')}."
            traits = _clean_traits(row["trait_names"])
            if traits:
                text += f" The surviving service description includes {_join_words(traits[:5])}."
            if row["status"] == "dead_confirmed":
                death_events = [
                    event for event in events_by_leader.get(int(row["leader_id"]), [])
                    if event["event_type"] == "leader_death_recorded"
                ]
                if death_events:
                    death = death_events[-1]
                    text += f" The surviving rolls record the death on {_natural_date(death['game_date'])}."
                else:
                    text += " The surviving rolls record the leader as dead, though the death notice is not reproduced here."
            elif row["status"] != "present":
                text += (
                    f" The name is last confirmed in {_year(row['last_seen_date'])}; after that the record falls silent, "
                    "without establishing death, retirement or reassignment."
                )
            paragraphs.append(text)

    if officials:
        names = [row["name"] for row in officials[:6]]
        paragraphs.append(
            f"Civil administration was carried by figures including {_join_words(names)}. Their careers are less dramatic in the surviving pages, "
            "but governors, nodes and councillors gave continuity to worlds that the fleets could only reach."
        )

    if envoys:
        names = [row["name"] for row in envoys[:6]]
        paragraphs.append(
            f"Beyond the borders, {_join_words(names)} appear in the diplomatic and first-contact record. Their work is mostly preserved as assignment rather than speech, "
            "and the chronicle leaves their words unwritten where no words survive."
        )

    # Preserve confirmed deaths and unexplained departures once, even if mentioned above.
    non_scientist_missing = [row for row in missing if row["leader_class"] != "scientist"]
    for row in non_scientist_missing:
        if row["status"] == "dead_confirmed":
            death_events = [
                event for event in events_by_leader.get(int(row["leader_id"]), [])
                if event["event_type"] == "leader_death_recorded"
            ]
            if death_events:
                death = death_events[-1]
                paragraphs.append(
                    f"The surviving rolls record the death of {row['name']} on {_natural_date(death['game_date'])}."
                )
            else:
                paragraphs.append(
                    f"The surviving rolls record {row['name']} as dead, though the surviving chronicle does not reproduce the notice here."
                )
        else:
            paragraphs.append(
                f"{row['name']} is last confirmed in {_year(row['last_seen_date'])}; thereafter the name disappears from the surviving rolls. "
                "The reason is not recorded, and no later scribe can honestly supply it."
            )

    return _chapter(
        "chapter-people",
        "III",
        "Names in the Long Record",
        "Rulers, commanders, scientists and servants of the Convocation",
        paragraphs,
    )


def _ships_chapter(ships, fleets, ship_events) -> str:
    paragraphs: list[str] = []
    opening_ships = [row for row in ships if row["baseline_present"]]
    present_ships = [row for row in ships if row["status"] == "present"]
    commissioned = [row for row in ship_events if row["event_type"] == "ship_commissioned"]
    fleet_births = [row for row in ship_events if row["event_type"] == "fleet_first_observed"]
    refits = [row for row in ship_events if "refit" in row["event_type"] or row["event_type"] == "naval_modernisation_wave_observed"]

    military_opening = [row for row in fleets if row["baseline_present"] and row["ship_class"] == "shipclass_military"]
    if military_opening:
        fleet = military_opening[0]
        paragraphs.append(
            f"The navy does not begin in these pages with a grand armada. At the opening of the record, {fleet['opening_name'] or fleet['name']} held {fleet['opening_ship_count'] or fleet['latest_ship_count']} military vessels. Alongside them stood the scientific and construction craft that made expansion possible."
        )
    else:
        paragraphs.append(
            f"Only {len(opening_ships)} ships are preserved in the opening register. From that small beginning, the naval record becomes steadily more crowded."
        )

    early_commissioned = [row for row in commissioned if _year(row["game_date"]) <= "2210"]
    if early_commissioned:
        paragraphs.append(
            f"The first decade is full of new hulls. The surviving chronicle records {len(early_commissioned)} commissioned vessels between the opening years and 2210—science ships, constructors, colony craft and corvettes. Their names form the practical vocabulary of expansion: Jal Everk, Irsk Bovam, Jal Turran, Kal Vimon, and many more."
        )

    unique_fleet_titles: list[tuple[str, str]] = []
    seen: set[str] = set()
    for row in sorted(fleet_births, key=lambda item: item["game_date"]):
        name = row["title"].replace(" Entered the Record", "")
        if (
            not name
            or name.startswith("Unnamed")
            or name in {"Lost Juvenile", "Bubbles"}
            or name in seen
        ):
            continue
        seen.add(name)
        unique_fleet_titles.append((row["game_date"], name))
    if unique_fleet_titles:
        chosen = unique_fleet_titles[:5]
        phrases = [f"{name} in {_year(date)}" for date, name in chosen]
        paragraphs.append(
            "New formations followed the new ships. The records first name " + _join_words(phrases) + ". Some formations were brief, some endured, and some names were reused as the navy was reorganised. The scribes therefore remember the appearance of the names without pretending every fleet identity remained continuous forever."
        )

    if refits:
        first_refit = min(row["game_date"] for row in refits)
        last_refit = max(row["game_date"] for row in refits)
        paragraphs.append(
            f"From {_year(first_refit)} onward the design record also shows repeated waves of refitting and modernisation, continuing as late as {_year(last_refit)}. The archive can prove that surviving ships changed their recorded designs; it cannot yet tell us which guns, armour or internal systems were replaced. Even so, the pattern is unmistakable: this was not a fleet frozen in its founding form."
        )

    bubbles = next((row for row in fleet_births if row["title"].startswith("Bubbles ")), None)
    if bubbles:
        paragraphs.append(
            f"Not every name in the naval rolls sounds like the product of a shipyard. In {_year(bubbles['game_date'])}, the record quietly introduces Bubbles. The evidence available here says only that Bubbles entered the military fleet record; the mystery is allowed to remain a mystery."
        )

    paragraphs.append(
        f"By the latest archived date, {len(present_ships)} mobile ships remained present in the registry. That number is not the whole measure of the navy's history: {len(ships) - len(present_ships)} other vessel identities had passed out of the surviving rolls over the decades, and absence alone does not tell us why."
    )

    return _chapter(
        "chapter-ships",
        "IV",
        "Ships Beneath Strange Suns",
        "The slow making of a starfaring power",
        paragraphs,
    )


def _scribe_system_name(value: str | None) -> str | None:
    """Return only system names that read naturally in an in-universe chronicle."""
    if not value:
        return None
    text = str(value).strip()
    low = text.lower()
    if "_" in text or low.endswith(" name") or low.startswith("unknown"):
        return None
    if low.endswith(" system"):
        text = text[:-7].strip()
    return text or None


def _event_attributes(event: HistoricalEvent) -> dict[str, str]:
    return {key: value for key, value in event.attributes}


def _attr_list(attrs: dict[str, str], key: str) -> list[str]:
    value = attrs.get(key)
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _attr_int(attrs: dict[str, str], key: str) -> int | None:
    try:
        return int(attrs[key])
    except (KeyError, TypeError, ValueError):
        return None


def _combat_chapter(historical_events: list[HistoricalEvent] | tuple[HistoricalEvent, ...]) -> str:
    """Render the Chronicle from synthesized combat episodes, not raw markers."""
    combat_events = [
        event for event in historical_events
        if event.category == "combat" and event.event_type == "combat_episode"
    ]
    paragraphs: list[str] = []

    if not combat_events:
        paragraphs.append(
            "The military archive contains no reconstructed combat episode in this edition. The chronicle therefore leaves the years of fighting undescribed rather than inventing them."
        )
        return _chapter("chapter-combat", "V", "The Years of Fire", "War, encounters and the marks left by battle", paragraphs)

    direct_events: list[HistoricalEvent] = []
    resolved_events: list[HistoricalEvent] = []
    lower_events: list[HistoricalEvent] = []
    for event in combat_events:
        attrs = _event_attributes(event)
        if attrs.get("evidence_kind") == "direct_anchored":
            direct_events.append(event)
        elif event.confidence == "high" and (
            attrs.get("systems") or attrs.get("opposing_countries") or attrs.get("player_fleets")
        ):
            resolved_events.append(event)
        else:
            lower_events.append(event)

    if direct_events:
        paragraphs.append(
            "No formal declaration of war survives in these pages, yet several battle-rolls are unusually complete. They preserve formations, commanders, opposing forces and retained loss tallies. Where those records survive, the Chronicle gives them precedence over weaker traces of violence."
        )

    for event in direct_events:
        attrs = _event_attributes(event)
        end_date = attrs.get("end_date") or event.game_date
        systems = [_scribe_system_name(value) for value in _attr_list(attrs, "systems")]
        systems = [value for value in systems if value]
        enemies = _attr_list(attrs, "opposing_countries") or _attr_list(attrs, "opposing_fleets")
        fleets = _attr_list(attrs, "player_fleets")
        commanders = _attr_list(attrs, "commanders")
        opposing_fleets = _attr_list(attrs, "opposing_fleets")

        if end_date != event.game_date:
            detail = f"From {_natural_date(event.game_date)} through {_natural_date(end_date)}, "
        else:
            detail = f"On {_natural_date(event.game_date)}, "
        detail += f"{_join_words(fleets[:6]) or 'Convocation forces'} entered a recorded episode of fighting"
        if enemies:
            detail += f" with {_join_words(enemies[:4])}"
        if systems:
            detail += f" in the {_join_words(systems[:3])} system{'s' if len(systems) > 1 else ''}"
        detail += "."

        if commanders:
            detail += f" The command rolls name {_join_words(commanders[:5])}."
        if opposing_fleets:
            detail += f" The opposing fleet rolls name {_join_words(opposing_fleets[:4])}."

        initial_side = _attr_int(attrs, "initial_player_losses")
        initial_opp = _attr_int(attrs, "initial_opposing_losses")
        latest_side = _attr_int(attrs, "latest_player_losses")
        latest_opp = _attr_int(attrs, "latest_opposing_losses")
        initial_observed = attrs.get("initial_observed_date")
        latest_observed = attrs.get("latest_observed_date")
        evolved = attrs.get("telemetry_evolved") == "true"

        if initial_side is not None and initial_opp is not None:
            if evolved and latest_side is not None and latest_opp is not None:
                if initial_observed:
                    detail += f" The earliest complete retained tally reconstructed by {initial_observed}"
                else:
                    detail += " The earliest complete retained tally"
                detail += (
                    f" recorded {initial_side} Convocation vessel{'s' if initial_side != 1 else ''} lost and "
                    f"{initial_opp} opposing vessel{'s' if initial_opp != 1 else ''} lost."
                )
                if latest_observed:
                    detail += f" Later retained fleet records reconstructed by {latest_observed}"
                else:
                    detail += " Later retained fleet records"
                detail += (
                    f" raised the known tally to {latest_side} Convocation vessel{'s' if latest_side != 1 else ''} lost and "
                    f"{latest_opp} opposing vessel{'s' if latest_opp != 1 else ''} lost. "
                    "These are changing observations of the same retained battle record, not separate casualty totals."
                )
            elif initial_side or initial_opp:
                detail += (
                    f" The retained battle tallies record {initial_side} Convocation vessel{'s' if initial_side != 1 else ''} lost and "
                    f"{initial_opp} opposing vessel{'s' if initial_opp != 1 else ''} lost."
                )
            else:
                detail += " The surviving retained fleet tallies record no vessel losses for either side."

        outcome = attrs.get("formal_outcome")
        if outcome == "victory":
            detail += " A surviving formal battle-roll establishes victory."
        elif outcome == "defeat":
            detail += " A surviving formal battle-roll establishes defeat."
        else:
            detail += " No surviving record establishes victory or defeat."
        paragraphs.append(detail)

    if resolved_events:
        by_year: dict[str, list[HistoricalEvent]] = {}
        for event in resolved_events:
            by_year.setdefault(_year(event.game_date), []).append(event)

        for year in sorted(by_year):
            year_events = by_year[year]
            systems: list[str] = []
            enemies: list[str] = []
            fleets: list[str] = []
            commanders: list[str] = []
            for event in year_events:
                attrs = _event_attributes(event)
                for value in _attr_list(attrs, "systems"):
                    clean = _scribe_system_name(value)
                    if clean and clean not in systems:
                        systems.append(clean)
                for value in _attr_list(attrs, "opposing_countries"):
                    if value not in enemies:
                        enemies.append(value)
                for value in _attr_list(attrs, "player_fleets"):
                    if value not in fleets:
                        fleets.append(value)
                for value in _attr_list(attrs, "commanders"):
                    if value not in commanders:
                        commanders.append(value)

            text = (
                f"Beyond the clearer battle-rolls, {year} preserves {_small_number(len(year_events))} further high-confidence combat episode"
                f"{'s' if len(year_events) != 1 else ''}."
            )
            if systems:
                text += f" The surviving location evidence places the fighting at {_join_words(systems[:5])}."
            if enemies:
                text += f" Opposing forces named in the surviving evidence include {_join_words(enemies[:4])}."
            if fleets:
                text += f" Convocation formations named in these episodes include {_join_words(fleets[:5])}."
            if commanders:
                text += f" Commanders attached to those formations include {_join_words(commanders[:4])}."
            text += " The deeper ledger retains the individual combat dates and ship-level markers."
            paragraphs.append(text)

    if lower_events:
        year_counts: dict[str, int] = {}
        for event in lower_events:
            year_counts[_year(event.game_date)] = year_counts.get(_year(event.game_date), 0) + 1
        ranges = [f"{year} ({count})" for year, count in sorted(year_counts.items())]
        paragraphs.append(
            f"A further {len(lower_events)} lower-confidence combat episode{'s' if len(lower_events) != 1 else ''} remain in the deeper military ledger"
            + (f", distributed across {_join_words(ranges)}" if ranges else "")
            + ". They are preserved as evidence, but this Chronicle does not promote unresolved station labels or isolated activity markers into named battles."
        )

    return _chapter(
        "chapter-combat",
        "V",
        "The Years of Fire",
        "War, encounters and the marks left by battle",
        paragraphs,
    )

def _technology_chapter(technology_snapshots) -> str:
    paragraphs: list[str] = []
    if not technology_snapshots:
        paragraphs.append(
            "The learned registers have not yet been reconstructed for this edition of the archive, and so the chronicle declines to invent a march of discoveries it cannot presently prove."
        )
        return _chapter("chapter-technology", "VI", "The Treasury of Knowledge", "The accumulated arts of a starfaring civilization", paragraphs)

    history = derive_technology_history(technology_snapshots)
    opening = history["opening"]
    events = history["events"]
    latest = history["latest"]

    if opening:
        examples = [row.name for row in opening[:10]]
        paragraphs.append(
            f"When the surviving record opens, the Convocation already possesses {len(opening)} named technologies in its learned register. "
            f"Among that inherited foundation were {_join_words(examples)}. These are not claimed as discoveries of the opening year; they are simply the knowledge with which the archive begins."
        )

    by_year: dict[str, list] = {}
    for event in events:
        by_year.setdefault(_year(event.game_date), []).append(event)

    for year, year_events in by_year.items():
        labels = []
        for event in year_events:
            label = event.name
            if event.event_type == "technology_level_increased" and event.level > 1:
                label += f" (recorded level {event.level})"
            labels.append(label)
        # Keep prose readable while ensuring every observed advance is named.
        chunks = [labels[i:i + 8] for i in range(0, len(labels), 8)]
        for index, chunk in enumerate(chunks):
            if index == 0:
                prefix = f"Across the learned rolls of {year}, new knowledge enters the record: "
            else:
                prefix = f"The same year's registers add further advances: "
            paragraphs.append(prefix + _join_words(chunk) + ".")

    if latest:
        paragraphs.append(
            f"By {technology_snapshots[-1].game_date}, the surviving register contained {len(latest)} researched technologies, "
            f"with {len(events)} advances first appearing after the opening record. The archive can usually tell us by which preserved roll an advance had entered use; "
            "where it cannot supply the exact day of discovery, neither does this chronicle pretend to know it."
        )

    return _chapter(
        "chapter-technology",
        "VI",
        "The Treasury of Knowledge",
        "The accumulated arts of a starfaring civilization",
        paragraphs,
    )


def _science_chapter(db: Database, campaign_id: int) -> str:
    paragraphs: list[str] = []
    try:
        interpretation = derive_science_interpretation(_cache_science_snapshots(db, campaign_id))
    except Exception:
        interpretation = None

    if interpretation is None:
        paragraphs.append("The scientific archive could not be assembled for this reading of the chronicle.")
        return _chapter("chapter-science", "VII", "Questions Without Easy Answers", "Science, ruins and unfinished work", paragraphs)

    red_projects = [row for row in interpretation.project_families if row.project_key in _RED_GIANT_PROJECT_KEYS]
    red_situations = [row for row in interpretation.situations if row.type_key == _RED_GIANT_SITUATION_KEY]
    if red_projects or red_situations:
        dates = [row.first_observed for row in red_projects] + [row.first_observed for row in red_situations]
        ends = [row.last_observed for row in red_projects] + [row.last_observed for row in red_situations]
        first, last = min(dates), max(ends)
        project_names = [row.title for row in sorted(red_projects, key=lambda x: x.first_observed)]
        paragraphs.append(
            f"The old sun was not merely scenery. From {_year(first)} through {_year(last)}, the surviving scientific record repeatedly returns to the Red Giant question. {_join_words(project_names[:4])} appear as parts of that long work. The archive preserves the labour more clearly than the ending, and where the ending is uncertain the scribes will not manufacture one."
        )

    sites = sorted(interpretation.archaeology_sites, key=lambda row: row.first_observed)
    for site in sites[:3]:
        location = _join_words(list(site.location_names)) or "an unresolved place"
        text = f"In {_year(site.first_observed)}, the archive records {site.title} at {location}."
        if site.scientist_names:
            text += f" The work is linked to {_join_words(list(site.scientist_names))}."
        if site.progress_marker_dates:
            text += f" Later records preserve {len(site.progress_marker_dates)} dated progress markers, enough to show sustained work without proving a final conclusion."
        paragraphs.append(text)

    contextual_projects = [
        row for row in interpretation.project_families
        if row.project_key not in _RED_GIANT_PROJECT_KEYS
        and (row.scientist_names or row.ship_names or row.location_names)
    ]
    contextual_projects.sort(key=lambda row: row.first_observed)
    if contextual_projects:
        chosen = contextual_projects[:6]
        names = [row.title for row in chosen]
        paragraphs.append(
            "Beyond those larger arcs, the scientific rolls are crowded with particular questions: " + _join_words(names) + ". Some disappear from later records, some remain visible for decades. The record often tells us who worked on them and which ship carried the task, but not always whether the work ended in triumph, failure or simple abandonment."
        )

    situations = [
        row for row in interpretation.situations
        if row.type_key not in {_RED_GIANT_SITUATION_KEY, "situation_observation_insight"}
        and not row.type_key.endswith("_deficit")
        and row.type_key != "situation_planetary_revolt"
    ]
    situations.sort(key=lambda row: row.first_observed)
    if situations:
        row = situations[0]
        paragraphs.append(
            f"One later episode bears the name {row.title}, first observed in {_year(row.first_observed)}. It remains a reminder that not every crisis or discovery can be reduced to a neat ending: the archive preserves its presence and progress, but not enough evidence for the scribes to declare how the story finally resolved."
        )

    if not paragraphs:
        paragraphs.append(
            "The surviving archives contain scientific work, but some of it remains too fragmentary to weave safely into a continuous account. Those fragments are retained in the deeper record rather than forced into a false conclusion."
        )

    return _chapter(
        "chapter-science",
        "VII",
        "Questions Without Easy Answers",
        "Science, ruins and unfinished work",
        paragraphs,
    )


def _closing_chapter(campaign, worlds, leaders, ships) -> str:
    present_leaders = [row for row in leaders if row["status"] == "present"]
    present_ships = [row for row in ships if row["status"] == "present"]
    paragraphs = [
        f"The surviving chronicle presently closes on {campaign['latest_game_date']}. By then the archive still recorded {len(worlds)} inhabited worlds under the Convocation, {len(present_ships)} mobile ships, and {len(present_leaders)} named leaders still present in the rolls.",
        "These numbers are useful, but they are not the history itself. The history lies in the distance between the first small fleet and the later navy; between one homeworld and the colonies beyond it; between the names present on the first page and those that entered service decades later; between questions first posed beneath an ageing star and mysteries still unresolved when the record ends.",
        "Nor is this an ending. It is only the latest surviving page. The archive remains open, the calendar continues, and future scribes will inherit whatever the Convocation does next.",
    ]
    return _chapter(
        "chapter-closing",
        "VIII",
        "The Chronicle Remains Open",
        f"The record as it stood on {campaign['latest_game_date']}",
        paragraphs,
    )


def render_scribes_journal(db: Database, campaign_id: int) -> Path:
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist.")

    entries = db.history_entries(campaign_id)
    founding = [row for row in entries if row["entry_type"] == "founding"]
    worlds = list(db.world_registry(campaign_id))
    leaders = list(db.leader_registry(campaign_id))
    ships = list(db.ship_registry(campaign_id))
    fleets = list(db.fleet_registry(campaign_id))
    ship_events = list(db.ship_fleet_events(campaign_id, visible_only=True))
    career_events = list(db.leader_career_events(campaign_id, visible_only=True))
    presentation = build_presentation_history(db, campaign_id)
    combat_snapshots = list(presentation.combat_snapshots)
    ship_snapshots = list(presentation.ship_snapshots)
    technology_snapshots = list(presentation.technology_snapshots)

    raw_chapters = [
        _opening_chapter(db, campaign_id, campaign, founding, worlds, leaders, fleets),
        _expansion_chapter(campaign, worlds),
        _people_chapter(campaign, leaders, career_events),
        _ships_chapter(ships, fleets, ship_events),
        _combat_chapter(presentation.events),
        _technology_chapter(technology_snapshots),
        _science_chapter(db, campaign_id),
        _closing_chapter(campaign, worlds, leaders, ships),
    ]
    authority_dates = _chapter_authority_dates(
        campaign, worlds, leaders, ship_events, combat_snapshots, technology_snapshots
    )
    ruler_observations = _ruler_observations(db, campaign_id)
    chapters: list[str] = []
    for index, (chapter_html, anchor_date) in enumerate(zip(raw_chapters, authority_dates)):
        if index == len(raw_chapters) - 1:
            chapters.append(_sign_chapter(chapter_html, _final_note_html(str(campaign['latest_game_date']))))
            continue
        ruler = _ruler_for_date(ruler_observations, anchor_date)
        chapters.append(
            _sign_chapter(
                chapter_html,
                _authority_html(ruler, str(campaign['empire_name']), anchor_date),
            )
        )

    title = f"The Chronicle of {campaign['empire_name']}"
    target = scribes_path(db, campaign_id)
    target.parent.mkdir(parents=True, exist_ok=True)

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(title)} - As the Scribes Saw It</title>
<style>
:root{{
  --ink:#2a221a;
  --muted:#756651;
  --paper:#f3ead6;
  --paper-deep:#e7d7b8;
  --gold:#9d763d;
  --line:#c8ae82;
  --night:#17120e;
  --width:920px;
}}
*{{box-sizing:border-box}}
html{{scroll-behavior:smooth}}
body{{
  margin:0;
  background:
    radial-gradient(circle at 20% 0%,rgba(255,255,255,.26),transparent 28rem),
    #cdbc9c;
  color:var(--ink);
  font-family:Georgia,"Times New Roman",serif;
}}
.topbar{{
  position:sticky;top:0;z-index:20;
  display:flex;align-items:center;gap:10px;
  padding:9px max(16px,calc((100vw - var(--width))/2));
  background:rgba(23,18,14,.97);
  border-bottom:1px solid #5b4630;
  box-shadow:0 4px 16px rgba(0,0,0,.18);
}}
.topbar a,.topbar button{{
  border:1px solid #765b39;border-radius:5px;
  padding:8px 11px;background:#2d2118;color:#f1e4ce;
  font:600 12px Arial,sans-serif;text-decoration:none;cursor:pointer;
}}
.topbar .spacer{{flex:1}}
.cover{{
  min-height:78vh;
  display:flex;align-items:center;justify-content:center;
  padding:70px 24px;
  background:
    linear-gradient(rgba(19,14,10,.70),rgba(19,14,10,.86)),
    radial-gradient(circle at center,#5f482d,#17120e 66%);
  color:#f6ecd9;text-align:center;
  border-bottom:7px solid var(--gold);
}}
.cover-inner{{max-width:900px}}
.sigil{{font-size:30px;color:#d5b06a;letter-spacing:.35em;margin-bottom:28px}}
.kicker{{font:700 11px Arial,sans-serif;letter-spacing:.25em;text-transform:uppercase;color:#d6ba86}}
h1{{font-size:clamp(46px,8vw,92px);line-height:.94;font-weight:500;margin:16px 0 18px}}
.cover .dates{{font-size:19px;color:#dbcdb7}}
.cover .motto{{max-width:680px;margin:34px auto 0;font-size:19px;line-height:1.65;font-style:italic;color:#eadcc6}}
.book{{width:min(calc(100% - 28px),var(--width));margin:0 auto;background:var(--paper);box-shadow:0 0 40px rgba(44,31,18,.18);padding:68px clamp(28px,7vw,82px) 100px}}
.preface{{padding:0 0 54px;border-bottom:1px solid var(--line);margin-bottom:68px}}
.preface h2,.chapter h2{{font-weight:500}}
.preface p,.prose p{{font-size:19px;line-height:1.85;margin:0 0 1.2em}}
.preface p:first-of-type::first-letter,.prose .lead::first-letter{{float:left;font-size:4.1em;line-height:.78;padding:.08em .10em 0 0;color:#8d632d}}
.chapter{{scroll-margin-top:65px;margin:0 auto 84px;max-width:780px}}
.chapter-number{{font:700 11px Arial,sans-serif;letter-spacing:.28em;text-transform:uppercase;color:var(--gold)}}
.chapter h2{{font-size:42px;line-height:1.05;margin:9px 0 7px}}
.chapter-subtitle{{font-style:italic;color:var(--muted);font-size:17px;margin-bottom:30px}}
.authority{{margin:42px 0 12px auto;max-width:430px;padding:18px 0 4px;border-top:1px solid var(--line);text-align:right}}
.authority-kicker{{font:700 10px Arial,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}}
.authority-name{{font-size:26px;font-style:italic;color:#6f4d27;margin-top:8px}}
.authority-role,.authority-date{{font-size:13px;color:var(--muted);margin-top:3px}}
.final-note{{margin-top:46px;padding:24px 26px;border:1px solid var(--line);background:rgba(231,215,184,.45);text-align:center}}
.final-note-title{{font-size:22px;font-style:italic;color:#76542c;margin-bottom:10px}}
.final-note p{{font-size:16px!important;line-height:1.65!important;color:var(--muted);margin:0!important}}
.chapter::after{{content:"✦";display:block;text-align:center;color:#aa8752;margin-top:52px;font-size:18px}}
.colophon{{max-width:760px;margin:0 auto;padding-top:38px;border-top:1px solid var(--line);text-align:center;color:var(--muted);font-size:14px;line-height:1.6}}
@media(max-width:700px){{
  .topbar{{padding:8px;flex-wrap:wrap}}
  .cover{{min-height:65vh}}
  .book{{width:100%;padding:42px 22px 70px}}
  .preface p,.prose p{{font-size:17px}}
  .chapter h2{{font-size:34px}}
}}
@media print{{
  @page{{size:A4 portrait;margin:18mm 17mm 20mm}}
  body{{background:white}}
  .topbar{{display:none!important}}
  .cover{{min-height:245mm;break-after:page;border:0}}
  .book{{width:auto;box-shadow:none;padding:0;background:white}}
  .preface{{break-after:page}}
  .chapter{{max-width:none;break-before:page;margin:0}}
  .chapter h2{{font-size:28pt}}
  .preface p,.prose p{{font-size:11.5pt;line-height:1.65}}
  .authority,.final-note{{break-inside:avoid}}
}}
</style>
</head>
<body id="top">
<nav class="topbar">
  <a href="/journal">Evidence Journal</a>
  <a href="/timeline">Empire Timeline</a>
  <a href="/campaign">Campaign</a>
  <div class="spacer"></div>
  <a href="/scribes/pdf" title="Generate and download a book-style PDF">Export PDF</a>
  <button type="button" onclick="window.print()">Print</button>
</nav>
<section class="cover">
  <div class="cover-inner">
    <div class="sigil">✦ ◇ ✦</div>
    <div class="kicker">As the Scribes Saw It</div>
    <h1>{_e(title)}</h1>
    <div class="dates">A narrative history of the surviving record, {_e(campaign['first_game_date'])}–{_e(campaign['latest_game_date'])}</div>
    <div class="motto">Of all that was done, much was forgotten. Of all that survived, this is what we remember.</div>
  </div>
</section>
<main class="book">
  <section class="preface">
    <h2>A Note from the Later Archive</h2>
    <p>The deeper ledger keeps every useful date, every movement, every fragment and every uncertainty because the past is rarely tidy. This chronicle has a different purpose: to gather those surviving pieces into the fullest account that can be told without giving invention the name of memory.</p>
    <p>Where the archive knows, the scribes speak plainly. Where it only suggests, the language remains cautious. Where the evidence is silent, silence is preserved. Each completed chapter is set beneath the authority of the ruler recorded for that period and signed in that ruler's name; no speech, motive, childhood, death or triumph is supplied merely to make the tale neater.</p>
  </section>
  {''.join(chapters)}
  <div class="colophon">Compiled from the surviving archives of {_e(campaign['empire_name'])}. The deeper evidence ledger preserves the fragments and uncertainties from which this chronicle was drawn.</div>
</main>
</body>
</html>
"""

    fd, temp_name = tempfile.mkstemp(prefix=".scribes_", suffix=".html", dir=target.parent)
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


def render_scribes_pdf(db: Database, campaign_id: int) -> Path:
    """Generate a standalone, book-style PDF from the same evidence-led text."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    )
    from xml.sax.saxutils import escape as xml_escape

    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist.")

    entries = db.history_entries(campaign_id)
    founding = [row for row in entries if row["entry_type"] == "founding"]
    worlds = list(db.world_registry(campaign_id))
    leaders = list(db.leader_registry(campaign_id))
    ships = list(db.ship_registry(campaign_id))
    fleets = list(db.fleet_registry(campaign_id))
    ship_events = list(db.ship_fleet_events(campaign_id, visible_only=True))
    career_events = list(db.leader_career_events(campaign_id, visible_only=True))
    presentation = build_presentation_history(db, campaign_id)
    combat_snapshots = list(presentation.combat_snapshots)
    ship_snapshots = list(presentation.ship_snapshots)
    technology_snapshots = list(presentation.technology_snapshots)

    raw_chapters = [
        _opening_chapter(db, campaign_id, campaign, founding, worlds, leaders, fleets),
        _expansion_chapter(campaign, worlds),
        _people_chapter(campaign, leaders, career_events),
        _ships_chapter(ships, fleets, ship_events),
        _combat_chapter(presentation.events),
        _technology_chapter(technology_snapshots),
        _science_chapter(db, campaign_id),
        _closing_chapter(campaign, worlds, leaders, ships),
    ]
    authority_dates = _chapter_authority_dates(
        campaign, worlds, leaders, ship_events, combat_snapshots, technology_snapshots
    )
    ruler_observations = _ruler_observations(db, campaign_id)

    target = scribes_pdf_path(db, campaign_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".tmp.pdf")

    page_w, _page_h = A4
    doc = SimpleDocTemplate(
        str(temp),
        pagesize=A4,
        leftMargin=19 * mm,
        rightMargin=19 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"The Chronicle of {campaign['empire_name']}",
        author="Stellaris Historian",
        subject="As the Scribes Saw It",
    )

    styles = getSampleStyleSheet()
    ink = colors.HexColor("#2A221A")
    muted = colors.HexColor("#756651")
    gold = colors.HexColor("#9D763D")
    line = colors.HexColor("#C8AE82")

    cover_kicker = ParagraphStyle(
        "CoverKicker", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=9, leading=12, alignment=TA_CENTER, textColor=gold, spaceAfter=9,
    )
    cover_title = ParagraphStyle(
        "CoverTitle", parent=styles["Title"], fontName="Times-Roman",
        fontSize=31, leading=34, alignment=TA_CENTER, textColor=ink, spaceAfter=14,
    )
    cover_sub = ParagraphStyle(
        "CoverSub", parent=styles["Normal"], fontName="Times-Italic",
        fontSize=11, leading=16, alignment=TA_CENTER, textColor=muted,
    )
    chapter_no = ParagraphStyle(
        "ChapterNo", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=8, leading=10, textColor=gold, spaceAfter=4,
    )
    chapter_title = ParagraphStyle(
        "ChapterTitle", parent=styles["Heading1"], fontName="Times-Roman",
        fontSize=24, leading=27, textColor=ink, spaceAfter=4,
    )
    chapter_sub = ParagraphStyle(
        "ChapterSub", parent=styles["Normal"], fontName="Times-Italic",
        fontSize=10.5, leading=14, textColor=muted, spaceAfter=15,
    )
    body = ParagraphStyle(
        "Body", parent=styles["BodyText"], fontName="Times-Roman",
        fontSize=10.8, leading=16.5, textColor=ink, spaceAfter=10,
    )
    authority_kicker = ParagraphStyle(
        "AuthorityKicker", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=7.5, leading=10, alignment=TA_RIGHT, textColor=muted,
    )
    authority_name = ParagraphStyle(
        "AuthorityName", parent=styles["Normal"], fontName="Times-Italic",
        fontSize=17, leading=20, alignment=TA_RIGHT, textColor=gold,
    )
    authority_role = ParagraphStyle(
        "AuthorityRole", parent=styles["Normal"], fontName="Times-Roman",
        fontSize=8.5, leading=11, alignment=TA_RIGHT, textColor=muted,
    )
    final_style = ParagraphStyle(
        "Final", parent=styles["Normal"], fontName="Times-Italic",
        fontSize=11, leading=16, alignment=TA_CENTER, textColor=muted,
    )

    story = []
    story.extend([
        Spacer(1, 38 * mm),
        Paragraph("AS THE SCRIBES SAW IT", cover_kicker),
        Paragraph(xml_escape(f"The Chronicle of {campaign['empire_name']}"), cover_title),
        HRFlowable(width="62%", thickness=0.8, color=gold, spaceBefore=5, spaceAfter=12, hAlign="CENTER"),
        Paragraph(
            xml_escape(
                f"A narrative history of the surviving record, "
                f"{campaign['first_game_date']} - {campaign['latest_game_date']}"
            ),
            cover_sub,
        ),
        Spacer(1, 16 * mm),
        Paragraph(
            "<i>Of all that was done, much was forgotten.<br/>"
            "Of all that survived, this is what we remember.</i>",
            cover_sub,
        ),
        PageBreak(),
        Paragraph("A Note from the Later Archive", chapter_title),
        Paragraph(
            "The deeper ledger keeps every useful date, every movement, every fragment and every uncertainty because the past is rarely tidy. "
            "This chronicle has a different purpose: to gather those surviving pieces into the fullest account that can be told without giving invention the name of memory.",
            body,
        ),
        Paragraph(
            "Where the archive knows, the scribes speak plainly. Where it only suggests, the language remains cautious. "
            "Where the evidence is silent, silence is preserved. Each completed chapter is set beneath the authority of "
            "the ruler recorded for that period and signed in that ruler's name; no speech, motive, childhood, death or triumph "
            "is supplied merely to make the tale neater.",
            body,
        ),
    ])

    roman = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]
    for index, (chapter_html, anchor_date) in enumerate(zip(raw_chapters, authority_dates)):
        title, subtitle, paragraphs = _chapter_parts(chapter_html)
        story.append(PageBreak())
        story.append(Paragraph(f"CHAPTER {roman[index]}", chapter_no))
        story.append(Paragraph(xml_escape(title), chapter_title))
        story.append(Paragraph(xml_escape(subtitle), chapter_sub))
        for paragraph in paragraphs:
            story.append(Paragraph(xml_escape(paragraph), body))

        if index == len(raw_chapters) - 1:
            story.extend([
                Spacer(1, 8 * mm),
                HRFlowable(
                    width="70%", thickness=0.6, color=line,
                    spaceBefore=4, spaceAfter=10, hAlign="CENTER"
                ),
                Paragraph("<b>The final page is left unsigned.</b>", final_style),
                Paragraph(
                    xml_escape(
                        f"The surviving archive ends on {campaign['latest_game_date']}, but the civilization does not. "
                        "This is only the present edge of the record; the next hand to sign these pages belongs to "
                        "history yet unwritten."
                    ),
                    final_style,
                ),
            ])
            continue

        ruler = _ruler_for_date(ruler_observations, anchor_date)
        if ruler:
            data = [
                [Paragraph("SET DOWN IN THE CHRONICLE BY", authority_kicker)],
                [Paragraph(xml_escape(str(ruler.get("name") or "Unnamed Ruler")), authority_name)],
                [Paragraph(xml_escape(f"Ruler of {campaign['empire_name']}"), authority_role)],
                [Paragraph(xml_escape(f"Signed to the surviving record - {_year(anchor_date)}"), authority_role)],
            ]
            table = Table(data, colWidths=[78 * mm], hAlign="RIGHT")
            table.setStyle(TableStyle([
                ("LINEABOVE", (0, 0), (-1, 0), 0.6, line),
                ("TOPPADDING", (0, 0), (-1, 0), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.extend([Spacer(1, 7 * mm), table])

    def footer(canvas, _doc_obj):
        page = canvas.getPageNumber()
        if page <= 1:
            return
        canvas.saveState()
        canvas.setStrokeColor(line)
        canvas.setLineWidth(0.35)
        canvas.line(19 * mm, 12 * mm, page_w - 19 * mm, 12 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(muted)
        canvas.drawString(19 * mm, 7.5 * mm, str(campaign["empire_name"]))
        canvas.drawRightString(page_w - 19 * mm, 7.5 * mm, str(page))
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    os.replace(temp, target)
    return target
