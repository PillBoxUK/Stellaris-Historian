"""v0.0.83 local, *read-only* SQLite browser for Historian.

No SQL-changing operation is exposed. Paths are selected by an explicit list,
not user-supplied filesystem paths. Keep this secondary to the Imperial Annals.
"""
from __future__ import annotations
import csv
import io
import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

MAX_PAGE = 200
MAX_EXPORT = 50000
MAX_TEXT = 12000


def databases(main_db: Path, campaign_archive: Path | None = None) -> dict[str, Path]:
    result = {'historian': Path(main_db)}
    if campaign_archive:
        root = Path(campaign_archive)
        for key, filename in (
            ('civic', 'Civic_Frontier_History.sqlite3'),
            ('research', 'Research_History.sqlite3'),
        ):
            p = root / filename
            if p.is_file():
                result[key] = p
    return result


@contextmanager
def readonly_connection(path: Path):
    if not path.is_file():
        raise FileNotFoundError('Database is not available.')
    # URL escaping handles Windows drives, spaces, and Unicode file names.
    uri = path.resolve().as_uri() + '?mode=ro'
    conn = sqlite3.connect(uri, uri=True, timeout=5, check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA query_only=ON')
        conn.execute('PRAGMA busy_timeout=2000')
        yield conn
    finally:
        conn.close()


def _names(conn) -> list[str]:
    return [str(r[0]) for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name COLLATE NOCASE"
    )]


def _identifier(conn, table: str) -> str:
    if table not in _names(conn):
        raise ValueError('Unknown database table.')
    return '"' + table.replace('"', '""') + '"'


def _campaign_filter(conn, table: str, campaign_id: int | None):
    if campaign_id is None:
        return '', []
    cols = [r[1] for r in conn.execute('PRAGMA table_info(' + _identifier(conn, table) + ')')]
    if 'campaign_id' in cols:
        return ' WHERE "campaign_id" = ?', [int(campaign_id)]
    if table == 'campaigns' and 'id' in cols:
        return ' WHERE "id" = ?', [int(campaign_id)]
    return '', []


def available_tables(path: Path, campaign_id: int | None = None) -> list[dict]:
    with readonly_connection(path) as conn:
        result = []
        for table in _names(conn):
            q = _identifier(conn, table)
            where, args = _campaign_filter(conn, table, campaign_id)
            count = conn.execute('SELECT COUNT(*) FROM ' + q + where, args).fetchone()[0]
            result.append({'name': table, 'rows': count, 'fields': len(conn.execute('PRAGMA table_info(' + q + ')').fetchall())})
        return result


def schema(path: Path, table: str) -> dict:
    with readonly_connection(path) as conn:
        q = _identifier(conn, table)
        columns = [dict(row) for row in conn.execute('PRAGMA table_info(' + q + ')')]
        indexes = [dict(row) for row in conn.execute('PRAGMA index_list(' + q + ')')]
        return {'table': table, 'columns': columns, 'indexes': indexes}


def _value(v):
    if isinstance(v, bytes):
        return '0x' + v[:512].hex() + ('…' if len(v)>512 else '')
    if v is not None and not isinstance(v, (int, float, str, bool)):
        return str(v)
    if isinstance(v, str) and len(v)>MAX_TEXT:
        return v[:MAX_TEXT] + '… [truncated; use CSV export for full data]'
    return v


def table_rows(path: Path, table: str, *, campaign_id: int | None = None,
               offset: int = 0, limit: int = 50, search: str = '') -> dict:
    if offset < 0 or offset > 10000000 or not 1 <= limit <= MAX_PAGE or len(search)>160:
        raise ValueError('Invalid pagination or search.')
    with readonly_connection(path) as conn:
        q = _identifier(conn, table)
        cols = [r[1] for r in conn.execute('PRAGMA table_info(' + q + ')')]
        where, args = _campaign_filter(conn, table, campaign_id)
        if search.strip():
            # Parameterised substring search across bounded textual columns.
            searchable = [c for c in cols if c.lower() in {
                'name','title','body','game_date','event_type','status','leader_class','empire_name',
                'archive_filename','subject_name','category','date_kind','assignment_name'}]
            if not searchable:
                searchable = cols[:5]
            sql_term = '%' + search.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_') + '%'
            parts = ['CAST("' + c.replace('"','""') + '" AS TEXT) LIKE ? ESCAPE \'\\\'' for c in searchable]
            where += (' AND ' if where else ' WHERE ') + '(' + ' OR '.join(parts) + ')'
            args.extend([sql_term] * len(parts))
        total = conn.execute('SELECT COUNT(*) FROM '+q+where, args).fetchone()[0]
        cursor = conn.execute('SELECT * FROM '+q+where+' LIMIT ? OFFSET ?', args+[limit,offset])
        return {'table': table, 'columns': [d[0] for d in cursor.description],
                'rows': [[_value(v) for v in row] for row in cursor.fetchall()],
                'total': total, 'offset': offset, 'limit': limit}


_ALLOWED_AUTH = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}
if hasattr(sqlite3, 'SQLITE_RECURSIVE'):
    _ALLOWED_AUTH.add(sqlite3.SQLITE_RECURSIVE)


def select_query(path: Path, query: str) -> dict:
    query = query.strip()
    if len(query)>6000 or not re.match(r'(?is)^\s*(SELECT|WITH)\b', query):
        raise ValueError('Only SELECT and WITH … SELECT queries are permitted.')
    with readonly_connection(path) as conn:
        def authorizer(action, arg1, arg2, dbname, trigger):
            return sqlite3.SQLITE_OK if action in _ALLOWED_AUTH else sqlite3.SQLITE_DENY
        conn.set_authorizer(authorizer)
        # Stop expensive queries without locking Historian's live writer.
        import time
        deadline = time.monotonic() + 2.0
        conn.set_progress_handler(lambda: int(time.monotonic()>deadline), 1000)
        cursor = conn.execute(query)
        if cursor.description is None:
            raise ValueError('Query did not return data.')
        rows = cursor.fetchmany(MAX_PAGE+1)
        return {'columns': [d[0] for d in cursor.description],
                'rows': [[_value(v) for v in row] for row in rows[:MAX_PAGE]],
                'truncated': len(rows)>MAX_PAGE, 'limit': MAX_PAGE}


def csv_export(path: Path, table: str, campaign_id: int | None = None) -> str:
    with readonly_connection(path) as conn:
        q = _identifier(conn, table)
        where, args = _campaign_filter(conn, table, campaign_id)
        cursor = conn.execute('SELECT * FROM ' + q + where + ' LIMIT ?', args+[MAX_EXPORT+1])
        stream = io.StringIO(newline='')
        writer = csv.writer(stream)
        writer.writerow([d[0] for d in cursor.description])
        # CSV injection avoidance when opened in spreadsheets.
        for idx,row in enumerate(cursor):
            if idx >= MAX_EXPORT:
                raise ValueError('Export exceeds the 50,000-row safety limit.')
            writer.writerow([('\''+v) if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@'))
                             else v.hex() if isinstance(v,bytes) else v for v in row])
        return stream.getvalue()
