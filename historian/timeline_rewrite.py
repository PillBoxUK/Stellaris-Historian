"""Full evidence-and-narrative rebuild with a recoverable SQLite backup.

Every archived save is reviewed chronologically with current domain parsers,
reusing only version-valid per-save caches. All canonical source saves and
processed flags remain untouched. The final HTML is published atomically.
"""
from __future__ import annotations

from pathlib import Path
import json
import os
import tempfile
import zipfile
import sqlite3
import time
from .history_processor import review_campaign
from .native_milestones import capture_native_milestones
from .db import Database
from .story_text import catalogue_status
from .research_history import capture_observation, read_observations
from .civic_frontier import capture as capture_civic_frontier, read_observations as civic_observations
from .timeline import render_timeline


def rewrite_timeline(db: Database, campaign_id: int, progress=None) -> dict:
    campaign=db.campaign(campaign_id)
    if campaign is None: raise ValueError('Campaign not found')
    snapshots=db.all_snapshots(campaign_id)
    archive=Path(str(campaign['archive_dir']))
    cache=archive/'.historian_cache'
    missing=[]; failed=[]; cached=0; read=0
    research_added=0; research_cached=0; research_failed=[]; research_seconds=0.0
    civic_added=0; civic_cached=0; civic_failed=[]; civic_seconds=0.0
    if not snapshots:raise ValueError('There are no archived saves to rebuild')
    for n,row in enumerate(snapshots,1):
        source=Path(str(row['archive_path']))
        if not source.is_file():
            # A campaign archive can be moved; try the retained local folder.
            source=archive/str(row['archive_filename'])
        if not source.is_file():
            missing.append(str(row['archive_filename']))
        else:
            try:
                with zipfile.ZipFile(source) as z:
                    meta=z.read('meta').decode('utf-8','replace')
                    if 'date=' not in meta:
                        failed.append(f'{source.name}: no game date in metadata')
                    else:read+=1
                try:
                    detail=capture_observation(archive,source,str(row['sha256']))
                    research_cached += int(detail['cached'])
                    research_added += int(not detail['cached'])
                    research_seconds += detail['seconds']
                except Exception as exc:
                    research_failed.append(f'{source.name}: {exc}')
                try:
                    detail=capture_civic_frontier(archive,source,str(row['sha256']))
                    civic_cached+=int(detail['cached'])
                    civic_added+=int(not detail['cached'])
                    civic_seconds+=detail['seconds']
                except Exception as exc:
                    civic_failed.append(f'{source.name}: {exc}')
            except (OSError,KeyError,zipfile.BadZipFile) as exc:
                failed.append(f'{source.name}: {exc}')
        index=cache/(str(row['sha256'])+'.json')
        if index.is_file():cached+=1
        if progress and (n==1 or n%8==0 or n==len(snapshots)):
            progress(n,len(snapshots),f'Inspected {n}/{len(snapshots)} saves; research {research_added} new; civic/frontier {civic_added} new; {cached} core caches')
    if missing or failed:
        raise ValueError(f'Archive audit failed: {len(missing)} missing saves, {len(failed)} unreadable. Original timeline unchanged; see missing names in archive.')
    # Back up canonical SQLite before regenerating any derived tables. Do not
    # copy live SQLite/WAL files: the backup API captures a consistent snapshot.
    if progress:progress(len(snapshots),len(snapshots),'Preserving the original historical database…')
    backups=Path(db.path).parent/'autobackups'
    backups.mkdir(parents=True,exist_ok=True)
    stamp=time.strftime('%Y%m%d_%H%M%S')
    backup=backups/f'historian_pre_timeline_rebuild_{campaign_id}_{stamp}.sqlite3'
    with sqlite3.connect(str(db.path),timeout=60) as source, sqlite3.connect(str(backup)) as target:
        source.backup(target)
    # Re-derive EVERYTHING supported by the current parsers. Unlike the old
    # button, this rebuilds canonical *derived* evidence, not merely the page.
    result=review_campaign(db,campaign_id,progress=progress)
    if not result.get('rebuilt'):
        raise ValueError(f'Historical reconstruction stopped: {result.get("errors",[])[:3]}. Original database backup: {backup}')
    if progress:progress(len(snapshots),len(snapshots),'Recovering native milestones and composing the Imperial Annals…')
    # Archive's most recent processed save preserves cumulative player timeline
    # milestones. Publish only supported interpretation, never future scheduled
    # events or unrelated galaxy intelligence.
    latest=next((r for r in reversed(snapshots) if int(r['processed'])),None)
    native_total=0
    if latest is not None:
        path=Path(str(latest['archive_path']))
        if not path.is_file():path=archive/str(latest['archive_filename'])
        native=capture_native_milestones(archive,path,str(latest['sha256']))
        native_total=len(native.get('events',[]))
    rendered=render_timeline(db,campaign_id)
    status=catalogue_status()
    report={
      'version':'0.0.82','archived_saves_inspected':len(snapshots),
      'full_historical_rebuild':True, 'reviewed_by_current_parsers':result.get('reviewed',0),
      'rebuild_cache_hits':result.get('cache_hits',0),
      'rebuild_cache_reparsed':result.get('cache_misses',0)+result.get('cache_extends',0),
      'database_backup':str(backup),
      'native_timeline_milestones':native_total,
      'save_metadata_read':read,'parsed_snapshot_caches_present':cached,
      'missing_parsed_caches':len(snapshots)-cached,
      'story_localisation':status,
      'research_ledger_new':research_added,
      'research_ledger_reused':research_cached,
      'research_ledger_failed':research_failed[:50],
      'civic_frontier_new':civic_added, 'civic_frontier_reused':civic_cached,
      'civic_frontier_errors':civic_failed[:50],
      'civic_frontier_seconds':round(civic_seconds,2),
      'civic_frontier_observations':len(civic_observations(archive,snapshots)),
      'research_reparse_seconds':round(research_seconds,2),
      'research_observations_loaded':len(read_observations(archive,snapshots)),
      'unresolved_story_descriptions':rendered.read_text(encoding='utf-8').count('Full script description has not been located.'),
      'warning':'Native story popup choices not retained by the archive are not invented. Snapshot parsing caches are version-checked before reuse. An incomplete post-audit processing failure may require restoration from the automatic pre-rebuild SQLite backup.', 
      'timeline_path':str(rendered),'last_game_date':str(campaign['latest_game_date'] or '')
    }
    target=archive/'Timeline_Rewrite_Report.json'
    fd,tmp=tempfile.mkstemp(prefix='.timeline_audit_',suffix='.json',dir=archive)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(report,f,indent=2,ensure_ascii=False)
        os.replace(tmp,target)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return report
