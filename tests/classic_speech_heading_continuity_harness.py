"""Focused regression coverage for Browse Mode heading-continuity presentation.

This harness does not start NVDA. It models the two distinct speech bindings that
NVDA TextInfo uses: the implementation module creates presentation scope and the
public speech package formats structural control fields.
"""
from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = ROOT / "_speech_core" / "processors" / "web" / "heading_continuity.py"
CONFIG_PATH = ROOT / "_speech_core" / "settings" / "web" / "heading_continuity_config.py"


def _load_module(name: str, path: Path):
	module_spec = importlib.util.spec_from_file_location(name, path)
	assert module_spec is not None and module_spec.loader is not None
	module = importlib.util.module_from_spec(module_spec)
	module_spec.loader.exec_module(module)
	return module


runtime_module = _load_module("heading_continuity_harness_runtime", RUNTIME_PATH)
HeadingContinuityRuntime = runtime_module.HeadingContinuityRuntime


class FakeDocument:
	isReady = True
	VBufHandle = object()


class FakeInfo:
	def __init__(self, document):
		self.obj = document


class HeadingContinuityRuntimeTests(unittest.TestCase):
	def setUp(self):
		self.document = FakeDocument()
		self.focus = types.SimpleNamespace(treeInterceptor=self.document)
		self.runtime = HeadingContinuityRuntime(
			is_enabled=lambda: True,
			get_focus_object=lambda: self.focus,
			line_unit="line",
			caret_reason="caret",
			reading_chunk_unit="readingChunk",
			sayall_reason="sayAll",
			heading_role="heading",
		)
		self.calls = []
		self.public_speech = types.SimpleNamespace()

		def original_text(info, _use_cache, _format, unit, reason):
			self.calls.append((unit, reason))
			yield from self.public_speech.getControlFieldSpeech(
				{"role": "heading"}, (), "start_inControlFieldStack"
			)

		def original_control(attrs, ancestors, field_type, *args, **kwargs):
			return [f"native:{field_type}:{attrs.get('role')}"]

		self.speech_implementation = types.SimpleNamespace(getTextInfoSpeech=original_text)
		self.say_all = types.SimpleNamespace(_getTextInfoSpeech=original_text)
		self.public_speech.getControlFieldSpeech = original_control
		self.original_text = original_text
		self.original_control = original_control
		self.assertTrue(self.runtime.install(self.speech_implementation, self.public_speech, self.say_all))

	def tearDown(self):
		self.runtime.restore()

	def _speech(self, unit="line", reason="caret"):
		return list(
			self.speech_implementation.getTextInfoSpeech(
				FakeInfo(self.document), False, None, unit, reason
			)
		)

	def test_same_heading_continuation_is_suppressed_on_a_ready_focused_caret_line(self):
		self.assertEqual(self._speech(), [])
		self.assertEqual(self.calls, [("line", "caret")])

	def test_first_or_distinct_heading_control_remains_native(self):
		self.assertEqual(
			self.public_speech.getControlFieldSpeech(
				{"role": "heading"}, (), "start_addedToControlFieldStack"
			),
			["native:start_addedToControlFieldStack:heading"],
		)

	def test_disabled_unready_stale_and_non_caret_paths_remain_native(self):
		self.runtime._is_enabled = lambda: False
		self.assertEqual(self._speech(), ["native:start_inControlFieldStack:heading"])
		self.runtime._is_enabled = lambda: True
		self.document.isReady = False
		self.assertEqual(self._speech(), ["native:start_inControlFieldStack:heading"])
		self.document.isReady = True
		self.focus.treeInterceptor = FakeDocument()
		self.assertEqual(self._speech(), ["native:start_inControlFieldStack:heading"])
		self.focus.treeInterceptor = self.document
		self.assertEqual(self._speech(unit="paragraph"), ["native:start_inControlFieldStack:heading"])

	def test_say_all_uses_the_same_scoped_wrapper_and_restore_is_identity_safe(self):
		self.assertIs(self.say_all._getTextInfoSpeech, self.speech_implementation.getTextInfoSpeech)
		self.assertEqual(
			list(self.say_all._getTextInfoSpeech(FakeInfo(self.document), False, None, "readingChunk", "sayAll")),
			[],
		)
		wrapped_text = self.speech_implementation.getTextInfoSpeech
		wrapped_control = self.public_speech.getControlFieldSpeech
		self.runtime.restore()
		self.assertIs(self.speech_implementation.getTextInfoSpeech, self.original_text)
		self.assertIs(self.public_speech.getControlFieldSpeech, self.original_control)
		self.assertIs(self.say_all._getTextInfoSpeech, self.original_text)
		self.assertIsNot(wrapped_text, self.original_text)
		self.assertIsNot(wrapped_control, self.original_control)


class HeadingContinuityConfigTests(unittest.TestCase):
	def setUp(self):
		self.original_config = sys.modules.get("config")
		self.conf = types.SimpleNamespace(profiles=[{}])
		sys.modules["config"] = types.SimpleNamespace(conf=self.conf)
		self.module = _load_module("heading_continuity_harness_config", CONFIG_PATH)

	def tearDown(self):
		if self.original_config is None:
			sys.modules.pop("config", None)
		else:
			sys.modules["config"] = self.original_config

	def test_default_is_off_and_string_booleans_are_normalized(self):
		self.assertFalse(self.module.get_heading_continuity_enabled())
		self.conf.profiles[0]["classicSpeech"] = {"headingContinuityData": {"enabled": "true"}}
		self.assertTrue(self.module.get_heading_continuity_enabled())
		self.conf.profiles[0]["classicSpeech"]["headingContinuityData"]["enabled"] = "False"
		self.assertFalse(self.module.get_heading_continuity_enabled())

	def test_set_and_restore_preserve_unrelated_classicspeech_data(self):
		self.conf.profiles[0]["classicSpeech"] = {"pageSummaryData": {"notifyWhenPageReady": True}}
		snapshot = self.module.capture_heading_continuity_state()
		self.assertTrue(self.module.set_heading_continuity_enabled(True))
		self.assertTrue(self.module.get_heading_continuity_enabled())
		self.module.restore_heading_continuity_state(snapshot)
		self.assertFalse(self.module.get_heading_continuity_enabled())
		self.assertEqual(
			self.conf.profiles[0]["classicSpeech"]["pageSummaryData"], {"notifyWhenPageReady": True}
		)


class HeadingContinuityIntegrationSourceTests(unittest.TestCase):
	def test_plugin_config_and_web_dialog_register_a_transaction_safe_opt_in_control(self):
		config_source = (ROOT / "_speech_core" / "plugin_config.py").read_text(encoding="utf-8")
		dialog_source = (ROOT / "_speech_core" / "settings" / "web" / "dialog.py").read_text(encoding="utf-8")
		plugin_source = (ROOT / "classicSpeech.py").read_text(encoding="utf-8")
		self.assertIn('"headingContinuityData"', config_source)
		self.assertIn('"enabled": "boolean(default=False)"', config_source)
		self.assertIn("Reduce repeated heading levels on continuation lines", dialog_source)
		self.assertIn("capture_heading_continuity_state", dialog_source)
		self.assertIn("restore_heading_continuity_state", dialog_source)
		self.assertIn("set_heading_continuity_enabled", dialog_source)
		self.assertIn("install_heading_continuity(log)", plugin_source)
		self.assertIn("headingContinuityRuntime.restore()", plugin_source)


if __name__ == "__main__":
	unittest.main(verbosity=2)
