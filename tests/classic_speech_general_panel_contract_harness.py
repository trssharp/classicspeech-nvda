"""Direct persistence contracts for ClassicSpeech General Settings panels.

These tests exercise each panel's real ``apply_live`` method with minimal
control doubles. This gives option-level coverage without relying on wx's UI
implementation in the outside-NVDA harness.
"""
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

import classic_speech_nvda_master_harness as nvda_harness
import config
import globalPluginHandler
import speech


class Control:
    def __init__(self, value):
        self.value = value

    def GetValue(self):
        return self.value

    def GetSelection(self):
        return self.value

    def GetStringSelection(self):
        return self.value


class GeneralPanelContractTests(unittest.TestCase):
    def setUp(self):
        nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
        self.module = nvda_harness._import_classic_speech_like_nvda()
        self.plugin = self.module.GlobalPlugin()
        globalPluginHandler.runningPlugins.append(self.plugin)

    def tearDown(self):
        self.plugin.terminate()
        globalPluginHandler.runningPlugins.clear()
        speech.extensions.filter_speechSequence.callbacks.clear()
        nvda_harness._reset_global_plugin_imports()

    def _section(self):
        return config.conf.profiles[0]["classicSpeech"]

    def test_hotkeys_panel_persists_every_control(self):
        from globalPlugins._speech_core.settings.hotkeys_panel import HotkeysPanel

        panel = types.SimpleNamespace(
            hotkeyModeChoice=Control(3),
            hotkeyFormatChoice=Control(1),
            hotkeyTypesChoice=Control(0),
            dialogAccessKeyOnlyCheck=Control(True),
        )
        panel._getModeFromChoice = lambda: HotkeysPanel._getModeFromChoice(panel)
        panel._getFormatFromChoice = lambda: HotkeysPanel._getFormatFromChoice(panel)
        panel._getTypesFromChoice = lambda: HotkeysPanel._getTypesFromChoice(panel)
        HotkeysPanel.apply_live(panel)

        section = self._section()
        self.assertEqual(section["hotkeyMode"], "both")
        self.assertEqual(section["hotkeyFormat"], "expandedNoPlus")
        self.assertEqual(section["hotkeyTypes"], "access")
        self.assertTrue(section["hotkeyDialogAccessKeyOnly"])

    def test_menus_panel_persists_every_toggle_and_message(self):
        from globalPlugins._speech_core.settings.menus_panel import MenusPanel

        panel = types.SimpleNamespace(
            announceMenuOpen=Control(False),
            menuOpenMessage=Control("Open custom"),
            announceMenuClose=Control(True),
            menuCloseMessage=Control("Close custom"),
            announceMenuBarFocus=Control(False),
            menuBarFocusMessage=Control("Focus custom"),
            announceMenuBarLeave=Control(True),
            menuBarLeaveMessage=Control("Leave custom"),
        )
        MenusPanel.apply_live(panel)

        section = self._section()
        self.assertEqual(
            {key: section[key] for key in (
                "announceMenuOpen", "announceMenuClose", "announceMenuBarFocus", "announceMenuBarLeave",
            )},
            {
                "announceMenuOpen": False,
                "announceMenuClose": True,
                "announceMenuBarFocus": False,
                "announceMenuBarLeave": True,
            },
        )
        self.assertEqual(section["menuOpenMessage"], "Open custom")
        self.assertEqual(section["menuCloseMessage"], "Close custom")
        self.assertEqual(section["menuBarFocusMessage"], "Focus custom")
        self.assertEqual(section["menuBarLeaveMessage"], "Leave custom")

    def test_text_processing_panel_persists_every_control(self):
        from globalPlugins._speech_core.settings.text_processing_panel import TextProcessingPanel

        panel = types.SimpleNamespace(
            announceNewLinesDuringSayAll=Control(True),
            newLineMessage=Control("new row"),
            splitMixedCaseWords=Control(True),
            suppressWordInternalDashes=Control(True),
            spellAlphanumericData=Control("Spell mixed letters and numbers phonetically"),
            listItemStateReporting=Control("Say both"),
            repeatedCharacterMode=Control("Count repeated characters and spaces"),
        )
        TextProcessingPanel.apply_live(panel)

        self.assertEqual(
            self._section()["textProcessingData"],
            {
                "announceNewLinesDuringSayAll": True,
                "newLineMessage": "new row",
                "splitMixedCaseWords": True,
                "suppressWordInternalDashes": True,
                "spellAlphanumericData": "phonetic",
                "listItemStateReporting": "both",
                "repeatedCharacterMode": "count",
            },
        )

    def test_number_processing_panel_persists_every_control(self):
        from globalPlugins._speech_core.settings.number_processing_panel import NumberProcessingPanel

        panel = types.SimpleNamespace(
            numberProcessingMode=Control("Pairs"),
            singleDigitsThreshold=Control("Seven or more digits"),
            phoneNumberProcessing=Control("Grouped digits"),
            friendlyTollFreePrefixes=Control(False),
            currencyProcessing=Control("Dollars and cents"),
            ordinalProcessing=Control("Ordinals as words"),
            numericDateProcessing=Control("Full"),
            numericDateFormat=Control("Day month year"),
            recognizeIsoDates=Control(False),
            useWindowsDateFormat=Control(True),
        )
        NumberProcessingPanel.apply_live(panel)

        self.assertEqual(
            self._section()["numberProcessingData"],
            {
                "numberProcessingMode": "pairs",
                "singleDigitsIfNumberContains": "7",
                "phoneNumberProcessing": "groupedDigits",
                "friendlyTollFreePrefixes": False,
                "currencyProcessing": "dollarsAndCents",
                "ordinalProcessing": "words",
                "numericDateProcessing": "full",
                "numericDateFormat": "dmy",
                "recognizeIsoDates": False,
                "useWindowsDateFormat": True,
            },
        )

    def test_misc_panel_persists_classicspeech_and_native_controls(self):
        from globalPlugins._speech_core.settings.misc_panel import MiscPanel

        panel = types.SimpleNamespace(
            announceDefaultButton=Control(True),
            guessObjectPositionInformationWhenUnavailable=Control(True),
            queryObjectSourceChoice=Control(2),
            objectNavigationProcessing=Control(True),
            preventAutomaticSpeechInterrupt=Control(True),
            speechInterruptForCharacters=Control(False),
            speechInterruptForEnter=Control(True),
            automaticSpeechInterruptFallbackMs=Control("2000 ms"),
        )
        MiscPanel.apply_live(panel)

        section = self._section()
        self.assertTrue(section["announceDefaultButton"])
        self.assertEqual(section["queryObjectSource"], "navigator")
        self.assertTrue(section["objectNavigationProcessing"])
        self.assertTrue(section["preventAutomaticSpeechInterrupt"])
        self.assertEqual(section["automaticSpeechInterruptFallbackMs"], 2000)
        self.assertTrue(config.conf["presentation"]["guessObjectPositionInformationWhenUnavailable"])
        self.assertFalse(config.conf["keyboard"]["speechInterruptForCharacters"])
        self.assertTrue(config.conf["keyboard"]["speechInterruptForEnter"])
    def test_speech_timing_panel_persists_global_and_per_token_timing(self):
        from globalPlugins._speech_core.settings.speech_timing_panel import SpeechTimingPanel
        from globalPlugins._speech_core.settings.constants import TOKEN_ORDER_KINDS

        panel = types.SimpleNamespace(
            shapeConfig={"renames": {}, "mutedLabels": [], "order": list(TOKEN_ORDER_KINDS)},
            globalPauseChoice=Control(1),
            pausePlacementChoice=Control(1),
            pauseAfterFinalToken=Control(False),
            tokenPauseChoices={kind: Control(0) for kind in TOKEN_ORDER_KINDS},
        )
        panel._getPauseValueFromChoice = lambda: SpeechTimingPanel._getPauseValueFromChoice(panel)
        panel._getPausePlacementFromChoice = lambda: SpeechTimingPanel._getPausePlacementFromChoice(panel)
        panel._getTokenPauseValueFromChoice = lambda control: SpeechTimingPanel._getTokenPauseValueFromChoice(panel, control)
        panel._refreshShapeFromControls = lambda: SpeechTimingPanel._refreshShapeFromControls(panel)

        shape = SpeechTimingPanel.get_working_shape_config(panel)
        SpeechTimingPanel.apply_live(panel, save=True)

        self.assertEqual(shape["pauseMode"], "global")
        self.assertEqual(shape["globalPause"], 80)
        self.assertEqual(shape["pausePlacement"], "after")
        self.assertFalse(shape["pauseAfterFinalToken"])
        self.assertEqual(shape["pauses"], {kind: -1 for kind in TOKEN_ORDER_KINDS})
        self.assertEqual(self._section()["shapeData"]["pausePlacement"], "after")
        from globalPlugins._speech_core.verbosity import VerbosityManager
        self.assertEqual(VerbosityManager().get_shape_config()["pausePlacement"], "after")

    def test_key_labels_panel_persists_renames_and_muted_labels(self):
        from globalPlugins._speech_core.settings.key_labels_panel import KeyLabelsPanel

        panel = types.SimpleNamespace(
            keyLabelConfig={},
            keyPanel=types.SimpleNamespace(
                getRenames=lambda: {"f1": "Help"},
                getMutedLabels=lambda: ["tab"],
            ),
        )
        panel._refreshWorkingConfigFromControls = lambda: KeyLabelsPanel._refreshWorkingConfigFromControls(panel)
        KeyLabelsPanel.apply_live(panel, save=True)

        self.assertEqual(
            self._section()["keyLabelData"],
            {"renames": {"f1": "Help"}, "mutedLabels": ["tab"]},
        )
        from globalPlugins._speech_core.key_labels import get_key_label_config
        self.assertEqual(get_key_label_config(), {"renames": {"f1": "Help"}, "mutedLabels": ["tab"]})


if __name__ == "__main__":
    unittest.main(verbosity=2)
