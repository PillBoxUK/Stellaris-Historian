from __future__ import annotations

from dataclasses import dataclass

from .models import ScienceSnapshot


@dataclass(frozen=True)
class ObservationWindow:
    first_observed: str
    last_observed: str
    first_absent_after_last: str | None
    present_in_latest: bool
    observation_runs: int


@dataclass(frozen=True)
class ArchaeologyInterpretation:
    site_id: int
    title: str
    type_key: str
    first_observed: str
    last_observed: str
    first_absent_after_last: str | None
    record_persists_in_latest: bool
    location_names: tuple[str, ...]
    highest_chapter_index: int | None
    scientist_names: tuple[str, ...]
    progress_marker_dates: tuple[str, ...]
    observation_runs: int


@dataclass(frozen=True)
class ProjectFamilyInterpretation:
    project_key: str
    title: str
    project_ids: tuple[int, ...]
    instance_count: int
    peak_concurrent_instances: int
    first_observed: str
    last_observed: str
    first_absent_after_last: str | None
    present_in_latest: bool
    location_names: tuple[str, ...]
    ship_names: tuple[str, ...]
    scientist_names: tuple[str, ...]


@dataclass(frozen=True)
class SituationInterpretation:
    situation_id: int
    type_key: str
    title: str
    first_observed: str
    last_observed: str
    first_absent_after_last: str | None
    present_in_latest: bool
    latest_progress: float | None
    latest_approach_key: str | None
    target_type: str | None
    target_id: int | None
    observation_runs: int


@dataclass(frozen=True)
class ScienceInterpretation:
    archaeology_sites: tuple[ArchaeologyInterpretation, ...]
    project_families: tuple[ProjectFamilyInterpretation, ...]
    situations: tuple[SituationInterpretation, ...]
    raw_project_instances: int
    anomaly_ids: tuple[int, ...]


def _dates_in_order(snapshots: list[ScienceSnapshot]) -> list[str]:
    return [snapshot.game_date for snapshot in snapshots]


def _presence_indexes(
    snapshots: list[ScienceSnapshot],
    attr: str,
    record_id: int,
) -> list[int]:
    indexes: list[int] = []
    for index, snapshot in enumerate(snapshots):
        records = getattr(snapshot, attr)
        if record_id in records:
            indexes.append(index)
    return indexes


def _observation_window(
    snapshots: list[ScienceSnapshot],
    attr: str,
    record_id: int,
) -> ObservationWindow:
    indexes = _presence_indexes(snapshots, attr, record_id)
    if not indexes:
        raise ValueError(f"Record {record_id} was not observed in {attr}.")

    runs = 1
    for previous, current in zip(indexes, indexes[1:]):
        if current != previous + 1:
            runs += 1

    last_index = indexes[-1]
    first_absent_after_last = (
        snapshots[last_index + 1].game_date
        if last_index + 1 < len(snapshots)
        else None
    )

    return ObservationWindow(
        first_observed=snapshots[indexes[0]].game_date,
        last_observed=snapshots[last_index].game_date,
        first_absent_after_last=first_absent_after_last,
        present_in_latest=last_index == len(snapshots) - 1,
        observation_runs=runs,
    )


def _unique(values) -> tuple:
    result = []
    for value in values:
        if value is None or value == "":
            continue
        if value not in result:
            result.append(value)
    return tuple(result)


