"""NVDA settings stay where the user put them, whatever ClassicSpeech is doing.

* Cancel in Web / Browse Mode Settings puts back each NVDA setting the dialog
  changes, exactly as it was stored, in the configuration profile it changed.
* A voice profile's temporary overlay must not swallow NVDA settings saved
  while its voice speaks: they are kept when it ends, apart from the overlay's
  own voice settings.
* While NVDA's or ClassicSpeech's settings dialogs or the NVDA menu are open,
  voice overlays pause, as NVDA's own configuration profiles do, except for a
  preview the user asked for.

The fake configuration manager stores values in profiles and writes to the
newest one, as NVDA 2026.2's ConfigManager does.
"""
from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tests") not in sys.path:
	sys.path.insert(0, str(ROOT / "tests"))

import classic_speech_nvda_master_harness as nvda_harness  # noqa: E402
import classic_speech_settings_removal_harness as removal  # noqa: E402
import config  # noqa: E402

FakeConfigManager = removal.FakeConfigManager
FakeProfile = removal.FakeProfile


class _NVDAConfigTestCase(unittest.TestCase):
	"""Import ClassicSpeech like NVDA, with an NVDA-like config.conf."""

	def setUp(self):
		nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
		nvda_harness._import_classic_speech_like_nvda()
		self._saved_conf = config.conf
		self._saved_gui = sys.modules.get("gui")

	def tearDown(self):
		config.conf = self._saved_conf
		if self._saved_gui is None:
			sys.modules.pop("gui", None)
		else:
			sys.modules["gui"] = self._saved_gui
		nvda_harness._reset_global_plugin_imports()

	def _use_config(self, base, *profiles):
		conf = FakeConfigManager(base)
		for profile in profiles:
			conf.profiles.append(profile)
			if getattr(profile, "name", None):
				conf._profileCache[profile.name] = profile
		config.conf = conf
		return conf

	def _settings_gui_open(self, is_open):
		gui = types.ModuleType("gui")
		gui.shouldConfigProfileTriggersBeSuspended = lambda: is_open
		sys.modules["gui"] = gui


class WebBrowseCancelTests(_NVDAConfigTestCase):
	def setUp(self):
		super().setUp()
		self.web = importlib.import_module("globalPlugins._speech_core.settings.web.formatting_config")

	def _base(self):
		return FakeProfile({
			"virtualBuffers": {"linesPerPage": "40", "maxLineLength": "not a number", "loadChromiumVBufOnBusyState": "DEFAULT"},
			"documentFormatting": {"reportLinks": "False", "reportFontName": "True"},
			"annotations": {},
			"braille": {"reportLiveRegions": "DEFAULT", "messageTimeout": "4"},
		})

	def _change_everything(self, conf):
		from globalPlugins._speech_core.nvda_settings_backup import recording_nvda_change

		self.web.set_virtual_buffer_setting("linesPerPage", 55)
		self.web.set_virtual_buffer_setting("maxLineLength", 120)
		self.web.set_web_document_formatting_setting("reportLinks", True)
		self.web.set_annotation_setting("reportDetails", True)
		# The dialog's feature flag combo boxes write through config.conf, as the dialog wraps them.
		with recording_nvda_change(("braille",), "reportLiveRegions"):
			conf["braille"]["reportLiveRegions"] = "DISABLED"
		with recording_nvda_change(("virtualBuffers",), "loadChromiumVBufOnBusyState"):
			conf["virtualBuffers"]["loadChromiumVBufOnBusyState"] = "DISABLED"

	def test_cancel_puts_back_exactly_what_was_stored(self):
		base = self._base()
		conf = self._use_config(base)
		snapshot = self.web.capture_web_browse_state()
		self._change_everything(conf)
		self.assertEqual(base["virtualBuffers"]["linesPerPage"], 55)
		self.web.restore_web_browse_state(snapshot)
		self.assertEqual(base, self._base(), "every setting is stored exactly as before, even a malformed one")

	def test_cancel_changes_only_the_profile_the_dialog_changed(self):
		base = self._base()
		word = FakeProfile({"virtualBuffers": {"linesPerPage": "10"}}, name="Word", filename="Word.ini")
		conf = self._use_config(base, word)
		snapshot = self.web.capture_web_browse_state()
		self._change_everything(conf)
		self.assertEqual(word["virtualBuffers"]["linesPerPage"], 55)
		self.web.restore_web_browse_state(snapshot)
		self.assertEqual(word, FakeProfile({"virtualBuffers": {"linesPerPage": "10"}, "documentFormatting": {}, "annotations": {}, "braille": {}}))
		self.assertEqual(base, self._base())
		self.assertIn("Word", conf._dirtyProfiles)

	def test_cancel_works_while_a_voice_profile_voice_speaks(self):
		base = self._base()
		overlay = FakeProfile({"speech": {"espeak": {"rate": "30"}}})
		conf = self._use_config(base, overlay)
		snapshot = self.web.capture_web_browse_state()
		self._change_everything(conf)
		self.assertEqual(base["virtualBuffers"]["linesPerPage"], 55, "changes reach the saved configuration")
		self.assertNotIn("virtualBuffers", overlay)
		self.web.restore_web_browse_state(snapshot)
		self.assertEqual(base, self._base())
		self.assertIs(conf.profiles[-1], overlay)

	def test_one_failed_part_of_cancel_does_not_stop_the_rest(self):
		from globalPlugins._speech_core.settings.web.dialog import WebBrowseSettingsDialog

		dialog = object.__new__(WebBrowseSettingsDialog)
		restored = []

		def fail():
			raise ValueError("Value must be a section")

		dialog._restoreNativeWebBrowseBaseline = fail
		dialog._restoreModeIndicationBaseline = lambda: restored.append("mode")
		dialog._restoreHeadingContinuityBaseline = lambda: restored.append("heading")
		dialog._restorePageSummaryBaseline = lambda: restored.append("summary")
		dialog._restoreEdgeNotificationBaseline = lambda: restored.append("edge")
		dialog._restoreTransactionBaseline()
		self.assertEqual(restored, ["mode", "heading", "summary", "edge"])


