"""Focused tests for generated, NVDA-comparable ClassicSpeech package versions."""
from __future__ import annotations

import importlib.util
import os
import re
import sys
import tempfile
import unittest
import zipfile
from io import BytesIO, StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "package_addon.py"


def _load_packager():
    spec = importlib.util.spec_from_file_location("classicspeech_package_addon", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _nvda_addon_handler() -> Path | None:
    """NVDA's addonHandler from the NVDA checkout the other harnesses use, if there is one."""
    explicit_path = os.environ.get("CLASSICSPEECH_NVDA_MASTER", "").strip()
    if explicit_path:
        checkouts = [Path(explicit_path).expanduser()]
    else:
        checkouts = [ancestor / "nvda master" for ancestor in ROOT.parents]
    for checkout in checkouts:
        addon_handler = checkout / "source" / "addonHandler" / "__init__.py"
        if addon_handler.is_file():
            return addon_handler
    return None


def _nvda_manifest_spec(addon_handler_source: str) -> str:
    """The rules NVDA's AddonManifest checks manifest.ini against."""
    block = addon_handler_source.split("class AddonManifest(ConfigObj):", 1)[1]
    return block.split("configspec = ConfigObj(", 1)[1].split('"""', 2)[1]


def _read_manifest_like_nvda(manifest_bytes: bytes, spec: str):
    """Read and validate a manifest the way NVDA's AddonManifest does."""
    from configobj import ConfigObj

    try:
        from configobj.validate import ValidateError, Validator
    except ImportError:  # configobj before 5.0.7 shipped validate as its own module
        from validate import ValidateError, Validator

    def api_version(value):
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}\.\d+(?:\.\d+)?|0\.0\.0", value):
            raise ValidateError(f"not an NVDA API version: {value!r}")
        return value

    manifest = ConfigObj(
        BytesIO(manifest_bytes),
        configspec=ConfigObj(StringIO(spec)),
        encoding="utf-8",
        default_encoding="utf-8",
    )
    return manifest, manifest.validate(Validator({"apiVersion": api_version}), copy=True, preserve_errors=True)


