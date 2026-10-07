from __future__ import annotations

from pathlib import Path
import json
import os
import re
import tempfile
from typing import Callable

from ...core.stellaris_text import (
    _extract_braced_after,
    _find_named_block,
    _int_scalar,
    _numeric_record,
    _record_name,
    _scalar,
)
from ...db import Database
from ...localisation import _load_index_data, resolve_localisation_key
from ...save_reader import read_save_texts
from ...snapshot_cache import campaign_cache_dir, load_or_parse_snapshot
from .history import _publishable_diplomatic_actor
from .models import DiplomaticRelationState


ProgressCallback = Callable[[int, int, dict], None]

_HISTORY_JSON = "First_Contact_History.json"
_HISTORY_DEBUG = "First_Contact_History_Debug.txt"
_INVALID_OBJECT_ID = 4294967295


def _named_blocks(text: str | None, key: str):
    if not text:
        return
    pattern = re.compile(rf'(?m)^\s*{re.escape(key)}\s*=\s*\{{')
    for match in pattern.finditer(text):
        block = _extract_braced_after(text, match.start())
        if block is not None:
            yield block


def _valid_date(value: str | None) -> bool:
    return bool(value and re.fullmatch(r"\d+\.\d{2}\.\d{2}", value))


def _inline_scalar(text: str | None, key: str) -> str | None:
    if not text:
        return None
    match = re.search(
        rf'(?<![A-Za-z0-9_.:-]){re.escape(key)}\s*=\s*(?:"([^"]*)"|([^\s{{}}]+))',
        text,
    )
    if not match:
        return None
    return match.group(1) or match.group(2)


def _inline_int(text: str | None, key: str) -> int | None:
    value = _inline_scalar(text, key)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _any_named_block(text: str | None, key: str) -> str | None:
    if not text:
        return None
    match = re.search(
        rf'(?<![A-Za-z0-9_.:-]){re.escape(key)}\s*=\s*\{{',
        text,
    )
    if not match:
        return None
    return _extract_braced_after(text, match.start())


def _contact_record(gamestate: str, contact_id: int) -> str | None:
    for manager in _named_blocks(gamestate, "first_contacts"):
        contacts = _find_named_block(manager, "contacts")
        record = _numeric_record(contacts, contact_id)
        if record:
            return record
    return None


def _country_record(gamestate: str, country_id: int | None) -> str | None:
    if country_id is None:
        return None
    countries = _find_named_block(gamestate, "country")
    return _numeric_record(countries, country_id)


def _anonymous_blocks(text: str | None) -> tuple[str, ...]:
    """Return anonymous top-level ``{ ... }`` children from a variables block."""
    if not text:
        return ()
    result: list[str] = []
    depth = 0
    start: int | None = None
    in_quote = False
    escaped = False
    for index, char in enumerate(text):
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
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                result.append(text[start + 1:index])
                start = None
    return tuple(result)


def _name_block_for_field(record: str | None, field: str) -> str | None:
    # Country records contain nested objects that can themselves have name=...
    # fields. Only the direct child field belongs to the country identity.
    return _top_inline_block(record, field)


def _direct_name_scalar(record: str | None, field: str) -> str | None:
    value = _top_inline_scalar(record, field)
    return value.strip() if value else None


def _brace_depth_before(text: str, position: int) -> int:
    depth = 0
    in_quote = False
    escaped = False
    for char in text[:position]:
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
        elif char == "}" and depth:
            depth -= 1
    return depth


def _top_inline_scalar(text: str | None, key: str) -> str | None:
    if not text:
        return None
    pattern = re.compile(
        rf'(?<![A-Za-z0-9_.:-]){re.escape(key)}\s*=\s*(?:"([^"]*)"|([^\s{{}}]+))'
    )
    for match in pattern.finditer(text):
        if _brace_depth_before(text, match.start()) == 0:
            return match.group(1) or match.group(2)
    return None


def _top_inline_block(text: str | None, key: str) -> str | None:
    if not text:
        return None
    pattern = re.compile(rf'(?<![A-Za-z0-9_.:-]){re.escape(key)}\s*=\s*\{{')
    for match in pattern.finditer(text):
        if _brace_depth_before(text, match.start()) == 0:
            return _extract_braced_after(text, match.start())
    return None


def _clean_rendered_name(value: str | None) -> str | None:
    if not value:
        return None
    value = re.sub(r"\s+", " ", str(value)).strip(" \t\r\n,.-")
    return value or None


def _humanise_name_key(value: str | None) -> str | None:
    value = _clean_rendered_name(value)
    if not value:
        return None
    if value.startswith("NAME_"):
        value = value[5:]
    value = value.replace("_", " ")
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    return _clean_rendered_name(value)


def _technical_name_reason(value: str | None) -> str | None:
    """Return why a raw token is not safe as a public diplomatic identity.

    This deliberately judges the *raw* saved token before localisation. A script
    key such as ``build_waystation_poi_name`` can have perfectly readable English
    localisation while still not being the country's name.
    """
    raw = _clean_rendered_name(value)
    if not raw:
        return "missing"
    folded = raw.casefold()
    if re.fullmatch(r"country\s+\d+", folded):
        return "numeric_country_fallback"
    if any(token in raw for token in ("$", "%", "<", ">", "[", "]")):
        return "unresolved_placeholder"

    exact = {
        "build_waystation_poi_name",
        "gateway_system",
        "observing_country",
        "this_country",
        "lith_human",
        "global_event_country",
        "contact_country",
        "target_country",
    }
    if folded in exact:
        return "known_technical_identifier"

    technical_fragments = (
        "_poi_name",
        "poi_name",
        "build_waystation",
        "first_contact",
        "name_format",
        "format.",
        "event_target",
        "saved_target",
    )
    if any(fragment in folded for fragment in technical_fragments):
        return "technical_identifier"

    if raw.startswith("NAME_"):
        return "unresolved_NAME_key"
    if re.fullmatch(r"[a-z0-9_.:-]+", folded) and (
        "_" in folded or "." in folded
    ):
        return "raw_script_key"
    return None


