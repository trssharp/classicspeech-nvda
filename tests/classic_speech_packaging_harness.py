"""Focused tests for generated, NVDA-comparable ClassicSpeech package versions."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

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

    def test_invalid_version_or_label_is_rejected(self):
        with self.assertRaises(ValueError):
            self.packager.package_filename("4.0-edge-notifications")
        with self.assertRaises(ValueError):
            self.packager.package_filename("20260724.16", "build unsafe")
        with self.assertRaises(ValueError):
            self.packager.build_version("2026-07-24", "zero")


if __name__ == "__main__":
    unittest.main()
