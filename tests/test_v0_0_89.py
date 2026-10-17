"""v0.0.89: British-English narrative, evidence-only milestones and intelligence."""
from pathlib import Path
from historian.timeline import (
    _four_year_census_dates, _group_service_anniversaries, _long_date,
    _people_government_milestones, _TIMELINE_STYLE,
)
from historian.founding_chapter import founding_chapter
from historian.civic_frontier import _observed_player_spy_networks, VERSION, render_intelligence_history

ROOT=Path(__file__).resolve().parents[1]

def census(year, available=True, opening=False):
    return {'year':str(year),'date':f'{year}.01.01','opening':opening,
            'available':available,'people':[],
            'source':{'game_date':f'{year}.01.01','sha256':'b'*64,'snapshot_id':year} if available else None}


def test_four_yearly_census_keeps_annual_evidence_separate():
    rows=[census(y,opening=(y==2200)) for y in range(2200,2210)]
    assert _four_year_census_dates(rows)=={'2200.01.01','2204.01.01','2208.01.01'}
    # An event in June 2202 gives a new January census in 2203, never in June.
    assert '2203.01.01' in _four_year_census_dates(rows, {'2202.06.15'})
    rows[3]['available']=False
    assert '2203.01.01' not in _four_year_census_dates(rows, {'2202.06.15'})
    assert '2204.01.01' in _four_year_census_dates(rows, {'2202.06.15'})


def test_group_people_with_individual_audit_trail():
    entries = [dict(date='2205.01.01',years=5,name=name,leader_id=i,role='Official',
                    group='Council',office=office,evidence=f'snapshot #{i}')
               for i,name,office in [(11,"K'Vara Korik",'First Speaker'),
                                      (12,'D\'Kheera','Head of Research'),
                                      (13,'Sikirooka','Minister of Defence')]]
    grouped = _group_service_anniversaries(entries,'Veyran Shadow Concord 2')
    assert len(grouped)==1
    assert all(name in grouped[0].body for name in ("K'Vara Korik", "D'Kheera", 'Sikirooka'))
    assert 'snapshot #11' in grouped[0].evidence and 'snapshot #13' in grouped[0].evidence
    assert 'uninterrupted' in grouped[0].body or 'continuous' in grouped[0].body


def test_uk_dates_and_articles_without_campaign_invention():
    assert _long_date('2202.01.01')=='1 January 2202'
    assert _long_date('2210.12.03')=='3 December 2210'
    text=founding_chapter(dict(name='Veyran Shadow Concord 2',species_name='Veyran',
                               species_group='avian',government='gov_executive_committee',
                               homeworld='Veyra Prime'))
    assert 'an avian people' in text
    assert 'an executive committee' in text


def test_player_only_spy_networks_and_passive_not_claimed_active():
    save = '''spy_networks=\n{\n 0={\n owner=0\n target=12\n }\n 1={\n owner=3\n target=0\n infiltration=22\n }\n 2={\n owner=0\n target=19\n infiltration=12.5\n spymaster=85\n }\n 3={\n owner=0\n target=4294967295\n }\n}'''
    got=_observed_player_spy_networks(save,0)
    assert list(got)==['0','2']
    assert got['0']['active_evidence'] is False
    assert got['2']['active_evidence'] is True
    assert got['2']['spymaster']==85
    assert got['2']['infiltration']==12.5
    assert VERSION==4


def test_no_readability_loss_in_pdf_under_dark_theme():
    style=(ROOT/'static/historian-theme.css').read_text('utf-8')
    assert 'FORCE readable printed history' in style
    assert 'html[data-historian-theme="dark"] .event-main' in style
    assert '.people-note{display:none!important}' in _TIMELINE_STYLE
    assert 'background:#fff!important' in style
