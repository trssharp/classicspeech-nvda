"""Regression harness for v2/v04 feedback cleanup items."""
from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import classic_speech_nvda_master_harness as nvda_harness  # noqa: E402
import api  # noqa: E402
import config  # noqa: E402
import globalCommands  # noqa: E402
import globalPluginHandler  # noqa: E402
import scriptHandler  # noqa: E402
import speech  # noqa: E402


class FeedbackPauseConfigTests(unittest.TestCase):
    def setUp(self):
        nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()

    def tearDown(self):
        nvda_harness._reset_global_plugin_imports()
        speech.extensions.filter_speechSequence.callbacks.clear()
        globalPluginHandler.runningPlugins.clear()

    def test_shape_pause_config_spec_defaults_use_global_pause_sentinel(self):
        module = nvda_harness._import_classic_speech_like_nvda()
        plugin = module.GlobalPlugin()
        try:
            pauses = config.conf.spec["classicSpeech"]["shapeData"]["pauses"]
            expected = {name: "integer(default=-1)" for name in pauses}
            self.assertEqual(dict(pauses), expected)
        finally:
            plugin.terminate()

    def test_key_label_runtime_restores_native_labels_when_terminated(self):
        import keyLabels
        from globalPlugins._speech_core.key_labels import KeyLabelRuntime

        keyLabels.localizedKeyLabels.clear()
        keyLabels.localizedKeyLabels["f1"] = "F1"
        runtime = KeyLabelRuntime()
        runtime.install()
        try:
            runtime.apply_config({"renames": {"f1": "help"}, "mutedLabels": []})
            self.assertEqual(keyLabels.localizedKeyLabels["f1"], "help")
        finally:
            runtime.terminate()
        self.assertEqual(keyLabels.localizedKeyLabels["f1"], "F1")


class FeedbackCancelRestoreTests(unittest.TestCase):
    def setUp(self):
        base = nvda_harness._HarnessBaseConfig()
        config.conf.clear()
        config.conf.BASE_ONLY_SECTIONS = set()
        config.conf.spec = {}
        config.conf.validator = object()
        config.conf.profiles = [base]
        config.conf["presentation"] = {
            "reportKeyboardShortcuts": True,
            "reportObjectPositionInformation": True,
            "guessObjectPositionInformationWhenUnavailable": False,
            "reportObjectDescriptions": True,
            "reportTooltips": False,
        }
        base["classicSpeech"] = {
            "defaultProfile": "Beginner",
            "announceDefaultButton": True,
            "speechHookEnabled": True,
            "profileData": {},
            "profileBehaviorData": {},
            "shapeData": {},
            "keyLabelData": {"renames": {}, "mutedLabels": []},
        }
        speech.extensions.filter_speechSequence.callbacks.clear()
        globalPluginHandler.runningPlugins.clear()

    def tearDown(self):
        nvda_harness._reset_global_plugin_imports()
        speech.extensions.filter_speechSequence.callbacks.clear()
        globalPluginHandler.runningPlugins.clear()

    def test_cancel_restore_reapplies_hook_default_button_and_position_guessing(self):
        module = nvda_harness._import_classic_speech_like_nvda()
        plugin = module.GlobalPlugin()
        globalPluginHandler.runningPlugins.append(plugin)
        try:
            from globalPlugins._speech_core.settings.advanced_config import _set_speech_hook_enabled
            from globalPlugins._speech_core.settings.dialog import ClassicSpeechDialog
            from globalPlugins._speech_core.settings.misc_config import _set_default_button_enabled
            from globalPlugins._speech_core.settings.config_core import _set_nvda_setting

            dialog = object.__new__(ClassicSpeechDialog)
            dialog._captureTransactionBaseline()

            _set_speech_hook_enabled(False)
            _set_default_button_enabled(False)
            _set_nvda_setting("presentation", "guessObjectPositionInformationWhenUnavailable", True)

            self.assertNotIn(plugin._filterSpeechSequence, speech.extensions.filter_speechSequence.callbacks)
            self.assertFalse(plugin.processor.verbosity.announce_default_button)
            self.assertTrue(config.conf["presentation"]["guessObjectPositionInformationWhenUnavailable"])

            dialog._restoreTransactionBaseline()

            self.assertIn(plugin._filterSpeechSequence, speech.extensions.filter_speechSequence.callbacks)
            self.assertTrue(plugin.processor.verbosity.announce_default_button)
            self.assertFalse(config.conf["presentation"]["guessObjectPositionInformationWhenUnavailable"])
        finally:
            plugin.terminate()


