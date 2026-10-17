"""Read-only historian evidence/publication audit, v0.0.85.

Usage from StellarisHistorian root:
  .venv/Scripts/python.exe scripts/audit_annals_v0_0_85.py --campaign-id 7
  .venv/Scripts/python.exe scripts/audit_annals_v0_0_85.py --list-campaigns

This prints findings to the console. It never modifies archives, SQLite,
Ironman saves, tables, processed flags, caching, or timeline HTML.
"""
from __future__ import annotations
import argparse
import json
import re
import sqlite3
from pathlib import Path

PLACEHOLDERS = re.compile(r'PREFIX_NAME_FORMAT|\b(?:NAME|SHIP|FLEET|LEADER|COUNTRY|PLANET|SYSTEM)_[A-Z][A-Z0-9_]*\b|\$[^\s$]+\$|\[(?:Root|This|Target|From)\.[^]]+\]', re.I)


def audit(db: Path, campaign_id: int) -> dict:
    """Inspect only persisted metadata and generated output, never source saves."""
    conn = sqlite3.connect('file:' + db.resolve().as_posix() + '?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    try:
        c = conn.execute('SELECT id,empire_name,first_game_date,latest_game_date,archive_dir FROM campaigns WHERE id=?',(campaign_id,)).fetchone()
        if c is None:
            raise ValueError(f'Campaign {campaign_id} is not in the database')
        rows=conn.execute('SELECT game_date,processed FROM snapshots WHERE campaign_id=? ORDER BY game_date,id',(campaign_id,)).fetchall()
        processed=[str(s['game_date']) for s in rows if s['processed']]
        unprocessed=[str(s['game_date']) for s in rows if not s['processed']]
        observed={d for d in processed}
        start=str(c['first_game_date'] or '')
        last=str(c['latest_game_date'] or '')
        annual=[f'{y}.01.01' for y in range(int(start[:4]),int(last[:4])+1) if start <= f'{y}.01.01' <= last] if len(start)>=10 and len(last)>=10 else []
        path=Path(str(c['archive_dir']))/'Empire_Timeline.html'
        warnings=[]
        if unprocessed: warnings.append(f'{len(unprocessed)} archived snapshots have not been processed. New history may be absent from the timeline.')
        if processed and max(processed)<last: warnings.append(f'Last processed date {max(processed)} is earlier than latest archive {last}.')
        missing=[d for d in annual if d not in observed]
        if missing: warnings.append(f'{len(missing)} exact 1 January archive dates are absent/untested: '+', '.join(missing[:8])+(' ...' if len(missing)>8 else ''))
        page={'path':str(path),'exists':path.is_file()}
        if path.is_file():
            html=path.read_text(encoding='utf-8', errors='replace')
            # Inspect *published article fronts*. JSON evidence intentionally
            # retains unresolved original source tokens and is not a narrative.
            from html import unescape
            article_fronts = re.findall(r'<article\s+class=\"event\".*?</article>', html, re.S|re.I)
            visible_prose = '\n'.join(unescape(re.sub(r'<[^>]+>', ' ', article)) for article in article_fronts)
            tokens=sorted(set(PLACEHOLDERS.findall(visible_prose)))
            page.update(bytes=len(html.encode('utf-8')),unresolved_tokens=tokens[:30])
            if tokens: warnings.append('Unresolved localisation tokens are present in timeline output: '+', '.join(tokens[:8]))
            if str(c['empire_name']).casefold() != 'commonwealth of man' and ('Commonwealth service' in visible_prose or 'Commonwealth territory' in visible_prose):
                warnings.append('A Commonwealth-only phrase is present in a non-Commonwealth timeline.')
        else:
            warnings.append('No generated Empire_Timeline.html found in the registered campaign archive.')
        return {'campaign_id':c['id'],'empire':c['empire_name'],'start':start,'latest_archived_date':last,
                'last_processed_date':max(processed) if processed else None,
                'archived_saves':len(rows),'processed_saves':len(processed),
                'unprocessed_saves':len(unprocessed),'year_boundaries_with_processed_saves':sum(d in observed for d in annual),
                'year_boundaries_without_exact_processed_saves':missing,
                'timeline':page,'warnings':warnings,
                'scope':'Archive metadata and published HTML only. No unprocessed save is read; a PDF or screenshot is never primary historical evidence.'}
    finally: conn.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',type=Path,default=Path('data/historian.db'))
    p.add_argument('--campaign-id',type=int)
    p.add_argument('--list-campaigns',action='store_true')
    opts=p.parse_args()
    if opts.list_campaigns:
        con=sqlite3.connect('file:'+opts.db.resolve().as_posix()+'?mode=ro',uri=True)
        try:
            for id_,empire in con.execute('SELECT id,empire_name FROM campaigns ORDER BY id'):
                print(f'{id_}: {empire}')
        finally: con.close()
    elif opts.campaign_id is not None:
        print(json.dumps(audit(opts.db,opts.campaign_id),ensure_ascii=False,indent=2))
    else:
        p.error('Choose --campaign-id N or --list-campaigns')
if __name__=='__main__':main()