class VoiceOverlayCarryTests(_NVDAConfigTestCase):
	def setUp(self):
		super().setUp()
		self._settings_gui_open(False)
		self.overlay_module = importlib.import_module("globalPlugins._speech_core.voice_profile_overlay")
		self.trigger_module = importlib.import_module("globalPlugins._speech_core.voice_profile_trigger")
		self.base = FakeProfile({
			"speech": {"synth": "espeak", "espeak": {"voice": "en", "rate": "50"}},
			"presentation": {"reportTooltips": "False"},
		})
		self.conf = self._use_config(self.base)

	def _overlay(self, rate="30"):
		return self.overlay_module.VoiceProfileOverlay(
			self.conf, "espeak", {"voice": "en-gb", "rate": rate}, profile_factory=FakeProfile
		)

	def test_a_setting_saved_while_the_profile_voice_speaks_is_kept(self):
		overlay = self._overlay()
		overlay.enter()
		# The user presses OK in NVDA's settings before the voice finishes.
		self.conf["presentation"]["reportTooltips"] = True
		self.conf["documentFormatting"]["reportFontName"] = True
		self.assertIn("presentation", overlay._profile, "NVDA stores it in the newest profile")
		overlay.exit()
		self.assertEqual(self.base["presentation"]["reportTooltips"], True)
		self.assertEqual(self.base["documentFormatting"]["reportFontName"], True)
		self.assertEqual(self.conf.profiles, [self.base])

	def test_the_profile_voice_itself_is_never_kept(self):
		overlay = self._overlay()
		overlay.enter()
		# NVDA saves the synthesizer's current settings, the profile's voice, on a configuration save;
		# a synthesizer may round them, and the synth settings ring may change them.
		self.conf["speech"]["espeak"]["rate"] = 31
		self.conf["speech"]["espeak"]["voice"] = "en-us"
		self.assertEqual(overlay._profile["speech"]["espeak"]["rate"], 31)
		overlay.exit()
		self.assertEqual(self.base["speech"]["espeak"], {"voice": "en", "rate": "50"})

	def test_other_speech_settings_and_a_new_synthesizer_are_kept(self):
		overlay = self._overlay()
		overlay.enter()
		self.conf["speech"]["symbolLevel"] = 300
		self.conf["speech"]["synth"] = "oneCore"
		overlay.exit()
		self.assertEqual(self.base["speech"]["symbolLevel"], 300)
		self.assertEqual(self.base["speech"]["synth"], "oneCore")

	def test_nested_overlays_pass_changes_down_to_the_saved_configuration(self):
		outer, inner = self._overlay("30"), self._overlay("20")
		outer.enter()
		inner.enter()
		self.conf["presentation"]["reportTooltips"] = True
		inner.exit()
		self.assertEqual(outer._profile["presentation"]["reportTooltips"], True)
		outer.exit()
		self.assertEqual(self.base["presentation"]["reportTooltips"], True)

	def _cross_synth_trigger(self):
		active = [types.SimpleNamespace(name="espeak")]
		trigger = self.trigger_module.CrossSynthProfileTrigger(
			"role.LINK", "ibmeci", {"rate": 80}, config_manager=self.conf,
			profile_factory=FakeProfile, active_synth_getter=lambda: active[0],
		)
		return trigger, active

	def test_another_synthesizer_keeps_speech_settings_out_but_other_changes_in(self):
		trigger, active = self._cross_synth_trigger()
		trigger.enter()
		# NVDA unloads the user's synthesizer, saving its settings (here rounded), and loads the item's.
		self.conf["speech"]["espeak"]["rate"] = 51
		active[0] = removal._FakeDriver()
		self.conf["speech"]["ibmeci"]["rate"] = 81
		self.conf["presentation"]["reportTooltips"] = True
		trigger.exit()
		self.assertEqual(self.base["presentation"]["reportTooltips"], True)
		self.assertEqual(self.base["speech"], {"synth": "espeak", "espeak": {"voice": "en", "rate": "50"}})

	def test_a_synthesizer_the_user_chooses_meanwhile_is_kept(self):
		trigger, _active = self._cross_synth_trigger()
		trigger.enter()
		self.conf["speech"]["synth"] = "oneCore"
		trigger.exit()
		self.assertEqual(self.base["speech"]["synth"], "oneCore")


