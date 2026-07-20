"""Focused outside-NVDA regression harness for v4 System prosody routing.

The routing is deliberately limited to existing ClassicSpeech POSITION and
HOTKEY semantic tokens. It builds speech commands only; it never assigns a
value to the active synthesizer.
"""
from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import classic_speech_core_harness as core_harness  # noqa: E402

core_harness._install_nvda_stubs()
import config  # noqa: E402
import speech.commands as commands  # noqa: E402
from speech.commands import BreakCommand  # noqa: E402


class _ProsodyCommand:
    settingName = ""

    def __init__(self, offset=0, multiplier=1):
        self.offset = offset
        self.multiplier = multiplier
        self.isDefault = offset == 0 and multiplier == 1


class RateCommand(_ProsodyCommand):
    settingName = "rate"


class PitchCommand(_ProsodyCommand):
    settingName = "pitch"


class VolumeCommand(_ProsodyCommand):
    settingName = "volume"


class ConfigProfileTriggerCommand:
    def __init__(self, trigger, enter):
        self.trigger = trigger
        self.enter = enter


commands.RateCommand = RateCommand
commands.PitchCommand = PitchCommand
commands.VolumeCommand = VolumeCommand
commands.ConfigProfileTriggerCommand = ConfigProfileTriggerCommand
EndUtteranceCommand = commands.EndUtteranceCommand


class Setting:
    def __init__(self, setting_id):
        self.id = setting_id


class FakeSynth:
    name = "fakeSynth"
    supportedSettings = (Setting("rate"), Setting("pitch"), Setting("volume"), Setting("voice"), Setting("variant"))

    def __init__(self):
        self.rate = 50
        self.pitch = 40
        self.volume = 60
        self.variant = "standard"
        self.assignments = []

    def __setattr__(self, name, value):
        if name in {"rate", "pitch", "volume"} and hasattr(self, name):
            self.assignments.append((name, value))
        super().__setattr__(name, value)


SYNTH = FakeSynth()
synth_driver_handler = types.ModuleType("synthDriverHandler")
synth_driver_handler.getSynth = lambda: SYNTH
sys.modules["synthDriverHandler"] = synth_driver_handler


def _clear_prosody_imports():
    for name in ("_speech_core.prosody_routing", "_speech_core.formatter"):
        sys.modules.pop(name, None)


def _set_voice_profile_data(data, configured=None):
    config.conf.clear()
    configured = configured or {
        "rate": SYNTH.rate,
        "pitch": SYNTH.pitch,
        "volume": SYNTH.volume,
    }
    config.conf["speech"] = {"fakeSynth": dict(configured)}
    config.conf.profiles = [{"classicSpeech": {"voiceProfileData": data}}]


DEFAULT_PROFILE = {
    "enabledTokens": {
        "name": True,
        "role": True,
        "value": True,
        "state": True,
        "position": True,
        "description": True,
        "tooltip": False,
        "hotkey": True,
    },
    "pauseMode": "global",
    "globalPause": 80,
    "order": ["name", "role", "value", "state", "position", "description", "tooltip", "hotkey"],
    "renames": {},
    "mutedLabels": [],
    "pauses": {},
    "pauseAfterFinalToken": False,
    "pausePlacement": "before",
}


