from __future__ import annotations

from pathlib import Path

from .history import derive_technology_history, technology_evidence_summary, technology_window_label
from .models import TechnologySnapshot


def write_technology_diagnostic(
    archive_dir: Path,
    snapshots: list[TechnologySnapshot],
) -> Path:
    archive_dir = Path(archive_dir)
    path = archive_dir / "Technology_Evidence_Debug.txt"
    summary = technology_evidence_summary(snapshots)
    history = derive_technology_history(snapshots)

    lines = [
        "STELLARIS HISTORIAN - TECHNOLOGY EVIDENCE DEBUG",
        "",
        "This diagnostic records researched technologies visible in the player's country tech_status.",
        "A technology first appearing between two archived snapshots is known to have been acquired in that interval; the exact completion day is not invented.",
        "Research-queue entries are excluded until they become completed technology entries.",
        "",
        f"Snapshots analysed: {len(snapshots)}",
        f"Distinct dated archive days: {summary['distinct_archive_dates']}",
        f"Additional same-day archives: {summary['same_day_extra_archives']}",
        f"Days with differing same-date technology states: {summary['same_day_disagreement_days']}",
        f"Archives with invalid/unusable dates: {summary['invalid_date_archives']}",
        f"Technologies already known at the opening snapshot: {summary['opening_technologies']}",
        f"First-observed technology gains / level increases: {summary['technology_events']}",
        f"Technologies known in the latest snapshot: {summary['latest_technologies']}",
        "",
        "TECHNOLOGY GAINS",
        "================",
    ]

    if not history["events"]:
        lines.append("No technology acquisitions were newly observed between archived snapshots.")
    else:
        for event in history["events"]:
            level = f" (level {event.level})" if event.level > 1 else ""
            window = technology_window_label(event)
            lines.extend([
                "",
                f"{event.game_date} - {event.name}{level}",
                f"  Key: {event.key}",
                f"  Evidence window: {window}",
                f"  Event: {event.event_type}",
            ])

    lines.extend([
        "",
        "INTERPRETATION RULES",
        "====================",
        "- First appearance establishes an acquisition window, not an exact research-completion day.",
        "- Technologies present in the first archived state are opening knowledge, not claimed discoveries of that date.",
        "- Same-day archives are aggregated as dated observations, not ordered into a fictitious interval.",
        "- A technology level is only announced when it exceeds every level previously observed.",
        "- If saves disagree within one in-game date, no exact same-day acquisition order is inferred.",
        "- Queued research is not treated as completed technology.",
        "- Localised names come from the user's installed game/DLC/mod localisation when available; raw keys are humanised only as a fallback.",
        "",
    ])

    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path
