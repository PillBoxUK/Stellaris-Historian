"""Publication-only treatment of unresolved Stellaris names.

Game/save name expressions are evidence and remain untouched in SQLite and
source archives. The readable Imperial Annals must not mistake an unresolved
script/localisation token for a person's, ship's, or world's proper name.

No invented proper names and no changes to the underlying evidence layer.
"""
from __future__ import annotations

import re

_UNRESOLVED = re.compile(
    r"(?:\bPREFIX_NAME_FORMAT\b|\b(?:NAME|SHIP|FLEET|LEADER|COUNTRY|PLANET|SYSTEM)_" 
    r"[A-Z][A-Z0-9_]*\b|\$[^\s$]+\$|\[[A-Za-z][A-Za-z0-9_.]*\]|"
    r"%(?:ADJ|NAME|PREFIX|SUFFIX)%|\b(?:[A-Za-z0-9]+_)?(?:GetName|GetAdj)\b)",
    re.IGNORECASE,
)


def unresolved(value: object) -> bool:
    return bool(_UNRESOLVED.search(str(value or "")))


def usable_name(value: object) -> bool:
    text = str(value or "").strip()
    return bool(text) and not unresolved(text) and not text.casefold() in {
        'none', 'null', 'unknown', 'unnamed', 'unresolved', '4294967295'
    }


def publication_assignment(value: object, location_type: str = '') -> str:
    """Keep the supported *kind* of assignment when its name is unresolved.

    "Science Ship: PREFIX_NAME_FORMAT" -> "aboard a science vessel";
    the technical original remains stored in the dated cache/database.
    """
    raw = str(value or '').strip()
    if not raw:
        return ''
    if not unresolved(raw):
        return raw
    low = (raw + ' ' + str(location_type or '')).casefold()
    if 'science ship' in low:
        return 'aboard a science vessel whose name is not preserved'
    if 'construction ship' in low:
        return 'aboard a construction vessel whose name is not preserved'
    if 'colony ship' in low:
        return 'aboard a colony vessel whose name is not preserved'
    if 'fleet' in low:
        return 'with a fleet whose name is not preserved'
    if 'planet' in low or 'colony' in low:
        return 'on a world whose name is not preserved'
    if 'system' in low:
        return 'in an unnamed system'
    return ''  # Unknown kind: don't claim an unsupported destination.


def ship_subject(name: str, ship_type: str) -> tuple[str, str]:
    """Return a display title/subject; no proper name is fabricated."""
    kind = str(ship_type or 'ship').strip().casefold()
    if usable_name(name):
        return f'{name} enters service', f'the {kind} ship {name}'
    return f'A {kind} ship enters service', f'a {kind} ship'
