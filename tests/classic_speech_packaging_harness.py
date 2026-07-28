"""Focused tests for generated, NVDA-comparable ClassicSpeech package versions."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
import zipfile
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
            arguments = SimpleNamespace(version="20260728.1", label="layout")
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


if __name__ == "__main__":
    unittest.main()
