from __future__ import annotations

from pathlib import Path

from .correlation import CorrelatedEngagement, DirectCombatEpisode, correlation_summary


def _join(values: tuple[str, ...] | list[str]) -> str:
    return ", ".join(value for value in values if value) or "Not resolved"


def write_combat_correlation_diagnostic(
    archive_dir: Path,
    engagements: list[CorrelatedEngagement],
    direct_episodes: list[DirectCombatEpisode] | None = None,
) -> Path:
    path = Path(archive_dir) / "Combat_Correlation_Debug.txt"
    summary = correlation_summary(engagements)
    direct_episodes = direct_episodes or []

    lines = [
        "STELLARIS HISTORIAN - COMBAT CORRELATION DEBUG",
        "",
        "v0.0.38 correlation rules are evidence-first.",
        "Exact last_combat_activity dates are factual save evidence.",
        "Same-date grouping is a reconstruction step; confidence describes the grouping, not whether the individual combat markers are real.",
        "A ship disappearing in the same archive window is only a POSSIBLE LOSS. It is never called destroyed without stronger evidence.",
        "Diplomatic killed_ships values are preserved as directional relation counters. Historian does not yet translate them into 'kills inflicted' or 'ships lost'.",
        "",
        f"Candidate combat dates: {summary['candidate_engagements']}",
        f"Publishable correlated engagements: {summary['publishable_engagements']}",
        f"High-confidence correlations: {summary['high_confidence']}",
        f"Medium-confidence correlations: {summary['medium_confidence']}",
        f"Low-confidence/single-marker records: {summary['low_confidence']}",
        f"Engagements with relation-counter changes in the surrounding archive window: {summary['with_relation_deltas']}",
        f"Engagements whose surrounding archive window contains ship disappearances: {summary['with_possible_losses']}",
        f"Engagements with possible losses linked to a participant fleet: {summary['with_fleet_linked_possible_losses']}",
        f"Direct fleet-combat episodes reconstructed from combat_stats: {len(direct_episodes)}",
        f"Direct episodes with named opposing countries: {sum(1 for row in direct_episodes if row.enemy_country_names)}",
        f"Direct player ship losses recorded in combat telemetry: {sum(row.player_ships_lost for row in direct_episodes)}",
        f"Direct opposing ship losses recorded in combat telemetry: {sum(row.enemy_ships_lost for row in direct_episodes)}",
        "",
        "DIRECT FLEET COMBAT TELEMETRY",
        "=============================",
    ]

    if not direct_episodes:
        lines.append("No non-empty player fleet combat_stats records were preserved in the analysed snapshots.")
    else:
        for episode in direct_episodes:
            lines.extend([
                "",
                f"{episode.start_date} - Direct combat episode",
                f"  Evidence: player fleet combat/fleet_stats.combat_stats save records",
                f"  Latest archive observation carrying this telemetry: {episode.latest_observed_date}",
                f"  System: {episode.system_name or 'Not resolved'}"
                + (f" (ID {episode.system_id})" if episode.system_id is not None else ""),
                f"  Player fleets: {_join(tuple(row.player_fleet_name for row in episode.player_fleets))}",
                f"  Commanders: {_join(episode.commander_names)}",
                f"  Opposing countries: {_join(episode.enemy_country_names)}",
                f"  Opposing fleets: {_join(episode.enemy_fleet_names)}",
                f"  Aggregate player ships lost in direct fleet telemetry: {episode.player_ships_lost}",
                f"  Aggregate opposing ships lost in direct fleet telemetry: {episode.enemy_ships_lost}",
            ])
            for state in episode.player_fleets:
                enemies = ", ".join(
                    f"{enemy.country_name or ('Country ' + str(enemy.country_id))} / {enemy.fleet_name or ('Fleet ' + str(enemy.fleet_id))}"
                    for enemy in state.enemy_fleets
                ) or "Not resolved"
                lines.append(
                    f"    - {state.start_date}: {state.player_fleet_name}"
                    + (f" under {state.commander_name}" if state.commander_name else "")
                    + f"; player fleet losses {state.player_ships_lost or 0}; enemy {enemies}"
                )

    lines.extend(["", "CORRELATED ENGAGEMENT CANDIDATES", "================================"])

    for event in engagements:
        lines.extend([
            "",
            f"{event.combat_date} - Correlated combat activity",
            f"  Correlation confidence: {event.correlation_confidence.upper()}",
            f"  Publishable historical event: {'YES' if event.publishable else 'NO'}",
            f"  First archive observation of contributing marker(s): {event.first_observed_date}",
            f"  Exact ship markers: {len(event.ship_participants)}",
            f"  Exact starbase markers: {len(event.starbase_participants)}",
            f"  Formal battle records on exact date: {len(event.formal_battles)}",
            f"  Fleets in first-observed marker context: {_join(event.fleet_names)}",
            f"  Commanders in first-observed marker context: {_join(event.commander_names)}",
            f"  Systems in first-observed marker context: {_join(event.context_system_names)}",
        ])

        if event.window_end_date:
            lines.append(
                "  Surrounding archive window: "
                f"{event.window_start_date or 'record opening'} -> {event.window_end_date}"
            )
        if event.mobile_ships_before is not None and event.mobile_ships_after is not None:
            lines.append(
                f"  Mobile ship count across window: {event.mobile_ships_before} -> {event.mobile_ships_after}"
            )
        if event.queued_builds_after is not None:
            lines.append(f"  Queued builds at end of window: {event.queued_builds_after}")

        if event.ship_participants:
            lines.append("  Ship markers:")
            for state in event.ship_participants:
                details = [f"ID {state.ship_id}", state.ship_type]
                if state.fleet_name:
                    details.append(f"fleet {state.fleet_name}")
                if state.commander_name:
                    details.append(f"commander {state.commander_name}")
                if state.system_name:
                    details.append(f"snapshot context {state.system_name}")
                lines.append(f"    - {state.ship_name}: " + "; ".join(details))

        if event.starbase_participants:
            lines.append("  Starbase markers:")
            for state in event.starbase_participants:
                details = [f"ID {state.starbase_id}"]
                if state.system_name:
                    details.append(f"snapshot context {state.system_name}")
                lines.append(f"    - {state.starbase_name}: " + "; ".join(details))

        if event.relation_counter_deltas:
            lines.append("  Relation kill-counter changes in same archive window:")
            for delta in event.relation_counter_deltas:
                flags = []
                if delta.hostile:
                    flags.append("hostile")
                if delta.first_contact_hostility:
                    flags.append("first-contact hostility")
                suffix = f" ({', '.join(flags)})" if flags else ""
                lines.append(
                    f"    - {delta.other_country_name}{suffix}: "
                    f"player-side record {delta.player_counter_before} -> {delta.player_counter_after} "
                    f"(delta {delta.player_counter_delta:+d}); reciprocal record "
                    f"{delta.reciprocal_counter_before} -> {delta.reciprocal_counter_after} "
                    f"(delta {delta.reciprocal_counter_delta:+d})"
                )

        if event.possible_losses:
            lines.append("  Ship disappearances inside same archive window (NOT proven combat losses):")
            for loss in event.possible_losses:
                linked = "participant-fleet link" if loss.linked_to_participant_fleet else "no direct fleet link"
                fleet = f"; fleet {loss.fleet_name}" if loss.fleet_name else ""
                lines.append(
                    f"    - {loss.ship_name} (ID {loss.ship_id}; {loss.ship_type}{fleet}; {linked})"
                )

        lines.append(
            "  Interpretation: exact combat date(s) are factual; opponent, location-at-combat, outcome and casualties remain unclaimed unless formal/direct evidence above proves them."
        )

    lines.extend([
        "",
        "CORRELATION SAFETY RULES",
        "========================",
        "- Same-day markers may be grouped as a probable shared engagement when multiple entities, a starbase, a formal battle, or other independent evidence supports the grouping.",
        "- Snapshot system/fleet/commander context is not silently converted into exact battle-time fact.",
        "- Relation counter movement can identify a useful candidate counterpart in the same archive interval, but counter direction semantics remain deliberately unresolved in v0.0.38.",
        "- A missing ship is never called destroyed solely because it vanishes after combat.",
        "- Formal battle result evidence overrides correlation inference where a formal battle record survives.",
        "",
    ])

    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path
