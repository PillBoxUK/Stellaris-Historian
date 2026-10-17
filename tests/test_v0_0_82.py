"""v0.0.82 — native governance, system discovery and infrastructure regression.

Run from the Historian root with `python test_v0_0_82.py`.
No external saves, active user files, game installation or network required.
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from historian.civic_frontier import (_db, read_observations, timeline_events,
                                       extract_observation, VERSION)
from historian.narrative_clean import clean_game_description


def make(date):
    return {'date':date, 'player_country_id':29,
            'government': {'type':'gov_military_dictatorship','authority':'auth_dictatorial',
                          'ethics':['ethic_militarist'],'civics':['civic_a'],
                          'ruler_id':8,'agenda':'agenda_display_of_power',
                          'council_positions':['councilor_research'],
                          'policies':['unrestricted_wars']},
            'sectors': {'3':{'name':'Home','type':'core_sector','capital':10}},
            'stations': {'1':{'role':'starbase','system_id':11,'system':'Deneb',
                             'built':'2200.01.01','level':'starbase_level_starport',
                             'modules':['shipyard'],'buildings':[]}},
            'discovered_systems': {'11':'Deneb'}}


def run():
    opening=make('2200.01.01')
    middle=make('2200.07.01')
    middle['government']={**middle['government'], 'ethics':['ethic_militarist','ethic_materialist'],
                          'agenda':'agenda_strong_on_our_own',
                          'council_positions':['councilor_defense','councilor_research'],
                          'policies':['unrestricted_wars','slavery_allowed']}
    middle['sectors']['12']={'name':'Keso','type':'regular_sector','capital':14}
    middle['stations']['1']={**middle['stations']['1'], 'level':'starbase_level_starhold',
                             'modules':['shipyard','anchorage']}
    middle['stations']['5']={'role':'research','system_id':17,'system':'Vesta','built':'2200.05.16'}
    middle['stations']['9']={'role':'starbase','system_id':17,'system':'Vesta',
                            'built':'2200.06.19','level':'starbase_level_outpost',
                            'modules':[],'buildings':[]}
    middle['discovered_systems']['17']='Vesta'
    late=make('2201.01.01')
    late['government']={**middle['government'], 'type':'gov_military_commissariat',
                        'ruler_id':10}
    late['stations']=dict(middle['stations'])
    late['discovered_systems']=dict(middle['discovered_systems'])
    late['sectors']=dict(middle['sectors'])
    events=timeline_events([opening,middle,late])
    titles=[e['title'] for e in events]
    assert 'Government reorganised' in titles
    assert 'A new council agenda' in titles
    assert 'The laws and policies of the realm evolve' in titles
    assert 'The governing council is reorganised' in titles
    assert 'A change in the political outlook' in titles
    assert 'Vesta enters imperial control' in titles
    assert 'Vesta enters the charts' in titles
    assert 'Research Station established in the Vesta system' in titles
    assert 'Starbase expanded in the Deneb system' in titles
    research=next(e for e in events if e['title'].startswith('Research Station'))
    assert research['date']=='2200.05.16'
    assert research['date_kind']=='exact_save_field'
    assert '16 May 2200' in research['body']
    assert not any(e['date']=='2200.01.01' for e in events) # starting holdings not fabricated
    assert all('player' not in e['body'].lower() for e in events)
    assert not any('slavery' in e['body'].lower() and 'occurred' in e['body'].lower() for e in events)
    assert all(e['category'] in ('Politics','Exploration','Infrastructure','Expansion') for e in events)

    # Sidecar isolation: only the current campaign's hash-matched processed
    # saves are allowed to surface in the published chronology.
    with TemporaryDirectory() as temp:
        archive=Path(temp)
        with _db(archive/'Civic_Frontier_History.sqlite3') as con:
            con.execute('INSERT INTO observations VALUES (?,?,?,?,?,?)',
                        ('one','2200.01.01','first.sav',29,json.dumps(opening),VERSION))
            con.execute('INSERT INTO observations VALUES (?,?,?,?,?,?)',
                        ('two','2200.07.01','other.sav',29,json.dumps(middle),VERSION))
        snapshots=[{'id':1,'sha256':'one','game_date':'2200.01.01','processed':1},
                   {'id':2,'sha256':'two','game_date':'2200.07.01','processed':0}]
        rows=read_observations(archive,snapshots)
        assert len(rows)==1 and rows[0]['snapshot_id']==1
    assert not clean_game_description('The people on have stumbled upon a new type of species.')
    assert not clean_game_description('Planetary Revolt on [Target.GetName]')
    print('PASS v0.0.82: politics, councils, policies, territory, stations, exact dates, baseline, source integrity, clean story prose')

if __name__=='__main__':
    run()
