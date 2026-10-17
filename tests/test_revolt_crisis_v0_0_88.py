"""Native save-only revolt state, cross-save chronology and provenance tests."""
from pathlib import Path
from types import SimpleNamespace
import json
import sqlite3
import tempfile

from historian.civic_frontier import (
    _direct_scalar, _observed_player_situations, _is_revolt_situation,
    _crisis_key, revolt_evidence, timeline_events, VERSION, read_observations,
    render_civic_frontier_history,
)

WORLD = {'44': {'planet_id':44, 'colony_id':2, 'name':'Veyra Prime',
                'crime':73.5,'stability':28.0}}


def state(*, stage=0, situation_id=12, owner=0, target=2,
          definition='planetary_revolt', progress=4.0):
    return '''situations=\n{{\n situations=\n {{\n  {identifier}=\n  {{\n   country={owner}\n   target=\n   {{\n    type=colony\n    id={target}\n    opener_id=4294967295\n   }}\n   type="{definition}"\n   progress={progress}\n   stage={stage}\n   approach="approach_revolt_do_nothing"\n  }}\n }}\n}}'''.format(
        identifier=situation_id, owner=owner, target=target,
        definition=definition, progress=progress, stage=stage)


def obs(date, active=None, ident='a'):
    return {'date':date, 'government':{}, 'sectors':{},'stations':{},
            'discovered_systems':{},'active_situations':active or {},
            'snapshot_sha256':ident,'colony_conditions':WORLD}


def test_nested_target_type_does_not_mask_actual_situation_type():
    block = '''\n  country=0\n  target=\n  {\n   type=colony\n   id=2\n  }\n  type="planetary_revolt"\n  stage=1\n'''
    assert _direct_scalar(block,'type') == 'planetary_revolt'
    assert _direct_scalar(block,'country') == '0'


def test_owned_crises_only_and_native_keys_unmodified():
    seen = _observed_player_situations(state(), 0, WORLD)
    assert len(seen) == 1
    row = seen['12']
    assert row['key'] == 'planetary_revolt'
    assert row['world'] == 'Veyra Prime'
    assert row['target_type'] == 'colony'
    assert row['stage'] == 0 and row['progress'] == 4.0
    assert _is_revolt_situation(row)
    assert _observed_player_situations(state(owner=19),0,WORLD) == {}
    assert _observed_player_situations(state(target=9),0,WORLD) == {}
    assert _observed_player_situations(state(definition='situation_scientific_opportunity'),0,WORLD)['12']


def test_revolt_sequence_does_not_invent_exact_start_or_end():
    first = _observed_player_situations(state(),0,WORLD)
    changed = _observed_player_situations(state(stage=1,progress=47.0),0,WORLD)
    rows = [obs('2222.01.01'),obs('2222.04.01',first),
            obs('2222.07.01',changed),obs('2222.10.01')]
    events = [e for e in timeline_events(rows) if 'revolt' in e['title'].lower() or 'unrest' in e['title'].lower()]
    assert len(events) == 3
    assert [e['date'] for e in events] == ['2222.04.01','2222.07.01','2222.10.01']
    assert all(e['date_kind'] == 'first_observed' for e in events)
    assert 'active' in events[0]['body']
    assert 'outcome' in events[1]['body']
    assert 'not established' in events[2]['body']
    assert 'resolved' not in ' '.join(e['body'] for e in events)
    evidence = revolt_evidence(rows)
    assert len(evidence) == 2
    assert evidence[0]['sha256'] == 'a'


def test_preexisting_crisis_and_id_reuse_no_false_same_episode():
    first = _observed_player_situations(state(),0,WORLD)
    other = _observed_player_situations(state(definition='civil_unrest',stage=2),0,WORLD)
    entries = timeline_events([obs('2222.01.01',first),obs('2222.04.01',other)])
    related = [e for e in entries if 'revolt' in e['title'].lower() or 'unrest' in e['title'].lower()]
    assert len(related) == 3
    assert related[0]['date_kind'] == 'opening_observation'
    assert _crisis_key(first['12']) != _crisis_key(other['12'])


def test_v2_observations_remain_readable():
    from historian.civic_frontier import _db
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        with _db(root/'Civic_Frontier_History.sqlite3') as conn:
            conn.execute('INSERT INTO observations VALUES (?,?,?,?,?,?)',
                         ('v2hash','2220.01.01','ironman-90.sav',0,json.dumps(obs('2220.01.01')),2))
        records = read_observations(root, [{'sha256':'v2hash','processed':1,
             'game_date':'2220.01.01','id':45}])
        assert len(records) == 1 and records[0]['snapshot_sha256'] == 'v2hash'
        assert VERSION == 4


def test_foreign_colony_situation_never_in_players_chronicle():
    other = _observed_player_situations(state(owner=200),0,WORLD)
    assert other == {}
    assert not timeline_events([obs('2222.04.01',other)])


def test_civic_page_renders_crisis_register_and_exports_full_hashes():
    from historian.civic_frontier import _db
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        incident = _observed_player_situations(state(),0,WORLD)
        row = obs('2222.04.01',incident,ident='b'*64)
        with _db(root/'Civic_Frontier_History.sqlite3') as db:
            db.execute('INSERT INTO observations VALUES (?,?,?,?,?,?)',
                       ('b'*64,'2222.04.01','ironman-88.sav',0,json.dumps(row),3))
        class Fixture:
            def campaign(self, _cid):
                return {'archive_dir':str(root), 'empire_name':'Veyran Shadow Concord 2'}
            def all_snapshots(self, _cid):
                return [{'sha256':'b'*64,'processed':1,'game_date':'2222.04.01','id':44}]
        page = render_civic_frontier_history(Fixture(),1)
        content = page.read_text('utf-8')
        csv_text = (root/'Public_Order_Crisis_Observations.csv').read_text('utf-8-sig')
        assert 'Planetary revolt &amp; civic crisis tracking' in content
        assert 'Veyra Prime' in content
        assert 'planetary_revolt' in content
        assert 'Export the complete save-backed crisis ledger' in content
        assert ',0,4.0,approach_revolt_do_nothing,' in csv_text
        assert 'b'*64 in csv_text
        assert 'A revolt crisis already looms over Veyra Prime' in content
