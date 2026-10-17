"""v0.0.78: archive-safe rewrite, actual game-text descriptions, voice and dashboard."""
from __future__ import annotations
from pathlib import Path
from tempfile import TemporaryDirectory
import json, os, zipfile
from unittest.mock import patch
from historian.db import Database
from historian.historical_events import HistoricalEvent
from historian.story_text import game_description, _index
from historian.timeline import _story_prose, _technology_timeline_events, _opening_narrative
from historian.timeline_rewrite import rewrite_timeline


def run():
    with TemporaryDirectory() as d:
        root=Path(d)
        game=root/'Stellaris'
        l=(game/'localisation'/'english');l.mkdir(parents=True)
        (l/'sample_l_english.yml').write_text('''\ufeffl_english:\n REMOVE_IMPLANTS:0 "Remove Malfunctioning Implants"\n REMOVE_IMPLANTS_DESC:0 "A network of implanted devices has failed, leaving its hosts vulnerable to unpredictable neural disturbances. Medical teams must investigate the cause before action can be taken."\n CRYSTAL_STUDY_DESC:0 "Unusual crystalline formations are being examined for their unusual physical properties and potential applications."\n''',encoding='utf-8')
        with patch.dict(os.environ, {'STELLARIS_GAME_DIR': str(game)}):
            _index.cache_clear()
            description,source=game_description('REMOVE_IMPLANTS')
            assert 'neural disturbances' in description, description
            assert 'installed Stellaris' in source
            event=HistoricalEvent('2212.04.01','science','special_project_observed','Remove Malfunctioning Implants','First archived observation','high','first_observed','science_interpretation',65,(('project_key','REMOVE_IMPLANTS'),('scientists','Hong Lin')))
            item=_story_prose(event)
            assert 'neural disturbances' in item.body and 'underway' not in item.body
            assert 'Hong Lin' in item.evidence and 'option' in item.evidence
            crystal=HistoricalEvent('2277.01.01','science','special_project_observed','Crystalline Study','First observation','high','first_observed','science_interpretation',60,(('project_key','CRYSTAL_STUDY'),))
            assert 'crystalline formations' in _story_prose(crystal).body
            _index.cache_clear()
        technology=HistoricalEvent('2200.01.01','technology','technology_learned','Doctrine: Fleet Support','Research','high','first_observed','technology_history',75)
        tech=_technology_timeline_events([technology])
        assert tech and '1st of January, 2200' in tech[0].body
        db=Database(root/'data.db')
        folder=root/'campaign';folder.mkdir()
        cid=db.create_campaign('test','game','start.sav','Commonwealth of Man','4.5.2',str(folder),'2200.01.01')
        archive=folder/'ironman-start.sav'
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('meta','name="Commonwealth of Man"\ndate="2200.01.01"')
            z.writestr('gamestate','date="2200.01.01"')
        db.insert_snapshot(cid,kind='start',game_date='2200.01.01',sha256='a'*64,
                           archive_filename=archive.name,archive_path=str(archive),source_mtime=0,source_size=0,sequence_no=0)
        saved=db.history_entries(cid)
        assert 'earliest surviving' in _opening_narrative(db,cid,'Commonwealth of Man','2200.01.01')
        output=folder/'Empire_Timeline.html'
        with patch('historian.timeline_rewrite.render_timeline',side_effect=lambda db,cid:output.write_text('TEST') or output):
            # Normal output's path must be returned by the mocked renderer.
            pass
        def fake_render(_db,_cid):
            output.write_text('GENERATED')
            return output
        progress=[]
        with patch('historian.timeline_rewrite.render_timeline',side_effect=fake_render), \
             patch('historian.timeline_rewrite.review_campaign',return_value={'rebuilt':True,'reviewed':1,'cache_hits':0,'cache_misses':1,'cache_extends':0}):
            report=rewrite_timeline(db,cid,progress=lambda n,t,m:progress.append((n,t,m)))
        assert report['archived_saves_inspected']==1 and report['save_metadata_read']==1,report
        assert output.read_text()=='GENERATED'
        assert (folder/'Timeline_Rewrite_Report.json').is_file()
        assert not db.history_entries(cid) and progress
    app=Path(__file__).resolve().parent
    html=(app/'static/campaign.html').read_text()
    js=(app/'static/campaign.js').read_text()
    assert 'Update Historical Timeline' in html and 'api/rewrite-timeline' in js
    assert 'style.css?v=081' in html and 'campaign.js?v=081' in html
    assert 'Use Game Texts' in html
    print('PASS: v0.0.78 installed-game text, credible story source, chronology, safe archive traversal, rewrite report and UI')

if __name__=='__main__':run()
