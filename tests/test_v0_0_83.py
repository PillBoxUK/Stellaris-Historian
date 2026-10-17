"""v0.0.83: safe, standalone checks against a synthetic temp SQLite database.
Run from installation root: python tests/test_v0_0_83.py
"""
from __future__ import annotations
import sqlite3
import tempfile
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from historian.local_database_browser import available_tables,table_rows,schema,select_query,csv_export,readonly_connection
from historian.government_people import government_data,render_government_people


def run():
    with tempfile.TemporaryDirectory() as temp:
        path=Path(temp)/'historian.db'
        with sqlite3.connect(path) as c:
            c.executescript('''CREATE TABLE campaigns(id INTEGER PRIMARY KEY,empire_name TEXT,first_game_date TEXT,latest_game_date TEXT);
            CREATE TABLE leader_registry(leader_id INTEGER,campaign_id INTEGER,first_seen_date TEXT,last_seen_date TEXT,name TEXT,leader_class TEXT,traits TEXT,trait_names TEXT,status TEXT,recruitment_date TEXT,latest_level INTEGER,latest_assignment TEXT,latest_council_role TEXT);
            CREATE TABLE leader_deep_evidence(campaign_id INTEGER,leader_id INTEGER,species_name TEXT,death_date TEXT,death_reason_value TEXT);
            CREATE TABLE leader_career_events(id INTEGER PRIMARY KEY,campaign_id INTEGER,leader_id INTEGER,game_date TEXT,event_type TEXT,title TEXT,body TEXT,confidence TEXT,date_kind TEXT,snapshot_id INTEGER);
            CREATE TABLE politics_states(campaign_id INTEGER,game_date TEXT,snapshot_id INTEGER,state_json TEXT);
            CREATE TABLE politics_history_events(id INTEGER PRIMARY KEY,campaign_id INTEGER,game_date TEXT,event_type TEXT,title TEXT,body TEXT,confidence TEXT,date_kind TEXT,subject_name TEXT);
            CREATE TABLE world_registry(campaign_id INTEGER,planet_id INTEGER,name TEXT);
            CREATE TABLE world_history_events(campaign_id INTEGER,game_date TEXT,event_type TEXT,title TEXT,body TEXT,date_kind TEXT,confidence TEXT,planet_id INTEGER,id INTEGER);
            INSERT INTO campaigns VALUES(4,'Example Commonwealth','2200.01.01','2203.01.01');
            INSERT INTO leader_registry VALUES(123,4,'2200.01.01','2202.01.01','Ada Example','official','["trait"]','["Efficient"]','dead_confirmed','2200.01.01',4,'Planet: Example','Minister of State');
            INSERT INTO leader_deep_evidence VALUES(4,123,'Human','2202.06.04','Died of natural causes');
            INSERT INTO leader_career_events VALUES(1,4,123,'2202.06.04','leader_death_recorded','Ada Example Recorded Dead','Confirmation from a death notice','high','exact_notification_date',8);
            INSERT INTO politics_states VALUES(4,'2200.01.01',1,'{"ruler_id":123,"ruler_name":"Ada Example"}');
            INSERT INTO politics_history_events VALUES(1,4,'2200.01.01','ruler_identity_observed','Opening ruler','Opening state','high','archive_opening','Ada Example');
            INSERT INTO world_registry VALUES(4,20,'Example');
            ''')
        assert len(available_tables(path,4))>=7
        assert table_rows(path,'leader_registry',campaign_id=4,search='Ada')['total']==1
        assert table_rows(path,'leader_registry',campaign_id=3)['total']==0
        assert schema(path,'leader_registry')['columns']
        assert 'Ada Example' in csv_export(path,'leader_registry',4)
        assert select_query(path,'SELECT name FROM leader_registry LIMIT 2')['rows']==[['Ada Example']]
        for command in ('DELETE FROM leader_registry','DROP TABLE leader_registry','PRAGMA writable_schema=ON','WITH x AS (SELECT 1) SELECT * FROM x; DELETE FROM leader_registry'):
            try:select_query(path,command)
            except (ValueError,sqlite3.Error):pass
            else:raise AssertionError('Non-read-only SQL accepted: '+command)
        data=government_data(path,4)
        assert len(data['leaders'])==1 and data['confirmed_deaths']==1
        assert data['leaders'][0]['traits']==['Efficient']
        assert data['rulers'][0]['name']=='Ada Example'
        rendered=render_government_people(path,4)
        assert '2202.06.04' in rendered and 'Died of natural causes' in rendered
        with readonly_connection(path) as conn:
            try:conn.execute('DELETE FROM leader_registry')
            except sqlite3.Error:pass
            else:raise AssertionError('Database connection allowed a write')
        assert sqlite3.connect(path).execute('SELECT COUNT(*) FROM leader_registry').fetchone()[0]==1
    print('PASS v0.0.83 - government profiles, confirmed death, traits, SQLite table/schema/CSV/SELECT, campaign isolation, write protection')


if __name__=='__main__':run()
