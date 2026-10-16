"""Automatic voice generation suspends with NVDA's GUI, not speech processing.

Uses isolated NVDA/config/scheme fakes; never opens a GUI or writes live settings.
"""
from __future__ import annotations

import ast
from contextlib import nullcontext
import importlib
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import classic_speech_schemes_harness as schemes
import classic_speech_settings_safety_harness as safety


class AutomaticVoiceSuspensionTests(schemes.SchemeHarnessBase):
    def setUp(self):
        super().setUp()
        self.routing = importlib.import_module("globalPlugins._speech_core.prosody_routing")
        self.trigger_module = importlib.import_module("globalPlugins._speech_core.voice_profile_trigger")
        self.suspended = False
        gui = types.ModuleType("gui")
        gui.shouldConfigProfileTriggersBeSuspended = lambda: self.suspended
        self.gui_patch = patch.dict(sys.modules, {"gui": gui})
        self.gui_patch.start()
        self.addCleanup(self.gui_patch.stop)
        self.ids = ("focusNavigation", "reviewObjectNavigation", "keyboardEntry", "mouse", "systemNotifications")

    def profiles(self, snapshot):
        self.section["voiceProfileData"] = {"fakeSynth": {key: dict(snapshot) for key in self.ids}}

    def assert_no_added_voice(self, output):
        self.assertFalse([item for item in output if isinstance(item, (
            schemes.ConfigProfileTriggerCommand, schemes.RateCommand, schemes.PitchCommand, schemes.VolumeCommand))])

    def test_all_category_generation_bypasses_full_profiles_and_prosody_then_resumes(self):
        native = schemes.commands.BreakCommand(time=25)
        sequence = [native, "native words"]
        for snapshot in ({"variant": "deep"}, {"pitch": 70}):
            self.profiles(snapshot)
            for profile_id in self.ids:
                with self.subTest(snapshot=snapshot, category=profile_id):
                    self.suspended = False
                    self.assertNotEqual(self.routing.wrap_profile_sequence(sequence, profile_id), sequence)
                    self.suspended = True
                    self.assertEqual(self.routing.wrap_profile_sequence(sequence, profile_id), sequence)
                    self.assertEqual(self.routing._profile_prosody_commands(profile_id), ((), ()))
                    self.suspended = False
                    self.assertNotEqual(self.routing.wrap_profile_sequence(sequence, profile_id), sequence)

    def test_native_commands_are_preserved_not_stripped(self):
        self.profiles({"pitch": 70})
        self.suspended = True
        sequence = [schemes.PitchCommand(offset=10), "Capital", schemes.PitchCommand(), schemes.commands.EndUtteranceCommand()]
        for profile_id in self.ids:
            out = self.routing.wrap_profile_sequence(sequence, profile_id)
            self.assertEqual(out, sequence)
            self.assertTrue(all(a is b for a, b in zip(out, sequence)))

    def test_inline_category_fallback_is_also_gated_and_resumes(self):
        self.profiles({"pitch": 70})
        with patch.object(self.routing, "active_full_profile_trigger", return_value=None):
            for profile_id in self.ids:
                with self.subTest(category=profile_id):
                    self.suspended = False
                    self.assertTrue(self.routing._profile_prosody_commands(profile_id)[0])
                    self.assertNotEqual(self.routing.wrap_profile_sequence(["words"], profile_id), ["words"])
                    self.suspended = True
                    self.assertEqual(self.routing._profile_prosody_commands(profile_id), ((), ()))
                    self.assertEqual(self.routing.wrap_profile_sequence(["words"], profile_id), ["words"])
                    self.suspended = False
                    self.assertNotEqual(self.routing.wrap_profile_sequence(["words"], profile_id), ["words"])

    def test_filter_keeps_raw_history_and_scheme_sound_while_voices_suspend(self):
        self.profiles({"variant": "deep"})
        self.configure({"role.LINK": {"sound": self.sound(), "voice": {
            "enabled": True, "bySynth": {"fakeSynth": schemes._voice_record(pitch=70)}}}})
        plugin = self.module.GlobalPlugin()
        schemes.globalPluginHandler.runningPlugins.append(plugin)
        self.addCleanup(plugin.terminate)
        self.suspended = True
        plugin.processor._bypass_next_sequence = True
        output = plugin._filterSpeechSequence([self.markers.LabelMarker(["role.LINK"]), "link", "Home"])
        self.assert_no_added_voice(output)
        self.assertEqual([x for x in output if isinstance(x, str)], ["link", "Home"])
        self.assertTrue(any(isinstance(x, self.runtime.SchemeSoundCommand) for x in output))
        self.assertEqual(plugin.history.items(), ["link Home"])

    def test_formatter_focus_review_system_position_hotkey_keep_formatting(self):
        from globalPlugins._speech_core.formatter import SpeechFormatter
        from globalPlugins._speech_core.tokens import token

        self.profiles({"pitch": 70, "variant": "deep"})
        tokens = [token("name", spoken="Save"), token("role", raw="button", spoken="button"),
                  token("position", spoken="3 of 9"), token("hotkey", spoken="Control+S")]
        profile = {"renames": {"role": {"button": "control"}}, "globalPause": 25}
        for origin in ("focus", "objectNavigation"):
            for system in (False, True):
                with self.subTest(origin=origin, system=system):
                    with self.routing.system_notification_profile_routing() if system else nullcontext():
                        self.suspended = False
                        routed = SpeechFormatter().format(tokens, profile, speech_origin=origin)
                        self.suspended = True
                        bypassed = SpeechFormatter().format(tokens, profile, speech_origin=origin)
                    self.assert_no_added_voice(bypassed)
                    self.assertEqual([x for x in bypassed if isinstance(x, str)], [x for x in routed if isinstance(x, str)])
                    self.assertIn("3 of 9", bypassed)
                    self.assertIn("Control+S", bypassed)
                    self.assertTrue(any(isinstance(x, schemes.commands.BreakCommand) for x in bypassed))

    def test_scheme_label_format_element_same_cross_synth_and_inline_resume(self):
        voices = [
            {"enabled": True, "bySynth": {"fakeSynth": schemes._voice_record(pitch=70)}},
            {"enabled": True, "bySynth": {"fakeSynth": schemes._voice_record(variant="deep")}},
            {"enabled": True, "engine": "espeak", "bySynth": {"espeak": {"voice": "en"}}},
        ]
        for voice in voices:
            for kind in ("label", "format", "element"):
                with self.subTest(voice=voice, kind=kind):
                    item = "fmt.bold" if kind == "format" else "role.LINK"
                    self.configure({item: {"voice": voice}})
                    marker = {"label": self.markers.LabelMarker([item]),
                              "format": self.markers.FormatMarker([item]),
                              "element": self.markers.ElementStartMarker(1, [item])}[kind]
                    sequence = [marker, "words"]
                    self.suspended = False
                    self.assertNotEqual(self.runtime.apply_schemes(sequence), ["words"])
                    self.suspended = True
                    self.assertEqual(self.runtime.apply_schemes(sequence), ["words"])
                    self.suspended = False
                    self.assertNotEqual(self.runtime.apply_schemes(sequence), ["words"])

    def test_suspension_keeps_scheme_sounds_sound_only_and_marker_cleanup(self):
        self.suspended = True
        for sound_only in (False, True):
            self.configure({"role.LINK": {"sound": self.sound(), "soundOnly": sound_only,
                "voice": {"enabled": True, "bySynth": {"fakeSynth": schemes._voice_record(pitch=70)}}}})
            native = schemes.commands.BreakCommand(time=25)
            out = self.runtime.apply_schemes([native, self.markers.LabelMarker(["role.LINK"]), "link"])
            self.assert_no_added_voice(out)
            self.assertIs(out[0], native)
            self.assertEqual(len([x for x in out if isinstance(x, self.runtime.SchemeSoundCommand)]), 1)
            self.assertEqual([x for x in out if isinstance(x, str)], [] if sound_only else ["link"])
            self.assertFalse(any(isinstance(x, self.markers.SchemeMarker) for x in out))

    def test_predicate_follows_real_nvda_menu_and_shown_window_semantics(self):
        # Execute only the actual upstream predicate, with no GUI side effects.
        root = Path(os.environ.get("CLASSICSPEECH_NVDA_MASTER", schemes.ROOT.parent / "nvda master"))
        tree = ast.parse((root / "source/gui/__init__.py").read_text(encoding="utf-8"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "shouldConfigProfileTriggersBeSuspended")
        flags = [0]
        windows = []
        env = {"winUser": types.SimpleNamespace(getGUIThreadInfo=lambda _: types.SimpleNamespace(flags=flags[0])),
               "winBindings": types.SimpleNamespace(kernel32=types.SimpleNamespace(GetCurrentThreadId=lambda: 1)),
               "wx": types.SimpleNamespace(GetTopLevelWindows=lambda: windows)}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "nvda-gui-predicate", "exec"), env)
        sys.modules["gui"].shouldConfigProfileTriggersBeSuspended = env[node.name]
        self.assertFalse(self.trigger_module.settings_gui_open())
        flags[0] = 0x10
        self.assertTrue(self.trigger_module.settings_gui_open())
        flags[0] = 0
        shown = [True]
        windows.append(types.SimpleNamespace(IsShown=lambda: shown[0], shouldSuspendConfigProfileTriggers=True))
        # No foreground check: a shown dialog stays suspended after Alt+Tab.
        self.assertTrue(self.trigger_module.settings_gui_open())
        shown[0] = False
        self.assertFalse(self.trigger_module.settings_gui_open())


