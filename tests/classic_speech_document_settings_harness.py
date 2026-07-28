"""ClassicSpeech v3 Document Reading / Proofing settings harness.

This verifies the v3 plan stays a native NVDA documentFormatting settings
wrapper: no document processor, no TextInfo hook, no web/browse clutter.
"""
from __future__ import annotations

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


INCLUDED_DOCUMENT_KEYS = {
    "reportFontName",
    "reportFontSize",
    "fontAttributeReporting",
    "reportSuperscriptsAndSubscripts",
    "reportEmphasis",
    "reportHighlight",
    "reportStyle",
    "reportColor",
    "reportTransparentColor",
    "reportComments",
    "reportBookmarks",
    "reportRevisions",
    "reportSpellingErrors2",
    "reportPage",
    "reportLineNumber",
    "reportLineIndentation",
    "ignoreBlankLinesForRLI",
    "reportParagraphIndentation",
    "reportLineSpacing",
    "reportAlignment",
    "reportTables",
    "reportTableHeaders",
    "reportTableCellCoords",
    "reportCellBorders",
    "detectFormatAfterCursor",
}

EXCLUDED_WEB_KEYS = {
    "reportHeadings",
    "reportLinks",
    "reportLinkType",
    "reportGraphics",
    "reportLists",
    "reportBlockQuotes",
    "reportGroupings",
    "reportLandmarks",
    "reportArticles",
    "reportFrames",
    "reportFigures",
    "reportClickable",
    "includeLayoutTables",
}


