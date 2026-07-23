"""Focused outside-NVDA tests for ClassicSpeech Edge notification configuration."""
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


class _FakeCheckList:
    """Small checklist stand-in for panel behavior tests outside wx/NVDA."""

    def __init__(self):
        self.items = []
        self.checked = []
        self.selection = -1
        self.focused = False

    def GetSelection(self):
        return self.selection

    def Clear(self):
        self.items = []
        self.checked = []

    def Append(self, text):
        self.items.append(text)

    def Check(self, index, check=True):
        while len(self.checked) <= index:
            self.checked.append(False)
        self.checked[index] = bool(check)

    def SetSelection(self, index):
        self.selection = index

    def SetFocus(self):
        self.focused = True

    def SetString(self, index, text):
        self.items[index] = text

    def IsChecked(self, index):
        return self.checked[index]


class _ChecklistEvent:
    def __init__(self, index):
        self.index = index

    def GetInt(self):
        return self.index


class _KeyEvent:
    def __init__(self, key):
        self.key = key
        self.skipped = False

    def GetKeyCode(self):
        return self.key

    def Skip(self):
        self.skipped = True


EXPECTED_ACTIVITIES = [
    ("PageLoading", "Page loading"),
    ("RefreshingPage", "Page refresh"),
    ("ClosingTab", "Close tab"),
    ("OpeningNewTab", "New tab"),
    ("OpeningWindow", "Open window"),
    ("OpeningInPrivateWindow", "Open InPrivate window"),
    ("GoingBack", "Back"),
    ("GoingForward", "Forward"),
    ("CantGoBack", "No previous page"),
    ("CantGoForward", "No next page"),
    ("HubDownloadsNewDownload", "Start download"),
    ("HubDownloadsCompleteState", "Download completed"),
    ("HubDownloadsInProgressState", "Download progress"),
    ("HubDownloadsIndeterminateProgressState", "Download progress unavailable"),
    ("ToolbarButtonRemoved", "Toolbar button removed"),
    ("SearchMode", "Search mode"),
    ("SearchModeAvailable", "Search mode available"),
    ("NotificationAppear", "General browser notification"),
    ("UpdateNotification", "Edge update"),
    ("PageZoom", "Zoom changes"),
    ("Autofill option here", "Autofill option"),
    ("AutofillSuggestionFilled", "Autofill filled"),
    ("PopupClosed", "Autofill popup closed"),
    ("AutofillSuggestionHideButton", "Hide autofill suggestion"),
    ("RemoveSuggestion", "Remove suggestion"),
    ("ContentSettingNotification", "Site permission or content setting"),
    ("ExcelAutofillSuggestionTriggered", "Excel autofill suggestion"),
]
DEFAULT_ENABLED_IDS = (
    "HubDownloadsNewDownload",
    "HubDownloadsCompleteState",
    "UpdateNotification",
    "PageZoom",
    "RemoveSuggestion",
    "ContentSettingNotification",
    "ExcelAutofillSuggestionTriggered",
)


