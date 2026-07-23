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
		dialog.notifyWhenPageReadyCheckBox = ValueControl(True)
		dialog.pageReadyMessageEdit = ValueControl("  Ready from dialog  ")
		dialog.pageLoadSummaryMode = ChoiceControl(0)
		dialog._pageLoadSummaryModes = ("native", "afterReady", "orientation")
		dialog.pageSummaryElementList = CheckListControl((1, 3))
		dialog._originalPageSummaryTypes = ("heading", "landmark", "link", "formField", "button", "table")
		dialog._originalPageSummaryTitle = False
		dialog._originalPageLoadSummaryMode = "native"
		dialog._originalNotifyWhenPageReady = False
		dialog._originalPageReadyMessage = "Page ready"
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
		self.assertTrue(config.conf.profiles[0]["classicSpeech"]["pageSummaryData"]["notifyWhenPageReady"])
		self.assertEqual(
			config.conf.profiles[0]["classicSpeech"]["pageSummaryData"]["pageReadyMessage"],
			"Ready from dialog",
		)
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
		dialog.notifyWhenPageReadyCheckBox.value = False
		dialog.pageReadyMessageEdit.value = "Changed after apply"
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
		self.assertTrue(config.conf.profiles[0]["classicSpeech"]["pageSummaryData"]["notifyWhenPageReady"])
		self.assertEqual(
			config.conf.profiles[0]["classicSpeech"]["pageSummaryData"]["pageReadyMessage"],
			"Ready from dialog",
		)

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

	def test_page_ready_controls_are_hidden_as_one_native_row_and_refresh_scrolling(self):
		dialog_source = (ROOT / "_speech_core" / "settings" / "web_settings_dialog.py").read_text(encoding="utf-8")
		self.assertIn('"Notify when page is ready"', dialog_source)
		self.assertIn('"Page ready message:"', dialog_source)
		self.assertIn("wx.TextCtrl", dialog_source)
		self.assertIn("get_notify_when_page_ready", dialog_source)
		self.assertIn("get_page_ready_message", dialog_source)
		self.assertIn("self.pageReadyMessageRow.Hide()", dialog_source)
		self.assertIn("self.pageReadyMessageRow.Show(", dialog_source)
		self.assertIn("self.pageSummaryPanel.SetupScrolling(scroll_x=False)", dialog_source)
		self.assertIn("self.pageReadyMessageEdit.Bind(wx.EVT_TEXT, self.onChanged)", dialog_source)
		self.assertIn("self.notifyWhenPageReadyCheckBox.Bind(wx.EVT_CHECKBOX, self.onPageReadyChanged)", dialog_source)
		self.assertLess(
			dialog_source.index("self.notifyWhenPageReadyCheckBox"),
			dialog_source.index('"Page-load summary:"'),
		)
		self.assertLess(
			dialog_source.index("self.pageReadyMessageRow"),
			dialog_source.index('"Page-load summary:"'),
		)

	def test_page_ready_handler_updates_visibility_then_live_applies(self):
		nvda_harness._import_classic_speech_like_nvda()
		from globalPlugins._speech_core.settings.web_settings_dialog import WebBrowseSettingsDialog

		class CheckBox:
			def IsChecked(self):
				return True

		class Row:
			def __init__(self):
				self.visible = None
			def Show(self, visible=True):
				self.visible = visible

		dialog = object.__new__(WebBrowseSettingsDialog)
		dialog.notifyWhenPageReadyCheckBox = CheckBox()
		dialog.pageReadyMessageRow = Row()
		dialog.pageSummaryPanel = type("Panel", (), {"Layout": lambda self: None, "SetupScrolling": lambda self, **kwargs: None})()
		dialog.panelHost = type("Host", (), {"Layout": lambda self: None})()
		dialog.Layout = lambda: None
		calls = []
		dialog.onChanged = lambda evt=None: calls.append(evt)

		dialog.onPageReadyChanged()

		self.assertTrue(dialog.pageReadyMessageRow.visible)
		self.assertEqual(calls, [None])

	def test_page_ready_close_restores_its_baseline(self):
		nvda_harness._import_classic_speech_like_nvda()
		from globalPlugins._speech_core.settings import web_formatting_config
		from globalPlugins._speech_core.settings import web_summary_config
		from globalPlugins._speech_core.settings.web_settings_dialog import WebBrowseSettingsDialog

		dialog = object.__new__(WebBrowseSettingsDialog)
		dialog._originalWebBrowse = web_formatting_config.capture_web_browse_state()
		dialog._originalPageSummaryTypes = web_summary_config.get_included_element_types()
		dialog._originalPageSummaryTitle = web_summary_config.get_include_document_title()
		dialog._originalPageLoadSummaryMode = web_summary_config.get_page_load_summary_mode()
		dialog._originalNotifyWhenPageReady = False
		dialog._originalPageReadyMessage = "Page ready"
		dialog._releasePopup = lambda: None
		web_summary_config.set_notify_when_page_ready(True)
		web_summary_config.set_page_ready_message("Changed before close")
		event = type("CloseEvent", (), {"skipped": False, "Skip": lambda self: setattr(self, "skipped", True)})()

		dialog.onClose(event)

		self.assertTrue(event.skipped)
		self.assertFalse(web_summary_config.get_notify_when_page_ready())
		self.assertEqual(web_summary_config.get_page_ready_message(), "Page ready")

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


