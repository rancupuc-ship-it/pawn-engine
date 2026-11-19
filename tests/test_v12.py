import html
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import updates


class UpdateCheck(unittest.TestCase):
    def test_version_compare(self):
        self.assertTrue(updates.is_newer("1.3", "1.2"))
        self.assertTrue(updates.is_newer("v1.2.1", "1.2"))
        self.assertTrue(updates.is_newer("2.0", "1.9.9"))
        self.assertFalse(updates.is_newer("1.2", "1.2.0"))
        self.assertFalse(updates.is_newer("1.1", "1.2"))
        self.assertEqual(updates.parse_version("v1.10"), (1, 10))

    def test_statuses(self):
        newer = updates.check("me/pawn", fetch=lambda r: {"tag_name": "v9.0", "body": "big"}, current="1.2")
        self.assertEqual(newer["status"], "newer")
        self.assertEqual(newer["latest"], "9.0")
        self.assertTrue(newer["url"].endswith("/me/pawn/releases/latest/download/PawnEngine-Setup.exe"))
        self.assertEqual(updates.check("me/pawn", fetch=lambda r: {"tag_name": "v1.2"}, current="1.2")["status"], "current")
        self.assertEqual(updates.check("", current="1.2")["status"], "unset")

    def test_offline_never_raises(self):
        def boom(repo):
            raise OSError("no internet")
        self.assertEqual(updates.check("me/pawn", fetch=boom)["status"], "offline")
        self.assertEqual(updates.check("me/pawn", fetch=lambda r: {})["status"], "offline")

    def test_release_json_is_valid(self):
        data = json.loads((ROOT / "release.json").read_text())
        self.assertIn("repo", data)


class OpenFromCommandLine(unittest.TestCase):
    def test_project_arg(self):
        import main
        d = Path(tempfile.mkdtemp())
        (d / "project.pawnproj").write_text("{}")
        self.assertEqual(main.project_arg([str(d)]), d)
        self.assertEqual(main.project_arg([str(d / "project.pawnproj")]), d)
        self.assertEqual(main.project_arg(["--play", "x"]), None)
        self.assertIsNone(main.project_arg([str(d / "nope")]))
        self.assertIsNone(main.project_arg([]))


class ShippingFiles(unittest.TestCase):
    def test_workflows_are_valid_yaml(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        for f in (ROOT / ".github" / "workflows").glob("*.yml"):
            data = yaml.safe_load(f.read_text())
            self.assertIn("jobs", data, f.name)

    def test_installer_script(self):
        iss = (ROOT / "installer" / "PawnEngine.iss").read_text()
        for needle in ("AppVersion={#AppVersion}", "OutputBaseFilename=PawnEngine-Setup", ".pawnproj", "[Icons]", "UninstallDisplayIcon"):
            self.assertIn(needle, iss)
        self.assertTrue((ROOT / "assets" / "icon.ico").exists())

    def test_build_command_bundles_release_json(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import build_app
        cmd = " ".join(build_app.command())
        self.assertIn("release.json", cmd)
        self.assertIn("pawn_core", cmd)
        self.assertTrue((ROOT / "release.json").exists())

    def test_site_code_sample_is_real_pawn(self):
        from pawnlang import parse
        page = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
        code = html.unescape(re.sub(r"<[^>]+>", "", re.search(r"<pre>(.*?)</pre>", page, re.S).group(1)))
        parse(code)
        for img in ("screenshot-dark.png", "screenshot-light.png", "icon.png"):
            self.assertTrue((ROOT / "site" / img).exists(), img)


if __name__ == "__main__":
    unittest.main()
