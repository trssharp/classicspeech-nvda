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
        section = self.config.conf.profiles[0]["classicSpeech"]
        data = section["pageSummaryData"]

        self.assertTrue(self.summary_config.set_automatic_reporting_enabled(" true "))
        self.assertIs(data["automaticReportOnPageLoad"], True)
        self.assertTrue(self.summary_config.get_automatic_reporting_enabled())

        for invalid_value in ("unexpected", 1, object(), None):
            self.assertFalse(self.summary_config.set_automatic_reporting_enabled(invalid_value))
            self.assertIs(data["automaticReportOnPageLoad"], False)
            self.assertFalse(self.summary_config.get_automatic_reporting_enabled())

    def test_invalid_saved_choices_are_dropped_without_losing_valid_choices(self):
        section = self.config.conf.profiles[0]["classicSpeech"]
        section["pageSummaryData"] = {"includedElementTypes": ["unknown", "link", "link", 1]}
        self.assertEqual(self.summary_config.get_included_element_types(), ("link",))

    def test_empty_saved_list_is_preserved_as_an_intentional_no_elements_choice(self):
        self.summary_config.set_included_element_types([])
        self.assertEqual(self.summary_config.get_included_element_types(), ())
        section = self.config.conf.profiles[0]["classicSpeech"]
        self.assertEqual(section["pageSummaryData"]["includedElementTypes"], [])


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
        )

        self.api = api
        self.ui = ui
        self.speech_extensions = speech.extensions
        self.ui.messages.clear()
        self.laters = []
        self.original_call_later = self.module.wx.CallLater
        self.module.wx.CallLater = self._call_later
        set_automatic_reporting_enabled(False)
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


if __name__ == "__main__":
    unittest.main()
