"""v0.0.81: evidence-first origins, native milestones, war exhaustion, full rebuild."""
from __future__ import annotations
import json, re, tempfile, zipfile
from pathlib import Path
from unittest.mock import patch
from historian.founding_chapter import extract_founding_profile, founding_chapter
from historian.native_milestones import extract_player_milestones, milestone_events, capture_native_milestones
from historian.narrative_clean import clean_game_description
from historian.domains.combat.parser import _war_direct_float
from historian.db import Database
from historian.timeline_rewrite import rewrite_timeline
from historian.timeline import _founding_prologue, _native_milestones, _opening_narrative


def run():
    # A biological hive is NOT a machine despite gestalt ethics.
    text='''player=
{
 {
  country=3
 }
}
species_db=
{
 28=
 {
  name=
  {
   key="SPEC_Myrran"
  }
  class="FUN"
  portrait="fungoid_01"
  traits=
  {
   trait="trait_organic"
   trait="trait_adaptive"
  }
 }
}
country=
{
 3=
 {
  founder_species_ref=28
  homeworld_name=
  {
   key="NAME_Aurora"
  }
  government=
  {
   type="gov_hive_mind"
   authority="auth_hive_mind"
   origin="origin_special_purpose"
   civics=
   {
    "civic_ascetic"
   }
  }
  ethos=
  {
   ethics=
   {
    "ethic_gestalt_consciousness"
   }
  }
  timeline_events=
  {
   {
    date="2200.01.02"
    definition="timeline_first_war_won"
    data={ 3 4 }
    types={ country country }
   }
   {
    date="2200.01.01"
    definition="timeline_event_year"
   }
  }
 }
}
galactic_community=
{
 community_formed="2200.01.04"
 council_established="2200.01.07"
}
'''
    with tempfile.TemporaryDirectory() as work:
        root=Path(work);save=root/'ironman-start.sav'
        with zipfile.ZipFile(save,'w',compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('meta','name="Test Myrran"\ndate="2200.01.01"\nversion="4.5.2"')
            z.writestr('gamestate',text)
        data=extract_founding_profile(save)
        assert data['species_name']=='Myrran',data
        assert data['homeworld']=='Aurora',data
        assert data['species_group']=='fungoid' and data['gestalt'] and not data['machine']
        narrative=founding_chapter(data)
        assert 'Myrran' in narrative and 'Aurora' in narrative and 'machine' not in narrative.lower(),narrative
        assert '\n\n' in narrative and 'trait_organic' not in narrative
        native=capture_native_milestones(root,save,'x'*64)
        assert native['galactic_community_formed']=='2200.01.04'
        assert native['galactic_council_established']=='2200.01.07'
        assert len(native['events'])==2,native
        events=milestone_events(native,'Test Myrran')
        assert any(e['date']=='2200.01.02' and 'victory' in e['body'] for e in events)
        assert any(e['title']=='Formation of the Galactic Community' for e in events)
        assert all('year' not in e['title'].lower() for e in events)
        cached=capture_native_milestones(root,save,'x'*64)
        assert cached==native
        assert _war_direct_float('''\t\tstart_date="2200.01.01"\n\t\tbattles={\n\t\t\tattacker_war_exhaustion=0.99\n\t\t}\n\t\tattacker_war_exhaustion=0.40\n\t\tdefender_war_exhaustion=0.20''','attacker_war_exhaustion')==0.4
        assert _war_direct_float('''\t\tstart_date="2200.01.01"\n\t\tbattles={\n\t\t\tattacker_war_exhaustion=0.99\n\t\t}''','attacker_war_exhaustion') is None
        assert 'game' not in clean_game_description('The scientists discovered a capsule with a secret chart.').lower()
        db=Database(root/'historian.db')
        cid=db.create_campaign('myrran',str(root),str(save),'Test Myrran','4.5.2',str(root),'2200.01.01')
        db.insert_snapshot(cid,kind='start',game_date='2200.01.01',sha256='x'*64,archive_filename=save.name,archive_path=str(save),source_mtime=0,source_size=save.stat().st_size,sequence_no=0)
        prologue=_founding_prologue(db,cid)
        assert prologue and 'Myrran' in prologue[0] and 'Aurora' in prologue[0]
        assert len(_native_milestones(db,cid,'Test Myrran'))==0  # unprocessed never published
        db.mark_processed(db.all_snapshots(cid)[0]['id'])
        assert len(_native_milestones(db,cid,'Test Myrran'))==3
        # Full reconstruction: patch expensive review so test isolates orchestration.
        output=root/'Empire_Timeline.html'
        output.write_text('OLD\n')
        calls=[]
        def fake_review(_db,_cid,*,progress=None):
            calls.append('review')
            assert (Path(_db.path).parent/'autobackups').is_dir()
            return {'rebuilt':True,'reviewed':1,'cache_hits':0,'cache_misses':1,'cache_extends':0}
        def fake_render(_db,_cid):
            calls.append('render')
            output.write_text('NEW\n')
            return output
        with patch('historian.timeline_rewrite.review_campaign',side_effect=fake_review),patch('historian.timeline_rewrite.render_timeline',side_effect=fake_render):
            report=rewrite_timeline(db,cid)
        assert calls==['review','render'],calls
        assert report['full_historical_rebuild'] and report['reviewed_by_current_parsers']==1
        assert Path(report['database_backup']).exists() and Path(report['database_backup']).stat().st_size>0
        assert report['native_timeline_milestones']==2
        assert output.read_text()=='NEW\n'
        before=output.read_text()
        with patch('historian.timeline_rewrite.review_campaign',return_value={'rebuilt':False,'errors':['bad save']}):
            try:rewrite_timeline(db,cid)
            except ValueError:pass
            else:assert False,'must fail closed'
        assert output.read_text()==before
    print('PASS v0.0.81: native founding/Hive Mind, exact milestones, global institutions, direct war exhaustion, staging backup, full rebuild orchestration')

if __name__=='__main__':run()