def _candidate_rejection_reason(
    raw_value: str | None,
    resolved_value: str | None,
    method: str | None,
) -> str | None:
    raw = _clean_rendered_name(raw_value)
    raw_reason = _technical_name_reason(raw)
    grammar_key = bool(
        raw in {"%ADJ%", "%ADJECTIVE%"}
        or (raw and raw.startswith("format."))
        or (raw and raw.startswith("NAME_"))
    )
    if grammar_key and resolved_value and resolved_value != raw:
        # These are recognised name-template families. They are safe only after
        # rendering into a clean display value; the unresolved key itself is not.
        return _technical_name_reason(resolved_value)
    if raw_reason:
        return raw_reason
    return _technical_name_reason(resolved_value)


def _looks_resolved_country_name(value: str | None) -> bool:
    value = _clean_rendered_name(value)
    if not value:
        return False
    if _technical_name_reason(value):
        return False
    return bool(re.search(r"[A-Za-z]", value))


def _resolve_name_token(value: str | None, source_save: Path) -> tuple[str | None, str]:
    """Resolve a scalar/name token while preserving technical-key rejection."""
    raw = _clean_rendered_name(value)
    if not raw:
        return None, "missing"

    # NAME_* is a localisation family, not a display string. Prefer installed
    # localisation; if a DLC/mod key is absent, a conservative humanised fallback
    # is better than leaking the raw token into the journal.
    if raw.startswith("NAME_"):
        try:
            localised = resolve_localisation_key(source_save, raw)
        except Exception:
            localised = None
        localised = _clean_rendered_name(localised)
        if localised and not _technical_name_reason(localised):
            return localised, "localisation_key"
        humanised = _humanise_name_key(raw)
        if humanised and not _technical_name_reason(humanised):
            return humanised, "NAME_key_humanised"
        return raw, "rejected_unresolved_NAME_key"

    # Reject known script identifiers BEFORE looking up their human-readable
    # localisation. This is the v0.0.50.2 contact-91 failure mode.
    reason = _technical_name_reason(raw)
    if reason:
        return raw, f"rejected_{reason}"

    try:
        localised = resolve_localisation_key(source_save, raw)
    except Exception:
        localised = None
    localised = _clean_rendered_name(localised)
    if localised and not _technical_name_reason(localised):
        return localised, "localisation_key"

    return raw, "literal"


def _format_stellaris_adjective(noun: str | None, source_save: Path) -> str | None:
    """Apply Stellaris ``adj_NN*`` localisation grammar to a generated noun.

    Generated country-name expressions store the base species/identity noun in
    the ``adjective`` variable. Stellaris then chooses the longest matching
    ``adj_NN<suffix>`` rule (for example ``r -> *ran $1$``), substitutes the
    base noun into ``*`` and lets the remaining ``$1$`` continue the surrounding
    generated-name expression. If no installed rule matches, the noun is kept.
    """
    noun = _clean_rendered_name(noun)
    if not noun:
        return None

    try:
        values = _load_index_data(source_save).values
    except Exception:
        values = {}

    rules: list[tuple[str, str]] = []
    for raw_key, raw_template in values.items():
        key = str(raw_key)
        if not key.startswith("adj_NN"):
            continue
        suffix = key[len("adj_NN"):].lstrip("*")
        template = str(raw_template).split("|", 1)[0].strip()
        if template:
            rules.append((suffix, template))

    noun_folded = noun.casefold()
    for suffix, template in sorted(rules, key=lambda item: len(item[0]), reverse=True):
        if suffix and not noun_folded.endswith(suffix.casefold()):
            continue
        stem = noun[:-len(suffix)] if suffix else noun
        rendered = template.replace("*", stem)
        return _clean_rendered_name(rendered) or noun

    return noun


def _relation_name_search(
    politics_snapshots: list,
    rows: list[dict],
    country_id: int | None,
    source_save: Path,
    *,
    start_index: int,
) -> dict:
    """Scan later cached relation names, retaining rejected candidates too."""
    result = {"selected": None, "candidates": []}
    if country_id is None:
        return result

    seen: set[tuple[str | None, str | None]] = set()
    for index in range(max(0, start_index), len(politics_snapshots)):
        snapshot = politics_snapshots[index]
        relation = snapshot.relations.get(int(country_id))
        if relation is None:
            continue
        raw_name = _clean_rendered_name(relation.country_name)
        resolved, method = _resolve_name_token(raw_name, source_save)
        rejection = _candidate_rejection_reason(raw_name, resolved, method)
        accepted = bool(
            not rejection
            and resolved
            and _looks_resolved_country_name(resolved)
        )
        signature = (raw_name, resolved)
        if signature in seen:
            continue
        seen.add(signature)
        candidate = {
            "field": "relations_manager",
            "raw_value": raw_name,
            "value": resolved,
            "method": method,
            "accepted": accepted,
            "rejection_reason": rejection,
            "archive_date": str(rows[index]["game_date"]),
            "snapshot_index": index,
        }
        result["candidates"].append(candidate)
        if accepted and result["selected"] is None:
            result["selected"] = candidate

    result["candidates"] = result["candidates"][:24]
    return result


