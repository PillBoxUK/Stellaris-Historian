"""Stellaris conditional-name grammar rendered without publishing script tokens."""
from __future__ import annotations
import re

def clean_stellaris_name(raw: str, gender: str | None = None) -> str:
    """Render a saved conditional gender-name format, retaining its raw form in evidence.

    Stellaris produces text such as ``Sextus&!masc $1$ Cloelia|||masc:$1$ Cloelius``.
    Never print the grammar. When a gender is unavailable, retain the unambiguous
    forename rather than guessing between two conflicting surnames.
    """
    text = " ".join(str(raw or "").split())
    match = re.fullmatch(r"(.*?)&!masc\s+\$1\$\s+(.*?)\|\|\|masc:\$1\$\s+(.*)", text, re.I)
    if match:
        first, feminine, masculine = (part.strip() for part in match.groups())
        sex = str(gender or "").casefold()
        surname = (masculine if sex in {"male", "masculine", "masc"} else
                   feminine if sex in {"female", "feminine", "fem"} else "")
        return " ".join(part for part in (first, surname) if part)
    # The simpler Stellaris alternative form can occur without &!masc.
    match = re.fullmatch(r"(.*?)\$1\$\s+(.*?)\|\|\|masc:\$1\$\s+(.*)", text, re.I)
    if match:
        first, feminine, masculine = (part.strip() for part in match.groups())
        sex = str(gender or "").casefold()
        surname = (masculine if sex in {"male", "masculine", "masc"} else
                   feminine if sex in {"female", "feminine", "fem"} else "")
        return " ".join(part for part in (first, surname) if part)
    return text