class SystemProsodyRoutingTests(unittest.TestCase):
    def setUp(self):
        SYNTH.rate, SYNTH.pitch, SYNTH.volume = 50, 40, 60
        SYNTH.assignments.clear()
        _clear_prosody_imports()

    def _formatter_and_tokens(self):
        formatter = importlib.import_module("_speech_core.formatter").SpeechFormatter
        tokens = importlib.import_module("_speech_core.tokens")
        return formatter, tokens

    def test_explicit_system_scope_wraps_complete_position_and_hotkey_report_in_one_trigger_pair(self):
        _set_voice_profile_data({
            "fakeSynth": {
                "systemNotifications": {"variant": "systemVariant"},
            },
        }, configured={"rate": 50, "pitch": 40, "volume": 60, "variant": "standard"})
        SpeechFormatter, tokens = self._formatter_and_tokens()
        from _speech_core.prosody_routing import system_notification_profile_routing
        with system_notification_profile_routing():
            out = SpeechFormatter().format([
                tokens.token(tokens.TOKEN_NAME, spoken="Save"),
                tokens.token(tokens.TOKEN_POSITION, spoken="3 of 9"),
                tokens.token(tokens.TOKEN_HOTKEY, spoken="Control+S"),
            ], profile_config=DEFAULT_PROFILE)

        self.assertEqual(type(out[0]), ConfigProfileTriggerCommand)
        self.assertTrue(out[0].enter)
        self.assertEqual(out[0].trigger.spec, "classicSpeech:voiceProfile:systemNotifications")
        self.assertEqual(type(out[-1]), ConfigProfileTriggerCommand)
        self.assertFalse(out[-1].enter)
        self.assertIs(out[0].trigger, out[-1].trigger)
        self.assertEqual([item for item in out[1:-1] if isinstance(item, str)], ["Save", "3 of 9", "Control+S"])
        self.assertFalse(any(isinstance(item, _ProsodyCommand) for item in out))
        self.assertEqual(SYNTH.assignments, [])

    def test_focus_snapshot_wraps_complete_focus_announcement_in_one_trigger_pair(self):
        _set_voice_profile_data({
            "fakeSynth": {
                "focusNavigation": {"rate": 70, "pitch": 35, "volume": 80},
                "systemNotifications": {"variant": "systemVariant"},
            },
        })
        SpeechFormatter, tokens = self._formatter_and_tokens()
        out = SpeechFormatter().format([
            tokens.token(tokens.TOKEN_NAME, spoken="Save"),
            tokens.token(tokens.TOKEN_ROLE, spoken="button"),
            tokens.token(tokens.TOKEN_VALUE, spoken="enabled"),
            tokens.token(tokens.TOKEN_STATE, spoken="pressed"),
            tokens.token(tokens.TOKEN_POSITION, spoken="3 of 9"),
            tokens.token(tokens.TOKEN_HOTKEY, spoken="Control+S"),
        ], profile_config=DEFAULT_PROFILE)

        # Focus content and System metadata receive separate full-profile transactions.
        triggers = [item for item in out if isinstance(item, ConfigProfileTriggerCommand)]
        self.assertEqual([trigger.trigger.spec for trigger in triggers], [
            "classicSpeech:voiceProfile:focusNavigation", "classicSpeech:voiceProfile:focusNavigation",
            "classicSpeech:voiceProfile:systemNotifications", "classicSpeech:voiceProfile:systemNotifications",
        ])
        self.assertEqual([item for item in out if isinstance(item, str)], [
            "Save", "button", "enabled", "pressed", "3 of 9", "Control+S",
        ])
        self.assertFalse(any(isinstance(item, _ProsodyCommand) for item in out))
        self.assertEqual(SYNTH.assignments, [])

    def test_nested_baseline_and_overrides_are_resolved_for_focus_and_system_routes(self):
        _set_voice_profile_data({
            "fakeSynth": {
                "focusNavigation": {
                    "baseline": {"rate": 50, "pitch": 40, "volume": 60},
                    "overrides": {"rate": 70},
                },
                "systemNotifications": {
                    "baseline": {"rate": 50, "pitch": 40, "volume": 60},
                    "overrides": {"volume": 80},
                },
            },
        })
        SpeechFormatter, tokens = self._formatter_and_tokens()
        from _speech_core.prosody_routing import system_notification_profile_routing
        focus = SpeechFormatter().format([
            tokens.token(tokens.TOKEN_NAME, spoken="Save"),
        ], profile_config=DEFAULT_PROFILE)
        with system_notification_profile_routing():
            system = SpeechFormatter().format([
                tokens.token(tokens.TOKEN_POSITION, spoken="3 of 9"),
            ], profile_config=DEFAULT_PROFILE)

        # Complete formatter-owned sequences use one Preview-style transaction
        # for every changed supported setting, including numeric-only profiles.
        for sequence, expected_profile in ((focus, "focusNavigation"), (system, "systemNotifications")):
            self.assertIsInstance(sequence[0], ConfigProfileTriggerCommand)
            self.assertTrue(sequence[0].enter)
            self.assertEqual(sequence[0].trigger.spec, f"classicSpeech:voiceProfile:{expected_profile}")
            self.assertIsInstance(sequence[-1], ConfigProfileTriggerCommand)
            self.assertFalse(sequence[-1].enter)
            self.assertIs(sequence[0].trigger, sequence[-1].trigger)
        self.assertEqual(SYNTH.assignments, [])

    def test_new_profile_records_route_voice_plus_explicit_overrides_not_stale_baseline_values(self):
        _set_voice_profile_data({
            "fakeSynth": {
                "reviewObjectNavigation": {
                    "baseline": {
                        "voice": "voiceA", "variant": "standard", "rate": 50,
                        "pitch": 40, "volume": 60, "breath": 0,
                    },
                    "overrides": {"variant": "reviewVariant"},
                },
            },
        }, configured={"voice": "voiceA", "variant": "standard", "rate": 50, "pitch": 40, "volume": 60})
        from _speech_core.prosody_routing import _active_profile_snapshot

        driver, snapshot = _active_profile_snapshot("reviewObjectNavigation")

        self.assertIs(driver, SYNTH)
        self.assertEqual(snapshot, {"voice": "voiceA", "variant": "reviewVariant", "rate": 50})

    def test_review_profile_wraps_the_full_object_navigation_announcement(self):
        _set_voice_profile_data({
            "fakeSynth": {
                "reviewObjectNavigation": {"rate": 70, "pitch": 35, "volume": 80},
            },
        })
        SpeechFormatter, tokens = self._formatter_and_tokens()
        out = SpeechFormatter().format([
            tokens.token(tokens.TOKEN_NAME, spoken="Save"),
            tokens.token(tokens.TOKEN_ROLE, spoken="button"),
            tokens.token(tokens.TOKEN_VALUE, spoken="enabled"),
            tokens.token(tokens.TOKEN_STATE, spoken="pressed"),
            tokens.token(tokens.TOKEN_POSITION, spoken="3 of 9"),
            tokens.token(tokens.TOKEN_DESCRIPTION, spoken="Saves the document"),
            tokens.token(tokens.TOKEN_HOTKEY, spoken="Control+S"),
        ], profile_config=DEFAULT_PROFILE, speech_origin="objectNavigation")

        self.assertIsInstance(out[0], ConfigProfileTriggerCommand)
        self.assertTrue(out[0].enter)
        self.assertEqual(out[0].trigger.spec, "classicSpeech:voiceProfile:reviewObjectNavigation")
        self.assertIsInstance(out[-1], ConfigProfileTriggerCommand)
        self.assertFalse(out[-1].enter)
        self.assertIs(out[0].trigger, out[-1].trigger)
        self.assertEqual([item for item in out[1:-1] if isinstance(item, str)], ["Save", "button", "enabled", "pressed", "3 of 9", "Saves the document", "Control+S"])
        self.assertFalse(any(isinstance(item, _ProsodyCommand) for item in out))
        self.assertEqual(SYNTH.assignments, [])

    def test_review_command_only_fragment_does_not_create_a_profile_transaction(self):
        _set_voice_profile_data({
            "fakeSynth": {"reviewObjectNavigation": {"variant": "reviewVariant"}},
        }, configured={"rate": 50, "pitch": 40, "volume": 60, "variant": "standard"})
        from _speech_core.prosody_routing import wrap_review_literal_sequence

        command_only = object()
        out = wrap_review_literal_sequence([command_only])

        self.assertEqual(out, [command_only])
        self.assertEqual(SYNTH.assignments, [])

    def test_review_literal_wrapper_preserves_original_command_order(self):
        _set_voice_profile_data({
            "fakeSynth": {"reviewObjectNavigation": {"rate": 70, "pitch": 35, "volume": 80}},
        })
        from _speech_core.prosody_routing import wrap_review_literal_sequence

        leading_command = object()
        trailing_command = object()
        out = wrap_review_literal_sequence([leading_command, "literal review text", trailing_command])

        self.assertIsInstance(out[0], ConfigProfileTriggerCommand)
        self.assertTrue(out[0].enter)
        self.assertIs(out[1], leading_command)
        self.assertEqual(out[2], "literal review text")
        self.assertIs(out[3], trailing_command)
        self.assertIsInstance(out[4], ConfigProfileTriggerCommand)
        self.assertFalse(out[4].enter)
        self.assertIs(out[0].trigger, out[4].trigger)
        self.assertEqual(SYNTH.assignments, [])

    def test_review_literal_wrapper_restarts_prosody_after_each_end_utterance(self):
        _set_voice_profile_data({
            "fakeSynth": {"reviewObjectNavigation": {"rate": 70, "pitch": 35, "volume": 80}},
        })
        from _speech_core.prosody_routing import wrap_review_literal_sequence

        first_end = EndUtteranceCommand()
        second_end = EndUtteranceCommand()
        out = wrap_review_literal_sequence(["R", first_end, "e", second_end])

        self.assertEqual([type(item) for item in out], [
            ConfigProfileTriggerCommand, str, EndUtteranceCommand, str, EndUtteranceCommand, ConfigProfileTriggerCommand,
        ])
        self.assertTrue(out[0].enter)
        self.assertEqual(out[1], "R")
        self.assertIs(out[2], first_end)
        self.assertEqual(out[3], "e")
        self.assertIs(out[4], second_end)
        self.assertFalse(out[5].enter)
        self.assertIs(out[0].trigger, out[5].trigger)
        self.assertEqual(SYNTH.assignments, [])

    def test_review_literal_wrapper_combines_capital_pitch_with_review_pitch(self):
        _set_voice_profile_data({
            "fakeSynth": {"reviewObjectNavigation": {"rate": 70, "pitch": 35, "volume": 80}},
        })
        from _speech_core.prosody_routing import wrap_review_literal_sequence

        native_capital_pitch = PitchCommand(offset=30)
        native_capital_reset = PitchCommand()
        end = EndUtteranceCommand()
        out = wrap_review_literal_sequence([native_capital_pitch, "R", native_capital_reset, end])

        self.assertEqual([type(item) for item in out], [
            ConfigProfileTriggerCommand, PitchCommand, str, PitchCommand, EndUtteranceCommand, ConfigProfileTriggerCommand,
        ])
        # Native capitalization commands stay untouched inside the one Review
        # transaction; the direct transaction applies the profile pitch itself.
        self.assertTrue(out[0].enter)
        self.assertEqual(out[1].offset, 30)
        self.assertEqual(out[2], "R")
        self.assertTrue(out[3].isDefault)
        self.assertIs(out[4], end)
        self.assertFalse(out[5].enter)
        self.assertIs(out[0].trigger, out[5].trigger)
        self.assertEqual(SYNTH.assignments, [])

    def test_offsets_use_saved_nvda_values_not_temporary_live_driver_values(self):
        # Preview temporarily sets driver properties, but NVDA prosody commands
        # are defined relative to the saved synth configuration.
        SYNTH.rate, SYNTH.pitch, SYNTH.volume = 30, 70, 20
        SYNTH.assignments.clear()
        _set_voice_profile_data(
            {"fakeSynth": {"focusNavigation": {"rate": 70, "pitch": 35, "volume": 80}}},
            configured={"rate": 50, "pitch": 40, "volume": 60},
        )
        SpeechFormatter, tokens = self._formatter_and_tokens()
        out = SpeechFormatter().format(
            [tokens.token(tokens.TOKEN_NAME, spoken="Save")],
            profile_config=DEFAULT_PROFILE,
        )

        self.assertIsInstance(out[0], ConfigProfileTriggerCommand)
        self.assertTrue(out[0].enter)
        self.assertEqual(out[0].trigger.spec, "classicSpeech:voiceProfile:focusNavigation")
        self.assertEqual(out[1], "Save")
        self.assertIsInstance(out[2], ConfigProfileTriggerCommand)
        self.assertFalse(out[2].enter)
        self.assertIs(out[0].trigger, out[2].trigger)
        self.assertEqual(SYNTH.assignments, [])

    def test_explicit_preview_suppresses_stale_persisted_profile_commands_once(self):
        _set_voice_profile_data({"fakeSynth": {"focusNavigation": {"rate": 70}}})
        SpeechFormatter, tokens = self._formatter_and_tokens()
        from _speech_core.prosody_routing import suppress_profile_prosody_routing

        source = [tokens.token(tokens.TOKEN_NAME, spoken="Preview sample")]
        with suppress_profile_prosody_routing():
            preview = SpeechFormatter().format(source, profile_config=DEFAULT_PROFILE)
        normal = SpeechFormatter().format(source, profile_config=DEFAULT_PROFILE)

        self.assertEqual(preview, ["Preview sample"])
        self.assertIsInstance(normal[0], ConfigProfileTriggerCommand)
        self.assertTrue(normal[0].enter)
        self.assertEqual(normal[0].trigger.spec, "classicSpeech:voiceProfile:focusNavigation")
        self.assertIsInstance(normal[-1], ConfigProfileTriggerCommand)
        self.assertFalse(normal[-1].enter)

    def test_pause_is_outside_profile_commands_and_reset_precedes_next_token(self):
        _set_voice_profile_data({"fakeSynth": {"systemNotifications": {"rate": 70}}})
        SpeechFormatter, tokens = self._formatter_and_tokens()
        profile = dict(DEFAULT_PROFILE, globalPause=25, pausePlacement="before")
        from _speech_core.prosody_routing import system_notification_profile_routing
        with system_notification_profile_routing():
            out = SpeechFormatter().format([
                tokens.token(tokens.TOKEN_NAME, spoken="Item"),
                tokens.token(tokens.TOKEN_POSITION, spoken="1 of 2"),
                tokens.token(tokens.TOKEN_HOTKEY, spoken="Alt+I"),
            ], profile_config=profile)
        # One System transaction owns the complete report; pauses stay inside it.
        self.assertEqual([type(item).__name__ if not isinstance(item, str) else item for item in out], [
            "ConfigProfileTriggerCommand", "Item", "BreakCommand", "1 of 2", "BreakCommand", "Alt+I", "ConfigProfileTriggerCommand",
        ])
        self.assertTrue(out[0].enter)
        self.assertFalse(out[-1].enter)
        self.assertIs(out[0].trigger, out[-1].trigger)
        self.assertEqual(out[2].time, 25)

    def test_native_only_focus_to_system_boundary_retains_before_pause(self):
        _set_voice_profile_data({})
        SpeechFormatter, tokens = self._formatter_and_tokens()
        profile = dict(DEFAULT_PROFILE, globalPause=25, pausePlacement="before")
        out = SpeechFormatter().format([
            tokens.token(tokens.TOKEN_NAME, spoken="Item"),
            tokens.token(tokens.TOKEN_POSITION, spoken="1 of 2"),
            tokens.token(tokens.TOKEN_HOTKEY, spoken="Alt+I"),
        ], profile_config=profile)
        self.assertEqual([type(item).__name__ if not isinstance(item, str) else item for item in out], [
            "Item", "BreakCommand", "1 of 2", "BreakCommand", "Alt+I",
        ])
        self.assertEqual([item.time for item in out if isinstance(item, BreakCommand)], [25, 25])

    def test_non_prosody_review_profile_brackets_untouched_sequence_with_native_trigger_commands(self):
        _set_voice_profile_data(
            {"fakeSynth": {"reviewObjectNavigation": {"variant": "expressive"}}},
            configured={"rate": 50, "pitch": 40, "volume": 60, "variant": "standard"},
        )
        _clear_prosody_imports()
        from _speech_core.prosody_routing import wrap_review_literal_sequence

        source = ["Review text", EndUtteranceCommand()]
        out = wrap_review_literal_sequence(source)
        self.assertEqual([type(item) for item in out], [ConfigProfileTriggerCommand, str, EndUtteranceCommand, ConfigProfileTriggerCommand])
        self.assertTrue(out[0].enter)
        self.assertFalse(out[-1].enter)
        self.assertIs(out[0].trigger, out[-1].trigger)
        self.assertEqual(out[1:3], source)
        self.assertEqual(SYNTH.assignments, [])

    def test_every_category_variant_delta_uses_one_native_trigger_pair(self):
        from _speech_core.prosody_routing import wrap_profile_sequence

        source = ["Owned category speech", EndUtteranceCommand()]
        for profile_id in (
            "focusNavigation",
            "reviewObjectNavigation",
            "keyboardEntry",
            "systemNotifications",
        ):
            with self.subTest(profile_id=profile_id):
                _set_voice_profile_data(
                    {"fakeSynth": {profile_id: {"variant": "expressive"}}},
                    configured={"rate": 50, "pitch": 40, "volume": 60, "variant": "standard"},
                )
                _clear_prosody_imports()
                from _speech_core.prosody_routing import wrap_profile_sequence
                out = wrap_profile_sequence(source, profile_id)
                self.assertEqual(
                    [type(item) for item in out],
                    [ConfigProfileTriggerCommand, str, EndUtteranceCommand, ConfigProfileTriggerCommand],
                )
                self.assertTrue(out[0].enter)
                self.assertFalse(out[-1].enter)
                self.assertIs(out[0].trigger, out[-1].trigger)
                self.assertEqual(out[1:3], source)
                self.assertEqual(SYNTH.assignments, [])

    def test_formatter_routes_variant_trigger_to_focus_object_and_system_owners(self):
        _set_voice_profile_data(
            {"fakeSynth": {
                "focusNavigation": {"variant": "focusVariant"},
                "reviewObjectNavigation": {"variant": "reviewVariant"},
                "systemNotifications": {"variant": "systemVariant"},
            }},
            configured={"rate": 50, "pitch": 40, "volume": 60, "variant": "standard"},
        )
        _clear_prosody_imports()
        SpeechFormatter, tokens = self._formatter_and_tokens()
        from _speech_core.prosody_routing import system_notification_profile_routing

        source = [tokens.token(tokens.TOKEN_POSITION, spoken="2 of 9")]
        focus = SpeechFormatter().format(source, profile_config=DEFAULT_PROFILE)
        review = SpeechFormatter().format(source, profile_config=DEFAULT_PROFILE, speech_origin="objectNavigation")
        with system_notification_profile_routing():
            system = SpeechFormatter().format(source, profile_config=DEFAULT_PROFILE)

        for sequence, expected_profile in (
            (focus, "systemNotifications"),
            (review, "reviewObjectNavigation"),
            (system, "systemNotifications"),
        ):
            with self.subTest(profile_id=expected_profile):
                self.assertIsInstance(sequence[0], ConfigProfileTriggerCommand)
                self.assertTrue(sequence[0].enter)
                self.assertIsInstance(sequence[-1], ConfigProfileTriggerCommand)
                self.assertFalse(sequence[-1].enter)
                self.assertEqual(sequence[0].trigger.spec, f"classicSpeech:voiceProfile:{expected_profile}")
                self.assertIs(sequence[0].trigger, sequence[-1].trigger)
                self.assertTrue(any(isinstance(item, str) and item == "2 of 9" for item in sequence))
        self.assertEqual(SYNTH.assignments, [])

    def test_missing_snapshot_unsupported_nonnumeric_or_equal_values_preserve_exact_formatter_output(self):
        SpeechFormatter, tokens = self._formatter_and_tokens()
        source_tokens = [
            tokens.token(tokens.TOKEN_POSITION, spoken="1 of 2"),
            tokens.token(tokens.TOKEN_HOTKEY, spoken="Alt+I"),
        ]
        _set_voice_profile_data({})
        baseline = SpeechFormatter().format(source_tokens, profile_config=DEFAULT_PROFILE)

        _set_voice_profile_data(
            {"fakeSynth": {"systemNotifications": {"rate": 50, "pitch": "fast", "voice": "other"}}},
            configured={"rate": 50, "pitch": 40, "volume": 60, "voice": "other"},
        )
        _clear_prosody_imports()
        SpeechFormatter, _tokens = self._formatter_and_tokens()
        from _speech_core.prosody_routing import system_notification_profile_routing
        with system_notification_profile_routing():
            routed = SpeechFormatter().format(source_tokens, profile_config=DEFAULT_PROFILE)
        def sequence_shape(sequence):
            return [
                item if isinstance(item, str) else (type(item).__name__, getattr(item, "time", None))
                for item in sequence
            ]
        self.assertEqual(sequence_shape(routed), sequence_shape(baseline))
        self.assertEqual(SYNTH.assignments, [])


if __name__ == "__main__":
    unittest.main()
