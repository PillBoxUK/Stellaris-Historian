"""Planetary civic conditions are evidence-only; no screenshot facts are imported."""
from pathlib import Path
import json
import sqlite3
import tempfile

from historian.civic_frontier import (_observed_colony_conditions, _db, read_observations,
                                      timeline_events, VERSION)
from historian.core.stellaris_text import _find_named_block, _numeric_record
from historian.save_reader import read_save_texts, empire_profile_from_text


def test_native_ironman_colony_values():
    saved = Path('/mnt/data/ironman-57.sav')
    if not saved.exists():
        return  # This fixture is not shipped in the overlay.
    meta, gamestate = read_save_texts(saved)
    profile = empire_profile_from_text(meta, gamestate)
    player = _numeric_record(_find_named_block(gamestate, 'country'), profile.player_country_id)
    state = _observed_colony_conditions(gamestate, player, saved)
    assert state and any(row['name'] == 'Veyra Prime' for row in state.values())
    original = next(row for row in state.values() if row['name'] == 'Veyra Prime')
    assert original['crime'] is not None and original['stability'] is not None
    assert not original['incident_modifier_candidates']


def test_incident_keys_are_candidates_not_events():
    country = "owned_planets=\n{\n 1\n}"
    game = '''colony=\n{
 1=\n {
  carrier=\n  {
    reference=22
  }
  crime=73.5
  stability=26.8
 }
}
planet=\n{
 22=\n {
  name="Test Prime"
  planet_modifier="civil_unrest"
  flags=\n  {
    bribed_officials=22200101
    unrelated_flag=22200102
  }
  timed_modifier=\n  {
    items=\n    {
     {
       modifier="high_crime"
       days=15
     }
    }
  }
 }
}'''
    result = _observed_colony_conditions(game, country)
    assert result['22']['crime'] == 73.5
    assert result['22']['stability'] == 26.8
    assert 'bribed_officials' in result['22']['incident_flag_candidates']
    assert 'high_crime' in result['22']['incident_modifier_candidates']
    assert 'unrelated_flag' not in result['22']['incident_flag_candidates']
    # These are not published as riots, corruption cases or arrests on the Annals.
    rows = [{'date':'2220.01.01','government':{},'sectors':{},'stations':{},
             'discovered_systems':{},'colony_conditions':result}]
    assert not timeline_events(rows)


def test_legacy_v1_evidence_survives_v2_reader():
    with tempfile.TemporaryDirectory() as d:
        root=Path(d)
        with _db(root/'Civic_Frontier_History.sqlite3') as con:
            con.execute('INSERT INTO observations VALUES (?,?,?,?,?,?)',
                        ('testsha','2200.01.01','ironman-start.sav',0,json.dumps({'date':'2200.01.01','government':{}}),1))
        allowed=[{'sha256':'testsha','processed':1,'game_date':'2200.01.01','id':4}]
        result=read_observations(root, allowed)
        assert len(result)==1 and result[0]['snapshot_id']==4
        assert result[0]['snapshot_sha256']=='testsha'
        assert VERSION >= 2
