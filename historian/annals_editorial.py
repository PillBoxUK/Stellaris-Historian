"""Pure, read-only editorial helpers for the Imperial Annals.

Source entries remain authoritative. These helpers rank visibility and compose
short extracts from original descriptions; they never infer event outcomes,
causes or new chronology. The user's browser annotations are a separate layer.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterable

MONTHS = ('January','February','March','April','May','June','July','August',
          'September','October','November','December')


def reading_importance(event) -> int:
    """Editorial salience only, not historical evidence or a game statistic."""
    base = max(0, min(100, int(getattr(event, 'importance', 50) or 0)))
    category = str(getattr(event, 'category', '')).casefold()
    title = str(getattr(event, 'title', '')).casefold()
    if category == 'war':
        base = max(base, 90)
    if category in ('politics', 'command', 'diplomacy', 'combat'):
        base = max(base, 60)
    if any(word in title for word in ('first ', 'founded', 'colonised', 'revolt',
                                      'war begins', 'victory', 'defeat', 'dies',
                                      'coronation', 'government changes')):
        base = max(base, 85)
    if 'station established' in title or 'station completed' in title:
        base = min(base, 39)  # routine infrastructure, without losing it
    return base


def date_label(date_kind: str, evidence: str = '') -> tuple[str, str]:
    """Distinguish explicit chronology from later sightings, without guessing."""
    kind = str(date_kind or '').lower()
    if kind in ('exact_save_field', 'exact_event', 'exact', 'dated', 'retained_event_date'):
        return ('Dated event', 'The source retains an explicit event date.')
    if kind in ('first_observed', 'archive_observation', 'first_seen', 'observation'):
        return ('First recorded by', 'This is an observation date, not proof of the day of occurrence.')
    if kind in ('starting_state', 'opening_state', 'archive_start'):
        return ('Already recorded at the opening', 'The start of the archive is not a founding date.')
    if kind in ('retained_or_observed', 'mixed', ''):
        return ('Date evidence varies', 'Read the supporting source notes for this entry.')
    # Unknown definitions are not silently promoted to exact event dates.
    return ('Archival date', 'The exact occurrence date has not been independently established.')


def period_extract(events: Iterable, *, limit: int = 2) -> list[str]:
    """Quote complete source-authored historical sentences; never rewrite facts."""
    candidates = sorted(events, key=lambda ev: (-reading_importance(ev), ev.game_date, ev.title))
    result: list[str] = []
    seen: set[str] = set()
    for event in candidates:
        body = re.sub(r'\s+', ' ', str(getattr(event, 'body', '') or '')).strip()
        if not body or body.casefold() in seen:
            continue
        # Avoid boilerplate diagnostic text rather than paraphrasing uncertain facts.
        if any(x in body.casefold() for x in ('source observation:', 'raw id:', 'cached component:')):
            continue
        seen.add(body.casefold())
        result.append(body)
        if len(result) == limit:
            break
    return result


def month_groups(events: Iterable) -> list[tuple[str, str, list]]:
    """Keep dates ordered and same-day entries together; no inferred intervening events."""
    groups = defaultdict(list)
    for event in events:
        groups[str(event.game_date)[:7]].append(event)
    return [ (key, MONTHS[int(key[5:7])-1] if key[5:7].isdigit() and 1 <= int(key[5:7]) <= 12 else key,
              sorted(items, key=lambda e: (e.game_date, -reading_importance(e), e.title)))
            for key, items in sorted(groups.items())]