def derive_science_interpretation(
    snapshots: list[ScienceSnapshot],
) -> ScienceInterpretation:
    if not snapshots:
        return ScienceInterpretation((), (), (), 0, ())

    archaeology_ids = sorted(
        {
            site_id
            for snapshot in snapshots
            for site_id in snapshot.archaeology_sites
        }
    )

    archaeology_rows: list[ArchaeologyInterpretation] = []
    for site_id in archaeology_ids:
        observed = [
            snapshot.archaeology_sites[site_id]
            for snapshot in snapshots
            if site_id in snapshot.archaeology_sites
        ]
        window = _observation_window(snapshots, "archaeology_sites", site_id)
        latest = observed[-1]
        chapter_values = [
            row.chapter_index
            for row in observed
            if row.chapter_index is not None
        ]
        marker_dates = sorted(
            {
                date
                for row in observed
                for date in row.player_completion_dates
            }
        )

        archaeology_rows.append(
            ArchaeologyInterpretation(
                site_id=site_id,
                title=latest.title,
                type_key=latest.type_key,
                first_observed=window.first_observed,
                last_observed=window.last_observed,
                first_absent_after_last=window.first_absent_after_last,
                record_persists_in_latest=window.present_in_latest,
                location_names=_unique(row.location_name for row in observed),
                highest_chapter_index=max(chapter_values) if chapter_values else None,
                scientist_names=_unique(row.scientist_name for row in observed),
                progress_marker_dates=tuple(marker_dates),
                observation_runs=window.observation_runs,
            )
        )

    # Stellaris can recycle numeric special-project IDs after an older project
    # disappears. The stable semantic identity is therefore (ID, project key),
    # not the numeric ID alone. Keeping that distinction prevents a later
    # project from inheriting the scientist/ship/location evidence of an older
    # project that happened to reuse the same ID.
    project_instances: dict[tuple[int, str], list] = {}
    for snapshot in snapshots:
        for project_id, project in snapshot.special_projects.items():
            identity = (project_id, project.project_key)
            project_instances.setdefault(identity, []).append(project)

    families: dict[str, list[tuple[int, str]]] = {}
    for identity, records in project_instances.items():
        if not records:
            continue
        families.setdefault(identity[1], []).append(identity)

    def project_presence_indexes(project_id: int, project_key: str) -> list[int]:
        indexes: list[int] = []
        for index, snapshot in enumerate(snapshots):
            record = snapshot.special_projects.get(project_id)
            if record is not None and record.project_key == project_key:
                indexes.append(index)
        return indexes

    project_rows: list[ProjectFamilyInterpretation] = []
    latest_projects = snapshots[-1].special_projects
    for project_key, identities in sorted(families.items()):
        all_records = [
            project
            for identity in identities
            for project in project_instances[identity]
        ]

        first_indexes: list[int] = []
        last_indexes: list[int] = []
        for project_id, identity_key in identities:
            indexes = project_presence_indexes(project_id, identity_key)
            if indexes:
                first_indexes.append(indexes[0])
                last_indexes.append(indexes[-1])

        first_index = min(first_indexes)
        last_index = max(last_indexes)

        latest_record = None
        for snapshot in reversed(snapshots):
            matching = [
                record
                for record in snapshot.special_projects.values()
                if record.project_key == project_key
            ]
            if matching:
                latest_record = matching[-1]
                break
        if latest_record is None:
            continue

        present_in_latest = any(
            record.project_key == project_key
            for record in latest_projects.values()
        )
        first_absent_after_last = (
            snapshots[last_index + 1].game_date
            if last_index + 1 < len(snapshots) and not present_in_latest
            else None
        )

        peak_concurrent = max(
            sum(
                1
                for record in snapshot.special_projects.values()
                if record.project_key == project_key
            )
            for snapshot in snapshots
        )

        project_ids = tuple(sorted(identity[0] for identity in identities))
        project_rows.append(
            ProjectFamilyInterpretation(
                project_key=project_key,
                title=latest_record.title,
                project_ids=project_ids,
                instance_count=len(identities),
                peak_concurrent_instances=peak_concurrent,
                first_observed=snapshots[first_index].game_date,
                last_observed=snapshots[last_index].game_date,
                first_absent_after_last=first_absent_after_last,
                present_in_latest=present_in_latest,
                location_names=_unique(row.location_name for row in all_records),
                ship_names=_unique(row.linked_ship_name for row in all_records),
                scientist_names=_unique(row.scientist_name for row in all_records),
            )
        )

    situation_ids = sorted(
        {
            situation_id
            for snapshot in snapshots
            for situation_id in snapshot.situations
        }
    )
    situation_rows: list[SituationInterpretation] = []
    for situation_id in situation_ids:
        observed = [
            snapshot.situations[situation_id]
            for snapshot in snapshots
            if situation_id in snapshot.situations
        ]
        window = _observation_window(snapshots, "situations", situation_id)
        latest = observed[-1]
        situation_rows.append(
            SituationInterpretation(
                situation_id=situation_id,
                type_key=latest.type_key,
                title=latest.title,
                first_observed=window.first_observed,
                last_observed=window.last_observed,
                first_absent_after_last=window.first_absent_after_last,
                present_in_latest=window.present_in_latest,
                latest_progress=latest.progress,
                latest_approach_key=latest.approach_key,
                target_type=latest.target_type,
                target_id=latest.target_id,
                observation_runs=window.observation_runs,
            )
        )

    anomaly_ids = sorted(
        {
            anomaly_id
            for snapshot in snapshots
            for anomaly_id in snapshot.anomaly_ids
        }
    )

    return ScienceInterpretation(
        archaeology_sites=tuple(archaeology_rows),
        project_families=tuple(project_rows),
        situations=tuple(situation_rows),
        raw_project_instances=len(project_instances),
        anomaly_ids=tuple(anomaly_ids),
    )
