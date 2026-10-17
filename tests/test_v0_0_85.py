"""Synthetic v0.0.85 narrative safety and read-only provenance regression suite.

The installed Windows application additionally needs its standard integration
checks. These fixtures do not use user saves or alter the real database.
"""
from __future__ import annotations
import ast
import importlib.util
import io
import sqlite3
import json
import tempfile
from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from historian.publication_names import usable_name, unresolved, publication_assignment, ship_subject


def run():
    assert unresolved('PREFIX_NAME_FORMAT')
    assert unresolved('Science Ship: PREFIX_NAME_FORMAT')
    assert unresolved('[Root.GetName]')
    assert not unresolved('VSC Fierce Hatchling')
    assert usable_name("K'Vara Korik")
    assert not usable_name('PREFIX_NAME_FORMAT')
    assert publication_assignment('Science Ship: PREFIX_NAME_FORMAT') == 'aboard a science vessel whose name is not preserved'
    assert publication_assignment('Planet: Veyra Prime') == 'Planet: Veyra Prime'
    assert publication_assignment('Fleet: PREFIX_NAME_FORMAT') == 'with a fleet whose name is not preserved'
    assert ship_subject('PREFIX_NAME_FORMAT','Science')==('A science ship enters service','a science ship')
    assert ship_subject('VSC Starling','Science')==('VSC Starling enters service','the science ship VSC Starling')

    # The full census integration is covered by test_v0_0_83_1.py. A compact
    # pure-narrative fixture here prevents Commonwealth copy/paste regressions.
    # Import the real module from the application when available; otherwise
    # use the same test-only shim as the annual-census test.
    try:
        from historian.domains.people import CACHE_COMPONENT_NAME
    except ModuleNotFoundError:
        import types
        domains=types.ModuleType('historian.domains');domains.__path__=[]
        people=types.ModuleType('historian.domains.people')
        people.CACHE_COMPONENT_NAME='people';people.CACHE_COMPONENT_VERSION=1
        sys.modules['historian.domains']=domains
        sys.modules['historian.domains.people']=people
    from historian.annual_census import census_prose
    entry={'available':True,'year':'2200','date':'2200.01.01','opening':True,
           'government':'Executive Committee','authority':'Oligarchic','ruler_name':"K'Vara Korik",
           'people':[
               {'name':"K'Vara Korik",'leader_class':'Official','ruler':True,'group':'Ruler','council_office':'','assignment':'','traits':['Spycraft']},
               {'name':'Sakeeri','leader_class':'Scientist','ruler':False,'group':'Council','council_office':'Head of Research','assignment':'aboard a science vessel whose name is not preserved','traits':['Adaptable']},
               {'name':"D'Kheera",'leader_class':'Envoy','ruler':False,'group':'Other service','council_office':'','assignment':'','traits':[]},
           ]}
    text=census_prose(entry,'Veyran Shadow Concord')
    assert 'Commonwealth' not in text and 'PREFIX_NAME_FORMAT' not in text
    assert "K'Vara Korik" in text and 'Spycraft' in text
    assert 'Sakeeri' in text and 'Head of Research' in text
    assert 'an envoy' in text and 'unidentified' not in text
    assert not census_prose({**entry,'available':False},'Veyran Shadow Concord')

    # Confirm timeline source parses and remains structured as a proper HTML
    # historical renderer. Don't require a guessed app bootstrap in a patch-only tree.
    src=(root/'historian/timeline.py').read_text(encoding='utf-8')
    ast.parse(src)
    assert "{world} enters Commonwealth territory" not in src
    assert "'The Commonwealth', value" not in src
    assert 'date_kind=\'processed_snapshot_state\'' in src
    assert 'war-track' in src and 'year-heading' in src and 'timeline' in src

    audit_path=root/'scripts/audit_annals_v0_0_85.py'
    spec=importlib.util.spec_from_file_location('audit_annals',audit_path)
    mod=importlib.util.module_from_spec(spec);assert spec and spec.loader;spec.loader.exec_module(mod)
    with tempfile.TemporaryDirectory() as folder:
        d=Path(folder);db=d/'h.db';arch=d/'archive';arch.mkdir()
        with sqlite3.connect(db) as c:
            c.executescript('CREATE TABLE campaigns(id INTEGER PRIMARY KEY,empire_name TEXT,first_game_date TEXT,latest_game_date TEXT,archive_dir TEXT);'
                            'CREATE TABLE snapshots(id INTEGER PRIMARY KEY,campaign_id INTEGER,game_date TEXT,processed INTEGER);')
            c.execute('INSERT INTO campaigns VALUES (1,?,?,?,?)',('Veyran Shadow Concord','2200.01.01','2202.01.01',str(arch)))
            c.execute('INSERT INTO snapshots VALUES(1,1,?,1)',('2200.01.01',))
            c.execute('INSERT INTO snapshots VALUES(2,1,?,1)',('2201.01.01',))
            c.execute('INSERT INTO snapshots VALUES(3,1,?,0)',('2202.01.01',))
            c.commit()
        before=db.read_bytes()
        report=mod.audit(db,1)
        assert report['processed_saves']==2 and report['unprocessed_saves']==1
        assert report['year_boundaries_without_exact_processed_saves']==['2202.01.01']
        assert report['last_processed_date']=='2201.01.01'
        assert db.read_bytes()==before
    print('PASS v0.0.85: unresolved name guards, Veyran census, neutral imperial terminology, chronology boundary and read-only audit')

if __name__=='__main__':run()
