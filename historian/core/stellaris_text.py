from __future__ import annotations

from pathlib import Path
import re
from contextlib import contextmanager
from contextvars import ContextVar

# A per-save lifetime is essential: retaining large Stellaris text across
# quarterly saves would increase memory use without bound.
_PARSE_INDEX: ContextVar[dict | None] = ContextVar("historian_scan_index", default=None)
_INDEX_MIN_CHARS = 100_000


@contextmanager
def indexed_scan_scope():
    token = _PARSE_INDEX.set({"blocks": {}, "numbers": {}, "indented": {}})
    try:
        yield
    finally:
        _PARSE_INDEX.reset(token)


from ..localisation import resolve_localisation_key


# A native Stellaris gamestate can exceed 50 MB. Scanning every character in
# Python for every block extraction made Ships, People and Science progressively
# more expensive as the galaxy grew. Find structural tokens in C instead, and
# inspect Python state only for braces / quotes. Semantics remain identical.
_STRUCTURAL_TOKENS = re.compile(r'[{}"]')


def _braced_content_and_end(text: str, token_start: int) -> tuple[str | None, int | None]:
    brace = text.find("{", token_start)
    if brace < 0:
        return None, None

    depth = 0
    quoted = False
    for match in _STRUCTURAL_TOKENS.finditer(text, brace):
        index = match.start()
        char = match.group()
        if char == '"':
            # Quoted escaped quotes are not delimiters. A run of backslashes
            # only escapes a quote when its length is odd (\\" vs \").
            backslashes = 0
            before = index - 1
            while before >= brace and text[before] == "\\":
                backslashes += 1
                before -= 1
            if backslashes % 2 == 0:
                quoted = not quoted
        elif not quoted:
            if char == "{":
                depth += 1
            else:
                depth -= 1
                if depth == 0:
                    return text[brace + 1:index], index + 1
    return None, None


def _extract_braced_after(text: str, token_start: int) -> str | None:
    content, _end = _braced_content_and_end(text, token_start)
    return content


def _find_named_block(text: str, key: str) -> str | None:
    context = _PARSE_INDEX.get()
    use_cache = context is not None and len(text) >= _INDEX_MIN_CHARS
    cache_key = (id(text), key)
    if use_cache:
        saved = context["blocks"].get(cache_key)
        if saved is not None:
            return saved[1]

    match = re.search(rf'(?m)^{re.escape(key)}\s*=\s*\{{', text)
    if not match:
        match = re.search(rf'(?m)^\s*{re.escape(key)}\s*=\s*\{{', text)
    result = _extract_braced_after(text, match.start()) if match else None
    if use_cache:
        # Hold text while cached: re-used Python object IDs can otherwise
        # silently associate a different subsection with the old result.
        context["blocks"][cache_key] = (text, result)
    return result


def _top_numeric_records(block: str | None):
    if not block:
        return

    pattern = re.compile(r'(?m)^\s*(\d+)\s*=\s*\{')
    position = 0
    while (match := pattern.search(block, position)) is not None:
        # Extract the content and the record endpoint in ONE balanced scan.
        # The previous implementation rescanned every record a second time.
        record, end = _braced_content_and_end(block, match.start())
        if record is None or end is None:
            break
        yield int(match.group(1)), record
        position = end


def _numeric_record(block: str | None, numeric_id: int) -> str | None:
    if not block:
        return None
    context = _PARSE_INDEX.get()
    if context is not None and len(block) >= _INDEX_MIN_CHARS:
        key = id(block)
        entry = context["numbers"].get(key)
        if entry is None:
            entry = {"text": block, "lookups": 0, "individual": {}, "offsets": None}
            context["numbers"][key] = entry
        if entry["offsets"] is not None:
            span = entry["offsets"].get(numeric_id)
            return block[span[0]:span[1]] if span is not None else None
        if numeric_id in entry["individual"]:
            return entry["individual"][numeric_id]
        entry["lookups"] += 1
        if entry["lookups"] >= 3:
            # The indexed traversal skips nested numeric IDs and is shared
            # among all Ships, People and Science lookups for this save.
            offsets = {}
            position = 0
            pattern = re.compile(r'(?m)^\s*(\d+)\s*=\s*\{')
            while (match := pattern.search(block, position)) is not None:
                opening = block.find("{", match.start())
                _content, end = _braced_content_and_end(block, match.start())
                if end is None:
                    break
                offsets[int(match.group(1))] = (opening + 1, end - 1)
                position = end
            entry["offsets"] = offsets
            entry["individual"].clear()
            span = offsets.get(numeric_id)
            return block[span[0]:span[1]] if span is not None else None
    else:
        entry = None

    match = re.search(rf'(?m)^\s*{numeric_id}\s*=\s*\{{', block)
    result = _extract_braced_after(block, match.start()) if match else None
    if entry is not None:
        entry["individual"][numeric_id] = result
    return result