def _render_name_expression(
    block: str | None,
    source_save: Path,
    *,
    depth: int = 0,
    template_override: str | None = None,
) -> tuple[str | None, dict]:
    """Render the subset of Stellaris name grammar used by country identities.

    v0.0.50.4 retains the generated-empire forms that mattered in live testing:
    ``%ADJ%`` and ``%ADJECTIVE%``.  These formats can be nested several levels
    deep, so merely substituting the outer token loses words from names such as
    "Stellar Hazaran Council".
    """
    if not block or depth > 10:
        return None, {"method": "missing_or_too_deep"}

    key = _top_inline_scalar(block, "key")
    literal = (_top_inline_scalar(block, "literal") or "").casefold() == "yes"
    if not key:
        value_block = _top_inline_block(block, "value")
        if value_block:
            return _render_name_expression(value_block, source_save, depth=depth + 1)
        return None, {"method": "no_key"}

    if literal:
        cleaned = _clean_rendered_name(key)
        return cleaned, {
            "method": "literal",
            "key": key,
            "resolved": bool(cleaned),
        }

    try:
        resolved_template = resolve_localisation_key(source_save, key)
    except Exception:
        resolved_template = None
    resolved_template = _clean_rendered_name(resolved_template)

    if template_override is not None:
        template = template_override
        template_method = "generated_name_grammar"
    elif key == "%ADJECTIVE%":
        # Stellaris uses adj_format as the grammar template when %ADJECTIVE%
        # itself has no direct localisation entry. The semantic form is
        # "%adjective% $1$" for the country-name structures seen in saves.
        if resolved_template:
            template = resolved_template
        else:
            try:
                adj_format = resolve_localisation_key(source_save, "adj_format")
            except Exception:
                adj_format = None
            adj_format = _clean_rendered_name(adj_format)
            if adj_format and "adj" in adj_format:
                template = adj_format.replace("adj", "%adjective%", 1)
            else:
                template = "%adjective% $1$"
        template_method = "adjective_grammar"
    elif key == "%ADJ%":
        # %ADJ% is a wrapper around its first variable. The inner payload can
        # itself have a $1$ continuation. We render that continuation explicitly
        # below before placing it into the outer $1$ slot.
        template = "$1$"
        template_method = "adj_wrapper_grammar"
    elif resolved_template:
        template = resolved_template
        template_method = "templated_localisation"
    elif key.startswith("NAME_"):
        template = _humanise_name_key(key) or key
        template_method = "templated_NAME_key_humanised"
    else:
        template = key
        template_method = "templated_raw_key"

    substitutions: dict[str, str] = {}
    variables = _top_inline_block(block, "variables")
    variable_blocks = _anonymous_blocks(variables)
    for variable in variable_blocks:
        var_key = _top_inline_scalar(variable, "key")
        if not var_key:
            continue
        value_block = _top_inline_block(variable, "value")
        if value_block:
            # Special Stellaris %ADJ% rule: the wrapper's first value commonly
            # looks like key="Stellar" with its own variable 1 containing the
            # species adjective/government form. Treat the inner key as a prefix
            # template rather than dropping its continuation.
            if key == "%ADJ%" and var_key == "1":
                inner_key = _top_inline_scalar(value_block, "key")
                inner_vars = _top_inline_block(value_block, "variables")
                inner_has_one = any(
                    _top_inline_scalar(item, "key") == "1"
                    for item in _anonymous_blocks(inner_vars)
                )
                if inner_key and inner_has_one and not (
                    "$" in inner_key or "%" in inner_key or "<" in inner_key or "[" in inner_key
                ):
                    try:
                        inner_base = resolve_localisation_key(source_save, inner_key)
                    except Exception:
                        inner_base = None
                    inner_base = _clean_rendered_name(inner_base) or _humanise_name_key(inner_key) or inner_key
                    rendered, _meta = _render_name_expression(
                        value_block,
                        source_save,
                        depth=depth + 1,
                        template_override=f"{inner_base} $1$",
                    )
                else:
                    rendered, _meta = _render_name_expression(
                        value_block,
                        source_save,
                        depth=depth + 1,
                    )
            else:
                rendered, _meta = _render_name_expression(
                    value_block,
                    source_save,
                    depth=depth + 1,
                )
        else:
            rendered = _top_inline_scalar(variable, "value")
        rendered = _clean_rendered_name(rendered)
        if rendered and var_key == "adjective":
            rendered = _format_stellaris_adjective(rendered, source_save)
        if rendered:
            substitutions[var_key] = rendered

    rendered = str(template)
    for var_key, var_value in substitutions.items():
        for left, right in (("$", "$"), ("%", "%"), ("<", ">"), ("[", "]")):
            rendered = rendered.replace(f"{left}{var_key}{right}", var_value, 1)

    # Stellaris' adjective suffix templates can intentionally carry a numeric
    # continuation placeholder. After normal substitutions, discard any numeric
    # placeholder that remains unresolved rather than leaking it into the name.
    for pattern in (r"\[[0-9]*\]", r"\$[0-9]*\$", r"%[0-9]*%", r"<[0-9]*>"):
        rendered = re.sub(pattern, "", rendered)

    # Resolve second-level $LOCALISATION_KEY$ references conservatively.
    for _ in range(4):
        changed = False
        for token in tuple(dict.fromkeys(re.findall(r"\$([^$]+)\$", rendered))):
            if token in substitutions:
                continue
            try:
                replacement = resolve_localisation_key(source_save, token)
            except Exception:
                replacement = None
            if replacement:
                rendered = rendered.replace(f"${token}$", replacement)
                changed = True
        if not changed:
            break

    rendered = _clean_rendered_name(rendered)
    return rendered, {
        "method": template_method,
        "key": key,
        "template": template,
        "variables": substitutions,
        "resolved": _looks_resolved_country_name(rendered),
    }


def _country_name_info(
    gamestate: str,
    country_id: int | None,
    source_save: Path,
) -> dict:
    if country_id is None:
        return {"display": None, "resolved": None, "method": "no_country_id", "candidates": []}
    record = _country_record(gamestate, country_id)
    if not record:
        fallback = f"Country {country_id}"
        return {"display": fallback, "resolved": None, "method": "record_missing", "candidates": [fallback]}

    candidates: list[dict] = []

    direct_raw = _direct_name_scalar(record, "name")
    if direct_raw:
        direct, direct_method = _resolve_name_token(direct_raw, source_save)
        candidates.append({
            "field": "name",
            "raw_value": direct_raw,
            "value": direct,
            "method": direct_method,
        })

    name_block = _name_block_for_field(record, "name")
    if name_block:
        rendered, meta = _render_name_expression(name_block, source_save)
        if rendered:
            candidates.append({"field": "name", "value": rendered, **meta})

    # Preserve legacy extraction as a diagnostic fallback.  It is intentionally
    # lower priority because it does not substitute modern name variables.
    try:
        legacy = _record_name(record, source_save, fallback=f"Country {country_id}")
    except Exception:
        legacy = f"Country {country_id}"
    if legacy:
        candidates.append({"field": "legacy_name", "value": legacy, "method": "legacy_record_name"})

    pre_block = _name_block_for_field(record, "pre_communications_name")
    if pre_block:
        rendered, meta = _render_name_expression(pre_block, source_save)
        if rendered:
            candidates.append({"field": "pre_communications_name", "value": rendered, **meta})
    pre_direct_raw = _direct_name_scalar(record, "pre_communications_name")
    if pre_direct_raw:
        pre_direct, pre_method = _resolve_name_token(pre_direct_raw, source_save)
        candidates.append({
            "field": "pre_communications_name",
            "raw_value": pre_direct_raw,
            "value": pre_direct,
            "method": pre_method,
        })

    for item in candidates:
        raw_value = item.get("raw_value") or item.get("key") or item.get("value")
        value = item.get("value")
        reason = _candidate_rejection_reason(raw_value, value, item.get("method"))
        accepted = bool(
            not reason
            and value
            and _looks_resolved_country_name(value)
            and item.get("resolved", True) is not False
        )
        item["accepted"] = accepted
        if reason:
            item["rejection_reason"] = reason

    resolved_item = next(
        (item for item in candidates if item.get("field") == "name" and item.get("accepted")),
        None,
    )
    if resolved_item is None:
        resolved_item = next(
            (item for item in candidates if item.get("field") == "legacy_name" and item.get("accepted")),
            None,
        )

    resolved = resolved_item.get("value") if resolved_item else None
    display = resolved or next(
        (item.get("value") for item in candidates if item.get("accepted")),
        f"Country {country_id}",
    )
    method = resolved_item.get("method") if resolved_item else "unresolved_template"
    identity_hints = {}
    for field in ("adjective", "name_list", "type", "personality"):
        raw_value = _direct_name_scalar(record, field)
        if raw_value:
            identity_hints[field] = raw_value

    return {
        "display": _clean_rendered_name(display),
        "resolved": _clean_rendered_name(resolved),
        "method": method,
        "candidates": candidates[:12],
        "identity_hints": identity_hints,
    }


