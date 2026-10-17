"""Read-only regression checks for the Windows console banner hotfix."""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BannerV0871Test(unittest.TestCase):
    def test_banner_ascii_only_and_no_replacement_glyphs(self):
        raw = (ROOT / "assets" / "stellaris_banner.txt").read_bytes()
        text = raw.decode("ascii")
        self.assertNotIn("\ufffd", text)
        self.assertNotIn("?", text)
        rows = [line for line in text.splitlines() if "#" in line]
        self.assertEqual(len(rows), 7)
        self.assertTrue(all(len(row) <= 78 for row in rows))
        self.assertIn("H I S T O R I A N", text)
        self.assertIn("by PillBoxUK", text)

    def test_launcher_loads_banner_and_shows_correct_version(self):
        launcher = (ROOT / "start.bat").read_text(encoding="utf-8")
        self.assertIn('type "assets\\stellaris_banner.txt"', launcher)
        self.assertIn("Stellaris Historian v0.0.90", launcher)
        self.assertIn("STELLARIS HISTORIAN v0.0.90", launcher)

    def test_python_and_manifest_versions_agree(self):
        version = (ROOT / "historian" / "__init__.py").read_text()
        manifest = json.loads((ROOT / "historian_manifest.json").read_text())
        self.assertIn('0.0.90',version)
        self.assertEqual(manifest["version"], "0.0.90")


if __name__ == "__main__":
    unittest.main()
