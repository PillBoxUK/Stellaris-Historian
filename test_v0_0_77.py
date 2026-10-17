"""v0.0.77 timeline narrative, source bounds, dynamic war bars and approved design."""
from __future__ import annotations
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from types import SimpleNamespace as N
import re, json, shutil
from historian.db import Database
from historian.historical_events import HistoricalEvent
from historian.timeline import (_leader_prose,_ship_milestones,_combat_timeline_event,
                               _expansion_prose,_long_date,render_timeline,TimelineEvent)

def row(date,cat,typ,title,desc,importance=75,attrs=(),kind='exact_save_field'):
    return HistoricalEvent(date,cat,typ,title,desc,'high',kind,'leader_history',importance,attrs)

def run():
    hong=row('2200.05.03','people','leader_entered_service','Hong Lin Entered Service',
      'Stellaris records Hong Lin as entering service as a scientist on 2200.05.03. The first surviving archived state containing this leader is dated 2200.07.01. By 2200.07.01, Hong Lin was assigned to the science ship Enigma.',attrs=(('leader_id','88'),))
    hers=_leader_prose(hong,'Commonwealth of Man',[])
    assert len(hers)==2, hers
    assert hers[0].game_date=='2200.05.03' and 'scientific service' in hers[0].body
    assert 'Enigma' not in hers[0].body
    assert hers[1].game_date=='2200.07.01' and 'Enigma' in hers[1].body
    assert '2200.05.03' not in hers[1].body
    assert '2200.07.01' not in hers[1].body
    ruler=row('2302.07.01','people','leader_became_ruler','Eve Featherstone Became Ruler','By 2302.07.01, Eve Featherstone was recorded as ruler.')
    rulers=_leader_prose(ruler,'Commonwealth of Man',[])
    assert rulers[0].title=='Eve Featherstone assumes the leadership',rulers
    assert 'Became Ruler' not in rulers[0].body
    missing=row('2243.01.01','people','leader_missing_unconfirmed','Miguel Ortiz Left the Surviving Record',
      'Miguel Ortiz no longer present by 2243.01.01.',kind='first_observed')
    assert 'fate is unknown' in _leader_prose(missing,'Commonwealth of Man',[])[0].body
    combat=row('2296.12.18','combat','combat_episode','Aesir campaign','Raw combat evidence',90,
         (('systems','Aesir, Qifitar'),('opposing_countries','Hulfiran United Stars'),
         ('player_fleets','Strike Force Titan, Strike Force Cerberus'),('commanders','Lin Zhao, Helmuth Baumann'),
         ('end_date','2297.04.03'),('evidence_kind','direct_anchored'),
         ('initial_player_losses','1'),('initial_opposing_losses','3')),'first_observed')
    battle=_combat_timeline_event(combat,'Commonwealth of Man')
    assert '18th of December, 2296' in battle.body
    assert 'Lin Zhao' in battle.body and 'Helmuth Baumann' in battle.body
    assert '2297' in battle.body and '1 Commonwealth of Man ship lost' in battle.body
    assert not re.search('retreated|disengaged|returned|fled|player|Historian|game',battle.body,re.I),battle.body
    assert 'independently proven' in battle.evidence
    founding=row('2287.09.17','expansion','colony_founded','Fellix Founded',
      'The record identifies the colony of Fellix in the Fellix system as founded on 2287.09.17. The first surviving archived state containing the colony is dated 2287.10.01.')
    colony=_expansion_prose(founding)
    assert colony.body=='A new settlement took shape on Fellix, in the Fellix system.'
    assert 'not independently prove' in colony.evidence
    assert _long_date('2296.12.18')=='18th of December, 2296'
    assert _long_date('2257.02.13')=='13th of February, 2257'

    class ShipDB:
        def ship_registry(self,_):return [dict(ship_id=42,opening_ship_type='Battlecruiser',ship_type='Battlecruiser',
          opening_name='CSS Resolute',name='CSS Resolute',first_seen_date='2266.07.01',opening_construction_date='2266.04.19',
          construction_date='2266.04.19',opening_fleet_name='Strike Force Titan',opening_commander_name='Lin Zhao')]
        def campaign(self,_):return {'first_game_date':'2200.01.01'}
    ships=_ship_milestones(ShipDB(),1)
    assert len(ships)==2,ships
    assert ships[0].game_date=='2266.04.19' and 'Strike Force' not in ships[0].body
    assert ships[1].game_date=='2266.07.01' and 'Strike Force Titan' in ships[1].body
    assert 'under Lin Zhao' in ships[1].body
    assert all('on 2266.04.19' not in e.body for e in ships)

    with TemporaryDirectory() as temp:
        root=Path(temp)
        db=Database(root/'history.sqlite')
        folder=root/'campaign';folder.mkdir()
        cid=db.create_campaign('demo','game','ironman.sav','Commonwealth of Man','4.0',str(folder),'2200.01.01')
        db.update_campaign(cid,'Commonwealth of Man','4.0','2325.11.07')
        war=dict(id=67108865,title='War of Conquest against Hulfiran United Stars',start='2256.02.21',
                 last='2278.07.01',first_observed='2256.04.01',first_absent='2278.10.01',details='First absent by 2278.10.01')
        rows=hers+rulers+[battle,colony]+ships
        with patch('historian.timeline.build_presentation_history',return_value=N(events=[])),\
             patch('historian.timeline._collect_events',return_value=(rows,{})),\
             patch('historian.timeline._war_spans',return_value=[war]):
            html_path=render_timeline(db,cid)
        html=html_path.read_text(encoding='utf-8')
        assert 'id="year-2258"' in html and 'id="year-2277"' in html
        assert '<div class="war-track"' in html
        assert 'THE IMPERIAL ANNALS · A CIVILISATION REMEMBERED' in html
        assert 'id="jump-year"' in html
        assert 'class="floating"' in html
        assert 'war-journal#war-' in html
        assert 'Hong Lin began serving aboard the science ship Enigma' in html
        assert 'style="display:' not in html
        from playwright.sync_api import sync_playwright
        if shutil.which('chromium'):
            with sync_playwright() as pw:
                browser=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox'])
                page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
                errors=[];page.on('pageerror',lambda x:errors.append(str(x)))
                page.set_content(html,wait_until='load');page.wait_for_timeout(260)
                assert page.locator('.war-period').count()==1
                height=page.locator('.war-period').evaluate('(e)=>e.getBoundingClientRect().height')
                assert height>600,height
                assert page.locator('.event').count()==len(rows)+1,(page.locator('.event').count(), len(rows),[(x.game_date,x.title) for x in rows])
                assert page.locator('button[data-filter="Command"]').count()==1
                assert page.locator('body').evaluate('(e)=>getComputedStyle(e).backgroundColor')=='rgb(248, 244, 235)'
                page.screenshot(path='/mnt/data/Stellaris_Historian_v0.0.77_Timeline_Preview.png',full_page=False)
                page.locator('button[data-event="0"]').click(force=True)
                assert page.locator('#floating').is_visible()
                page.locator('#card-flip').click()
                assert 'Dating and evidence' in page.locator('#floating-content').inner_text()
                page.locator('#card-close').click()
                page.locator('.war-period').click(force=True)
                assert 'War chronology' not in page.locator('#floating-content').inner_text()
                assert page.locator('.detail-link[href="/war-journal#war-67108865"]').count()==1
                page.locator('#card-close').click()
                page.locator('button[data-filter="People"]').click()
                assert page.locator('.event:visible').count() == len([r for r in rows if r.category=='People'])
                page.locator('button[data-filter="All"]').click()
                page.locator('#jump-year').fill('2296');page.locator('#year-go').click()
                assert not errors,errors
                page.set_viewport_size({'width':420,'height':900});page.wait_for_timeout(120)
                assert page.locator('.chronicle').evaluate('(x)=>x.scrollWidth<=innerWidth')
                browser.close()
    print('PASS: exact vs first-observed separate dates; natural combat, leadership, ships, colony; archive provenance; dynamic paper UI, war spans, card flips, year jump, narrow viewport')

if __name__=='__main__':run()
