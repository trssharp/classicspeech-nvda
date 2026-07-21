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
    def __init__(self, items_by_type=None, unsupported_types=(), root_name=None):
        self.items_by_type = dict(items_by_type or {})
        self.unsupported_types = set(unsupported_types)
        self.iterator_calls = []
        self.focus_marker = object()
        self.cursor_marker = object()
        self.rootNVDAObject = type("Root", (), {"name": root_name})()

    def _iterNodesByType(self, item_type, direction="next", pos=None):
        self.iterator_calls.append((item_type, direction, pos))
        if item_type in self.unsupported_types:
            raise NotImplementedError(item_type)
        return iter(self.items_by_type.get(item_type, ()))


class RootAccessRaisesBrowseDocument(FakeBrowseDocument):
    @property
    def rootNVDAObject(self):
        raise RuntimeError("stale tree interceptor")

    @rootNVDAObject.setter
    def rootNVDAObject(self, value):
        pass


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

    def test_document_title_formatting_normalizes_whitespace_and_uses_one_sentence_separator(self):
        summary = "1 heading, 2 links."
        self.assertEqual(
            self.summary.format_summary_with_document_title("Example page", summary),
            "Title: Example page. 1 heading, 2 links.",
        )
        self.assertEqual(
            self.summary.format_summary_with_document_title("Example page.", summary),
            "Title: Example page. 1 heading, 2 links.",
        )
        self.assertEqual(
            self.summary.format_summary_with_document_title("  Help! \n", summary),
            "Title: Help! 1 heading, 2 links.",
        )
        self.assertEqual(
            self.summary.format_summary_with_document_title("What\t is\nnew?", summary),
            "Title: What is new? 1 heading, 2 links.",
        )
        self.assertEqual(
            self.summary.format_summary_with_document_title("Loading…", summary),
            "Title: Loading… 1 heading, 2 links.",
        )
        self.assertEqual(
            self.summary.format_summary_with_document_title("  Example\n page\t overview  ", summary),
            "Title: Example page overview. 1 heading, 2 links.",
        )
        for title in (None, "", " \t ", 1):
            self.assertEqual(self.summary.format_summary_with_document_title(title, summary), summary)

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
        self.assertIn("includeDocumentTitle", spec["pageSummaryData"])
        self.assertFalse(self.summary_config.get_include_document_title())
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

    def test_document_title_choice_defaults_off_and_round_trips(self):
        self.assertFalse(self.summary_config.get_include_document_title())
        self.assertTrue(self.summary_config.set_include_document_title(True))
        self.assertTrue(self.summary_config.get_include_document_title())
        section = self.config.conf.profiles[0]["classicSpeech"]
        self.assertTrue(section["pageSummaryData"]["includeDocumentTitle"])
        self.assertFalse(self.summary_config.set_include_document_title(False))

    def test_document_title_choice_parses_only_explicit_boolean_values(self):
        section = self.config.conf.profiles[0]["classicSpeech"]
        data = section["pageSummaryData"]
        for saved_value, expected in (
            ("False", False),
            ("True", True),
            (" false ", False),
            ("unexpected", False),
        ):
            data["includeDocumentTitle"] = saved_value
            self.assertIs(self.summary_config.get_include_document_title(), expected)
        self.assertFalse(self.summary_config.set_include_document_title("unexpected"))
        self.assertFalse(data["includeDocumentTitle"])
        self.assertTrue(self.summary_config.set_include_document_title(" true "))
        self.assertTrue(data["includeDocumentTitle"])

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
        from globalPlugins._speech_core.settings.web_summary_config import (
            set_include_document_title,
            set_included_element_types,
        )
        self.api = api
        self.ui = ui
        self.ui.messages.clear()
        set_included_element_types(["heading", "link"])
        set_include_document_title(False)

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

    def test_page_summary_includes_enabled_document_title_without_moving_quick_nav_or_focus(self):
        from globalPlugins._speech_core.settings.web_summary_config import set_include_document_title

        heading = FakeQuickNavItem()
        link = FakeQuickNavItem()
        document = FakeBrowseDocument(
            {"heading": [heading], "link": [link]}, root_name="ClassicSpeech documentation",
        )
        focus = type("Focus", (), {"treeInterceptor": document})()
        self.api.getFocusObject = lambda: focus
        set_include_document_title(True)
        plugin = object.__new__(self.module.GlobalPlugin)

        plugin.script_pageSummary(None)

        self.assertEqual(self.ui.messages, ["Title: ClassicSpeech documentation. 1 heading, 1 link."])
        self.assertIs(self.api.getFocusObject(), focus)
        self.assertEqual(heading.report_calls, 0)
        self.assertEqual(heading.move_calls, 0)
        self.assertEqual(link.report_calls, 0)
        self.assertEqual(link.move_calls, 0)

    def test_page_summary_uses_count_only_output_when_document_root_is_missing(self):
        heading = FakeQuickNavItem()
        link = FakeQuickNavItem()
        document = FakeBrowseDocument({"heading": [heading], "link": [link]})
        del document.rootNVDAObject
        focus = type("Focus", (), {"treeInterceptor": document})()
        self.api.getFocusObject = lambda: focus
        from globalPlugins._speech_core.settings.web_summary_config import set_include_document_title

        set_include_document_title(True)
        plugin = object.__new__(self.module.GlobalPlugin)

        plugin.script_pageSummary(None)

        self.assertEqual(self.ui.messages, ["1 heading, 1 link."])
        self.assertIs(self.api.getFocusObject(), focus)
        self.assertEqual(heading.report_calls, 0)
        self.assertEqual(heading.move_calls, 0)
        self.assertEqual(link.report_calls, 0)
        self.assertEqual(link.move_calls, 0)

    def test_page_summary_uses_count_only_output_when_document_title_access_raises(self):
        import logHandler

        class BrokenRoot:
            @property
            def name(self):
                raise RuntimeError("stale root")

        heading = FakeQuickNavItem()
        link = FakeQuickNavItem()
        document = FakeBrowseDocument({"heading": [heading], "link": [link]})
        document.rootNVDAObject = BrokenRoot()
        focus = type("Focus", (), {"treeInterceptor": document})()
        self.api.getFocusObject = lambda: focus
        from globalPlugins._speech_core.settings.web_summary_config import set_include_document_title

        logHandler.log.messages.clear()
        set_include_document_title(True)
        plugin = object.__new__(self.module.GlobalPlugin)

        plugin.script_pageSummary(None)

        self.assertEqual(self.ui.messages, ["1 heading, 1 link."])
        self.assertIn(
            ("debug", "ClassicSpeech: failed to read page summary document title"),
            logHandler.log.messages,
        )
        self.assertIs(self.api.getFocusObject(), focus)
        self.assertEqual(heading.report_calls, 0)
        self.assertEqual(heading.move_calls, 0)
        self.assertEqual(link.report_calls, 0)
        self.assertEqual(link.move_calls, 0)

    def test_page_summary_uses_count_only_output_when_document_root_access_raises(self):
        import logHandler
        from globalPlugins._speech_core.settings.web_summary_config import set_include_document_title

        heading = FakeQuickNavItem()
        link = FakeQuickNavItem()
        document = RootAccessRaisesBrowseDocument({"heading": [heading], "link": [link]})
        focus = type("Focus", (), {"treeInterceptor": document})()
        self.api.getFocusObject = lambda: focus
        logHandler.log.messages.clear()
        set_include_document_title(True)
        plugin = object.__new__(self.module.GlobalPlugin)

        plugin.script_pageSummary(None)

        self.assertEqual(self.ui.messages, ["1 heading, 1 link."])
        self.assertIn(
            ("debug", "ClassicSpeech: failed to read page summary document title"),
            logHandler.log.messages,
        )
        self.assertIs(self.api.getFocusObject(), focus)
        self.assertEqual(heading.report_calls, 0)
        self.assertEqual(heading.move_calls, 0)
        self.assertEqual(link.report_calls, 0)
        self.assertEqual(link.move_calls, 0)

    def test_page_summary_reports_unavailable_outside_browse_mode(self):
        self.api.getFocusObject = lambda: object()
        plugin = object.__new__(self.module.GlobalPlugin)

        import speech.extensions
        callbacks_before = list(speech.extensions.filter_speechSequence.callbacks)
        plugin.script_pageSummary(None)

        self.assertEqual(speech.extensions.filter_speechSequence.callbacks, callbacks_before)
        self.assertEqual(self.ui.messages, ["Page summary is not available here."])


if __name__ == "__main__":
    unittest.main()
