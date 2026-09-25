"""Returned-sequence diagnostics must not change voice routing or speech."""
from contextlib import ExitStack
import unittest
from unittest.mock import patch

import classic_speech_compact_toast_harness as toast


class FilterLoggingTests(unittest.TestCase):
    setUp = toast.CompactToastTests.setUp
    tearDown = toast.CompactToastTests.tearDown
    emit = toast.CompactToastTests.emit
    toast = toast.CompactToastTests.toast

    def test_all_processed_early_returns_log_exact_output_only_when_enabled(self):
        routes = (
            ('keyboard', 'wrap_keyboard_entry_sequence', 'typed keyboard/braille entry uses Keyboard profile'),
            ('mouse', 'wrap_mouse_sequence', 'mouse pointer feedback uses Mouse profile'),
            ('system', 'wrap_system_notification_sequence', 'scoped System notification uses System profile'),
            ('systemScript', 'wrap_system_notification_sequence', 'scoped System notification uses System profile'),
            ('status', 'wrap_review_literal_sequence', 'review cursor status uses Review profile'),
            ('object', 'wrap_review_literal_sequence', 'object navigation native sequence uses Review profile'),
            ('review', 'wrap_review_literal_sequence', 'review cursor sequence uses Review profile'),
            ('scheme', None, 'bypass: NVDA text speech carrying scheme marks'),
            ('literal', None, 'bypass: literal review/caret text after text processing'),
        )
        for route, wrapper, message in routes:
            for enabled in (False, True):
                with self.subTest(route=route, enabled=enabled), ExitStack() as stack:
                    for name, active in (
                        ('is_keyboard_entry_profile_routing_active', route == 'keyboard'),
                        ('is_mouse_pointer_profile_routing_active', route == 'mouse'),
                        ('is_system_notification_profile_routing_active', route == 'system'),
                        ('get_object_navigation_processing_enabled', False),
                        ('has_range_marks', route == 'scheme'),
                        ('get_debug_logging_enabled', enabled),
                    ):
                        stack.enter_context(patch.object(self.module, name, return_value=active))
                    for name, active in (
                        ('_is_input_help_active', False),
                        ('_is_system_voice_script_active', route == 'systemScript'),
                        ('_is_review_cursor_status_script_active', route == 'status'),
                        ('_is_object_navigation_script_active', route == 'object'),
                        ('_is_review_cursor_literal_script_active', route == 'review'),
                        ('_is_review_movement_boundary_sequence', False),
                    ):
                        stack.enter_context(patch.object(self.plugin, name, return_value=active))
                    stack.enter_context(patch.object(self.plugin, '_apply_text_processing'))
                    stack.enter_context(patch.object(self.plugin.processor, 'should_process', return_value=False))
                    stack.enter_context(patch.object(self.plugin.processor, 'should_bypass_literal_review', return_value=route == 'literal'))
                    history = stack.enter_context(patch.object(self.plugin, '_record_history'))
                    logger = stack.enter_context(patch.object(self.module.log, 'info'))
                    raw = ['native text', self.command]
                    enter, leave = object(), object()
                    expected = [enter, *raw, leave] if wrapper else raw
                    if wrapper:
                        voice = stack.enter_context(patch.object(self.module, wrapper, return_value=expected))
                    output = self.plugin._filterSpeechSequenceCore(raw)
                    self.assertIs(output, expected)
                    self.assertEqual(raw, ['native text', self.command])
                    history.assert_called_once_with(raw, expected)
                    if wrapper:
                        voice.assert_called_once_with(raw)
                    messages = [call.args[0] for call in logger.call_args_list]
                    outputs = [value for value in messages if value.startswith('ClassicSpeech debug: filter output:')]
                    self.assertEqual(outputs, [f'ClassicSpeech debug: filter output: {expected}'] if enabled else [])
                    if enabled:
                        self.assertTrue(any(message in value for value in messages))
                    else:
                        logger.assert_not_called()

    def test_disabled_logging_does_not_format_new_returned_sequence(self):
        class Returned(list):
            def __str__(self):
                raise AssertionError('debug-disabled output formatted eagerly')
        expected = Returned(['native', self.command])
        with patch.object(self.module, 'get_debug_logging_enabled', return_value=False), \
             patch.object(self.module, 'is_keyboard_entry_profile_routing_active', return_value=True), \
             patch.object(self.module, 'wrap_keyboard_entry_sequence', return_value=expected), \
             patch.object(self.module.log, 'info') as logger:
            self.assertIs(self.plugin._filterSpeechSequenceCore(['native']), expected)
            logger.assert_not_called()

    def test_captured_hermes_toast_logs_compacted_output_and_keeps_real_wrapper(self):
        self.name = 'New notification from Hermes, Hermes finished, Hi Tim! I’m here. What are we working on?.. 1 of 1'
        expected = ['Hermes, Hermes finished, Hi Tim! I’m here. What are we working on?..', self.command]
        baseline = None
        for enabled in (False, True):
            with patch.object(self.module, 'get_debug_logging_enabled', return_value=enabled), \
                 patch.object(self.module.log, 'info') as logger, \
                 patch.object(self.module, 'wrap_system_notification_sequence', wraps=self.module.wrap_system_notification_sequence) as voice:
                self.toast('Toast_win8').event_UIA_toolTipOpened()
                voice.assert_called_once_with(expected)
                self.assertEqual(self.emitted[-1], expected)
                if baseline is None:
                    baseline = self.emitted[-1]
                self.assertEqual(self.emitted[-1], baseline)
                messages = [call.args[0] for call in logger.call_args_list]
                self.assertEqual([m for m in messages if m.startswith('ClassicSpeech debug: filter output:')],
                                 [f'ClassicSpeech debug: filter output: {expected}'] if enabled else [])


if __name__ == '__main__':
    unittest.main()
