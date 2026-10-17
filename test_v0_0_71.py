"""v0.0.71 evidence, date and research-boundary regressions; no save writes."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from historian.domains.technology.models import TechnologyEvent, TechnologySnapshot, TechnologyState
from historian.domains.technology.history import (
    derive_technology_history, technology_window_label, technology_coverage_audit,
    technology_evidence_summary,
)
from historian.domains.technology.diagnostic import write_technology_diagnostic
from historian.war_journal import FormalWarRecord, _war_technology_html, _research_audit_html


def tech(key, level=1):
    return TechnologyState(key, key.replace('tech_', '').replace('_', ' ').title(), level)


def snap(index, date, **items):
    return TechnologySnapshot(index, date, 0, {key: tech(key, value) for key, value in items.items()})


saves = [
    snap(7, '2293.04.01', tech_mining=1),
    snap(8, '2294.04.01', tech_mining=1, tech_weaving=1),
    # Inconsistent records sharing this date: still just one dated observation.
    snap(9, '2294.04.01', tech_mining=1, tech_weaving=2, tech_lasers=1),
    snap(10, '2294.07.01', tech_mining=1, tech_weaving=2, tech_lasers=1),
    # Partial cache missing techs, and a level regression in a later snapshot.
    snap(11, '2295.01.01', tech_weaving=1),
    snap(12, '2295.04.01', tech_mining=1, tech_weaving=2, tech_lasers=1),
    snap(13, '2296.01.01', tech_weaving=3, tech_lasers=1, tech_mining=1),
    snap(14, '0.01.01', tech_bogus=99),
]
# Disorder input; order by date, not list position.
result = derive_technology_history(list(reversed(saves)))
events = result['events']
assert {(e.key, e.level, e.game_date, e.previous_game_date) for e in events} == {
    ('tech_weaving', 2, '2294.04.01', '2293.04.01'),
    ('tech_lasers', 1, '2294.04.01', '2293.04.01'),
    ('tech_weaving', 3, '2296.01.01', '2295.04.01'),
}
assert all(e.previous_game_date < e.game_date for e in events)
assert all('after '+e.game_date+' and by '+e.game_date not in technology_window_label(e) for e in events)
assert 'tech_bogus' not in [e.key for e in events]
assert [t.key for t in result['opening']] == ['tech_mining']
assert {t.key:t.level for t in result['latest']} == {'tech_mining':1, 'tech_weaving':3, 'tech_lasers':1}
audit = technology_coverage_audit(saves)
assert audit['snapshots'] == 8
assert audit['dated_snapshots'] == 7
assert audit['invalid_date_snapshots'] == 1
assert audit['distinct_dates'] == 6
assert audit['same_date_additional_snapshots'] == 1
assert audit['same_date_disagreement_days'] == 1
assert technology_evidence_summary(saves)['technology_events'] == 3
assert 'Same-day states differing' in _research_audit_html(result)
assert '2293.04.01' in _research_audit_html(result)
assert 'No valid dated completed-technology' in _research_audit_html(derive_technology_history([]))

# Date-only no phantom acquisitions if every archive on a day has identical state.
identical = [snap(1,'2200.01.01'), snap(2,'2200.04.01', tech_alpha=1),
             snap(3,'2200.04.01', tech_alpha=1), snap(4,'2200.07.01', tech_alpha=1)]
assert len(derive_technology_history(identical)['events']) == 1
# Opening-day additions can't be assigned a strictly earlier date.
opening_same_day = [snap(1,'2200.01.01'), snap(2,'2200.01.01',tech_alpha=1),
                    snap(3,'2200.04.01',tech_alpha=1)]
assert not derive_technology_history(opening_same_day)['events']

# Defensive fallback against legacy inconsistent TechnologyEvent objects.
event = events[0]
assert 'same-day archive order' in technology_window_label(replace(event,previous_game_date=event.game_date))
assert 'inconsistent' in technology_window_label(replace(event,previous_game_date='2299.01.01'))
assert 'earlier bound not established' in technology_window_label(replace(event,previous_game_date=None))
assert 'date uncertain' in technology_window_label(replace(event,game_date='0.01.01'))

war = FormalWarRecord(war_id=555, name='War', start_date='2294.01.01', first_observed='2294.01.01',
                      last_observed='2295.04.01', player_side='attacker', attacker_war_goal='conquest',
                      defender_war_goal='conquest')
html = _war_technology_html(war, tuple(events),snapshots_available=True,
                            technology_dates=tuple(s.game_date for s in saves))
assert '2294.04.01' in html
assert '2 distinct technology archive date(s)' not in html # 2294.04 / 2294.07 / 2295.01 / 2295.04
assert '4 distinct technology archive date(s)' in html
assert 'may predate war' in html
assert 'cross the first war archive boundary' in html
assert 'after 2294.04.01 and by 2294.04.01' not in html
assert 'tech_bogus' not in html
assert 'research-coverage' in html
assert '2296.01.01' not in html  # later repeatable level rise is not attributed to this war
assert 'conflict caused the research' in html

# Distinguish no within-war technology dates from no observed research.
empty = _war_technology_html(war,tuple(events),snapshots_available=True,
                             technology_dates=('2293.04.01','2296.04.01'))
assert 'no within-war archive coverage' in empty
assert 'research stopped' in empty
unavailable = _war_technology_html(war,(),snapshots_available=False)
assert 'archive coverage unavailable' in unavailable
# HTML injection cannot escape its table cells.
injected = replace(event,name='<img src=x onerror=alert(1)>')
escaped = _war_technology_html(war,(injected,),snapshots_available=True,
                               technology_dates=('2293.04.01','2294.04.01'))
assert '<img src=x onerror=alert(1)>' not in escaped
assert '&lt;img src=x onerror=alert(1)&gt;' in escaped

with TemporaryDirectory() as temp:
    path = write_technology_diagnostic(Path(temp),saves)
    text=path.read_text(encoding='utf-8')
    assert 'Additional same-day archives: 1' in text
    assert 'Days with differing same-date technology states: 1' in text
    assert 'Archives with invalid/unusable dates: 1' in text
    assert 'after 2294.04.01 and by 2294.04.01' not in text

source = (Path(__file__).parent/'historian/war_journal.py').read_text(encoding='utf-8')
assert 'RESEARCH EVIDENCE AND ARCHIVE COVERAGE' in source
assert 'research.querySelector' in source
print('ALL v0.0.71 RESEARCH AND WAR EVIDENCE TESTS PASS')
