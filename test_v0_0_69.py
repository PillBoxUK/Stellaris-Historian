"""v0.0.69 native battle/cache regression, updated for v0.0.71.1 save-only evidence."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json,hashlib,sys,time
sys.path.insert(0, str(Path(__file__).parent))
from historian.war_journal import FormalWarRecord,_war_victory_annotation,_formal_war_html
from historian.war_intelligence import _cached_save,_one_save,_exhaustion_only,investigate_war

ROOT=Path(__file__).parent.parent
WAR=83886080
PARTIES={0,16777226}

def war(wid=WAR,start='2293.04.26',last='2300.07.01',end='2300.10.01'):
 return FormalWarRecord(war_id=wid,name='War '+str(wid),start_date=start,first_observed=start,last_observed=last,first_absent_after_last=end,
    player_side='attacker',attacker_war_goal='humiliation',defender_war_goal='conquest',attacker_country_ids=(0,),defender_country_ids=(16777226,))

one=war()
a=_war_victory_annotation(one,'Commonwealth of Man')
assert a is None
html=_formal_war_html(one,'2300.10.01','Commonwealth of Man')
assert 'Screenshot-confirmed' not in html
assert 'Not verified from archived war' in html
assert 'Ending observed between 2300.07.01 and 2300.10.01' in html
assert not _war_victory_annotation(war(start='2293.04.27'),'Commonwealth of Man')
assert not _war_victory_annotation(one,'Another campaign')
assert not _war_victory_annotation(war(last='2300.10.01',end='2301.01.01'),'Commonwealth of Man')
sil=war(wid=100663296,start='2301.06.12',last='2303.01.01',end='2303.04.01')
assert _war_victory_annotation(sil,'Commonwealth of Man') is None
print('War-ending native-archive-only audit PASS')

p=ROOT/'ironman-399.sav'
assert p.is_file()
state=_one_save(p,WAR,0,PARTIES)
assert state['battle_exhaustion']==_exhaustion_only(p,WAR)
assert len(state['battle_exhaustion']) >= 21
assert state['battle_exhaustion'][0]['attacker_exhaustion_raw'] is not None
assert state['battle_exhaustion'][0]['defender_exhaustion_raw'] is not None
assert all('attacker_exhaustion_raw' in b for b in state['battle_exhaustion'])
print('Battle-local exhaustion parity against actual native battle entries PASS')

with TemporaryDirectory() as d:
 root=Path(d); cache=root/'.historian_evidence';cache.mkdir()
 digest=hashlib.sha256(p.read_bytes()).hexdigest()
 # v68 index migration: validated old contents, no need to reparse all station/planet records
 old={k:state[k] for k in ('battles','planets','opponent_stations')}
 (cache/f'military_v1_{WAR}_{digest}.json').write_text(json.dumps({'signature':[1,WAR,0,sorted(PARTIES),digest], 'value':old}))
 row={'sha256':digest,'archive_path':str(p)}
 stats={'cache_hits':0,'raw_reads':0,'legacy_reused':0}
 new=_cached_save(cache,row,WAR,0,PARTIES,stats)
 assert new==state, 'Migrated v68 station/planet evidence must match a full fresh v69 parse'
 assert stats=={'cache_hits':0,'raw_reads':1,'legacy_reused':1},stats
 cached=_cached_save(cache,row,WAR,0,PARTIES,stats)
 assert cached==new and stats['cache_hits']==1
 print('Lossless v0.0.68 cache upgrade + warm cache PASS')

 class DB:
  def campaign(self, cid):return {'archive_dir':str(root)}
  def processed_snapshots(self, cid):return [dict(game_date='2298.07.01',sha256=digest,archive_path=str(p))]
 progress=[]
 report=investigate_war(DB(),1,WAR,0,tuple(PARTIES),'2293.04.26','2299.01.01',
     progress=lambda done,total,date,stat:progress.append((done,total,date,dict(stat))))
 assert progress[0][0]==0 and progress[-1][0]==1
 assert report['battle_exhaustion_evidence']
 assert report['ground_battles'] and report['ground_battles'][0]['date'] is None
 assert 'war exhaustion' in report['disclaimer']
 print('Archive progress, native army placeholder and exhaustion labels PASS')
print('ALL v0.0.69 TESTS PASS')