class QueueBoundaryTests(safety.SettingsDialogPauseTests):
    # Inherit preview, cross-synth, missing-GUI, pause/resume and dialog contracts.
    def test_queued_before_open_checks_gui_at_enter_and_preserves_native_profile(self):
        native = safety.FakeProfile({"speech": {"espeak": {"rate": 55}}}, name="native")
        self.conf.profiles.append(native)
        self._settings_gui_open(False)
        trigger = self._trigger()
        self._settings_gui_open(True)
        trigger.enter()
        self.assertEqual(self.conf.profiles, [self.base, native])
        self.driver.rate = 61
        trigger.exit()
        self.assertEqual(self.driver.rate, 61, "paused entry never captures/restores a stale baseline")
        self.assertEqual(self.conf.profiles, [self.base, native])

    def test_opening_settings_does_not_prematurely_restore_an_active_utterance(self):
        self._settings_gui_open(False)
        trigger = self._trigger()
        trigger.enter()
        self._settings_gui_open(True)
        self.assertTrue(self.trigger_module.settings_gui_open())
        self.assertEqual(self.driver.voice, "en-gb")
        self.assertEqual(len(self.conf.profiles), 2)
        trigger.exit()
        self.assertEqual(self.driver.voice, "en")
        self.assertEqual(self.conf.profiles, [self.base])


if __name__ == "__main__":
    unittest.main()
