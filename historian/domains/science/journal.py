from __future__ import annotations

from html import escape
from pathlib import Path
import json
import re

from ...db import Database
from ...localisation import resolve_localisation_key
from . import CACHE_COMPONENT_NAME, CACHE_COMPONENT_VERSION
from .cache import snapshot_from_dict
from .history import (
    ArchaeologyInterpretation,
    ProjectFamilyInterpretation,
    ScienceInterpretation,
    SituationInterpretation,
    derive_science_interpretation,
)
from .models import ScienceSnapshot


_RED_GIANT_PROJECT_KEYS = {
    "INF_ORIGIN_RED_GIANT_TRIANGULATION",
    "INF_ORIGIN_RED_GIANT_PROTECT_HOMEWORLD",
    "INF_ORIGIN_RED_GIANT_PARLAY",
    "INF_ORIGIN_RED_GIANT_BOARD_STATION",
}
_RED_GIANT_SITUATION_KEY = "situation_red_giant_expansion"
_ECONOMIC_OR_POLITICAL_SITUATION_KEYS = {
    "situation_alloys_deficit",
    "situation_food_deficit",
    "situation_planetary_revolt",
}


def _e(value) -> str:
    return escape("" if value is None else str(value))


def _humanise_key(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    for prefix in (
        "approach_",
        "situation_",
        "special_project_",
        "project_",
    ):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    cleaned = re.sub(r"\d+$", "", cleaned)
    cleaned = cleaned.replace("_", " ").strip()
    return cleaned.title() if cleaned else value


def _localised_label(source_save: Path, key: str | None) -> str | None:
    if not key:
        return None
    return resolve_localisation_key(source_save, key) or _humanise_key(key)


def _safe_description(source_save: Path, *keys: str | None) -> str | None:
    for key in keys:
        if not key:
            continue
        value = resolve_localisation_key(source_save, key)
        if not value:
            continue
        # Dynamic scripted tokens are useful in-game but confusing in a static
        # historical journal when Historian cannot resolve their scope safely.
        if "[" in value or "]" in value:
            continue
        return value
    return None


def _cache_science_snapshots(db: Database, campaign_id: int) -> list[ScienceSnapshot]:
    campaign = db.campaign(campaign_id)
    if campaign is None:
        return []

    cache_dir = Path(campaign["archive_dir"]) / ".historian_cache"
    result: list[ScienceSnapshot] = []

    for row in db.all_snapshots(campaign_id):
        path = cache_dir / f"{row['sha256']}.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        component = payload.get("components", {}).get(CACHE_COMPONENT_NAME, {})
        if component.get("version") != CACHE_COMPONENT_VERSION:
            continue
        data = component.get("data")
        if not isinstance(data, dict):
            continue
        try:
            result.append(snapshot_from_dict(data, snapshot_id=int(row["id"])))
        except (KeyError, TypeError, ValueError):
            continue

    return result


def _status_sentence(*, present: bool, last: str, absent_after: str | None) -> str:
    if present:
        return "It remains present in the latest archived state."
    if absent_after:
        return (
            f"It is no longer observed by {absent_after}, after last being present "
            f"on {last}; the archive does not establish whether it succeeded, failed, "
            "expired or was cancelled."
        )
    return "It is no longer observed in the surviving archive; its outcome is not established."


def _window(first: str, last: str) -> str:
    return first if first == last else f"{first} to {last}"


def _red_giant_arc(
    interpretation: ScienceInterpretation,
    source_save: Path,
) -> str:
    projects = [
        row for row in interpretation.project_families
        if row.project_key in _RED_GIANT_PROJECT_KEYS
    ]
    situations = [
        row for row in interpretation.situations
        if row.type_key == _RED_GIANT_SITUATION_KEY
    ]
    if not (projects or situations):
        return ""

    first_dates = [row.first_observed for row in projects] + [row.first_observed for row in situations]
    last_dates = [row.last_observed for row in projects] + [row.last_observed for row in situations]
    first = min(first_dates)
    last = max(last_dates)

    paragraphs: list[str] = [
        f"The surviving archive records the Red Giant story arc from {first} through {last}."
    ]

    situation = situations[0] if situations else None
    if situation:
        description = _safe_description(
            source_save,
            f"{situation.type_key}_desc",
            f"{situation.type_key}_DESC",
        )
        if description:
            paragraphs.append(description)
        if situation.latest_approach_key:
            approach = _localised_label(source_save, situation.latest_approach_key)
            if approach:
                paragraphs.append(
                    f"The latest preserved approach for {situation.title} is recorded as {approach}."
                )

    for row in sorted(projects, key=lambda item: (item.first_observed, item.title)):
        if row.peak_concurrent_instances > 1:
            detail = (
                f"{row.title} appears as {row.peak_concurrent_instances} simultaneous "
                f"objectives between {row.first_observed} and {row.last_observed}."
            )
        else:
            detail = (
                f"{row.title} is observed from {row.first_observed} through {row.last_observed}."
            )
        paragraphs.append(detail)

    paragraphs.append(
        "Historian groups these records because they share the Red Giant event chain; "
        "it does not infer a final outcome where the save does not preserve one."
    )

    return f"""
      <article class="chronicle-event science-event story-arc">
        <div class="date">{_e(_window(first, last))}</div>
        <h3>The Red Giant Story Arc</h3>
        {''.join(f'<p>{_e(paragraph)}</p>' for paragraph in paragraphs)}
        <div class="evidence evidence-stack">
          <span><strong>Basis:</strong> linked situation and special-project evidence</span>
        </div>
      </article>
    """


def _archaeology_article(site: ArchaeologyInterpretation) -> str:
    location = ", ".join(site.location_names) if site.location_names else "an unresolved location"
    scientists = ", ".join(site.scientist_names)
    body = [
        f"The archive first records {site.title} at {location} on {site.first_observed}."
    ]
    if scientists:
        body.append(f"Save evidence links the investigation to scientist {scientists}.")
    if site.highest_chapter_index is not None:
        body.append(
            f"The site reached at least recorded chapter index {site.highest_chapter_index}."
        )
    if site.progress_marker_dates:
        body.append(
            f"Stellaris retains {len(site.progress_marker_dates)} dated archaeology progress marker(s), "
            "which Historian treats as chapter/progress evidence rather than proof that the entire site completed."
        )
    body.append(
        _status_sentence(
            present=site.record_persists_in_latest,
            last=site.last_observed,
            absent_after=site.first_absent_after_last,
        )
    )

    return f"""
      <article class="chronicle-event science-event archaeology-event">
        <div class="date">{_e(site.first_observed)}</div>
        <h3>{_e(site.title)}</h3>
        {''.join(f'<p>{_e(paragraph)}</p>' for paragraph in body)}
        <div class="evidence evidence-stack">
          <span><strong>Window:</strong> {_e(_window(site.first_observed, site.last_observed))}</span>
          <span><strong>Location:</strong> {_e(location)}</span>
        </div>
      </article>
    """


def _project_article(row: ProjectFamilyInterpretation) -> str:
    body = [
        f"{row.title} first appears as an active special project on {row.first_observed}."
    ]
    if row.scientist_names:
        body.append(
            f"The archived project evidence links it to scientist {', '.join(row.scientist_names)}."
        )
    if row.ship_names:
        body.append(
            f"The linked science vessel is recorded as {', '.join(row.ship_names)}."
        )
    if row.location_names:
        body.append(f"Recorded location: {', '.join(row.location_names)}.")
    if row.peak_concurrent_instances > 1:
        body.append(
            f"At its peak the save contains {row.peak_concurrent_instances} simultaneous objectives in this project family."
        )
    body.append(
        _status_sentence(
            present=row.present_in_latest,
            last=row.last_observed,
            absent_after=row.first_absent_after_last,
        )
    )

    return f"""
      <article class="chronicle-event science-event project-event">
        <div class="date">{_e(row.first_observed)}</div>
        <h3>{_e(row.title)}</h3>
        {''.join(f'<p>{_e(paragraph)}</p>' for paragraph in body)}
        <div class="evidence evidence-stack">
          <span><strong>Observed:</strong> {_e(_window(row.first_observed, row.last_observed))}</span>
        </div>
      </article>
    """


def _situation_article(row: SituationInterpretation, source_save: Path) -> str:
    body = [
        f"The situation {row.title} is first observed on {row.first_observed}."
    ]
    if row.latest_approach_key:
        approach = _localised_label(source_save, row.latest_approach_key)
        if approach:
            body.append(f"The latest preserved approach is {approach}.")
    if row.latest_progress is not None:
        body.append(f"The last archived progress value is {row.latest_progress:g}.")
    body.append(
        _status_sentence(
            present=row.present_in_latest,
            last=row.last_observed,
            absent_after=row.first_absent_after_last,
        )
    )

    return f"""
      <article class="chronicle-event science-event situation-event">
        <div class="date">{_e(row.first_observed)}</div>
        <h3>{_e(row.title)}</h3>
        {''.join(f'<p>{_e(paragraph)}</p>' for paragraph in body)}
        <div class="evidence evidence-stack">
          <span><strong>Observed:</strong> {_e(_window(row.first_observed, row.last_observed))}</span>
        </div>
      </article>
    """


def render_science_section(db: Database, campaign_id: int) -> str:
    campaign = db.campaign(campaign_id)
    if campaign is None:
        return ""

    snapshots = _cache_science_snapshots(db, campaign_id)
    if not snapshots:
        return ""

    interpretation = derive_science_interpretation(snapshots)
    source_save = Path(campaign["source_save"])

    arc_html = _red_giant_arc(interpretation, source_save)

    archaeology_html = "".join(
        _archaeology_article(site)
        for site in sorted(
            interpretation.archaeology_sites,
            key=lambda item: (item.first_observed, item.title),
        )
    )

    # Only publish projects where the archive preserves a person, vessel,
    # location, or a genuine multi-objective family. Everything else remains
    # in the greedy diagnostics until stronger context is available.
    project_rows = [
        row for row in interpretation.project_families
        if row.project_key not in _RED_GIANT_PROJECT_KEYS
        and (
            row.scientist_names
            or row.ship_names
            or row.location_names
            or row.peak_concurrent_instances > 1
        )
    ]
    project_html = "".join(
        _project_article(row)
        for row in sorted(project_rows, key=lambda item: (item.first_observed, item.title))
    )

    # Economic shortages and revolts belong to future economy/politics domains.
    # Observation Insights are kept diagnostic-only until their observed target
    # can be resolved to a meaningful empire/species name. Other narrative
    # situations, such as Organic Singularity, are safe to publish conservatively.
    situation_rows = [
        row for row in interpretation.situations
        if row.type_key != _RED_GIANT_SITUATION_KEY
        and row.type_key not in _ECONOMIC_OR_POLITICAL_SITUATION_KEYS
        and row.type_key != "situation_observation_insight"
    ]
    situation_html = "".join(
        _situation_article(row, source_save)
        for row in sorted(situation_rows, key=lambda item: (item.first_observed, item.title))
    )

    if not any((arc_html, archaeology_html, project_html, situation_html)):
        return ""

    return f"""
      <section>
        <h2>Science, Exploration and Discoveries</h2>
        <p class="note">
          This chapter is reconstructed from archived archaeology, special-project
          and situation evidence. Historian groups related records into readable
          story arcs, but it does not invent outcomes: a project disappearing from
          a later save is not automatically called completed, failed or cancelled.
          Routine or weakly contextualised evidence remains preserved in the
          Science diagnostic files rather than being published here.
        </p>

        {
          f'<h3>Major Story Arcs</h3><div class="chronicle-events">{arc_html}</div>'
          if arc_html else ''
        }

        {
          f'<h3>Archaeology and Excavations</h3><div class="chronicle-events">{archaeology_html}</div>'
          if archaeology_html else ''
        }

        {
          f'<h3>Research Expeditions and Special Projects</h3><div class="chronicle-events">{project_html}</div>'
          if project_html else ''
        }

        {
          f'<h3>Observed Scientific Situations</h3><div class="chronicle-events">{situation_html}</div>'
          if situation_html else ''
        }
      </section>
    """
