from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import zipfile


@dataclass(frozen=True)
class CampaignSummary:
    save_path: str
    folder_name: str
    empire_name: str
    game_date: str
    version: str | None
    modified: float


@dataclass(frozen=True)
class EmpireProfile:
    empire_name: str
    game_date: str
    version: str | None
    player_country_id: int | None
    government_type: str | None
    authority: str | None
    origin: str | None
    ethics: tuple[str, ...]
    civics: tuple[str, ...]


def _quoted_value(text: str, key: str) -> str | None:
    match = re.search(
        rf'(?m)^\s*{re.escape(key)}\s*=\s*"([^"]*)"',
        text,
    )
    return match.group(1) if match else None


def _clean_name(raw: str | None) -> str:
    if not raw:
        return "Unknown Empire"

    # Some mods put colour/icon control codes into the meta name.
    colour = re.search(r"\x11[A-Za-z](.*?)\x11!", raw)
    if colour:
        raw = colour.group(1)

    raw = re.sub(r"\x13[^\x13]*\x13", " ", raw)
    raw = "".join(ch if ord(ch) >= 32 else " " for ch in raw)
    raw = re.sub(r"\s+", " ", raw).strip()

    return raw or "Unknown Empire"


def _extract_braced_after(text: str, token_start: int) -> str | None:
    brace = text.find("{", token_start)

    if brace < 0:
        return None

    depth = 0
    in_quote = False
    escaped = False

    for index in range(brace, len(text)):
        char = text[index]

        if in_quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_quote = False
            continue

        if char == '"':
            in_quote = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1

            if depth == 0:
                return text[brace + 1:index]

    return None


def _find_named_block(text: str, key: str) -> str | None:
    match = re.search(
        rf'(?m)^\s*{re.escape(key)}\s*=\s*\{{',
        text,
    )

    if not match:
        return None

    return _extract_braced_after(text, match.start())


def _find_numeric_child(block: str, numeric_id: int) -> str | None:
    match = re.search(
        rf'(?m)^\s*{numeric_id}\s*=\s*\{{',
        block,
    )

    if not match:
        return None

    return _extract_braced_after(block, match.start())


def _player_country_id(gamestate: str) -> int | None:
    player = _find_named_block(gamestate, "player")

    if not player:
        return None

    match = re.search(
        r"(?m)^\s*country\s*=\s*(\d+)",
        player,
    )

    return int(match.group(1)) if match else None


def _government_profile(
    gamestate: str,
    country_id: int | None,
) -> tuple[str | None, str | None, str | None, tuple[str, ...], tuple[str, ...]]:
    if country_id is None:
        return None, None, None, (), ()

    countries = _find_named_block(gamestate, "country")

    if not countries:
        return None, None, None, (), ()

    country = _find_numeric_child(countries, country_id)

    if not country:
        return None, None, None, (), ()

    government = _find_named_block(country, "government")
    ethos = _find_named_block(country, "ethos")

    government_type = _quoted_value(government or "", "type")
    authority = _quoted_value(government or "", "authority")
    origin = _quoted_value(government or "", "origin")

    civics: tuple[str, ...] = ()

    if government:
        civics_block = _find_named_block(government, "civics")

        if civics_block:
            civics = tuple(re.findall(r'"([^"]+)"', civics_block))

    ethics: tuple[str, ...] = ()

    if ethos:
        # Stellaris uses more than one ethics encoding across saves/mods.
        # Common forms are:
        #   ethic="ethic_name"
        # or:
        #   ethics={ "ethic_name" "ethic_other" }
        ethics = tuple(
            re.findall(
                r'(?m)^\s*ethic\s*=\s*"([^"]+)"',
                ethos,
            )
        )

        if not ethics:
            ethics_block = _find_named_block(ethos, "ethics")

            if ethics_block:
                ethics = tuple(
                    re.findall(
                        r'"([^"]+)"',
                        ethics_block,
                    )
                )

    return government_type, authority, origin, ethics, civics



def read_save_texts(path: Path) -> tuple[str, str]:
    """Read meta and gamestate in a single ZIP open."""
    with zipfile.ZipFile(path, "r") as archive:
        meta = archive.read("meta").decode("utf-8", errors="replace")
        gamestate = archive.read("gamestate").decode("utf-8", errors="replace")
    return meta, gamestate


def empire_profile_from_text(meta: str, gamestate: str) -> EmpireProfile:
    empire_name = _clean_name(_quoted_value(meta, "name"))
    game_date = _quoted_value(meta, "date") or "Unknown"
    version = _quoted_value(meta, "version")
    country_id = _player_country_id(gamestate)
    government_type, authority, origin, ethics, civics = _government_profile(
        gamestate, country_id
    )
    return EmpireProfile(
        empire_name=empire_name,
        game_date=game_date,
        version=version,
        player_country_id=country_id,
        government_type=government_type,
        authority=authority,
        origin=origin,
        ethics=ethics,
        civics=civics,
    )


def read_campaign_summary(path: Path) -> CampaignSummary:
    stat = path.stat()

    with zipfile.ZipFile(path, "r") as archive:
        meta = archive.read("meta").decode("utf-8", errors="replace")

    return CampaignSummary(
        save_path=str(path),
        folder_name=path.parent.name,
        empire_name=_clean_name(_quoted_value(meta, "name")),
        game_date=_quoted_value(meta, "date") or "Unknown",
        version=_quoted_value(meta, "version"),
        modified=stat.st_mtime,
    )


def read_empire_profile(path: Path) -> EmpireProfile:
    meta, gamestate = read_save_texts(path)
    return empire_profile_from_text(meta, gamestate)


def valid_stellaris_save(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            names = set(archive.namelist())

            if "meta" not in names or "gamestate" not in names:
                return False

            archive.read("meta")

        return True

    except (OSError, zipfile.BadZipFile, KeyError):
        return False