class PackageVersioningTests(unittest.TestCase):
    def setUp(self):
        self.packager = _load_packager()

    def test_package_filename_uses_generated_date_and_run_version(self):
        version = self.packager.build_version("2026-07-24", "16")
        self.assertEqual(version, "20260724.16")
        self.assertEqual(
            self.packager.package_filename(version, "gddf21ae"),
            "ClassicSpeech-20260724.16-gddf21ae.nvda-addon",
        )
        self.assertEqual(
            self.packager.package_filename("4.0.0"),
            "ClassicSpeech-4.0.0.nvda-addon",
        )

    def test_release_archive_has_full_commit_and_stable_provenance(self):
        import json
        commit = "abcdef0123456789" * 2 + "abcdef01"
        version = self.packager.release_notes_version(self.packager.RELEASE_NOTES)
        original = (ROOT / "manifest.ini").read_bytes()
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory)
            with mock.patch.object(self.packager, "DIST", output), mock.patch.object(
                sys, "argv", [str(SCRIPT), "--version", version, "--commit", commit]
            ):
                self.packager.main()
            with zipfile.ZipFile(output / f"ClassicSpeech-{version}.nvda-addon") as archive:
                self.assertEqual(json.loads(archive.read("globalPlugins/_speech_core/build_info.json")),
                                 {"version": version, "channel": "stable", "commit": commit})
        self.assertEqual((ROOT / "manifest.ini").read_bytes(), original)
        workflow = (ROOT / ".github/workflows/verify-and-package.yml").read_text(encoding="utf-8")
        self.assertIn('--commit "$COMMIT_SHA"', workflow)
        for invalid in ("abc", "A" * 40, "x" * 40):
            with self.assertRaises(ValueError):
                self.packager.build_metadata(version, commit=invalid)
        self.assertEqual(self.packager.build_metadata("20260928.1")["channel"], "unknown")

    def test_invalid_version_or_label_is_rejected(self):
        with self.assertRaises(ValueError):
            self.packager.package_filename("4.0-edge-notifications")
        with self.assertRaises(ValueError):
            self.packager.package_filename("20260724.16", "build unsafe")
        with self.assertRaises(ValueError):
            self.packager.build_version("2026-07-24", "zero")

    def test_package_keeps_page_entry_runtime_inside_web_processors(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)
            arguments = SimpleNamespace(version="20260728.1", label="layout", sync_changelog=False, channel="auto", commit="")
            with mock.patch.object(self.packager, "DIST", output_directory), mock.patch.object(
                self.packager, "_parse_args", return_value=arguments
            ):
                self.packager.main()

            package_path = output_directory / "ClassicSpeech-20260728.1-layout.nvda-addon"
            with zipfile.ZipFile(package_path) as archive:
                members = set(archive.namelist())

        self.assertIn(
            "globalPlugins/_speech_core/processors/web/page_entry.py", members
        )
        self.assertNotIn("globalPlugins/page_orientation_runtime.py", members)
        self.assertIn("globalPlugins/_speech_core/settings/web/__init__.py", members)
        self.assertIn("globalPlugins/_speech_core/settings/web/formatting_config.py", members)
        self.assertIn("globalPlugins/_speech_core/settings/web/summary_config.py", members)
        self.assertIn("globalPlugins/_speech_core/settings/web/dialog.py", members)
        self.assertNotIn("globalPlugins/_speech_core/settings/web_formatting_config.py", members)
        self.assertNotIn("globalPlugins/_speech_core/settings/web_summary_config.py", members)
        self.assertNotIn("globalPlugins/_speech_core/settings/web_settings_dialog.py", members)
        self.assertIn("globalPlugins/_speech_core/settings/text/__init__.py", members)
        self.assertIn("globalPlugins/_speech_core/settings/text/config.py", members)
        self.assertIn("globalPlugins/_speech_core/settings/text/panel.py", members)
        self.assertNotIn("globalPlugins/_speech_core/settings/text_processing_config.py", members)
        self.assertNotIn("globalPlugins/_speech_core/settings/text_processing_panel.py", members)
        self.assertIn("locale/es/LC_MESSAGES/nvda.mo", members)
        self.assertNotIn("locale/es/LC_MESSAGES/nvda.po", members)

    def test_package_contains_the_user_guide_nvda_opens(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)
            arguments = SimpleNamespace(version="20260918.1", label="guide", sync_changelog=False, channel="auto", commit="")
            with mock.patch.object(self.packager, "DIST", output_directory), mock.patch.object(
                self.packager, "_parse_args", return_value=arguments
            ):
                self.packager.main()

            package_path = output_directory / "ClassicSpeech-20260918.1-guide.nvda-addon"
            with zipfile.ZipFile(package_path) as archive:
                members = set(archive.namelist())
                manifest = archive.read("manifest.ini").decode("utf-8")

        # NVDA's Add-on Store Help opens doc/<language>/<docFileName> from the add-on root.
        self.assertEqual(self.packager.manifest_doc_file_name(manifest), "readme.html")
        self.assertIn("doc/en/readme.html", members)
        self.assertIn("globalPlugins/_speech_core/user_guide.py", members)

    def test_manifest_doc_file_name_is_read_from_quoted_or_bare_values(self):
        read = self.packager.manifest_doc_file_name
        self.assertEqual(read("name = X\ndocFileName = readme.html\n"), "readme.html")
        self.assertEqual(read('docFileName = "guide.html"\r\n'), "guide.html")
        self.assertIsNone(read("name = X\n"))
        self.assertIsNone(read("docFileName =\n"))


