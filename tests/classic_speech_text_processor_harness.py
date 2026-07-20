"""ClassicSpeech text processor regression harness.

This imports the shared NVDA stubs and processor facades from the core harness,
then runs the literal text processing tests separately so both harness files stay
small and screen-reader friendly.
"""
from __future__ import annotations

import types
import unittest

from classic_speech_core_harness import (
    BaseSpeechProcessor,
    BreakCommand,
    TextProcessor,
    TOKEN_HOTKEY,
    TOKEN_NAME,
    TOKEN_POSITION,
    TOKEN_ROLE,
    api,
    classify_tokens,
    parse_shortcut_list,
    parse_trailing_label_shortcut,
)


class TextProcessorTests(unittest.TestCase):
    def setUp(self):
        import config

        config.conf["classicSpeech"]["textProcessingData"] = {
            "announceNewLinesDuringSayAll": False,
            "newLineMessage": "new line",
            "splitMixedCaseWords": False,
            "suppressWordInternalDashes": False,
            "spellAlphanumericData": "off",
            "repeatedCharacterMode": "3",
            "filterRepeatedCharacters": False,
            "repeatedCharacterLimit": 3,
        }
        config.conf["classicSpeech"]["numberProcessingData"] = {
            "numberProcessingMode": "synthesizer",
            "singleDigitsIfNumberContains": "synthesizer",
        }

    def tearDown(self):
        import speech
        import config

        speech.sayAll.SayAllHandler.isRunning = lambda: False
        api.getFocusObject = lambda: None
        config.conf["classicSpeech"]["textProcessingData"] = {
            "announceNewLinesDuringSayAll": False,
            "newLineMessage": "new line",
            "splitMixedCaseWords": False,
            "suppressWordInternalDashes": False,
            "spellAlphanumericData": "off",
            "repeatedCharacterMode": "3",
            "filterRepeatedCharacters": False,
            "repeatedCharacterLimit": 3,
        }
        config.conf["classicSpeech"]["numberProcessingData"] = {
            "numberProcessingMode": "synthesizer",
            "singleDigitsIfNumberContains": "synthesizer",
        }

    def test_say_all_literal_newlines_are_announced(self):
        import config
        import speech

        config.conf["classicSpeech"]["textProcessingData"]["announceNewLinesDuringSayAll"] = True
        speech.sayAll.SayAllHandler.isRunning = lambda: True
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["first\nsecond"]),
            ["first", "new line", "second"],
        )

    def test_say_all_double_carriage_return_announces_blank_line_boundary(self):
        import config
        import speech

        config.conf["classicSpeech"]["textProcessingData"]["announceNewLinesDuringSayAll"] = True
        speech.sayAll.SayAllHandler.isRunning = lambda: True
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["first\r\rsecond"]),
            ["first", "new line", "new line", "second"],
        )

    def test_newlines_are_not_changed_outside_say_all(self):
        import config

        config.conf["classicSpeech"]["textProcessingData"]["announceNewLinesDuringSayAll"] = True
        processor = TextProcessor()
        self.assertEqual(processor.process_literal_sequence(["first\nsecond"]), ["first\nsecond"])

    def test_newline_announcement_is_off_by_default_until_ui_exists(self):
        import speech

        speech.sayAll.SayAllHandler.isRunning = lambda: True
        processor = TextProcessor()
        self.assertEqual(processor.process_literal_sequence(["first\nsecond"]), ["first\nsecond"])

    def test_base_processor_applies_newline_message_before_literal_bypass(self):
        import config
        import speech

        config.conf["classicSpeech"]["textProcessingData"]["announceNewLinesDuringSayAll"] = True
        speech.sayAll.SayAllHandler.isRunning = lambda: True
        api.getFocusObject = lambda: types.SimpleNamespace(
            role=types.SimpleNamespace(name="EDITABLETEXT"),
            name="Editor",
            parent=None,
        )
        sequence = ["first\nsecond"]
        BaseSpeechProcessor().process(sequence)
        self.assertEqual(sequence, ["first", "new line", "second"])

    def test_mixed_case_splitting_is_off_by_default(self):
        processor = TextProcessor()
        self.assertEqual(processor.process_literal_sequence(["SayAll"]), ["SayAll"])

    def test_mixed_case_splitting_spec_examples_when_enabled(self):
        import config

        config.conf["classicSpeech"]["textProcessingData"]["splitMixedCaseWords"] = True
        processor = TextProcessor()
        examples = {
            "SayAll": "Say All",
            "helloWorld": "hello World",
            "readOnly": "read Only",
            "NVDAHTTP": "NVDAHTTP",
            "URLParser": "URLParser",
            "item2Value": "item2 Value",
        }
        for input_text, expected_text in examples.items():
            with self.subTest(input_text=input_text):
                self.assertEqual(
                    processor.process_literal_sequence([input_text]),
                    [expected_text],
                )

    def test_mixed_case_splitting_spec_sentence_when_enabled(self):
        import config

        config.conf["classicSpeech"]["textProcessingData"]["splitMixedCaseWords"] = True
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["SayAll helloWorld readOnly NVDAHTTP URLParser item2Value"]),
            ["Say All hello World read Only NVDAHTTP URLParser item2 Value"],
        )

    def test_base_processor_applies_mixed_case_before_literal_bypass(self):
        import config

        config.conf["classicSpeech"]["textProcessingData"]["splitMixedCaseWords"] = True
        api.getFocusObject = lambda: types.SimpleNamespace(
            role=types.SimpleNamespace(name="EDITABLETEXT"),
            name="Editor",
            parent=None,
        )
        sequence = ["helloWorld"]
        BaseSpeechProcessor().process(sequence)
        self.assertEqual(sequence, ["hello World"])

    def test_word_internal_dash_suppression_is_off_by_default(self):
        processor = TextProcessor()
        self.assertEqual(processor.process_literal_sequence(["sister-in-law"]), ["sister-in-law"])

    def test_word_internal_dash_suppression_only_replaces_letter_to_letter_dashes(self):
        import config

        config.conf["classicSpeech"]["textProcessingData"]["suppressWordInternalDashes"] = True
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence([
                "sister-in-law read-only 1-800-444-4443 03-16-00 A-123 123-A"
            ]),
            ["sister in law read only 1-800-444-4443 03-16-00 A-123 123-A"],
        )

    def test_word_internal_dash_suppression_runs_before_mixed_case_splitting(self):
        import config

        config.conf["classicSpeech"]["textProcessingData"]["suppressWordInternalDashes"] = True
        config.conf["classicSpeech"]["textProcessingData"]["splitMixedCaseWords"] = True
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["read-onlySayAll"]),
            ["read only Say All"],
        )

    def test_spell_alphanumeric_data_is_off_by_default(self):
        processor = TextProcessor()
        self.assertEqual(processor.process_literal_sequence(["license 123RON"]), ["license 123RON"])

    def test_spell_alphanumeric_data_spells_plain_mixed_letter_digit_tokens(self):
        import config

        config.conf["classicSpeech"]["textProcessingData"]["spellAlphanumericData"] = "spell"
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["license 123RON AB12CD item42"]),
            ["license 1 2 3 R O N A B 1 2 C D i t e m 4 2"],
        )

    def test_spell_alphanumeric_data_leaves_plain_numbers_and_punctuated_numbers(self):
        import config

        config.conf["classicSpeech"]["textProcessingData"]["spellAlphanumericData"] = "spell"
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["123 2026 03-16-00 2:00 1-800-444-4443"]),
            ["123 2026 03-16-00 2:00 1-800-444-4443"],
        )

    def test_spell_alphanumeric_data_phonetic_mode_spells_plain_mixed_letter_digit_tokens(self):
        import config

        config.conf["classicSpeech"]["textProcessingData"]["spellAlphanumericData"] = "phonetic"
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["license 123RON AB12CD item42"]),
            ["license 1 2 3 Romeo Oscar November Alpha Bravo 1 2 Charlie Delta India Tango Echo Mike 4 2"],
        )

    def test_spell_alphanumeric_data_phonetic_mode_leaves_plain_numbers_and_punctuated_numbers(self):
        import config

        config.conf["classicSpeech"]["textProcessingData"]["spellAlphanumericData"] = "phonetic"
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["123 2026 03-16-00 2:00 1-800-444-4443"]),
            ["123 2026 03-16-00 2:00 1-800-444-4443"],
        )

    def test_spell_alphanumeric_data_runs_before_mixed_case_splitting(self):
        import config

        config.conf["classicSpeech"]["textProcessingData"]["spellAlphanumericData"] = "spell"
        config.conf["classicSpeech"]["textProcessingData"]["splitMixedCaseWords"] = True
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["item2Value SayAll"]),
            ["i t e m 2 V a l u e Say All"],
        )

    def test_hotkey_like_strings_are_not_rewritten_by_early_text_processing(self):
        import config

        config.conf["classicSpeech"]["textProcessingData"]["spellAlphanumericData"] = "spell"
        config.conf["classicSpeech"]["textProcessingData"]["splitMixedCaseWords"] = True
        config.conf["classicSpeech"]["textProcessingData"]["suppressWordInternalDashes"] = True
        config.conf["classicSpeech"]["numberProcessingData"] = {
            "numberProcessingMode": "singleDigits",
            "singleDigitsIfNumberContains": "synthesizer",
        }
        processor = TextProcessor()
        examples = [
            "Alt+1",
            "Ctrl+F12",
            "Alt, N  Ctrl+N",
            "New Window Ctrl+Shift+N",
        ]
        for text in examples:
            with self.subTest(text=text):
                self.assertEqual(processor.process_literal_sequence([text]), [text])

    def test_hotkey_guard_does_not_disable_normal_text_number_processing(self):
        import config

        config.conf["classicSpeech"]["textProcessingData"]["spellAlphanumericData"] = "spell"
        config.conf["classicSpeech"]["numberProcessingData"] = {
            "numberProcessingMode": "singleDigits",
            "singleDigitsIfNumberContains": "synthesizer",
        }
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["license AB12 and 123"]),
            ["license A B one two and one two three"],
        )

    def test_repeated_character_mode_defaults_to_three(self):
        processor = TextProcessor()
        self.assertEqual(processor.process_literal_sequence(["wait!!!!!!"]), ["wait!!!"])

    def test_repeated_character_native_mode_leaves_text_unchanged(self):
        import config

        config.conf["classicSpeech"]["textProcessingData"]["repeatedCharacterMode"] = "native"
        processor = TextProcessor()
        self.assertEqual(processor.process_literal_sequence(["wait!!!!!!"]), ["wait!!!!!!"])

    def test_repeated_character_numeric_modes_do_not_report_spaces(self):
        import config

        processor = TextProcessor()
        examples = {
            "3": ("wait!!!!!!!!!!    indent", ["wait!!!    indent"]),
            "4": ("wait!!!!!!!!!!    indent", ["wait", "exclamation mark exclamation mark exclamation mark exclamation mark", "    indent"]),
            "5": ("wait!!!!!!!!!!    indent", ["wait", "exclamation mark exclamation mark exclamation mark exclamation mark exclamation mark", "    indent"]),
            "6": ("wait!!!!!!!!!!    indent", ["wait", "exclamation mark exclamation mark exclamation mark exclamation mark exclamation mark exclamation mark", "    indent"]),
        }
        for mode, (input_text, expected) in examples.items():
            with self.subTest(mode=mode):
                config.conf["classicSpeech"]["textProcessingData"]["repeatedCharacterMode"] = mode
                self.assertEqual(processor.process_literal_sequence([input_text]), expected)

    def test_repeated_character_modes_above_three_speak_dash_names_explicitly(self):
        import config

        processor = TextProcessor()
        examples = {
            "4": ["dash dash dash dash"],
            "5": ["dash dash dash dash dash"],
            "6": ["dash dash dash dash dash dash"],
        }
        for mode, expected in examples.items():
            with self.subTest(mode=mode):
                config.conf["classicSpeech"]["textProcessingData"]["repeatedCharacterMode"] = mode
                self.assertEqual(processor.process_literal_sequence(["----------\r"]), expected + ["\r"])

    def test_repeated_character_all_mode_speaks_each_repeated_symbol_and_ignores_spaces(self):
        import config

        config.conf["classicSpeech"]["textProcessingData"]["repeatedCharacterMode"] = "all"
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["wait!!!!!!    indent"]),
            [
                "wait",
                "exclamation mark exclamation mark exclamation mark exclamation mark exclamation mark exclamation mark",
                "    indent",
            ],
        )
        self.assertEqual(
            processor.process_literal_sequence(["----------\r"]),
            ["dash dash dash dash dash dash dash dash dash dash", "\r"],
        )

    def test_repeated_character_count_mode_reports_repeated_punctuation_and_spaces(self):
        import config

        config.conf["classicSpeech"]["textProcessingData"]["repeatedCharacterMode"] = "count"
        processor = TextProcessor()
        self.assertEqual(
            processor.process_literal_sequence(["wait!!!!!!    indent"]),
            ["wait", "6 exclamation marks", "4 spaces", "indent"],
        )

    def test_repeated_character_count_mode_uses_readable_plural_labels(self):
        import config

        config.conf["classicSpeech"]["textProcessingData"]["repeatedCharacterMode"] = "count"
        processor = TextProcessor()
        examples = {
            "----": ["4 dashes"],
            "////": ["4 slashes"],
            "\\\\\\\\": ["4 backslashes"],
            "====": ["4 equals signs"],
        }
        for text, expected in examples.items():
            with self.subTest(text=text):
                self.assertEqual(processor.process_literal_sequence([text]), expected)

    def test_repeated_character_modes_ignore_letters_and_numbers(self):
        import config

        processor = TextProcessor()
        examples = {
            "3": ["letter bookkeeper 1000!!!!", ["letter bookkeeper 1000!!!"]],
            "count": ["letter bookkeeper 1000!!!!", ["letter bookkeeper 1000", "4 exclamation marks"]],
        }
        for mode, (input_text, expected) in examples.items():
            with self.subTest(mode=mode):
                config.conf["classicSpeech"]["textProcessingData"]["repeatedCharacterMode"] = mode
                self.assertEqual(processor.process_literal_sequence([input_text]), expected)


