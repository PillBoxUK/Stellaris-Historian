from __future__ import annotations

from pathlib import Path
import re

from ...core.stellaris_text import _extract_braced_after, _find_named_block, _numeric_record
from ...localisation import resolve_localisation_key
from ...save_reader import EmpireProfile
from .models import TechnologySnapshot, TechnologyState


def _humanise_technology_key(key: str) -> str:
    value = key
    if value.startswith("tech_"):
        value = value[5:]
    value = value.replace("_", " ").strip()
    value = re.sub(r"\s+", " ", value)
    # Keep familiar acronyms readable where the fallback name is used.
    words = []
    for word in value.split():
        if word.lower() in {"ftl", "ai", "pd"}:
            words.append(word.upper())
        else:
            words.append(word.capitalize())
    return " ".join(words) or key


def _player_country_record_fast(gamestate: str, country_id: int) -> str | None:
    """Locate the player's top-level country record without materialising all countries.

    Stellaris writes the global country block at top level and its country records one
    indentation level beneath it. The narrow search is substantially faster on large
    Ironman saves. A structural fallback is retained for unusual formatting/mods.
    """
    country_match = re.search(r"(?m)^\s*country\s*=\s*\{", gamestate)
    if country_match:
        start = country_match.start()
        # The ordinary save format uses one tab for top-level country IDs.
        direct = re.search(
            rf"(?m)^\t{re.escape(str(country_id))}\s*=\s*\{{",
            gamestate[country_match.end():],
        )
        if direct:
            absolute = country_match.end() + direct.start()
            record = _extract_braced_after(gamestate, absolute)
            if record is not None:
                return record

    countries = _find_named_block(gamestate, "country")
    return _numeric_record(countries, country_id)


def extract_technology_snapshot(
    *,
    gamestate: str,
    profile: EmpireProfile,
    source_save: Path,
    snapshot_id: int,
) -> TechnologySnapshot:
    country_id = profile.player_country_id
    if country_id is None:
        raise ValueError("Could not determine the player country ID for technology parsing.")

    country = _player_country_record_fast(gamestate, country_id)
    if not country:
        raise ValueError(f"Could not locate player country {country_id} for technology parsing.")

    tech_status = _find_named_block(country, "tech_status") or ""

    # Completed technologies are represented by a technology key immediately
    # followed by its researched level. Queue entries also contain technology=,
    # but do not use this completed-entry shape, so they are deliberately excluded.
    completed = re.findall(
        r'(?m)^\s*technology\s*=\s*"([^"]+)"\s*\n\s*level\s*=\s*(-?\d+)',
        tech_status,
    )

    technologies: dict[str, TechnologyState] = {}
    for key, raw_level in completed:
        try:
            level = int(raw_level)
        except ValueError:
            continue
        if level < 1:
            continue

        previous = technologies.get(key)
        if previous is not None and previous.level >= level:
            continue

        name = resolve_localisation_key(source_save, key) or _humanise_technology_key(key)
        technologies[key] = TechnologyState(key=key, name=name, level=level)

    return TechnologySnapshot(
        snapshot_id=snapshot_id,
        game_date=profile.game_date,
        player_country_id=country_id,
        technologies=technologies,
    )
