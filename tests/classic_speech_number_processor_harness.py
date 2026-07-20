"""ClassicSpeech number/date/currency processor regression harness.

This harness starts as a safety fence before number-processing behavior exists.
It verifies that ClassicSpeech's current literal-text path preserves numeric,
date/time, phone-like, and currency strings by default so future JAWS-style
number processing can be added opt-in without accidentally changing native
NVDA/synth behavior.
"""
from __future__ import annotations

import types
import unittest

from classic_speech_core_harness import BaseSpeechProcessor, TextProcessor, api


_DEFAULT_TEXT_PROCESSING_DATA = {
    "announceNewLinesDuringSayAll": False,
    "newLineMessage": "new line",
    "splitMixedCaseWords": False,
    "suppressWordInternalDashes": False,
    "spellAlphanumericData": "off",
    "repeatedCharacterMode": "3",
    "filterRepeatedCharacters": False,
    "repeatedCharacterLimit": 3,
}

_DEFAULT_NUMBER_PROCESSING_DATA = {
    "numberProcessingMode": "synthesizer",
    "singleDigitsIfNumberContains": "synthesizer",
    "phoneNumberProcessing": "native",
    "friendlyTollFreePrefixes": True,
    "currencyProcessing": "native",
    "ordinalProcessing": "native",
    "numericDateProcessing": "native",
    "numericDateFormat": "mdy",
    "recognizeIsoDates": True,
    "useWindowsDateFormat": False,
}


NUMBER_PROCESSING_BASELINE_EXAMPLES = [
    "$1.23",
    "$9.99",
    "$10.00",
    "$0.02",
    "$100",
    "€10",
    "£10",
    "03-16-00",
    "03-16",
    "12:30",
    "1-800-444-4443",
    "54321",
    "123",
    "1050",
    "123RON",
    "item42",
    "A-123",
    "123-A",
    "3/4",
]


class NumberProcessorBaselinePassThroughTests(unittest.TestCase):
    def setUp(self):
        import config
        import speech

        config.conf["classicSpeech"]["textProcessingData"] = dict(_DEFAULT_TEXT_PROCESSING_DATA)
        config.conf["classicSpeech"]["numberProcessingData"] = dict(_DEFAULT_NUMBER_PROCESSING_DATA)
        speech.sayAll.SayAllHandler.isRunning = lambda: False
        api.getFocusObject = lambda: None

    def tearDown(self):
        import config
        import speech

        config.conf["classicSpeech"]["textProcessingData"] = dict(_DEFAULT_TEXT_PROCESSING_DATA)
        config.conf["classicSpeech"]["numberProcessingData"] = dict(_DEFAULT_NUMBER_PROCESSING_DATA)
        speech.sayAll.SayAllHandler.isRunning = lambda: False
        api.getFocusObject = lambda: None

    def test_text_processor_preserves_number_currency_and_date_strings_by_default(self):
        processor = TextProcessor()
        for text in NUMBER_PROCESSING_BASELINE_EXAMPLES:
            with self.subTest(text=text):
                self.assertEqual(processor.process_literal_sequence([text]), [text])

    def test_base_processor_literal_bypass_preserves_number_strings_by_default(self):
        api.getFocusObject = lambda: types.SimpleNamespace(
            role=types.SimpleNamespace(name="EDITABLETEXT"),
            name="Editor",
            parent=None,
        )
        for text in NUMBER_PROCESSING_BASELINE_EXAMPLES:
            with self.subTest(text=text):
                sequence = [text]
                BaseSpeechProcessor().process(sequence)
                self.assertEqual(sequence, [text])

    def test_text_processor_preserves_mixed_number_sentence_by_default(self):
        processor = TextProcessor()
        sentence = "Invoice $9.99 due 03-16-00, call 1-800-444-4443, code 123RON."
        self.assertEqual(processor.process_literal_sequence([sentence]), [sentence])


