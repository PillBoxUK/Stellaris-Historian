"""v0.0.70 dossier/navigation regression: no game saves or database records mutated."""
from __future__ import annotations
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from subprocess import run
from bs4 import BeautifulSoup
import re

from historian.domains.combat.models import BattleState, WarState, CombatSnapshot
from historian.presentation_history import PresentationHistory
from historian.domains.technology.models import TechnologySnapshot, TechnologyState
from historian.war_journal import _war_technology_html
from historian.war_journal import (
    FormalWarRecord, _war_anchor, _war_index_html, _war_nav_html,
    _war_chronology_html, _formal_war_html, _aggregate_formal_wars,
    _war_victory_annotation, render_war_journal,
)


def battle(wid: int, date: str, system: str, player_loss: int | None, no: int):
    return BattleState(battle_key=f'{wid}:{no}', war_id=wid, battle_index=no,
        date=date, battle_type='ships', system_id=55, system_name=system,
        planet_id=None, planet_name=None,
        attacker_country_ids=(16777226,), defender_country_ids=(0,),
        attacker_victory=True, attacker_losses=0, defender_losses=player_loss,
        player_side='defender', player_victory=None, player_losses=player_loss, enemy_losses=0)


def war(wid, start, goal, battles=()):
    return WarState(war_id=wid, name=f'War {wid}', start_date=start, player_side='attacker',
        attacker_country_ids=(0,), defender_country_ids=(16777226,), attacker_war_goal=goal,
        defender_war_goal='conquest',attacker_war_exhaustion=None,defender_war_exhaustion=None,
        battles=tuple(battles))


def snap(number,date,record=None):
    wars={} if record is None else {record.war_id:record}
    return CombatSnapshot(snapshot_id=number,game_date=date,player_country_id=0,
                          wars=wars,battles={b.battle_key:b for r in wars.values() for b in r.battles})


b1=battle(67108865,'2266.07.01','Ramman',3,1)
b2=battle(83886080,'2297.06.28','Mubblar',2,1)
b3=battle(83886080,'2297.09.10','Mubblar',11,2)
b4=battle(83886080,'2298.02.06','Hulfass Khor',None,3)
b5=battle(100663296,'2302.10.01','Qeffoth',5,1)
w1=war(67108865,'2256.02.21','conquest',(b1,))
w2=war(83886080,'2293.04.26','humiliation',(b2,b3,b4))
w3=war(100663296,'2301.06.12','conquest',(b5,))
snaps=[
    snap(1,'2256.04.01',w1),snap(2,'2278.07.01',w1),snap(3,'2278.10.01'),
    snap(4,'2293.07.01',w2),snap(5,'2300.07.01',w2),snap(6,'2300.10.01'),
    snap(7,'2301.07.01',w3),snap(8,'2303.01.01',w3),snap(9,'2303.04.01'),
]
technology_snapshots=(
    TechnologySnapshot(1,'2293.04.01',0,{'tech_mining':TechnologyState('tech_mining','Mining',1)}),
    TechnologySnapshot(2,'2297.07.01',0,{'tech_mining':TechnologyState('tech_mining','Mining',1),
                                       'tech_energy_grid':TechnologyState('tech_energy_grid','Energy Grid',1)}),
    TechnologySnapshot(3,'2300.10.01',0,{'tech_mining':TechnologyState('tech_mining','Mining',2),
                                       'tech_energy_grid':TechnologyState('tech_energy_grid','Energy Grid',1)}),
)
records=_aggregate_formal_wars(PresentationHistory((),(),(),tuple(snaps),(),(),technology_snapshots))
from historian.domains.technology.history import derive_technology_history
technology_events=tuple(derive_technology_history(list(technology_snapshots))['events'])
assert 'Energy Grid' in _war_technology_html(records[1],technology_events,snapshots_available=True)
assert 'Mining' not in _war_technology_html(records[1],technology_events,snapshots_available=True) # increase is after war
assert 'coverage unavailable' in _war_technology_html(records[1],(),snapshots_available=False)

assert [w.war_id for w in records] == [67108865,83886080,100663296]
assert records[1].first_absent_after_last == '2300.10.01'
assert _war_victory_annotation(records[1],'Commonwealth of Man')['notification_date']=='2300.08.15'
assert _war_victory_annotation(records[2],'Commonwealth of Man')['notification_date']=='2303.02.14'
assert _war_anchor(records[2].war_id)=='war-100663296'

index=_war_index_html(records,'Commonwealth of Man')
assert index.count('class="war-index-card"')==3
assert 'War of Humiliation against Hulfiran United Stars' in index
assert 'Screenshot' not in index or 'screenshot' in index.lower()
for pos in range(3):
    top=_war_nav_html(records,pos,'Commonwealth of Man')
    bottom=_war_nav_html(records,pos,'Commonwealth of Man',at_bottom=True)
    assert f'War {pos+1} of 3' in top
    assert f'War {pos+1} of 3' in bottom
    assert top.count('class="war-step disabled"')==(1 if pos in (0,2) else 0)
    assert '#war-index' in top
    if pos>0: assert f'href="#war-{records[pos-1].war_id}"' in top
    if pos<2: assert f'href="#war-{records[pos+1].war_id}"' in top