def _indented_numeric_record(block: str | None, numeric_id: int) -> str | None:
    """Resolve only direct numeric children at the first record's indent."""
    if not block:
        return None
    context = _PARSE_INDEX.get()
    use_cache = context is not None and len(block) >= _INDEX_MIN_CHARS
    key = id(block)
    entry = context["indented"].get(key) if use_cache else None
    if entry is None:
        first = re.search(r'(?m)^([ \t]*)\d+\s*=\s*\{', block)
        if not first:
            return None
        entry = {"text": block, "indent": first.group(1), "count": 0,
                 "individual": {}, "offsets": None}
        if use_cache:
            context["indented"][key] = entry
    if entry["offsets"] is not None:
        span = entry["offsets"].get(numeric_id)
        return block[span[0]:span[1]] if span else None
    if numeric_id in entry["individual"]:
        return entry["individual"][numeric_id]
    entry["count"] += 1
    if use_cache and entry["count"] >= 3:
        pattern = re.compile(rf'(?m)^{re.escape(entry["indent"])}(\d+)\s*=\s*\{{')
        offsets = {}
        for match in pattern.finditer(block):
            opening = block.find("{", match.start())
            _content, end = _braced_content_and_end(block, match.start())
            if end is not None:
                offsets[int(match.group(1))] = (opening + 1, end - 1)
        entry["offsets"] = offsets
        entry["individual"].clear()
        span = offsets.get(numeric_id)
        return block[span[0]:span[1]] if span else None
    match = re.search(rf'(?m)^{re.escape(entry["indent"])}{numeric_id}\s*=\s*\{{', block)
    result = _extract_braced_after(block, match.start()) if match else None
    if use_cache:
        entry["individual"][numeric_id] = result
    return result


def _scalar(
    text: str | None,
    key: str,
) -> str | None:
    if not text:
        return None

    match = re.search(
        rf'(?m)^\s*{re.escape(key)}\s*=\s*(?:"([^"]*)"|([^\s{{}}]+))',
        text,
    )

    if not match:
        return None

    return match.group(1) or match.group(2)


def _int_scalar(
    text: str | None,
    key: str,
) -> int | None:
    value = _scalar(
        text,
        key,
    )

    if value is None:
        return None

    try:
        return int(value)
    except ValueError:
        return None


def _id_list_from_block(
    text: str | None,
    key: str,
) -> tuple[int, ...]:
    block = _find_named_block(
        text or "",
        key,
    )

    if not block:
        return ()

    return tuple(
        int(value)
        for value in re.findall(
            r'(?<![\w.])(\d+)(?![\w.])',
            block,
        )
    )


def _humanise_key(key: str | None) -> str | None:
    if not key:
        return None

    value = key

    for marker in (
        "_SHIP_",
        "_FLEET_",
        "_CHR_",
        "_CLASS_",
    ):
        if marker in value:
            value = value.split(
                marker,
                1,
            )[1]
            break

    for prefix in (
        "NAME_",
        "SPEC_",
        "shipclass_",
    ):
        if value.startswith(prefix):
            value = value[len(prefix):]

    value = value.replace(
        "_",
        " ",
    )

    value = re.sub(
        r"(?<=[a-z0-9])(?=[A-Z])",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    return value or key


def _resolved_key(
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
        return resolved

    return _humanise_key(
        key
    )


def _name_block(
    record: str,
) -> str | None:
    match = re.search(
        r'(?m)^\s*name\s*=\s*\{',
        record,
    )

    if not match:
        return None

    return _extract_braced_after(
        record,
        match.start(),
    )


def _record_name(
    record: str,
    source_save: Path,
    *,
    fallback: str,
) -> str:
    direct = re.search(
        r'(?m)^\s*name\s*=\s*"([^"]+)"',
        record,
    )

    if direct:
        return direct.group(1).strip() or fallback

    block = _name_block(
        record
    )

    if not block:
        return fallback

    keys = re.findall(
        r'key="([^"]+)"',
        block,
    )

    if not keys:
        return fallback

    if re.search(
        r'(?m)^\s*literal\s*=\s*yes',
        block,
    ):
        return keys[0]

    # Prefer concrete ship/fleet/character localisation keys over formatting
    # wrappers such as PREFIX_NAME_FORMAT.
    for marker in (
        "_SHIP_",
        "_FLEET_",
    ):
        for key in keys:
            if marker in key:
                return _resolved_key(
                    source_save,
                    key,
                ) or fallback

    character_keys = [
        key
        for key in keys
        if "_CHR_" in key
    ]

    if character_keys:
        parts = [
            _resolved_key(
                source_save,
                key,
            )
            for key in character_keys[:2]
        ]

        parts = [
            part
            for part in parts
            if part
        ]

        if parts:
            return " ".join(parts)

    first_key = keys[0]

    # Starbase names commonly wrap the actual system key in variables.
    if first_key.startswith(
        "STARBASE_"
    ) or first_key == "shipclass_starbase_name":
        for key in keys[1:]:
            if (
                key.startswith("SPEC_")
                or key.startswith("NAME_")
            ):
                system = _resolved_key(
                    source_save,
                    key,
                )

                if system:
                    return f"{system} Starbase"

    for key in keys:
        if key in {
            "PREFIX_NAME_FORMAT",
            "%LEADER_1%",
            "%ACRONYM%",
            "%ADJECTIVE%",
            "NAME",
            "PREFIX",
            "base",
            "adjective",
            "1",
            "2",
        }:
            continue

        resolved = _resolved_key(
            source_save,
            key,
        )

        if resolved:
            return resolved

    return _resolved_key(
        source_save,
        first_key,
    ) or fallback
