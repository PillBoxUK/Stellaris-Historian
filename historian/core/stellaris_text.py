from __future__ import annotations

from pathlib import Path
import re

from ..localisation import resolve_localisation_key


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
        rf'(?m)^{re.escape(key)}\s*=\s*\{{',
        text,
    )

    if not match:
        match = re.search(
            rf'(?m)^\s*{re.escape(key)}\s*=\s*\{{',
            text,
        )

    if not match:
        return None

    return _extract_braced_after(
        text,
        match.start(),
    )


def _top_numeric_records(block: str | None):
    if not block:
        return

    pattern = re.compile(
        r'(?m)^\s*(\d+)\s*=\s*\{'
    )

    position = 0

    while True:
        match = pattern.search(
            block,
            position,
        )

        if not match:
            break

        record = _extract_braced_after(
            block,
            match.start(),
        )

        if record is None:
            break

        brace = block.find(
            "{",
            match.start(),
        )

        depth = 0
        in_quote = False
        escaped = False
        end = None

        for index in range(brace, len(block)):
            char = block[index]

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
                    end = index + 1
                    break

        yield int(match.group(1)), record

        if end is None:
            break

        position = end


def _numeric_record(
    block: str | None,
    numeric_id: int,
) -> str | None:
    if not block:
        return None

    match = re.search(
        rf'(?m)^\s*{numeric_id}\s*=\s*\{{',
        block,
    )

    if not match:
        return None

    return _extract_braced_after(
        block,
        match.start(),
    )


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
