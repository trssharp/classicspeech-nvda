"""Position number presentation: semantic-only, after verbosity filtering."""
import copy
import types
import unittest
from unittest.mock import patch

from classic_speech_core_harness import BaseSpeechProcessor, SpeechFormatter, api
import config
from _speech_core import formatter
from _speech_core.tokens import token
from _speech_core.processors.numbers import process_number_text


class PositionNumberTests(unittest.TestCase):
    def setUp(self):
        self.saved = copy.deepcopy(config.conf["classicSpeech"])
        self.focus_getter = api.getFocusObject
        config.conf["classicSpeech"]["numberProcessingData"] = {}
        self.profile = {"globalPause": 25, "order": ["position", "name", "role"]}

    def tearDown(self):
        config.conf["classicSpeech"] = self.saved
        api.getFocusObject = self.focus_getter

    def mode(self, value):
        config.conf["classicSpeech"]["numberProcessingData"]["numberProcessingMode"] = value

    def render(self, text, kind="position"):
        return [x for x in SpeechFormatter().format([token(kind, raw=text, spoken=text)], self.profile) if isinstance(x, str)]

    def test_four_modes(self):
        for mode, expected in {
            "synthesizer": "1 of 1900",
            "singleDigits": "one of one nine zero zero",
            "pairs": "one of nineteen oh zero",
            "fullNumbers": "one of one thousand nine hundred",
        }.items():
            with self.subTest(mode=mode):
                self.mode(mode)
                self.assertEqual(self.render("1 of 1900"), [expected])

    def test_native_ignores_other_number_features_and_threshold(self):
        config.conf["classicSpeech"]["numberProcessingData"] = {
            "numberProcessingMode": "synthesizer", "singleDigitsIfNumberContains": "5",
            "phoneNumberProcessing": "groupedDigits", "currencyProcessing": "dollarsAndCents",
            "numericDateProcessing": "full", "ordinalProcessing": "words",
        }
        self.assertEqual(self.render("1 of 1234567890"), ["1 of 1234567890"])

    def test_safe_layouts_and_unsupported_numbers(self):
        self.mode("fullNumbers")
        self.assertEqual(self.render("1 of 1,900"), ["one of one thousand nine hundred"])
        for text in ("1 of 1,,900", "1 of ,1900", "1 of 1900,", "1 of 19.00", "1 / 1900",
                     "item 1 of 1900", "1 of 1900 items", "01 of 1900", "1 of 01900",
                     "1 of 1234567890123456789", "1 von 1900", "-1 of 1900"):
            with self.subTest(text=text):
                self.assertEqual(self.render(text), [text])

    def test_only_position_tokens_and_global_protection(self):
        self.mode("fullNumbers")
        for kind in ("name", "value", "description", "tooltip", "hotkey", "role", "state"):
            with self.subTest(kind=kind):
                profile = dict(self.profile, enabledTokens={"tooltip": True})
                out = SpeechFormatter().format([token(kind, raw="1 of 1900")], profile)
                self.assertIn("1 of 1900", out)
        for text in ("1 of 1900", "Chapter 1 of 1900", "1,234 of 5,678"):
            self.assertEqual(process_number_text(text), text)

    def test_filter_each_first_off_before_rendering(self):
        self.mode("fullNumbers")
        for mode, expected in (("each", [True, True]), ("first", [True, False]), ("off", [False, False])):
            processor = BaseSpeechProcessor()
            with patch.object(processor.position_filter, "_get_position_container_signature", return_value="container"):
                for present in expected:
                    tokens = [token("position", raw="1 of 1900")]
                    kept = processor._apply_position_mode(tokens, mode_override=mode)
                    out = processor.formatter.format(kept, self.profile)
                    self.assertEqual("one of one thousand nine hundred" in out, present)

    def test_routes_schemes_pauses_renames_and_source_are_preserved(self):
        tokens = [token("name", raw="1 of 1900"), token("role", raw="button"), token("position", raw="1 of 1900", source=["1 of 1900"])]
        before = copy.deepcopy(tokens)
        profile = dict(self.profile, renames={"button": "1 of 1900"})
        marker = object()
        wrappers = {route: (object(), object()) for route in ("focusNavigation", "systemNotifications", "reviewObjectNavigation")}
        def wrap(seq, route, **kwargs):
            start, end = wrappers.setdefault(route, (object(), object()))
            return [start, *seq, end]
        def shape(seq):
            return [("pause", x.time) if hasattr(x, "time") else x for x in seq]
        with patch.object(formatter, "wrap_profile_sequence", side_effect=wrap), patch.object(formatter, "label_marker_for_token", side_effect=lambda t: marker if t.kind == "role" else None):
            for origin in ("focus", "objectNavigation"):
                self.mode("synthesizer")
                native = SpeechFormatter().format(tokens, profile, origin)
                self.mode("fullNumbers")
                changed = SpeechFormatter().format(tokens, profile, origin)
                expected = list(native)
                expected[expected.index("1 of 1900")] = "one of one thousand nine hundred"
                self.assertEqual(shape(changed), shape(expected))
        self.assertEqual(tokens, before)

    def test_unrecognized_layout_and_document_phrase_remain_literal(self):
        self.mode("fullNumbers")
        # The classifier does not currently recognize comma-grouped positions.
        # Do not broaden recognition as a side effect of presentation formatting.
        api.getFocusObject = lambda: types.SimpleNamespace(role=types.SimpleNamespace(name="LISTITEM"), name="Alpha", parent=None)
        out = BaseSpeechProcessor().process(["Alpha", "1 of 1,900"])
        self.assertIn("1 of 1,900", " ".join(x for x in out if isinstance(x, str)))
        api.getFocusObject = lambda: types.SimpleNamespace(role=types.SimpleNamespace(name="EDITABLETEXT"), name="Editor", parent=None)
        text = "Chapter 1 of 1900"
        self.assertEqual(BaseSpeechProcessor().process([text]), [text])

    def test_conversion_is_not_called_for_filtered_positions(self):
        processor = BaseSpeechProcessor()
        with patch.object(formatter, "format_position_numbers", side_effect=AssertionError("filtered token rendered")):
            kept = processor._apply_position_mode([token("position", raw="1 of 1900")], mode_override="off")
            self.assertEqual(processor.formatter.format(kept, self.profile), [])

    def test_engine_command_boundaries_and_raw_cache(self):
        self.mode("fullNumbers")
        config.conf["classicSpeech"]["positionMode"] = "each"
        api.getFocusObject = lambda: types.SimpleNamespace(role=types.SimpleNamespace(name="LISTITEM"), name="Alpha", parent=None)
        processor = BaseSpeechProcessor()
        start, middle, end = object(), object(), object()
        source = [start, "Alpha", middle, "1 of 1900", end]
        out = processor.process(list(source))
        self.assertIn("one of one thousand nine hundred", out)
        self.assertLess(out.index(start), out.index("Alpha"))
        self.assertLess(out.index("Alpha"), out.index(middle))
        self.assertLess(out.index(middle), out.index("one of one thousand nine hundred"))
        self.assertLess(out.index("one of one thousand nine hundred"), out.index(end))
        self.assertEqual(processor._last_raw_sequence, source)


if __name__ == "__main__":
    unittest.main()
