"""Static deployment checks (not real-browser screenshot assertions)."""
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
class ThemeReleaseTests(unittest.TestCase):
    def test_theme_on_static_pages(self):
        for name in ('campaign.html','splash.html','imperial_dashboard.html','database_explorer.html'):
            with self.subTest(name=name):
                text=(ROOT/'static'/name).read_text('utf-8')
                self.assertIn('/static/historian-theme.css?v=087',text)
                self.assertIn('/static/historian-theme.js?v=087',text)
    def test_theme_on_generated_html(self):
        for name in ('timeline','journal','scribes','annual_census','government_people','war_journal','empire_archive','time_machine','interactive_timeline','research_history','civic_frontier'):
            with self.subTest(name=name):
                text=(ROOT/'historian'/(name+'.py')).read_text('utf-8')
                self.assertTrue('/static/historian-theme.css?v=087' in text or '/static/historian-theme.css?v=089' in text or '/static/historian-theme.css?v=090' in text)
                self.assertTrue('/static/historian-theme.js?v=087' in text or '/static/historian-theme.js?v=089' in text or '/static/historian-theme.js?v=090' in text)
    def test_both_close_buttons_use_shared_close(self):
        for page in ('campaign','splash'):
            text=(ROOT/'static'/(page+'.js')).read_text('utf-8')
            self.assertIn('window.HistorianClose(closeButton, status)',text)
            self.assertNotIn('You can close this browser tab.',text)
    def test_version(self):
        self.assertIn('0.0.90',(ROOT/'historian/__init__.py').read_text('utf-8'))
    def test_no_user_saves_or_db(self):
        self.assertFalse((ROOT/'data').exists())
if __name__=='__main__': unittest.main()