class ManifestChangelogTests(unittest.TestCase):
    """The manifest changelog is the What's new NVDA 2026.1 and later show in the Add-on Store."""

    def setUp(self):
        self.packager = _load_packager()
        self.manifest_text = (ROOT / "manifest.ini").read_text(encoding="utf-8")
        notes = ROOT / "docs" / self.packager.RELEASE_NOTES
        self.whats_new = self.packager.release_whats_new(notes.read_text(encoding="utf-8"))

    def test_manifest_carries_the_current_release_whats_new(self):
        self.assertIsNotNone(self.whats_new, f"docs/{self.packager.RELEASE_NOTES} has no What's new section")
        self.packager.check_changelog(self.whats_new)
        self.assertEqual(
            self.packager.manifest_changelog(self.manifest_text),
            self.whats_new,
            "run: python scripts/package_addon.py --sync-changelog",
        )
        self.assertIsNotNone(self.packager.release_notes_version(self.packager.RELEASE_NOTES))

    def test_nvda_reads_the_changelog_exactly_as_written(self):
        addon_handler = _nvda_addon_handler()
        if addon_handler is None:
            self.skipTest("no NVDA checkout to read NVDA's manifest rules from")
        try:
            import configobj  # noqa: F401
        except ImportError:
            self.skipTest("configobj, which NVDA bundles, is not installed")
        spec = _nvda_manifest_spec(addon_handler.read_text(encoding="utf-8"))
        self.assertIn("changelog = string(default=None)", spec)
        release = self.packager.release_notes_version(self.packager.RELEASE_NOTES)
        packaged = self.packager.manifest_with_version(ROOT / "manifest.ini", release).encode("utf-8")
        for manifest_bytes in ((ROOT / "manifest.ini").read_bytes(), packaged):
            manifest, result = _read_manifest_like_nvda(manifest_bytes, spec)
            self.assertIs(result, True, result)
            self.assertEqual(manifest["changelog"], self.whats_new)
        # NVDA 2025.1 to 2025.3 have no changelog in their rules, and must still accept the manifest.
        older_spec = re.sub(r"(?m)^changelog = .*$", "", spec)
        manifest, result = _read_manifest_like_nvda(packaged, older_spec)
        self.assertIs(result, True, result)
        self.assertEqual(manifest["version"], release)
        self.assertIn("changelog", manifest.extra_values)

    def test_package_manifest_keeps_the_whats_new(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)
            arguments = SimpleNamespace(version="20260920.1", label="notes", sync_changelog=False, channel="auto", commit="")
            with mock.patch.object(self.packager, "DIST", output_directory), mock.patch.object(
                self.packager, "_parse_args", return_value=arguments
            ):
                self.packager.main()

            package_path = output_directory / "ClassicSpeech-20260920.1-notes.nvda-addon"
            with zipfile.ZipFile(package_path) as archive:
                members = set(archive.namelist())
                manifest = archive.read("manifest.ini").decode("utf-8")

        self.assertEqual(self.packager.manifest_changelog(manifest), self.whats_new)
        self.assertIn("\nversion = 20260920.1\n", manifest)
        self.assertIn(f"globalPlugins/docs/{self.packager.RELEASE_NOTES}", members)

    def test_packaging_refuses_a_missing_or_stale_whats_new(self):
        check = self.packager.check_release_changelog
        current = 'name = X\nversion = 0.0.0\nchangelog = """* New thing."""\n'
        with tempfile.TemporaryDirectory() as temporary_directory:
            notes = Path(temporary_directory) / "RELEASE-2.5.md"
            notes.write_text(
                "# ClassicSpeech 2.5\n\nIntro.\n\n## What's new\n\n* New thing.\n\n## Notes\n\n* Detail.\n",
                encoding="utf-8",
            )
            check(current, notes, "2.5")
            check(current, notes, "20260920.3")
            with self.assertRaisesRegex(ValueError, "--sync-changelog"):
                check('name = X\nchangelog = """* Old thing."""\n', notes, "2.5")
            with self.assertRaisesRegex(ValueError, "--sync-changelog"):
                check("name = X\nversion = 0.0.0\n", notes, "20260920.3")
            # A release can't go out with the What's new of the release before it.
            with self.assertRaisesRegex(ValueError, r"RELEASE-2\.6\.md"):
                check(current, notes, "2.6")
            notes.write_text("# ClassicSpeech 2.5\n\n## Notes\n\n* Detail.\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "What's new"):
                check(current, notes, "2.5")
            with self.assertRaisesRegex(ValueError, "Missing release notes"):
                check(current, Path(temporary_directory) / "RELEASE-2.7.md", "20260920.3")

    def test_whats_new_runs_to_the_next_level_one_or_two_heading(self):
        read = self.packager.release_whats_new
        notes = (
            "# ClassicSpeech 2.5\r\n\r\nIntro.\r\n\r\n## What's new\r\n\r\n### Fixes\r\n\r\n* One.\r\n\r\n"
            "### Changes\r\n\r\n* Two.\r\n\r\n## Notes\r\n\r\n* Not part of it.\r\n"
        )
        self.assertEqual(read(notes), "### Fixes\n\n* One.\n\n### Changes\n\n* Two.")
        self.assertEqual(read("## What's new\n* The last section."), "* The last section.")
        self.assertIsNone(read("# ClassicSpeech 2.5\n\n## Notes\n\n* Detail.\n"))
        self.assertIsNone(read("## What's new\n\n## Notes\n"))

    def test_sync_writes_the_whats_new_into_the_manifest(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            folder = Path(temporary_directory)
            manifest = folder / "manifest.ini"
            notes = folder / "RELEASE-2.5.md"
            manifest.write_bytes(b"name = X\r\nversion = 0.0.0\r\ndocFileName = readme.html\r\n")
            notes.write_text(
                "## What's new\n\n* Settings are in `%APPDATA%\\nvda\\ClassicSpeech`.\n\n## Notes\n", encoding="utf-8"
            )
            self.assertTrue(self.packager.sync_changelog(manifest, notes))
            self.assertFalse(self.packager.sync_changelog(manifest, notes))
            written = manifest.read_bytes()
            self.assertNotIn(b"\n", written.replace(b"\r\n", b""), "the manifest's line endings changed")
            text = manifest.read_text(encoding="utf-8")
            self.assertEqual(
                self.packager.manifest_changelog(text), "* Settings are in `%APPDATA%\\nvda\\ClassicSpeech`."
            )
            self.assertEqual(self.packager.manifest_doc_file_name(text), "readme.html")

            notes.write_text("## What's new\n\n* Replaced.\n", encoding="utf-8")
            self.assertTrue(self.packager.sync_changelog(manifest, notes))
            text = manifest.read_text(encoding="utf-8")
            self.assertEqual(self.packager.manifest_changelog(text), "* Replaced.")
            self.assertEqual(text.count("changelog ="), 1)

            notes.write_text("# ClassicSpeech 2.5\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "What's new"):
                self.packager.sync_changelog(manifest, notes)

    def test_a_changelog_the_manifest_cannot_hold_is_refused(self):
        for changelog in ("", "  \n", 'Say """this"""', "Uses %(name)s"):
            with self.subTest(changelog=changelog), self.assertRaises(ValueError):
                self.packager.manifest_with_changelog("name = X\n", changelog)
        with self.assertRaisesRegex(ValueError, "triple-quoted"):
            self.packager.manifest_with_changelog('name = X\nchangelog = "one line"\n', "* New.")

    def test_changelog_lines_that_look_like_settings_stay_text(self):
        changelog = "version = 9.9 is text\ndocFileName = other.html\n[not a section]\n# not a comment"
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest = Path(temporary_directory) / "manifest.ini"
            for source in (
                "name = X\nversion = 0.0.0\ndocFileName = readme.html\n",
                'name = X\nchangelog = """old"""\nversion = 0.0.0\ndocFileName = readme.html\n',
            ):
                with self.subTest(source=source):
                    manifest.write_text(self.packager.manifest_with_changelog(source, changelog), encoding="utf-8")
                    packaged = self.packager.manifest_with_version(manifest, "2.5")
                    self.assertIn("\nversion = 2.5\n", packaged)
                    self.assertEqual(self.packager.manifest_changelog(packaged), changelog)
                    self.assertEqual(self.packager.manifest_doc_file_name(packaged), "readme.html")
        windows = 'name = X\r\nchangelog = """First.\r\ndocFileName = other.html\r\nLast."""\r\ndocFileName = readme.html\r\n'
        self.assertEqual(self.packager.manifest_doc_file_name(windows), "readme.html")
        self.assertEqual(self.packager.manifest_changelog(windows), "First.\ndocFileName = other.html\nLast.")


if __name__ == "__main__":
    unittest.main()
