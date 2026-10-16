"""v0.0.66 parser-index integrity, bounded lifetime, and death-audit checks.

Runs without any private campaign data; optional fixture comparison is documented
in docs/RELEASE_v0.0.66.md.  No save, database or cached data is altered.
"""
from __future__ import annotations

import random
import re
import tempfile
from pathlib import Path

from historian.core.stellaris_text import (
    _PARSE_INDEX,
    _extract_braced_after,
    _find_named_block,
    _indented_numeric_record,
    _numeric_record,
    _top_numeric_records,
    indexed_scan_scope,
)
from historian.domains.people.notification_deaths import write_notification_death_diagnostic


def _reference_braced_after(text: str, token_start: int) -> str | None:
    brace = text.find('{', token_start)
    if brace < 0:
        return None
    depth, quoted, escaped = 0, False, False
    for index in range(brace, len(text)):
        c = text[index]
        if quoted:
            if escaped:
                escaped = False
            elif c == '\\':
                escaped = True
            elif c == '"':
                quoted = False
        elif c == '"':
            quoted = True
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return text[brace+1:index]
    return None


def _reference_numeric(block: str, key: int) -> str | None:
    m = re.search(rf'(?m)^\s*{key}\s*=\s*\{{', block)
    return _reference_braced_after(block, m.start()) if m else None


def _reference_indented(block: str, key: int) -> str | None:
    first = re.search(r'(?m)^([ \t]*)\d+\s*=\s*\{', block)
    if not first:
        return None
    m = re.search(rf'(?m)^{re.escape(first.group(1))}{key}\s*=\s*\{{', block)
    return _reference_braced_after(block, m.start()) if m else None


def test_syntax() -> None:
    cases = [
        'head={ a={ nested={1=2} } } trail',
        'outer = { quote="x{y}\\\"z" next={ good="value" } }',
        'obj={ esc="\\\\\"" after={ nested={ yup=yes } } }',
        'stuff={ unclosed={',
        'no brace at all',
        '1={ mixed="a\\\\\\\"b" { c=1 } }',
    ]
    rng = random.Random(66)
    def node(depth: int) -> str:
        inner = ('{ deeply }', '{not a brace}', 'normal', 'escaped \\\" quote')
        parts = []
        for i in range(rng.randint(2, 8)):
            if depth < 4 and rng.random() < 0.55:
                parts.append(f'field{i}={{ {node(depth + 1)} }}')
            else:
                parts.append(f'field{i}="{rng.choice(inner)}"')
        return '\n'.join(parts)
    cases.extend(f'outer={{\n{node(0)}\n}}' for _ in range(30))
    for case in cases:
        for offset in (0, min(5,len(case))):
            assert _extract_braced_after(case, offset) == _reference_braced_after(case, offset), case


def test_indexed_semantics() -> None:
    records = []
    for i in range(150):
        nested = f'  {1000 + i}={{ fake={i} }}\n' if i % 3 == 0 else ''
        records.append(f'  {i}={{\n    name="Some {{words}} {i}"\n{nested}  }}\n')
    block = ''.join(records)  # Smaller than cache threshold: exercise no-cache path.
    for i in (149, 11, 0, 28, 11, 999999, 149):
        assert _numeric_record(block, i) == _reference_numeric(block, i)
        assert _indented_numeric_record(block, i) == _reference_indented(block, i)
    assert list(_top_numeric_records(block)) == [
        (i, _reference_numeric(block, i)) for i in range(150)
    ]
    huge = block * 40  # Cache is activated. Duplicate IDs retain earliest match.
    with indexed_scan_scope():
        for i in (149, 11, 0, 28, 11, 999999, 149):
            assert _numeric_record(huge, i) == _reference_numeric(huge, i)
            assert _indented_numeric_record(huge, i) == _reference_indented(huge, i)
        first = _find_named_block('foo={\n' + huge + '\n}\n', 'foo')
        second = _find_named_block('foo={\n' + huge + '\n}\n', 'foo')
        assert first == second
        assert _PARSE_INDEX.get() is not None
    assert _PARSE_INDEX.get() is None, 'Save-scoped index leaked past its lifetime'


def test_historical_death_diagnostic() -> None:
    with tempfile.TemporaryDirectory() as temp:
        rows = [
            dict(leader_id=i, leader_name=name, death_date=date,
                 evidence_kind='notification_leader_death_named',
                 first_absent_date=None, reason=None)
            for i, name, date in (
                (1, 'Roberto Ruiz', '2245.09.08'),
                (2, 'Sidney Beauclair', '2257.02.13'),
                (3, 'Anika Shastri', '2264.04.28'),
                (4, 'Hong Lin', '2277.04.23'),
            )
        ]
        path = write_notification_death_diagnostic(
            Path(temp),
            {"promotions": [], "rejected": [], "raw_reads": 0,
             "historical_confirmed": rows},
        )
        contents = path.read_text()
        assert 'Confirmed historical notification-derived deaths in SQLite: 4' in contents
        assert 'Newly promoted deaths in this pass: 0' in contents
        assert all(row['leader_name'] in contents for row in rows)


if __name__ == '__main__':
    test_syntax()
    test_indexed_semantics()
    test_historical_death_diagnostic()
    print('v0.0.66 parser integrity / scoped cache / historic deaths: PASS')
