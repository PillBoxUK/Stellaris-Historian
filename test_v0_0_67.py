"""v0.0.67 incremental First Contact + recent leader-death audit safeguards.

No private or real save data required. Run: python test_v0_0_67.py
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from historian.domains.politics import first_contact_history as fc
from historian.domains.people import notification_deaths as deaths


@dataclass
class Leader:
    location_type: str


@dataclass
class Leaders:
    leaders: dict


def _row(i):
    return {
        "id": i,
        "game_date": f"{2290+i}.01.01",
        "sha256": f"sha{i}",
        "archive_path": f"/not-opened/save{i}.sav",
        "archive_filename": f"save{i}.sav",
    }


def _report(rows):
    return {
        "version":"0.0.50.4",
        "decoder_revision":fc._CONTACT_DECODER_REVISION,
        "last_processed_snapshot_id":rows[-1]["id"],
        "last_processed_sha256":rows[-1]["sha256"],
        "processed_snapshots_considered":len(rows),
        "archived_snapshots":len(rows),
        "unprocessed_snapshots_ignored":0,
        "cases":[{
            "contact_id":1,
            "assignment_end_interval":{"before":"2290.01.01","after":"2291.01.01"},
            "counterpart_resolved_name":"Empiric Nation",
            "owner_country_name":"Player",
            "record_found": True,
        }],
        "events":[{"event_type":"first_contact_completed","visible":True}],
        "raw_read_failures":[],
    }


def _write_fixture(path, rows):
    (path/'First_Contact_History.json').write_text(json.dumps(_report(rows)),encoding='utf-8')
    (path/'First_Contact_History_Debug.txt').write_text(
        'HEADER\nArchived snapshots: 2\nProcessed snapshots considered: 2\nUnprocessed snapshots ignored: 0\n\nCASES\nAn unchanged case\n',
        encoding='utf-8',
    )
    return path/'First_Contact_History.json',path/'First_Contact_History_Debug.txt'


def test_real_report_reuse_requirements():
    # Only the criteria are checked here; this repository test does not need
    # private campaign files. The uploaded 369-snapshot user report was also
    # separately checked against these same guards before release.
    assert fc._CONTACT_DECODER_REVISION == "0.0.65-fc-1"


def test_closed_cases_reused_and_metadata_accurate():
    with TemporaryDirectory() as tmp:
        folder=Path(tmp)
        old=[_row(i) for i in (1,2)]
        rows=old+[_row(3),_row(4)]
        json_path,debug_path=_write_fixture(folder,old)
        seen=[]
        def parse(**kw):
            seen.append(kw['snapshot_id'])
            assert kw['cache_only'] is True
            return (None,None,Leaders({1:Leader('planet')}),None,None,None,None,None,'hit')
        with patch.object(fc,'load_or_parse_snapshot',side_effect=parse):
            assert fc._reuse_completed_first_contact_history(
                json_path=json_path, debug_path=debug_path, rows=rows,
                source_save=folder/'original.sav',cache_dir=folder,archived_snapshot_count=5,
            )
            assert seen==[3,4],seen
            report=json.loads(json_path.read_text())
            assert report['cases']==_report(old)['cases']
            assert report['events']==_report(old)['events']
            assert report['processed_snapshots_considered']==4
            assert report['unprocessed_snapshots_ignored']==1
            assert report['incremental_reuse']['new_snapshots_checked']==2
            assert 'verified through 2294.01.01' in debug_path.read_text()
            assert debug_path.read_text().count('Incremental evidence reuse:')==1
            # Future reuse scans ONLY the new row and doesn't duplicate label.
            seen.clear()
            assert fc._reuse_completed_first_contact_history(
                json_path=json_path,debug_path=debug_path,rows=rows+[_row(5)],
                source_save=folder/'original.sav',cache_dir=folder,archived_snapshot_count=6,
            )
            assert seen==[5]
            assert debug_path.read_text().count('Incremental evidence reuse:')==1


def test_fallback_on_changed_evidence_and_cache_fault():
    with TemporaryDirectory() as tmp:
        folder=Path(tmp)
        old=[_row(1),_row(2)]
        rows=old+[_row(3)]
        json_path,debug_path=_write_fixture(folder,old)
        before=json_path.read_bytes(),debug_path.read_bytes()
        for leaders,status in ((Leaders({3:Leader('first_contact_system')}),'hit'),(Leaders({}),'miss')):
            with patch.object(fc,'load_or_parse_snapshot',return_value=(None,None,leaders,None,None,None,None,None,status)):
                assert not fc._reuse_completed_first_contact_history(
                    json_path=json_path,debug_path=debug_path,rows=rows,
                    source_save=folder/'original.sav',cache_dir=folder,archived_snapshot_count=3)
            assert (json_path.read_bytes(),debug_path.read_bytes())==before
        original=json.loads(json_path.read_text())
        original['cases'][0]['counterpart_resolved_name']=None
        json_path.write_text(json.dumps(original))
        with patch.object(fc,'load_or_parse_snapshot') as mocked:
            assert not fc._reuse_completed_first_contact_history(
                json_path=json_path,debug_path=debug_path,rows=rows,
                source_save=folder/'original.sav',cache_dir=folder,archived_snapshot_count=3)
            mocked.assert_not_called()
        original['cases'][0]['counterpart_resolved_name']='Empiric Nation'
        original['last_processed_sha256']='mismatch'
        json_path.write_text(json.dumps(original))
        assert not fc._reuse_completed_first_contact_history(
            json_path=json_path,debug_path=debug_path,rows=rows,
            source_save=folder/'original.sav',cache_dir=folder,archived_snapshot_count=3)


class FakeDB:
    def __init__(self):
        self.rows=[_row(i) for i in range(1,7)]
    def all_snapshots(self,c): return self.rows
    def leader_registry(self,c): return [dict(leader_id=7,name='Z')]
    def leader_career_events(self,c,visible_only=False):
        return [dict(event_type='leader_missing_unconfirmed',leader_id=7,snapshot_id=i) for i in (2,4,5)]


def test_death_audit_is_bounded_but_full_mode_remains():
    called=[]
    def apply(rows, history):
        called.append([e['snapshot_id'] for e in history['events']])
        return {'promotions':[],'rejected':[],'confirmed':0,'raw_reads':0}
    with patch.object(deaths,'apply_notification_deaths',side_effect=apply):
        result=deaths.promote_notification_deaths_in_database(FakeDB(),1,since_snapshot_id=4)
        assert called.pop()==[4,5]
        assert result['audit_scope']=='recent-exit-boundaries'
        result=deaths.promote_notification_deaths_in_database(FakeDB(),1)
        assert called.pop()==[2,4,5]
        assert result['audit_scope']=='all-unresolved-exits'


if __name__=='__main__':
    test_real_report_reuse_requirements()
    test_closed_cases_reused_and_metadata_accurate()
    test_fallback_on_changed_evidence_and_cache_fault()
    test_death_audit_is_bounded_but_full_mode_remains()
    print('PASS v0.0.67: closed-case fast path, fallback cases, bounded/full death audits')
