"""Pure editorial and local Annals export tests; no actual saves or user DB."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

from historian import timeline as t
from historian.annals_editorial import date_label, month_groups, period_extract, reading_importance


def e(date, title, body, category='Science', importance=60):
    return t.TimelineEvent(date,title,body,category,importance,
                           evidence='Source save hash abc; archived assertion',date_kind='first_observed',source='fixture')


def test_dating_does_not_promote_observation_to_exact():
    assert date_label('first_observed')[0]=='First recorded by'
    assert date_label('exact_save_field')[0]=='Dated event'
    assert date_label('starting_state')[0]=='Already recorded at the opening'
    assert date_label('unrecognised_key')[0]=='Archival date'


def test_monthly_groups_use_only_real_dates_and_body():
    items=[e('2200.03.19','Event B','An expedition made its first landfall.'),
           e('2200.01.01','Initial view','The civilisation had a homeworld.'),
           e('2200.03.02','Event A','A station was founded.')]
    grouped=month_groups(items)
    assert [(a,b) for a,b,_ in grouped]==[('2200.01','January'),('2200.03','March')]
    text=' '.join(period_extract(grouped[1][2]))
    assert 'station was founded' in text and 'expedition' in text
    assert 'because' not in text


def test_safety_and_importance():
    ordinary=e('2202.01.01','Research Station established','A station was built.','Infrastructure',80)
    historic=e('2202.01.01','First colony founded','A settlement was established.','Expansion',52)
    assert reading_importance(ordinary)<=39
    assert reading_importance(historic)>=85
    assert not (Path(__file__).resolve().parents[1]/'data').exists()


def test_render_produces_british_editorial_and_browser_only_personalisation(tmp_path):
    world=e('2200.01.01','First colony founded','A new settlement was established.','Expansion',85)
    spy=e('2201.07.13','Spy network observed','An intelligence network was recorded.','Diplomacy',67)
    fake=SimpleNamespace(combat_snapshots=[])
    class DB:
        def campaign(self, cid):
            return {'empire_name':'Test Concord','first_game_date':'2200.01.01',
                    'latest_game_date':'2201.07.13','archive_dir':str(tmp_path)}
    with (patch.object(t,'_collect_events',return_value=([world,spy],{})),
          patch.object(t,'_war_spans',return_value=[]),
          patch.object(t,'build_presentation_history',return_value=fake)):
        page=t.render_timeline(DB(),17)
    html=page.read_text('utf-8')
    assert 'January' in html and 'July' in html
    assert 'reading-level' in html and 'export-html' in html
    assert 'PERSONAL ANNOTATION' in html and 'Stored in this browser only' in html
    assert 'Source save hash' in html and 'First recorded by' in html
    assert 'data-importance="85"' in html
    assert 'data-importance="67"' in html
    assert html.count('class="event"')==2
    assert 'year-overview' in html and 'month-lead' in html
    assert 'Screenshot' not in html
    assert '<title>Test Concord' in html
    assert 'historian.annals.personal.v090.' in html
    assert 'historian-theme.css?v=090' in html
    assert 'historian.annals.personal.v090.' in t._TIMELINE_JS


def test_script_syntax():
    p=subprocess.run(['node','--check','-'],input=t._TIMELINE_JS,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
