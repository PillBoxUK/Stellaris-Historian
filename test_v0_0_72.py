"""v0.0.72 regression: SQLite-only Empire Archive, source provenance and browser UX."""
from __future__ import annotations

from pathlib import Path
import shutil
import json
import re
from tempfile import TemporaryDirectory
from unittest.mock import patch

from historian.db import Database, utc_now
from historian.empire_archive import (
    build_empire_archive_data, empire_archive_path, render_empire_archive,
)

with TemporaryDirectory() as directory:
    root = Path(directory)
    archive = root / 'Commonwealth of Man'
    archive.mkdir()
    db = Database(root / 'data' / 'historian.db')
    cid = db.create_campaign('demo', 'game', 'ironman.sav', '<Test & Empire>', '4.0', str(archive), '2200.01.01')
    db.update_campaign(cid, '<Test & Empire>', '4.0', '2210.04.01')
    now = utc_now()
    with db.connect() as con:
        con.executemany('''INSERT INTO snapshots(campaign_id,kind,game_date,sha256,archive_filename,archive_path,captured_utc,processed)
                               VALUES(?,'periodic',?,?,?,?,?,?)''', [
            (cid,'2200.01.01','aa','ironman-1.sav',str(archive/'ironman-1.sav'),now,1),
            (cid,'2210.04.01','bb','ironman-2.sav',str(archive/'ironman-2.sav'),now,0),
        ])
        snap_id=con.execute('SELECT id FROM snapshots WHERE processed=1').fetchone()[0]
        unprocessed=con.execute('SELECT id FROM snapshots WHERE processed=0').fetchone()[0]
        con.execute('''INSERT INTO history_entries(campaign_id,snapshot_id,game_date,entry_type,title,body,created_utc)
                       VALUES(?,?,'2200.01.01','opening','Empire founded','Opening evidence',?)''',(cid,snap_id,now))
        con.execute('''INSERT INTO history_entries(campaign_id,snapshot_id,game_date,entry_type,title,body,created_utc)
                       VALUES(?,?,'2210.04.01','opening','Should not appear','Unprocessed source',?)''',(cid,unprocessed,now))
        con.execute('''INSERT INTO leader_registry(campaign_id,leader_id,first_seen_date,last_seen_date,name,leader_class,status)
                       VALUES(?,7,'2200.01.01','2210.04.01','Captain </script> dangerous','commander','present')''',(cid,))
        con.execute('''INSERT INTO leader_career_events(campaign_id,event_key,game_date,event_type,leader_id,title,body,visible,created_utc)
                       VALUES(?,'event-1','2204.04.01','leader_entered_service',7,'Entered service','Observed first service',1,?)''',(cid,now))
        con.execute('''INSERT INTO leader_career_events(campaign_id,event_key,game_date,event_type,leader_id,title,body,visible,created_utc)
                       VALUES(?,'event-2','2205.04.01','leader_missing_unconfirmed',7,'Missing','Not death verified',0,?)''',(cid,now))
        con.execute('''INSERT INTO world_registry(campaign_id,planet_id,first_seen_date,last_seen_date,name,latest_population,status)
                       VALUES(?,55,'2200.01.01','2210.04.01','New London',83,'observed')''',(cid,))
        con.execute('''INSERT INTO world_history_events(campaign_id,event_key,game_date,event_type,planet_id,title,body,visible,created_utc)
                       VALUES(?,'world-1','2203.04.01','colony_observed',55,'Colony observed','Colony event first observed',1,?)''',(cid,now))
        con.execute('''INSERT INTO fleet_registry(campaign_id,fleet_id,first_seen_date,last_seen_date,name,ship_class,status)
                       VALUES(?,9,'2201.01.01','2210.04.01','Task Force 9','corvette','observed')''',(cid,))
        con.execute('''INSERT INTO ship_registry(campaign_id,ship_id,first_seen_date,last_seen_date,name,ship_type,status)
                       VALUES(?,15,'2201.01.01','2210.04.01','CNS Prospect','corvette','observed')''',(cid,))
        con.execute('''INSERT INTO ship_fleet_events(campaign_id,event_key,game_date,event_type,fleet_id,title,body,visible,created_utc)
                       VALUES(?,'fleet-1','2204.01.01','fleet_observed',9,'Fleet assembled','Seen at archive',1,?)''',(cid,now))
        con.execute('''INSERT INTO politics_history_events(campaign_id,event_key,game_date,category,event_type,title,body,visible,created_utc)
                       VALUES(?,'dipl-1','2207.01.01','diplomacy','relations_observed','New contact','Communications first retained',1,?)''',(cid,now))
    with patch('historian.save_reader.read_save_texts',side_effect=AssertionError('save parsed')):
        data=build_empire_archive_data(db,cid)
        assert data['campaign']['archived']==2 and data['campaign']['processed']==1
        assert data['counts']['people']=={'published':1,'technical':1}
        assert len(data['registry']['people'])==1
        assert data['registry']['worlds'][0]['fields'][1]==['Last recorded','2210.04.01']
        assert data['registry']['ships'][0]['name']=='CNS Prospect'
        assert any(e['title']=='New contact' for e in data['events'])
        assert not any(e['title']=='Should not appear' for e in data['events'])
        assert any(e.get('subject_kind')=='fleets' and e['subject_id']=='9' for e in data['events'])
        path=render_empire_archive(db,cid)
        assert path==empire_archive_path(db,cid)
        html=path.read_text(encoding='utf-8')
        assert 'Captain </script> dangerous' not in html
        assert 'Captain \\u003c/script\\u003e dangerous' in html
        assert 'Source:' in html and 'Export JSON' in html
        assert 'No screenshots' in html
        assert '2210.04.01' in html
        assert 'War Journal' in html
        # Existing HTML survives if a subsequent publication fails.
        with patch('historian.empire_archive.build_empire_archive_data',side_effect=RuntimeError('read failed')):
            try:
                render_empire_archive(db,cid)
            except RuntimeError:
                pass
            else:
                raise AssertionError('render did not fail')
        assert path.read_text(encoding='utf-8')==html
        assert sorted(x.name for x in archive.iterdir())==['Empire_Archive.html']
    print('PASS: SQLite-only history, linked records, privacy, atomic publication, defensive evidence labels')
    # Optional browser interaction check using the installed Chromium when available.
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('SKIP: Chromium browser regression (playwright not installed)')
    else:
        chromium = shutil.which('chromium') or shutil.which('chromium-browser')
        if not chromium:
            print('SKIP: Chromium executable not present in test environment')
        else:
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True,executable_path=chromium,args=['--no-sandbox'])
                page=browser.new_page()
                errors=[]
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.set_content(html,wait_until="load")
                assert page.locator('h1').inner_text()=='<Test & Empire> — Empire Archive'
                assert page.locator('.stat').count()>=6
                page.get_by_role('button',name='Leaders',exact=True).click()
                assert page.get_by_text('Captain </script> dangerous').count()>0
                page.get_by_role('button',name='Inspect history').click()
                assert page.get_by_text('Entered service',exact=True).count()==1
                assert page.get_by_text('Missing',exact=True).count()==0
                page.locator('#technical').check()
                assert page.get_by_text('Missing',exact=True).count()==1
                page.locator('#search').fill('unrelated')
                assert page.get_by_text('No matching records').count()>0
                page.locator('#search').fill('Captain')
                assert page.get_by_text('Captain </script> dangerous').count()>0
                page.get_by_role('button',name='Chronology').click()
                assert page.get_by_text('Should not appear').count()==0
                page.locator('#search').fill('')
                page.get_by_role('button',name='Diplomacy',exact=True).click()
                assert page.get_by_text('New contact').count()==1
                assert not errors,errors
                browser.close()
            print('PASS: Chromium tabs, search, records, technical observations and XSS escaping')

print('ALL v0.0.72 TESTS PASSED')