class EdgeNotificationConfigTests(unittest.TestCase):
    def setUp(self):
        nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
        nvda_harness._import_classic_speech_like_nvda()
        from globalPlugins._speech_core import plugin_config
        from globalPlugins._speech_core.settings import edge_notifications_config

        plugin_config._initClassicSpeechConfig()
        self.edge = edge_notifications_config

    def tearDown(self):
        nvda_harness._reset_global_plugin_imports()

    def test_registry_is_unique_complete_and_in_stable_order(self):
        actual = [
            (activity.activity_id, activity.label)
            for activity in self.edge.EDGE_NOTIFICATION_ACTIVITIES
        ]
        self.assertEqual(actual, EXPECTED_ACTIVITIES)
        self.assertEqual(len(actual), 27)
        self.assertEqual(len({activity_id for activity_id, _label in actual}), 27)
        self.assertEqual(actual.count(("UpdateNotification", "Edge update")), 1)
        self.assertNotIn("ShowSuggestions", [activity_id for activity_id, _label in actual])
        self.assertEqual(self.edge.DEFAULT_ENABLED_ACTIVITY_IDS, DEFAULT_ENABLED_IDS)

    def test_spec_is_base_only_and_declares_registry_defaults_and_open_message_mapping(self):
        self.assertIn("classicSpeech", config.conf.BASE_ONLY_SECTIONS)
        spec = config.conf.spec["classicSpeech"]
        self.assertIn("edgeNotificationData", spec)
        data_spec = spec["edgeNotificationData"]
        self.assertIn("enabledActivityIds", data_spec)
        self.assertIn("HubDownloadsNewDownload", data_spec["enabledActivityIds"])
        self.assertEqual(data_spec["customMessages"], {"__many__": "string(default='')"})

    def test_enabled_ids_use_defaults_for_missing_or_malformed_data_but_preserve_empty(self):
        self.assertEqual(self.edge.get_enabled_activity_ids(), DEFAULT_ENABLED_IDS)
        section = config.conf.profiles[0]["classicSpeech"]

        malformed_values = (
            "not a list",
            {"PageZoom": True},
            ("PageZoom",),
            {"PageZoom"},
            b"PageZoom",
            iter(["PageZoom"]),
        )
        for value in malformed_values:
            with self.subTest(value=type(value).__name__):
                section["edgeNotificationData"] = {"enabledActivityIds": value}
                self.assertEqual(self.edge.get_enabled_activity_ids(), DEFAULT_ENABLED_IDS)

        section["edgeNotificationData"] = {"enabledActivityIds": []}
        self.assertEqual(self.edge.get_enabled_activity_ids(), ())

    def test_enabled_ids_drop_unknown_duplicates_and_non_strings_in_registry_order(self):
        normalized = self.edge.set_enabled_activity_ids([
            "PageZoom", "unknown", "HubDownloadsCompleteState", "PageZoom", 1,
            "UpdateNotification", None, "HubDownloadsNewDownload",
        ])
        self.assertEqual(normalized, (
            "HubDownloadsNewDownload", "HubDownloadsCompleteState", "UpdateNotification", "PageZoom",
        ))
        data = config.conf.profiles[0]["classicSpeech"]["edgeNotificationData"]
        self.assertEqual(data["enabledActivityIds"], list(normalized))

    def test_custom_messages_trim_blank_values_and_remain_independent_of_suppression(self):
        normalized = self.edge.set_custom_messages({
            "PageLoading": "  Loading page  ",
            "PageZoom": "   ",
            "unknown": "discarded",
            "ClosingTab": 1,
        })
        self.assertEqual(normalized, {"PageLoading": "Loading page"})
        self.assertEqual(self.edge.get_custom_messages(), {"PageLoading": "Loading page"})

        self.edge.set_enabled_activity_ids([])
        self.assertEqual(self.edge.get_enabled_activity_ids(), ())
        self.assertEqual(self.edge.get_custom_messages(), {"PageLoading": "Loading page"})

    def test_missing_or_malformed_custom_messages_resolve_to_an_empty_mapping(self):
        self.assertEqual(self.edge.get_custom_messages(), {})
        data = config.conf.profiles[0]["classicSpeech"]["edgeNotificationData"]
        data["customMessages"] = ["not", "a", "mapping"]
        self.assertEqual(self.edge.get_custom_messages(), {})
        self.assertEqual(self.edge.set_custom_message("PageZoom", "  Zoomed  "), "Zoomed")
        self.assertEqual(self.edge.set_custom_message("PageZoom", "  "), "")
        self.assertEqual(self.edge.get_custom_messages(), {})

    def test_snapshot_restore_isolated_for_dialog_transactions(self):
        self.edge.set_enabled_activity_ids(["PageZoom", "PageLoading"])
        self.edge.set_custom_messages({"PageLoading": "Custom loading"})
        snapshot = self.edge.capture_edge_notification_state()

        self.edge.set_enabled_activity_ids([])
        self.edge.set_custom_messages({"PageZoom": "Custom zoom"})
        self.edge.restore_edge_notification_state(snapshot)

        self.assertEqual(self.edge.get_enabled_activity_ids(), ("PageLoading", "PageZoom"))
        self.assertEqual(self.edge.get_custom_messages(), {"PageLoading": "Custom loading"})

    def test_snapshot_restore_uses_defaults_for_malformed_enabled_ids(self):
        self.edge.set_enabled_activity_ids([])
        self.edge.set_custom_messages({"PageLoading": "Custom loading"})

        self.edge.restore_edge_notification_state({
            "enabledActivityIds": "bad",
            "customMessages": {},
        })

        self.assertEqual(self.edge.get_enabled_activity_ids(), DEFAULT_ENABLED_IDS)
        self.assertEqual(self.edge.get_custom_messages(), {})


