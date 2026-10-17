"""Regression: the canonical War Journal never trusts manually supplied screenshots or notes."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from historian.war_journal import (
    FormalWarRecord, _war_display_title, _war_victory_annotation,
    _formal_war_html, _war_index_html, _war_chronology_html, render_war_journal,
)
from historian.presentation_history import PresentationHistory

war = FormalWarRecord(
    war_id=83886080, name='War 83886080', start_date='2293.04.26',
    first_observed='2293.07.01', last_observed='2300.07.01',
    first_absent_after_last='2300.10.01', player_side='attacker',
    attacker_war_goal='humiliation', defender_war_goal='conquest',
    attacker_country_ids=(0,), defender_country_ids=(16777226,),
)
assert _war_victory_annotation(war, 'Commonwealth of Man') is None
assert _war_display_title(war, 'Commonwealth of Man')[0] == 'War of Humiliation'
assert _war_display_title(war, 'Commonwealth of Man', {16777226:'Hulfiran United Stars'})[0] == 'War of Humiliation against Hulfiran United Stars'
native = replace(war, name='Native war name')
assert _war_display_title(native, 'Commonwealth of Man')[0] == 'Native war name'
index = _war_index_html([war], 'Commonwealth of Man')
card = _formal_war_html(war, '2300.10.01', 'Commonwealth of Man')
chron = _war_chronology_html(war, {'notification_date':'2300.08.15'})
combined = index + card + chron
assert '2300.08.15' not in combined
assert 'screenshot-confirmed' not in combined.lower()
assert 'Victory notice' not in combined
assert 'war-confirmation' not in combined
assert 'Ending observed between 2300.07.01 and 2300.10.01' in card
assert 'first later archive without this war' in chron.lower()

# If local manual annotation files exist, they must never be opened. The code
# must continue working even if such files are absent or corrupted.
real_read_text = Path.read_text
def refuse_manual_annotations(self, *args, **kwargs):
    if self.name in ('war_name_annotations.json', 'war_party_names.json', 'war_outcome_annotations.json'):
        raise AssertionError(f'Forbidden external annotation read: {self.name}')
    return real_read_text(self, *args, **kwargs)
with patch.object(Path, 'read_text', new=refuse_manual_annotations):
    assert _war_display_title(war, 'Commonwealth of Man')[0] == 'War of Humiliation'
    assert _war_victory_annotation(war, 'Commonwealth of Man') is None
    with TemporaryDirectory() as temp:
        class DB:
            def campaign(self, campaign_id):
                return {'archive_dir':temp, 'empire_name':'Commonwealth of Man',
                        'latest_game_date':'2300.10.01'}
        with patch('historian.war_journal.build_presentation_history',
                   return_value=PresentationHistory((),(),(),(),(),(),())):
            generated=render_war_journal(DB(),1)
        html=generated.read_text(encoding='utf-8')
        assert 'Save-only history:' in html
        assert 'SCREENSHOT EVIDENCE' not in html
        assert 'manually entered annotations are not consulted' in html.lower()
print('ALL v0.0.71.1 SAVE-ONLY WAR HISTORY TESTS PASS')
