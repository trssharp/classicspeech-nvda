"""Build provenance and publication workflow guards (never publishes)."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("package_addon", ROOT / "scripts/package_addon.py")
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class DevelopmentDeliveryTests(unittest.TestCase):
    def test_build_metadata_distinguishes_channel_from_preference(self):
        sha = "a" * 40
        self.assertEqual(package.build_metadata("20260928.7", "dev", sha),
                         {"version": "20260928.7", "channel": "dev", "commit": sha})
        self.assertEqual(package.build_metadata("2.0", "auto", "")["channel"], "stable")
        self.assertEqual(package.build_metadata("20260928.7", "auto", "")["channel"], "unknown")
        for version, channel, commit in [("2.0", "dev", sha), ("20260928.7", "dev", "abc"),
                                        ("20260230.1", "dev", sha), ("20260928.0", "dev", sha)]:
            with self.assertRaises(ValueError):
                package.build_metadata(version, channel, commit)

    def test_dev_publication_has_only_manual_trigger_and_write_only_at_publish(self):
        text = (ROOT / ".github/workflows/publish-dev.yml").read_text()
        trigger = text.split("on:\n", 1)[1].split("permissions:", 1)[0]
        self.assertIn("workflow_dispatch:", trigger)
        for forbidden in ("push:", "schedule:", "workflow_run:", "pull_request:", "workflow_call:"):
            self.assertNotIn(forbidden, trigger)
        before, publish = text.split("  publish:", 1)
        self.assertNotIn("contents: write", before)
        self.assertIn("contents: write", publish)
        self.assertIn("github.ref == 'refs/heads/dev'", before)
        self.assertIn("github.repository == 'trssharp/classicspeech-nvda'", before)
        self.assertIn("github.event_name == 'workflow_dispatch'", before)
        self.assertIn("needs: verify", publish)
        self.assertIn("--prerelease", publish)
        self.assertIn("--latest=false", publish)
        self.assertIn("--verify-tag", publish)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("scripts/verify.py", before)
        self.assertIn("inputs.commit", before)
        self.assertIn("refs/heads/dev", publish)

    def test_actual_dev_archive_contains_provenance(self):
        run = subprocess.run([sys.executable, str(ROOT / "scripts/package_addon.py"),
                              "--version", "20260928.7", "--channel", "dev", "--commit", "a" * 40],
                             cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        path = ROOT / "dist/ClassicSpeech-20260928.7.nvda-addon"
        with zipfile.ZipFile(path) as archive:
            metadata = json.loads(archive.read("globalPlugins/_speech_core/build_info.json"))
            self.assertEqual(metadata, package.build_metadata("20260928.7", "dev", "a" * 40))
            self.assertIn(b"version = 20260928.7", archive.read("manifest.ini"))
            self.assertIn("globalPlugins/_speech_core/update_channels.py", archive.namelist())
        self.assertTrue(path.with_suffix(".nvda-addon.sha256").is_file())


if __name__ == "__main__":
    unittest.main()
