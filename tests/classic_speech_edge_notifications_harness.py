"""Focused outside-NVDA tests for ClassicSpeech Edge notification configuration."""
from __future__ import annotations

import copy
import importlib
import subprocess
import sys
import types
import unittest
import zipfile
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
        self.skipCount = 0

    def GetInt(self):
        return self.index

    def Skip(self):
        self.skipCount += 1


class _KeyEvent:
    def __init__(self, key):
        self.key = key
        self.skipped = False

    def GetKeyCode(self):
        return self.key

    def Skip(self):
        self.skipped = True


class _FakeTextEntryDialog:
    """Captures the real RenameListPanel prompt without creating native wx UI."""

    instances = []
    response = ""

    def __init__(self, parent, message, title, value=""):
        self.parent = parent
        self.message = message
        self.title = title
        self.value = value
        self.destroyed = False
        self.__class__.instances.append(self)

    def ShowModal(self):
        return sys.modules["wx"].ID_OK

    def GetValue(self):
        return self.__class__.response

    def Destroy(self):
        self.destroyed = True


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
        config.conf.profiles[0]["classicSpeech"] = {}
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
        config.conf.profiles[0]["classicSpeech"] = {}
        self.edge.set_custom_messages({})
        data = config.conf.profiles[0]["classicSpeech"]["edgeNotificationData"]
        data["customMessages"] = ["not", "a", "mapping"]
        self.assertEqual(self.edge.get_custom_messages(), {})
        self.assertEqual(self.edge.set_custom_message("PageZoom", "  Zoomed  "), "Zoomed")
        self.assertEqual(self.edge.set_custom_message("PageZoom", "  "), "")
        self.assertEqual(self.edge.get_custom_messages(), {})

    def test_capture_and_load_effective_defaults_do_not_create_edge_data(self):
        base_config = config.conf.profiles[0]
        base_config.pop("classicSpeech", None)
        snapshot = self.edge.capture_edge_notification_state()
        self.assertEqual(self.edge.get_enabled_activity_ids(), DEFAULT_ENABLED_IDS)
        self.assertEqual(self.edge.get_custom_messages(), {})
        self.assertEqual(snapshot["enabledActivityIds"], list(DEFAULT_ENABLED_IDS))
        self.assertEqual(snapshot["customMessages"], {})
        self.assertNotIn("classicSpeech", base_config)

        # The same no-data snapshot must remove only Edge data if an unrelated
        # ClassicSpeech setting appears before the dialog is cancelled.
        base_config["classicSpeech"] = {"unrelatedSetting": "keep me"}
        section = base_config["classicSpeech"]
        self.edge.set_enabled_activity_ids([])
        self.edge.set_custom_messages({})
        self.edge.restore_edge_notification_state(snapshot)
        self.assertNotIn("edgeNotificationData", section)
        self.assertEqual(section["unrelatedSetting"], "keep me")

    def test_snapshot_restore_preserves_existing_edge_data_exactly_including_empty_enabled_list(self):
        config.conf.profiles[0]["classicSpeech"] = {}
        section = config.conf.profiles[0]["classicSpeech"]
        expected_data = {
            "enabledActivityIds": [],
            "customMessages": {"PageLoading": "Original loading"},
            "futureSetting": {"preserve": True},
        }
        section["edgeNotificationData"] = copy.deepcopy(expected_data)
        snapshot = self.edge.capture_edge_notification_state()

        self.edge.set_enabled_activity_ids(["PageZoom"])
        self.edge.set_custom_messages({"PageZoom": "Custom zoom"})
        self.edge.restore_edge_notification_state(snapshot)

        self.assertEqual(section["edgeNotificationData"], expected_data)
        self.assertEqual(self.edge.get_enabled_activity_ids(), ())
        self.assertEqual(self.edge.get_custom_messages(), {"PageLoading": "Original loading"})

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
        panel._renamePromptTitle = "Custom notification message: {display}"
        panel._renamePromptMessage = (
            "Enter a custom notification message for '{display}'. "
            "Leave blank to restore the native Edge announcement."
        )
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
        self.assertIn('renamePromptTitle="Custom notification message: {display}"', source)
        self.assertIn("Enter a custom notification message for '{display}'.", source)
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

        wx = sys.modules["wx"]
        original_dialog = wx.TextEntryDialog
        wx.TextEntryDialog = _FakeTextEntryDialog
        self.addCleanup(setattr, wx, "TextEntryDialog", original_dialog)
        _FakeTextEntryDialog.instances = []
        _FakeTextEntryDialog.response = "  Loading now  "

        panel.onListKeyDown(_KeyEvent(wx.WXK_F2))
        self.assertEqual(len(_FakeTextEntryDialog.instances), 1)
        dialog = _FakeTextEntryDialog.instances[0]
        self.assertEqual(dialog.title, "Custom notification message: Page loading")
        self.assertEqual(
            dialog.message,
            "Enter a custom notification message for 'Page loading'. "
            "Leave blank to restore the native Edge announcement.",
        )
        self.assertTrue(dialog.destroyed)
        self.assertEqual(panel.getCustomMessages(), {"PageLoading": "Loading now"})
        self.assertFalse(panel.listCtrl.checked[0])
        self.assertEqual(panel.listCtrl.items[0], "Page loading, custom message: Loading now")
        self.assertEqual(len(changes), 1)

        panel.onListKeyDown(_KeyEvent(wx.WXK_DELETE))
        self.assertEqual(panel.getCustomMessages(), {})
        self.assertFalse(panel.listCtrl.checked[0])
        self.assertEqual(panel.listCtrl.items[0], "Page loading")
        self.assertEqual(len(changes), 2)

        panel.listCtrl.checked[0] = True
        panel.onChecklistToggled(_ChecklistEvent(0))
        self.assertEqual(panel.getEnabledActivityIds(), ("PageLoading",))
        self.assertEqual(len(changes), 3)

    def test_checklist_toggle_propagates_once_while_updating_edge_enabled_state_once(self):
        panel = self._make_panel(enabled_ids=(), custom_messages={})
        changes = []
        panel._onChange = lambda: changes.append(True)
        panel.listCtrl.checked[0] = True
        event = _ChecklistEvent(0)

        panel.onChecklistToggled(event)

        self.assertEqual(event.skipCount, 1)
        self.assertNotIn("PageLoading", panel._workingMuted)
        self.assertEqual(panel.getEnabledActivityIds(), ("PageLoading",))
        self.assertEqual(changes, [True])

    def test_every_activity_toggle_uses_deferred_native_state_and_changes_only_that_id_once(self):
        """Exercise every real checklist row through RenameListPanel's queue.

        CustomCheckListBox emits before it flips its native check state.  This
        deliberately queues the real callback for each canonical Edge ID, then
        applies the native flip before draining it.  Both directions prove a
        row cannot accidentally add/remove a neighboring activity.
        """
        wx = sys.modules["wx"]
        queued = []
        original_call_after = wx.CallAfter
        wx.CallAfter = lambda callback, *args, **kwargs: queued.append((callback, args, kwargs))
        self.addCleanup(setattr, wx, "CallAfter", original_call_after)
        all_ids = tuple(activity.activity_id for activity in self.edge.EDGE_NOTIFICATION_ACTIVITIES)

        for index, activity_id in enumerate(all_ids):
            with self.subTest(activity_id=activity_id, transition="add"):
                panel = self._make_panel(enabled_ids=(), custom_messages={})
                changes = []
                panel._onChange = lambda: changes.append(True)
                event = _ChecklistEvent(index)
                panel.onChecklistToggled(event)
                self.assertEqual(event.skipCount, 1)
                self.assertEqual(changes, [])
                self.assertEqual(len(queued), 1)
                panel.listCtrl.checked[index] = True
                callback, args, kwargs = queued.pop()
                callback(*args, **kwargs)
                self.assertEqual(panel.getEnabledActivityIds(), (activity_id,))
                self.assertEqual(changes, [True])

            with self.subTest(activity_id=activity_id, transition="remove"):
                panel = self._make_panel(enabled_ids=all_ids, custom_messages={})
                changes = []
                panel._onChange = lambda: changes.append(True)
                event = _ChecklistEvent(index)
                panel.onChecklistToggled(event)
                self.assertEqual(event.skipCount, 1)
                self.assertEqual(changes, [])
                self.assertEqual(len(queued), 1)
                panel.listCtrl.checked[index] = False
                callback, args, kwargs = queued.pop()
                callback(*args, **kwargs)
                self.assertEqual(
                    panel.getEnabledActivityIds(),
                    tuple(candidate for candidate in all_ids if candidate != activity_id),
                )
                self.assertEqual(changes, [True])

    def test_suspended_checklist_toggle_still_propagates_without_changing_state(self):
        panel = self._make_panel(enabled_ids=(), custom_messages={})
        changes = []
        panel._onChange = lambda: changes.append(True)
        panel._suspendEvents = True
        panel.listCtrl.checked[0] = True
        event = _ChecklistEvent(0)

        panel.onChecklistToggled(event)

        self.assertEqual(event.skipCount, 1)
        self.assertIn("PageLoading", panel._workingMuted)
        self.assertEqual(panel.getEnabledActivityIds(), ())
        self.assertEqual(changes, [])

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

