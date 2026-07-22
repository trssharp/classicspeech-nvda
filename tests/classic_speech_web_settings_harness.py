"""ClassicSpeech v3 Web / Browse Mode settings harness.

This verifies that the v3 web dialog is a native NVDA settings wrapper: it
writes virtualBuffers plus web-oriented documentFormatting keys, uses native
labels/control shapes from NVDA master, and preserves OK/Apply/Cancel-style
state snapshots without starting NVDA.
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

VIRTUAL_BUFFER_SAMPLE = {
	"maxLineLength": 80,
	"linesPerPage": 40,
	"useScreenLayout": True,
	"enableOnPageLoad": False,
	"autoSayAllOnPageLoad": True,
	"autoPassThroughOnFocusChange": False,
	"autoPassThroughOnCaretMove": True,
	"passThroughAudioIndication": True,
	"trapNonCommandGestures": False,
	"loadChromiumVBufOnBusyState": "DEFAULT",
	"browseModeTouchNavigationElements": ["heading", "link", "table"],
}

ANNOTATIONS_SAMPLE = {
	"reportDetails": False,
	"reportAriaDescription": True,
}

BRAILLE_WEB_SAMPLE = {
	"reportLiveRegions": "DEFAULT",
}

WEB_DOCUMENT_FORMATTING_SAMPLE = {
	"includeLayoutTables": True,
	"reportHeadings": True,
	"reportLinks": False,
	"reportLinkType": True,
	"reportGraphics": False,
	"reportLists": True,
	"reportBlockQuotes": False,
	"reportGroupings": True,
	"reportLandmarks": False,
	"reportArticles": True,
	"reportFrames": False,
	"reportFigures": True,
	"reportClickable": False,
}


class WebBrowseConfigHelperTests(unittest.TestCase):
	def setUp(self):
		nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
		config.conf["virtualBuffers"] = dict(VIRTUAL_BUFFER_SAMPLE)
		config.conf["documentFormatting"].update(WEB_DOCUMENT_FORMATTING_SAMPLE)
		config.conf["annotations"] = dict(ANNOTATIONS_SAMPLE)
		config.conf["braille"] = dict(BRAILLE_WEB_SAMPLE)

	def tearDown(self):
		nvda_harness._reset_global_plugin_imports()

	def test_helpers_wrap_exact_native_web_browse_key_sets(self):
		nvda_harness._import_classic_speech_like_nvda()
		from globalPlugins._speech_core.settings import web_formatting_config as web_config

		self.assertEqual(set(web_config.VIRTUAL_BUFFER_KEYS), set(VIRTUAL_BUFFER_SAMPLE))
		self.assertEqual(set(web_config.WEB_DOCUMENT_FORMATTING_KEYS), set(WEB_DOCUMENT_FORMATTING_SAMPLE))
		self.assertEqual(web_config.VIRTUAL_BUFFER_DEFAULTS["maxLineLength"], 100)
		self.assertEqual(web_config.VIRTUAL_BUFFER_DEFAULTS["linesPerPage"], 25)
		self.assertEqual(web_config.VIRTUAL_BUFFER_DEFAULTS["browseModeTouchNavigationElements"], [
			"heading", "link", "formField", "list", "table",
		])
		self.assertTrue(web_config.WEB_DOCUMENT_FORMATTING_DEFAULTS["reportHeadings"])
		self.assertFalse(web_config.WEB_DOCUMENT_FORMATTING_DEFAULTS["includeLayoutTables"])
		self.assertFalse(web_config.WEB_DOCUMENT_FORMATTING_DEFAULTS["reportArticles"])
		self.assertEqual(set(web_config.ANNOTATION_KEYS), set(ANNOTATIONS_SAMPLE))
		self.assertEqual(set(web_config.BRAILLE_WEB_KEYS), set(BRAILLE_WEB_SAMPLE))
		self.assertTrue(web_config.ANNOTATION_DEFAULTS["reportDetails"])
		self.assertEqual(web_config.FEATURE_FLAG_DEFAULTS["reportLiveRegions"], "DEFAULT")

	def test_helpers_read_write_and_coerce_native_buckets(self):
		nvda_harness._import_classic_speech_like_nvda()
		from globalPlugins._speech_core.settings import web_formatting_config as web_config

		self.assertEqual(web_config.get_virtual_buffer_setting("maxLineLength"), 80)
		self.assertEqual(web_config.get_virtual_buffer_setting("browseModeTouchNavigationElements"), [
			"heading", "link", "table",
		])
		self.assertTrue(web_config.get_web_document_formatting_setting("includeLayoutTables"))
		self.assertFalse(web_config.get_web_document_formatting_setting("reportClickable"))

		web_config.set_virtual_buffer_setting("maxLineLength", "120")
		web_config.set_virtual_buffer_setting("useScreenLayout", 0)
		web_config.set_virtual_buffer_setting("browseModeTouchNavigationElements", ("heading", "list"))
		web_config.set_web_document_formatting_setting("reportClickable", 1)

		self.assertEqual(config.conf["virtualBuffers"]["maxLineLength"], 120)
		self.assertFalse(config.conf["virtualBuffers"]["useScreenLayout"])
		self.assertEqual(config.conf["virtualBuffers"]["browseModeTouchNavigationElements"], ["heading", "list"])
		self.assertTrue(config.conf["documentFormatting"]["reportClickable"])
		web_config.set_annotation_setting("reportDetails", True)
		self.assertTrue(web_config.get_annotation_setting("reportDetails"))

	def test_capture_restore_supports_cancel_and_apply_semantics(self):
		nvda_harness._import_classic_speech_like_nvda()
		from globalPlugins._speech_core.settings import web_formatting_config as web_config

		snapshot = web_config.capture_web_browse_state()
		web_config.set_virtual_buffer_setting("linesPerPage", 55)
		web_config.set_web_document_formatting_setting("reportLinks", True)
		web_config.set_annotation_setting("reportDetails", True)
		config.conf["braille"]["reportLiveRegions"] = "DISABLED"
		config.conf["virtualBuffers"]["loadChromiumVBufOnBusyState"] = "DISABLED"
		self.assertEqual(config.conf["virtualBuffers"]["linesPerPage"], 55)
		self.assertTrue(config.conf["documentFormatting"]["reportLinks"])
		self.assertTrue(config.conf["annotations"]["reportDetails"])

		web_config.restore_web_browse_state(snapshot)
		self.assertEqual(config.conf["virtualBuffers"]["linesPerPage"], 40)
		self.assertFalse(config.conf["documentFormatting"]["reportLinks"])
		self.assertFalse(config.conf["annotations"]["reportDetails"])
		self.assertEqual(config.conf["braille"]["reportLiveRegions"], "DEFAULT")
		self.assertEqual(config.conf["virtualBuffers"]["loadChromiumVBufOnBusyState"], "DEFAULT")


class WebBrowseNativeFidelityTests(unittest.TestCase):
	def test_dialog_source_preserves_native_browse_mode_labels_and_controls(self):
		dialog_source = (ROOT / "_speech_core" / "settings" / "web_settings_dialog.py").read_text(encoding="utf-8")
		for expected in [
			"&Maximum number of characters on one line",
			"&Number of lines per page",
			"Use &screen layout (when supported)",
			"&Enable browse mode on page load",
			"Automatic &Say All on page load",
			"Include l&ayout tables",
			"Automatic focus mode for focus changes",
			"Automatic focus mode for caret movement",
			"Audio indication of focus and browse modes",
			"&Trap all non-command gestures from reaching the document",
			"T&ouch navigation elements:",
			"Load Chromium virtual buffer when document busy.",
			"Report 'has details' for structured annotations",
			"Report aria-description always",
			"Braille report live regions:",
		]:
			self.assertIn(expected, dialog_source)
		self.assertIn("nvdaControls.SelectOnFocusSpinCtrl", dialog_source)
		self.assertIn("nvdaControls.CustomCheckListBox", dialog_source)
		self.assertIn("nvdaControls.FeatureFlagCombo", dialog_source)
		self.assertIn("scrolledpanel.ScrolledPanel", dialog_source)
		self.assertIn("SetupScrolling(scroll_x=False)", dialog_source)
		self.assertIn('keyPath=["virtualBuffers", "loadChromiumVBufOnBusyState"]', dialog_source)
		self.assertIn('keyPath=["braille", "reportLiveRegions"]', dialog_source)
		self.assertIn("capture_web_browse_state", dialog_source)
		self.assertIn("restore_web_browse_state", dialog_source)

	def test_all_dialog_control_families_apply_and_transaction(self):
		nvda_harness._import_classic_speech_like_nvda()
		from globalPlugins._speech_core.settings.web_settings_dialog import WebBrowseSettingsDialog

		class ValueControl:
			def __init__(self, value):
				self.value = value

			def GetValue(self):
				return self.value

			def IsChecked(self):
				return bool(self.value)

		class ChoiceControl:
			def __init__(self, selection):
				self.selection = selection

			def GetSelection(self):
				return self.selection

		class CheckListControl:
			def __init__(self, checked=(0, 2)):
				self.checked = list(checked)
			def GetCheckedItems(self):
				return list(self.checked)

		class FeatureControl:
			def __init__(self, section, key, value):
				self.section = section
				self.key = key
				self.value = value
				self.saved = False

			def saveCurrentValueToConf(self):
				config.conf[self.section][self.key] = self.value
				self.saved = True

		class ApplyButton:
			def __init__(self):
				self.shown = False
				self.enabled = False

			def Show(self):
				self.shown = True

			def Hide(self):
				self.shown = False

			def Enable(self, value):
				self.enabled = bool(value)

		dialog = object.__new__(WebBrowseSettingsDialog)
		dialog.maxLengthEdit = ValueControl(120)
		dialog.pageLinesEdit = ValueControl(55)
		for attr in (
			"useScreenLayoutCheckBox",
			"enableOnPageLoadCheckBox",
			"autoSayAllCheckBox",
			"autoPassThroughOnFocusChangeCheckBox",
			"autoPassThroughOnCaretMoveCheckBox",
			"passThroughAudioIndicationCheckBox",
			"trapNonCommandGesturesCheckBox",
		):
			setattr(dialog, attr, ValueControl(False))
		dialog._browseModeElements = [("heading", "Headings"), ("link", "Links"), ("table", "Tables")]
		dialog.browseModeTouchNavigationList = CheckListControl()
		dialog.loadChromiumBusyCombo = FeatureControl(
			"virtualBuffers", "loadChromiumVBufOnBusyState", "DISABLED"
		)
		dialog.annotationDetailsCheckBox = ValueControl(True)
		dialog.ariaDescriptionCheckBox = ValueControl(False)
		web_attrs = (
			"layoutTablesCheckBox", "headingsCheckBox", "linksCheckBox", "linkTypeCheckBox",
			"graphicsCheckBox", "listsCheckBox", "blockQuotesCheckBox", "groupingsCheckBox",
			"landmarksCheckBox", "articlesCheckBox", "framesCheckBox", "figuresCheckBox",
			"clickableCheckBox",
		)
		for index, attr in enumerate(web_attrs):
			setattr(dialog, attr, ValueControl(index % 2 == 0))
		dialog.brailleLiveRegionsCombo = FeatureControl("braille", "reportLiveRegions", "ENABLED")
		from globalPlugins._speech_core.web_summary import SUMMARY_ITEM_TYPES
		dialog._pageSummaryElements = [("documentTitle", "Title")] + [
			(item.item_type, item.plural_label)
			for item in SUMMARY_ITEM_TYPES
		]
		# The initial page-load mode is native/no summary.
		dialog.pageLoadSummaryMode = ChoiceControl(0)
		dialog._pageLoadSummaryModes = ("native", "afterReady", "orientation")
		dialog.pageSummaryElementList = CheckListControl((1, 3))
		dialog._originalPageSummaryTypes = ("heading", "landmark", "link", "formField", "button", "table")
		dialog._originalPageSummaryTitle = False
		dialog._originalPageLoadSummaryMode = "native"
		dialog.applyBtn = ApplyButton()
		dialog.layoutCalls = 0
		dialog.Layout = lambda: setattr(dialog, "layoutCalls", dialog.layoutCalls + 1)
		dialog.Destroy = lambda: setattr(dialog, "destroyed", True)
		dialog.destroyed = False

		dialog._originalWebBrowse = __import__(
			"globalPlugins._speech_core.settings.web_formatting_config", fromlist=["capture_web_browse_state"]
		).capture_web_browse_state()
		dialog.onChanged()
		self.assertEqual(config.conf["virtualBuffers"]["maxLineLength"], 120)
		self.assertEqual(
			config.conf.profiles[0]["classicSpeech"]["pageSummaryData"]["includedElementTypes"],
			["annotation", "comboBox"],
		)
		self.assertEqual(
			config.conf.profiles[0]["classicSpeech"]["pageSummaryData"]["pageLoadSummaryMode"],
			"native",
		)
		self.assertEqual(config.conf["virtualBuffers"]["browseModeTouchNavigationElements"], ["heading", "table"])
		self.assertEqual(config.conf["virtualBuffers"]["loadChromiumVBufOnBusyState"], "DISABLED")
		self.assertTrue(config.conf["annotations"]["reportDetails"])
		self.assertFalse(config.conf["annotations"]["reportAriaDescription"])
		self.assertEqual(config.conf["braille"]["reportLiveRegions"], "ENABLED")
		self.assertTrue(dialog.applyBtn.shown)
		self.assertTrue(dialog.applyBtn.enabled)
		self.assertGreaterEqual(dialog.layoutCalls, 1)

		# Selecting Orientation writes through immediately and makes Apply available.
		dialog.pageLoadSummaryMode.selection = 2
		dialog.onChanged()
		self.assertEqual(
			config.conf.profiles[0]["classicSpeech"]["pageSummaryData"]["pageLoadSummaryMode"],
			"orientation",
		)

		# Apply makes the current Page Summary choices the new Cancel baseline.
		dialog.onApply(None)
		dialog.pageLoadSummaryMode.selection = 0
		dialog.pageSummaryElementList.checked = [8]
		dialog.onChanged()
		self.assertEqual(
			config.conf.profiles[0]["classicSpeech"]["pageSummaryData"]["includedElementTypes"],
			["heading"],
		)
		self.assertEqual(
			config.conf.profiles[0]["classicSpeech"]["pageSummaryData"]["pageLoadSummaryMode"],
			"native",
		)
		dialog.onCancel(None)
		self.assertTrue(dialog.destroyed)
		self.assertEqual(
			config.conf.profiles[0]["classicSpeech"]["pageSummaryData"]["includedElementTypes"],
			["annotation", "comboBox"],
		)
		self.assertEqual(
			config.conf.profiles[0]["classicSpeech"]["pageSummaryData"]["pageLoadSummaryMode"],
			"orientation",
		)
		self.assertEqual(config.conf["virtualBuffers"]["maxLineLength"], 120)
		self.assertEqual(config.conf["virtualBuffers"]["loadChromiumVBufOnBusyState"], "DISABLED")
		self.assertTrue(config.conf["annotations"]["reportDetails"])
		self.assertEqual(config.conf["braille"]["reportLiveRegions"], "ENABLED")

	def test_touch_navigation_uses_checklist_event_and_propagating_handler(self):
		dialog_source = (ROOT / "_speech_core" / "settings" / "web_settings_dialog.py").read_text(encoding="utf-8")
		self.assertIn(
			"self.browseModeTouchNavigationList.Bind(wx.EVT_CHECKLISTBOX, self.onTouchNavigationChanged)",
			dialog_source,
		)
		self.assertNotIn(
			"self.browseModeTouchNavigationList.Bind(wx.EVT_LIST_ITEM_ACTIVATED",
			dialog_source,
		)

	def test_touch_navigation_handler_propagates_and_marks_dialog_dirty(self):
		nvda_harness._import_classic_speech_like_nvda()
		from globalPlugins._speech_core.settings.web_settings_dialog import WebBrowseSettingsDialog

		dialog = object.__new__(WebBrowseSettingsDialog)
		calls = []
		dialog.onChanged = lambda evt=None: calls.append(evt)
		event = type("ChecklistEvent", (), {
			"skipped": False,
			"Skip": lambda self: setattr(self, "skipped", True),
		})()

		dialog.onTouchNavigationChanged(event)

		self.assertTrue(event.skipped)
		self.assertEqual(calls, [event])

	def test_general_document_panel_still_excludes_web_keys(self):
		nvda_harness._import_classic_speech_like_nvda()
		from globalPlugins._speech_core.settings import document_formatting_config as doc_config
		from globalPlugins._speech_core.settings import web_formatting_config as web_config

		self.assertTrue(
			set(doc_config.DOCUMENT_READING_PROOFING_KEYS).isdisjoint(web_config.WEB_DOCUMENT_FORMATTING_KEYS)
		)

	def test_classic_speech_has_preferences_submenu_entry_points(self):
		classic_speech = (ROOT / "classicSpeech.py").read_text(encoding="utf-8")
		self.assertIn("preferencesMenu", classic_speech)
		self.assertIn("ClassicSpeech", classic_speech)
		self.assertIn("General Settings...", classic_speech)
		self.assertIn("Web / Browse Mode Settings...", classic_speech)
		self.assertIn("_openWebBrowseSettings", classic_speech)
	def test_page_summary_category_uses_accessible_checklist_and_propagating_handler(self):
		dialog_source = (ROOT / "_speech_core" / "settings" / "web_settings_dialog.py").read_text(encoding="utf-8")
		self.assertIn('self._pageSummaryElements = [("documentTitle", "Title")]', dialog_source)
		self.assertIn("choices=[label for _itemType, label in self._pageSummaryElements]", dialog_source)
		self.assertIn("get_include_document_title", dialog_source)
		self.assertIn("set_include_document_title", dialog_source)
		self.assertIn('"Page-load summary:"', dialog_source)
		for choice in (
			'"NVDA native, no summary"',
			'"Summary after page is ready"',
			'"Replace initial page speech with summary"',
		):
			self.assertIn(choice, dialog_source)
		self.assertIn("self.pageLoadSummaryMode.Bind(wx.EVT_CHOICE, self.onChanged)", dialog_source)
		self.assertLess(
			dialog_source.index("self.pageLoadSummaryMode"),
			dialog_source.index('"Page Summary choices:"'),
		)
		self.assertNotIn('Shift+{item.key}', dialog_source)
		self.assertNotIn('item.key} and', dialog_source)
		for expected in (
			'"Page Summary"',
			"self.pageSummaryPanel = scrolledpanel.ScrolledPanel",
			"self.pageSummaryElementList",
			"Page Summary choices:",
			"nvdaControls.CustomCheckListBox",
			"self.pageSummaryElementList.Bind(wx.EVT_CHECKLISTBOX, self.onPageSummaryChanged)",
			"Choose the Browse Mode element types included when you press NVDA+Shift+U.",
			"get_included_element_types",
			"set_included_element_types",
			"get_page_load_summary_mode",
			"set_page_load_summary_mode",
			"_originalPageLoadSummaryMode",
		):
			self.assertIn(expected, dialog_source)

	def test_page_summary_handler_propagates_and_marks_dialog_dirty(self):
		nvda_harness._import_classic_speech_like_nvda()
		from globalPlugins._speech_core.settings.web_settings_dialog import WebBrowseSettingsDialog

		dialog = object.__new__(WebBrowseSettingsDialog)
		calls = []
		dialog.onChanged = lambda evt=None: calls.append(evt)
		event = type("ChecklistEvent", (), {
			"skipped": False,
			"Skip": lambda self: setattr(self, "skipped", True),
		})()

		dialog.onPageSummaryChanged(event)

		self.assertTrue(event.skipped)
		self.assertEqual(calls, [event])


if __name__ == "__main__":
	unittest.main()