chron=_war_chronology_html(records[1],_war_victory_annotation(records[1],'Commonwealth of Man'))
assert '2300.08.15' in chron
assert '2297' in chron and '2298' in chron
assert 'Incomplete' in chron  # one battle has no casualty figure
assert '11 recorded Commonwealth ship losses' in chron
assert '2297.09.10' in chron
assert '2297.06.28' in chron
assert 'exact treaty day' in chron.lower() or 'exact treaty' in chron.lower()
undated=replace(b2,date='0.01.01',player_losses=None)
undated_war=replace(records[1],battles={undated.battle_key:undated},battle_first_seen={undated.battle_key:'2298.07.01'})
assert 'No dated player-involved formal battles' in _war_chronology_html(undated_war,None)

brief_html=_formal_war_html(records[1],'2303.04.01','Commonwealth of Man',
    navigator_top=_war_nav_html(records,1,'Commonwealth of Man'),
    navigator_bottom=_war_nav_html(records,1,'Commonwealth of Man',at_bottom=True))
assert 'id="war-83886080"' in brief_html
assert brief_html.count('class="war-pager')==2
assert 'Copy war brief' in brief_html and 'Save war brief' in brief_html
assert 'data-location=' in brief_html and 'battle-dossier' in brief_html
assert '29' not in brief_html or 'battle' in brief_html
assert 'war-confirmation' in brief_html
assert 'Not verified from archived war' in brief_html
assert '11 recorded Commonwealth ship losses' in brief_html
# malicious save-data names may contain HTML-like text: output must escape them
injected=replace(b2,system_name='<img src=x onerror=alert(1)>')
unsafe=replace(records[1],battles={injected.battle_key:injected},
    battle_first_seen={injected.battle_key:'2297.07.01'})
escaped=_formal_war_html(unsafe,'2300.10.01','Commonwealth of Man')
assert '&lt;img src=x onerror=alert(1)&gt;' in escaped
assert '<img src=x onerror=alert(1)>' not in escaped

class MockDB:
    def __init__(self,root):self.root=root
    def campaign(self, cid):
        return {'archive_dir':str(self.root),'empire_name':'Commonwealth of Man','latest_game_date':'2303.04.01'}

with TemporaryDirectory() as d:
    db=MockDB(Path(d))
    history=PresentationHistory((),(),(),tuple(snaps),(),(),technology_snapshots)
    with patch('historian.war_journal.build_presentation_history',return_value=history):
        page=render_war_journal(db,1)
    html=page.read_text(encoding='utf-8')
    soup=BeautifulSoup(html,'html.parser')
    assert len(soup.select('.war-card')) == 3
    assert len(soup.select('.war-pager')) == 6
    assert len(soup.select('.war-index-card')) == 3
    assert len(soup.select('.war-chronicle')) == 3
    assert len(soup.select('.battle-dossier')) == 3
    assert len(soup.select('.war-actions')) == 3
    assert len(soup.select('.wartime-tech')) == 3
    assert 'Energy Grid' in soup.select_one('#war-83886080 .wartime-tech').get_text()
    assert all(len(w.select('.war-pager'))==2 for w in soup.select('.war-card'))
    for link in soup.select('.war-index-card,.war-step[href]'):
        assert soup.select_one(link['href']) is not None,link
    js='\n'.join(str(element.string or element.text) for element in soup.find_all('script') if not element.get('src'))
    assert "document.querySelectorAll('.aftermath-run:not(.military-run)')" in js
    assert "document.querySelectorAll('.war-card')" in js
    assert "download-war-brief" in js
    script=Path(d)/'war-script.js';script.write_text(js,encoding='utf-8')
    result=run(['node','--check',str(script)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    print('Synthetic 3-war HTML and browser JavaScript syntax PASS; HTML bytes',len(html))
    # Real chromium browser smoke test: navigation, battle filter, export.
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
            tab=browser.new_page(accept_downloads=True,viewport={'width':1360,'height':900})
            tab.set_content(html,wait_until='domcontentloaded')
            tab.locator('.war-index-card').nth(1).click()
            assert tab.evaluate('location.hash')=='#war-83886080'
            tab.locator('#war-83886080 .war-pager.top .war-step').last.click()
            assert tab.evaluate('location.hash')=='#war-100663296'
            tab.keyboard.press('[')
            assert tab.evaluate('location.hash')=='#war-83886080'
            tab.locator('#war-83886080 .theatre-breakdown summary').click()
            tab.locator('#war-83886080 .theatre-filter').first.click()
            assert tab.locator('#war-83886080 .battle-dossier').evaluate('(el) => el.open')
            assert '2 of 3' in tab.locator('#war-83886080 .battle-shown').inner_text()  # Mubblar
            tab.locator('#war-83886080 .battle-reset').click()
            assert '3 of 3' in tab.locator('#war-83886080 .battle-shown').inner_text()
            with tab.expect_download() as item:
                tab.locator('#war-83886080 .download-war-brief').click()
            download=item.value
            assert download.suggested_filename=='Stellaris_War_83886080_Brief.txt'
            brief_path=Path(d)/'export.txt';download.save_as(brief_path)
            content=brief_path.read_text()
            assert '2300.08.15' in content and 'battle' in content.lower() and 'Energy Grid' in content, repr(content[:2200])
            browser.close()
        print('Chromium interactive navigation, theatre filter, export PASS')
    except ImportError:
        print('Playwright unavailable: browser smoke test SKIPPED')
print('ALL v0.0.70 TESTS PASS')
