"""v0.0.80: machine-empire voice, conditional name grammar, semantic deduplication."""
from historian.timeline import (_clean_stellaris_name,_clean_legacy_names,_deduplicate_semantic_events,
                               _opening_narrative,TimelineEvent,_aux_ship_prose,_story_prose)
from historian.historical_events import HistoricalEvent
from unittest.mock import patch
from types import SimpleNamespace

def t(date,title,body,category='Navy',importance=60,evidence='native evidence'):
    return TimelineEvent(date,title,body,category,importance,evidence=evidence)

def run():
    raw='Sextus&!masc $1$ Cloelia|||masc:$1$ Cloelius'
    assert _clean_stellaris_name(raw, 'male')=='Sextus Cloelius'
    assert _clean_stellaris_name(raw, 'female')=='Sextus Cloelia'
    assert _clean_stellaris_name(raw, None)=='Sextus'
    gendered = {'name':raw,'gender':'male'}
    e = t('2200.10.01',raw+' takes command',raw+' assumes command', 'People')
    clean=_clean_legacy_names([e],{1:gendered})[0]
    assert clean.title=='Sextus Cloelius takes command' and raw not in clean.body
    assert clean.evidence==e.evidence
    rows=[t('2200.02.26','Agathemerus commissioned','Agathemerus, a science ship, entered service.'),
          t('2200.02.26','Agathemerus enters service','The science ship Agathemerus entered service. It strengthened expeditions charting distant stars.','Exploration'),
          t('2200.04.01','Ancient Capsule Analysis: research project recorded','Ancient Capsule Analysis appears in the archive.','Story'),
          t('2200.04.01','Ancient Capsule Analysis','Analysis of the orbital capsule revealed coordinates of previously unknown celestial bodies.','Story')]
    de=_deduplicate_semantic_events(rows)
    assert len(de)==2,de
    assert any('coordinates' in x.body for x in de)
    assert any('expeditions' in x.body for x in de)
    assert all('research project recorded' not in x.title for x in de)
    machine=SimpleNamespace(__getitem__=lambda self,k: None)
    class DB:
        def history_entries(self,_):
            return [dict(entry_type='founding',government_type='gov_machine_intelligence',
                    authority='auth_machine_intelligence',ethics='ethic_gestalt_consciousness',
                    civics='civic_machine_chosen,civic_machine_built_to_last', origin='origin_treasure_hunters')]
    original=_opening_narrative(DB(),1,'Quentian Animus 4','2200.01.01')
    assert 'machine civilisation' in original and 'treasure' not in original.lower()
    assert 'relics' in original and 'scientist' not in original.lower()
    event=HistoricalEvent('2200.02.26','military','ship_commissioned',
            'Science Ship Agathemerus Commissioned',
            'The science ship Agathemerus entered service on 2200.02.26',
            'high','exact_save_field','ship_history',75)
    sh=_aux_ship_prose(event,'Quentian Animus 4')
    assert 'she ' not in sh.body.lower() and 'it strengthened' in sh.body.lower()
    story=HistoricalEvent('2200.04.01','science','special_project_observed',
            'Ancient Capsule Analysis','Ancient Capsule Analysis appears in the record',
            'high','first_observed','science_history',85,(('project_key','CAPSULE_ANALYSIS'),))
    with patch('historian.timeline.game_description',return_value=(
          'The analysis of an orbital capsule revealed an ancient chart and unfamiliar coordinates.',
          'localisation')):
        desc=_story_prose(story,'Quentian Animus 4')
    assert 'ancient chart' in desc.body and 'began investigating' not in desc.body
    print('PASS v0.0.80: gender variants, old name display, no invented names, ship and story dedup, machine voice, contextual project')

if __name__=='__main__':run()