class SettingsDialogPauseTests(_NVDAConfigTestCase):
	def setUp(self):
		super().setUp()
		self.runtime = importlib.import_module("globalPlugins._speech_core.voice_profile_runtime")
		self.trigger_module = importlib.import_module("globalPlugins._speech_core.voice_profile_trigger")
		self.base = FakeProfile({"speech": {"synth": "espeak", "espeak": {"voice": "en", "rate": 50}}})
		self.conf = self._use_config(self.base)
		self.driver = types.SimpleNamespace(
			name="espeak",
			voice="en",
			rate=50,
			supportedSettings=(types.SimpleNamespace(id="voice"), types.SimpleNamespace(id="rate")),
		)

	def _trigger(self, preview=False):
		return self.runtime.make_voice_profile_overlay_trigger(
			"focusNavigation", self.conf, self.driver, {"voice": "en-gb", "rate": 30},
			profile_factory=FakeProfile, preview=preview,
		)

	def test_voice_profiles_pause_while_a_settings_dialog_or_the_nvda_menu_is_open(self):
		self._settings_gui_open(True)
		trigger = self._trigger()
		trigger.enter()
		self.assertEqual(self.conf.profiles, [self.base])
		self.assertEqual((self.driver.voice, self.driver.rate), ("en", 50))
		trigger.exit()
		self.assertEqual(self.conf.profiles, [self.base])

	def test_a_preview_still_speaks_with_the_profile_voice(self):
		self._settings_gui_open(True)
		trigger = self._trigger(preview=True)
		trigger.enter()
		self.assertEqual(len(self.conf.profiles), 2)
		self.assertEqual(self.driver.voice, "en-gb")
		trigger.exit()
		self.assertEqual(self.conf.profiles, [self.base])
		self.assertEqual((self.driver.voice, self.driver.rate), ("en", 50))

	def test_voice_profiles_apply_again_once_settings_are_closed(self):
		self._settings_gui_open(True)
		trigger = self._trigger()
		trigger.enter()
		trigger.exit()
		self._settings_gui_open(False)
		trigger.enter()
		self.assertEqual(len(self.conf.profiles), 2)
		trigger.exit()
		self.assertEqual(self.conf.profiles, [self.base])

	def test_another_synthesizer_pauses_too(self):
		self._settings_gui_open(True)
		trigger = self.trigger_module.CrossSynthProfileTrigger(
			"role.LINK", "ibmeci", {}, config_manager=self.conf, profile_factory=FakeProfile,
			active_synth_getter=lambda: self.driver,
		)
		trigger.enter()
		self.assertEqual(self.conf.profiles, [self.base])
		trigger.exit()

	def test_scheme_previews_are_marked_as_previews(self):
		source = (ROOT / "_speech_core" / "settings" / "schemes_panel.py").read_text(encoding="utf-8")
		preview = source.split("def preview_with_active_synthesizer", 1)[1].split("\ndef ", 1)[0]
		self.assertIn("preview=True", preview)

	def test_classic_speech_settings_dialogs_pause_profiles_like_nvdas_own(self):
		from globalPlugins._speech_core.settings.dialog import ClassicSpeechDialog
		from globalPlugins._speech_core.settings.schemes_dialog import SpeechSoundSchemesDialog
		from globalPlugins._speech_core.settings.voice_profiles_dialog import VoiceProfilesDialog
		from globalPlugins._speech_core.settings.web.dialog import WebBrowseSettingsDialog

		from globalPlugins._speech_core.settings.presets.dialog import PresentationPresetsDialog

		for dialog in (ClassicSpeechDialog, PresentationPresetsDialog, WebBrowseSettingsDialog, VoiceProfilesDialog, SpeechSoundSchemesDialog):
			self.assertIs(getattr(dialog, "shouldSuspendConfigProfileTriggers", False), True, dialog.__name__)

	def test_without_nvdas_gui_voice_profiles_are_not_paused(self):
		sys.modules.pop("gui", None)
		sys.modules["gui"] = types.ModuleType("gui")
		self.assertFalse(self.trigger_module.settings_gui_open())


if __name__ == "__main__":
	unittest.main()