def _country_name(gamestate: str, country_id: int | None, source_save: Path) -> str | None:
    return _country_name_info(gamestate, country_id, source_save).get("display")


def _saved_targets(record: str | None) -> tuple[dict, ...]:
    if not record:
        return ()
    result: list[dict] = []
    pattern = re.compile(r'(?m)^\s*saved_event_target\s*=\s*\{')
    for match in pattern.finditer(record):
        block = _extract_braced_after(record, match.start())
        if not block:
            continue
        target_id = _inline_int(block, "id")
        if target_id == _INVALID_OBJECT_ID:
            target_id = None
        result.append({
            "name": _inline_scalar(block, "name"),
            "type": _inline_scalar(block, "type"),
            "id": target_id,
        })
    return tuple(result)


def _choice_candidates(record: str | None) -> tuple[tuple[str, str], ...]:
    if not record:
        return ()
    result: list[tuple[str, str]] = []
    pattern = re.compile(
        r'(?mi)^\s*([A-Za-z0-9_.:-]*(?:choice|option|response|selected)[A-Za-z0-9_.:-]*)\s*=\s*(?:"([^"]*)"|([^\s{}]+))'
    )
    for match in pattern.finditer(record):
        key = match.group(1)
        value = match.group(2) or match.group(3) or ""
        pair = (key, value)
        if pair not in result:
            result.append(pair)
        if len(result) >= 12:
            break
    return tuple(result)


def _contact_state(
    gamestate: str,
    contact_id: int,
    source_save: Path,
) -> dict | None:
    record = _contact_record(gamestate, contact_id)
    if not record:
        return None

    owner_id = _int_scalar(record, "owner")
    counterpart_id = _int_scalar(record, "country")
    leader_id = _int_scalar(record, "leader")
    if leader_id == _INVALID_OBJECT_ID:
        leader_id = None

    has_name = bool(re.search(r'(?m)^\s*name\s*=', record))
    pre_contact_name = (
        _record_name(record, source_save, fallback=f"First Contact {contact_id}")
        if has_name
        else None
    )

    event = _find_named_block(record, "event")
    targets = _saved_targets(record)
    contact_target = next(
        (
            item for item in targets
            if item.get("name") == "contact_country" and item.get("type") == "country"
        ),
        None,
    )

    return {
        "contact_id": contact_id,
        "owner_country_id": owner_id,
        "counterpart_country_id": counterpart_id,
        "pre_contact_name": pre_contact_name,
        "location_id": _int_scalar(record, "location"),
        "leader_id": leader_id,
        "record_date": _scalar(record, "date"),
        "last_roll": _scalar(record, "last_roll"),
        "days_left": _scalar(record, "days_left"),
        "difficulty": _scalar(record, "difficulty"),
        "clues": _scalar(record, "clues"),
        "stage": _scalar(record, "stage"),
        "status": _scalar(record, "status"),
        "event_id": _scalar(event, "event_id"),
        "contact_country_target_id": (
            contact_target.get("id") if contact_target is not None else None
        ),
        "saved_targets": list(targets),
        "choice_candidates": [[key, value] for key, value in _choice_candidates(record)],
    }


def _flag_on_country(
    gamestate: str,
    holder_country_id: int | None,
    completed_country_id: int | None,
    *,
    direction: str,
) -> dict:
    if holder_country_id is None or completed_country_id is None:
        return {"present": False, "direction": direction}

    holder = _country_record(gamestate, holder_country_id)
    key = f"first_contact_completed{completed_country_id}"
    if not holder:
        return {
            "present": False,
            "key": key,
            "direction": direction,
            "holder_country_id": holder_country_id,
        }

    block = _any_named_block(holder, key)
    if block is not None:
        exact_date = None
        for date_key in ("date", "completion_date", "completed_date"):
            candidate = _scalar(block, date_key)
            if _valid_date(candidate):
                exact_date = candidate
                break
        return {
            "present": True,
            "key": key,
            "direction": direction,
            "holder_country_id": holder_country_id,
            "flag_date": _scalar(block, "flag_date"),
            "flag_days": _scalar(block, "flag_days"),
            "exact_date": exact_date,
        }

    scalar_match = re.search(
        rf'(?m)^\s*{re.escape(key)}\s*=\s*(?:"([^"]*)"|([^\s{{}}]+))',
        holder,
    )
    if scalar_match:
        return {
            "present": True,
            "key": key,
            "direction": direction,
            "holder_country_id": holder_country_id,
            "value": scalar_match.group(1) or scalar_match.group(2),
            "exact_date": None,
        }

    return {
        "present": False,
        "key": key,
        "direction": direction,
        "holder_country_id": holder_country_id,
    }


