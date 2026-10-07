from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import re
import zipfile


@dataclass
class LocalisationIndex:
    values: dict[str, str] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)
    steam_root: str | None = None
    steam_libraries: list[str] = field(default_factory=list)
    paradox_roots: list[str] = field(default_factory=list)
    scanned_loose_files: int = 0
    scanned_zip_archives: int = 0
    scanned_zip_members: int = 0
    notes: list[str] = field(default_factory=list)


_LOCALISATION_CACHE: dict[str, LocalisationIndex] = {}


def clear_localisation_cache() -> None:
    _LOCALISATION_CACHE.clear()


def _find_steam_root(source_save: Path) -> Path | None:
    current = source_save.resolve()

    for parent in (current, *current.parents):
        if parent.name.lower() == "steam":
            return parent

    return None


def _steam_library_roots(steam_root: Path) -> list[Path]:
    roots: list[Path] = [steam_root]

    vdf = steam_root / "config" / "libraryfolders.vdf"

    if not vdf.exists():
        return roots

    try:
        text = vdf.read_text(
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return roots

    for raw_path in re.findall(
        r'"path"\s*"([^"]+)"',
        text,
    ):
        library = Path(
            raw_path.replace("\\\\", "\\")
        )

        if library not in roots:
            roots.append(library)

    return roots


def _paradox_stellaris_roots() -> list[Path]:
    candidates: list[Path] = []

    home = Path.home()

    candidates.append(
        home / "Documents" / "Paradox Interactive" / "Stellaris"
    )
    candidates.append(
        home / "OneDrive" / "Documents" / "Paradox Interactive" / "Stellaris"
    )

    for env_name in (
        "USERPROFILE",
        "OneDrive",
        "OneDriveConsumer",
        "OneDriveCommercial",
    ):
        raw = os.environ.get(env_name)

        if not raw:
            continue

        candidates.append(
            Path(raw)
            / "Documents"
            / "Paradox Interactive"
            / "Stellaris"
        )

    unique: list[Path] = []
    seen: set[str] = set()

    for path in candidates:
        key = str(path).lower()

        if key not in seen:
            seen.add(key)
            unique.append(path)

    return unique


def _decode_localisation_value(value: str) -> str:
    value = value.replace(r'\"', '"')
    value = value.replace(r"\n", "\n")
    value = value.replace(r"\t", " ")
    return value.strip()


_LOCALISATION_LINE = re.compile(
    r'(?m)^\s*([^\s:#]+):(?:\d+)?\s+"((?:[^"\\]|\\.)*)"\s*$'
)


def _read_yml_text(
    text: str,
    index: LocalisationIndex,
    source_label: str,
) -> None:
    for match in _LOCALISATION_LINE.finditer(text):
        key = match.group(1)
        value = _decode_localisation_value(
            match.group(2)
        )

        index.values[key] = value
        index.sources[key] = source_label


def _read_yml_file(
    path: Path,
    index: LocalisationIndex,
) -> None:
    try:
        text = path.read_text(
            encoding="utf-8-sig",
            errors="replace",
        )
    except OSError as exc:
        index.notes.append(
            f"Could not read loose localisation file: {path} ({exc})"
        )
        return

    index.scanned_loose_files += 1

    _read_yml_text(
        text,
        index,
        str(path),
    )


def _is_english_localisation_member(name: str) -> bool:
    normal = name.replace("\\", "/").lower()

    return (
        normal.endswith(".yml")
        and (
            "/localisation/english/" in f"/{normal}"
            or "/localization/english/" in f"/{normal}"
        )
    )


def _read_localisation_zip(
    path: Path,
    index: LocalisationIndex,
) -> None:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            index.scanned_zip_archives += 1

            for name in archive.namelist():
                if not _is_english_localisation_member(name):
                    continue

                try:
                    raw = archive.read(name)
                except (KeyError, OSError):
                    continue

                index.scanned_zip_members += 1

                text = raw.decode(
                    "utf-8-sig",
                    errors="replace",
                )

                _read_yml_text(
                    text,
                    index,
                    f"{path}::{name}",
                )

    except (OSError, zipfile.BadZipFile) as exc:
        index.notes.append(
            f"Could not scan localisation ZIP: {path} ({exc})"
        )


def _scan_loose_localisation(
    root: Path,
    index: LocalisationIndex,
) -> None:
    if not root.exists():
        return

    patterns = (
        "localisation/english/**/*.yml",
        "localization/english/**/*.yml",
    )

    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            _read_yml_file(
                path,
                index,
            )


def _scan_zip_tree(
    root: Path,
    index: LocalisationIndex,
) -> None:
    if not root.exists():
        return

    for path in sorted(
        root.glob("**/*.zip")
    ):
        _read_localisation_zip(
            path,
            index,
        )


def _descriptor_targets(
    stellaris_root: Path,
) -> list[Path]:
    mod_root = stellaris_root / "mod"

    if not mod_root.exists():
        return []

    targets: list[Path] = []

    for descriptor in sorted(
        mod_root.glob("*.mod")
    ):
        try:
            text = descriptor.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            continue

        for _, raw in re.findall(
            r'(?m)^\s*(path|archive)\s*=\s*"([^"]+)"',
            text,
        ):
            raw = raw.replace("\\\\", "\\")

            candidate = Path(raw)

            if not candidate.is_absolute():
                candidate = stellaris_root / candidate

            targets.append(candidate)

    return targets


def _cache_key(source_save: Path) -> str:
    steam_root = _find_steam_root(source_save)

    if steam_root is not None:
        return f"steam::{str(steam_root.resolve()).lower()}"

    return f"source::{str(source_save.resolve()).lower()}"


def _load_index_data(
    source_save: Path,
) -> LocalisationIndex:
    cache_key = _cache_key(source_save)

    if cache_key in _LOCALISATION_CACHE:
        return _LOCALISATION_CACHE[cache_key]

    index = LocalisationIndex()

    steam_root = _find_steam_root(
        source_save
    )

    if steam_root is None:
        index.notes.append(
            "Steam root could not be derived from the supplied source-save path."
        )
    else:
        index.steam_root = str(
            steam_root
        )

        libraries = _steam_library_roots(
            steam_root
        )

        index.steam_libraries = [
            str(path)
            for path in libraries
        ]

        for library_root in libraries:
            game_root = (
                library_root
                / "steamapps"
                / "common"
                / "Stellaris"
            )

            if game_root.exists():
                _scan_loose_localisation(
                    game_root,
                    index,
                )

                _scan_zip_tree(
                    game_root / "dlc",
                    index,
                )

            workshop_root = (
                library_root
                / "steamapps"
                / "workshop"
                / "content"
                / "281990"
            )

            if workshop_root.exists():
                for item in sorted(
                    workshop_root.iterdir()
                ):
                    if not item.is_dir():
                        continue

                    _scan_loose_localisation(
                        item,
                        index,
                    )

                    _scan_zip_tree(
                        item,
                        index,
                    )

    paradox_roots = _paradox_stellaris_roots()

    index.paradox_roots = [
        str(path)
        for path in paradox_roots
    ]

    for stellaris_root in paradox_roots:
        if not stellaris_root.exists():
            continue

        mod_root = stellaris_root / "mod"

        if mod_root.exists():
            for child in sorted(
                mod_root.iterdir()
            ):
                if child.is_dir():
                    _scan_loose_localisation(
                        child,
                        index,
                    )

                    _scan_zip_tree(
                        child,
                        index,
                    )

                elif (
                    child.is_file()
                    and child.suffix.lower() == ".zip"
                ):
                    _read_localisation_zip(
                        child,
                        index,
                    )

        for target in _descriptor_targets(
            stellaris_root
        ):
            if target.is_dir():
                _scan_loose_localisation(
                    target,
                    index,
                )

                _scan_zip_tree(
                    target,
                    index,
                )

            elif (
                target.is_file()
                and target.suffix.lower() == ".zip"
            ):
                _read_localisation_zip(
                    target,
                    index,
                )

    _LOCALISATION_CACHE[
        cache_key
    ] = index

    return index


def _load_index(
    source_save: Path,
) -> dict[str, str]:
    return _load_index_data(
        source_save
    ).values


def _resolve_references(
    text: str,
    values: dict[str, str],
    max_passes: int = 4,
) -> str:
    result = text

    for _ in range(max_passes):
        changed = False

        def replace(
            match: re.Match,
        ) -> str:
            nonlocal changed

            key = match.group(1)

            if key in values:
                changed = True
                return values[key]

            return match.group(0)

        result = re.sub(
            r"\$([A-Za-z0-9_.-]+)\$",
            replace,
            result,
        )

        if not changed:
            break

    return result


def _clean_markup(text: str) -> str:
    text = re.sub(
        r"§.",
        "",
        text,
    )

    text = re.sub(
        r"£[^£\s]+£",
        "",
        text,
    )

    lines: list[str] = []

    for raw_line in text.splitlines():
        line = re.sub(
            r"[ \t]+",
            " ",
            raw_line,
        ).strip()

        lines.append(line)

    cleaned: list[str] = []

    for line in lines:
        if (
            not line
            and cleaned
            and not cleaned[-1]
        ):
            continue

        cleaned.append(line)

    return "\n".join(
        cleaned
    ).strip()


def _significant_origin_tokens(
    origin_key: str,
) -> list[str]:
    tokens = re.split(
        r"[^a-z0-9]+",
        origin_key.lower(),
    )

    ignored = {
        "",
        "origin",
        "origins",
        "desc",
        "description",
        "text",
        "name",
    }

    return [
        token
        for token in tokens
        if token not in ignored
    ]


def _description_candidates(
    values: dict[str, str],
    origin_key: str,
) -> list[str]:
    direct = [
        f"{origin_key}_desc",
        f"{origin_key}_description",
        f"{origin_key}_text",
        f"{origin_key}.desc",
    ]

    results: list[str] = []

    for key in direct:
        if key in values and key not in results:
            results.append(key)

    tokens = _significant_origin_tokens(
        origin_key
    )

    scored: list[tuple[int, str]] = []

    for key in values:
        lowered = key.lower()

        if not (
            "desc" in lowered
            or "description" in lowered
            or lowered.endswith("_text")
        ):
            continue

        score = 0

        if lowered.startswith(
            origin_key.lower()
        ):
            score += 100

        if "origin" in lowered:
            score += 20

        matched_tokens = sum(
            1
            for token in tokens
            if token in lowered
        )

        score += matched_tokens * 20

        if (
            tokens
            and matched_tokens == len(tokens)
        ):
            score += 60

        if score > 0:
            scored.append(
                (score, key)
            )

    scored.sort(
        key=lambda item: (
            -item[0],
            len(item[1]),
            item[1].lower(),
        )
    )

    for _, key in scored:
        if key not in results:
            results.append(key)

    return results


def _title_candidates(
    values: dict[str, str],
    origin_key: str,
) -> list[str]:
    direct = [
        origin_key,
        f"{origin_key}_name",
        f"{origin_key}_title",
    ]

    results: list[str] = []

    for key in direct:
        if key in values and key not in results:
            results.append(key)

    return results


def resolve_origin_lore(
    source_save: Path,
    origin_key: str | None,
) -> dict | None:
    if not origin_key:
        return None

    index = _load_index_data(
        source_save
    )

    values = index.values

    if not values:
        return None

    title = None
    title_key = None

    for key in _title_candidates(
        values,
        origin_key,
    ):
        title = values.get(key)

        if title:
            title_key = key
            break

    description = None
    description_key = None

    for key in _description_candidates(
        values,
        origin_key,
    ):
        candidate = values.get(key)

        if not candidate:
            continue

        cleaned = _clean_markup(
            _resolve_references(
                candidate,
                values,
            )
        )

        if len(cleaned) < 40:
            continue

        description = cleaned
        description_key = key
        break

    if not description:
        return None

    if title:
        title = _clean_markup(
            _resolve_references(
                title,
                values,
            )
        )

    return {
        "origin_key": origin_key,
        "title_key": title_key,
        "title": title or origin_key,
        "description_key": description_key,
        "description": description,
        "description_source": index.sources.get(
            description_key
        ),
    }


def _preview(value: str | None, limit: int = 220) -> str:
    if not value:
        return ""

    cleaned = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    if len(cleaned) <= limit:
        return cleaned

    return cleaned[: limit - 3] + "..."


def _related_origin_keys(
    values: dict[str, str],
    origin_key: str,
    limit: int = 40,
) -> list[str]:
    tokens = _significant_origin_tokens(
        origin_key
    )

    scored: list[tuple[int, str]] = []

    for key in values:
        lowered = key.lower()

        matched_tokens = sum(
            1
            for token in tokens
            if token in lowered
        )

        if matched_tokens == 0:
            continue

        score = matched_tokens * 20

        if "origin" in lowered:
            score += 10

        if (
            "desc" in lowered
            or "description" in lowered
            or "story" in lowered
            or "text" in lowered
        ):
            score += 20

        if lowered.startswith(
            origin_key.lower()
        ):
            score += 80

        scored.append(
            (score, key)
        )

    scored.sort(
        key=lambda item: (
            -item[0],
            len(item[1]),
            item[1].lower(),
        )
    )

    return [
        key
        for _, key in scored[:limit]
    ]


def write_origin_localisation_debug(
    source_save: Path,
    origin_key: str | None,
    output_path: Path,
) -> Path:
    """
    Write a human-readable diagnostic file for origin localisation discovery.
    This is intended for debugging mod/DLC localisation and contains no save
    modifications.
    """
    clear_localisation_cache()

    index = _load_index_data(
        source_save
    )

    values = index.values

    lines: list[str] = []

    lines.append("STELLARIS HISTORIAN - ORIGIN LOCALISATION DEBUG")
    lines.append("=" * 47)
    lines.append("")
    lines.append(f"Source save used for localisation discovery: {source_save}")
    lines.append(f"Source save exists: {source_save.exists()}")
    lines.append(f"Raw origin key: {origin_key or '<none>'}")
    lines.append(f"Steam root found: {index.steam_root or '<not found>'}")
    lines.append(f"Localisation keys loaded: {len(values)}")
    lines.append(f"Loose localisation files scanned: {index.scanned_loose_files}")
    lines.append(f"ZIP archives scanned: {index.scanned_zip_archives}")
    lines.append(f"English localisation members read from ZIPs: {index.scanned_zip_members}")
    lines.append("")

    lines.append("STEAM LIBRARIES")
    lines.append("---------------")

    if index.steam_libraries:
        lines.extend(
            f"- {path}"
            for path in index.steam_libraries
        )
    else:
        lines.append("- None discovered")

    lines.append("")
    lines.append("PARADOX STELLARIS ROOTS CHECKED")
    lines.append("-------------------------------")

    if index.paradox_roots:
        lines.extend(
            f"- {path}"
            for path in index.paradox_roots
        )
    else:
        lines.append("- None")

    lines.append("")

    if not origin_key:
        lines.append("No origin key was available, so no candidate search was performed.")
    else:
        lines.append("EXACT / STANDARD KEYS")
        lines.append("---------------------")

        standard_keys = [
            origin_key,
            f"{origin_key}_name",
            f"{origin_key}_title",
            f"{origin_key}_desc",
            f"{origin_key}_description",
            f"{origin_key}_text",
            f"{origin_key}.desc",
        ]

        for key in standard_keys:
            if key in values:
                lines.append(f"[FOUND] {key}")
                lines.append(f"  Source: {index.sources.get(key, '<unknown>')}")
                lines.append(f"  Value: {_preview(values.get(key))}")
            else:
                lines.append(f"[MISSING] {key}")

        lines.append("")
        lines.append("DESCRIPTION CANDIDATES")
        lines.append("----------------------")

        candidates = _description_candidates(
            values,
            origin_key,
        )

        if candidates:
            for number, key in enumerate(
                candidates[:30],
                start=1,
            ):
                lines.append(f"{number}. {key}")
                lines.append(f"   Source: {index.sources.get(key, '<unknown>')}")
                lines.append(f"   Value: {_preview(values.get(key))}")
        else:
            lines.append("No description candidates found.")

        lines.append("")
        lines.append("RELATED ORIGIN KEYS")
        lines.append("-------------------")

        related = _related_origin_keys(
            values,
            origin_key,
        )

        if related:
            for number, key in enumerate(
                related,
                start=1,
            ):
                lines.append(f"{number}. {key}")
                lines.append(f"   Source: {index.sources.get(key, '<unknown>')}")
                lines.append(f"   Value: {_preview(values.get(key))}")
        else:
            lines.append("No related localisation keys found.")

        lines.append("")
        lines.append("CURRENT RESOLUTION RESULT")
        lines.append("-------------------------")

        result = resolve_origin_lore(
            source_save,
            origin_key,
        )

        if result:
            lines.append("Resolved: YES")
            lines.append(f"Title key: {result.get('title_key')}")
            lines.append(f"Title: {result.get('title')}")
            lines.append(f"Description key: {result.get('description_key')}")
            lines.append(f"Description source: {result.get('description_source')}")
            lines.append(f"Description preview: {_preview(result.get('description'), 500)}")
        else:
            lines.append("Resolved: NO")

    if index.notes:
        lines.append("")
        lines.append("SCAN NOTES")
        lines.append("----------")
        lines.extend(
            f"- {note}"
            for note in index.notes
        )

    lines.append("")
    lines.append("IMPORTANT")
    lines.append("---------")
    lines.append(
        "Historian does not invent origin lore. This report is intended to show "
        "exactly what localisation data was visible to the app."
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    return output_path


def resolve_localisation_key(
    source_save: Path,
    key: str | None,
) -> str | None:
    """
    Resolve one exact Stellaris localisation key from the user's locally
    installed vanilla/DLC/mod localisation. Returns None when unavailable.
    """
    if not key:
        return None

    index = _load_index_data(
        source_save
    )

    value = index.values.get(
        key
    )

    if not value:
        return None

    resolved = _resolve_references(
        value,
        index.values,
    )

    resolved = _clean_markup(
        resolved
    )

    return resolved or None