class EdgeNotificationsPanelTests(unittest.TestCase):
    def setUp(self):
        nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
        nvda_harness._import_classic_speech_like_nvda()
        from globalPlugins._speech_core.settings import edge_notifications_config
        from globalPlugins._speech_core.settings.edge_notifications_panel import EdgeNotificationsPanel
        from globalPlugins._speech_core.settings.rename_list_panel import RenameListPanel

        self.edge = edge_notifications_config
        self.EdgeNotificationsPanel = EdgeNotificationsPanel
        self.RenameListPanel = RenameListPanel

    def tearDown(self):
        nvda_harness._reset_global_plugin_imports()

    def _make_panel(self, enabled_ids=(), custom_messages=None):
        """Exercise panel logic without constructing native wx controls."""
        panel = self.EdgeNotificationsPanel.__new__(self.EdgeNotificationsPanel)
        panel._labels = [activity.activity_id for activity in self.edge.EDGE_NOTIFICATION_ACTIVITIES]
        panel._activityIds = list(panel._labels)
        panel._workingRenames = {}
        panel._workingMuted = set()
        panel._displayLabels = {
            activity.activity_id: activity.label
            for activity in self.edge.EDGE_NOTIFICATION_ACTIVITIES
        }
        panel._onChange = None
        panel._suspendEvents = False
        panel._compactDisplay = True
        panel._customDisplaySuffix = "custom message: {text}"
        panel.listCtrl = _FakeCheckList()
        panel.loadData(list(enabled_ids), custom_messages or {})
        return panel

    def test_panel_source_has_accessible_compact_edge_controls_without_legacy_status_captions(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "_speech_core" / "settings" / "edge_notifications_panel.py").read_text(encoding="utf-8")

        self.assertIn("class EdgeNotificationsPanel(RenameListPanel)", source)
        self.assertIn('title="Microsoft Edge notifications"', source)
        self.assertIn("Space: announce or suppress. F2: set a custom announcement.", source)
        self.assertIn("Delete: restore the native Edge announcement. Shift+F10: menu.", source)
        self.assertIn('renameMenuLabel="Set custom message\\tF2"', source)
        self.assertIn('clearRenameMenuLabel="Restore native message\\tDelete"', source)
        self.assertIn('checkedActionCaption="Announce"', source)
        self.assertIn('uncheckedActionCaption="Suppress"', source)
        self.assertNotIn("Announce,", source)
        self.assertNotIn("Suppress,", source)

    def test_registry_data_translates_to_compact_checked_rows_and_round_trips_normalized_ids(self):
        panel = self._make_panel(
            enabled_ids=("PageZoom", "PageLoading", "unknown", "PageZoom"),
            custom_messages={"PageLoading": "  Loading now  ", "unknown": "discard"},
        )
        page_loading = panel._labels.index("PageLoading")
        page_zoom = panel._labels.index("PageZoom")
        closing_tab = panel._labels.index("ClosingTab")

        self.assertEqual(panel.listCtrl.items[page_loading], "Page loading, custom message: Loading now")
        self.assertEqual(panel.listCtrl.items[page_zoom], "Zoom changes")
        self.assertEqual(panel.listCtrl.items[closing_tab], "Close tab")
        self.assertTrue(panel.listCtrl.checked[page_loading])
        self.assertTrue(panel.listCtrl.checked[page_zoom])
        self.assertFalse(panel.listCtrl.checked[closing_tab])
        self.assertEqual(panel.getEnabledActivityIds(), ("PageLoading", "PageZoom"))
        self.assertEqual(panel.getCustomMessages(), {"PageLoading": "Loading now"})

    def test_f2_delete_and_space_keep_custom_messages_independent_from_suppression(self):
        panel = self._make_panel(enabled_ids=(), custom_messages={})
        panel.listCtrl.SetSelection(0)
        changes = []
        panel._onChange = lambda: changes.append(True)

        prompted = []
        panel._promptForRename = lambda activity_id: prompted.append(activity_id) or True
        panel.onListKeyDown(_KeyEvent(sys.modules["wx"].WXK_F2))
        self.assertEqual(prompted, ["PageLoading"])
        self.assertFalse(panel.listCtrl.checked[0])

        panel._workingRenames["PageLoading"] = "Loading now"
        panel._refreshSingleRow(0)
        panel.onListKeyDown(_KeyEvent(sys.modules["wx"].WXK_DELETE))
        self.assertEqual(panel.getCustomMessages(), {})
        self.assertFalse(panel.listCtrl.checked[0])

        panel.listCtrl.checked[0] = True
        panel.onChecklistToggled(_ChecklistEvent(0))
        self.assertEqual(panel.getEnabledActivityIds(), ("PageLoading",))
        self.assertGreaterEqual(len(changes), 2)

    def test_default_rename_list_wording_remains_the_token_editor_wording(self):
        panel = self.RenameListPanel.__new__(self.RenameListPanel)
        panel._displayLabels = {}
        panel._workingMuted = set()
        panel._workingRenames = {"button": "btn"}
        panel._compactDisplay = False
        panel._customDisplaySuffix = "renamed to {text}"

        self.assertEqual(panel._displayTextFor("button"), "button, spoken, renamed to btn")
        panel._workingMuted.add("button")
        self.assertEqual(panel._displayTextFor("button"), "button, muted, renamed to btn")


if __name__ == "__main__":
    unittest.main()