def _completion_evidence(
    gamestate: str,
    player_country_id: int | None,
    counterpart_country_id: int | None,
) -> dict:
    """Check both retained directions of Stellaris First Contact completion flags.

    Normal empires can retain the reciprocal marker on the counterpart country
    (``first_contact_completed<player_id>``), while fauna/special contacts may
    expose the player-side marker.  Either is direct retained completion evidence;
    diagnostics keep both sides so no direction is silently assumed.
    """
    direct = _flag_on_country(
        gamestate,
        player_country_id,
        counterpart_country_id,
        direction="player_to_counterpart",
    )
    reciprocal = _flag_on_country(
        gamestate,
        counterpart_country_id,
        player_country_id,
        direction="counterpart_to_player",
    )
    present = bool(direct.get("present") or reciprocal.get("present"))
    if direct.get("present") and reciprocal.get("present"):
        source = "both"
        chosen = direct
    elif reciprocal.get("present"):
        source = "counterpart_to_player"
        chosen = reciprocal
    elif direct.get("present"):
        source = "player_to_counterpart"
        chosen = direct
    else:
        source = "none"
        chosen = direct

    exact_date = direct.get("exact_date") or reciprocal.get("exact_date")
    return {
        "present": present,
        "source": source,
        "key": chosen.get("key"),
        "exact_date": exact_date,
        "player_to_counterpart": direct,
        "counterpart_to_player": reciprocal,
    }


def _assignment_windows(rows: list[dict], leader_snapshots: list) -> list[dict]:
    leader_ids: set[int] = set()
    for snapshot in leader_snapshots:
        leader_ids.update(snapshot.leaders)

    windows: list[dict] = []
    for leader_id in sorted(leader_ids):
        active_contact: int | None = None
        start_index: int | None = None
        leader_name: str | None = None

        for index, snapshot in enumerate(leader_snapshots):
            leader = snapshot.leaders.get(leader_id)
            contact_id = None
            if leader is not None and leader.location_type == "first_contact_system":
                contact_id = leader.location_id

            if contact_id == active_contact:
                continue

            if active_contact is not None and start_index is not None:
                windows.append({
                    "contact_id": int(active_contact),
                    "leader_id": int(leader_id),
                    "leader_name": leader_name or f"Leader {leader_id}",
                    "start_index": start_index,
                    "start_before_index": start_index - 1 if start_index > 0 else None,
                    "last_active_index": index - 1,
                    "end_after_index": index,
                })

            if contact_id is not None:
                active_contact = int(contact_id)
                start_index = index
                leader_name = leader.name if leader is not None else f"Leader {leader_id}"
            else:
                active_contact = None
                start_index = None
                leader_name = None

        if active_contact is not None and start_index is not None:
            windows.append({
                "contact_id": int(active_contact),
                "leader_id": int(leader_id),
                "leader_name": leader_name or f"Leader {leader_id}",
                "start_index": start_index,
                "start_before_index": start_index - 1 if start_index > 0 else None,
                "last_active_index": len(rows) - 1,
                "end_after_index": None,
            })

    windows.sort(key=lambda item: (item["start_index"], item["contact_id"], item["leader_id"]))
    return windows


_FIRST_CONTACT_NON_DIPLOMATIC_TOKENS = (
    "gateway_system",
    "incoming asteroid",
    "mining drone",
    "mineral extraction operation",
    "cracked crystalline shard",
    "space amoeba",
    "spaceborne organics",
    "voidwyrm",
    "leviathan",
    "locust swarm",
    "build_waystation",
    "_poi_name",
    "poi_name",
)


def _publishable_counterpart(
    country_id: int | None,
    name: str | None,
    *,
    resolved_name: str | None = None,
) -> bool:
    if country_id is None or not name:
        return False

    relation = DiplomaticRelationState(country_id=country_id, country_name=name)
    if _publishable_diplomatic_actor(relation):
        return True

    # Generic Politics/Diplomacy deliberately treats very high country IDs as
    # suspicious because many event pseudo-countries live there.  First Contact
    # has stronger direct evidence: the contact record itself names the country.
    # Permit a high-ID counterpart only when its modern templated country name
    # resolves cleanly and does not look like an event/system pseudo actor.
    candidate = _clean_rendered_name(resolved_name or name)
    if not _looks_resolved_country_name(candidate):
        return False
    folded = candidate.casefold()
    if any(token in folded for token in _FIRST_CONTACT_NON_DIPLOMATIC_TOKENS):
        return False
    return True


def _selected_indices(windows: list[dict], total: int) -> list[int]:
    selected: set[int] = set()
    for window in windows:
        for key in ("start_before_index", "start_index", "last_active_index", "end_after_index"):
            value = window.get(key)
            if isinstance(value, int) and 0 <= value < total:
                selected.add(value)

        # Dynamic empire names can settle only after communications complete.
        # Sample several bounded later checkpoints plus the campaign edge so the
        # decoder can follow the same country id without rereading every save.
        end_after = window.get("end_after_index")
        if isinstance(end_after, int):
            for offset in (1, 4, 12, 24):
                index = end_after + offset
                if 0 <= index < total:
                    selected.add(index)

    if total:
        selected.add(total - 1)
    return sorted(selected)