class EdgeNotificationRuntimeTests(unittest.TestCase):
    """Exercise the root-level Edge app module with only small NVDA stubs."""
    def setUp(self):
        nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
        nvda_harness._import_classic_speech_like_nvda()
        from globalPlugins._speech_core import plugin_config
        from globalPlugins._speech_core.settings import edge_notifications_config
        plugin_config._initClassicSpeechConfig()
        self.edge = edge_notifications_config
        self.messages = []
        from globalPlugins._speech_core.settings.web_summary_config import set_notify_when_page_ready
        self.set_notify_when_page_ready = set_notify_when_page_ready
        self.set_notify_when_page_ready(False)
        app_module_handler = types.ModuleType("appModuleHandler")
        app_module_handler.AppModule = type("AppModule", (), {})
        sys.modules["appModuleHandler"] = app_module_handler
        ui = types.ModuleType("ui")
        ui.message = self.messages.append
        sys.modules["ui"] = ui
        app_modules = types.ModuleType("appModules")
        app_modules.__path__ = [str(ROOT / "appModules")]
        sys.modules["appModules"] = app_modules
        sys.modules.pop("appModules.msedge", None)
        self.module = importlib.import_module("appModules.msedge")
        self.app = self.module.AppModule()

    def tearDown(self):
        sys.modules.pop("appModules.msedge", None)
        sys.modules.pop("appModules", None)
        sys.modules.pop("appModuleHandler", None)
        nvda_harness._reset_global_plugin_imports()

    def _event(self, activity_id, **kwargs):
        native_calls = []
        self.app.event_UIA_notification(object(), lambda: native_calls.append(True), activityId=activity_id, **kwargs)
        return native_calls

    def test_signature_is_resilient_to_current_nvda_notification_arguments(self):
        self.edge.set_enabled_activity_ids(["PageZoom"])
        self.assertEqual(self._event("PageZoom", notificationKind=1, notificationProcessing=2, displayString="native", extraFutureArgument=True), [True])

    def test_unknown_none_and_non_string_ids_delegate_once_without_custom_message(self):
        self.edge.set_enabled_activity_ids([])
        self.edge.set_custom_messages({"PageZoom": "Custom zoom"})
        for activity_id in (None, "NotClassicSpeechEdgeActivity", 1, object()):
            with self.subTest(activity_id=repr(activity_id)):
                self.assertEqual(self._event(activity_id), [True])
        self.assertEqual(self.messages, [])

    def test_recognized_suppressed_event_is_swallowed_without_native_or_message(self):
        self.edge.set_enabled_activity_ids([])
        self.edge.set_custom_messages({"PageLoading": "Custom loading"})
        self.assertEqual(self._event("PageLoading"), [])
        self.assertEqual(self.messages, [])

    def test_recognized_enabled_custom_event_announces_trimmed_message_without_native(self):
        self.edge.set_enabled_activity_ids(["PageLoading"])
        self.edge.set_custom_messages({"PageLoading": "  Loading now  "})
        self.assertEqual(self._event("PageLoading"), [])
        self.assertEqual(self.messages, ["Loading now"])

    def test_recognized_enabled_native_event_delegates_once(self):
        self.edge.set_enabled_activity_ids(["PageLoading"])
        self.edge.set_custom_messages({})
        self.assertEqual(self._event("PageLoading"), [True])
        self.assertEqual(self.messages, [])

    def test_page_loading_start_is_suppressed_when_disabled(self):
        self.edge.set_enabled_activity_ids([])
        self.edge.set_custom_messages({"PageLoading": "Custom loading"})

        self.assertEqual(self._event("PageLoading", displayString=" Loading page "), [])
        self.assertEqual(self.messages, [])

    def test_page_loading_start_uses_its_custom_message_when_enabled(self):
        self.edge.set_enabled_activity_ids(["PageLoading"])
        self.edge.set_custom_messages({"PageLoading": "  Loading now  "})

        self.assertEqual(self._event("PageLoading", displayString="Loading page"), [])
        self.assertEqual(self.messages, ["Loading now"])

    def test_page_loading_complete_never_uses_the_start_custom_message(self):
        self.edge.set_enabled_activity_ids(["PageLoading"])
        self.edge.set_custom_messages({"PageLoading": "Loading now"})

        self.assertEqual(self._event("PageLoading", displayString="Loading complete"), [True])
        self.assertEqual(self.messages, [])

    def test_page_loading_complete_is_native_only_when_enabled_and_page_ready_is_disabled(self):
        cases = (
            ([], False, []),
            (["PageLoading"], False, [True]),
            (["PageLoading"], True, []),
        )
        for enabled_ids, page_ready_enabled, expected_native_calls in cases:
            with self.subTest(enabled_ids=enabled_ids, page_ready_enabled=page_ready_enabled):
                self.messages.clear()
                self.edge.set_enabled_activity_ids(enabled_ids)
                self.edge.set_custom_messages({"PageLoading": "Loading now"})
                self.set_notify_when_page_ready(page_ready_enabled)

                self.assertEqual(
                    self._event("PageLoading", displayString="Loading complete"),
                    expected_native_calls,
                )
                self.assertEqual(self.messages, [])

    def test_page_loading_complete_fails_open_when_page_ready_config_cannot_be_read(self):
        original = self.module.get_notify_when_page_ready
        self.addCleanup(setattr, self.module, "get_notify_when_page_ready", original)
        self.module.get_notify_when_page_ready = lambda: (_ for _ in ()).throw(RuntimeError("bad config"))
        self.edge.set_enabled_activity_ids(["PageLoading"])
        self.edge.set_custom_messages({"PageLoading": "Loading now"})

        self.assertEqual(self._event("PageLoading", displayString="Loading complete"), [True])
        self.assertEqual(self.messages, [])

    def test_other_page_loading_display_text_retains_the_existing_policy(self):
        self.edge.set_enabled_activity_ids(["PageLoading"])
        self.edge.set_custom_messages({"PageLoading": "Loading now"})
        self.set_notify_when_page_ready(True)

        self.assertEqual(self._event("PageLoading", displayString="Loading status changed"), [])
        self.assertEqual(self.messages, ["Loading now"])

    def test_unknown_events_are_unchanged_even_with_loading_display_text(self):
        self.edge.set_enabled_activity_ids([])
        self.edge.set_custom_messages({"PageLoading": "Loading now"})
        self.set_notify_when_page_ready(True)

        self.assertEqual(self._event("UnregisteredLoadComplete", displayString="Loading complete"), [True])
        self.assertEqual(self.messages, [])

    def test_every_canonical_activity_has_suppressed_native_and_custom_runtime_paths(self):
        """Prove all 27 registry-owned IDs take exactly the documented route."""
        for index, activity in enumerate(self.edge.EDGE_NOTIFICATION_ACTIVITIES):
            activity_id = activity.activity_id
            with self.subTest(activity_id=activity_id, configuration="suppressed"):
                self.messages.clear()
                self.edge.set_enabled_activity_ids([])
                self.edge.set_custom_messages({activity_id: f"suppressed {index}"})
                self.assertEqual(self._event(activity_id), [])
                self.assertEqual(self.messages, [])

            with self.subTest(activity_id=activity_id, configuration="enabled-native"):
                self.messages.clear()
                self.edge.set_enabled_activity_ids([activity_id])
                self.edge.set_custom_messages({})
                self.assertEqual(self._event(activity_id), [True])
                self.assertEqual(self.messages, [])

            with self.subTest(activity_id=activity_id, configuration="enabled-custom"):
                custom_message = f"Custom Edge activity {index}: {activity_id}"
                self.messages.clear()
                self.edge.set_enabled_activity_ids([activity_id])
                self.edge.set_custom_messages({activity_id: f"  {custom_message}  "})
                self.assertEqual(self._event(activity_id), [])
                self.assertEqual(self.messages, [custom_message])

    def test_runtime_configuration_is_read_again_for_each_event(self):
        self.edge.set_enabled_activity_ids([])
        self.assertEqual(self._event("PageZoom"), [])
        self.edge.set_enabled_activity_ids(["PageZoom"])
        self.edge.set_custom_messages({"PageZoom": "  Zoom changed  "})
        self.assertEqual(self._event("PageZoom"), [])
        self.assertEqual(self.messages, ["Zoom changed"])
        self.edge.set_custom_messages({})
        self.assertEqual(self._event("PageZoom"), [True])

    def test_malformed_config_access_fails_open_to_native_for_recognized_events(self):
        original = self.module.edge_notifications_config.get_enabled_activity_ids
        self.addCleanup(setattr, self.module.edge_notifications_config, "get_enabled_activity_ids", original)
        self.module.edge_notifications_config.get_enabled_activity_ids = lambda: (_ for _ in ()).throw(RuntimeError("bad config"))
        self.assertEqual(self._event("PageLoading"), [True])
        self.assertEqual(self.messages, [])

    def test_malformed_config_getter_results_fail_open_to_native_for_recognized_events(self):
        enabled_getter = self.module.edge_notifications_config.get_enabled_activity_ids
        custom_messages_getter = self.module.edge_notifications_config.get_custom_messages
        self.addCleanup(setattr, self.module.edge_notifications_config, "get_enabled_activity_ids", enabled_getter)
        self.addCleanup(setattr, self.module.edge_notifications_config, "get_custom_messages", custom_messages_getter)

        for malformed_enabled_ids in (None, "not an activity ID", object(), ("PageLoading", 1)):
            with self.subTest(enabled_ids=repr(malformed_enabled_ids)):
                self.module.edge_notifications_config.get_enabled_activity_ids = lambda value=malformed_enabled_ids: value
                self.module.edge_notifications_config.get_custom_messages = lambda: {}
                self.assertEqual(self._event("PageLoading"), [True])
                self.assertEqual(self.messages, [])

        self.module.edge_notifications_config.get_enabled_activity_ids = lambda: ("PageLoading",)
        for malformed_custom_messages in (None, "PageLoading", object()):
            with self.subTest(custom_messages=repr(malformed_custom_messages)):
                self.module.edge_notifications_config.get_custom_messages = lambda value=malformed_custom_messages: value
                self.assertEqual(self._event("PageLoading"), [True])
                self.assertEqual(self.messages, [])

    def test_unknown_enabled_id_getter_results_fail_open_to_native_for_recognized_events(self):
        enabled_getter = self.module.edge_notifications_config.get_enabled_activity_ids
        custom_messages_getter = self.module.edge_notifications_config.get_custom_messages
        self.addCleanup(setattr, self.module.edge_notifications_config, "get_enabled_activity_ids", enabled_getter)
        self.addCleanup(setattr, self.module.edge_notifications_config, "get_custom_messages", custom_messages_getter)
        self.module.edge_notifications_config.get_custom_messages = lambda: {}

        for malformed_enabled_ids in (("unknown",), ["unknown"], ("PageLoading", "unknown")):
            with self.subTest(enabled_ids=repr(malformed_enabled_ids)):
                self.module.edge_notifications_config.get_enabled_activity_ids = lambda value=malformed_enabled_ids: value
                self.assertEqual(self._event("PageLoading"), [True])
                self.assertEqual(self.messages, [])

    def test_source_stays_a_narrow_uia_notification_policy(self):
        source = (ROOT / "appModules" / "msedge.py").read_text(encoding="utf-8")
        self.assertIn("def event_UIA_notification(", source)
        self.assertIn("activityId=None", source)
        self.assertNotIn("ShowSuggestions", source)
        self.assertNotIn("comtypes", source)
        self.assertNotIn("overlay", source.lower())
        # Deliberately no HubDownloads foreground guard: no faithful outside-NVDA
        # focus/tree contract exists in this harness, so generic heuristics are unsafe.
        self.assertNotIn('"HubDownloads" in activityId', source)


class EdgeNotificationPackageTests(unittest.TestCase):
    def test_fixed_date_archive_contains_root_app_module(self):
        build_date = "2001-02-03"
        package = ROOT / "dist" / f"ClassicSpeech-{build_date}.nvda-addon"
        checksum = package.with_suffix(package.suffix + ".sha256")
        self.addCleanup(package.unlink, missing_ok=True)
        self.addCleanup(checksum.unlink, missing_ok=True)
        result = subprocess.run([sys.executable, "scripts/package_addon.py", "--date", build_date], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with zipfile.ZipFile(package) as archive:
            self.assertIn("appModules/msedge.py", archive.namelist())


if __name__ == "__main__":
    unittest.main()
