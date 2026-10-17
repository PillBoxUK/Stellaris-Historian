"""v0.0.84 Imperial Situation Room regression tests: no real campaign data modified.
Run: python tests/test_v0_0_84.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from historian.imperial_dashboard import dashboard_data


def create_fixture(root: Path):
    archive = root / 'archive';archive.mkdir();(archive / '.historian_cache').mkdir()
    db = root / 'historian.db'
    with sqlite3.connect(db) as con:
        con.executescript('''
            CREATE TABLE campaigns(id INTEGER PRIMARY KEY,empire_name TEXT,first_game_date TEXT,latest_game_date TEXT,archive_dir TEXT);
            CREATE TABLE snapshots(id INTEGER PRIMARY KEY,campaign_id INT,sequence_no INT,game_date TEXT,sha256 TEXT,archive_filename TEXT,archive_path TEXT,processed INT);
            CREATE TABLE politics_states(id INTEGER PRIMARY KEY,campaign_id INT,snapshot_id INT,state_json TEXT);
            CREATE TABLE leader_career_events(id INTEGER PRIMARY KEY,campaign_id INT,game_date TEXT,event_type TEXT,title TEXT,body TEXT,visible INT,date_kind TEXT);
            CREATE TABLE politics_history_events(id INTEGER PRIMARY KEY,campaign_id INT,game_date TEXT,event_type TEXT,title TEXT,body TEXT,visible INT,date_kind TEXT);
            CREATE TABLE world_history_events(id INTEGER PRIMARY KEY,campaign_id INT,game_date TEXT,event_type TEXT,title TEXT,body TEXT,visible INT,date_kind TEXT);
            CREATE TABLE ship_fleet_events(id INTEGER PRIMARY KEY,campaign_id INT,game_date TEXT,event_type TEXT,title TEXT,body TEXT,visible INT,date_kind TEXT);
        ''')
        con.execute('INSERT INTO campaigns VALUES(4,?,?,?,?)',('Example Commonwealth','2200.01.01','2203.04.01',str(archive)))
        con.execute('INSERT INTO campaigns VALUES(5,?,?,?,?)',('Other Empire','2200.01.01','2203.04.01',str(archive)))
        con.execute("INSERT INTO leader_career_events VALUES(1,4,'2203.04.01','leader_death_recorded','Joan died','Confirmed death notification',1,'exact_save_field')")
        con.execute("INSERT INTO leader_career_events VALUES(2,5,'2203.04.01','leader_death_recorded','PRIVATE LEAK','Other realm',1,'exact_save_field')")
        con.execute("INSERT INTO politics_history_events VALUES(3,4,'2203.04.01','ruler','New administration','Succession',1,'first_observed')")
        con.execute("INSERT INTO politics_history_events VALUES(4,4,'2203.04.01','technical','DO NOT SHOW','Hidden',0,'first_observed')")
        for num,date,pop,tcount,count in [(1,'2200.01.01',500,1,1),(2,'2201.01.01',750,2,2),(3,'2201.01.01',890,3,3),(4,'2203.04.01',1000,4,4)]:
            source=archive/f'ironman-{num}.sav';source.write_bytes(('fixture save '+str(num)).encode());st=source.stat();sha=hashlib.sha256(source.read_bytes()).hexdigest()
            components={'worlds': {'version':2,'data':{'game_date':date,'player_country_id':0,'worlds':{'7':{'name':'Unity','system_name':'Deneb','owner_id':0,'population':pop,'designation_name':'Capital'}}}},
                        'technology':{'version':1,'data':{'game_date':date,'technologies':{str(i):{} for i in range(tcount)}}},
                        'ship_fleet':{'version':2,'data':{'game_date':date,'ships':{str(i):{} for i in range(count*2)},'fleets':{str(i):{} for i in range(count)}}},
                        'leaders':{'version':5,'data':{'game_date':date,'leaders':{'14':{'name':'Ada','leader_class':'official','traits':['a'], 'trait_names':['Cautious'],'is_ruler':True,'council_role_name':'Head of State'},'15':{'name':'Joan','leader_class':'scientist','trait_names':['Meticulous'],'council_role_name':'Head of Research'}}}}}
            cache={'cache_schema_version':1,'source_sha256':sha,'archive_size':st.st_size,'archive_mtime_ns':st.st_mtime_ns,'components':components}
            (archive/'.historian_cache'/(sha+'.json')).write_text(json.dumps(cache))
            con.execute('INSERT INTO snapshots VALUES(?,?,?,?,?,?,?,1)',(num,4,num,date,sha,source.name,str(source)))
            con.execute('INSERT INTO politics_states(campaign_id,snapshot_id,state_json) VALUES(4,?,?)',(num,json.dumps({'ruler_id':14,'ruler_name':'Ada','government_type':'gov_military_dictatorship','authority':'auth_dictatorial','ethics':['ethic_militarist'],'civics':['civic_nationalistic_zeal']})))
            if num==1:
                con.execute('INSERT INTO snapshots VALUES(40,5,1,?,?,?,?,1)',(date,sha,source.name,str(source)))
            if num != 4: # latest civic evidence intentionally missing; no older -> latest projection
                pass
        con.commit()
    civic = archive / 'Civic_Frontier_History.sqlite3'
    with sqlite3.connect(civic) as con:
        con.execute('CREATE TABLE observations(sha256 TEXT,game_date TEXT,payload TEXT,parser_version INT)')
        with sqlite3.connect(db) as hist:
            for number,sha,date in hist.execute('SELECT id,sha256,game_date FROM snapshots WHERE campaign_id=4 ORDER BY id'):
                payload={'date':date,'stations':{str(i):{'role':'starbase','system_id':i,'system':'Region'} for i in range(number)},'discovered_systems':{str(i):'System' for i in range(number+2)}}
                con.execute('INSERT INTO observations VALUES(?,?,?,1)',(sha,date,json.dumps(payload)))
        con.commit()
    return db, archive


def main():
    with tempfile.TemporaryDirectory(prefix='stellaris_dash_') as tmp:
        db,archive=create_fixture(Path(tmp));before=db.read_bytes()
        doc=dashboard_data(db,4,force=True)
        assert doc['empire']=='Example Commonwealth'
        assert doc['latest_date']=='2203.04.01'
        assert len(doc['series'])==4
        assert [p['population'] for p in doc['series']]==[500,750,890,1000],doc['series']
        assert doc['current']['leaders']==2 and doc['current']['fleets']==4
        assert doc['current']['controlled_systems']==4 and doc['current']['known_systems']==6
        assert doc['people']['ruler']['name']=='Ada' and doc['people']['council'][0]['name']=='Joan'
        assert any(e['title']=='Joan died' for e in doc['events'])
        assert all('PRIVATE LEAK' not in str(e) and 'DO NOT SHOW' not in str(e) for e in doc['events'])
        # Corrupt a single cache: latest figures must be unavailable, not previous-save values.
        with sqlite3.connect(db) as con:
            sha=con.execute('SELECT sha256 FROM snapshots WHERE id=4').fetchone()[0]
        cache=archive/'.historian_cache'/(sha+'.json')
        payload=json.loads(cache.read_text());payload['archive_size']+=1;cache.write_text(json.dumps(payload))
        missing=dashboard_data(db,4,force=True)
        assert missing['current']['population'] is None and missing['current']['ships'] is None
        assert missing['current']['stations']==4  # independent Civic ledger unaffected
        assert missing['coverage']['core_unavailable']==1
        # Only read operations to the user's DB; untouched bytes & integrity.
        assert db.read_bytes()==before
        with sqlite3.connect(db) as con:
            assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert doc['current']['technologies']==4
        print('v0.0.84: timeline sources, same-date saves, no cross-campaign leakage, damaged cache refusal, sidecar independence and read-only integrity: PASS')

if __name__=='__main__':main()
