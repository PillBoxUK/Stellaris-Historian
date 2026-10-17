"""v0.0.79: research queues, sidecar durability, dated prose, no destructive writes."""
from __future__ import annotations
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib,time,zipfile
from historian.db import Database
from historian.research_history import (
    parse_research_save, capture_observation, read_observations,
    research_events, render_research_history, ledger_path
)
from historian.timeline import _research_queue_timeline_events, _aux_ship_prose
from historian.historical_events import HistoricalEvent


def _fixture_save(path: Path, date: str, queue_date: str | None, key: str, progress: float):
    queue = (f'{{\nprogress={progress}\ntechnology="{key}"\ndate="{queue_date}"\n}}'
             if queue_date else '')
    game=(f'player={{\n {{ name="unknown"\n country=0\n }}\n}}\n'
          f'country={{\n\t0={{\n tech_status={{\n'
          f'physics_queue={{ {queue} }}\n'
          f'society_queue={{ {queue} }}\n'
          f'engineering_queue={{ {queue} }}\n'
          ' }\n }\n}\n')
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('meta',f'date="{date}"\n')
        z.writestr('gamestate',game)


def run():
    actual=[Path('/mnt/data/ironman-start.sav'),Path('/mnt/data/ironman-429.sav'),
            Path('/mnt/data/ironman-453.sav'),Path('/mnt/data/ironman-496.sav')]
    with TemporaryDirectory() as fixtures:
        files=Path(fixtures)
        if all(p.is_file() for p in actual):
            available=actual
        else:
            available=[files/x for x in ('ironman-start.sav','ironman-429.sav',
                                        'ironman-453.sav','ironman-496.sav')]
            _fixture_save(available[0], '2200.01.01', None, 'tech_power_plant_2', 0)
            _fixture_save(available[1], '2306.01.01', '2305.09.17', 'tech_power_plant_2', 957.41008)
            _fixture_save(available[2], '2312.01.01', '2310.02.05', 'tech_reactor_boosters_3', 5671.0)
            _fixture_save(available[3], '2322.04.01', '2321.09.27', 'tech_dyson_swarm', 8823.0)
        _run_actual_test(available)


def _run_actual_test(available):
    beginning=parse_research_save(available[0])
    assert beginning['game_date']=='2200.01.01' and not any(beginning['queues'].values())
    late=parse_research_save(available[1]);assert late['game_date']=='2306.01.01'
    p=late['queues']['physics'][0]
    assert p['key']=='tech_power_plant_2' and p['queue_date']=='2305.09.17' and abs(p['progress']-957.41008)<.01,p
    with TemporaryDirectory() as temp:
        root=Path(temp)
        archive=root/'campaign';archive.mkdir()
        db=Database(root/'historian.db')
        cid=db.create_campaign('research-fixture','game','ironman.sav','Commonwealth of Man','4.5.2',str(archive),'2200.01.01')
        for n,save in enumerate(available):
            details=parse_research_save(save)
            sha=hashlib.sha256(save.read_bytes()).hexdigest()
            db.insert_snapshot(cid,kind='start' if n==0 else 'periodic', game_date=details['game_date'],
                               sha256=sha, archive_filename=save.name,archive_path=str(save),
                               source_mtime=0,source_size=0,sequence_no=n)
            record=db.all_snapshots(cid)[-1]
            db.mark_processed(record['id'])
            first=capture_observation(archive,save,sha)
            cached=capture_observation(archive,save,sha)
            assert not first['cached'] and cached['cached']
            assert first['seconds']<3,first
        observed=read_observations(archive,list(db.all_snapshots(cid)))
        assert len(observed)==len(available)
        events=research_events(observed)
        assert any(e['discipline']=='physics' and e['key']=='tech_power_plant_2' for e in events)
        entries=_research_queue_timeline_events(db,cid,'Commonwealth of Man',[])
        assert entries and any('research' in e.body.lower() for e in entries)
        assert all('player' not in e.body.lower() and 'Historian' not in e.body for e in entries)
        assert any('first observed' in e.evidence for e in entries)
        report=render_research_history(db,cid)
        html=report.read_text(encoding='utf-8')
        assert 'Physics' in html and 'Engineering' in html and 'tech_power_plant_2' not in html
        assert 'Research History' in html and '/timeline' in html
        assert ledger_path(archive).is_file()
        assert db.snapshot_count(cid)==len(available)
        assert all(db.all_snapshots(cid)[i]['processed'] for i in range(len(available)))
        ship=HistoricalEvent('2209.03.08','military','ship_commissioned',
                             'Construction Ship Assiduity Commissioned',
                             'The construction ship Assiduity entered service on 2209.03.08, at Deneb Starbase, assigned to Assiduity.',
                             'high','exact_save_field','ship_history',75)
        prose=_aux_ship_prose(ship,'Commonwealth of Man')
        assert 'infrastructure' in prose.body and 'Deneb Starbase' in prose.body and 'not establish that it was built there' in prose.body
        from playwright.sync_api import sync_playwright
        import shutil
        if shutil.which('chromium'):
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
                page=browser.new_page(viewport={'width':1280,'height':850})
                errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.set_content(html)
                assert page.locator('.project').count()>=3
                page.locator('button[data-branch="society"]').click()
                assert page.locator('.project:visible').count()>=1
                page.locator('button[data-branch="all"]').click()
                page.locator('#find').fill('Power Plant')
                assert page.locator('.project:visible').count()>=1
                page.locator('#find').fill('')
                page.locator('.project:visible').first.locator('summary').click()
                assert page.locator('.project:visible').first.locator('li').count()>=1
                assert not errors,errors
                browser.close()
        print('PASS: native queue dates, progress, three branches, idempotency, safe research sidecar, prose, Chromium dossier',len(observed),'saves',len(events),'changes')

if __name__=='__main__':run()
