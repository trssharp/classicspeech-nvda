"""Pure regression gate for ClassicSpeech's temporary active-synth config overlay."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


class Setting:
	def __init__(self, setting_id):
		self.id = setting_id
		self.useConfig = True


class FakeDriver:
	"""A driver whose voice selection normally changes dependent defaults."""

	name = "fakeSynth"

	def __init__(self):
		self.supportedSettings = tuple(Setting(setting_id) for setting_id in (
			"variant", "rateBoost", "rate", "voice",
		))
		self.voice = "voiceA"
		self.variant = "standard"
		self.rateBoost = False
		self.rate = 40
		self.loads = []

	def loadSettings(self, onlyChanged=False, snapshot=None):
		for setting in self.supportedSettings:
			value = snapshot.get(setting.id)
			if value is None or (onlyChanged and getattr(self, setting.id) == value):
				continue
			setattr(self, setting.id, value)
		self.loads.append((onlyChanged, dict(snapshot)))


class FakeConfigManager:
	def __init__(self, base):
		self.profiles = [base]
		self.switches = []

	def _handleProfileSwitch(self, shouldNotify=False):
		self.switches.append(shouldNotify)

	def effective_snapshot(self, synth_name):
		result = {}
		for profile in self.profiles:
			result.update(profile.get("speech", {}).get(synth_name, {}))
		return result


class FullSynthOverlayTests(unittest.TestCase):
	def setUp(self):
		self.base = {
			"speech": {
				"synth": "fakeSynth",
				"fakeSynth": {
					"voice": "voiceA", "variant": "standard", "rateBoost": False, "rate": 40,
				},
			}
		}
		self.config = FakeConfigManager(self.base)
		self.driver = FakeDriver()
		self.profile = {
			"voice": "voiceB", "variant": "expressive", "rateBoost": True, "rate": 70,
		}

	def _load_current_config(self):
		self.driver.loadSettings(onlyChanged=True, snapshot=self.config.effective_snapshot(self.driver.name))

	def test_enter_and_exit_use_full_resolved_snapshot_without_direct_driver_mutation(self):
		from _speech_core.voice_profile_overlay import VoiceProfileOverlay

		overlay = VoiceProfileOverlay(self.config, self.driver.name, self.profile, profile_factory=dict)
		overlay.enter()
		self.assertEqual(self.config.effective_snapshot(self.driver.name), self.profile)
		self.assertEqual((self.driver.voice, self.driver.variant, self.driver.rateBoost, self.driver.rate),
			("voiceA", "standard", False, 40))
		self._load_current_config()
		self.assertEqual((self.driver.voice, self.driver.variant, self.driver.rateBoost, self.driver.rate),
			("voiceB", "expressive", True, 70))
		overlay.exit()
		self._load_current_config()
		self.assertEqual((self.driver.voice, self.driver.variant, self.driver.rateBoost, self.driver.rate),
			("voiceA", "standard", False, 40))
		self.assertEqual(self.config.profiles, [self.base])
		self.assertEqual(self.config.switches, [False, False])

	def test_trigger_post_reload_trace_is_optional_and_queued_after_overlay_entry(self):
		source = (ROOT / "_speech_core" / "voice_profile_trigger.py").read_text(encoding="utf-8")
		trigger_source = source.split("class VoiceProfileOverlayTrigger:", 1)[1]
		enter_block = trigger_source.split("\n	def enter(self):", 1)[1].split("\n	def exit(self):", 1)[0]
		self.assertIn("wx.CallAfter(self._trace_live_variant_after_reload)", enter_block)
		self.assertIn("except Exception:", enter_block)
		self.assertLess(enter_block.index("self._overlay.enter()"), enter_block.index("wx.CallAfter"))
		self.assertIn("liveVariant=", source)

	def test_direct_transaction_applies_all_profile_settings_and_restores_native_snapshot(self):
		from _speech_core.voice_profile_trigger import VoiceProfileDirectSettingsTransaction

		transaction = VoiceProfileDirectSettingsTransaction(self.driver, self.profile)
		transaction.enter()
		self.assertEqual((self.driver.voice, self.driver.variant, self.driver.rateBoost, self.driver.rate),
			("voiceB", "expressive", True, 70))
		transaction.exit()
		self.assertEqual((self.driver.voice, self.driver.variant, self.driver.rateBoost, self.driver.rate),
			("voiceA", "standard", False, 40))

	def test_trigger_exposes_only_the_speech_manager_profile_contract(self):
		from _speech_core.voice_profile_overlay import VoiceProfileOverlay
		from _speech_core.voice_profile_trigger import VoiceProfileOverlayTrigger

		overlay = VoiceProfileOverlay(self.config, self.driver.name, self.profile, profile_factory=dict)
		trigger = VoiceProfileOverlayTrigger("focusNavigation", overlay)
		self.assertTrue(trigger.hasProfile)
		self.assertFalse(trigger._shouldNotifyProfileSwitch)
		trigger.enter()
		self._load_current_config()
		self.assertEqual(self.driver.variant, "expressive")
		trigger.exit()
		self._load_current_config()
		self.assertEqual(self.driver.variant, "standard")

	def test_runtime_factory_synchronizes_overlay_with_post_selector_driver_state(self):
		from _speech_core.voice_profile_runtime import make_voice_profile_overlay_trigger

		trigger = make_voice_profile_overlay_trigger("reviewObjectNavigation", self.config, self.driver, self.profile, profile_factory=dict)
		trigger.enter()
		self.assertEqual((self.driver.variant, self.driver.rateBoost), ("expressive", True))
		self.assertEqual(self.config.effective_snapshot(self.driver.name), self.profile)
		self._load_current_config()
		self.assertEqual((self.driver.variant, self.driver.rateBoost), ("expressive", True))
		trigger.exit()
		self._load_current_config()
		self.assertEqual((self.driver.variant, self.driver.rateBoost), ("standard", False))

	def test_overlay_exit_is_lifo_and_failure_cannot_remove_another_active_overlay(self):
		from _speech_core.voice_profile_overlay import VoiceProfileOverlay

		first = VoiceProfileOverlay(self.config, self.driver.name, self.profile, profile_factory=dict)
		second = VoiceProfileOverlay(self.config, self.driver.name, {**self.profile, "rate": 80}, profile_factory=dict)
		first.enter()
		second.enter()
		with self.assertRaises(RuntimeError):
			first.exit()
		self.assertTrue(first.active)
		second.exit()
		first.exit()
		self.assertEqual(self.config.profiles, [self.base])

	def test_overlay_never_changes_the_configured_synth_driver(self):
		from _speech_core.voice_profile_overlay import VoiceProfileOverlay

		overlay = VoiceProfileOverlay(self.config, self.driver.name, self.profile, profile_factory=dict)
		overlay.enter()
		self.assertEqual(self.config.effective_snapshot(self.driver.name), self.profile)
		self.assertEqual(self.base["speech"]["synth"], "fakeSynth")
		overlay.exit()


if __name__ == "__main__":
	unittest.main()