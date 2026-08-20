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

    def Enable(self, enabled=True):
        self.enabled = bool(enabled)

    def IsEnabled(self):
        return getattr(self, "enabled", True)


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

    def test_hotkeys_off_disables_dependent_controls(self):
        from globalPlugins._speech_core.settings.hotkeys_panel import HotkeysPanel

        panel = types.SimpleNamespace(
            hotkeyModeChoice=Control(0),
            hotkeyFormatChoice=Control(0),
            hotkeyTypesChoice=Control(0),
            dialogAccessKeyOnlyCheck=Control(False),
        )
        panel._getModeFromChoice = lambda: HotkeysPanel._getModeFromChoice(panel)

        HotkeysPanel._syncDependentControlsAvailability(panel)

        self.assertFalse(panel.hotkeyFormatChoice.IsEnabled())
        self.assertFalse(panel.hotkeyTypesChoice.IsEnabled())
        self.assertFalse(panel.dialogAccessKeyOnlyCheck.IsEnabled())

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

    def test_menus_disable_messages_for_unchecked_announcements(self):
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

        MenusPanel._syncMessageAvailability(panel)

        self.assertFalse(panel.menuOpenMessage.IsEnabled())
        self.assertTrue(panel.menuCloseMessage.IsEnabled())
        self.assertFalse(panel.menuBarFocusMessage.IsEnabled())
        self.assertTrue(panel.menuBarLeaveMessage.IsEnabled())

    def test_text_processing_panel_persists_every_control(self):
        from globalPlugins._speech_core.settings.text.panel import TextProcessingPanel

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
        )
        self._section()["automaticSpeechInterruptFallbackMs"] = 2000
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
    def test_verbosity_panel_persists_selected_profile_tokens_and_position_mode(self):
        from globalPlugins._speech_core.settings.verbosity_panel import VerbosityPanel

        class CheckedList:
            def __init__(self, checked_items):
                self.checked_items = checked_items

            def GetCheckedItems(self):
                return self.checked_items

        panel = types.SimpleNamespace(
            currentEditProfile="Beginner",
            profileConfig={"enabledTokens": {"name": True, "position": True, "value": True}},
            profileBehavior={},
            activeProfileChoice=Control(2),
            tokenList=CheckedList([2, 4]),
            positionModeChoice=Control(1),
        )
        panel._getPositionModeFromChoice = lambda: VerbosityPanel._getPositionModeFromChoice(panel)
        panel._refreshWorkingConfigFromControls = lambda: VerbosityPanel._refreshWorkingConfigFromControls(panel)

        profile = VerbosityPanel.get_working_profile_config(panel)
        behavior = VerbosityPanel.get_working_profile_behavior(panel)
        VerbosityPanel.apply_live(panel, save=True)

        self.assertEqual(panel.currentEditProfile, "Advanced")
        self.assertEqual(
            profile["enabledTokens"],
            {"name": False, "position": True, "value": True, "role": False, "state": True, "description": False, "tooltip": True},
        )
        self.assertEqual(behavior["positionMode"], "first")
        saved = self._section()["profileData"]["Advanced"]
        self.assertFalse(saved["enabledTokens"]["role"])
        self.assertTrue(saved["enabledTokens"]["tooltip"])
        self.assertEqual(self._section()["profileBehaviorData"]["Advanced"]["positionMode"], "first")

    def test_advanced_hook_message_is_disabled_when_announcement_is_off(self):
        from globalPlugins._speech_core.settings.advanced_panel import AdvancedPanel

        panel = types.SimpleNamespace(
            announceSpeechHookLoaded=Control(False),
            speechHookLoadedMessage=Control("ClassicSpeech hook loaded"),
        )

        AdvancedPanel._syncSpeechHookLoadedMessageAvailability(panel)

        self.assertFalse(panel.speechHookLoadedMessage.IsEnabled())

    def test_token_editor_persists_order_renames_and_muted_labels(self):
        from globalPlugins._speech_core.settings.token_editor_panel import TokenEditorPanel
        from globalPlugins._speech_core.settings.constants import TOKEN_ORDER_KINDS

        class TokenList:
            def __init__(self, order):
                self.order = order
            def GetCount(self):
                return len(self.order)
            def GetClientData(self, index):
                return self.order[index]
            def GetString(self, index):
                return self.order[index]

        class RenameData:
            def __init__(self, renames, muted):
                self.renames = renames
                self.muted = muted
            def getRenames(self):
                return self.renames
            def getMutedLabels(self):
                return self.muted

        order = ["state", "role", "name", "value", "position", "description", "hotkey"]
        panel = types.SimpleNamespace(
            shapeConfig={"order": list(TOKEN_ORDER_KINDS), "renames": {"custom": "Custom", "role": "Old"}, "mutedLabels": ["custom", "role"]},
            tokenOrderList=TokenList(order),
            rolePanel=RenameData({"role": "Type"}, ["role"]),
            statePanel=RenameData({"state": "Status"}, ["state"]),
        )
        panel._normalizeOrder = lambda values: TokenEditorPanel._normalizeOrder(panel, values)
        panel._getTokenOrderFromList = lambda: TokenEditorPanel._getTokenOrderFromList(panel)
        panel._rebuildMergedRenames = lambda: TokenEditorPanel._rebuildMergedRenames(panel)
        panel._rebuildMutedLabels = lambda: TokenEditorPanel._rebuildMutedLabels(panel)
        panel._refreshWorkingConfigFromControls = lambda: TokenEditorPanel._refreshWorkingConfigFromControls(panel)
        TokenEditorPanel.apply_live(panel, save=True)

        saved = self._section()["shapeData"]
        self.assertEqual(saved["order"], order)
        self.assertEqual(saved["renames"], {"custom": "Custom", "role": "Type", "state": "Status"})
        self.assertEqual(saved["mutedLabels"], ["custom", "role", "state"])

    def test_document_reading_proofing_panel_persists_every_native_control(self):
        from globalPlugins._speech_core.settings.document_reading_proofing_panel import DocumentReadingProofingPanel

        class Checked(Control):
            def IsChecked(self):
                return self.value

        panel = types.SimpleNamespace(
            fontNameCheckBox=Checked(True), fontSizeCheckBox=Checked(True), fontAttrsList=Control(3),
            superscriptsAndSubscriptsCheckBox=Checked(True), emphasisCheckBox=Checked(True), highlightCheckBox=Checked(False),
            styleCheckBox=Checked(True), colorCheckBox=Checked(True), transparentColorCheckBox=Checked(True),
            commentsCheckBox=Checked(False), bookmarksCheckBox=Checked(False), revisionsCheckBox=Checked(False),
            reportSpellingErrors2=types.SimpleNamespace(GetCheckedItems=lambda: [0, 2]),
            pageCheckBox=Checked(False), lineNumberCheckBox=Checked(True), lineIndentationCombo=Control(3),
            ignoreBlankLinesRLICheckbox=Checked(True), paragraphIndentationCheckBox=Checked(True), lineSpacingCheckBox=Checked(True),
            alignmentCheckBox=Checked(True), tablesCheckBox=Checked(False), tableHeadersComboBox=Control(3),
            tableCellCoordsCheckBox=Checked(False), borderComboBox=Control(2), detectFormatAfterCursorCheckBox=Checked(True),
        )
        panel._get_spelling_errors_value = lambda: DocumentReadingProofingPanel._get_spelling_errors_value(panel)
        panel._sync_line_indentation_dependency = lambda: None
        panel._sync_transparent_color_dependency = lambda: None
        DocumentReadingProofingPanel.apply_live(panel, save=True)

        expected = {
            "reportFontName": True, "reportFontSize": True, "fontAttributeReporting": 3,
            "reportSuperscriptsAndSubscripts": True, "reportEmphasis": True, "reportHighlight": False,
            "reportStyle": True, "reportColor": True, "reportTransparentColor": True,
            "reportComments": False, "reportBookmarks": False, "reportRevisions": False,
            "reportSpellingErrors2": 5, "reportPage": False, "reportLineNumber": True,
            "reportLineIndentation": 3, "ignoreBlankLinesForRLI": True,
            "reportParagraphIndentation": True, "reportLineSpacing": True, "reportAlignment": True,
            "reportTables": False, "reportTableHeaders": 3, "reportTableCellCoords": False,
            "reportCellBorders": 2, "detectFormatAfterCursor": True,
        }
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertEqual(config.conf["documentFormatting"].get(key), value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
