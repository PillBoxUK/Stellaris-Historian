from __future__ import annotations

from pathlib import Path

from .history import derive_technology_history, technology_evidence_summary
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
            if event.previous_game_date:
                window = f"after {event.previous_game_date} and by {event.game_date}"
            else:
                window = f"by {event.game_date}"
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
        "- Queued research is not treated as completed technology.",
        "- Localised names come from the user's installed game/DLC/mod localisation when available; raw keys are humanised only as a fallback.",
        "",
    ])

    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path
