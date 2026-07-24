"""Focused tests for reproducible, manifest-versioned ClassicSpeech packages."""
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

	def test_package_filename_includes_manifest_version_and_utc_build_date(self):
		version = self.packager.get_manifest_version(ROOT / "manifest.ini")
		self.assertEqual(
			self.packager.package_filename(version, "2026-07-24", "rc.1"),
			f"ClassicSpeech-{version}-rc.1-2026-07-24.nvda-addon",
		)

	def test_manifest_version_must_be_a_safe_filename_component(self):
		with self.assertRaises(ValueError):
			self.packager.package_filename("4.0-edge-notifications", "2026-07-24")
		with self.assertRaises(ValueError):
			self.packager.package_filename("4.0.26", "2026-07-24", "dev unsafe")


if __name__ == "__main__":
	unittest.main()
