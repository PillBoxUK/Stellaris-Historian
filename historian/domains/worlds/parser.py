from __future__ import annotations

from pathlib import Path
import re

from ...localisation import resolve_localisation_key
from ...save_reader import EmpireProfile
from ...core.stellaris_text import (
    _extract_braced_after,
    _find_named_block,
    _id_list_from_block,
    _int_scalar,
    _scalar,
)
from .models import WorldSnapshot, WorldState


def _top_numeric_record(
    block: str | None,
    numeric_id: int,
) -> str | None:
    """
    Fetch a direct numeric child from a Paradox block without accidentally
    matching the same number inside a nested job/pop/building structure.

    Stellaris indents direct records consistently within these top-level
    databases. The first direct numeric record gives us that indentation.
    """
    if not block:
        return None

    first = re.search(
        r"(?m)^([ \t]*)\d+\s*=\s*\{",
        block,
    )

    if not first:
        return None

    indent = first.group(1)

    match = re.search(
        rf"(?m)^{re.escape(indent)}{numeric_id}\s*=\s*\{{",
        block,
    )

    if not match:
        return None

    return _extract_braced_after(
        block,
        match.start(),
    )


def _normalise_space(value: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def _humanise_name_key(
    key: str | None,
    *,
    suffix: str | None = None,
) -> str | None:
    if not key:
        return None

    value = key.strip()

    for prefix in (
        "SPEC_",
        "NAME_",
    ):
        if value.startswith(prefix):
            value = value[len(prefix):]
            break

    if suffix and value.lower().endswith(
        f"_{suffix.lower()}"
    ):
        value = value[: -(len(suffix) + 1)]

    value = value.replace(
        "_",
        " ",
    )

    value = re.sub(
        r"(?<=[a-z0-9])(?=[A-Z])",
        " ",
        value,
    )

    value = _normalise_space(
        value
    )

    if not value:
        return None

    # Preserve mixed-case generated proper names where possible.
    if " " not in value and any(
        char.isupper()
        for char in value[1:]
    ):
        return value

    return value.title()


def _resolved_or_humanised(
    source_save: Path,
    key: str | None,
    *,
    suffix: str | None = None,
) -> str | None:
    if not key:
        return None

    resolved = resolve_localisation_key(
        source_save,
        key,
    )

    if resolved:
        resolved = _normalise_space(
            resolved
        )

        if suffix and resolved.lower().endswith(
            f" {suffix.lower()}"
        ):
            resolved = resolved[: -(len(suffix) + 1)].strip()

        if resolved:
            return resolved

    return _humanise_name_key(
        key,
        suffix=suffix,
    )


def _name_variable_values(
    name_block: str,
    source_save: Path,
    *,
    suffix: str | None = None,
) -> list[tuple[str, str]]:
    """Return ordered (variable, rendered value) pairs from a generated name."""
    variables = _find_named_block(
        name_block,
        "variables",
    )

    if not variables:
        return []

    values: list[tuple[str, str]] = []

    pattern = re.compile(
        r'(?ms)key="(?P<variable>[^"]+)"\s*value\s*=\s*(?P<brace>\{)'
    )

    for match in pattern.finditer(
        variables
    ):
        value_block = _extract_braced_after(
            variables,
            match.start("brace"),
        )

        if not value_block:
            continue

        value_keys = re.findall(
            r'key="([^"]+)"',
            value_block,
        )

        if not value_keys:
            continue

        # The first key inside value={...} is the concrete rendered value for
        # the common Stellaris generated-name structures we care about.
        raw_value = value_keys[0]
        rendered = _resolved_or_humanised(
            source_save,
            raw_value,
            suffix=suffix,
        )

        if not rendered:
            continue

        if rendered.casefold() in {
            "name",
            "planet",
            "system",
        }:
            continue

        values.append(
            (
                match.group("variable"),
                rendered,
            )
        )

    return values


def _generated_name_from_block(
    name_block: str,
    source_save: Path,
    *,
    suffix: str | None = None,
) -> str | None:
    """
    Render common Stellaris generated names instead of returning only the first
    concrete token.

    This matters for names such as "Pleione Prime" and "Wenkwort Artem", where
    the save can store a PLANET_NAME_FORMAT wrapper plus multiple variables.
    """
    top_match = re.search(
        r'(?m)^\s*key="([^"]+)"',
        name_block,
    )

    if not top_match:
        return None

    wrapper_key = top_match.group(1)
    variables = _name_variable_values(
        name_block,
        source_save,
        suffix=suffix,
    )

    if not variables:
        return None

    values_by_key = {
        key: value
        for key, value in variables
    }

    # If localisation exposes a variable template, honour it. This keeps the
    # resolver compatible with modded formats without hard-coding word order.
    template = resolve_localisation_key(
        source_save,
        wrapper_key,
    )

    if template and "$" in template:
        rendered = template

        for key, value in variables:
            rendered = rendered.replace(
                f"${key}$",
                value,
            )

        rendered = re.sub(
            r"\$[^$]+\$",
            "",
            rendered,
        )
        rendered = _normalise_space(
            rendered
        )

        if rendered:
            return rendered

    upper = wrapper_key.upper()

    # NEW_COLONY_NAME_* is normally just a NAME wrapper. Returning the NAME
    # variable avoids exposing the localisation wrapper itself.
    if upper.startswith(
        "NEW_COLONY_NAME_"
    ):
        return (
            values_by_key.get("NAME")
            or variables[0][1]
        )

    # PLANET_NAME_FORMAT and similar generated display names are composites.
    # Preserve variable order from the save and de-duplicate repeated tokens.
    if (
        upper.startswith("PLANET_NAME_")
        or upper.startswith("STAR_NAME_")
        or upper.endswith("_NAME_FORMAT")
    ):
        ordered: list[str] = []

        for _, value in variables:
            if not ordered or ordered[-1].casefold() != value.casefold():
                ordered.append(
                    value
                )

        composed = _normalise_space(
            " ".join(
                ordered
            )
        )

        if composed:
            return composed

    return None


def _display_name_from_record(
    record: str | None,
    source_save: Path,
    *,
    fallback: str,
    suffix: str | None = None,
) -> str:
    if not record:
        return fallback

    direct = re.search(
        r'(?m)^\s*name\s*=\s*"([^"]+)"',
        record,
    )

    if direct:
        value = _normalise_space(
            direct.group(1)
        )

        if value:
            return value

    name_block = _find_named_block(
        record,
        "name",
    )

    if not name_block:
        return fallback

    keys = re.findall(
        r'key="([^"]+)"',
        name_block,
    )

    if not keys:
        return fallback

    # A nested generated-name variable (for example NUMERAL=IV) may itself be
    # literal. Only treat the whole name block as literal when it has no
    # variables wrapper of its own.
    if (
        not _find_named_block(
            name_block,
            "variables",
        )
        and re.search(
            r"(?m)^\s*literal\s*=\s*yes",
            name_block,
        )
    ):
        return _normalise_space(
            keys[0]
        ) or fallback

    generated = _generated_name_from_block(
        name_block,
        source_save,
        suffix=suffix,
    )

    if generated:
        return generated

    def wrapper(key: str) -> bool:
        upper = key.upper()

        return (
            key in {
                "NAME",
                "PREFIX",
                "PARENT",
                "NUMERAL",
                "base",
                "adjective",
                "1",
                "2",
            }
            or upper.startswith("NEW_COLONY_NAME_")
            or upper.startswith("STAR_NAME_")
            or upper.startswith("PLANET_NAME_")
            or upper.endswith("_NAME_FORMAT")
        )

    # Generated names commonly put the concrete name in a variable after a
    # generic wrapper such as NEW_COLONY_NAME_1 or STAR_NAME_1_OF_3.
    ordered = keys[1:] + keys[:1]

    for key in ordered:
        if wrapper(key):
            continue

        value = _resolved_or_humanised(
            source_save,
            key,
            suffix=suffix,
        )

        if value and value.casefold() not in {
            "name",
            "planet",
            "system",
        }:
            return value

    for key in keys:
        value = _resolved_or_humanised(
            source_save,
            key,
            suffix=suffix,
        )

        if value and value.casefold() not in {
            "name",
            "planet",
            "system",
        }:
            return value

    return fallback


def planet_display_name(
    gamestate: str,
    planet_id: int,
    source_save: Path,
) -> str | None:
    planets = _find_named_block(
        gamestate,
        "planet",
    )

    record = _top_numeric_record(
        planets,
        planet_id,
    )

    if not record:
        return None

    value = _display_name_from_record(
        record,
        source_save,
        fallback="Unnamed World",
        suffix="planet",
    )

    if (
        "%" in value
        or "$" in value
        or value.upper().startswith("STAR NAME")
        or value.upper().startswith("PLANET NAME")
        or value.upper().startswith("NEW COLONY NAME")
    ):
        return "Unnamed World"

    return value


def world_location_display_name(
    gamestate: str,
    location_id: int,
    source_save: Path,
) -> str | None:
    """
    Resolve a leader/location planet reference across Stellaris save formats.

    Current saves can expose colony IDs in leader assignments while older saves
    expose planet IDs directly.
    """
    colonies = _find_named_block(
        gamestate,
        "colony",
    )

    if colonies is not None:
        colony_record = _top_numeric_record(
            colonies,
            location_id,
        )

        if colony_record:
            carrier = _find_named_block(
                colony_record,
                "carrier",
            )

            planet_id = _int_scalar(
                carrier,
                "reference",
            )

            if planet_id is not None:
                return planet_display_name(
                    gamestate,
                    planet_id,
                    source_save,
                )

    return planet_display_name(
        gamestate,
        location_id,
        source_save,
    )


def _system_display_name(
    galactic_objects: str | None,
    system_id: int | None,
    source_save: Path,
) -> str | None:
    if system_id is None:
        return None

    record = _top_numeric_record(
        galactic_objects,
        system_id,
    )

    if not record:
        return None

    value = _display_name_from_record(
        record,
        source_save,
        fallback="Unnamed System",
        suffix="system",
    )

    if (
        "%" in value
        or "$" in value
        or value.upper().startswith("STAR NAME")
    ):
        return "Unnamed System"

    return value


def _planet_class_name(
    source_save: Path,
    key: str | None,
) -> str | None:
    if not key:
        return None

    resolved = resolve_localisation_key(
        source_save,
        key,
    )

    if resolved:
        return _normalise_space(
            resolved
        )

    value = key

    if value.startswith("pc_"):
        value = value[3:]

    special = {
        "gaia": "Gaia World",
        "continental": "Continental World",
        "ocean": "Ocean World",
        "tropical": "Tropical World",
        "desert": "Desert World",
        "arid": "Arid World",
        "savannah": "Savanna World",
        "alpine": "Alpine World",
        "arctic": "Arctic World",
        "tundra": "Tundra World",
        "volcanic": "Volcanic World",
        "hive": "Hive World",
        "machine": "Machine World",
        "ecumenopolis": "Ecumenopolis",
        "habitat": "Habitat",
    }

    if value in special:
        return special[value]

    return value.replace(
        "_",
        " ",
    ).title()


def _designation_name(
    source_save: Path,
    key: str | None,
) -> str | None:
    if not key:
        return None

    # Prefer stable player-facing names for well-known vanilla designation
    # keys. Localisation files can contain duplicate/context-specific labels
    # (for example "Central Core" or "University Planet") that are not the
    # designation shown in the colony outliner.
    mapping = {
        "col_capital": "Capital",
        "col_capital_hive": "Hive Capital",
        "col_capital_machine": "Machine Capital",
        "col_research": "Tech-World",
        "col_mining": "Mining World",
        "col_generator": "Generator World",
        "col_farming": "Agri-World",
        "col_forge": "Forge World",
        "col_factory": "Factory World",
        "col_industrial": "Industrial World",
        "col_hive": "Hive World",
    }

    if key in mapping:
        return mapping[key]

    resolved = resolve_localisation_key(
        source_save,
        key,
    )

    if resolved:
        return _normalise_space(
            resolved
        )

    value = key

    if value.startswith("col_"):
        value = value[4:]

    return value.replace(
        "_",
        " ",
    ).title()


def _valid_stellaris_date(
    value: str | None,
) -> str | None:
    if not value or value == "0.01.01":
        return None

    if not re.fullmatch(
        r"-?\d+\.\d{2}\.\d{2}",
        value,
    ):
        return None

    return value


def extract_world_snapshot(
    *,
    gamestate: str,
    profile: EmpireProfile,
    source_save: Path,
    snapshot_id: int,
    leader_names: dict[int, str] | None = None,
) -> WorldSnapshot:
    country_id = profile.player_country_id

    if country_id is None:
        raise ValueError(
            "Could not determine player country ID for world parsing."
        )

    countries = _find_named_block(
        gamestate,
        "country",
    )

    country = _top_numeric_record(
        countries,
        country_id,
    )

    if not country:
        raise ValueError(
            "Could not locate player country record for world parsing."
        )

    owned_ids = _id_list_from_block(
        country,
        "owned_planets",
    )

    capital_ref = _int_scalar(
        country,
        "capital",
    )

    colonies = _find_named_block(
        gamestate,
        "colony",
    )

    planets = _find_named_block(
        gamestate,
        "planet",
    )

    galactic_objects = _find_named_block(
        gamestate,
        "galactic_object",
    )

    leader_names = leader_names or {}

    modern_colonies = colonies is not None
    worlds: dict[int, WorldState] = {}

    capital_planet_id: int | None = None

    if modern_colonies and capital_ref is not None:
        capital_colony = _top_numeric_record(
            colonies,
            capital_ref,
        )

        capital_carrier = _find_named_block(
            capital_colony or "",
            "carrier",
        )

        capital_planet_id = _int_scalar(
            capital_carrier,
            "reference",
        )
    elif capital_ref is not None:
        capital_planet_id = capital_ref

    for owned_id in owned_ids:
        colony_id: int | None = None
        state_record: str | None = None
        planet_id: int | None = None

        if modern_colonies:
            colony_record = _top_numeric_record(
                colonies,
                owned_id,
            )

            if colony_record:
                carrier = _find_named_block(
                    colony_record,
                    "carrier",
                )

                planet_id = _int_scalar(
                    carrier,
                    "reference",
                )

                if planet_id is not None:
                    colony_id = owned_id
                    state_record = colony_record

        if planet_id is None:
            # Older saves store colony state directly on the planet and
            # owned_planets contains planet IDs rather than colony IDs.
            planet_id = owned_id

        planet_record = _top_numeric_record(
            planets,
            planet_id,
        )

        if not planet_record:
            continue

        if state_record is None:
            state_record = planet_record

        coordinate = _find_named_block(
            planet_record,
            "coordinate",
        )

        system_id = _int_scalar(
            coordinate,
            "origin",
        )

        planet_class_key = _scalar(
            planet_record,
            "planet_class",
        )

        governor_id = _int_scalar(
            state_record,
            "governor",
        )

        if governor_id is None:
            governor_id = _int_scalar(
                planet_record,
                "governor",
            )

        designation_key = (
            _scalar(
                state_record,
                "final_designation",
            )
            or _scalar(
                state_record,
                "designation",
            )
        )

        district_count = len(
            _id_list_from_block(
                state_record,
                "districts",
            )
        )

        building_count = len(
            _id_list_from_block(
                state_record,
                "buildings_cache",
            )
        )

        world = WorldState(
            planet_id=planet_id,
            colony_id=colony_id,
            name=_display_name_from_record(
                planet_record,
                source_save,
                fallback="Unnamed World",
                suffix="planet",
            ),
            system_id=system_id,
            system_name=_system_display_name(
                galactic_objects,
                system_id,
                source_save,
            ),
            planet_class_key=planet_class_key,
            planet_class_name=_planet_class_name(
                source_save,
                planet_class_key,
            ),
            planet_size=_int_scalar(
                planet_record,
                "planet_size",
            ),
            colonize_date=_valid_stellaris_date(
                _scalar(
                    planet_record,
                    "colonize_date",
                )
                or _scalar(
                    state_record,
                    "colonize_date",
                )
            ),
            owner_id=_int_scalar(
                planet_record,
                "owner",
            ),
            original_owner_id=_int_scalar(
                planet_record,
                "original_owner",
            ),
            controller_id=_int_scalar(
                planet_record,
                "controller",
            ),
            governor_id=governor_id,
            governor_name=(
                leader_names.get(
                    governor_id
                )
                if governor_id is not None
                else None
            ),
            population=_int_scalar(
                state_record,
                "num_sapient_pops",
            ),
            employable_pops=_int_scalar(
                state_record,
                "employable_pops",
            ),
            designation_key=designation_key,
            designation_name=_designation_name(
                source_save,
                designation_key,
            ),
            ascension_tier=_int_scalar(
                state_record,
                "ascension_tier",
            ),
            district_count=district_count,
            building_count=building_count,
            is_capital=(
                capital_planet_id == planet_id
            ),
        )

        worlds[
            planet_id
        ] = world

    return WorldSnapshot(
        snapshot_id=snapshot_id,
        game_date=profile.game_date,
        player_country_id=country_id,
        worlds=worlds,
    )
