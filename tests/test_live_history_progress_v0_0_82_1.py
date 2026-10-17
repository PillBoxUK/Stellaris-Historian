"""Dependency-free regression test for the v0.0.82.1 Live History hotfix.

Run from Historian installation root:
    python tests/test_live_history_progress_v0_0_82_1.py

Mocks I/O and all Stellaris parsing; never accesses or alters actual campaign data.
"""
from __future__ import annotations

import ast
from pathlib import Path
import time
from types import SimpleNamespace
from tempfile import TemporaryDirectory

SOURCE = Path(__file__).resolve().parents[1] / 'historian' / 'history_processor.py'


def load_processing_function(source: Path, context: dict):
    tree = ast.parse(source.read_text(encoding='utf-8'), filename=str(source))
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == 'process_unprocessed')
    standalone = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    exec(compile(standalone, str(source), 'exec'), context)
    return context['process_unprocessed']


class FakeDB:
    def __init__(self):
        # Two *distinct saves* on one game date must each be processed.
        self.snapshots = [
            {'id': 519, 'sha256': 'distinct-hash-519', 'archive_path': '519.sav',
             'archive_filename': 'ironman-519.sav', 'game_date': '2327.01.08', 'kind': 'normal'},
            {'id': 520, 'sha256': 'distinct-hash-520', 'archive_path': '520.sav',
             'archive_filename': 'ironman-520.sav', 'game_date': '2327.01.08', 'kind': 'normal'},
        ]
        self.done = set()
        self.entries = []
        self.checkpoints = 0

    def reconcile_processed_snapshots(self, cid):
        return 0

    def unprocessed_snapshots(self, cid):
        return [x for x in self.snapshots if x['id'] not in self.done]

    def previous_snapshot(self, cid, snapshot_id):
        match = [x for x in self.snapshots if x['id'] < snapshot_id]
        return match[-1] if match else None

    def add_history_entry(self, **kwargs):
        self.entries.append(kwargs)

    def apply_ship_fleet_delta(self, *args):
        pass

    def apply_leader_delta(self, *args):
        pass

    def apply_world_delta(self, *args):
        pass

    def apply_politics_delta(self, *args):
        pass

    def mark_processed(self, sid):
        self.done.add(sid)

    def unprocessed_count(self, cid):
        return len(self.unprocessed_snapshots(cid))

    def checkpoint(self):
        self.checkpoints += 1


def run_once(progress_provided: bool):
    with TemporaryDirectory() as temp:
        db = FakeDB()
        loaded = []
        observed_progress = []
        messages = []

        def parser(*, archive_path, source_save, source_sha256, snapshot_id,
                   cache_dir, timings=None, **kwargs):
            loaded.append((snapshot_id, source_sha256))
            if timings is not None:
                timings['zip_read'] = 0.001
            state = SimpleNamespace(ships=[], fleets=[], shipyards=[], build_orders=[])
            leaders = SimpleNamespace(leaders=[])
            worlds = SimpleNamespace(worlds=[])
            science = SimpleNamespace(archaeology_sites=[], special_projects=[], situations=[])
            combat = SimpleNamespace(wars=[], battles=[], ship_activity=[], starbase_activity=[])
            technology = SimpleNamespace(technologies=[])
            politics = SimpleNamespace(relations=[], traditions=[])
            return (SimpleNamespace(game_date='2327.01.08'), state, leaders, worlds,
                    science, combat, technology, politics, 'hit')

        def make_entry(snap, profile):
            return dict(snapshot_id=snap['id'], game_date=snap['game_date'],
                        entry_type='checkpoint', title='Checkpoint', body='Body',
                        government_type=None, authority=None, origin=None,
                        ethics=None, civics=None)

        def log(message):
            messages.append(str(message))

        context = {
            'Database': FakeDB,
            'Path': Path,
            'time': time,
            'activity': log,
            'warning': log,
            'error': log,
            'format_duration': lambda s: f'{s:.3f}s',
            '_campaign_context': lambda db, cid: (
                {'empire_name': 'Commonwealth of Man', 'archive_dir': temp},
                Path(temp) / 'source.sav', Path(temp) / 'cache'),
            '_cache_counter': lambda: {'hit': 0, 'extend': 0, 'miss': 0},
            '_record_cache_status': lambda cache, key: cache.__setitem__(key, cache.get(key, 0) + 1),
            '_cache_summary': lambda cache: 'Cache mocked',
            '_format_parse_timings': lambda *a: 'mocked',
            'load_or_parse_snapshot': parser,
            '_build_entry': make_entry,
            'transition_data': lambda *a, **kw: {},
            'leader_transition_data': lambda *a, **kw: {},
            'world_transition_data': lambda *a, **kw: {},
            'politics_transition_data': lambda *a, **kw: {},
            'capture_observation': lambda *a: {'cached': True},
            '_record_performance_sample': lambda *a: None,
            '_diagnostics_dir': lambda *a: Path(temp),
            'promote_notification_deaths_in_database': lambda *a, **kw: {'confirmed': 0},
            'historical_notification_deaths': lambda *a: 0,
            'write_notification_death_diagnostic': lambda *a: None,
            'write_politics_database_diagnostic': lambda *a: SimpleNamespace(name='Politics_Debug.txt'),
        }
        process = load_processing_function(SOURCE, context)
        if progress_provided:
            result = process(db, 1, progress=lambda i, n, msg: observed_progress.append((i, n, msg)))
        else:
            result = process(db, 1)

        assert result['processed'] == 2, result
        assert result['remaining'] == 0, result
        assert result['errors'] == [], result
        assert db.done == {519, 520}, db.done
        assert len(db.entries) == 2 and {e['snapshot_id'] for e in db.entries} == {519, 520}
        assert all(e['game_date'] == '2327.01.08' for e in db.entries)
        assert (519, 'distinct-hash-519') in loaded
        assert (520, 'distinct-hash-520') in loaded
        assert db.checkpoints == 1
        assert len(observed_progress) == (2 if progress_provided else 0)
        assert not any("name 'progress' is not defined" in s for s in messages)
        # Subsequent polling must not mark either snapshot a second time.
        repeat = process(db, 1)
        assert repeat['processed'] == 0 and len(db.entries) == 2


def run():
    compile(SOURCE.read_bytes(), str(SOURCE), 'exec')
    run_once(progress_provided=False)
    run_once(progress_provided=True)
    print('PASS v0.0.82.1: two same-date distinct saves processed independently; '
          'optional callback works; subsequent poll idempotent; no save/database access')


if __name__ == '__main__':
    run()
