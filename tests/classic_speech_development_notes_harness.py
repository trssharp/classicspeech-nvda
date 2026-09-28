"""Rolling dev notes are package-only; stable notes and source stay immutable."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("package_addon", ROOT / "scripts/package_addon.py")
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class DevelopmentNotesTests(unittest.TestCase):
    def test_dev_extraction_uses_existing_section_rules_and_rejects_unsafe_text(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "docs").mkdir()
            notes = root / "docs/DEVELOPMENT.md"
            with mock.patch.object(package, "ROOT", root):
                for text in ("# Missing", "## What's new\n\n## Other", '## What\'s new\nBad """',
                             "## What's new\nBad %(name)s"):
                    notes.write_text(text, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        package.development_whats_new()
                notes.write_text("# Dev\r\n## What's new\r\n### Fixes\r\n* One.\r\n## Maintenance\r\nNot shipped.", encoding="utf-8", newline="")
                self.assertEqual(package.development_whats_new(), "### Fixes\n* One.")
                notes.unlink()
                with self.assertRaises(OSError):
                    package.development_whats_new()

    def test_actual_packages_and_release_body_share_notes_without_source_writes(self):
        tracked = [ROOT / "manifest.ini", *sorted((ROOT / "docs").glob("RELEASE-*.md"))]
        before = {p: p.read_bytes() for p in tracked}
        dev = package.development_whats_new()
        stable = package.release_whats_new((ROOT / "docs" / package.RELEASE_NOTES).read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as folder:
            dist = Path(folder)
            for channel, version, expected in (("dev", "20260928.901", dev), ("stable", "2.0", stable),
                                               ("auto", "20260928.902", stable)):
                args = SimpleNamespace(version=version, label="", sync_changelog=False, channel=channel, commit="a" * 40)
                with mock.patch.object(package, "DIST", dist), mock.patch.object(package, "_parse_args", return_value=args):
                    package.main()
                with zipfile.ZipFile(dist / package.package_filename(version)) as archive:
                    self.assertEqual(package.manifest_changelog(archive.read("manifest.ini").decode("utf-8")), expected)
                    member = "globalPlugins/docs/" + ("DEVELOPMENT.md" if channel == "dev" else package.RELEASE_NOTES)
                    self.assertEqual(package.release_whats_new(archive.read(member).decode("utf-8")), expected)
                    self.assertNotIn("globalPlugins/docs/" + (package.RELEASE_NOTES if channel == "dev" else "DEVELOPMENT.md"), archive.namelist())
                    metadata = json.loads(archive.read("globalPlugins/_speech_core/build_info.json"))
                    self.assertEqual(metadata, package.build_metadata(version, channel, "a" * 40))
                    if channel == "dev":
                        from configobj import ConfigObj
                        from io import BytesIO
                        self.assertEqual(ConfigObj(BytesIO(archive.read("manifest.ini")), encoding="utf-8")["changelog"], dev)
            result = subprocess.run([sys.executable, "-m", "scripts.dev_release_notes", "--version", "20260928.901", "--commit", "a" * 40,
                                     "--output", str(dist / "notes.md")], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            body = (dist / "notes.md").read_text(encoding="utf-8")
            self.assertEqual(package.release_whats_new(body), dev)
            self.assertIn("20260928.901", body)
            self.assertIn("Source commit: " + "a" * 40, body)
            self.assertIn("not a stable release", body)
        self.assertEqual(before, {p: p.read_bytes() for p in tracked})

    def test_existing_version_keeps_its_notes_when_rolling_source_changes(self):
        import shutil
        with mock.patch.object(sys, "path", [str(ROOT), *sys.path]):
            from scripts import dev_release_notes
            from scripts import package_addon as notes_package
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "source"
            # Work on a private snapshot, never edit the repository's rolling notes.
            root.mkdir()
            for name in (*package.RUNTIME_FILES, *package.ROOT_FILES, "manifest.ini"):
                shutil.copy2(ROOT / name, root / name)
            for name in (*package.RUNTIME_DIRECTORIES, *package.APP_MODULE_DIRECTORIES,
                         *package.DOC_DIRECTORIES, *package.LOCALE_DIRECTORIES, "docs"):
                shutil.copytree(ROOT / name, root / name, ignore=shutil.ignore_patterns("__pycache__"))
            dist = Path(folder) / "builds"
            with mock.patch.object(package, "ROOT", root), mock.patch.object(package, "DIST", dist), mock.patch.object(notes_package, "ROOT", root):
                notes = root / "docs/DEVELOPMENT.md"
                snapshots = []
                for version, text in (("20260928.903", "* First change."), ("20260928.904", "* First change.\n* Next change.")):
                    notes.write_text("## What's new\n\n" + text + "\n", encoding="utf-8")
                    args = SimpleNamespace(version=version, label="", sync_changelog=False, channel="dev", commit="a" * 40)
                    with mock.patch.object(package, "_parse_args", return_value=args):
                        package.main()
                    body = dev_release_notes.release_body(version, "a" * 40)
                    body_path = dist / (version + ".md")
                    body_path.write_text(body, encoding="utf-8")
                    snapshots.append((dist / package.package_filename(version), body_path, text))
                for archive_path, body_path, text in snapshots:
                    with zipfile.ZipFile(archive_path) as archive:
                        self.assertEqual(package.manifest_changelog(archive.read("manifest.ini").decode("utf-8")), text)
                        self.assertEqual(package.release_whats_new(archive.read("globalPlugins/docs/DEVELOPMENT.md").decode("utf-8")), text)
                    self.assertEqual(package.release_whats_new(body_path.read_text(encoding="utf-8")), text)

    def test_dev_sync_cannot_replace_stable_source_changelog(self):
        before = (ROOT / "manifest.ini").read_bytes()
        result = subprocess.run([sys.executable, "scripts/package_addon.py", "--sync-changelog", "--channel", "dev"],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((ROOT / "manifest.ini").read_bytes(), before)

    def test_manual_workflow_composes_notes_in_verified_checkout_before_upload(self):
        text = (ROOT / ".github/workflows/publish-dev.yml").read_text(encoding="utf-8")
        command = 'python -m scripts.dev_release_notes --version "$version" --commit "$COMMIT" --output release-assets/notes.md'
        self.assertIn(command, text)
        self.assertLess(text.index("scripts/verify.py"), text.index(command))
        self.assertLess(text.index(command), text.index("actions/upload-artifact"))
        self.assertNotIn("printf 'Development build", text)
        self.assertIn("--notes-file notes.md", text)


if __name__ == "__main__":
    unittest.main()
