"""Focused regression coverage for custom Browse and Focus Mode messages."""
from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = ROOT / "_speech_core" / "processors" / "web" / "mode_indication.py"
CONFIG_PATH = ROOT / "_speech_core" / "settings" / "web" / "mode_indication_config.py"


def _load_runtime():
	module_spec = importlib.util.spec_from_file_location("mode_indication_harness_runtime", RUNTIME_PATH)
	assert module_spec is not None and module_spec.loader is not None
	module = importlib.util.module_from_spec(module_spec)
	module_spec.loader.exec_module(module)
	return module


def _load_config():
	module_spec = importlib.util.spec_from_file_location("mode_indication_harness_config", CONFIG_PATH)
	assert module_spec is not None and module_spec.loader is not None
	module = importlib.util.module_from_spec(module_spec)
	module_spec.loader.exec_module(module)
	return module


class CustomModeIndicationRuntimeTests(unittest.TestCase):
	def setUp(self):
		self.original_browse_mode = sys.modules.get("browseMode")
		self.original_config = sys.modules.get("config")
		self.original_ui = sys.modules.get("ui")
		self.messages = []
		self.native_calls = []
		self.config = types.SimpleNamespace(conf={"virtualBuffers": {"passThroughAudioIndication": False}})
		sys.modules["config"] = self.config
		sys.modules["ui"] = types.SimpleNamespace(message=self.messages.append)
		self.browse_mode = types.ModuleType("browseMode")

		def native_report(document, onlyIfChanged=True):
			self.native_calls.append((document.passThrough, onlyIfChanged))
			if not onlyIfChanged or document.passThrough != native_report.last:
				self.messages.append("Focus mode" if document.passThrough else "Browse mode")
			native_report.last = document.passThrough

		native_report.last = False
		self.native_report = native_report
		self.browse_mode.reportPassThrough = native_report
		sys.modules["browseMode"] = self.browse_mode
		self.runtime = _load_runtime()
		self.plugin = object()
		self.record = None

	def tearDown(self):
		if self.record is not None:
			self.runtime.restore(self.plugin, self.record)
		for name, original in (("browseMode", self.original_browse_mode), ("config", self.original_config), ("ui", self.original_ui)):
			if original is None:
				sys.modules.pop(name, None)
			else:
				sys.modules[name] = original

	def _install(self, browse_message=None, focus_message=None):
		self.record = self.runtime.install(
			self.plugin,
			get_browse_mode_message=lambda: browse_message,
			get_focus_mode_message=lambda: focus_message,
		)
		self.assertIsNotNone(self.record)

	def test_native_audio_and_unconfigured_text_paths_remain_native(self):
		self._install()
		document = types.SimpleNamespace(passThrough=True)

		self.browse_mode.reportPassThrough(document)
		self.assertEqual(self.native_calls, [(True, True)])
		self.assertEqual(self.messages, ["Focus mode"])

		self.config.conf["virtualBuffers"]["passThroughAudioIndication"] = True
		document.passThrough = False
		self.browse_mode.reportPassThrough(document)
		self.assertEqual(self.native_calls, [(True, True), (False, True)])

	def test_custom_messages_replace_only_the_matching_unchecked_text_path(self):
		self._install(browse_message="Reading", focus_message="Editing")
		document = types.SimpleNamespace(passThrough=True)

		self.browse_mode.reportPassThrough(document)
		self.assertEqual(self.native_calls, [])
		self.assertEqual(self.messages, ["Editing"])
		self.assertTrue(self.native_report.last)

		document.passThrough = False
		self.browse_mode.reportPassThrough(document)
		self.assertEqual(self.native_calls, [])
		self.assertEqual(self.messages, ["Editing", "Reading"])
		self.assertFalse(self.native_report.last)

		self.browse_mode.reportPassThrough(document)
		self.assertEqual(self.messages, ["Editing", "Reading"])

	def test_restore_returns_the_exact_native_function(self):
		self._install(browse_message="Reading")
		self.assertIsNot(self.browse_mode.reportPassThrough, self.native_report)

		self.runtime.restore(self.plugin, self.record)
		self.record = None

		self.assertIs(self.browse_mode.reportPassThrough, self.native_report)


class CustomModeIndicationConfigTests(unittest.TestCase):
	def setUp(self):
		self.original_config = sys.modules.get("config")
		self.conf = types.SimpleNamespace(profiles=[{}])
		sys.modules["config"] = types.SimpleNamespace(conf=self.conf)
		self.module = _load_config()

	def tearDown(self):
		if self.original_config is None:
			sys.modules.pop("config", None)
		else:
			sys.modules["config"] = self.original_config

	def test_native_labels_are_display_defaults_and_blank_values_fall_back_to_native(self):
		self.assertEqual(self.module.get_browse_mode_message(), "Browse mode")
		self.assertEqual(self.module.get_focus_mode_message(), "Focus mode")
		self.assertIsNone(self.module.get_custom_browse_mode_message())
		self.assertIsNone(self.module.get_custom_focus_mode_message())
		self.module.set_browse_mode_message("Browse mode")
		self.module.set_focus_mode_message("Focus mode")
		self.assertIsNone(self.module.get_custom_browse_mode_message())
		self.assertIsNone(self.module.get_custom_focus_mode_message())

		self.module.set_browse_mode_message("  Reading  ")
		self.module.set_focus_mode_message("Editing")
		self.assertEqual(self.module.get_browse_mode_message(), "Reading")
		self.assertEqual(self.module.get_focus_mode_message(), "Editing")
		self.module.set_browse_mode_message("   ")
		self.assertEqual(self.module.get_browse_mode_message(), "Browse mode")
		self.assertIsNone(self.module.get_custom_browse_mode_message())

	def test_cancel_snapshot_restores_absent_data_without_losing_other_classicspeech_values(self):
		self.conf.profiles[0]["classicSpeech"] = {"pageSummaryData": {"notifyWhenPageReady": True}}
		snapshot = self.module.capture_mode_indication_state()
		self.module.set_browse_mode_message("Reading")
		self.module.restore_mode_indication_state(snapshot)

		self.assertNotIn("modeIndicationData", self.conf.profiles[0]["classicSpeech"])
		self.assertEqual(
			self.conf.profiles[0]["classicSpeech"]["pageSummaryData"], {"notifyWhenPageReady": True}
		)


if __name__ == "__main__":
	unittest.main(verbosity=2)
