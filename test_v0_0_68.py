"""v0.0.68 regression with untouched archived Ironman saves."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import json
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from historian.war_intelligence import _one_save, investigate_war
from historian.war_journal import FormalWarRecord, _war_display_title, _formal_war_html

FIXTURES = Path(__file__).parent.parent
WAR_ID = 83886080
PARTIES = (0, 16777226)
DATES = {394:"2297.04.01",395:"2297.07.01",396:"2297.10.01",398:"2298.04.01",399:"2298.07.01",401:"2299.01.01"}

class FakeDB:
    def __init__(self, root):
        self.root = root
        self.rows = []
        for no, date in DATES.items():
            path = FIXTURES / f'ironman-{no}.sav'
            assert path.exists(), path
            self.rows.append(dict(game_date=date, sha256=sha256(path.read_bytes()).hexdigest(), archive_path=str(path)))
    def campaign(self, campaign_id):
        return {"archive_dir": str(self.root)}
    def processed_snapshots(self, campaign_id):
        return self.rows


def main():
    war = FormalWarRecord(war_id=WAR_ID, name=f'War {WAR_ID}', start_date='2293.04.26',
        first_observed='2293.07.01', last_observed='2299.01.01', player_side='attacker',
        attacker_war_goal='humiliation', defender_war_goal='conquest',
        attacker_country_ids=(0,), defender_country_ids=(16777226,))
    title, reason = _war_display_title(war, 'Commonwealth of Man')
    assert title == 'War of Humiliation', (title,reason)  # no manual opponent annotations
    assert 'saved evidence' in reason or 'recorded' in reason
    out = _formal_war_html(war,'2299.01.01','Commonwealth of Man')
    assert 'Hulfiran United Stars' not in out  # old manually sourced label is not canonical
    spoof = FormalWarRecord(**{**vars(war), 'start_date': '2298.01.01'})
    assert 'Hulfiran United Stars' not in _war_display_title(spoof,'Commonwealth of Man')[0]
    try:
        import zlib
        start = time.perf_counter()
        for no in DATES:
            path = FIXTURES / f'ironman-{no}.sav'
            item = _one_save(path, WAR_ID, 0, set(PARTIES))
            if no <= 398:
                assert not item['battles']
            else:
                assert len(item['battles'])==1
                b = item['battles'][0]
                assert b['colony_id']==134 and b['date'] is None and b['player_tactical_side']=='defender'
                assert b['attacker_losses_raw']==b['defender_losses_raw']==0
            if no == 398:
                p=item['planets']['134']; assert (p['owner_id'],p['controller_id'])==(16777226,16777226)
            if no == 399:
                p=item['planets']['134']; assert (p['owner_id'],p['controller_id'])==(16777226,0)
                assert 'Thrus-Sanguur' in p['name']
            station=[x for x in item['opponent_stations'] if x['system_name']=='Mubblar']
            assert len(station)==1 and station[0]['starbase_id']==364
        print('Direct save evidence parity: all 6 saves PASS; time',round(time.perf_counter()-start,1),'sec')
    except Exception:
        raise
    with TemporaryDirectory() as folder:
        db=FakeDB(Path(folder))
        first=investigate_war(db,1,WAR_ID,0,PARTIES,'2293.04.26','2299.01.01')
        assert len(first['ground_battles'])==1
        assert first['ground_battles'][0]['first_archive']=='2298.07.01'
        assert first['ground_battles'][0]['date'] is None
        hits=[x for x in first['planetary_controller_changes'] if x['colony_id']==134]
        assert len(hits)==1 and hits[0]['before_date']=='2298.04.01' and hits[0]['after_date']=='2298.07.01'
        assert hits[0]['owner_id']==16777226 and hits[0]['later_controller_id']==0
        mublar=[x['combat_activity_date'] for x in first['enemy_starbase_activity'] if x['system_name']=='Mubblar']
        assert '2297.07.01' in mublar and '2297.08.01' in mublar
        assert '2264.03.17' not in mublar
        second=investigate_war(db,1,WAR_ID,0,PARTIES,'2293.04.26','2299.01.01')
        assert first==second
        assert len(list((Path(folder)/'.historian_evidence').glob('military_*.json')))==len(DATES)
        print('Ground, occupation, enemy-station, caching and scoped naming PASS')

if __name__=='__main__':
    main()
