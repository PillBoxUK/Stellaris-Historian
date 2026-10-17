"""v0.0.74: Time Machine, chaptered Scribes and evidence provenance regression."""
from __future__ import annotations
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from historian.db import Database, utc_now
from historian.time_machine import build_time_machine_data, render_time_machine
from historian.scribes import render_scribes_journal, render_scribes_pdf


def run():
    with TemporaryDirectory() as folder:
        root=Path(folder); archive=root/'campaign';archive.mkdir()
        db=Database(root/'historian.db')
        cid=db.create_campaign('example','game','ironman.sav','Commonwealth <script>alert(1)</script>','4.0',str(archive),'2200.01.01')
        db.update_campaign(cid,'Commonwealth <script>alert(1)</script>','4.0','2302.07.01')
        now=utc_now()
        with db.connect() as con:
            con.executemany('''INSERT INTO snapshots(campaign_id,kind,game_date,sha256,archive_filename,archive_path,captured_utc,processed)
                 VALUES(?,'periodic',?,?,?,?,?,?)''',[(cid,'2200.01.01','aa','save-a.sav','not-real',now,1),
                  (cid,'2302.07.01','bb','save-b.sav','not-real',now,1),
                  (cid,'2302.07.01','cc','save-c.sav','not-real',now,1),
                  (cid,'2302.10.01','dd','unprocessed.sav','not-real',now,0)])
            political_snapshot=con.execute("SELECT id FROM snapshots WHERE sha256='cc'").fetchone()[0]
            con.execute('''INSERT INTO politics_states(campaign_id,snapshot_id,game_date,state_json,created_utc)
                 VALUES(?,?,?,?,?)''',(cid,political_snapshot,'2302.07.01',json.dumps({"ruler_name":"Eve Featherstone","government_type":"Military Dictatorship","authority":"dictatorial","ethics":["Militarist"],"civics":["Nationalistic Zeal"],"traditions":["tr_supremacy"],"relations":{"8":{"country_name":"Hulfiran United Stars"}}}),now))
            con.execute('''INSERT INTO leader_registry(campaign_id,leader_id,first_seen_date,last_seen_date,name,leader_class,status)
                 VALUES(? ,7,'2200.01.01','2302.07.01','Test Leader', 'scientist','present')''',(cid,))
            con.execute('''INSERT INTO world_registry(campaign_id,planet_id,first_seen_date,last_seen_date,name,colonize_date,status)
                 VALUES(?,22,'2300.04.01','2302.07.01','Captured World','2220.01.01','present')''',(cid,))
            con.execute('''INSERT INTO politics_history_events(campaign_id,event_key,game_date,category,event_type,title,body,visible,created_utc)
                 VALUES(?,'pol-1','2302.07.01','politics','council_agenda_state_changed','Imperial agenda advanced','Internal council, not Galactic Council',1,?)''',(cid,now))
        timeline={"events":[
            {"date":"2200.01.01","group":"empire","title":"The surviving record opens","body":"Opening record","kind":"opening","visible":True,"source":"timeline","date_kind":"exact_save_field","confidence":"high"},
            {"date":"2302.07.01","group":"technology","title":"Research observed <script>evil</script>","body":"First observed","kind":"research","visible":True,"source":"technology_history","date_kind":"first_observed","confidence":"high"},
            {"date":"2302.07.01","group":"internal_council","title":"Imperial agenda advanced","body":"Not galactic","kind":"council","visible":True,"source":"politics","date_kind":"first_observed","confidence":"high"},
            {"date":"2302.07.01","group":"diplomacy","title":"Unpublished diplomacy","body":"Technical","kind":"relation","visible":False,"source":"politics","date_kind":"first_observed","confidence":"low"},
        ]}
        with patch('historian.time_machine.build_interactive_timeline_data',return_value=timeline), \
             patch('historian.save_reader.read_save_texts',side_effect=AssertionError('No raw saves')):
            data=build_time_machine_data(db,cid)
            assert len(data['stops'])==2,data['stops']
            assert data['stops'][-1]['file']=='save-c.sav'
            assert 'unprocessed.sav' not in json.dumps(data)
            assert any(e['category']=='technology' for e in data['events'])
            assert any(e['category']=='internal_council' for e in data['events'])
            assert not any(e['category']=='galactic' for e in data['events'])
            assert data['political_states'][0]['ruler']=='Eve Featherstone'
            assert data['political_states'][0]['relation_count']==1
            assert data['registry']['worlds'][0]['first']=='2300.04.01'
            assert not any('latest_population' in str(item) for item in data['registry']['worlds'])
            output=render_time_machine(db,cid)
            html=output.read_text(encoding='utf-8')
            assert '<script>evil</script>' not in html
            assert '\\u003cscript\\u003e' in html
            assert 'Commonwealth &lt;script&gt;' in html
            assert 'Time Machine' in html and 'Internal Council' in html
            assert 'No screenshots' in html
            print('PASS: date de-dup, latest-day same date, pending saves excluded, escaping, data provenance')
            try:
                from playwright.sync_api import sync_playwright
                import shutil
                chromium=shutil.which('chromium') or shutil.which('chromium-browser')
                if not chromium: raise ImportError
            except ImportError:
                print('SKIP: browser not installed')
            else:
                with sync_playwright() as pw:
                    browser=pw.chromium.launch(headless=True,executable_path=chromium,args=['--no-sandbox'])
                    page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                    page.set_content(html,wait_until='load')
                    assert page.locator('#date').inner_text()=='2302.07.01'
                    assert page.locator('#count-worlds').inner_text()=='1'
                    assert page.locator('#ruler').inner_text()=='Eve Featherstone'
                    assert 'Research observed <script>evil</script>' in page.locator('#event-list').inner_text()
                    page.locator('#topic-list button[data-c="technology"]').click()
                    assert 'Research observed' in page.locator('#event-list').inner_text()
                    page.locator('#prev').click()
                    assert page.locator('#date').inner_text()=='2200.01.01'
                    assert page.locator('#count-worlds').inner_text()=='0'
                    assert page.locator('#ruler').inner_text()=='—'
                    page.locator('#date-label').fill('2302.07.01');page.locator('#date-go').click()
                    assert page.locator('#date').inner_text()=='2302.07.01'
                    page.locator('#topic-list button[data-c="all"]').click()
                    page.locator('#technical').check()
                    assert 'Unpublished diplomacy' in page.locator('#event-list').inner_text()
                    assert not errors,errors
                    browser.close()
                print('PASS: Chromium read-only time scrubbing, category filtering, date jump, technical evidence')

        # These chapters must use general empire wording, not a stale faction name.
        # A missing starting raw .sav is allowed; scribe origin narrative is optional.
        with patch('historian.scribes.build_presentation_history') as presentation:
            presentation.return_value.combat_snapshots=[]
            presentation.return_value.ship_snapshots=[]
            presentation.return_value.technology_snapshots=[]
            presentation.return_value.events=[]
            with patch('historian.scribes._opening_origin_lore',return_value=None):
                chapter=render_scribes_journal(db,cid)
                page=chapter.read_text(encoding='utf-8')
                assert 'The Chambers of Power' in page
                assert 'No intervening ownership or construction is invented' in page
                assert 'signed in that ruler' not in page.lower()
                assert 'Convocation' not in page
                assert 'chapter-politics' in page and 'Night reading' in page
                assert 'The Chronicle of Commonwealth &lt;script&gt;' in page
                from playwright.sync_api import sync_playwright
                import shutil
                binary=shutil.which('chromium') or shutil.which('chromium-browser')
                if binary:
                    with sync_playwright() as pw:
                        browser=pw.chromium.launch(headless=True,executable_path=binary,args=['--no-sandbox']); pg=browser.new_page()
                        errors=[];pg.on('pageerror',lambda e:errors.append(str(e)))
                        pg.set_content(page,wait_until='load')
                        pg.locator('#reading-mode').click()
                        assert 'dark-reading' in pg.locator('.book').get_attribute('class')
                        assert pg.locator('.contents li').count()==9
                        pg.locator('.contents a[href="#chapter-politics"]').click()
                        assert pg.evaluate('location.hash')=='#chapter-politics'
                        assert not errors,errors
                        browser.close()
                    print('PASS: nine-chapter Scribes links and night reading browser test')
                pdf=render_scribes_pdf(db,cid)
                assert pdf.exists() and pdf.stat().st_size>3000
                import shutil
                shutil.copy2(pdf, '/mnt/data/_qa74_scribes_demo.pdf')
                print('PASS: refreshed Scribes standalone PDF created',pdf.stat().st_size,'bytes')

if __name__=='__main__':run();print('ALL v0.0.74 TESTS PASSED')