class NumberProcessorModeTests(unittest.TestCase):
    def setUp(self):
        import config
        import speech

        config.conf["classicSpeech"]["textProcessingData"] = dict(_DEFAULT_TEXT_PROCESSING_DATA)
        config.conf["classicSpeech"]["numberProcessingData"] = dict(_DEFAULT_NUMBER_PROCESSING_DATA)
        speech.sayAll.SayAllHandler.isRunning = lambda: False
        api.getFocusObject = lambda: None

    def tearDown(self):
        import config
        import speech

        config.conf["classicSpeech"]["textProcessingData"] = dict(_DEFAULT_TEXT_PROCESSING_DATA)
        config.conf["classicSpeech"]["numberProcessingData"] = dict(_DEFAULT_NUMBER_PROCESSING_DATA)
        speech.sayAll.SayAllHandler.isRunning = lambda: False
        api.getFocusObject = lambda: None

    def _set_mode(self, mode: str):
        import config

        config.conf["classicSpeech"]["numberProcessingData"]["numberProcessingMode"] = mode

    def _set_single_digits_threshold(self, threshold: str):
        import config

        config.conf["classicSpeech"]["numberProcessingData"]["singleDigitsIfNumberContains"] = threshold

    def _set_phone_number_processing(self, mode: str):
        import config

        config.conf["classicSpeech"]["numberProcessingData"]["phoneNumberProcessing"] = mode

    def _set_friendly_toll_free_prefixes(self, enabled: bool):
        import config

        config.conf["classicSpeech"]["numberProcessingData"]["friendlyTollFreePrefixes"] = enabled

    def _set_currency_processing(self, mode: str):
        import config

        config.conf["classicSpeech"]["numberProcessingData"]["currencyProcessing"] = mode

    def _set_ordinal_processing(self, mode: str):
        import config

        config.conf["classicSpeech"]["numberProcessingData"]["ordinalProcessing"] = mode

    def _set_numeric_date_processing(self, mode: str):
        import config

        config.conf["classicSpeech"]["numberProcessingData"]["numericDateProcessing"] = mode

    def _set_numeric_date_format(self, date_format: str):
        import config

        config.conf["classicSpeech"]["numberProcessingData"]["numericDateFormat"] = date_format

    def _set_recognize_iso_dates(self, enabled: bool):
        import config

        config.conf["classicSpeech"]["numberProcessingData"]["recognizeIsoDates"] = enabled

    def _set_use_windows_date_format(self, enabled: bool):
        import config

        config.conf["classicSpeech"]["numberProcessingData"]["useWindowsDateFormat"] = enabled

    def test_single_digits_mode_speaks_standalone_numbers_as_digits(self):
        self._set_mode("singleDigits")
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["123 1050 0"]),
            ["one two three one zero five zero zero"],
        )

    def test_pairs_mode_speaks_standalone_numbers_as_digit_pairs(self):
        self._set_mode("pairs")
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["1050 123 1005"]),
            ["ten fifty one twenty three ten oh five"],
        )

    def test_full_numbers_mode_speaks_standalone_numbers_as_words(self):
        self._set_mode("fullNumbers")
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["0 5 42 123 1005"]),
            ["zero five forty two one hundred twenty three one thousand five"],
        )

    def test_full_numbers_mode_supports_large_values_through_quadrillions(self):
        self._set_mode("fullNumbers")
        processor = TextProcessor()
        cases = {
            "10": "ten",
            "11": "eleven",
            "19": "nineteen",
            "20": "twenty",
            "21": "twenty one",
            "99": "ninety nine",
            "100": "one hundred",
            "101": "one hundred one",
            "110": "one hundred ten",
            "115": "one hundred fifteen",
            "999": "nine hundred ninety nine",
            "1000": "one thousand",
            "1001": "one thousand one",
            "1010": "one thousand ten",
            "1100": "one thousand one hundred",
            "12345": "twelve thousand three hundred forty five",
            "1000000": "one million",
            "1000001": "one million one",
            "1234567": "one million two hundred thirty four thousand five hundred sixty seven",
            "1000000000": "one billion",
            "1000000000000": "one trillion",
            "1000000000000000": "one quadrillion",
            "100000000000000000": "one hundred quadrillion",
            "999999999999999999": (
                "nine hundred ninety nine quadrillion "
                "nine hundred ninety nine trillion "
                "nine hundred ninety nine billion "
                "nine hundred ninety nine million "
                "nine hundred ninety nine thousand "
                "nine hundred ninety nine"
            ),
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(processor.process_literal_sequence([source]), [expected])

    def test_full_numbers_mode_ignores_commas_inside_whole_numbers(self):
        self._set_mode("fullNumbers")
        processor = TextProcessor()
        cases = {
            "1,234": "one thousand two hundred thirty four",
            "12,34": "one thousand two hundred thirty four",
            "1,23,456": "one hundred twenty three thousand four hundred fifty six",
            "1,2,3": "one hundred twenty three",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(processor.process_literal_sequence([source]), [expected])

    def test_number_modes_preserve_currency_dates_times_phones_and_alphanumerics(self):
        processor = TextProcessor()
        protected = (
            "$9.99 03-16-00 03-16 12:30 1-800-444-4443 "
            "123RON item42 A-123 123-A 3/4 00123 007 -123 12.34 1,234.56"
        )
        for mode in ("singleDigits", "pairs", "fullNumbers"):
            with self.subTest(mode=mode):
                self._set_mode(mode)
                self.assertEqual(processor.process_literal_sequence([protected]), [protected])

    def test_number_modes_preserve_position_count_strings_for_position_filtering(self):
        processor = TextProcessor()
        examples = ["1 of 10", "Verbosity 1 of 10", "1,234 of 5,678"]
        for mode in ("singleDigits", "pairs", "fullNumbers"):
            self._set_mode(mode)
            for text in examples:
                with self.subTest(mode=mode, text=text):
                    self.assertEqual(processor.process_literal_sequence([text]), [text])

    def test_single_digits_threshold_speaks_long_literal_number_from_log_as_digits(self):
        self._set_single_digits_threshold("5")
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["1234567890000\r"]),
            ["one two three four five six seven eight nine zero zero zero zero\r"],
        )

    def test_single_digits_threshold_keeps_shorter_numbers_synth_controlled(self):
        self._set_single_digits_threshold("5")
        processor = TextProcessor()
        self.assertEqual(processor.process_literal_sequence(["123 1050"]), ["123 1050"])

    def test_single_digits_threshold_runs_after_number_mode_for_long_standalone_numbers(self):
        self._set_mode("fullNumbers")
        self._set_single_digits_threshold("5")
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["123 54321"]),
            ["one hundred twenty three five four three two one"],
        )

    def test_single_digits_threshold_preserves_protected_number_like_strings(self):
        self._set_single_digits_threshold("5")
        processor = TextProcessor()
        protected = "123RON item42 1-800-444-4443 03-16-00 12:30 $12345 3/45678"
        self.assertEqual(processor.process_literal_sequence([protected]), [protected])

    def test_phone_number_processing_speaks_common_us_phone_numbers_as_grouped_digits(self):
        self._set_phone_number_processing("groupedDigits")
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["Call 555-123-4567, (555) 123-4567, or 5551234567."]),
            [
                "Call five five five, one two three, four five six seven, "
                "five five five, one two three, four five six seven, or "
                "five five five, one two three, four five six seven."
            ],
        )

    def test_phone_number_processing_supports_leading_one_dash_numbers(self):
        self._set_phone_number_processing("groupedDigits")
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["Call 1-800-444-4443."]),
            ["Call one eight hundred, four four four, four four four three."],
        )

    def test_phone_number_processing_speaks_common_toll_free_prefixes_friendly_by_default(self):
        self._set_phone_number_processing("groupedDigits")
        processor = TextProcessor()
        cases = {
            "1-800-444-4443": "one eight hundred, four four four, four four four three",
            "800-444-4443": "eight hundred, four four four, four four four three",
            "1-888-123-4567": "one eight eighty eight, one two three, four five six seven",
            "877-123-4567": "eight seventy seven, one two three, four five six seven",
            "1-866-123-4567": "one eight sixty six, one two three, four five six seven",
            "855-123-4567": "eight fifty five, one two three, four five six seven",
            "1-844-123-4567": "one eight forty four, one two three, four five six seven",
            "833-123-4567": "eight thirty three, one two three, four five six seven",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(processor.process_literal_sequence([source]), [expected])

    def test_phone_number_processing_can_disable_friendly_toll_free_prefixes(self):
        self._set_phone_number_processing("groupedDigits")
        self._set_friendly_toll_free_prefixes(False)
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["Call 1-800-444-4443 or 800-444-4443."]),
            [
                "Call one, eight zero zero, four four four, four four four three or "
                "eight zero zero, four four four, four four four three."
            ],
        )

    def test_phone_number_processing_does_not_use_friendly_prefix_for_normal_area_codes(self):
        self._set_phone_number_processing("groupedDigits")
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["Call 1-900-444-4443 or 900-444-4443."]),
            [
                "Call one, nine zero zero, four four four, four four four three or "
                "nine zero zero, four four four, four four four three."
            ],
        )

    def test_phone_number_processing_preserves_non_phone_codes_dates_and_times(self):
        self._set_phone_number_processing("groupedDigits")
        processor = TextProcessor()
        protected = "A-123 123-A 03-16-00 03-16 12:30 2026-09-05 123RON item42 123-45-6789"
        self.assertEqual(processor.process_literal_sequence([protected]), [protected])

    def test_currency_processing_speaks_simple_dollars_and_cents(self):
        self._set_currency_processing("dollarsAndCents")
        processor = TextProcessor()
        cases = {
            "$1.00": "one dollar",
            "$1.99": "one dollar and ninety nine cents",
            "$0.95": "ninety five cents",
            "$0.02": "two cents",
            "$1.01": "one dollar and one cent",
            "$2.01": "two dollars and one cent",
            "$10": "ten dollars",
            "$100.00": "one hundred dollars",
            "$1,234.56": "one thousand two hundred thirty four dollars and fifty six cents",
            "$1,000,000.00": "one million dollars",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(processor.process_literal_sequence([source]), [expected])

    def test_currency_processing_preserves_non_initial_scope_currency_strings(self):
        self._set_currency_processing("dollarsAndCents")
        processor = TextProcessor()
        protected = "€10 £10 ¥10 USD 10 10 dollars -$1.00 $1.2 $1.234 $abc $12,34.56"
        self.assertEqual(processor.process_literal_sequence([protected]), [protected])

    def test_ordinal_processing_speaks_standalone_ordinals_as_words(self):
        self._set_ordinal_processing("words")
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["1st 2nd 3rd 4th 11th 12th 13th 21st 22nd 23rd 100th 101st"]),
            ["first second third fourth eleventh twelfth thirteenth twenty first twenty second twenty third one hundredth one hundred first"],
        )

    def test_ordinal_processing_preserves_invalid_or_embedded_ordinals(self):
        self._set_ordinal_processing("words")
        processor = TextProcessor()
        protected = "1nd 2rd 3th 11st 12nd 13rd item1st A-1st 001st 1st-place 1st/2nd"
        self.assertEqual(processor.process_literal_sequence([protected]), [protected])

    def test_ordinal_processing_is_native_by_default(self):
        processor = TextProcessor()
        self.assertEqual(processor.process_literal_sequence(["1st 22nd 103rd"]), ["1st 22nd 103rd"])

    def test_numeric_date_processing_some_speaks_month_day_year_only(self):
        self._set_numeric_date_processing("some")
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["Due 5/9/2026 and 03-16-00."]),
            ["Due May ninth, twenty twenty six and March sixteenth, two thousand."],
        )
        self.assertEqual(processor.process_literal_sequence(["Due 5/9 and 03-16."]), ["Due 5/9 and 03-16."])

    def test_numeric_date_processing_full_also_speaks_month_day_fragments(self):
        self._set_numeric_date_processing("full")
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["Due 5/9/2026, 5/9, 03-16, and 1/3."]),
            ["Due May ninth, twenty twenty six, May ninth, March sixteenth, and January third."],
        )

    def test_numeric_date_processing_day_month_year_format(self):
        self._set_numeric_date_processing("full")
        self._set_numeric_date_format("dmy")
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["Due 5/9/2026, 17/8/2002, 5/9, and 17/8."]),
            [
                "Due September fifth, twenty twenty six, "
                "August seventeenth, two thousand two, September fifth, and August seventeenth."
            ],
        )

    def test_numeric_date_processing_year_month_day_format(self):
        self._set_numeric_date_processing("full")
        self._set_numeric_date_format("ymd")
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["Due 2026-09-05 and 2026/9/5, not 5/9/2026."]),
            [
                "Due September fifth, twenty twenty six and September fifth, twenty twenty six, "
                "not 5/9/2026."
            ],
        )

    def test_numeric_date_processing_recognizes_iso_dates_without_changing_mdy_format(self):
        self._set_numeric_date_processing("some")
        self._set_numeric_date_format("mdy")
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["Due 2026-09-05 and 5/9/2026."]),
            ["Due September fifth, twenty twenty six and May ninth, twenty twenty six."],
        )

    def test_numeric_date_processing_can_disable_iso_recognition_for_mdy_format(self):
        self._set_numeric_date_processing("some")
        self._set_numeric_date_format("mdy")
        self._set_recognize_iso_dates(False)
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["Due 2026-09-05 and 5/9/2026."]),
            ["Due 2026-09-05 and May ninth, twenty twenty six."],
        )

    def test_windows_date_format_overrides_explicit_format_when_supported(self):
        from _speech_core.processors import numbers

        original = numbers._get_windows_short_date_pattern
        self._set_numeric_date_processing("some")
        self._set_numeric_date_format("dmy")
        self._set_use_windows_date_format(True)
        numbers._get_windows_short_date_pattern = lambda: "M/d/yyyy"
        try:
            self.assertEqual(
                TextProcessor().process_literal_sequence(["Due 5/9/2026."]),
                ["Due May ninth, twenty twenty six."],
            )
        finally:
            numbers._get_windows_short_date_pattern = original

    def test_windows_date_format_uses_strict_year_month_day_when_reported(self):
        from _speech_core.processors import numbers

        original = numbers._get_windows_short_date_pattern
        self._set_numeric_date_processing("some")
        self._set_numeric_date_format("dmy")
        self._set_use_windows_date_format(True)
        numbers._get_windows_short_date_pattern = lambda: "yyyy-MM-dd"
        try:
            self.assertEqual(
                TextProcessor().process_literal_sequence(["Due 2026-09-05 and 2026/9/5."]),
                ["Due September fifth, twenty twenty six and September fifth, twenty twenty six."],
            )
        finally:
            numbers._get_windows_short_date_pattern = original

    def test_windows_date_format_still_falls_back_when_order_is_unsupported(self):
        from _speech_core.processors import numbers

        original = numbers._get_windows_short_date_pattern
        self._set_numeric_date_processing("some")
        self._set_numeric_date_format("dmy")
        self._set_use_windows_date_format(True)
        numbers._get_windows_short_date_pattern = lambda: "yyyy/dd/MM"
        try:
            self.assertEqual(
                TextProcessor().process_literal_sequence(["Due 17/8/2002."]),
                ["Due August seventeenth, two thousand two."],
            )
        finally:
            numbers._get_windows_short_date_pattern = original

    def test_strict_year_month_day_preserves_unsafe_year_first_strings(self):
        from _speech_core.processors import numbers

        original = numbers._get_windows_short_date_pattern
        self._set_numeric_date_processing("some")
        self._set_use_windows_date_format(True)
        numbers._get_windows_short_date_pattern = lambda: "yyyy-MM-dd"
        try:
            protected = "26-09-05 20260905 2026.09.05 A-2026-09-05 2026-09-05-B 2026-02-30"
            self.assertEqual(TextProcessor().process_literal_sequence([protected]), [protected])
        finally:
            numbers._get_windows_short_date_pattern = original

    def test_numeric_date_processing_preserves_invalid_dates_phones_and_codes(self):
        self._set_numeric_date_processing("full")
        processor = TextProcessor()
        protected = "13/1/2026 2/30/2026 2026-02-30 1-800-444-4443 A-123 123-A -123"
        self.assertEqual(processor.process_literal_sequence([protected]), [protected])


if __name__ == "__main__":
    unittest.main(verbosity=2)