class DocumentFormattingConfigHelperTests(unittest.TestCase):
    def setUp(self):
        nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
        config.conf["documentFormatting"] = {
            "reportFontName": False,
            "reportFontSize": True,
            "fontAttributeReporting": 2,
            "reportSuperscriptsAndSubscripts": False,
            "reportEmphasis": True,
            "reportHighlight": False,
            "reportStyle": True,
            "reportColor": False,
            "reportTransparentColor": True,
            "reportComments": True,
            "reportBookmarks": False,
            "reportRevisions": True,
            "reportSpellingErrors2": 5,
            "reportPage": True,
            "reportLineNumber": False,
            "reportLineIndentation": 0,
            "ignoreBlankLinesForRLI": True,
            "reportParagraphIndentation": False,
            "reportLineSpacing": True,
            "reportAlignment": False,
            "reportTables": True,
            "reportTableHeaders": 1,
            "reportTableCellCoords": False,
            "reportCellBorders": 2,
            "detectFormatAfterCursor": False,
            "reportLinks": True,
            "includeLayoutTables": True,
        }

    def tearDown(self):
        nvda_harness._reset_global_plugin_imports()

    def test_document_formatting_helpers_wrap_only_v3_document_keys(self):
        nvda_harness._import_classic_speech_like_nvda()
        from globalPlugins._speech_core.settings import document_formatting_config as doc_config

        self.assertEqual(set(doc_config.DOCUMENT_READING_PROOFING_KEYS), INCLUDED_DOCUMENT_KEYS)
        self.assertTrue(EXCLUDED_WEB_KEYS.isdisjoint(doc_config.DOCUMENT_READING_PROOFING_KEYS))
        self.assertEqual(doc_config.REPORT_LINE_INDENTATION_CHOICES[0], ("Off", 0))
        self.assertEqual(doc_config.REPORT_LINE_INDENTATION_CHOICES[-1], ("Both Speech and Tones", 3))
        self.assertEqual(doc_config.FONT_ATTRIBUTE_REPORTING_CHOICES[0], ("Off", 0))
        self.assertEqual(doc_config.FONT_ATTRIBUTE_REPORTING_CHOICES[-1], ("Speech and braille", 3))
        self.assertEqual(doc_config.REPORT_CELL_BORDERS_CHOICES[1], ("Styles", 1))
        self.assertEqual(doc_config.REPORT_CELL_BORDERS_CHOICES[2], ("Both Colors and Styles", 2))
        self.assertEqual(
            doc_config.REPORT_SPELLING_ERRORS_FLAGS,
            (("Speech", 1), ("Sound", 2), ("Braille", 4)),
        )
        self.assertTrue(doc_config._DEFAULTS["reportHighlight"])
        self.assertTrue(doc_config._DEFAULTS["reportComments"])
        self.assertTrue(doc_config._DEFAULTS["reportBookmarks"])
        self.assertFalse(doc_config._DEFAULTS["reportTransparentColor"])

    def test_transparent_color_dependency_matches_colors(self):
        nvda_harness._import_classic_speech_like_nvda()
        from globalPlugins._speech_core.settings.document_formatting_config import (
            _is_report_transparent_color_enabled,
            _set_document_formatting_setting,
        )

        _set_document_formatting_setting("reportColor", False)
        _set_document_formatting_setting("reportTransparentColor", True)
        self.assertFalse(_is_report_transparent_color_enabled())
        self.assertTrue(config.conf["documentFormatting"]["reportTransparentColor"])

        _set_document_formatting_setting("reportColor", True)
        self.assertTrue(_is_report_transparent_color_enabled())

    def test_line_indentation_dependency_matches_nvda_native(self):
        nvda_harness._import_classic_speech_like_nvda()
        from globalPlugins._speech_core.settings.document_formatting_config import (
            _is_ignore_blank_lines_for_rli_enabled,
            _set_document_formatting_setting,
        )

        for value, expected in ((0, False), (1, True), (2, True), (3, True)):
            _set_document_formatting_setting("reportLineIndentation", value)
            self.assertIs(_is_ignore_blank_lines_for_rli_enabled(), expected)

        _set_document_formatting_setting("ignoreBlankLinesForRLI", True)
        _set_document_formatting_setting("reportLineIndentation", 0)
        self.assertFalse(_is_ignore_blank_lines_for_rli_enabled())
        self.assertTrue(config.conf["documentFormatting"]["ignoreBlankLinesForRLI"])

    def test_snapshot_restore_keeps_web_settings_untouched(self):
        nvda_harness._import_classic_speech_like_nvda()
        from globalPlugins._speech_core.settings.document_formatting_config import (
            _capture_document_formatting_state,
            _restore_document_formatting_state,
            _set_document_formatting_setting,
        )

        original = _capture_document_formatting_state()
        _set_document_formatting_setting("reportFontName", True)
        _set_document_formatting_setting("reportLineIndentation", 2)
        _set_document_formatting_setting("ignoreBlankLinesForRLI", False)
        config.conf["documentFormatting"]["reportLinks"] = False

        _restore_document_formatting_state(original)
        self.assertFalse(config.conf["documentFormatting"]["reportFontName"])
        self.assertEqual(config.conf["documentFormatting"]["reportLineIndentation"], 0)
        self.assertTrue(config.conf["documentFormatting"]["ignoreBlankLinesForRLI"])
        self.assertFalse(config.conf["documentFormatting"]["reportLinks"])