class WebBrowseEdgeNotificationsIntegrationTests(unittest.TestCase):
	def setUp(self):
		nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
		nvda_harness._import_classic_speech_like_nvda()
		from globalPlugins._speech_core import plugin_config
		plugin_config._initClassicSpeechConfig()

	def tearDown(self):
		nvda_harness._reset_global_plugin_imports()

	def test_edge_category_is_permanent_fourth_scrolled_panel_wired_to_live_apply(self):
		dialog_source = (ROOT / "_speech_core" / "settings" / "web_settings_dialog.py").read_text(encoding="utf-8")
		self.assertIn("from .edge_notifications_config import (", dialog_source)
		self.assertIn("from .edge_notifications_panel import EdgeNotificationsPanel", dialog_source)
		self.assertIn('"Microsoft Edge Notifications",', dialog_source)
		self.assertLess(
			dialog_source.index('"Page Summary",'),
			dialog_source.index('"Microsoft Edge Notifications",'),
		)
		self.assertIn("self.edgeNotificationsPanel = scrolledpanel.ScrolledPanel", dialog_source)
		self.assertIn("self.edgeNotificationsEditor = EdgeNotificationsPanel(", dialog_source)
		self.assertIn("onChange=self.onChanged", dialog_source)
		self.assertIn("self.edgeNotificationsPanel.SetupScrolling(scroll_x=False)", dialog_source)
		self.assertIn(
			"self.dynamicPanels = [self.browseModePanel, self.webReportingPanel, self.pageSummaryPanel, self.edgeNotificationsPanel]",
			dialog_source,
		)
		self.assertNotIn("msedge.exe", dialog_source)

	def test_edge_apply_cancel_and_close_are_transactional_even_for_empty_values(self):
		from globalPlugins._speech_core.settings import edge_notifications_config as edge_config
		from globalPlugins._speech_core.settings import web_formatting_config
		from globalPlugins._speech_core.settings import web_summary_config
		from globalPlugins._speech_core.settings.web_settings_dialog import WebBrowseSettingsDialog

		class ValueControl:
			def __init__(self, value):
				self.value = value
			def GetValue(self):
				return self.value
			def IsChecked(self):
				return bool(self.value)

		class CheckListControl:
			def GetCheckedItems(self):
				return []

		class ChoiceControl:
			def GetSelection(self):
				return 0

		class FeatureControl:
			def saveCurrentValueToConf(self):
				pass

		class EdgePanel:
			def __init__(self, enabled_ids, messages):
				self.enabled_ids = enabled_ids
				self.messages = messages
			def getEnabledActivityIds(self):
				return self.enabled_ids
			def getCustomMessages(self):
				return self.messages

		edge_config.set_enabled_activity_ids(["PageLoading"])
		edge_config.set_custom_messages({"PageLoading": "Original"})
		dialog = object.__new__(WebBrowseSettingsDialog)
		dialog.maxLengthEdit = ValueControl(80)
		dialog.pageLinesEdit = ValueControl(40)
		for attr in (
			"useScreenLayoutCheckBox", "enableOnPageLoadCheckBox", "autoSayAllCheckBox",
			"autoPassThroughOnFocusChangeCheckBox", "autoPassThroughOnCaretMoveCheckBox",
			"passThroughAudioIndicationCheckBox", "trapNonCommandGesturesCheckBox",
			"annotationDetailsCheckBox", "ariaDescriptionCheckBox", "layoutTablesCheckBox",
			"headingsCheckBox", "linksCheckBox", "linkTypeCheckBox", "graphicsCheckBox",
			"listsCheckBox", "blockQuotesCheckBox", "groupingsCheckBox", "landmarksCheckBox",
			"articlesCheckBox", "framesCheckBox", "figuresCheckBox", "clickableCheckBox",
		):
			setattr(dialog, attr, ValueControl(False))
		dialog._browseModeElements = []
		dialog.browseModeTouchNavigationList = CheckListControl()
		dialog.loadChromiumBusyCombo = FeatureControl()
		dialog.brailleLiveRegionsCombo = FeatureControl()
		dialog.notifyWhenPageReadyCheckBox = ValueControl(False)
		dialog.pageReadyMessageEdit = ValueControl("Page ready")
		dialog.pageLoadSummaryMode = ChoiceControl()
		dialog._pageLoadSummaryModes = ("native", "afterReady", "orientation")
		dialog._pageSummaryElements = []
		dialog.pageSummaryElementList = CheckListControl()
		dialog.edgeNotificationsEditor = EdgePanel([], {})
		dialog._originalWebBrowse = web_formatting_config.capture_web_browse_state()
		dialog._originalPageSummaryTypes = web_summary_config.get_included_element_types()
		dialog._originalPageSummaryTitle = web_summary_config.get_include_document_title()
		dialog._originalPageLoadSummaryMode = web_summary_config.get_page_load_summary_mode()
		dialog._originalNotifyWhenPageReady = web_summary_config.get_notify_when_page_ready()
		dialog._originalPageReadyMessage = web_summary_config.get_page_ready_message()
		dialog._originalEdgeNotifications = edge_config.capture_edge_notification_state()
		dialog.Destroy = lambda: setattr(dialog, "destroyed", True)
		dialog._apply_to_config()
		self.assertEqual(edge_config.get_enabled_activity_ids(), ())
		self.assertEqual(edge_config.get_custom_messages(), {})

		# Apply moves the cancel baseline to the intentionally empty state.
		dialog._clearDirty = lambda: None
		dialog.onApply(None)
		dialog.edgeNotificationsEditor = EdgePanel(["PageZoom"], {"PageZoom": "Zoomed"})
		dialog._apply_to_config()
		dialog.onCancel(None)
		self.assertEqual(edge_config.get_enabled_activity_ids(), ())
		self.assertEqual(edge_config.get_custom_messages(), {})

		# Close likewise restores a captured empty baseline.
		edge_config.set_enabled_activity_ids(["PageZoom"])
		edge_config.set_custom_messages({"PageZoom": "Zoomed"})
		dialog._releasePopup = lambda: None
		event = type("CloseEvent", (), {"Skip": lambda self: None})()
		dialog.onClose(event)
		self.assertEqual(edge_config.get_enabled_activity_ids(), ())
		self.assertEqual(edge_config.get_custom_messages(), {})
	def test_edge_cancel_and_close_remove_an_unpersisted_edge_baseline(self):
		from globalPlugins._speech_core.settings import edge_notifications_config as edge_config
		from globalPlugins._speech_core.settings import web_formatting_config
		from globalPlugins._speech_core.settings import web_summary_config
		from globalPlugins._speech_core.settings.web_settings_dialog import WebBrowseSettingsDialog

		config.conf.profiles[0]["classicSpeech"] = {"unrelatedSetting": "keep me"}
		section = config.conf.profiles[0]["classicSpeech"]
		dialog = object.__new__(WebBrowseSettingsDialog)
		dialog._originalWebBrowse = web_formatting_config.capture_web_browse_state()
		dialog._originalPageSummaryTypes = web_summary_config.get_included_element_types()
		dialog._originalPageSummaryTitle = web_summary_config.get_include_document_title()
		dialog._originalPageLoadSummaryMode = web_summary_config.get_page_load_summary_mode()
		dialog._originalNotifyWhenPageReady = web_summary_config.get_notify_when_page_ready()
		dialog._originalPageReadyMessage = web_summary_config.get_page_ready_message()
		dialog._originalEdgeNotifications = edge_config.capture_edge_notification_state()
		dialog.Destroy = lambda: None

		edge_config.set_enabled_activity_ids([])
		edge_config.set_custom_messages({})
		dialog.onCancel(None)
		self.assertNotIn("edgeNotificationData", section)
		self.assertEqual(section["unrelatedSetting"], "keep me")

		edge_config.set_enabled_activity_ids(["PageZoom"])
		edge_config.set_custom_messages({"PageZoom": "Zoomed"})
		dialog._releasePopup = lambda: None
		event = type("CloseEvent", (), {"Skip": lambda self: None})()
		dialog.onClose(event)
		self.assertNotIn("edgeNotificationData", section)
		self.assertEqual(section["unrelatedSetting"], "keep me")

	def test_edge_ok_close_keeps_accepted_state_while_apply_close_restores_its_rebased_state(self):
		"""Destroy after OK raises EVT_CLOSE, unlike a normal later window close."""
		from globalPlugins._speech_core.settings import edge_notifications_config as edge_config
		from globalPlugins._speech_core.settings import web_formatting_config
		from globalPlugins._speech_core.settings import web_summary_config
		from globalPlugins._speech_core.settings.web_settings_dialog import WebBrowseSettingsDialog

		class EdgePanel:
			def __init__(self, enabled_ids, messages):
				self.enabled_ids = enabled_ids
				self.messages = messages
			def getEnabledActivityIds(self):
				return self.enabled_ids
			def getCustomMessages(self):
				return self.messages

		def make_dialog(enabled_ids, messages):
			dialog = object.__new__(WebBrowseSettingsDialog)
			dialog._originalWebBrowse = web_formatting_config.capture_web_browse_state()
			dialog._originalPageSummaryTypes = web_summary_config.get_included_element_types()
			dialog._originalPageSummaryTitle = web_summary_config.get_include_document_title()
			dialog._originalPageLoadSummaryMode = web_summary_config.get_page_load_summary_mode()
			dialog._originalNotifyWhenPageReady = web_summary_config.get_notify_when_page_ready()
			dialog._originalPageReadyMessage = web_summary_config.get_page_ready_message()
			dialog._originalEdgeNotifications = edge_config.capture_edge_notification_state()
			dialog.edgeNotificationsEditor = EdgePanel(enabled_ids, messages)
			dialog._apply_to_config = lambda: (
				edge_config.set_enabled_activity_ids(dialog.edgeNotificationsEditor.getEnabledActivityIds()),
				edge_config.set_custom_messages(dialog.edgeNotificationsEditor.getCustomMessages()),
			)
			dialog._clearDirty = lambda: None
			dialog.Destroy = lambda: setattr(dialog, "destroyed", True)
			dialog._releasePopup = lambda: None
			return dialog

		def close_event():
			return type("CloseEvent", (), {
				"skipped": False,
				"Skip": lambda self: setattr(self, "skipped", True),
			})()

		edge_config.set_enabled_activity_ids(["PageLoading"])
		edge_config.set_custom_messages({"PageLoading": "Original"})
		accepted = make_dialog(["PageZoom"], {"PageZoom": "Accepted zoom"})

		# Exercise the actual onOK -> onApply -> Destroy lifecycle, followed by
		# the EVT_CLOSE handler that Destroy causes in wx.
		accepted.onOK(None)
		self.assertIs(accepted.__dict__.get("_closeAfterOK"), True)
		accepted_close = close_event()
		accepted.onClose(accepted_close)

		self.assertTrue(accepted.destroyed)
		self.assertTrue(accepted_close.skipped)
		self.assertEqual(edge_config.get_enabled_activity_ids(), ("PageZoom",))
		self.assertEqual(edge_config.get_custom_messages(), {"PageZoom": "Accepted zoom"})

		# A caught Apply failure must not turn OK into an accepted close. The
		# ordinary close that follows must still roll back the earlier live edit.
		edge_config.set_enabled_activity_ids(["PageLoading"])
		edge_config.set_custom_messages({"PageLoading": "Original"})
		failed = make_dialog(["PageZoom"], {"PageZoom": "Live zoom"})
		failed._apply_to_config()

		def fail_apply():
			raise RuntimeError("simulated Apply failure")

		failed._apply_to_config = fail_apply
		failed.onOK(None)
		self.assertFalse(failed.__dict__.get("_closeAfterOK", False))
		self.assertFalse(failed.__dict__.get("destroyed", False))
		failed_close = close_event()
		failed.onClose(failed_close)

		self.assertTrue(failed_close.skipped)
		self.assertEqual(edge_config.get_enabled_activity_ids(), ("PageLoading",))
		self.assertEqual(edge_config.get_custom_messages(), {"PageLoading": "Original"})

		# Apply creates a new rollback baseline. A later ordinary window close
		# must still restore that baseline after further live edits.
		rebased = make_dialog(["PageLoading"], {"PageLoading": "Applied loading"})
		rebased.onApply(None)
		rebased.edgeNotificationsEditor = EdgePanel(["PageZoom"], {"PageZoom": "Later zoom"})
		rebased._apply_to_config()
		rebased_close = close_event()
		rebased.onClose(rebased_close)

		self.assertTrue(rebased_close.skipped)
		self.assertEqual(edge_config.get_enabled_activity_ids(), ("PageLoading",))
		self.assertEqual(edge_config.get_custom_messages(), {"PageLoading": "Applied loading"})


if __name__ == "__main__":
	unittest.main()