def _decode_case(
    *,
    window: dict,
    rows: list[dict],
    raw: dict[int, str],
    source_save: Path,
    player_country_id: int | None,
    politics_snapshots: list,
    player_country_name: str | None = None,
) -> dict:
    contact_id = int(window["contact_id"])
    candidate_indices = [
        window.get("start_index"),
        window.get("last_active_index"),
        window.get("end_after_index"),
    ]

    states: list[tuple[int, dict]] = []
    for index in candidate_indices:
        if not isinstance(index, int) or index not in raw:
            continue
        state = _contact_state(raw[index], contact_id, source_save)
        if state is not None:
            states.append((index, state))

    record_index, record = states[0] if states else (None, None)
    counterpart_id = record.get("counterpart_country_id") if record else None
    owner_id = record.get("owner_country_id") if record else player_country_id

    # Prefer the completion boundary, then later bounded raw checkpoints.  A
    # dynamic empire can keep a pre-communications/event-style name in the first
    # contact record and reveal its proper diplomatic name only later.
    priority_indices = [
        window.get("end_after_index"),
        window.get("last_active_index"),
        record_index,
        window.get("start_index"),
    ]
    later_start = window.get("end_after_index")
    if not isinstance(later_start, int):
        later_start = int(window.get("last_active_index") or 0)
    later_indices = [index for index in sorted(raw) if index >= later_start]
    name_indices = []
    for index in priority_indices + later_indices:
        if isinstance(index, int) and index not in name_indices:
            name_indices.append(index)

    counterpart_name = None
    counterpart_resolved_name = None
    counterpart_name_resolution: dict = {}
    counterpart_name_source: dict | None = None
    counterpart_country_attempts: list[dict] = []
    counterpart_relation_search: dict = {"selected": None, "candidates": []}
    owner_name = None
    if (
        owner_id is not None
        and player_country_id is not None
        and int(owner_id) == int(player_country_id)
        and player_country_name
    ):
        owner_name = str(player_country_name)
    for index in name_indices:
        if index not in raw:
            continue
        if counterpart_resolved_name is None and counterpart_id is not None:
            info = _country_name_info(raw[index], counterpart_id, source_save)
            attempt = {
                "archive_date": str(rows[index]["game_date"]),
                "snapshot_index": index,
                "display": info.get("display"),
                "resolved": info.get("resolved"),
                "method": info.get("method"),
                "candidates": info.get("candidates") or [],
                "identity_hints": info.get("identity_hints") or {},
            }
            counterpart_country_attempts.append(attempt)
            if not counterpart_name_resolution:
                counterpart_name_resolution = info
                counterpart_name = info.get("display")
            if info.get("resolved"):
                counterpart_name_resolution = info
                counterpart_resolved_name = info.get("resolved")
                counterpart_name = counterpart_resolved_name
                counterpart_name_source = {
                    "source": "country_record",
                    "archive_date": str(rows[index]["game_date"]),
                    "snapshot_index": index,
                    "method": info.get("method"),
                }
        if owner_name is None and owner_id is not None:
            owner_name = _country_name(raw[index], owner_id, source_save)
        if counterpart_resolved_name is not None and owner_name is not None:
            break

    # If raw country identity still uses a technical/pre-communications key,
    # follow the same country id through the cached relations_manager snapshots.
    # This is cache-only and therefore adds no raw-save parse cost.
    if counterpart_resolved_name is None and counterpart_id is not None:
        counterpart_relation_search = _relation_name_search(
            politics_snapshots,
            rows,
            counterpart_id,
            source_save,
            start_index=later_start,
        )
        relation_candidate = counterpart_relation_search.get("selected")
        if relation_candidate is not None:
            value = relation_candidate.get("value")
            if value and _looks_resolved_country_name(value):
                counterpart_resolved_name = value
                counterpart_name = value
                counterpart_name_source = {
                    "source": "relations_manager",
                    "archive_date": relation_candidate.get("archive_date"),
                    "snapshot_index": relation_candidate.get("snapshot_index"),
                    "method": relation_candidate.get("method"),
                    "raw_value": relation_candidate.get("raw_value"),
                }
                counterpart_name_resolution = {
                    "display": value,
                    "resolved": value,
                    "method": "relations_manager_followthrough",
                    "candidates": counterpart_relation_search.get("candidates") or [],
                }
        elif counterpart_relation_search.get("candidates"):
            # Preserve why later diplomatic labels were rejected, while keeping
            # the public counterpart unresolved rather than publishing a script label.
            counterpart_name_resolution = {
                "display": counterpart_name,
                "resolved": None,
                "method": "relation_candidates_rejected",
                "candidates": counterpart_relation_search.get("candidates") or [],
            }

    start_index = int(window["start_index"])
    last_active_index = int(window["last_active_index"])
    end_after_index = window.get("end_after_index")

    before_completion = {"present": False, "source": "none"}
    after_completion = {"present": False, "source": "none"}
    if counterpart_id is not None and last_active_index in raw:
        before_completion = _completion_evidence(
            raw[last_active_index], player_country_id, counterpart_id
        )
    if (
        counterpart_id is not None
        and isinstance(end_after_index, int)
        and end_after_index in raw
    ):
        after_completion = _completion_evidence(
            raw[end_after_index], player_country_id, counterpart_id
        )

    completion_confirmed = bool(
        isinstance(end_after_index, int)
        and not before_completion.get("present")
        and after_completion.get("present")
    )

    target_id = record.get("contact_country_target_id") if record else None
    target_matches_country = bool(
        counterpart_id is not None and target_id is not None and int(target_id) == int(counterpart_id)
    )

    return {
        "contact_id": contact_id,
        "leader_id": int(window["leader_id"]),
        "leader_name": window["leader_name"],
        "owner_country_id": owner_id,
        "owner_country_name": owner_name,
        "counterpart_country_id": counterpart_id,
        "counterpart_country_name": counterpart_name,
        "counterpart_resolved_name": counterpart_resolved_name,
        "counterpart_name_resolution": counterpart_name_resolution,
        "counterpart_name_source": counterpart_name_source,
        "counterpart_country_attempts": counterpart_country_attempts,
        "counterpart_relation_search": counterpart_relation_search,
        "pre_contact_name": record.get("pre_contact_name") if record else None,
        "location_id": record.get("location_id") if record else None,
        "record_date": record.get("record_date") if record else None,
        "stage": record.get("stage") if record else None,
        "status": record.get("status") if record else None,
        "event_id": record.get("event_id") if record else None,
        "contact_country_target_id": target_id,
        "target_matches_country": target_matches_country,
        "choice_candidates": record.get("choice_candidates", []) if record else [],
        "first_active_archive_date": str(rows[start_index]["game_date"]),
        "last_active_archive_date": str(rows[last_active_index]["game_date"]),
        "assignment_start_interval": {
            "before": (
                str(rows[window["start_before_index"]]["game_date"])
                if isinstance(window.get("start_before_index"), int)
                else None
            ),
            "after": str(rows[start_index]["game_date"]),
        },
        "assignment_end_interval": (
            {
                "before": str(rows[last_active_index]["game_date"]),
                "after": str(rows[end_after_index]["game_date"]),
            }
            if isinstance(end_after_index, int)
            else None
        ),
        "completion_flag_before": before_completion,
        "completion_flag_after": after_completion,
        "completion_confirmed": completion_confirmed,
        "completion_exact_date": (
            after_completion.get("exact_date") if completion_confirmed else None
        ),
        "publishable_counterpart": _publishable_counterpart(
            counterpart_id,
            counterpart_name,
            resolved_name=counterpart_resolved_name,
        ),
        "record_found": record is not None,
    }