class DocumentReadingProofingPanelSourceTests(unittest.TestCase):
    def setUp(self):
        nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()

    def test_web_settings_modules_are_grouped_under_the_web_domain(self):
        web_settings = ROOT / "_speech_core" / "settings" / "web"
        self.assertTrue((web_settings / "__init__.py").is_file())
        self.assertTrue((web_settings / "formatting_config.py").is_file())
        self.assertTrue((web_settings / "summary_config.py").is_file())
        self.assertTrue((web_settings / "dialog.py").is_file())

    def tearDown(self):
        nvda_harness._reset_global_plugin_imports()


    def test_panel_imports_and_category_is_registered(self):
        nvda_harness._import_classic_speech_like_nvda()
        from globalPlugins._speech_core.settings.dialog import ClassicSpeechDialog
        from globalPlugins._speech_core.settings.document_reading_proofing_panel import (
            DocumentReadingProofingPanel,
        )

        self.assertIn("Document Reading / Proofing", ClassicSpeechDialog.CATEGORY_NAMES)
        self.assertLess(
            ClassicSpeechDialog.CATEGORY_NAMES.index("Document Reading / Proofing"),
            ClassicSpeechDialog.CATEGORY_NAMES.index("Menus"),
        )
        self.assertTrue(hasattr(DocumentReadingProofingPanel, "apply_live"))

    def test_panel_source_contains_required_sections_and_excludes_web_keys(self):
        panel_source = (
            ROOT / "_speech_core" / "settings" / "document_reading_proofing_panel.py"
        ).read_text(encoding="utf-8")
        for label in (
            "Font",
            "Document information",
            "Pages and spacing",
            "Table information",
            "Advanced",
            "&Font name",
            "Font &size",
            "Font attrib&utes",
            "&Colors",
            "Report transparent color values",
            "Spelling or grammar e&rrors",
            "Line &indentation reporting:",
            "Ignore &blank lines for line indentation reporting",
            "H&eaders",
            "Cell &borders:",
            "Report formatting chan&ges after the cursor (can cause a lag)",
        ):
            self.assertIn(label, panel_source)
        for excluded in EXCLUDED_WEB_KEYS:
            self.assertNotIn(excluded, panel_source)
        self.assertNotIn("Restore Defaults", panel_source)

    def test_line_indentation_checkbox_dependency_is_wired(self):
        panel_source = (
            ROOT / "_speech_core" / "settings" / "document_reading_proofing_panel.py"
        ).read_text(encoding="utf-8")
        self.assertIn("_sync_line_indentation_dependency", panel_source)
        self.assertIn("ignoreBlankLinesRLICheckbox.Enable", panel_source)
        self.assertIn("lineIndentationCombo.Bind(wx.EVT_CHOICE", panel_source)
        self.assertIn("_is_ignore_blank_lines_for_rli_enabled", panel_source)

    def test_transparent_color_dependency_is_wired(self):
        panel_source = (
            ROOT / "_speech_core" / "settings" / "document_reading_proofing_panel.py"
        ).read_text(encoding="utf-8")
        self.assertLess(panel_source.index('"&Colors"'), panel_source.index('"Report transparent color values"'))
        self.assertIn("_sync_transparent_color_dependency", panel_source)
        self.assertIn("transparentColorCheckBox.Enable", panel_source)
        self.assertIn("colorCheckBox.Bind(wx.EVT_CHECKBOX, self.onColorChanged)", panel_source)

    def test_spelling_errors_uses_native_custom_checklist_not_raw_list(self):
        panel_source = (
            ROOT / "_speech_core" / "settings" / "document_reading_proofing_panel.py"
        ).read_text(encoding="utf-8")
        self.assertIn("from gui import guiHelper, nvdaControls", panel_source)
        self.assertIn("guiHelper.BoxSizerHelper", panel_source)
        self.assertIn("group.addLabeledControl", panel_source)
        self.assertIn("nvdaControls.CustomCheckListBox", panel_source)
        self.assertIn("reportSpellingErrors2.Bind(wx.EVT_CHECKLISTBOX", panel_source)
        self.assertIn("REPORT_SPELLING_ERRORS_FLAGS", panel_source)
        self.assertIn("self.reportSpellingErrors2.Select(0)", panel_source)
        self.assertIn("evt.Skip()", panel_source)
        self.assertNotIn("wx.CheckListBox", panel_source)
        self.assertNotIn("wx.ComboBox", panel_source)
        self.assertNotIn("EVT_COMBOBOX", panel_source)
        self.assertNotIn("REPORT_SPELLING_ERRORS_CHOICES", panel_source)
        self.assertNotIn("Speech, sound, and braille", panel_source)

    def test_spelling_errors_checklist_builds_native_bitmask(self):
        nvda_harness._import_classic_speech_like_nvda()
        from globalPlugins._speech_core.settings.document_reading_proofing_panel import (
            DocumentReadingProofingPanel,
        )

        class FakeCheckListBox:
            def GetCheckedItems(self):
                return [0, 2]

        panel = object.__new__(DocumentReadingProofingPanel)
        panel.reportSpellingErrors2 = FakeCheckListBox()
        self.assertEqual(panel._get_spelling_errors_value(), 5)

    def test_dialog_snapshots_document_formatting_for_cancel_and_apply(self):
        dialog_source = (ROOT / "_speech_core" / "settings" / "dialog.py").read_text(encoding="utf-8")
        self.assertIn("_capture_document_formatting_state", dialog_source)
        self.assertIn("_restore_document_formatting_state", dialog_source)
        self.assertIn("self._originalDocumentFormatting", dialog_source)
        self.assertIn("self.documentReadingProofingPanel.apply_live(save=True)", dialog_source)

    def test_dialog_cancel_restores_document_formatting_snapshot(self):
        nvda_harness._import_classic_speech_like_nvda()
        from globalPlugins._speech_core.settings.dialog import ClassicSpeechDialog

        config.conf["documentFormatting"] = {
            "reportFontName": False,
            "reportLineIndentation": 0,
            "ignoreBlankLinesForRLI": True,
            "reportLinks": True,
        }
        dialog = object.__new__(ClassicSpeechDialog)
        dialog._captureTransactionBaseline()
        config.conf["documentFormatting"]["reportFontName"] = True
        config.conf["documentFormatting"]["reportLineIndentation"] = 2
        config.conf["documentFormatting"]["ignoreBlankLinesForRLI"] = False
        config.conf["documentFormatting"]["reportLinks"] = False

        dialog._restoreTransactionBaseline()
        self.assertFalse(config.conf["documentFormatting"]["reportFontName"])
        self.assertEqual(config.conf["documentFormatting"]["reportLineIndentation"], 0)
        self.assertTrue(config.conf["documentFormatting"]["ignoreBlankLinesForRLI"])
        self.assertFalse(config.conf["documentFormatting"]["reportLinks"])

    def test_dialog_apply_recapture_makes_document_changes_committed(self):
        nvda_harness._import_classic_speech_like_nvda()
        from globalPlugins._speech_core.settings.dialog import ClassicSpeechDialog

        config.conf["documentFormatting"] = {
            "reportFontName": False,
            "reportLineIndentation": 0,
            "ignoreBlankLinesForRLI": True,
        }
        dialog = object.__new__(ClassicSpeechDialog)
        dialog._captureTransactionBaseline()
        config.conf["documentFormatting"]["reportFontName"] = True
        config.conf["documentFormatting"]["reportLineIndentation"] = 1
        dialog._captureTransactionBaseline()  # mirrors Apply recapturing committed state.
        config.conf["documentFormatting"]["reportFontName"] = False
        config.conf["documentFormatting"]["reportLineIndentation"] = 0

        dialog._restoreTransactionBaseline()
        self.assertTrue(config.conf["documentFormatting"]["reportFontName"])
        self.assertEqual(config.conf["documentFormatting"]["reportLineIndentation"], 1)
        self.assertTrue(config.conf["documentFormatting"]["ignoreBlankLinesForRLI"])

    def test_v3_does_not_add_document_processing_hooks(self):
        web_processor_root = ROOT / "_speech_core" / "processors" / "web"
        for path in sorted((ROOT / "_speech_core").rglob("*.py")):
            # Page-entry presentation belongs to the opt-in Web processor. It
            # deliberately mirrors NVDA's native Browse Mode line presentation
            # on fallback; that is not a generic document speech processor.
            if path.is_relative_to(web_processor_root):
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("speakTextInfo", text, path)
            self.assertNotIn("getTextInfoSpeech", text, path)
        processors = {p.name for p in (ROOT / "_speech_core" / "processors").glob("*.py")}
        self.assertNotIn("document.py", processors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
