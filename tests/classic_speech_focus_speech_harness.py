"""Focus speech regressions fixed in ClassicSpeech 1.02.

* Edit fields: the current line (or "blank") is read on focus unless the
  Verbosity option is cleared.
* A held container such as Chrome's "tool bar" is spoken on its own when the
  next sequence is not one of its items, so the field keeps its name and text.
* Mouse tracking speech uses the Mouse Voice Profile.
* Selecting or unselecting a list item, such as with Control+Space, says
  "selected" or "not selected" whatever List item state reporting says.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tests") not in sys.path:
	sys.path.insert(0, str(ROOT / "tests"))

from classic_speech_latency_harness import CountingObject, LatencyTestBase, _chain  # noqa: E402
import globalPluginHandler  # noqa: E402
import speech  # noqa: E402
import config  # noqa: E402
import unittest  # noqa: E402


class EditFieldContentsTests(LatencyTestBase):
	def _process(self, sequence, read_contents):
		from globalPlugins._speech_core.base_processor import BaseSpeechProcessor

		section = config.conf.profiles[0].setdefault("classicSpeech", {})
		section["readEditFieldContents"] = read_contents
		window = CountingObject("WINDOW", "Browse For Folder")
		edit = CountingObject("EDITABLETEXT", "Folder:")
		_chain(edit, window)
		self._focus(edit, window)
		processor = BaseSpeechProcessor()
		processor._safe_selected_text = lambda _focus: ""
		output = processor.process(list(sequence))
		return [item for item in output if isinstance(item, str)]

	def test_edit_field_contents_are_read_by_default(self):
		self.assertEqual(
			self._process(["Folder:", "edit", "classicspeech-nvda"], True),
			["Folder:", "edit", "classicspeech-nvda"],
		)

	def test_empty_edit_field_says_blank_when_contents_are_read(self):
		self.assertEqual(self._process(["Search box", "edit", "blank"], True), ["Search box", "edit", "blank"])

	def test_classic_suppression_remains_available(self):
		self.assertEqual(self._process(["Folder:", "edit", "classicspeech-nvda"], False), ["Folder:", "edit"])
		self.assertEqual(self._process(["Search box", "edit", "blank"], False), ["Search box", "edit"])

	def test_selected_prefix_is_still_simplified(self):
		self.assertEqual(
			self._process(["Speech hook loaded message:", "edit", "selected ClassicSpeech hook loaded"], True),
			["Speech hook loaded message:", "edit", "ClassicSpeech hook loaded"],
		)


class ContainerFollowUpTests(LatencyTestBase):
	def _plugin(self):
		plugin = self.module.GlobalPlugin()
		globalPluginHandler.runningPlugins.append(plugin)
		self.addCleanup(plugin.terminate)
		return plugin

	def test_container_before_a_non_item_is_spoken_on_its_own(self):
		plugin = self._plugin()
		window = CountingObject("WINDOW", "New Tab - Google Chrome")
		toolbar = CountingObject("TOOLBAR", "")
		edit = CountingObject("EDITABLETEXT", "Address and search bar")
		_chain(edit, toolbar, window)
		self._focus(edit, toolbar, window)
		plugin.processor._safe_selected_text = lambda _focus: ""
		speech.speak_calls.clear()

		held = plugin._filterSpeechSequence(["tool bar"])
		self.assertEqual(held, [])
		output = plugin._filterSpeechSequence(
			["Address and search bar", "edit", "Press tab then enter to ask AI Mode", "A"]
		)
		text = [item for item in output if isinstance(item, str)]

		self.assertEqual(speech.speak_calls, [["tool bar"]])
		self.assertEqual(text[:2], ["Address and search bar", "edit"])
		# The classifier joins the description and typed contents into one value.
		self.assertTrue(text[-1].endswith(" A"), text)


class SelectionChangeTests(LatencyTestBase):
	def _plugin(self):
		plugin = self.module.GlobalPlugin()
		globalPluginHandler.runningPlugins.append(plugin)
		self.addCleanup(plugin.terminate)
		return plugin

	def test_control_space_in_a_file_list_says_selected_and_not_selected(self):
		# The sequences NVDA 2026.2 sent for Control+Down Arrow, then Control+Space
		# twice, in File Explorer, with List item state reporting on its default.
		plugin = self._plugin()
		window = CountingObject("WINDOW", "File Explorer")
		items = CountingObject("LIST", "Items View")
		item = CountingObject("LISTITEM", "This PC")
		_chain(item, items, window)
		self._focus(item, items, window)

		def speak(sequence):
			return [part for part in plugin._filterSpeechSequence(list(sequence)) if isinstance(part, str)]

		self.assertEqual(speak(["This PC", "not selected", "2 of 41"]), ["This PC", "not selected", "2 of 41"])
		self.assertEqual(speak(["selected"]), ["This PC", "selected"])
		self.assertEqual(speak(["not selected"]), ["This PC", "not selected"])


class MouseRoutingTests(LatencyTestBase):
	def _plugin(self):
		plugin = self.module.GlobalPlugin()
		globalPluginHandler.runningPlugins.append(plugin)
		self.addCleanup(plugin.terminate)
		return plugin

	def test_mouse_tracking_speech_uses_the_mouse_profile(self):
		plugin = self._plugin()
		used = []
		self.module.wrap_mouse_sequence = lambda sequence: used.append(list(sequence)) or list(sequence)
		from globalPlugins._speech_core.prosody_routing import mouse_pointer_profile_routing

		with mouse_pointer_profile_routing():
			output = plugin._filterSpeechSequence(["Recycle Bin"])
		self.assertEqual(used, [["Recycle Bin"]])
		self.assertEqual(output, ["Recycle Bin"])

	def test_mouse_sequence_wrapper_names_the_mouse_profile(self):
		from globalPlugins._speech_core import prosody_routing

		recorded = []
		original = prosody_routing.wrap_profile_sequence
		prosody_routing.wrap_profile_sequence = lambda sequence, profile_id, **kwargs: recorded.append(profile_id) or list(sequence)
		try:
			prosody_routing.wrap_mouse_sequence(["Start"])
		finally:
			prosody_routing.wrap_profile_sequence = original
		self.assertEqual(recorded, ["mouse"])


if __name__ == "__main__":
	unittest.main(verbosity=2)