def _events(cases: list[dict]) -> list[dict]:
    events: list[dict] = []
    seen: set[tuple[str, int]] = set()

    for case in cases:
        contact_id = int(case["contact_id"])
        counterpart = (
            case.get("counterpart_country_name")
            or case.get("pre_contact_name")
            or f"contact {contact_id}"
        )
        publishable = bool(case.get("publishable_counterpart"))

        if case.get("record_found") and ("opened", contact_id) not in seen:
            seen.add(("opened", contact_id))
            record_date = case.get("record_date")
            event_date = (
                record_date if _valid_date(record_date)
                else case["first_active_archive_date"]
            )
            date_kind = (
                "retained_first_contact_record_date"
                if _valid_date(record_date)
                else "first_observed"
            )
            leader = case.get("leader_name") or f"leader {case.get('leader_id')}"
            pre = case.get("pre_contact_name")
            pre_text = (
                f" The pre-contact designation retained in the case was {pre}."
                if pre and pre.casefold() != str(counterpart).casefold()
                else ""
            )
            events.append({
                "event_type": "first_contact_case_recorded",
                "game_date": event_date,
                "date_kind": date_kind,
                "confidence": "high",
                "visible": publishable,
                "contact_id": contact_id,
                "counterpart_country_id": case.get("counterpart_country_id"),
                "counterpart_country_name": case.get("counterpart_country_name"),
                "leader_id": case.get("leader_id"),
                "leader_name": case.get("leader_name"),
                "title": f"First Contact Investigation Recorded: {counterpart}",
                "body": (
                    f"The retained First Contact structure records case {contact_id} involving "
                    f"{counterpart}, with {leader} assigned to the investigation."
                    f"{pre_text} "
                    "Historian reproduces the retained case date when present but does not "
                    "reinterpret it as an unrecorded diplomatic milestone."
                ),
            })

        if case.get("completion_confirmed") and ("completed", contact_id) not in seen:
            seen.add(("completed", contact_id))
            interval = case.get("assignment_end_interval") or {}
            exact_date = case.get("completion_exact_date")
            event_date = exact_date or interval.get("after") or case["last_active_archive_date"]
            date_kind = "exact_save_field" if exact_date else "between_snapshots"
            leader = case.get("leader_name") or f"leader {case.get('leader_id')}"
            completion_evidence = case.get("completion_flag_after") or {}
            completion_key = completion_evidence.get("key")
            completion_source = completion_evidence.get("source")
            if completion_source == "counterpart_to_player":
                marker_text = "the reciprocal counterpart-country completion marker"
            elif completion_source == "both":
                marker_text = "completion markers on both retained country records"
            else:
                marker_text = "the player-country completion marker"
            if exact_date:
                timing = f"The retained completion field records the date as {exact_date}."
            else:
                timing = (
                    f"The archive establishes completion between {interval.get('before')} and "
                    f"{interval.get('after')}; the exact day is not established."
                )
            events.append({
                "event_type": "first_contact_completed",
                "game_date": event_date,
                "date_kind": date_kind,
                "confidence": "high",
                "visible": publishable,
                "contact_id": contact_id,
                "counterpart_country_id": case.get("counterpart_country_id"),
                "counterpart_country_name": case.get("counterpart_country_name"),
                "leader_id": case.get("leader_id"),
                "leader_name": case.get("leader_name"),
                "title": f"First Contact Completed: {counterpart}",
                "body": (
                    f"{leader}'s First Contact assignment for case {contact_id} ended and "
                    f"{marker_text} `{completion_key or 'first_contact_completed'}` first appeared "
                    f"across the same archived interval. {timing} "
                    "No response choice is published unless a retained choice field is decoded directly."
                ),
            })

    events.sort(key=lambda item: (str(item.get("game_date") or ""), str(item.get("event_type") or ""), int(item.get("contact_id") or 0)))
    return events


def history_json_path(db: Database, campaign_id: int) -> Path:
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist.")
    diagnostics = Path(campaign["archive_dir"]) / "diagnostics"
    return diagnostics / _HISTORY_JSON


def load_first_contact_history(db: Database, campaign_id: int) -> dict:
    path = history_json_path(db, campaign_id)
    if not path.exists():
        return {"cases": [], "events": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"cases": [], "events": []}
    return data if isinstance(data, dict) else {"cases": [], "events": []}