class FeedbackNavigatorBypassCleanupTests(unittest.TestCase):
    def setUp(self):
        nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
        self.original_report_focus = globalCommands.commands.script_reportCurrentFocus
        self.original_current_script = scriptHandler.getCurrentScript

    def tearDown(self):
        globalCommands.commands.script_reportCurrentFocus = self.original_report_focus
        for name in (
            "_classicSpeechNavBypassInstalled",
            "_classicSpeechNavBypassOriginals",
        ):
            if hasattr(globalCommands.commands, name):
                delattr(globalCommands.commands, name)
        scriptHandler.getCurrentScript = self.original_current_script
        nvda_harness._reset_global_plugin_imports()
        speech.extensions.filter_speechSequence.callbacks.clear()
        globalPluginHandler.runningPlugins.clear()

    def test_plugin_no_longer_installs_dead_navigator_command_wrapper(self):
        module = nvda_harness._import_classic_speech_like_nvda()
        plugin = module.GlobalPlugin()
        try:
            self.assertFalse(hasattr(plugin, "_install_navigator_object_bypass"))
            self.assertFalse(hasattr(plugin, "_restore_navigator_object_bypass"))
            self.assertIs(globalCommands.commands.script_reportCurrentFocus, self.original_report_focus)
            self.assertFalse(hasattr(globalCommands.commands, "_classicSpeechNavBypassInstalled"))
        finally:
            plugin.terminate()

    def test_object_navigation_uses_review_voice_when_semantic_processing_is_disabled(self):
        config.conf.profiles[0]["classicSpeech"] = {
            "speechHookEnabled": True,
            "debugLogging": False,
            "objectNavigationProcessing": False,
        }
        module = nvda_harness._import_classic_speech_like_nvda()
        module.wrap_review_literal_sequence = lambda sequence: ["review profile"] + list(sequence)
        plugin = module.GlobalPlugin()

        def script_navigatorObject_moveFocus():
            return None

        scriptHandler.getCurrentScript = lambda: script_navigatorObject_moveFocus
        try:
            self.assertEqual(
                plugin._filterSpeechSequence(["Move focus"]),
                ["review profile", "Move focus"],
            )
        finally:
            plugin.terminate()

    def test_enabled_object_navigation_marks_one_processor_call_as_object_navigation(self):
        config.conf.profiles[0]["classicSpeech"] = {
            "speechHookEnabled": True,
            "debugLogging": False,
            "objectNavigationProcessing": True,
        }
        module = nvda_harness._import_classic_speech_like_nvda()
        plugin = module.GlobalPlugin()

        def script_navigatorObject_next():
            return None

        scriptHandler.getCurrentScript = lambda: script_navigatorObject_next
        origins = []
        original_process = plugin.processor.process

        def capture_process(sequence, speech_origin="focus"):
            origins.append(speech_origin)
            return original_process(sequence, speech_origin=speech_origin)

        plugin.processor.process = capture_process
        try:
            plugin._filterSpeechSequence(["navigator text"])
            self.assertEqual(origins, ["objectNavigation"])
        finally:
            plugin.terminate()

    def test_enabled_object_navigation_keeps_literal_review_native(self):
        config.conf.profiles[0]["classicSpeech"] = {
            "speechHookEnabled": True,
            "debugLogging": False,
            "objectNavigationProcessing": True,
        }
        module = nvda_harness._import_classic_speech_like_nvda()
        plugin = module.GlobalPlugin()

        def script_navigatorObject_next():
            return None

        scriptHandler.getCurrentScript = lambda: script_navigatorObject_next
        plugin.processor.should_bypass_literal_review = lambda _sequence: True
        try:
            sequence = ["literal review text"]
            result = plugin._filterSpeechSequence(sequence)
            self.assertIs(result, sequence)
            self.assertEqual(sequence, ["literal review text"])
        finally:
            plugin.terminate()

    def test_review_cursor_literal_route_ignores_object_navigation_master_gate(self):
        config.conf.profiles[0]["classicSpeech"] = {
            "speechHookEnabled": True,
            "debugLogging": False,
            "objectNavigationProcessing": False,
        }
        module = nvda_harness._import_classic_speech_like_nvda()
        plugin = module.GlobalPlugin()

        def script_review_currentLine():
            return None

        scriptHandler.getCurrentScript = lambda: script_review_currentLine
        plugin.processor.should_bypass_literal_review = lambda _sequence: True
        module.wrap_review_literal_sequence = lambda sequence: ["review profile"] + list(sequence)
        try:
            sequence = ["literal review text"]
            result = plugin._filterSpeechSequence(sequence)
            self.assertEqual(result, ["review profile", "literal review text"])
        finally:
            plugin.terminate()

    def test_literal_bypass_diagnostic_reports_bound_review_script_name(self):
        module = nvda_harness._import_classic_speech_like_nvda()
        plugin = module.GlobalPlugin()

        class ReviewScripts:
            def script_review_currentLine(self):
                return None

        scriptHandler.getCurrentScript = lambda: ReviewScripts().script_review_currentLine
        try:
            self.assertEqual(plugin._current_speech_script_name(), "script_review_currentLine")
        finally:
            plugin.terminate()

    def test_review_cursor_command_sequence_routes_before_literal_shape_check(self):
        config.conf.profiles[0]["classicSpeech"] = {
            "speechHookEnabled": True,
            "debugLogging": False,
            "objectNavigationProcessing": False,
        }
        module = nvda_harness._import_classic_speech_like_nvda()
        plugin = module.GlobalPlugin()

        def script_review_currentLine():
            return None

        scriptHandler.getCurrentScript = lambda: script_review_currentLine
        plugin.processor.should_bypass_literal_review = lambda _sequence: False
        plugin.processor.process = lambda sequence, speech_origin="focus": list(sequence)
        module.wrap_review_literal_sequence = lambda sequence: ["review profile"] + list(sequence)
        try:
            sequence = ["spelled review text"]
            result = plugin._filterSpeechSequence(sequence)
            self.assertEqual(result, ["review profile", "spelled review text"])
        finally:
            plugin.terminate()

    def test_review_status_scripts_use_review_profile(self):
        module = nvda_harness._import_classic_speech_like_nvda()
        module.wrap_review_literal_sequence = lambda sequence: ["review profile"] + list(sequence)
        plugin = module.GlobalPlugin()
        try:
            for script_name in (
                "script_toggleSimpleReviewMode",
                "script_toggleCaretMovesReviewCursor",
                "script_toggleFocusMovesNavigatorObject",
                "script_moveMouseToNavigatorObject",
                "script_moveNavigatorObjectToMouse",
                # NVDA+Shift+F and its direct Review-only helper both report
                # formatting at api.getReviewPosition(), never at the caret.
                "script_reportFormatting",
                "script_reportFormattingAtReview",
            ):
                script = lambda: None
                script.__name__ = script_name
                scriptHandler.getCurrentScript = lambda current=script: current
                self.assertEqual(
                    plugin._filterSpeechSequence([script_name]),
                    ["review profile", script_name],
                )
        finally:
            plugin.terminate()

    def test_caret_formatting_stays_native(self):
        module = nvda_harness._import_classic_speech_like_nvda()
        module.wrap_review_literal_sequence = lambda sequence: ["review profile"] + list(sequence)
        plugin = module.GlobalPlugin()

        def script_reportFormattingAtCaret():
            return None

        scriptHandler.getCurrentScript = lambda: script_reportFormattingAtCaret
        try:
            sequence = ["caret formatting"]
            self.assertIs(plugin._filterSpeechSequence(sequence), sequence)
        finally:
            plugin.terminate()


