"""Focused outside-NVDA tests for the ClassicSpeech Web Summary model."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class FakeQuickNavItem:
    def __init__(self):
        self.report_calls = 0
        self.move_calls = 0

    def report(self):
        self.report_calls += 1

    def moveTo(self):
        self.move_calls += 1


class FakeBrowseDocument:
    def __init__(self, items_by_type=None, unsupported_types=(), root_name=None, is_ready=True):
        self.items_by_type = dict(items_by_type or {})
        self.unsupported_types = set(unsupported_types)
        self.iterator_calls = []
        self.focus_marker = object()
        self.cursor_marker = object()
        self.isReady = is_ready
        # NVDA replaces VirtualBuffer.VBufHandle for each buffer load. The
        # automatic reporter uses that replacement as its load-cycle marker.
        self.VBufHandle = object()
        self.rootNVDAObject = type("Root", (), {"name": root_name})()

    def _iterNodesByType(self, item_type, direction="next", pos=None):
        self.iterator_calls.append((item_type, direction, pos))
        if item_type in self.unsupported_types:
            raise NotImplementedError(item_type)
        return iter(self.items_by_type.get(item_type, ()))


class WebSummaryModelTests(unittest.TestCase):
    def setUp(self):
        from _speech_core import web_summary

        self.summary = web_summary

    def test_requested_nvda_quick_nav_keys_are_exposed_in_stable_order(self):
        expected = [
            ("annotation", "A", "Annotations"),
            ("button", "B", "Buttons"),
            ("comboBox", "C", "Combo boxes"),
            ("landmark", "D", "Landmarks"),
            ("edit", "E", "Edit fields"),
            ("formField", "F", "Form fields"),
            ("graphic", "G", "Graphics"),
            ("heading", "H", "Headings"),
            ("link", "K", "Links"),
            ("list", "L", "Lists"),
            ("frame", "M", "Frames"),
            ("embeddedObject", "O", "Embedded objects"),
            ("blockQuote", "Q", "Block quotes"),
            ("radioButton", "R", "Radio buttons"),
            ("separator", "S", "Separators"),
            ("table", "T", "Tables"),
            ("error", "W", "Errors"),
            ("checkBox", "X", "Check boxes"),
        ]
        actual = [
            (item.item_type, item.key, item.plural_label)
            for item in self.summary.SUMMARY_ITEM_TYPES
        ]
        self.assertEqual(actual, expected)

    def test_default_included_types_are_headings_landmarks_links_forms_buttons_and_tables(self):
        self.assertEqual(
            self.summary.DEFAULT_INCLUDED_ITEM_TYPES,
            ("heading", "landmark", "link", "formField", "button", "table"),
        )

    def test_unknown_or_duplicate_saved_types_are_normalized_safely(self):
        class StringLikeLink:
            def __str__(self):
                return "link"

        self.assertEqual(
            self.summary.normalize_selected_item_types(
                ["link", "unknown", "heading", "link", "table", 1],
            ),
            ("heading", "link", "table"),
        )
        self.assertEqual(self.summary.normalize_selected_item_types([StringLikeLink()]), ())
        self.assertEqual(
            self.summary.normalize_selected_item_types(None),
            self.summary.DEFAULT_INCLUDED_ITEM_TYPES,
        )
        self.assertEqual(self.summary.normalize_selected_item_types([]), ())

    def test_zero_counts_are_omitted_from_the_summary(self):
        document = FakeBrowseDocument(
            {
                "heading": [],
                "landmark": [FakeQuickNavItem(), FakeQuickNavItem()],
                "link": [FakeQuickNavItem() for _ in range(42)],
                "table": [],
            },
        )
        result = self.summary.build_summary(document, ["heading", "landmark", "link", "table"])
        self.assertEqual(result, "2 landmarks, 42 links.")

    def test_no_matching_selected_types_uses_the_explicit_empty_message(self):
        document = FakeBrowseDocument({"heading": [], "table": []})
        result = self.summary.build_summary(document, ["heading", "table"])
        self.assertEqual(result, "No selected element types found.")

    def test_summary_uses_natural_singular_and_plural_phrases(self):
        document = FakeBrowseDocument(
            {
                "table": [FakeQuickNavItem()],
                "checkBox": [FakeQuickNavItem(), FakeQuickNavItem()],
            },
        )
        result = self.summary.build_summary(document, ["table", "checkBox"])
        self.assertEqual(result, "1 table, 2 check boxes.")

    def test_unsupported_item_types_are_omitted_without_failing_the_summary(self):
        document = FakeBrowseDocument(
            {"heading": [FakeQuickNavItem()]},
            unsupported_types={"landmark"},
        )
        result = self.summary.build_summary(document, ["heading", "landmark"])
        self.assertEqual(result, "1 heading.")

    def test_counting_does_not_move_or_report_quick_navigation_items(self):
        heading = FakeQuickNavItem()
        link = FakeQuickNavItem()
        document = FakeBrowseDocument({"heading": [heading], "link": [link]})
        focus_before = document.focus_marker
        cursor_before = document.cursor_marker

        result = self.summary.build_summary(document, ["heading", "link"])

        self.assertEqual(result, "1 heading, 1 link.")
        self.assertIs(document.focus_marker, focus_before)
        self.assertIs(document.cursor_marker, cursor_before)
        self.assertEqual(heading.report_calls, 0)
        self.assertEqual(heading.move_calls, 0)
        self.assertEqual(link.report_calls, 0)
        self.assertEqual(link.move_calls, 0)
        self.assertEqual(
            document.iterator_calls,
            [("heading", "next", None), ("link", "next", None)],
        )


class WebSummaryConfigTests(unittest.TestCase):
    def setUp(self):
        import classic_speech_nvda_master_harness as nvda_harness

        self.nvda_harness = nvda_harness
        nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
        nvda_harness._import_classic_speech_like_nvda()
        import config
        from globalPlugins._speech_core import plugin_config
        from globalPlugins._speech_core.settings import web_summary_config

        plugin_config._initClassicSpeechConfig()
        self.config = config
        self.summary_config = web_summary_config
        self.summary_config.get_included_element_types()

    def tearDown(self):
        self.nvda_harness._reset_global_plugin_imports()

    def test_page_summary_defaults_are_registered_in_classic_speech_config(self):
        spec = self.config.conf.spec["classicSpeech"]
        self.assertIn("pageSummaryData", spec)
        self.assertIn("includedElementTypes", spec["pageSummaryData"])
        self.assertEqual(
            spec["pageSummaryData"]["includeDocumentTitle"],
            "boolean(default=False)",
        )
        self.assertIn("automaticReportOnPageLoad", spec["pageSummaryData"])
        self.assertEqual(
            spec["pageSummaryData"]["automaticReportOnPageLoad"],
            "boolean(default=False)",
        )
        self.assertEqual(
            spec["pageSummaryData"]["notifyWhenPageReady"],
            "boolean(default=False)",
        )
        self.assertEqual(
            spec["pageSummaryData"]["pageReadyMessage"],
            "string(default='Page ready')",
        )
        self.assertFalse(self.summary_config.get_automatic_reporting_enabled())
        self.assertEqual(
            self.summary_config.get_included_element_types(),
            ("heading", "landmark", "link", "formField", "button", "table"),
        )

    def test_saved_choices_round_trip_in_stable_registry_order(self):
        self.summary_config.set_included_element_types(["table", "heading", "link"])
        self.assertEqual(
            self.summary_config.get_included_element_types(),
            ("heading", "link", "table"),
        )
        section = self.config.conf.profiles[0]["classicSpeech"]
        self.assertEqual(
            section["pageSummaryData"]["includedElementTypes"],
            ["heading", "link", "table"],
        )

    def test_title_option_is_configured_and_uses_natural_no_prefix_formatting(self):
        self.assertFalse(self.summary_config.get_include_document_title())
        self.assertTrue(self.summary_config.set_include_document_title(" true "))
        self.assertTrue(self.summary_config.get_include_document_title())
        self.assertFalse(self.summary_config.set_include_document_title("unexpected"))
        from _speech_core.web_summary import format_summary_with_document_title
        self.assertEqual(
            format_summary_with_document_title("  Example\npage  ", "1 heading."),
            "Example page. 1 heading.",
        )
        self.assertEqual(
            format_summary_with_document_title("", "1 heading."),
            "1 heading.",
        )


    def test_automatic_reporting_parses_only_explicit_boolean_values(self):
        self.config.conf.profiles[0]["classicSpeech"] = {"pageSummaryData": {}}
        section = self.config.conf.profiles[0]["classicSpeech"]
        data = section["pageSummaryData"]
        for saved_value, expected in (
            (True, True),
            (False, False),
            ("False", False),
            ("True", True),
            (" false ", False),
            (" true ", True),
            ("unexpected", False),
            (1, False),
            (None, False),
        ):
            data["automaticReportOnPageLoad"] = saved_value
            self.assertIs(self.summary_config.get_automatic_reporting_enabled(), expected)

    def test_automatic_reporting_setter_fails_closed_and_persists_normalized_boolean(self):
        self.config.conf.profiles[0]["classicSpeech"] = {"pageSummaryData": {}}
        section = self.config.conf.profiles[0]["classicSpeech"]
        data = section["pageSummaryData"]

        self.assertTrue(self.summary_config.set_automatic_reporting_enabled(" true "))
        self.assertIs(data["automaticReportOnPageLoad"], True)
        self.assertTrue(self.summary_config.get_automatic_reporting_enabled())

        for invalid_value in ("unexpected", 1, object(), None):
            self.assertFalse(self.summary_config.set_automatic_reporting_enabled(invalid_value))
            self.assertIs(data["automaticReportOnPageLoad"], False)
            self.assertFalse(self.summary_config.get_automatic_reporting_enabled())

    def test_page_ready_notification_defaults_are_off_with_the_default_message(self):
        self.assertFalse(self.summary_config.get_notify_when_page_ready())
        self.assertEqual(self.summary_config.get_page_ready_message(), "Page ready")

    def test_page_ready_notification_stored_values_are_normalized_and_trimmed(self):
        self.config.conf.profiles[0]["classicSpeech"] = {"pageSummaryData": {}}
        data = self.config.conf.profiles[0]["classicSpeech"]["pageSummaryData"]
        data.update(
            {
                "notifyWhenPageReady": " true ",
                "pageReadyMessage": "  Finished loading  ",
            }
        )

        self.assertTrue(self.summary_config.get_notify_when_page_ready())
        self.assertEqual(self.summary_config.get_page_ready_message(), "Finished loading")

    def test_page_ready_notification_malformed_values_fail_safe_and_blank_messages_use_defaults(self):
        self.config.conf.profiles[0]["classicSpeech"] = {"pageSummaryData": {}}
        data = self.config.conf.profiles[0]["classicSpeech"]["pageSummaryData"]
        for saved_value in ("unexpected", 1, None, object()):
            data["notifyWhenPageReady"] = saved_value
            self.assertFalse(self.summary_config.get_notify_when_page_ready())
        for saved_value in (None, 1, "  "):
            data["pageReadyMessage"] = saved_value
            self.assertEqual(self.summary_config.get_page_ready_message(), "Page ready")

    def test_page_ready_notification_setters_persist_independently(self):
        self.config.conf.profiles[0]["classicSpeech"] = {"pageSummaryData": {}}
        data = self.config.conf.profiles[0]["classicSpeech"]["pageSummaryData"]
        self.assertTrue(self.summary_config.set_notify_when_page_ready(" true "))
        self.assertEqual(self.summary_config.set_page_ready_message("  Ready custom  "), "Ready custom")
        self.assertEqual(data["notifyWhenPageReady"], True)
        self.assertEqual(data["pageReadyMessage"], "Ready custom")

        self.assertFalse(self.summary_config.set_notify_when_page_ready(None))
        self.assertEqual(data["pageReadyMessage"], "Ready custom")

    def test_invalid_saved_choices_are_dropped_without_losing_valid_choices(self):
        self.config.conf.profiles[0]["classicSpeech"] = {}
        section = self.config.conf.profiles[0]["classicSpeech"]
        section["pageSummaryData"] = {"includedElementTypes": ["unknown", "link", "link", 1]}
        self.assertEqual(self.summary_config.get_included_element_types(), ("link",))

    def test_empty_saved_list_is_preserved_as_an_intentional_no_elements_choice(self):
        self.summary_config.set_included_element_types([])
        self.assertEqual(self.summary_config.get_included_element_types(), ())
        section = self.config.conf.profiles[0]["classicSpeech"]
        self.assertEqual(section["pageSummaryData"]["includedElementTypes"], [])

    def test_page_entry_summary_delay_defaults_to_two_seconds_and_normalizes_zero_to_five(self):
        self.assertEqual(self.summary_config.get_page_entry_summary_delay_seconds(), 2)
        self.config.conf.profiles[0]["classicSpeech"] = {"pageSummaryData": {}}
        data = self.config.conf.profiles[0]["classicSpeech"]["pageSummaryData"]
        for saved_value, expected in (
            (0, 0),
            (5, 5),
            ("3", 3),
            (" 4 ", 4),
            (-1, 2),
            (6, 2),
            (True, 2),
            ("unexpected", 2),
            (None, 2),
        ):
            data["pageEntrySummaryDelaySeconds"] = saved_value
            self.assertEqual(self.summary_config.get_page_entry_summary_delay_seconds(), expected)
        self.assertEqual(self.summary_config.set_page_entry_summary_delay_seconds(" 1 "), 1)
        self.assertEqual(data["pageEntrySummaryDelaySeconds"], 1)
        self.assertEqual(self.summary_config.set_page_entry_summary_delay_seconds(99), 2)
        self.assertEqual(data["pageEntrySummaryDelaySeconds"], 2)


class WebSummaryCommandTests(unittest.TestCase):
    def setUp(self):
        import classic_speech_nvda_master_harness as nvda_harness
        self.nvda_harness = nvda_harness
        nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
        self.module = nvda_harness._import_classic_speech_like_nvda()
        import api
        import ui
        from globalPlugins._speech_core.settings.web_summary_config import set_included_element_types
        self.api = api
        self.ui = ui
        self.ui.messages.clear()
        set_included_element_types(["heading", "link"])

    def tearDown(self):
        self.nvda_harness._reset_global_plugin_imports()

    def test_page_summary_has_default_gesture_and_classicspeech_input_gestures_category(self):
        gestures = self.module.GlobalPlugin._GlobalPlugin__gestures
        self.assertEqual(gestures["kb:NVDA+Shift+U"], "pageSummary")
        source = (ROOT / "classicSpeech.py").read_text(encoding="utf-8")
        before_script = source.split("def script_pageSummary", 1)[0]
        decorator_block = before_script.rsplit("@scriptHandler.script(", 1)[1]
        self.assertIn('description="Reports selected Browse Mode element counts for the current page"', decorator_block)
        self.assertIn('category="ClassicSpeech"', decorator_block)

    def test_page_summary_speaks_selected_counts_without_moving_items_or_focus(self):
        heading = FakeQuickNavItem()
        link = FakeQuickNavItem()
        document = FakeBrowseDocument({"heading": [heading], "link": [link, FakeQuickNavItem()]})
        focus = type("Focus", (), {"treeInterceptor": document})()
        self.api.getFocusObject = lambda: focus
        plugin = object.__new__(self.module.GlobalPlugin)

        plugin.script_pageSummary(None)

        self.assertEqual(self.ui.messages, ["1 heading, 2 links."])
        self.assertEqual(heading.report_calls, 0)
        self.assertEqual(heading.move_calls, 0)
        self.assertEqual(link.report_calls, 0)
        self.assertEqual(link.move_calls, 0)
        self.assertIs(self.api.getFocusObject(), focus)


    def test_page_summary_is_count_only_even_when_the_document_has_a_title(self):
        document = FakeBrowseDocument(
            {"heading": [FakeQuickNavItem()], "link": [FakeQuickNavItem()]},
            root_name="ClassicSpeech documentation",
        )
        self.api.getFocusObject = lambda: type("Focus", (), {"treeInterceptor": document})()
        plugin = object.__new__(self.module.GlobalPlugin)

        plugin.script_pageSummary(None)

        self.assertEqual(self.ui.messages, ["1 heading, 1 link."])

    def test_page_summary_reports_unavailable_outside_browse_mode(self):
        self.api.getFocusObject = lambda: object()
        plugin = object.__new__(self.module.GlobalPlugin)

        import speech.extensions
        callbacks_before = list(speech.extensions.filter_speechSequence.callbacks)
        plugin.script_pageSummary(None)

        self.assertEqual(speech.extensions.filter_speechSequence.callbacks, callbacks_before)
        self.assertEqual(self.ui.messages, ["Page summary is not available here."])


class _ControlledLater:
    def __init__(self, delay, callback, *args, **kwargs):
        self.delay = delay
        self.callback = callback
        self.args = args
        self.kwargs = kwargs
        self.stopped = False

    def Stop(self):
        self.stopped = True

    def run(self):
        if not self.stopped:
            self.callback(*self.args, **self.kwargs)


class AutomaticWebSummaryRuntimeTests(unittest.TestCase):
    """Focused event-loop tests for the opt-in, ready-only runtime path."""

    def setUp(self):
        import classic_speech_nvda_master_harness as nvda_harness

        self.nvda_harness = nvda_harness
        nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
        self.module = nvda_harness._import_classic_speech_like_nvda()
        import api
        import speech.extensions
        import ui
        from globalPlugins._speech_core.settings.web_summary_config import (
            set_automatic_reporting_enabled,
            set_included_element_types,
            set_notify_when_page_ready,
            set_page_ready_message,
            set_page_orientation_enabled,
            set_page_entry_summary_delay_seconds,
        )

        self.api = api
        self.ui = ui
        self.speech_extensions = speech.extensions
        self.ui.messages.clear()
        self.laters = []
        self.original_call_later = self.module.wx.CallLater
        self.module.wx.CallLater = self._call_later
        set_automatic_reporting_enabled(False)
        set_page_orientation_enabled(False)
        set_page_entry_summary_delay_seconds(0)
        set_notify_when_page_ready(False)
        set_page_ready_message("Page ready")
        set_included_element_types(["heading", "link"])

    def tearDown(self):
        self.module.wx.CallLater = self.original_call_later
        self.nvda_harness._reset_global_plugin_imports()

    def _call_later(self, delay, callback, *args, **kwargs):
        later = _ControlledLater(delay, callback, *args, **kwargs)
        self.laters.append(later)
        return later

    def _start_event(self, document):
        focus = type("Focus", (), {"treeInterceptor": document})()
        target = type("DocumentTarget", (), {"treeInterceptor": document})()
        self.api.getFocusObject = lambda: focus
        plugin = object.__new__(self.module.GlobalPlugin)
        next_calls = []
        plugin.event_documentLoadComplete(target, lambda: next_calls.append("native"))
        self.assertEqual(next_calls, ["native"])
        return plugin, focus, target

    def test_disabled_auto_reporting_only_preserves_native_load_handling(self):
        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]})
        plugin, _focus, _target = self._start_event(document)

        self.assertEqual(self.laters, [])
        self.assertEqual(self.ui.messages, [])
        self.assertFalse(getattr(plugin, "_automaticSummaryPending", {}))

    def test_ready_default_disabled_in_native_summary_mode_preserves_native_load_handling(self):
        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]})
        plugin, _focus, _target = self._start_event(document)

        self.assertEqual(self.laters, [])
        self.assertEqual(self.ui.messages, [])
        self.assertFalse(getattr(plugin, "_automaticSummaryPending", {}))

    def test_ready_only_native_mode_speaks_the_normalized_custom_message_once(self):
        from globalPlugins._speech_core.settings.web_summary_config import (
            set_notify_when_page_ready,
            set_page_ready_message,
        )

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]})
        set_notify_when_page_ready(True)
        self.assertEqual(set_page_ready_message("  Finished loading  "), "Finished loading")
        _plugin, _focus, _target = self._start_event(document)

        self.assertEqual(len(self.laters), 1)
        self.laters.pop(0).run()
        self.assertEqual(self.ui.messages, ["Finished loading"])

    def test_configured_settling_delay_defers_summary_build_until_after_readiness(self):
        from globalPlugins._speech_core.settings.web_summary_config import (
            set_automatic_reporting_enabled,
            set_page_entry_summary_delay_seconds,
        )

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]})
        set_automatic_reporting_enabled(True)
        set_page_entry_summary_delay_seconds(2)
        _plugin, _focus, _target = self._start_event(document)

        self.assertEqual([later.delay for later in self.laters], [50])
        self.laters.pop(0).run()
        self.assertEqual(self.ui.messages, [])
        self.assertEqual([later.delay for later in self.laters], [2000])
        self.laters.pop(0).run()
        self.assertEqual(self.ui.messages, ["1 heading."])


    def test_ready_message_precedes_automatic_summary_for_the_same_ready_cycle(self):
        from globalPlugins._speech_core.settings.web_summary_config import (
            set_automatic_reporting_enabled,
            set_notify_when_page_ready,
        )

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]})
        set_automatic_reporting_enabled(True)
        set_notify_when_page_ready(True)
        _plugin, _focus, _target = self._start_event(document)

        self.laters.pop(0).run()
        self.assertEqual(self.ui.messages, ["Page ready", "1 heading."])

    def test_ready_message_precedes_page_orientation_summary_without_a_duplicate_callback(self):
        from globalPlugins._speech_core.settings.web_summary_config import (
            set_notify_when_page_ready,
            set_page_orientation_enabled,
        )

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]})
        focus = type("Focus", (), {"treeInterceptor": document})()
        target = type("DocumentTarget", (), {"treeInterceptor": document})()
        self.api.getFocusObject = lambda: focus
        set_page_orientation_enabled(True)
        set_notify_when_page_ready(True)
        plugin = object.__new__(self.module.GlobalPlugin)

        self.assertTrue(plugin._report_page_orientation_for_document(document))
        self.assertEqual(self.ui.messages, ["Page ready", "1 heading."])
        plugin.event_documentLoadComplete(target, lambda: None)
        self.assertEqual(self.laters, [])
        self.assertEqual(self.ui.messages, ["Page ready", "1 heading."])

    def test_orientation_mode_owns_ready_presentation_even_when_document_load_completes_first(self):
        from globalPlugins._speech_core.settings.web_summary_config import (
            set_notify_when_page_ready,
            set_page_orientation_enabled,
        )

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]})
        focus = type("Focus", (), {"treeInterceptor": document})()
        target = type("DocumentTarget", (), {"treeInterceptor": document})()
        self.api.getFocusObject = lambda: focus
        set_page_orientation_enabled(True)
        set_notify_when_page_ready(True)
        plugin = object.__new__(self.module.GlobalPlugin)

        plugin.event_documentLoadComplete(target, lambda: None)
        self.assertEqual(self.laters, [])
        self.assertEqual(self.ui.messages, [])
        self.assertTrue(plugin._report_page_orientation_for_document(document))
        self.assertEqual(self.ui.messages, ["Page ready", "1 heading."])

    def test_loading_ready_only_document_never_speaks_early_then_reports_once_when_ready(self):
        from globalPlugins._speech_core.settings.web_summary_config import set_notify_when_page_ready

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]}, is_ready=False)
        set_notify_when_page_ready(True)
        _plugin, _focus, _target = self._start_event(document)

        self.laters.pop(0).run()
        self.assertEqual(self.ui.messages, [])
        self.assertEqual(len(self.laters), 1)
        document.isReady = True
        self.laters.pop(0).run()
        self.assertEqual(self.ui.messages, ["Page ready"])

    def test_replaced_buffer_handle_during_pending_ready_retry_is_discarded(self):
        from globalPlugins._speech_core.settings.web_summary_config import set_notify_when_page_ready

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]}, is_ready=False)
        set_notify_when_page_ready(True)
        _plugin, _focus, _target = self._start_event(document)

        self.laters.pop(0).run()
        self.assertEqual(len(self.laters), 1)
        document.VBufHandle = object()
        document.isReady = True
        self.laters.pop(0).run()

        self.assertEqual(self.ui.messages, [])
        self.assertEqual(self.laters, [])

    def test_initially_unavailable_buffer_handle_can_report_when_it_arrives(self):
        from globalPlugins._speech_core.settings.web_summary_config import set_notify_when_page_ready

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]}, is_ready=False)
        document.VBufHandle = None
        set_notify_when_page_ready(True)
        _plugin, _focus, _target = self._start_event(document)

        self.laters.pop(0).run()
        self.assertEqual(len(self.laters), 1)
        document.VBufHandle = object()
        document.isReady = True
        self.laters.pop(0).run()

        self.assertEqual(self.ui.messages, ["Page ready"])
        self.assertEqual(self.laters, [])

    def test_repeated_load_events_dedupe_ready_only_notifications(self):
        from globalPlugins._speech_core.settings.web_summary_config import set_notify_when_page_ready

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]})
        set_notify_when_page_ready(True)
        plugin, _focus, target = self._start_event(document)
        plugin.event_documentLoadComplete(target, lambda: None)
        self.assertEqual(len(self.laters), 1)

        self.laters.pop(0).run()
        plugin.event_documentLoadComplete(target, lambda: None)
        self.assertEqual(self.ui.messages, ["Page ready"])
        self.assertEqual(self.laters, [])

    def test_disabling_ready_after_schedule_preserves_enabled_summary(self):
        from globalPlugins._speech_core.settings.web_summary_config import (
            set_automatic_reporting_enabled,
            set_notify_when_page_ready,
        )

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]})
        set_automatic_reporting_enabled(True)
        set_notify_when_page_ready(True)
        _plugin, _focus, _target = self._start_event(document)
        set_notify_when_page_ready(False)
        self.laters.pop(0).run()

        self.assertEqual(self.ui.messages, ["1 heading."])

    def test_disabling_summary_after_schedule_preserves_enabled_ready_notification(self):
        from globalPlugins._speech_core.settings.web_summary_config import (
            set_automatic_reporting_enabled,
            set_notify_when_page_ready,
        )

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]})
        set_automatic_reporting_enabled(True)
        set_notify_when_page_ready(True)
        _plugin, _focus, _target = self._start_event(document)
        set_automatic_reporting_enabled(False)
        self.laters.pop(0).run()

        self.assertEqual(self.ui.messages, ["Page ready"])

    def test_next_handler_runs_first_before_ready_setting_is_observed(self):
        from globalPlugins._speech_core.settings.web_summary_config import set_notify_when_page_ready

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]})
        focus = type("Focus", (), {"treeInterceptor": document})()
        target = type("DocumentTarget", (), {"treeInterceptor": document})()
        self.api.getFocusObject = lambda: focus
        plugin = object.__new__(self.module.GlobalPlugin)
        set_notify_when_page_ready(False)
        plugin.event_documentLoadComplete(target, lambda: set_notify_when_page_ready(True))

        self.assertEqual(len(self.laters), 1)

    def test_ready_current_document_reports_once_with_one_native_message_and_no_mutation(self):
        from globalPlugins._speech_core.settings.web_summary_config import set_automatic_reporting_enabled

        heading = FakeQuickNavItem()
        link = FakeQuickNavItem()
        document = FakeBrowseDocument({"heading": [heading], "link": [link, FakeQuickNavItem()]})
        set_automatic_reporting_enabled(True)
        callbacks_before = list(self.speech_extensions.filter_speechSequence.callbacks)
        plugin, focus, _target = self._start_event(document)
        focus_before = document.focus_marker
        cursor_before = document.cursor_marker

        self.assertEqual(len(self.laters), 1)
        self.laters.pop(0).run()

        self.assertEqual(self.ui.messages, ["1 heading, 2 links."])
        self.assertIs(self.api.getFocusObject(), focus)
        self.assertIs(document.focus_marker, focus_before)
        self.assertIs(document.cursor_marker, cursor_before)
        self.assertEqual(heading.report_calls, 0)
        self.assertEqual(heading.move_calls, 0)
        self.assertEqual(link.report_calls, 0)
        self.assertEqual(link.move_calls, 0)
        self.assertEqual(self.speech_extensions.filter_speechSequence.callbacks, callbacks_before)
        self.assertIsNone(getattr(plugin, "_automaticSummaryPending", None))

    def test_loading_document_never_speaks_early_then_reports_once_when_ready(self):
        from globalPlugins._speech_core.settings.web_summary_config import set_automatic_reporting_enabled

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]}, is_ready=False)
        set_automatic_reporting_enabled(True)
        _plugin, _focus, _target = self._start_event(document)

        self.laters.pop(0).run()
        self.assertEqual(self.ui.messages, [])
        self.assertEqual(len(self.laters), 1)
        document.isReady = True
        self.laters.pop(0).run()

        self.assertEqual(self.ui.messages, ["1 heading."])
        self.assertEqual(self.laters, [])

    def test_focus_change_discards_pending_work_silently(self):
        from globalPlugins._speech_core.settings.web_summary_config import set_automatic_reporting_enabled

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]})
        set_automatic_reporting_enabled(True)
        _plugin, _focus, _target = self._start_event(document)
        self.api.getFocusObject = lambda: type("Focus", (), {"treeInterceptor": FakeBrowseDocument()})()

        self.laters.pop(0).run()

        self.assertEqual(self.ui.messages, [])
        self.assertEqual(self.laters, [])

    def test_focus_change_discards_pending_ready_notification_silently(self):
        from globalPlugins._speech_core.settings.web_summary_config import set_notify_when_page_ready

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]})
        set_notify_when_page_ready(True)
        _plugin, _focus, _target = self._start_event(document)
        self.api.getFocusObject = lambda: type("Focus", (), {"treeInterceptor": FakeBrowseDocument()})()

        self.laters.pop(0).run()
        self.assertEqual(self.ui.messages, [])
        self.assertEqual(self.laters, [])

    def test_focus_leaving_pending_document_stops_and_clears_callback_before_it_runs(self):
        from globalPlugins._speech_core.settings.web_summary_config import set_automatic_reporting_enabled

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]})
        set_automatic_reporting_enabled(True)
        plugin, _focus, _target = self._start_event(document)
        pending = self.laters[0]
        next_calls = []
        other_document_focus = type("Focus", (), {"treeInterceptor": FakeBrowseDocument()})()

        plugin.event_gainFocus(other_document_focus, lambda: next_calls.append("native"))

        self.assertEqual(next_calls, ["native"])
        self.assertTrue(pending.stopped)
        self.assertIsNone(getattr(plugin, "_automaticSummaryPending", None))
        pending.run()
        self.assertEqual(self.ui.messages, [])

    def test_non_browse_focus_immediately_cancels_pending_callback(self):
        from globalPlugins._speech_core.settings.web_summary_config import set_automatic_reporting_enabled

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]})
        set_automatic_reporting_enabled(True)
        plugin, _focus, _target = self._start_event(document)
        pending = self.laters[0]
        next_calls = []

        plugin.event_gainFocus(object(), lambda: next_calls.append("native"))

        self.assertEqual(next_calls, ["native"])
        self.assertTrue(pending.stopped)
        self.assertIsNone(getattr(plugin, "_automaticSummaryPending", None))
        pending.run()
        self.assertEqual(self.ui.messages, [])

    def test_focus_within_pending_document_preserves_callback(self):
        from globalPlugins._speech_core.settings.web_summary_config import set_automatic_reporting_enabled

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]})
        set_automatic_reporting_enabled(True)
        plugin, _focus, _target = self._start_event(document)
        pending = self.laters[0]
        next_calls = []
        same_document_focus = type("Focus", (), {"treeInterceptor": document})()

        plugin.event_gainFocus(same_document_focus, lambda: next_calls.append("native"))

        self.assertEqual(next_calls, ["native"])
        self.assertFalse(pending.stopped)
        self.assertIs(getattr(plugin, "_automaticSummaryPending", None)[0], document)
        pending.run()
        self.assertEqual(self.ui.messages, ["1 heading."])

    def test_repeated_document_load_events_dedupe_pending_and_reported_cycles(self):
        from globalPlugins._speech_core.settings.web_summary_config import set_automatic_reporting_enabled

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]})
        set_automatic_reporting_enabled(True)
        plugin, _focus, target = self._start_event(document)
        plugin.event_documentLoadComplete(target, lambda: None)
        self.assertEqual(len(self.laters), 1)

        self.laters.pop(0).run()
        plugin.event_documentLoadComplete(target, lambda: None)

        self.assertEqual(self.ui.messages, ["1 heading."])
        self.assertEqual(self.laters, [])

    def test_reused_tree_interceptor_reports_again_for_a_new_buffer_load_cycle(self):
        from globalPlugins._speech_core.settings.web_summary_config import set_automatic_reporting_enabled

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]})
        set_automatic_reporting_enabled(True)
        plugin, _focus, target = self._start_event(document)
        self.laters.pop(0).run()

        # NVDA's VirtualBuffer keeps its Python identity across a refresh but
        # replaces VBufHandle when loadBuffer creates the refreshed buffer.
        document.VBufHandle = object()
        plugin.event_documentLoadComplete(target, lambda: None)
        self.assertEqual(len(self.laters), 1)
        self.laters.pop(0).run()

        self.assertEqual(self.ui.messages, ["1 heading.", "1 heading."])

    def test_next_handler_runs_before_automatic_setting_is_observed(self):
        from globalPlugins._speech_core.settings.web_summary_config import set_automatic_reporting_enabled

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]})
        focus = type("Focus", (), {"treeInterceptor": document})()
        target = type("DocumentTarget", (), {"treeInterceptor": document})()
        self.api.getFocusObject = lambda: focus
        plugin = object.__new__(self.module.GlobalPlugin)
        set_automatic_reporting_enabled(False)
        plugin.event_documentLoadComplete(target, lambda: set_automatic_reporting_enabled(True))

        self.assertEqual(len(self.laters), 1)

    def test_disabling_after_schedule_discards_callback_and_cleans_pending_state(self):
        from globalPlugins._speech_core.settings.web_summary_config import set_automatic_reporting_enabled

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]})
        set_automatic_reporting_enabled(True)
        plugin, _focus, _target = self._start_event(document)
        set_automatic_reporting_enabled(False)
        self.laters.pop(0).run()

        self.assertEqual(self.ui.messages, [])
        self.assertIsNone(getattr(plugin, "_automaticSummaryPending", None))

    def test_retry_exhaustion_discards_state_without_speaking(self):
        from globalPlugins._speech_core.settings.web_summary_config import set_automatic_reporting_enabled

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]}, is_ready=False)
        set_automatic_reporting_enabled(True)
        plugin, _focus, _target = self._start_event(document)
        while self.laters:
            self.laters.pop(0).run()

        self.assertEqual(self.ui.messages, [])
        self.assertIsNone(getattr(plugin, "_automaticSummaryPending", None))

    def test_unsupported_callback_document_is_discarded_silently(self):
        from globalPlugins._speech_core.settings.web_summary_config import set_automatic_reporting_enabled

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]})
        set_automatic_reporting_enabled(True)
        plugin, _focus, _target = self._start_event(document)
        document._iterNodesByType = None
        self.laters.pop(0).run()

        self.assertEqual(self.ui.messages, [])
        self.assertIsNone(getattr(plugin, "_automaticSummaryPending", None))

    def test_new_current_document_stops_old_callback_and_reports_only_current_document(self):
        from globalPlugins._speech_core.settings.web_summary_config import set_automatic_reporting_enabled

        old_document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]}, is_ready=False)
        current_document = FakeBrowseDocument({"link": [FakeQuickNavItem()]})
        set_automatic_reporting_enabled(True)
        plugin, focus, _target = self._start_event(old_document)
        old_later = self.laters[0]

        focus.treeInterceptor = current_document
        current_target = type("DocumentTarget", (), {"treeInterceptor": current_document})()
        plugin.event_documentLoadComplete(current_target, lambda: None)

        self.assertTrue(old_later.stopped)
        self.assertIs(getattr(plugin, "_automaticSummaryPending", None)[0], current_document)
        self.assertFalse(hasattr(plugin, "_AUTOMATIC_PAGE_SUMMARY_STATE_LIMIT"))
        self.laters[1].run()
        old_later.run()

        self.assertEqual(self.ui.messages, ["1 link."])
        self.assertIsNone(getattr(plugin, "_automaticSummaryPending", None))


    def test_automatic_report_is_count_only_even_when_the_document_has_a_title(self):
        from globalPlugins._speech_core.settings.web_summary_config import set_automatic_reporting_enabled

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]}, root_name="Ready page")
        set_automatic_reporting_enabled(True)
        _plugin, _focus, _target = self._start_event(document)

        self.laters.pop(0).run()

        self.assertEqual(self.ui.messages, ["1 heading."])

    def test_terminate_cancels_and_clears_pending_callbacks(self):
        from globalPlugins._speech_core.settings.web_summary_config import set_automatic_reporting_enabled

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]}, is_ready=False)
        set_automatic_reporting_enabled(True)
        plugin, _focus, _target = self._start_event(document)
        pending = self.laters[0]
        plugin._unregister_speech_hook = lambda: None
        plugin._restore_remote_speech_compatibility = lambda: None
        plugin._restore_windows_toast_system_route = lambda: None
        plugin._restore_system_notification_profile_routes = lambda: None
        plugin._restore_configuration_save_revert_system_routes = lambda: None
        plugin._restore_mouse_pointer_profile_route = lambda: None
        plugin._restore_keyboard_entry_profile_route = lambda: None
        plugin._restore_shortcut_speaker_bypass = lambda: None
        plugin._interruptController = type("Interrupt", (), {"uninstall": lambda self: None})()
        plugin._keyLabelRuntime = type("Labels", (), {"terminate": lambda self: None})()
        plugin._removeClassicSpeechMenu = lambda: None

        plugin.terminate()
        pending.run()

        self.assertTrue(pending.stopped)
        self.assertIsNone(getattr(plugin, "_automaticSummaryPending", None))
        self.assertEqual(self.ui.messages, [])

    def test_terminate_cancels_pending_ready_notification(self):
        from globalPlugins._speech_core.settings.web_summary_config import set_notify_when_page_ready

        document = FakeBrowseDocument({"heading": [FakeQuickNavItem()]}, is_ready=False)
        set_notify_when_page_ready(True)
        plugin, _focus, _target = self._start_event(document)
        pending = self.laters[0]
        plugin._unregister_speech_hook = lambda: None
        plugin._restore_remote_speech_compatibility = lambda: None
        plugin._restore_windows_toast_system_route = lambda: None
        plugin._restore_system_notification_profile_routes = lambda: None
        plugin._restore_configuration_save_revert_system_routes = lambda: None
        plugin._restore_mouse_pointer_profile_route = lambda: None
        plugin._restore_keyboard_entry_profile_route = lambda: None
        plugin._restore_shortcut_speaker_bypass = lambda: None
        plugin._interruptController = type("Interrupt", (), {"uninstall": lambda self: None})()
        plugin._keyLabelRuntime = type("Labels", (), {"terminate": lambda self: None})()
        plugin._removeClassicSpeechMenu = lambda: None

        plugin.terminate()
        pending.run()
        self.assertTrue(pending.stopped)
        self.assertIsNone(getattr(plugin, "_automaticSummaryPending", None))
        self.assertEqual(self.ui.messages, [])


class _BusyDiagnosticState:
    def __init__(self, name):
        self.name = name


class _BusyDiagnosticAppModule:
    appName = "firefox"


class Gecko_ia2:
    def __init__(self, root, loading=True, ready=False, pass_through=False):
        self.rootNVDAObject = root
        self.isLoading = loading
        self.isReady = ready
        self.passThrough = pass_through
        self.VBufHandle = object()


class _BusyDiagnosticObject:
    def __init__(self, states=(), parent=None):
        self.states = set(states)
        self.parent = parent
        self.appModule = _BusyDiagnosticAppModule()
        self.role = "document"
        self.name = "private document title"
        self._speakObjectPropertiesCache = {}


class BusyDiagnosticRuntimeTests(unittest.TestCase):
    """Debug-only provenance checks; they must not alter native event paths."""

    def setUp(self):
        import classic_speech_nvda_master_harness as nvda_harness

        self.nvda_harness = nvda_harness
        nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
        self.module = nvda_harness._import_classic_speech_like_nvda()
        import api
        import logHandler
        import speech.extensions
        import ui
        from globalPlugins._speech_core.settings.advanced_config import _set_debug_logging_enabled

        self.api = api
        self.log = logHandler.log
        self.speech_extensions = speech.extensions
        self.ui = ui
        self._set_debug = _set_debug_logging_enabled
        self._set_debug(False)
        self.log.messages.clear()
        self.ui.messages.clear()

    def tearDown(self):
        self._set_debug(False)
        self.nvda_harness._reset_global_plugin_imports()

    def _gecko_context(self, current=("BUSY",), cached=()):
        root = _BusyDiagnosticObject(current)
        document = Gecko_ia2(root)
        root.treeInterceptor = document
        root._speakObjectPropertiesCache["states"] = set(_BusyDiagnosticState(name) for name in cached)
        self.api.getFocusObject = lambda: root
        return root, document

    def test_busy_diagnostic_record_includes_required_event_focus_buffer_and_state_fields(self):
        root, document = self._gecko_context(current=("BUSY",), cached=())
        plugin = object.__new__(self.module.GlobalPlugin)

        record = plugin._busy_diagnostic_snapshot("stateChange", root)

        self.assertEqual(
            set(record),
            {
                "t_monotonic", "event", "obj_id", "obj_class", "app_name", "app_module_class",
                "role", "name", "states", "busy_now", "focus_id", "is_focus",
                "focus_ancestor_ids", "is_focus_ancestor", "focus_difference_level",
                "tree_interceptor_id", "tree_interceptor_class", "backend", "root_id", "is_root",
                "vbuf_handle_id", "is_loading", "is_ready", "pass_through", "cached_states_present",
                "cached_states", "current_states", "state_symmetric_difference", "busy_only_delta",
                "strict_candidate", "automatic_summary_pending", "automatic_summary_reported",
            },
        )
        self.assertEqual(record["event"], "stateChange")
        self.assertEqual(record["backend"], "gecko")
        self.assertTrue(record["is_focus"])
        self.assertTrue(record["is_root"])
        self.assertEqual(record["name"], "<redacted>")
        self.assertEqual(record["tree_interceptor_id"], id(document))

    def test_busy_diagnostic_marks_root_focused_gecko_loading_busy_only_candidate(self):
        root, _document = self._gecko_context(current=("BUSY",), cached=())
        plugin = object.__new__(self.module.GlobalPlugin)

        record = plugin._busy_diagnostic_snapshot("stateChange", root)

        self.assertTrue(record["busy_now"])
        self.assertEqual(record["state_symmetric_difference"], ["BUSY"])
        self.assertTrue(record["busy_only_delta"])
        self.assertTrue(record["strict_candidate"])

    def test_busy_diagnostic_marks_focus_ancestor_and_busy_plus_other_delta_non_candidates(self):
        ancestor = _BusyDiagnosticObject((_BusyDiagnosticState("BUSY"), _BusyDiagnosticState("SELECTED")))
        root = _BusyDiagnosticObject((_BusyDiagnosticState("BUSY"), _BusyDiagnosticState("SELECTED")), parent=ancestor)
        document = Gecko_ia2(root)
        root.treeInterceptor = document
        ancestor.treeInterceptor = document
        ancestor._speakObjectPropertiesCache["states"] = set()
        self.api.getFocusObject = lambda: root
        plugin = object.__new__(self.module.GlobalPlugin)

        record = plugin._busy_diagnostic_snapshot("stateChange", ancestor)

        self.assertTrue(record["is_focus_ancestor"])
        self.assertFalse(record["is_focus"])
        self.assertEqual(record["state_symmetric_difference"], ["BUSY", "SELECTED"])
        self.assertFalse(record["strict_candidate"])

    def test_busy_diagnostic_does_not_call_speech_filter_or_mutate_focus_caret_selection_or_cache(self):
        root, document = self._gecko_context(current=("BUSY",), cached=("SELECTED",))
        plugin = object.__new__(self.module.GlobalPlugin)
        cache_before = set(root._speakObjectPropertiesCache["states"])
        callbacks_before = list(self.speech_extensions.filter_speechSequence.callbacks)
        focus_before = self.api.getFocusObject()
        handle_before = document.VBufHandle

        plugin._busy_diagnostic_snapshot("stateChange", root)

        self.assertEqual(root._speakObjectPropertiesCache["states"], cache_before)
        self.assertEqual(self.speech_extensions.filter_speechSequence.callbacks, callbacks_before)
        self.assertIs(self.api.getFocusObject(), focus_before)
        self.assertIs(document.VBufHandle, handle_before)
        self.assertEqual(self.ui.messages, [])

    def test_busy_diagnostic_is_silent_when_classicspeech_debug_logging_is_off(self):
        root, _document = self._gecko_context(current=("BUSY",), cached=())
        plugin = object.__new__(self.module.GlobalPlugin)

        plugin._log_busy_diagnostic("stateChange", root)

        self.assertEqual(self.log.messages, [])

    def test_busy_diagnostic_enabled_emits_one_structured_redacted_record(self):
        import json

        root, _document = self._gecko_context(current=("BUSY",), cached=())
        plugin = object.__new__(self.module.GlobalPlugin)
        calls = []
        original_debug = self.module.log.debug
        self.module.log.debug = lambda *args, **kwargs: calls.append((args, kwargs))
        self._set_debug(True)
        try:
            plugin._log_busy_diagnostic("stateChange", root)
        finally:
            self.module.log.debug = original_debug

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0][0], "ClassicSpeech debug: %s")
        record = json.loads(calls[0][0][1])
        self.assertEqual(record["event"], "stateChange")
        self.assertEqual(record["name"], "<redacted>")
        self.assertTrue(record["strict_candidate"])

    def test_busy_diagnostic_missing_or_stale_fields_fail_closed_without_raising(self):
        class StaleObject:
            @property
            def appModule(self):
                raise RuntimeError("stale object")

        plugin = object.__new__(self.module.GlobalPlugin)

        record = plugin._busy_diagnostic_snapshot("stateChange", StaleObject())

        self.assertEqual(record["event"], "stateChange")
        self.assertFalse(record["strict_candidate"])
        self.assertEqual(record["name"], "<redacted>")

    def test_busy_diagnostic_event_handlers_call_next_handler_once_before_logging(self):
        root, document = self._gecko_context(current=("BUSY",), cached=())
        plugin = object.__new__(self.module.GlobalPlugin)
        self._set_debug(True)
        order = []
        plugin._log_busy_diagnostic = lambda event, obj: order.append(("log", event, obj))

        plugin.event_gainFocus(root, lambda: order.append(("native", "gainFocus")))
        plugin.event_stateChange(root, lambda: order.append(("native", "stateChange")))
        plugin.event_documentLoadComplete(document, lambda: order.append(("native", "documentLoadComplete")))

        self.assertEqual(
            order,
            [
                ("native", "gainFocus"), ("log", "gainFocus", root),
                ("native", "stateChange"), ("log", "stateChange", root),
                ("native", "documentLoadComplete"), ("log", "documentLoadComplete", document),
            ],
        )

    def test_busy_diagnostic_off_leaves_all_three_events_observationally_inert(self):
        root, document = self._gecko_context(current=("BUSY",), cached=())
        plugin = object.__new__(self.module.GlobalPlugin)
        observed = []
        plugin._log_busy_diagnostic = lambda *args: observed.append(args)
        calls = []

        plugin.event_gainFocus(root, lambda: calls.append("gainFocus"))
        plugin.event_stateChange(root, lambda: calls.append("stateChange"))
        plugin.event_documentLoadComplete(document, lambda: calls.append("documentLoadComplete"))

        self.assertEqual(calls, ["gainFocus", "stateChange", "documentLoadComplete"])
        self.assertEqual(observed, [])


if __name__ == "__main__":
    unittest.main()
