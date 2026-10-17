"""v0.0.73: evidence-only interactive chronology, controls and provenance."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import json
import shutil

from historian.db import Database, utc_now
from historian.historical_events import HistoricalEvent
from historian.timeline import TimelineEvent
from historian.interactive_timeline import build_interactive_timeline_data, render_interactive_timeline


def sample():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        archive = root / 'test-campaign'
        archive.mkdir()
        db = Database(root / 'historian.db')
        cid = db.create_campaign('demo', 'game', 'ironman.sav', 'Commonwealth <test>', '4.0', str(archive), '2200.01.01')
        db.update_campaign(cid, 'Commonwealth <test>', '4.0', '2300.10.01')
        now = utc_now()
        with db.connect() as con:
            con.execute('''INSERT INTO snapshots(campaign_id,kind,game_date,sha256,archive_filename,archive_path,captured_utc,processed)
                VALUES(?,'periodic','2200.01.01','aaa','ironman-1.sav','no-actual-file',?,1)''',(cid,now))
            con.execute('''INSERT INTO world_history_events(campaign_id,event_key,game_date,event_type,planet_id,title,body,visible,created_utc)
                VALUES(?,'col-1','2220.04.01','colony_founded',55,'Keso settled','First preserved colonisation record',1,?)''',(cid,now))
            con.execute('''INSERT INTO politics_history_events(campaign_id,event_key,game_date,category,event_type,title,body,visible,created_utc)
                VALUES(?,'p-1','2212.04.01','politics','council_agenda_state_changed','Imperial council agenda changed','Internal government council',1,?)''',(cid,now))
            con.execute('''INSERT INTO politics_history_events(campaign_id,event_key,game_date,category,event_type,title,body,visible,created_utc)
                VALUES(?,'p-2','2212.07.01','politics','council_agenda_progress_changed','Council progress','Telemetry',0,?)''',(cid,now))
        curated=[TimelineEvent('2231.09.04','The Fighting at Lawam','Retained fleet evidence; outcome unverified','Combat',90)]
        events=[HistoricalEvent('2207.01.01','technology','tech_first_observed','Destroyers','First observed as researched','high','first_observed','technology_history',72),
                HistoricalEvent('2211.01.01','technology','tech_first_observed','Quantum Computing </script>','Retained <evidence>','high','first_observed','technology_history',70)]
        contacts={'events':[{'game_date':'2225.07.01','event_type':'first_contact_completed','title':'First contact completed',
                              'body':'Mutual saved completion markers','date_kind':'between_snapshots','confidence':'high','visible':True,'contact_id':4},
                             {'game_date':'2250.07.01','event_type':'first_contact_case_recorded','title':'Unverified counterpart',
                              'body':'Technical case only','date_kind':'first_observed','visible':False}]}
        with patch('historian.interactive_timeline.build_presentation_history',return_value=SimpleNamespace(events=events)),\
             patch('historian.interactive_timeline._collect_events',return_value=(curated,{})),\
             patch('historian.interactive_timeline.load_first_contact_history',return_value=contacts),\
             patch('historian.save_reader.read_save_texts',side_effect=AssertionError('No Ironman read allowed')):
            data=build_interactive_timeline_data(db,cid)
            assert any(e['group']=='space' and e['date']=='2231.09.04' for e in data['events'])
            assert any(e['group']=='colonies' for e in data['events'])
            assert any(e['group']=='contacts' for e in data['events'])
            assert any(e['group']=='internal_council' for e in data['events'])
            assert not any(e['group']=='galactic' for e in data['events'])
            assert not any(e['group']=='federations' for e in data['events'])
            assert not any(e['group']=='ground' for e in data['events'])
            assert len([e for e in data['events'] if e['group']=='technology'])==2
            assert any(not e['visible'] for e in data['events'])
            assert data['campaign']['name']=='Commonwealth <test>'
            output=render_interactive_timeline(db,cid)
            html=output.read_text(encoding='utf-8')
            assert '<test>' not in html and 'Quantum Computing </script>' not in html
            assert 'Commonwealth &lt;test&gt;' in html and '\\u003c/script\\u003e' in html
            assert 'Interactive_Timeline.html' in str(output)
            assert 'No screenshots' in html
            print('PASS: compiled evidence data, politics-council distinction, raw save isolation, HTML escaping')
            try:
                from playwright.sync_api import sync_playwright
            except ImportError:
                print('SKIP: Playwright not installed')
                return
            chromium=shutil.which('chromium') or shutil.which('chromium-browser')
            if not chromium:
                print('SKIP: Chromium unavailable')
                return
            with sync_playwright() as pw:
                browser=pw.chromium.launch(headless=True,executable_path=chromium,args=['--no-sandbox'])
                page=browser.new_page()
                errors=[]
                page.on('pageerror',lambda err: errors.append(str(err)))
                page.set_content(html,wait_until='load')
                assert 'Commonwealth <test>' in page.locator('h1').inner_text()
                assert page.locator('#current-date').inner_text()=='2207.01.01'
                assert 'Destroyers' in page.locator('#detail').inner_text()
                page.locator('#next').click()
                assert page.locator('#current-date').inner_text()=='2211.01.01'
                page.locator('#date-box').fill('2225.07.01')
                page.locator('#date-go').click()
                assert page.locator('#current-date').inner_text()=='2225.07.01'
                page.locator('#event-list .event').filter(has_text='First contact completed').click()
                assert 'Mutual saved completion markers' in page.locator('#detail').inner_text()
                assert 'between_snapshots' in page.locator('#detail').inner_text()
                page.locator('#filters input[value="contacts"]').uncheck()
                assert 'First contact completed' not in page.locator('#event-list').inner_text()
                page.locator('#search').fill('Quantum')
                assert 'Quantum Computing </script>' in page.locator('#detail').inner_text()
                page.locator('#search').fill('')
                page.locator('#technical').check()
                page.locator('#date-box').fill('2250.07.01')
                page.locator('#date-go').click()
                page.locator('#filters input[value="contacts"]').check()
                assert 'Unverified counterpart' in page.locator('#event-list').inner_text()
                assert 'Federations not independently established' in page.locator('#coverage').inner_text()
                assert 'Galactic Community not independently established' in page.locator('#coverage').inner_text()
                assert not errors,errors
                browser.close()
            print('PASS: Chromium scrub navigation, date jump, first contacts, filters, search, technical evidence, provenance')

if __name__=='__main__':
    sample()
    print('ALL v0.0.73 TESTS PASSED')