class WindowsToastSystemVoiceTests(unittest.TestCase):
    """Keep only NVDA's dedicated transient-toast event paths in System Voice."""

    def setUp(self):
        nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
        self.original_nvda_objects = sys.modules.get("NVDAObjects")
        self.original_uia = sys.modules.get("NVDAObjects.UIA")
        self.emitted = []

        def emit(text):
            sequence = [text]
            for callback in list(speech.extensions.filter_speechSequence.callbacks):
                sequence = callback(sequence)
            self.emitted.append(sequence)

        class Toast_win8:
            def event_UIA_toolTipOpened(inner_self):
                emit("Windows 8 toast")

        class Toast_win10:
            def event_UIA_window_windowOpen(inner_self):
                emit("Windows toast")

            def event_UIA_toolTipOpened(inner_self):
                emit("Windows fallback toast")

        nvda_objects = types.ModuleType("NVDAObjects")
        uia = types.ModuleType("NVDAObjects.UIA")
        uia.Toast_win8 = Toast_win8
        uia.Toast_win10 = Toast_win10
        nvda_objects.UIA = uia
        sys.modules["NVDAObjects"] = nvda_objects
        sys.modules["NVDAObjects.UIA"] = uia
        self.Toast_win8 = Toast_win8
        self.Toast_win10 = Toast_win10
        self.original_win8 = Toast_win8.event_UIA_toolTipOpened
        self.original_win10_open = Toast_win10.event_UIA_window_windowOpen
        self.original_win10_tooltip = Toast_win10.event_UIA_toolTipOpened

        self.module = nvda_harness._import_classic_speech_like_nvda()
        self.module.wrap_system_notification_sequence = lambda sequence: ["system profile", *sequence]
        self.plugin = self.module.GlobalPlugin()

    def tearDown(self):
        self.plugin.terminate()
        if self.original_nvda_objects is None:
            sys.modules.pop("NVDAObjects", None)
        else:
            sys.modules["NVDAObjects"] = self.original_nvda_objects
        if self.original_uia is None:
            sys.modules.pop("NVDAObjects.UIA", None)
        else:
            sys.modules["NVDAObjects.UIA"] = self.original_uia
        nvda_harness._reset_global_plugin_imports()
        speech.extensions.filter_speechSequence.callbacks.clear()
        globalPluginHandler.runningPlugins.clear()

    def test_dedicated_toast_events_use_system_voice_and_restore_exact_methods(self):
        self.Toast_win8().event_UIA_toolTipOpened()
        self.Toast_win10().event_UIA_window_windowOpen()
        self.Toast_win10().event_UIA_toolTipOpened()
        self.assertEqual(
            self.emitted,
            [
                ["system profile", "Windows 8 toast"],
                ["system profile", "Windows toast"],
                ["system profile", "Windows fallback toast"],
            ],
        )

        self.plugin.terminate()
        self.assertIs(self.Toast_win8.event_UIA_toolTipOpened, self.original_win8)
        self.assertIs(self.Toast_win10.event_UIA_window_windowOpen, self.original_win10_open)
        self.assertIs(self.Toast_win10.event_UIA_toolTipOpened, self.original_win10_tooltip)


