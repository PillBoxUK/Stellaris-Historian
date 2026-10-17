"""v0.0.75 canonical timeline and safely bounded war-rail regression."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from types import SimpleNamespace as N
import json, re
from historian.timeline import render_timeline, TimelineEvent, _war_spans, _chronicle_voice
from historian.db import Database


def run():
    with TemporaryDirectory() as d:
        root=Path(d)
        db=Database(root/'data.db')
        archive=root/'campaign';archive.mkdir()
        cid=db.create_campaign('test','game','ironman.sav','Commonwealth of Man','4.0',str(archive),'2200.01.01')
        db.update_campaign(cid,'Commonwealth of Man','4.0','2317.01.01')
        enemy_id=93
        war=N(war_id=83886080,name='War 83886080',start_date='2256.02.21',
              player_side='attacker',attacker_war_goal='conquest',defender_war_goal='humiliation',
              attacker_country_ids=(1,),defender_country_ids=(enemy_id,),battles=[])
        snaps=[N(game_date='2256.04.01',wars={war.war_id:war},relation_kill_counters={},fleet_combat_stats={}),
               N(game_date='2278.07.01',wars={war.war_id:war},relation_kill_counters={},fleet_combat_stats={}),
               N(game_date='2278.10.01',wars={},relation_kill_counters={},fleet_combat_stats={})]
        presentation=N(combat_snapshots=snaps)
        spans=_war_spans(presentation,'Commonwealth of Man')
        assert len(spans)==1,spans
        assert spans[0]['start']=='2256.02.21' and spans[0]['last']=='2278.07.01'
        assert spans[0]['first_absent']=='2278.10.01'
        assert 'Hulfiran' not in spans[0]['title'] # no screenshot annotation or guessed name
        events=[TimelineEvent('2256.04.01','Vance Knight Entered Service',
                              'Vance Knight entered service on 2256.04.01.','People',leader_id=13),
                TimelineEvent('2258.10.01','Shields','Shields known by this date.','Technology'),
                TimelineEvent('2278.07.01','Final fight <script>alert(1)</script>',
                              'The outcome is not established.','Combat')]
        with patch('historian.timeline.build_presentation_history',return_value=presentation), \
             patch('historian.timeline._collect_events',return_value=(events,{})):
            path=render_timeline(db,cid)
        html=path.read_text(encoding='utf-8')
        assert 'data-year="2265"' in html and 'data-year="2277"' in html
        assert '<script>alert(1)</script>' not in html
        assert '\\u003cscript\\u003e' in html
        assert 'class="war-track"' in html and 'id="floating"' in html
        assert '/war-journal#war-' in html
        assert 'Source observation: event may have occurred earlier' in html
        assert not re.search(r'no player victory|the record identifies',html,re.I)
        assert '2256.02.21' in html and '2278.10.01' in html
        assert _chronicle_voice('The record identifies Vance Knight as entering service as a commander on 2256.11.16.') == 'Vance Knight entered service as a commander on 2256.11.16.'
        print('PASS: safe source dates, metadata, no manual names, long war-year continuity and escaping')
        try:
            from playwright.sync_api import sync_playwright
            import shutil
            chromium=shutil.which('chromium')
            if chromium:
                with sync_playwright() as pw:
                    browser=pw.chromium.launch(headless=True,executable_path=chromium,args=['--no-sandbox'])
                    page=browser.new_page(viewport={'width':1500,'height':900})
                    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                    page.set_content(html,wait_until='load')
                    page.wait_for_timeout(250)
                    page.screenshot(path='/mnt/data/_qa75_timeline.png')
                    assert page.locator('.war-period').count()==1
                    h=float(page.locator('.war-period').evaluate('(e)=>e.getBoundingClientRect().height'))
                    assert h>1000,h
                    page.locator('.war-period').click(force=True)
                    assert page.locator('#floating').is_visible()
                    assert page.locator('.floating-content a[href="/war-journal#war-83886080"]').count()==1
                    page.locator('#card-flip').click()
                    assert '2278.10.01' in page.locator('#floating-content').inner_text()
                    page.locator('#card-close').click()
                    assert not page.locator('#floating').is_visible()
                    page.locator('.event-open').filter(has_text='Vance Knight').click()
                    assert '/empire-archive?record=people:13' in page.locator('#floating-content').inner_html()
                    page.locator('#card-close').click()
                    page.locator('button[data-filter="People"]').click()
                    assert page.locator('.event:visible').count()==1
                    assert page.locator('.war-period').count()==1
                    assert not errors,errors
                    browser.close()
                print('PASS: Chromium war spans, flip, close, event links, filters, no JS errors')
        except ImportError:
            print('SKIP: Chromium unavailable')

if __name__=='__main__':run();print('ALL v0.0.75 TESTS PASS')
