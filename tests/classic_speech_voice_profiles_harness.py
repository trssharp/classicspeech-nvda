"""ClassicSpeech v4 Voice Profiles storage, controls, and dialog harness.

Runs outside NVDA with the existing ClassicSpeech stubs. It protects the first
milestone boundary: profile edits are synthesizer-specific snapshots and never
change the live synthesizer unless a future explicit preview does so.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
	sys.path.insert(0, str(ROOT / "tests"))

import classic_speech_nvda_master_harness as nvda_harness  # noqa: E402
import config  # noqa: E402


class ChoiceInfo:
	def __init__(self, item_id, display_name):
		self.id = item_id
		self.displayName = display_name


class ChoiceSetting:
	def __init__(self, setting_id, label):
		self.id = setting_id
		self.displayNameWithAccelerator = label
		self.displayName = label.replace("&", "")


class NumericSetting(ChoiceSetting):
	def __init__(self, setting_id, label, minimum=0, maximum=100, step=5):
		super().__init__(setting_id, label)
		self.minVal = minimum
		self.maxVal = maximum
		self.minStep = step
		self.largeStep = step * 2


class BooleanSetting(ChoiceSetting):
	def __init__(self, setting_id, label):
		super().__init__(setting_id, label)
		self.defaultVal = False


class SettingOwnedChoices(ChoiceSetting):
	"""A generic third-party choice setting without an availableX property."""
	def __init__(self, setting_id, label, choices):
		super().__init__(setting_id, label)
		self.choices = choices


class FakeDriver:
	def __init__(self, name="fakeSynth"):
		self.name = name
		self.voice = "voiceA"
		self.rate = 45
		self.rateBoost = False
		self.supportedSettings = (
			ChoiceSetting("voice", "&Voice"),
			NumericSetting("rate", "&Rate", 0, 100, 5),
			BooleanSetting("rateBoost", "Rate &boost"),
		)
		self.availableVoices = {
			"voiceA": ChoiceInfo("voiceA", "Voice A"),
			"voiceB": ChoiceInfo("voiceB", "Voice B"),
		}


class VoiceDefaultDriver:
	"""A generic driver whose voice assignment loads voice-specific defaults."""
	def __init__(self):
		self.name = "voiceDefaults"
		self._voice = "voiceA"
		self._variant = "variantA"
		self.rate = 40
		self.pitch = 10
		self.breath = 1
		self.supportedSettings = (
			NumericSetting("rate", "&Rate"),
			NumericSetting("pitch", "&Pitch"),
			NumericSetting("breath", "&Breath"),
			ChoiceSetting("voice", "&Voice"),
			ChoiceSetting("variant", "V&ariant"),
		)
		self.availableVoices = {
			"voiceA": ChoiceInfo("voiceA", "Voice A"),
			"voiceB": ChoiceInfo("voiceB", "Voice B"),
		}

	@property
	def voice(self):
		return self._voice

	@voice.setter
	def voice(self, value):
		self._voice = value
		defaults = {
			"voiceA": {"rate": 40, "pitch": 10, "breath": 1},
			"voiceB": {"rate": 70, "pitch": 80, "breath": 9},
		}[value]
		for setting_id, setting_value in defaults.items():
			setattr(self, setting_id, setting_value)

	@property
	def variant(self):
		return self._variant

	@variant.setter
	def variant(self, value):
		self._variant = value
		defaults = {
			"variantA": {
				"voiceA": {"pitch": 10, "breath": 1},
				"voiceB": {"pitch": 80, "breath": 9},
			},
			"variantB": {
				"voiceA": {"pitch": 77, "breath": 8},
				"voiceB": {"pitch": 77, "breath": 8},
			},
		}[value][self._voice]
		for setting_id, setting_value in defaults.items():
			setattr(self, setting_id, setting_value)


class VoiceProfileConfigTests(unittest.TestCase):
	def setUp(self):
		nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
		nvda_harness._import_classic_speech_like_nvda()
		self.driver = FakeDriver()

	def tearDown(self):
		nvda_harness._reset_global_plugin_imports()

	def test_fixed_rows_have_accessible_labels_and_native_row_is_read_only(self):
		from globalPlugins._speech_core.settings.voice_profiles_config import PROFILE_ROWS

		self.assertEqual(
			[(row.profile_id, row.label) for row in PROFILE_ROWS],
			[
				("focusNavigation", "Focus and navigation"),
				("reviewObjectNavigation", "Review and object navigation"),
				("keyboardEntry", "Keyboard entry"),
				("systemNotifications", "System and notifications"),
			],
		)
		self.assertTrue(all(row.editable for row in PROFILE_ROWS))

	def test_list_profiles_cannot_clear_saved_overrides(self):
		from globalPlugins._speech_core.settings.voice_profiles_config import VoiceProfileStore

		store = VoiceProfileStore(self.driver)
		store.set_value("focusNavigation", "rate", 70)
		before = json.loads(json.dumps(store._working_registry))
		for row in store.rows:
			store.get_snapshot(row.profile_id)
		self.assertEqual(store._working_registry, before)

	def test_explicit_reset_all_removes_active_synth_category_overrides_on_apply(self):
		from globalPlugins._speech_core.settings.voice_profiles_config import VoiceProfileStore

		store = VoiceProfileStore(self.driver)
		store.set_value("focusNavigation", "rate", 70)
		store.set_value("reviewObjectNavigation", "rate", 60)
		store.reset_all_overrides()
		self.assertNotIn(store.synth_id, store._working_registry)
		store.apply()
		persisted = json.loads(config.conf.profiles[0]["classicSpeech"]["voiceProfileData"])
		self.assertNotIn(store.synth_id, persisted)

	def test_reset_all_clears_every_active_category_preserves_other_synth_and_saves_once(self):
		from globalPlugins._speech_core.settings.voice_profiles_config import VoiceProfileStore

		active_profiles = {
			"focusNavigation": {"baseline": {"rate": 45}, "overrides": {"rate": 50}},
			"reviewObjectNavigation": {"baseline": {"rate": 45}, "overrides": {"rate": 55}},
			"keyboardEntry": {"baseline": {"rate": 45}, "overrides": {"rate": 60}},
			"systemNotifications": {"baseline": {"rate": 45}, "overrides": {"rate": 65}},
		}
		other_profiles = {
			"focusNavigation": {"baseline": {"rate": 20}, "overrides": {"rate": 25}},
		}
		config.conf.profiles[0].setdefault("classicSpeech", {})["voiceProfileData"] = json.dumps({
			"fakeSynth": active_profiles,
			"otherSynth": other_profiles,
		})
		store = VoiceProfileStore(self.driver)
		events = []
		original_reset = store.reset_all_overrides
		original_apply = store.apply
		original_save = getattr(config.conf, "save", None)
		store.reset_all_overrides = lambda: (events.append("reset"), original_reset())[1]
		store.apply = lambda: (events.append("apply"), original_apply())[1]
		config.conf.save = lambda: events.append("save")
		try:
			store.reset_all_overrides()
			store.apply()
		finally:
			if original_save is None:
				delattr(config.conf, "save")
			else:
				config.conf.save = original_save

		persisted = json.loads(config.conf.profiles[0]["classicSpeech"]["voiceProfileData"])
		self.assertEqual(events, ["reset", "apply", "save"])
		self.assertNotIn("fakeSynth", persisted)
		self.assertEqual(persisted["otherSynth"], other_profiles)

	def test_reset_then_selected_row_refresh_and_cancel_cannot_repersist_active_synth(self):
		from globalPlugins._speech_core.settings.voice_profiles_config import VoiceProfileStore

		config.conf.profiles[0].setdefault("classicSpeech", {})["voiceProfileData"] = json.dumps({
			"fakeSynth": {
				row.profile_id: {"baseline": {"rate": 45}, "overrides": {"rate": index + 50}}
				for index, row in enumerate(VoiceProfileStore(self.driver).rows)
			},
			"otherSynth": {"focusNavigation": {"baseline": {"rate": 20}, "overrides": {}}},
		})
		store = VoiceProfileStore(self.driver)
		store.reset_all_overrides()
		store.apply()
		store.mark_applied()

		# The dialog refreshes its selected row after reset. That lazy read creates
		# a new working record, but Cancel must restore the applied reset state.
		store.get_snapshot("focusNavigation")
		self.assertIn("fakeSynth", store._working_registry)
		store.cancel()
		store.apply()
		persisted = json.loads(config.conf.profiles[0]["classicSpeech"]["voiceProfileData"])
		self.assertNotIn("fakeSynth", persisted)
		self.assertIn("otherSynth", persisted)

	def test_first_access_inherits_independent_current_synth_snapshot(self):
		from globalPlugins._speech_core.settings.voice_profiles_config import VoiceProfileStore

		store = VoiceProfileStore(self.driver)
		focus = store.get_snapshot("focusNavigation")
		self.assertEqual(focus, {"voice": "voiceA", "rate": 45, "rateBoost": False})
		store.set_value("focusNavigation", "rate", 70)
		self.assertEqual(store.get_snapshot("focusNavigation")["rate"], 70)
		self.assertEqual(store.get_snapshot("reviewObjectNavigation")["rate"], 45)
		self.assertEqual(self.driver.rate, 45)

	def test_voice_change_captures_native_baseline_without_leaking_live_values(self):
		from globalPlugins._speech_core.settings.voice_profiles_config import VoiceProfileStore

		driver = VoiceDefaultDriver()
		store = VoiceProfileStore(driver)
		store.get_snapshot("focusNavigation")
		store.set_value("focusNavigation", "voice", "voiceB")
		self.assertEqual((driver.voice, driver.rate, driver.pitch, driver.breath), ("voiceA", 40, 10, 1))
		self.assertEqual(
			store.get_snapshot("focusNavigation"),
			{"voice": "voiceB", "variant": "variantA", "rate": 70, "pitch": 80, "breath": 9},
		)
		stored = store._working_registry["voiceDefaults"]["focusNavigation"]
		self.assertEqual(stored["overrides"], {})

	def test_variant_change_captures_native_defaults_and_preserves_only_explicit_dependents(self):
		from globalPlugins._speech_core.settings.voice_profiles_config import VoiceProfileStore

		driver = VoiceDefaultDriver()
		store = VoiceProfileStore(driver)
		store.set_value("focusNavigation", "voice", "voiceB")
		store.set_value("focusNavigation", "rate", 66)
		store.set_value("focusNavigation", "variant", "variantB")

		self.assertEqual((driver.voice, driver.variant, driver.rate, driver.pitch, driver.breath), ("voiceA", "variantA", 40, 10, 1))
		self.assertEqual(store.get_snapshot("focusNavigation"), {"voice": "voiceB", "variant": "variantB", "rate": 66, "pitch": 77, "breath": 8})
		self.assertEqual(store.get_preview_snapshot("focusNavigation"), {"voice": "voiceB", "variant": "variantB", "rate": 66})

	def test_explicit_dependent_value_overrides_the_voice_native_baseline(self):
		from globalPlugins._speech_core.settings.voice_profiles_config import VoiceProfileStore

		driver = VoiceDefaultDriver()
		store = VoiceProfileStore(driver)
		store.set_value("focusNavigation", "pitch", 33)
		store.set_value("focusNavigation", "voice", "voiceB")
		self.assertEqual(store.get_snapshot("focusNavigation")["pitch"], 33)
		self.assertEqual(
			store.get_preview_snapshot("focusNavigation"),
			{"voice": "voiceB", "variant": "variantA", "pitch": 33},
		)

	def test_legacy_flat_snapshot_is_retained_as_full_explicit_override(self):
		from globalPlugins._speech_core.settings.voice_profiles_config import VoiceProfileStore

		section = {"voiceProfileData": {"fakeSynth": {"focusNavigation": {"voice": "voiceB", "rate": 80}}}}
		store = VoiceProfileStore(self.driver, section)
		self.assertEqual(store.get_snapshot("focusNavigation"), {"voice": "voiceB", "rate": 80})
		self.assertEqual(store.get_preview_snapshot("focusNavigation"), {"voice": "voiceB", "rate": 80})

	def test_legacy_voice_change_migrates_to_selected_voice_native_baseline(self):
		"""A legacy voice choice must discard stale dependent flat overrides."""
		from globalPlugins._speech_core.settings.voice_profiles_config import VoiceProfileStore

		driver = VoiceDefaultDriver()
		section = {
			"voiceProfileData": {
				"voiceDefaults": {
					"focusNavigation": {
						"voice": "voiceA", "rate": 99, "pitch": 98, "breath": 97,
					}
				}
			}
		}
		store = VoiceProfileStore(driver, section)
		store.set_value("focusNavigation", "voice", "voiceB")

		self.assertEqual((driver.voice, driver.rate, driver.pitch, driver.breath), ("voiceA", 40, 10, 1))
		self.assertEqual(
			store.get_snapshot("focusNavigation"),
			{"voice": "voiceB", "variant": "variantA", "rate": 70, "pitch": 80, "breath": 9},
		)
		self.assertEqual(store.get_preview_snapshot("focusNavigation"), {"voice": "voiceB", "variant": "variantA"})
		self.assertEqual(
			store._working_registry["voiceDefaults"]["focusNavigation"],
			{"baseline": {"voice": "voiceB", "variant": "variantA", "rate": 70, "pitch": 80, "breath": 9}, "overrides": {}},
		)

	def test_post_migration_explicit_override_applies_over_selected_voice_native_defaults(self):
		from globalPlugins._speech_core.settings.voice_profiles_config import VoiceProfileStore
		from globalPlugins._speech_core.settings.voice_profiles_preview import PreviewEvents, VoiceProfilePreviewController

		driver = VoiceDefaultDriver()
		section = {"voiceProfileData": {"voiceDefaults": {"focusNavigation": {"voice": "voiceA", "rate": 99}}}}
		store = VoiceProfileStore(driver, section)
		store.set_value("focusNavigation", "voice", "voiceB")
		store.set_value("focusNavigation", "pitch", 33)
		observed = []
		controller = VoiceProfilePreviewController(
			store.get_preview_snapshot("focusNavigation"),
			"A test preview.",
			speak=lambda sequence: observed.append((driver.voice, driver.rate, driver.pitch, driver.breath)),
			index_command_factory=lambda token: ("index", token),
			events=PreviewEvents(FakeAction(), FakeAction(), FakeAction(), FakeAction()),
			scheduler=lambda seconds, callback: FakeTimer(seconds, callback),
			token_factory=lambda: 901,
			active_synth_getter=lambda: driver,
		)
		controller.start()
		self.assertEqual(observed, [("voiceB", 70, 33, 9)])
		controller.cancel()
		self.assertEqual((driver.voice, driver.rate, driver.pitch, driver.breath), ("voiceA", 40, 10, 1))

	def test_synth_records_are_isolated_and_preserved(self):
		from globalPlugins._speech_core.settings.voice_profiles_config import VoiceProfileStore

		first = VoiceProfileStore(self.driver)
		first.set_value("focusNavigation", "rate", 70)
		first.apply()
		other_driver = FakeDriver("otherSynth")
		other_driver.rate = 20
		second = VoiceProfileStore(other_driver)
		self.assertEqual(second.get_snapshot("focusNavigation")["rate"], 20)
		second.apply()
		persisted = json.loads(config.conf.profiles[0]["classicSpeech"]["voiceProfileData"])
		self.assertEqual(persisted["fakeSynth"]["focusNavigation"]["overrides"]["rate"], 70)
		self.assertEqual(persisted["otherSynth"]["focusNavigation"]["baseline"]["rate"], 20)

	def test_apply_persists_through_nvda_config_manager(self):
		from globalPlugins._speech_core.settings.voice_profiles_config import VoiceProfileStore

		calls = []
		original_save = getattr(config.conf, "save", None)
		config.conf.save = lambda: calls.append("saved")
		try:
			store = VoiceProfileStore(self.driver)
			store.set_value("focusNavigation", "rate", 75)
			store.apply()
		finally:
			if original_save is None:
				delattr(config.conf, "save")
			else:
				config.conf.save = original_save
		self.assertEqual(calls, ["saved"])

	def test_all_editable_categories_commit_independent_values_and_cancel_discards_only_unapplied_edits(self):
		from globalPlugins._speech_core.settings.voice_profiles_config import VoiceProfileStore

		store = VoiceProfileStore(self.driver)
		expected = {
			"focusNavigation": 50,
			"reviewObjectNavigation": 55,
			"keyboardEntry": 60,
			"systemNotifications": 65,
		}
		for profile_id, rate in expected.items():
			store.set_value(profile_id, "rate", rate)
		store.apply()
		persisted = json.loads(config.conf.profiles[0]["classicSpeech"]["voiceProfileData"])
		for profile_id, rate in expected.items():
			self.assertEqual(store.get_snapshot(profile_id)["rate"], rate)
			self.assertEqual(
				persisted["fakeSynth"][profile_id]["overrides"]["rate"],
				rate,
			)
		store.mark_applied()
		store.set_value("systemNotifications", "rate", 30)
		store.cancel()
		self.assertEqual(store.get_snapshot("systemNotifications")["rate"], 65)
		self.assertEqual(store.get_snapshot("keyboardEntry")["rate"], 60)

	def test_apply_and_cancel_restore_opening_config_state(self):
		from globalPlugins._speech_core.settings.voice_profiles_config import VoiceProfileStore

		store = VoiceProfileStore(self.driver)
		store.set_value("focusNavigation", "rate", 75)
		store.apply()
		self.assertEqual(store.get_snapshot("focusNavigation")["rate"], 75)
		store.set_value("focusNavigation", "rate", 30)
		store.cancel()
		self.assertEqual(store.get_snapshot("focusNavigation")["rate"], 45)
		self.assertNotIn("voiceProfileData", config.conf.profiles[0]["classicSpeech"])
	def test_preview_restores_all_supported_values_after_success(self):
		from globalPlugins._speech_core.settings.voice_profiles_preview import preview_snapshot

		observed = []
		preview_snapshot(
			self.driver,
			{"voice": "voiceB", "rate": 80, "rateBoost": True},
			lambda: observed.append((self.driver.voice, self.driver.rate, self.driver.rateBoost)),
		)
		self.assertEqual(observed, [("voiceB", 80, True)])
		self.assertEqual((self.driver.voice, self.driver.rate, self.driver.rateBoost), ("voiceA", 45, False))

	def test_preview_restores_all_supported_values_when_sample_fails(self):
		from globalPlugins._speech_core.settings.voice_profiles_preview import preview_snapshot

		with self.assertRaisesRegex(RuntimeError, "sample failed"):
			preview_snapshot(
				self.driver,
				{"voice": "voiceB", "rate": 80, "rateBoost": True},
				lambda: (_ for _ in ()).throw(RuntimeError("sample failed")),
			)
		self.assertEqual((self.driver.voice, self.driver.rate, self.driver.rateBoost), ("voiceA", 45, False))

	def test_preview_restores_all_supported_values_when_snapshot_apply_fails(self):
		from globalPlugins._speech_core.settings.voice_profiles_preview import preview_snapshot

		class FailingDriver(FakeDriver):
			def __init__(self):
				super().__init__()
				self.fail_rate_assignment = True

			def __setattr__(self, name, value):
				if name == "rate" and getattr(self, "fail_rate_assignment", False) and value == 80:
					raise RuntimeError("apply failed")
				super().__setattr__(name, value)

		driver = FailingDriver()
		with self.assertRaisesRegex(RuntimeError, "apply failed"):
			preview_snapshot(driver, {"voice": "voiceB", "rate": 80, "rateBoost": True}, lambda: None)
		self.assertEqual((driver.voice, driver.rate, driver.rateBoost), ("voiceA", 45, False))

	def test_preview_continues_restoration_after_one_restore_error(self):
		from globalPlugins._speech_core.settings.voice_profiles_preview import preview_snapshot

		class RestoreFailingDriver(FakeDriver):
			def __init__(self):
				super().__init__()
				self.fail_restore = True

			def __setattr__(self, name, value):
				if name == "rate" and getattr(self, "fail_restore", False) and value == 45:
					raise RuntimeError("restore failed")
				super().__setattr__(name, value)

		driver = RestoreFailingDriver()
		errors = []
		preview_snapshot(
			driver,
			{"voice": "voiceB", "rate": 80, "rateBoost": True},
			lambda: None,
			errors.append,
		)
		self.assertEqual(errors, ["rate"])
		self.assertEqual(driver.voice, "voiceA")
		self.assertEqual(driver.rate, 80)
		self.assertFalse(driver.rateBoost)


class VoiceProfileControlAndDialogTests(unittest.TestCase):
	def test_adapter_and_dialog_keep_edits_in_snapshot_not_live_driver(self):
		from globalPlugins._speech_core.settings import voice_profile_controls

		driver = FakeDriver()
		snapshot = {"voice": "voiceA", "rate": 45, "rateBoost": False}
		adapter = voice_profile_controls.VoiceProfileControls(driver, snapshot, lambda: None)
		self.assertEqual([item.setting_id for item in adapter.settings], ["voice", "rate", "rateBoost"])
		adapter.set_value("rate", 80)
		adapter.set_value("voice", "voiceB")
		self.assertEqual(snapshot["rate"], 80)
		self.assertEqual(snapshot["voice"], "voiceB")
		self.assertEqual(driver.rate, 45)
		self.assertEqual(driver.voice, "voiceA")

	def test_adapter_uses_nvda_choice_discovery_for_camel_case_driver_ids(self):
		from globalPlugins._speech_core.settings import voice_profile_controls

		class CamelCaseMetadataDriver:
			name = "camelCaseMetadata"
			pauseMode = "2"
			sampleRate = "1"
			supportedSettings = (
				ChoiceSetting("pauseMode", "&Pauses"),
				ChoiceSetting("sampleRate", "Sa&mple Rate"),
			)
			availablePausemodes = {
				"0": ChoiceInfo("0", "Do not shorten"),
				"2": ChoiceInfo("2", "Shorten all pauses"),
			}
			availableSamplerates = {
				"0": ChoiceInfo("0", "8 kHz"),
				"1": ChoiceInfo("1", "11 kHz"),
			}

		adapter = voice_profile_controls.VoiceProfileControls(
			CamelCaseMetadataDriver(), {"pauseMode": "2", "sampleRate": "1"}, lambda: None,
		)
		self.assertEqual([item.setting_id for item in adapter.settings], ["pauseMode", "sampleRate"])
		self.assertIn(("2", "Shorten all pauses"), adapter.settings[0].choices)
		self.assertIn(("1", "11 kHz"), adapter.settings[1].choices)

	def test_adapter_retains_choices_from_setting_owned_option_metadata(self):
		from globalPlugins._speech_core.settings import voice_profile_controls

		class AlternativeMetadataDriver:
			name = "alternativeMetadata"
			quality = "balanced"
			supportedSettings = (
				SettingOwnedChoices(
					"quality", "&Quality", (("fast", "Fast"), ("balanced", "Balanced")),
				),
			)

		snapshot = {"quality": "balanced"}
		adapter = voice_profile_controls.VoiceProfileControls(AlternativeMetadataDriver(), snapshot, lambda: None)
		self.assertEqual([item.setting_id for item in adapter.settings], ["quality"])
		self.assertEqual(adapter.settings[0].choices, (("fast", "Fast"), ("balanced", "Balanced")))
		adapter.set_value("quality", "fast")
		self.assertEqual(snapshot["quality"], "fast")

	def test_numeric_controls_match_nvda_voice_settings_slider_shape(self):
		source = (ROOT / "_speech_core" / "settings" / "voice_profile_controls.py").read_text(encoding="utf-8")
		self.assertIn("nvdaControls.EnhancedInputSlider", source)
		self.assertIn("minValue=setting.minVal", source)
		self.assertIn("maxValue=setting.maxVal", source)
		self.assertIn("control.SetLineSize(setting.minStep)", source)
		self.assertIn("control.SetPageSize(setting.largeStep)", source)
		self.assertIn("wx.EVT_SLIDER", source)
		self.assertNotIn("SelectOnFocusSpinCtrl", source)

	def test_refresh_snapshot_values_updates_built_dependents_without_callback(self):
		from globalPlugins._speech_core.settings import voice_profile_controls

		class FakeNumericControl:
			def __init__(self):
				self.value = None
			def SetValue(self, value):
				self.value = value

		class FakeBooleanControl(FakeNumericControl):
			pass

		class FakeChoiceControl:
			def __init__(self):
				self.selection = None
			def SetSelection(self, selection):
				self.selection = selection

		class RefreshDriver(FakeDriver):
			def __init__(self):
				super().__init__()
				self.quality = "balanced"
				self.supportedSettings += (
					SettingOwnedChoices("quality", "&Quality", (("fast", "Fast"), ("balanced", "Balanced"))),
				)

		driver = RefreshDriver()
		snapshot = {"voice": "voiceB", "rate": 70, "rateBoost": True, "quality": "fast"}
		changes = []
		adapter = voice_profile_controls.VoiceProfileControls(driver, snapshot, lambda *args: changes.append(args))
		rate = FakeNumericControl()
		rate_boost = FakeBooleanControl()
		voice = FakeChoiceControl()
		quality = FakeChoiceControl()
		adapter._controls_by_setting_id = {
			"rate": rate, "rateBoost": rate_boost, "voice": voice, "quality": quality,
		}

		self.assertTrue(adapter.refresh_snapshot_values(skip_setting_id="voice"))
		self.assertEqual((rate.value, rate_boost.value), (70, True))
		self.assertIsNone(voice.selection)
		self.assertEqual(quality.selection, 0)
		self.assertEqual(changes, [])

	def test_refresh_snapshot_values_reports_schema_mismatch_for_safe_rebuild(self):
		from globalPlugins._speech_core.settings import voice_profile_controls

		adapter = voice_profile_controls.VoiceProfileControls(
			FakeDriver(), {"voice": "voiceB", "rate": 80, "rateBoost": True}, lambda: None,
		)
		adapter._controls_by_setting_id = {"voice": object(), "rate": object()}
		self.assertFalse(adapter.refresh_snapshot_values(skip_setting_id="voice"))

	def test_dialog_source_declares_required_accessible_structure_and_transaction_hooks(self):
		source = (ROOT / "_speech_core" / "settings" / "voice_profiles_dialog.py").read_text(encoding="utf-8")
		for expected in (
			"nvdaControls.AutoWidthColumnListCtrl",
			"Voice profiles",
			"scrolledpanel.ScrolledPanel",
			"SetupScrolling(scroll_x=False)",
			"Pre&view selected profile",
			"Preview &text:",
			"wx.TextCtrl",
			"DEFAULT_PREVIEW_TEXT",
			"VoiceProfilePreviewController(",
			"speech.speak",
			"IndexCommand",
			"synthDriverHandler.synthIndexReached",
			"synthDriverHandler.synthDoneSpeaking",
			"speechExtensions.speechCanceled",
			"Previewing selected profile...",
			"self.profileList.Enable(not busy)",
			"self._cancelPreview()",
			"self.previewBtn.Enable(row.editable and not self._preview_is_active())",
			"Reset all Voice Profile overrides",
			"self.resetBtn.SetName(_(\"Reset all Voice Profile overrides\"))",
			"self.onResetAllOverrides",
			"wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING",
			"self.store.reset_all_overrides()",
			"MoveAfterInTabOrder(self.cancelBtn)",
			"self.store.apply()",
			"self.store.cancel()",
		):
			self.assertIn(expected, source)

	def test_voice_change_refreshes_dependents_in_place_before_safe_rebuild_fallback(self):
		source = (ROOT / "_speech_core" / "settings" / "voice_profiles_dialog.py").read_text(encoding="utf-8")
		selector_block = source.split('if setting_id in {"voice", "variant"}:', 1)[1].split("\n	def _focus_editor_control", 1)[0]
		self.assertIn('refresh_snapshot_values(skip_setting_id="voice")', selector_block)
		self.assertIn("self._show_profile(", selector_block)
		self.assertLess(
			selector_block.index('refresh_snapshot_values(skip_setting_id="voice")'),
			selector_block.index("self._show_profile("),
		)

	def test_profile_navigation_has_no_destructive_branch(self):
		source = (ROOT / "_speech_core" / "settings" / "voice_profiles_dialog.py").read_text(encoding="utf-8")
		self.assertNotIn("nvdaDefault", source)
		self.assertNotIn("select_nvda_default", source)

	def test_reset_dialog_no_keeps_existing_profiles_without_saving(self):
		from globalPlugins._speech_core.settings import voice_profiles_dialog
		from globalPlugins._speech_core.settings.voice_profiles_config import VoiceProfileStore

		store = VoiceProfileStore(FakeDriver())
		store.set_value("focusNavigation", "rate", 70)
		store.apply()
		before = config.conf.profiles[0]["classicSpeech"]["voiceProfileData"]
		original_message_box = voice_profiles_dialog.wx.MessageBox
		original_icon_warning = getattr(voice_profiles_dialog.wx, "ICON_WARNING", None)
		original_save = getattr(config.conf, "save", None)
		save_calls = []
		voice_profiles_dialog.wx.ICON_WARNING = 0
		voice_profiles_dialog.wx.MessageBox = lambda *args, **kwargs: 0
		config.conf.save = lambda: save_calls.append("save")
		try:
			probe = _ResetDialogProbe(store)
			voice_profiles_dialog.VoiceProfilesDialog.onResetAllOverrides(probe, None)
		finally:
			voice_profiles_dialog.wx.MessageBox = original_message_box
			if original_icon_warning is None:
				delattr(voice_profiles_dialog.wx, "ICON_WARNING")
			else:
				voice_profiles_dialog.wx.ICON_WARNING = original_icon_warning
			if original_save is None:
				delattr(config.conf, "save")
			else:
				config.conf.save = original_save

		self.assertEqual(probe.preview_cancellations, 1)
		self.assertEqual(probe.shown_profiles, [])
		self.assertEqual(save_calls, [])
		self.assertEqual(config.conf.profiles[0]["classicSpeech"]["voiceProfileData"], before)

	def test_reset_dialog_yes_saves_once_refreshes_selected_row_and_cancel_keeps_reset(self):
		from globalPlugins._speech_core.settings import voice_profiles_dialog
		from globalPlugins._speech_core.settings.voice_profiles_config import VoiceProfileStore

		store = VoiceProfileStore(FakeDriver())
		for index, row in enumerate(store.rows):
			store.set_value(row.profile_id, "rate", 50 + index)
		store.apply()
		other_store = VoiceProfileStore(FakeDriver("otherSynth"))
		other_store.set_value("focusNavigation", "rate", 25)
		other_store.apply()
		store = VoiceProfileStore(FakeDriver())
		events = []
		original_message_box = voice_profiles_dialog.wx.MessageBox
		original_icon_warning = getattr(voice_profiles_dialog.wx, "ICON_WARNING", None)
		original_save = getattr(config.conf, "save", None)
		original_reset = store.reset_all_overrides
		original_apply = store.apply
		voice_profiles_dialog.wx.ICON_WARNING = 0
		voice_profiles_dialog.wx.MessageBox = lambda *args, **kwargs: voice_profiles_dialog.wx.YES
		config.conf.save = lambda: events.append("save")
		store.reset_all_overrides = lambda: (events.append("reset"), original_reset())[1]
		store.apply = lambda: (events.append("apply"), original_apply())[1]
		try:
			probe = _ResetDialogProbe(store, events)
			voice_profiles_dialog.VoiceProfilesDialog.onResetAllOverrides(probe, None)
			voice_profiles_dialog.VoiceProfilesDialog.onCancel(probe, None)
		finally:
			voice_profiles_dialog.wx.MessageBox = original_message_box
			if original_icon_warning is None:
				delattr(voice_profiles_dialog.wx, "ICON_WARNING")
			else:
				voice_profiles_dialog.wx.ICON_WARNING = original_icon_warning
			if original_save is None:
				delattr(config.conf, "save")
			else:
				config.conf.save = original_save

		persisted = json.loads(config.conf.profiles[0]["classicSpeech"]["voiceProfileData"])
		self.assertEqual(events, ["reset", "apply", "save", "show", "clear", "destroy"])
		self.assertEqual(probe.preview_cancellations, 2)
		self.assertNotIn("fakeSynth", persisted)
		self.assertIn("otherSynth", persisted)

	def test_reset_dialog_close_after_selected_row_refresh_cannot_repersist_active_synth(self):
		from globalPlugins._speech_core.settings import voice_profiles_dialog
		from globalPlugins._speech_core.settings.voice_profiles_config import VoiceProfileStore

		store = VoiceProfileStore(FakeDriver())
		for index, row in enumerate(store.rows):
			store.set_value(row.profile_id, "rate", 50 + index)
		store.apply()
		store.reset_all_overrides()
		store.apply()
		store.mark_applied()
		probe = _ResetDialogProbe(store)
		probe._show_profile(store.rows[0])
		event = _CloseEvent()
		voice_profiles_dialog.VoiceProfilesDialog.onClose(probe, event)
		store.apply()

		persisted = json.loads(config.conf.profiles[0]["classicSpeech"]["voiceProfileData"])
		self.assertTrue(event.skipped)
		self.assertEqual(probe.preview_cancellations, 1)
		self.assertNotIn("fakeSynth", persisted)


class _ResetDialogProbe:
	"""Small handler receiver that exercises reset without constructing wx widgets."""
	def __init__(self, store, events=None):
		self.store = store
		self.currentProfileId = "focusNavigation"
		self.preview_cancellations = 0
		self.shown_profiles = []
		self.events = events if events is not None else []

	def _cancelPreview(self):
		self.preview_cancellations += 1

	def _show_profile(self, row):
		self.shown_profiles.append(row.profile_id)
		self.store.get_snapshot(row.profile_id)
		self.events.append("show")

	def _clearDirty(self):
		self.events.append("clear")

	def Destroy(self):
		self.events.append("destroy")


class _CloseEvent:
	def __init__(self):
		self.skipped = False

	def Skip(self):
		self.skipped = True


class FakeAction:
	def __init__(self):
		self.handlers = []

	def register(self, handler):
		self.handlers.append(handler)

	def unregister(self, handler):
		if handler in self.handlers:
			self.handlers.remove(handler)

	def emit(self, **kwargs):
		for handler in list(self.handlers):
			handler(**kwargs)


class FakeTimer:
	def __init__(self, seconds, callback):
		self.seconds = seconds
		self.callback = callback
		self.stopped = False

	def Stop(self):
		self.stopped = True

	def fire(self):
		if not self.stopped:
			self.callback()


class PreviewLifecycleTests(unittest.TestCase):
	def setUp(self):
		from _speech_core.settings.voice_profiles_preview import PreviewEvents

		self.driver = FakeDriver()
		self.other_driver = FakeDriver("other")
		self.driver.cancel_calls = 0
		self.other_driver.cancel_calls = 0
		self.driver.cancel = lambda: setattr(self.driver, "cancel_calls", self.driver.cancel_calls + 1)
		self.other_driver.cancel = lambda: setattr(self.other_driver, "cancel_calls", self.other_driver.cancel_calls + 1)
		self.index = FakeAction()
		self.done = FakeAction()
		self.changed = FakeAction()
		self.canceled = FakeAction()
		self.events = PreviewEvents(self.index, self.done, self.changed, self.canceled)
		self.active_driver = self.driver
		self.timers = []
		self.spoken = []
		self.finished = []
		self.restore_errors = []
		self.next_token = 700

	def _controller(self, snapshot=None, speak=None, driver_getter=None):
		from _speech_core.settings.voice_profiles_preview import VoiceProfilePreviewController

		def schedule(seconds, callback):
			timer = FakeTimer(seconds, callback)
			self.timers.append(timer)
			return timer

		def token_factory():
			self.next_token += 1
			return self.next_token

		return VoiceProfilePreviewController(
			snapshot or {"voice": "voiceB", "rate": 80, "rateBoost": True},
			"A test preview.",
			speak=speak or self.spoken.append,
			index_command_factory=lambda token: ("index", token),
			events=self.events,
			scheduler=schedule,
			token_factory=token_factory,
			active_synth_getter=driver_getter or (lambda: self.active_driver),
			on_restore_error=self.restore_errors.append,
			on_finished=self.finished.append,
		)

	def _assert_restored(self):
		self.assertEqual((self.driver.voice, self.driver.rate, self.driver.rateBoost), ("voiceA", 45, False))

	def test_success_requires_matching_index_then_matching_done(self):
		controller = self._controller()
		self.assertTrue(controller.start())
		self.assertEqual(self.spoken, [["A test preview.", ("index", controller.token)]])
		self.assertEqual((self.driver.voice, self.driver.rate, self.driver.rateBoost), ("voiceB", 80, True))
		self.done.emit(synth=self.driver)  # Completion before our terminal index.
		self.index.emit(synth=self.other_driver, index=controller.token)
		self.index.emit(synth=self.driver, index=controller.token + 1)
		self.assertTrue(controller.active)
		self.index.emit(synth=self.driver, index=controller.token)
		self.done.emit(synth=self.other_driver)
		self.assertTrue(controller.active)
		self.done.emit(synth=self.driver)
		self.assertFalse(controller.active)
		self.assertEqual(self.finished, ["completed"])
		self.assertTrue(self.timers[0].stopped)
		self._assert_restored()

	def test_preview_uses_selected_voice_native_defaults_then_explicit_overrides(self):
		from _speech_core.settings.voice_profiles_preview import VoiceProfilePreviewController

		driver = VoiceDefaultDriver()
		observed = []
		controller = VoiceProfilePreviewController(
			{"voice": "voiceB", "variant": "variantA", "pitch": 33},
			"A test preview.",
			speak=lambda sequence: observed.append((driver.voice, driver.rate, driver.pitch, driver.breath)),
			index_command_factory=lambda token: ("index", token),
			events=self.events,
			scheduler=lambda seconds, callback: FakeTimer(seconds, callback),
			token_factory=lambda: 901,
			active_synth_getter=lambda: driver,
		)
		controller.start()
		self.assertEqual(observed, [("voiceB", 70, 33, 9)])
		controller.cancel()
		self.assertEqual((driver.voice, driver.rate, driver.pitch, driver.breath), ("voiceA", 40, 10, 1))

	def test_global_cancel_race_is_terminal_and_late_events_are_noops(self):
		controller = self._controller()
		controller.start()
		self.canceled.emit()
		self._assert_restored()
		self.assertEqual(self.finished, ["speechCanceled"])
		self.index.emit(synth=self.driver, index=controller.token)
		self.done.emit(synth=self.driver)
		self.timers[0].fire()
		self.assertEqual(self.finished, ["speechCanceled"])
		self.assertEqual(self.driver.cancel_calls, 0)

	def test_cancel_during_speak_restores_without_arming_a_late_timeout(self):
		controller = self._controller(speak=lambda sequence: self.canceled.emit())
		self.assertTrue(controller.start())
		self.assertFalse(controller.active)
		self.assertEqual(self.finished, ["speechCanceled"])
		self.assertEqual(self.timers, [])
		self._assert_restored()

	def test_explicit_cancel_cancels_only_captured_active_driver_and_restores(self):
		controller = self._controller()
		controller.start()
		controller.cancel()
		self.assertEqual(self.driver.cancel_calls, 1)
		self.assertEqual(self.other_driver.cancel_calls, 0)
		self.assertEqual(self.finished, ["canceled"])
		self._assert_restored()
		self.assertEqual(len(self.index.handlers), 0)
		controller.cancel()
		self.assertEqual(self.driver.cancel_calls, 1)

	def test_timeout_cancels_only_captured_active_driver_then_restores(self):
		controller = self._controller()
		controller.start()
		self.assertGreaterEqual(self.timers[0].seconds, 15)
		self.assertLessEqual(self.timers[0].seconds, 30)
		self.timers[0].fire()
		self.assertEqual(self.driver.cancel_calls, 1)
		self.assertEqual(self.finished, ["timedOut"])
		self._assert_restored()

	def test_start_failures_restore_and_release_busy(self):
		controller = self._controller(speak=lambda sequence: (_ for _ in ()).throw(RuntimeError("speak failed")))
		with self.assertRaisesRegex(RuntimeError, "speak failed"):
			controller.start()
		self.assertFalse(controller.active)
		self._assert_restored()
		self.assertEqual(self.finished, ["startError"])

		class ApplyFailingDriver(FakeDriver):
			def __init__(self):
				super().__init__()
				self.fail_apply = True
			def __setattr__(self, name, value):
				if name == "rate" and value == 80 and getattr(self, "fail_apply", False):
					raise RuntimeError("apply failed")
				super().__setattr__(name, value)

		failing = ApplyFailingDriver()
		self.active_driver = failing
		controller = self._controller()
		with self.assertRaisesRegex(RuntimeError, "apply failed"):
			controller.start()
		self.assertFalse(controller.active)
		self.assertEqual((failing.voice, failing.rate, failing.rateBoost), ("voiceA", 45, False))

	def test_restore_error_continues_duplicate_start_rejected_and_synth_change_ends_preview(self):
		class RestoreFailingDriver(FakeDriver):
			def __init__(self):
				super().__init__()
				self.fail_restore = True
			def __setattr__(self, name, value):
				if name == "rate" and value == 45 and getattr(self, "fail_restore", False):
					raise RuntimeError("restore failed")
				super().__setattr__(name, value)

		self.driver = RestoreFailingDriver()
		self.driver.cancel_calls = 0
		self.driver.cancel = lambda: setattr(self.driver, "cancel_calls", self.driver.cancel_calls + 1)
		self.active_driver = self.driver
		controller = self._controller()
		self.assertTrue(controller.start())
		self.assertFalse(controller.start())
		self.changed.emit(synth=self.other_driver)
		self.assertEqual(self.finished, ["synthChanged"])
		self.assertEqual(self.restore_errors, ["rate"])
		self.assertEqual(self.driver.voice, "voiceA")
		self.assertFalse(self.driver.rateBoost)


if __name__ == "__main__":
	unittest.main()