class KeyboardEntryVoiceProfileTests(unittest.TestCase):
    def setUp(self):
        nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
        self.original_typed_entry = getattr(speech, "speakTypedCharacters", None)

    def tearDown(self):
        if self.original_typed_entry is None:
            if hasattr(speech, "speakTypedCharacters"):
                delattr(speech, "speakTypedCharacters")
        else:
            speech.speakTypedCharacters = self.original_typed_entry
        nvda_harness._reset_global_plugin_imports()
        speech.extensions.filter_speechSequence.callbacks.clear()
        globalPluginHandler.runningPlugins.clear()

    def test_typed_character_and_word_echo_use_keyboard_profile_only_within_typed_entry_scope(self):
        emitted = []

        def native_typed_entry(ch):
            for sequence in ([ch], ["typed word"]):
                output = sequence
                for callback in list(speech.extensions.filter_speechSequence.callbacks):
                    output = callback(output)
                emitted.append(output)

        speech.speakTypedCharacters = native_typed_entry
        module = nvda_harness._import_classic_speech_like_nvda()
        module.wrap_keyboard_entry_sequence = lambda sequence: ["keyboard profile"] + list(sequence)
        plugin = module.GlobalPlugin()
        try:
            speech.speakTypedCharacters("a")
            self.assertEqual(
                emitted,
                [["keyboard profile", "a"], ["keyboard profile", "typed word"]],
            )
            # An unscoped key-name/shortcut-shaped sequence is never Keyboard entry.
            shortcut_output = plugin._filterSpeechSequence(["Control+S"])
            self.assertNotIn("keyboard profile", shortcut_output)
        finally:
            plugin.terminate()

    def test_typed_entry_wrapper_restores_the_original_nvda_function_on_plugin_termination(self):
        def native_typed_entry(ch):
            return ch

        speech.speakTypedCharacters = native_typed_entry
        module = nvda_harness._import_classic_speech_like_nvda()
        plugin = module.GlobalPlugin()
        try:
            self.assertIsNot(speech.speakTypedCharacters, native_typed_entry)
        finally:
            plugin.terminate()
        self.assertIs(speech.speakTypedCharacters, native_typed_entry)

    def test_nvda_master_braille_input_reaches_the_shared_typed_entry_path(self):
        nvda_source = nvda_harness.NVDA_SOURCE
        braille_input = (nvda_source / "brailleInput.py").read_text(encoding="utf-8")
        nvda_object = (nvda_source / "NVDAObjects" / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("focusObj.event_typedCharacter(ch=ch)", braille_input)
        self.assertIn("speech.speakTypedCharacters(ch)", nvda_object)


class SystemVoiceScopeTests(unittest.TestCase):
    def setUp(self):
        nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
        self.module = nvda_harness._import_classic_speech_like_nvda()
        self.module.wrap_system_notification_sequence = lambda sequence: ["system profile", *sequence]
        self.plugin = self.module.GlobalPlugin()

    def tearDown(self):
        self.plugin.terminate()

    def test_system_scope_wraps_only_explicit_system_origin(self):
        with self.module.system_notification_profile_routing():
            self.assertEqual(self.plugin._filterSpeechSequence(["Secure Desktop"]), ["system profile", "Secure Desktop"])
        output = self.plugin._filterSpeechSequence(["Browse mode"])
        self.assertNotIn("system profile", output)
    def test_named_system_scripts_use_system_profile(self):
        import sys
        import types
        original_script_handler = sys.modules.get("scriptHandler")
        script_handler = types.ModuleType("scriptHandler")
        try:
            for script_name in (
                "script_speechMode",
                "script_dateTime",
                "script_say_battery_status",
                "script_toggleScreenCurtain",
                "script_reportActiveConfigurationProfile",
                "script_toggleConfigProfileTriggers",
                "script_cycleAudioDuckingMode",
                "script_toggleCurrentAppSleepMode",
                "script_profile_Work",
            ):
                script = lambda: None
                script.__name__ = script_name
                script_handler.getCurrentScript = lambda current=script: current
                sys.modules["scriptHandler"] = script_handler
                self.assertEqual(
                    self.plugin._filterSpeechSequence([script_name]),
                    ["system profile", script_name],
                )
        finally:
            if original_script_handler is None:
                sys.modules.pop("scriptHandler", None)
            else:
                sys.modules["scriptHandler"] = original_script_handler


class FeedbackHookBoundaryTests(unittest.TestCase):
    def test_insert_tab_delegates_to_nvda_native_when_hook_is_disabled(self):
        import globalCommands

        calls = []
        original = globalCommands.commands.script_reportCurrentFocus
        globalCommands.commands.script_reportCurrentFocus = lambda gesture=None: calls.append(gesture)
        config.conf.profiles[0]["classicSpeech"] = {
        	"speechHookEnabled": False,
        	"debugLogging": False,
        	"queryObjectSource": "focus",
        }
        module = nvda_harness._import_classic_speech_like_nvda()
        plugin = module.GlobalPlugin()
        try:
        	speech.speak_calls.clear()
        	plugin.script_queryCurrentObject("gesture")
        	self.assertEqual(calls, ["gesture"])
        	self.assertEqual(speech.speak_calls, [])
        	self.assertFalse(getattr(plugin.processor, "_bypass_next_sequence", False))
        finally:
        	plugin.terminate()
        	globalCommands.commands.script_reportCurrentFocus = original

    def test_native_shortcut_bypass_only_arms_when_hook_is_registered(self):
        from speech import shortcutKeys as nvdaShortcutKeys

        config.conf.profiles[0]["classicSpeech"] = {
        	"speechHookEnabled": False,
        	"debugLogging": False,
        }
        module = nvda_harness._import_classic_speech_like_nvda()
        plugin = module.GlobalPlugin()
        try:
        	plugin.processor._bypass_next_sequence = False
        	nvdaShortcutKeys.speakKeyboardShortcuts()
        	self.assertFalse(plugin.processor._bypass_next_sequence)
        	plugin.set_speech_hook_enabled(True)
        	nvdaShortcutKeys.speakKeyboardShortcuts()
        	self.assertTrue(plugin.processor._bypass_next_sequence)
        	plugin.set_speech_hook_enabled(False)
        	self.assertFalse(plugin.processor._bypass_next_sequence)
        finally:
        	plugin.terminate()

    def test_insert_tab_query_reports_unchecked_checkbox_state(self):
        import controlTypes

        config.conf.profiles[0]["classicSpeech"] = {
        	"speechHookEnabled": True,
        	"debugLogging": False,
        	"queryObjectSource": "focus",
        }
        module = nvda_harness._import_classic_speech_like_nvda()
        plugin = module.GlobalPlugin()
        try:
        	focus = types.SimpleNamespace(
        		name="Object navigation processing",
        		role=controlTypes.Role.CHECKBOX,
        		states=set(),
        		value="",
        		positionInfo={},
        		keyboardShortcut="",
        		description="",
        		parent=None,
        	)
        	api.getFocusObject = lambda: focus
        	text = plugin.processor.get_query_object_text(focus)
        	self.assertIn("Object navigation processing", text)
        	self.assertIn("checkbox", text)
        	self.assertIn("not checked", text)
        finally:
        	plugin.terminate()


class FeedbackSettingsWordingCleanupTests(unittest.TestCase):
    def test_reset_actions_are_worded_as_immediate_confirmed_actions(self):
        root = Path(__file__).resolve().parents[1]
        dialog_source = (root / "_speech_core" / "settings" / "dialog.py").read_text(encoding="utf-8")
        verbosity_source = (root / "_speech_core" / "settings" / "verbosity_panel.py").read_text(encoding="utf-8")
        token_source = (root / "_speech_core" / "settings" / "token_editor_panel.py").read_text(encoding="utf-8")
        key_source = (root / "_speech_core" / "settings" / "key_labels_panel.py").read_text(encoding="utf-8")

        self.assertIn('label="Reset Profile Now"', dialog_source)
        self.assertIn('SetLabel("Reset Profile Now")', dialog_source)
        self.assertIn('SetLabel("Reset Tokens to Defaults Now")', dialog_source)
        self.assertIn('SetLabel("Reset Key Labels to Defaults Now")', dialog_source)
        for source in (verbosity_source, token_source, key_source):
            self.assertIn("Cancel will not undo this reset.", source)
            self.assertIn("Choose Yes to reset now, or No to keep your current settings.", source)

    def test_rename_mute_checkboxes_do_not_emit_custom_spoken_messages(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "_speech_core" / "settings" / "rename_list_panel.py").read_text(encoding="utf-8")
        self.assertNotIn("import ui", source)
        self.assertNotIn("ui.message", source)
        self.assertNotIn("_announceMuteState", source)
        self.assertNotIn("announceToggle", source)



    def test_interrupt_controls_wrap_native_keyboard_settings(self):
        root = Path(__file__).resolve().parents[1]
        panel_source = (root / "_speech_core" / "settings" / "misc_panel.py").read_text(encoding="utf-8")
        config_source = (root / "_speech_core" / "settings" / "misc_config.py").read_text(encoding="utf-8")
        controller_source = (root / "_speech_core" / "interrupt_control.py").read_text(encoding="utf-8")
        plugin_config_source = (root / "_speech_core" / "plugin_config.py").read_text(encoding="utf-8")

        self.assertIn('label="Prevent automatic speech interruptions"', panel_source)
        self.assertIn('label="Speech interrupt for typed characters"', panel_source)
        self.assertIn('label="Speech interrupt for Enter key"', panel_source)
        self.assertIn('"keyboard", "speechInterruptForCharacters"', config_source)
        self.assertIn('"keyboard", "speechInterruptForEnter"', config_source)
        self.assertNotIn("allowKeyboardSpeechInterrupt", panel_source)
        self.assertNotIn("allowKeyboardSpeechInterrupt", config_source)
        self.assertNotIn("allowKeyboardSpeechInterrupt", controller_source)
        self.assertNotIn("allowKeyboardSpeechInterrupt", plugin_config_source)
        self.assertNotIn("_is_keyboard_cancel_request", controller_source)

    def test_native_keyboard_interrupt_wrappers_preserve_independent_values(self):
        from globalPlugins._speech_core.settings import misc_config

        config.conf["keyboard"] = {
            "speechInterruptForCharacters": True,
            "speechInterruptForEnter": False,
        }
        self.assertTrue(misc_config._get_speech_interrupt_for_typed_characters_enabled())
        self.assertFalse(misc_config._get_speech_interrupt_for_enter_enabled())

        misc_config._set_speech_interrupt_for_typed_characters_enabled(False)
        self.assertFalse(config.conf["keyboard"]["speechInterruptForCharacters"])
        self.assertFalse(config.conf["keyboard"]["speechInterruptForEnter"])

        misc_config._set_speech_interrupt_for_enter_enabled(True)
        self.assertFalse(config.conf["keyboard"]["speechInterruptForCharacters"])
        self.assertTrue(config.conf["keyboard"]["speechInterruptForEnter"])

    def test_automatic_interrupt_protection_remains_independent_of_keyboard_settings(self):
        from globalPlugins._speech_core.interrupt_control import SpeechInterruptController

        calls = []
        speech.cancelSpeech = lambda *args, **kwargs: calls.append((args, kwargs))
        config.conf["classicSpeech"] = {"preventAutomaticSpeechInterrupt": False}
        controller = SpeechInterruptController()
        controller.install()
        try:
            controller._should_allow_automatic_cancel_speech = lambda: False
            speech.cancelSpeech()
            self.assertEqual(len(calls), 1)

            config.conf["classicSpeech"]["preventAutomaticSpeechInterrupt"] = True
            speech.cancelSpeech()
            self.assertEqual(len(calls), 1)
        finally:
            controller.uninstall()

if __name__ == "__main__":
    unittest.main(verbosity=2)
