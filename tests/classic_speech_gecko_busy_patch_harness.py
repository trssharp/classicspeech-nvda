"""Isolated regression harness for the ClassicSpeech Gecko Busy runtime patch.

The harness supplies only the narrow NVDA surface patched by the experiment. It
never imports, starts, or modifies NVDA.
"""
from __future__ import annotations

import importlib
import sys
import types
import unittest
from enum import Enum
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


class GeckoBusyRuntimePatchTests(unittest.TestCase):
	def setUp(self):
		self._saved_modules = {
			name: sys.modules.get(name)
			for name in (
				"api", "controlTypes", "speech", "speech.speech", "virtualBuffers",
				"virtualBuffers.gecko_ia2", "NVDAObjects", "NVDAObjects.IAccessible",
				"NVDAObjects.IAccessible.mozilla", "_speech_core.gecko_busy_patch",
			)
		}
		self._install_fake_nvda_modules()
		self.patch_module = importlib.import_module("_speech_core.gecko_busy_patch")

	def tearDown(self):
		for name in tuple(self._saved_modules):
			sys.modules.pop(name, None)
		for name, module in self._saved_modules.items():
			if module is not None:
				sys.modules[name] = module

	def _install_fake_nvda_modules(self):
		class State(Enum):
			BUSY = 1
			FOCUSABLE = 2

		control_types = types.ModuleType("controlTypes")
		control_types.State = State
		sys.modules["controlTypes"] = control_types

		api = types.ModuleType("api")
		api.focus = None
		api.getFocusObject = lambda: api.focus
		sys.modules["api"] = api
		self.api = api
		self.State = State

		class Gecko_ia2:
			pass

		virtual_buffers = types.ModuleType("virtualBuffers")
		gecko = types.ModuleType("virtualBuffers.gecko_ia2")
		gecko.Gecko_ia2 = Gecko_ia2
		virtual_buffers.gecko_ia2 = gecko
		sys.modules["virtualBuffers"] = virtual_buffers
		sys.modules["virtualBuffers.gecko_ia2"] = gecko

		speech = types.ModuleType("speech")
		speech_speech = types.ModuleType("speech.speech")
		self.formatter_calls = []

		def getPropertiesSpeech(reason=None, **propertyValues):
			self.formatter_calls.append((reason, propertyValues))
			return list(propertyValues.get("states") or ())

		speech_speech.getPropertiesSpeech = getPropertiesSpeech
		speech.speech = speech_speech
		sys.modules["speech"] = speech
		sys.modules["speech.speech"] = speech_speech
		self.speech_speech = speech_speech

		class Document:
			def reportFocus(self):
				self.report_calls += 1
				return speech_speech.getPropertiesSpeech(
					reason="focus", states=self.states, _states=self.states,
				)

		mozilla = types.ModuleType("NVDAObjects.IAccessible.mozilla")
		mozilla.Document = Document
		accessible = types.ModuleType("NVDAObjects.IAccessible")
		accessible.mozilla = mozilla
		nvda_objects = types.ModuleType("NVDAObjects")
		nvda_objects.IAccessible = accessible
		sys.modules["NVDAObjects"] = nvda_objects
		sys.modules["NVDAObjects.IAccessible"] = accessible
		sys.modules["NVDAObjects.IAccessible.mozilla"] = mozilla
		self.Document = Document
		self.Gecko = Gecko_ia2

	def _matching_document(self):
		document = self.Document()
		document.states = {self.State.BUSY, self.State.FOCUSABLE}
		document._speakObjectPropertiesCache = {"states": document.states}
		document.report_calls = 0
		document.treeInterceptor = self.Gecko()
		document.treeInterceptor.rootNVDAObject = document
		document.treeInterceptor.passThrough = False
		document.treeInterceptor.isLoading = True
		document.treeInterceptor.isReady = False
		self.api.focus = document
		return document

	def test_disabled_does_not_patch(self):
		patch = self.patch_module.GeckoBusyPresentationPatch()
		original = self.Document.reportFocus
		self.assertFalse(patch.install())
		self.assertIs(self.Document.reportFocus, original)

	def test_match_uses_one_shot_copy_and_preserves_real_state_and_cache(self):
		patch = self.patch_module.GeckoBusyPresentationPatch(enabled=lambda: True)
		original = self.Document.reportFocus
		self.assertTrue(patch.install())
		document = self._matching_document()
		original_states = document.states
		original_cache_states = document._speakObjectPropertiesCache["states"]

		result = document.reportFocus()

		self.assertEqual(document.report_calls, 1)
		self.assertEqual(result, [self.State.FOCUSABLE])
		self.assertIs(document.states, original_states)
		self.assertEqual(document.states, {self.State.BUSY, self.State.FOCUSABLE})
		self.assertIs(document._speakObjectPropertiesCache["states"], original_cache_states)
		self.assertEqual(document._speakObjectPropertiesCache["states"], {self.State.BUSY, self.State.FOCUSABLE})
		self.assertIsNot(self.formatter_calls[-1][1]["states"], original_states)
		self.assertIs(self.Document.reportFocus, patch.report_focus_wrapper)
		patch.restore()
		self.assertIs(self.Document.reportFocus, original)

	def test_nonmatching_document_and_second_formatter_call_remain_native(self):
		patch = self.patch_module.GeckoBusyPresentationPatch(enabled=lambda: True)
		self.assertTrue(patch.install())
		document = self._matching_document()
		document.treeInterceptor.isReady = True

		result = document.reportFocus()
		self.assertEqual(set(result), {self.State.BUSY, self.State.FOCUSABLE})

		patch.restore()
		document = self._matching_document()
		def report_focus_with_two_calls(obj):
			first = self.speech_speech.getPropertiesSpeech(reason="focus", states=obj.states)
			second = self.speech_speech.getPropertiesSpeech(reason="focus", states=obj.states)
			return first, second
		self.Document.reportFocus = report_focus_with_two_calls
		self.assertTrue(patch.install())
		first, second = document.reportFocus()
		self.assertEqual(first, [self.State.FOCUSABLE])
		self.assertEqual(set(second), {self.State.BUSY, self.State.FOCUSABLE})

	def test_signature_rejection_fails_closed_without_partial_patch(self):
		def incompatible_formatter(required):
			return required
		self.speech_speech.getPropertiesSpeech = incompatible_formatter
		patch = self.patch_module.GeckoBusyPresentationPatch(enabled=lambda: True)
		original_report_focus = self.Document.reportFocus
		self.assertFalse(patch.install())
		self.assertIs(self.Document.reportFocus, original_report_focus)
		self.assertIs(self.speech_speech.getPropertiesSpeech, incompatible_formatter)

	def test_restore_is_identity_safe_and_reload_replaces_only_own_wrapper(self):
		original_report_focus = self.Document.reportFocus
		original_formatter = self.speech_speech.getPropertiesSpeech
		first = self.patch_module.GeckoBusyPresentationPatch(enabled=lambda: True)
		self.assertTrue(first.install())
		second = self.patch_module.GeckoBusyPresentationPatch(enabled=lambda: True)
		self.assertTrue(second.install())
		self.assertIsNot(self.Document.reportFocus, first.report_focus_wrapper)
		self.assertIs(self.Document.reportFocus, second.report_focus_wrapper)

		def later_addon_wrapper(*args, **kwargs):
			return "later"
		self.Document.reportFocus = later_addon_wrapper
		self.speech_speech.getPropertiesSpeech = later_addon_wrapper
		second.restore()
		self.assertIs(self.Document.reportFocus, later_addon_wrapper)
		self.assertIs(self.speech_speech.getPropertiesSpeech, later_addon_wrapper)

		# The first patch was replaced during reload and must no longer own either target.
		first.restore()
		self.assertIs(self.Document.reportFocus, later_addon_wrapper)
		self.assertIs(self.speech_speech.getPropertiesSpeech, later_addon_wrapper)
		self.assertIsNot(original_report_focus, later_addon_wrapper)
		self.assertIsNot(original_formatter, later_addon_wrapper)


if __name__ == "__main__":
	unittest.main()