def write_first_contact_history(
    db: Database,
    campaign_id: int,
    *,
    progress: ProgressCallback | None = None,
) -> Path:
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist.")

    rows = [dict(row) for row in db.all_snapshots(campaign_id)]
    source_save = Path(campaign["source_save"])
    cache_dir = campaign_cache_dir(Path(campaign["archive_dir"]))

    profiles = []
    leader_snapshots = []
    politics_snapshots = []
    cache_counts = {"hit": 0, "extend": 0, "miss": 0}
    for row in rows:
        (
            profile,
            _ship_snapshot,
            leader_snapshot,
            _world_snapshot,
            _science_snapshot,
            _combat_snapshot,
            _technology_snapshot,
            politics_snapshot,
            cache_status,
        ) = load_or_parse_snapshot(
            archive_path=Path(row["archive_path"]),
            source_save=source_save,
            source_sha256=row["sha256"],
            snapshot_id=int(row["id"]),
            cache_dir=cache_dir,
        )
        profiles.append(profile)
        leader_snapshots.append(leader_snapshot)
        politics_snapshots.append(politics_snapshot)
        cache_counts[cache_status] = cache_counts.get(cache_status, 0) + 1

    windows = _assignment_windows(rows, leader_snapshots)
    selected = _selected_indices(windows, len(rows))

    raw: dict[int, str] = {}
    failures: list[str] = []
    for position, index in enumerate(selected, start=1):
        row = rows[index]
        if progress is not None:
            progress(position, len(selected), row)
        try:
            _meta, gamestate = read_save_texts(Path(row["archive_path"]))
            raw[index] = gamestate
        except Exception as exc:
            failures.append(f"{row['game_date']} | {row['archive_filename']} | {exc}")

    player_country_id = None
    for profile in profiles:
        if profile.player_country_id is not None:
            player_country_id = int(profile.player_country_id)
            break

    cases = [
        _decode_case(
            window=window,
            rows=rows,
            raw=raw,
            source_save=source_save,
            player_country_id=player_country_id,
            politics_snapshots=politics_snapshots,
            player_country_name=str(campaign["empire_name"]),
        )
        for window in windows
    ]
    events = _events(cases)

    diagnostics = Path(campaign["archive_dir"]) / "diagnostics"
    diagnostics.mkdir(parents=True, exist_ok=True)
    json_path = diagnostics / _HISTORY_JSON
    debug_path = diagnostics / _HISTORY_DEBUG

    payload = {
        "version": "0.0.50.4",
        "campaign": str(campaign["empire_name"]),
        "archived_snapshots": len(rows),
        "player_country_id": player_country_id,
        "assignment_windows": len(windows),
        "raw_snapshots_read": len(raw),
        "cache": cache_counts,
        "cases": cases,
        "events": events,
        "raw_read_failures": failures,
        "rules": {
            "counterpart": "Published only when the retained contact record supplies a country id whose identity resolves cleanly from a top-level country name or later relations_manager evidence; nested technical/pre-communications name fields are never promoted as the country name.",
            "completion": "Published only when either the player-side first_contact_completed<counterpart_id> marker or the reciprocal counterpart-side first_contact_completed<player_id> marker first appears across the same archived interval in which the First Contact assignment ends, or a future direct completion date is decoded.",
            "response_choice": "Never published from keyword candidates alone; a direct retained selection field must be proven first.",
        },
    }

    fd, temp_name = tempfile.mkstemp(prefix="first_contact_history_", suffix=".json", dir=str(diagnostics))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_name, json_path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)

    lines = [
        "STELLARIS HISTORIAN - STRUCTURED FIRST CONTACT HISTORY",
        "",
        "v0.0.50.4 structured First Contact adjective-inflection and diagnostic-polish hotfix.",
        "This decoder extracts individual first_contacts.contacts records by the contact id retained on leader location.type=first_contact_system assignments.",
        "Counterpart identity now also applies installed Stellaris adj_NN* adjective suffix grammar inside nested %ADJ% / %ADJECTIVE% names, rejects technical relation/localisation labels before publication, and retains rejected candidates diagnostically; two-sided completion checks remain unchanged.",
        "",
        f"Campaign: {campaign['empire_name']}",
        f"Archived snapshots: {len(rows)}",
        f"Assignment windows: {len(windows)}",
        f"Structured cases: {len(cases)}",
        f"Published events: {sum(bool(event.get('visible')) for event in events)}",
        f"Raw snapshots read: {len(raw)}",
        f"Cache: {cache_counts.get('hit', 0)} hit / {cache_counts.get('extend', 0)} extend / {cache_counts.get('miss', 0)} miss",
        "",
        "CASES",
        "=====",
    ]

    if not cases:
        lines.append("No First Contact assignment windows were found.")
    else:
        for case in cases:
            lines.extend([
                f"Contact {case['contact_id']} | {case.get('counterpart_country_name') or case.get('pre_contact_name') or 'unresolved counterpart'}",
                f"  Leader: {case.get('leader_name')} (leader {case.get('leader_id')})",
                f"  Owner: {case.get('owner_country_name') or case.get('owner_country_id')} (country {case.get('owner_country_id')})",
                f"  Counterpart: {case.get('counterpart_country_name') or 'unresolved'} (country {case.get('counterpart_country_id')})",
                f"  Resolved country name: {case.get('counterpart_resolved_name') or 'not resolved'}",
                f"  Name resolution: {case.get('counterpart_name_resolution') or 'None'}",
                f"  Name source: {case.get('counterpart_name_source') or 'not resolved'}",
                f"  Country-name attempts: {case.get('counterpart_country_attempts') or 'None'}",
                f"  Relation-name search: {case.get('counterpart_relation_search') or 'None'}",
                f"  Pre-contact designation: {case.get('pre_contact_name') or 'not retained'}",
                f"  Retained record date: {case.get('record_date') or 'not retained'}",
                f"  Location id: {case.get('location_id')}",
                f"  Stage / status: {case.get('stage') or 'not retained'} / {case.get('status') or 'not retained'}",
                f"  Event id: {case.get('event_id') or 'not retained'}",
                f"  contact_country saved target: {case.get('contact_country_target_id')} (matches record.country: {case.get('target_matches_country')})",
                f"  Assignment first active archive: {case.get('first_active_archive_date')}",
                f"  Assignment last active archive: {case.get('last_active_archive_date')}",
                f"  Assignment start interval: {case.get('assignment_start_interval')}",
                f"  Assignment end interval: {case.get('assignment_end_interval')}",
                f"  Completion confirmed: {case.get('completion_confirmed')}",
                f"  Completion marker before: {case.get('completion_flag_before')}",
                f"  Completion marker after: {case.get('completion_flag_after')}",
                f"  Publishable counterpart: {case.get('publishable_counterpart')}",
                f"  Choice-like retained fields: {case.get('choice_candidates') or 'None'}",
                "",
            ])

    lines.extend(["PUBLISHED EVENTS", "================"])
    published = [event for event in events if event.get("visible")]
    if not published:
        lines.append("None")
    else:
        for event in published:
            lines.extend([
                f"{event.get('game_date')} | {event.get('event_type')} | {event.get('title')}",
                f"  Date kind: {event.get('date_kind')}",
                f"  Confidence: {event.get('confidence')}",
                f"  Body: {event.get('body')}",
                "",
            ])

    lines.extend(["RAW READ FAILURES", "================="])
    if failures:
        lines.extend("- " + value for value in failures)
    else:
        lines.append("None")

    lines.extend([
        "",
        "INTERPRETATION RULES",
        "====================",
        "1. The contact id is taken directly from a leader's first_contact_system location id and matched to first_contacts.contacts.<id>.",
        "2. Counterpart country identity is taken from the contact record's country field. Generated %ADJ% / %ADJECTIVE% name grammar is rendered recursively with installed adj_NN* adjective suffix rules; technical script/localisation identifiers are rejected before publication, and later country/relation candidates are retained for audit.",
        "3. A completion event is promoted when either direction of the counterpart-specific completion relationship first appears across the assignment-end interval: player first_contact_completed<counterpart_id> or reciprocal counterpart first_contact_completed<player_id>.",
        "4. The contact record's date field is retained literally and is not silently reinterpreted as a diplomatic milestone beyond what the record proves.",
        "5. Choice-like fields are diagnostic only until a specific retained response-selection field is proven.",
    ])

    debug_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return debug_path
