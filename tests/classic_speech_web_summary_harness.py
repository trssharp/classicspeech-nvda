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
    def __init__(self, items_by_type=None, unsupported_types=()):
        self.items_by_type = dict(items_by_type or {})
        self.unsupported_types = set(unsupported_types)
        self.iterator_calls = []
        self.focus_marker = object()
        self.cursor_marker = object()

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

    def test_invalid_saved_choices_are_dropped_without_losing_valid_choices(self):
        section = self.config.conf.profiles[0]["classicSpeech"]
        section["pageSummaryData"] = {"includedElementTypes": ["unknown", "link", "link", 1]}
        self.assertEqual(self.summary_config.get_included_element_types(), ("link",))

    def test_empty_saved_list_is_preserved_as_an_intentional_no_elements_choice(self):
        self.summary_config.set_included_element_types([])
        self.assertEqual(self.summary_config.get_included_element_types(), ())
        section = self.config.conf.profiles[0]["classicSpeech"]
        self.assertEqual(section["pageSummaryData"]["includedElementTypes"], [])


if __name__ == "__main__":
    unittest.main()