class HotkeyExtractorTests(unittest.TestCase):
    def test_v31_right_biased_trailing_menu_shortcut(self):
        label, shortcut = parse_trailing_label_shortcut("New Window Ctrl+Shift+N")
        self.assertEqual(label, "New Window")
        self.assertEqual(shortcut, "Ctrl+Shift+N")

    def test_textual_key_names_are_shortcuts(self):
        label, shortcut = parse_trailing_label_shortcut("Settings... Ctrl+Comma")
        self.assertEqual(label, "Settings...")
        self.assertEqual(shortcut, "Ctrl+Comma")

    def test_multi_shortcut_string_splits_access_and_command_shortcuts(self):
        self.assertEqual(parse_shortcut_list("Alt, N  Ctrl+N"), ["Alt+N", "Ctrl+N"])

    def test_hotkey_format_rejects_hotkey_type_values(self):
        import config

        processor = BaseSpeechProcessor().hotkeys
        for invalid_format in ("access", "command", "both"):
            with self.subTest(invalid_format=invalid_format):
                config.conf["classicSpeech"]["hotkeyFormat"] = invalid_format
                self.assertEqual(processor._get_hotkey_format(), "native")


class ClassifierTests(unittest.TestCase):
    def test_menu_item_with_trailing_shortcut_keeps_name_and_hotkey(self):
        tokens = classify_tokens(["New Window Ctrl+Shift+N", "menu item"], context="menu")
        by_kind = {tok.kind: tok for tok in tokens}
        self.assertEqual(by_kind[TOKEN_NAME].text(), "New Window")
        self.assertEqual(by_kind[TOKEN_ROLE].text().lower(), "menu item")
        self.assertEqual(by_kind[TOKEN_HOTKEY].text(), "Ctrl+Shift+N")

    def test_standalone_position_is_tokenized_but_combined_item_position_is_not(self):
        standalone = classify_tokens(["1 of 5"])
        self.assertEqual(standalone[-1].kind, TOKEN_POSITION)
        combined = classify_tokens(["Recycle Bin 1 of 17"])
        self.assertEqual(combined[0].kind, TOKEN_NAME)
        self.assertEqual(combined[0].text(), "Recycle Bin 1 of 17")

    def test_protected_leading_control_name_prevents_role_misclassification(self):
        tokens = classify_tokens(["Style", "combo box"], protect_first_name=True)
        self.assertEqual(tokens[0].kind, TOKEN_NAME)
        self.assertEqual(tokens[0].text(), "Style")
        self.assertTrue(any(tok.kind == TOKEN_ROLE and tok.text().lower() == "combo box" for tok in tokens))




if __name__ == "__main__":
    unittest.main(verbosity=2)
