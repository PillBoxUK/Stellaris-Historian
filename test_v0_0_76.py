"""v0.0.76 date-provenance, story coverage, CSS cache and layout regression."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import re
import json
from historian.timeline import _ship_milestones, _service_narrative, _empire_voice_states, _collect_events
from historian.historical_events import HistoricalEvent

class DB:
    def __init__(self):
        self.ships=[dict(ship_id=42,opening_ship_type='Battlecruiser',ship_type='Battlecruiser',
                         opening_name='CSS Resolute',name='CSS Resolute',first_seen_date='2266.07.01',
                         opening_construction_date='2266.04.19',construction_date='2266.04.19',
                         opening_fleet_name='Strike Force Titan',opening_commander_name='Lin Zhao',status='present'),
                    dict(ship_id=43,opening_ship_type='Battleship',ship_type='Battleship',
                         opening_name='CSS Valiant',name='CSS Valiant',first_seen_date='2272.10.01',
                         opening_construction_date=None,construction_date=None,
                         opening_fleet_name='Strike Force Cerberus',opening_commander_name='Helmuth Baumann',status='present')]
    def ship_registry(self, campaign_id):return self.ships
    def politics_states(self,campaign_id):return [dict(game_date='2250.01.01',state_json=json.dumps({'government_type':'Military Dictatorship','ethics':['ethic_militarist']}))]
    def campaign(self,campaign_id):return dict(empire_name='Commonwealth of Man',first_game_date='2200.01.01',latest_game_date='2274.01.01')
    def leader_registry(self,cid):return []
    def world_registry(self,cid):return []

def run():
    db=DB()
    ships=_ship_milestones(db,1)
    assert len(ships)==4, ships  # v0.0.77 separates commissioning from fleet posting
    assert ships[0].game_date=='2266.04.19'
    assert 'Strike Force Titan' not in ships[0].body
    assert ships[1].game_date=='2266.07.01' and 'Strike Force Titan under Lin Zhao' in ships[1].body
    assert ships[2].game_date=='2272.10.01' and 'By this date' in ships[2].body
    assert ships[3].game_date=='2272.10.01' and 'Strike Force Cerberus' in ships[3].body
    assert not re.search(r'volunteer|enlist|player|game|Historian', ' '.join(s.body for s in ships), re.I)
    states=_empire_voice_states(db,1)
    sample='Vance Knight entered service as a commander on 2256.11.16.'
    rewritten=_service_narrative(sample,'2256.11.16',states, 'Commonwealth of Man')
    assert 'Commonwealth of Man' in rewritten and 'command ranks' in rewritten and 'volunteer' not in rewritten
    assert _service_narrative(sample,'2200.01.01',states)==sample
    assert 'Commonwealth' not in _service_narrative(sample,'2256.11.16',states,'Sutharian Convocation')
    assert _service_narrative(sample,'2256.11.16',[('2250.01.01','democracy','')])=='Vance Knight entered public service as a commander on 2256.11.16.'
    science=[HistoricalEvent('2251.04.01','science','special_project_observed','Ancient Signal','First observation',
                             'high','first_observed','science_interpretation',58,
                             (('project_key','ANCIENT_SIGNAL'),('locations','Deneb'),('last_observed','2252.01.01'),('scientists','Naima al-Atrash'))),
             HistoricalEvent('2268.07.01','science','situation_observed','Organic Singularity','First observation',
                             'high','first_observed','science_interpretation',48,
                             (('situation_key','situation_organic_singularity'),)),
             HistoricalEvent('2256.01.01','science','situation_observed','Energy Deficit','First observation',
                             'high','first_observed','science_interpretation',32,
                             (('situation_key','situation_energy_deficit'),))]
    presentation=SimpleNamespace(events=science)
    rows,people=_collect_events(db,1,presentation=presentation)
    story=[row for row in rows if row.category=='Story']
    assert len(story)==2,[(row.category,row.title) for row in rows]
    assert 'Naima al-Atrash' in story[0].evidence
    assert 'option' in story[0].evidence.lower() and 'outcome' in story[0].evidence.lower()
    assert 'Energy Deficit' not in [row.title for row in rows]
    root=Path(__file__).parent
    h=(root/'static/campaign.html').read_text()
    css=(root/'static/style.css').read_text()
    assert 'style.css?v=081' in h and 'campaign.js?v=081' in h
    assert '.historian-library a.library-tile' in css and 'grid-template-columns:repeat(3,minmax(0,1fr))' in css
    from playwright.sync_api import sync_playwright
    import shutil
    if shutil.which('chromium'):
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1600,'height':960})
            page.set_content(h.replace('<link rel="stylesheet" href="/static/style.css?v=081">','<style>'+css+'</style>'))
            page.locator('#historian-library').evaluate('(el)=>el.hidden=false')
            assert page.locator('.library-tile').count()==7
            assert page.locator('.library-grid').evaluate('(el)=>getComputedStyle(el).display')=='grid'
            assert page.locator('.library-tile').first.evaluate('(el)=>getComputedStyle(el).display')=='flex'
            assert page.locator('.library-tile').first.evaluate('(el)=>getComputedStyle(el).color')!='rgb(85, 26, 139)' # not browser-default purple
            assert page.locator('.campaign-topbar').evaluate('(el)=>getComputedStyle(el).display')=='grid'
            page.screenshot(path='/mnt/data/_qa76_dashboard.png',full_page=True)
            page.set_viewport_size({'width':550,'height':1000})
            page.wait_for_timeout(100)
            assert page.locator('.library-grid').evaluate('(el)=>getComputedStyle(el).gridTemplateColumns.split(" ").length-1')==0
            assert page.locator('.campaign-topbar').evaluate('(el)=>el.scrollWidth<=innerWidth')
            browser.close()
    print('PASS: ship first-sighting provenance; regime style; scientific stories; CSS cache and layout')
if __name__=='__main__':run()
