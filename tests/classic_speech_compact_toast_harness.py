"""Source-backed event tests with captured and synthetic speech fixtures."""
import ast
import importlib
import sys
import types
import unittest
from unittest.mock import Mock, patch

import classic_speech_nvda_master_harness as nvda


class CompactToastTests(unittest.TestCase):
    def setUp(self):
        nvda.ClassicSpeechNVDAConfigStartupTests().setUp()
        self.emitted = []
        self.braille = []
        self.clock = 10.0
        self.command = object()
        self.name = "New notification from Example App\nKeep actions in this window"
        nvda.config.conf['presentation'] = {'reportHelpBalloons': True}
        env = dict(
            NVDAObject=object, UIA=type('UIA', (), {}),
            config=nvda.config,
            controlTypes=types.SimpleNamespace(OutputReason=types.SimpleNamespace(FOCUS='focus')),
            speech=types.SimpleNamespace(speakObject=self.emit),
            braille=types.SimpleNamespace(
                handler=types.SimpleNamespace(message=self.braille.append),
                regions=types.SimpleNamespace(properties=types.SimpleNamespace(
                    getPropertiesBraille=lambda **kw: kw))),
            winVersion=types.SimpleNamespace(getWinVer=lambda: 1703, WIN10_1511=1511, WIN10_1703=1703),
            time=types.SimpleNamespace(time=lambda: self.clock),
        )
        for file, names in [('NVDAObjects/behaviors.py', ('Notification',)),
                            ('NVDAObjects/UIA/__init__.py', ('Toast_win8', 'Toast_win10'))]:
            tree = ast.parse((nvda.NVDA_SOURCE / file).read_text(encoding='utf-8-sig'))
            nodes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name in names]
            self.assertEqual(len(nodes), len(names))
            exec(compile(ast.Module(body=nodes, type_ignores=[]), file, 'exec'), env)
        self.uia = types.ModuleType('NVDAObjects.UIA')
        for name in ('Toast_win8', 'Toast_win10'):
            setattr(self.uia, name, env[name])
        self.modules = patch.dict(sys.modules, {'NVDAObjects.UIA': self.uia,
                                               'NVDAObjects': types.SimpleNamespace(UIA=self.uia)})
        self.modules.start()
        self.module = nvda._import_classic_speech_like_nvda()
        self.plugin = self.module.GlobalPlugin()
        self.runtime = importlib.import_module(self.module.__package__ + '._speech_core.compact_toasts')

    def tearDown(self):
        if hasattr(self, 'plugin'):
            self.plugin.terminate()
        self.modules.stop()
        nvda._reset_global_plugin_imports()
        nvda.speech.extensions.filter_speechSequence.callbacks.clear()
        nvda.globalPluginHandler.runningPlugins.clear()

    def emit(self, obj, **kwargs):
        sequence = [obj.name, 'window', self.command]
        for callback in list(nvda.speech.extensions.filter_speechSequence.callbacks):
            sequence = callback(sequence)
        self.emitted.append(sequence)

    def toast(self, cls='Toast_win10'):
        obj = getattr(self.uia, cls)()
        obj.name = self.name
        obj.role = 'window'
        obj.UIAElement = types.SimpleNamespace(getRuntimeID=lambda: (1, 2, 3))
        return obj

    def test_captured_comma_shape_strips_prefix_and_terminal_scaffolding(self):
        self.name = 'New notification from Hermes, Hermes finished, Hi Tim! What’s up?.. 1 of 1'
        obj = self.toast()
        obj.event_UIA_window_windowOpen()
        self.assertEqual(self.emitted[-1],
                         ['Hermes, Hermes finished, Hi Tim! What’s up?..', self.command])
        self.assertEqual(obj.name, self.name)
        self.assertIs(self.emitted[-1][-1], self.command)

    def test_terminal_count_matrix_preserves_body_and_commands(self):
        body = 'Hermes, Actions window 2 of 9, New notification from body...'
        enter, middle, exit = object(), object(), object()
        for count in ('1 of 1', '2 of 12', '123 of 456', '0 of 0', '01 of 002'):
            for actions in ('', ' . Actions.'):
                for prefix in ('', 'New notification from '):
                    with self.subTest(count=count, actions=actions, prefix=prefix):
                        self.name = prefix + body + actions + ' ' + count
                        obj = self.toast()
                        raw = [enter, obj.name, middle, 'window', exit]
                        with self.runtime.toast_scope(obj):
                            output = self.runtime.transform(raw)
                        self.assertEqual(output, [enter, body, middle, exit])
                        self.assertEqual(raw, [enter, self.name, middle, 'window', exit])
                        self.assertEqual(obj.name, self.name)

    def test_count_cleanup_does_not_consume_adjacent_message_words(self):
        for body in ('App, Actions', 'App, Actions.', 'App, window',
                     'App, 2 of 9', 'App, . actions.', 'App, . Actions. More',
                     'App\r\nActions window\r\nmessage...'):
            self.name = 'New notification from ' + body + ' 12 of 123'
            with self.subTest(body=body), self.runtime.toast_scope(self.toast()):
                self.assertEqual(self.runtime.transform([self.name, 'window']), [body])

    def test_live_suffix_fixtures_preserve_routing_history_and_braille(self):
        fixtures = (
            ('Hermes, ClassicSpeech automated test CS-T02, Body says New notification from another app. Keep this text...', ''),
            ('Hermes, ClassicSpeech automated test CS-T03, Actions and window are message words. Keep them...', ' . Actions.'),
        )
        enter, exit = object(), object()
        for body, actions in fixtures:
            self.name = 'New notification from ' + body + actions + ' 1 of 1'
            obj = self.toast('Toast_win8')
            self.plugin._record_history = Mock()
            with patch.object(self.module, 'wrap_system_notification_sequence',
                              side_effect=lambda seq: [enter] + list(seq) + [exit]) as voice, \
                 patch.object(self.module.scheme_runtime, 'apply_schemes', side_effect=lambda seq: seq) as scheme:
                obj.event_UIA_toolTipOpened()
                voice.assert_called_once_with([body, self.command])
                scheme.assert_called_once_with([enter, body, self.command, exit])
            self.assertEqual(self.emitted[-1], [enter, body, self.command, exit])
            self.assertEqual(self.plugin._record_history.call_args.args[0],
                             [self.name, 'window', self.command])
            self.assertEqual(self.braille[-1], {'name': self.name, 'role': 'window'})
            self.assertEqual(obj.name, self.name)

    def test_unknown_terminal_shapes_keep_existing_prefix_only_behavior(self):
        for suffix in ('', ' . Actions.', ' 1 of 1 window', ' 1 of 1 ',
                       ' 1 of 1\n', ' one of two', ' 1 OF 2', ' 1 of\t2',
                       ' -1 of 2', ' 1.5 of 2', ' １ of ２'):
            self.name = 'New notification from App, body' + suffix
            obj = self.toast()
            with self.runtime.toast_scope(obj):
                self.assertEqual(self.runtime.transform([obj.name, 'window']),
                                 [self.name.removeprefix('New notification from '), 'window'])
        self.name = 'New notification from App, body 1 of 1'
        obj = self.toast()
        for raw in ([obj.name], [obj.name, 'Window'], [obj.name, 'window', 'extra'],
                    [obj.name, 'extra', 'window'], ['extra', obj.name, 'window'],
                    ['window', obj.name], [obj.name, 'window', 'window']):
            with self.subTest(raw=raw), self.runtime.toast_scope(obj):
                expected = [self.runtime.compact_name(x) if x == obj.name else x for x in raw]
                self.assertEqual(self.runtime.transform(raw), expected)
        duplicate = [obj.name, obj.name, 'window']
        with self.runtime.toast_scope(obj):
            self.assertIs(self.runtime.transform(duplicate), duplicate)
        raw = [obj.name, 'window']
        self.assertIs(self.runtime.transform(raw), raw)
        with self.runtime.toast_scope(obj):
            mismatch = ['New notification from another app 1 of 1', 'window']
            self.assertIs(self.runtime.transform(mismatch), mismatch)

    def test_suffix_hook_disabled_is_native(self):
        self.name = 'New notification from App, body . Actions. 2 of 12'
        self.plugin.set_speech_hook_enabled(False)
        self.toast('Toast_win8').event_UIA_toolTipOpened()
        self.assertEqual(self.emitted[-1], [self.name, 'window', self.command])
        self.plugin.set_speech_hook_enabled(True)
        self.toast('Toast_win8').event_UIA_toolTipOpened()
        self.assertEqual(self.emitted[-1], ['App, body', self.command])

    def test_compaction_preserves_system_profile_and_scheme_calls(self):
        self.plugin.processor.process = Mock(side_effect=AssertionError('generic processor'))
        self.plugin._apply_text_processing = Mock(side_effect=AssertionError('text processor'))
        for prefixed in (False, True):
            with self.subTest(prefixed=prefixed):
                self.name = ("New notification from " if prefixed else "") + "Example App\nKeep actions in this window"
                expected = "Example App\nKeep actions in this window"
                with patch.object(self.module, 'wrap_system_notification_sequence',
                                  side_effect=lambda seq: ['system profile'] + list(seq)) as voice, \
                     patch.object(self.module.scheme_runtime, 'apply_schemes',
                                  side_effect=lambda seq: list(seq) + ['scheme result']) as scheme:
                    self.toast('Toast_win8').event_UIA_toolTipOpened()
                    voice.assert_called_once_with([expected, 'window', self.command])
                    scheme.assert_called_once_with(['system profile', expected, 'window', self.command])
                    self.assertEqual(self.emitted[-1],
                                     ['system profile', expected, 'window', self.command, 'scheme result'])
                self.assertEqual(self.braille[-1], {'name': self.name, 'role': 'window'})
                self.assertIsNone(self.runtime.current_toast())

    def test_notification_disable_and_native_dedupe(self):
        obj = self.toast()
        nvda.config.conf['presentation']['reportHelpBalloons'] = False
        obj.event_UIA_window_windowOpen()
        self.assertEqual(self.emitted, [])
        self.assertEqual(self.braille, [])
        self.clock += 2
        nvda.config.conf['presentation']['reportHelpBalloons'] = True
        obj.event_UIA_window_windowOpen()
        obj.event_UIA_window_windowOpen()
        self.assertEqual(len(self.emitted), 1)
        self.assertEqual(len(self.braille), 1)

    def test_win8_alias_is_scoped(self):
        self.toast('Toast_win8').event_UIA_toolTipOpened()
        self.assertEqual(self.emitted[0][0], 'Example App\nKeep actions in this window')

    def test_hook_disabled_is_exact_native(self):
        self.plugin.set_speech_hook_enabled(False)
        self.toast().event_UIA_window_windowOpen()
        self.assertEqual(self.emitted, [[self.name, 'window', self.command]])
        self.assertIsNone(self.runtime.current_toast())
        self.plugin.set_speech_hook_enabled(True)
        self.clock += 2
        self.toast().event_UIA_window_windowOpen()
        self.assertEqual(self.emitted[-1][0], 'Example App\nKeep actions in this window')

    def test_absent_or_nonleading_prefix_is_unchanged(self):
        for value in ('App, ordinary notice Actions window',
                      'Nouvelle notification de App\nmessage',
                      'Body says New notification from App',
                      ' New notification from App', 'new notification from App'):
            with self.subTest(value=value):
                self.name = value
                self.toast('Toast_win8').event_UIA_toolTipOpened()
                self.assertEqual(self.emitted[-1], [value, 'window', self.command])

    def test_format_preserves_body_and_suffix(self):
        for remainder in ('App, message Actions Close window',
                          'App\nNew notification from Body\nActions Close window',
                          'App', '\nmessage', 'App\n', ''):
            with self.subTest(remainder=remainder):
                self.assertEqual(self.runtime.compact_name('New notification from ' + remainder), remainder)

    def test_only_exact_emitted_name_is_replaced(self):
        obj = self.toast()
        # A wrapper's scope does not authorize rewriting arbitrary fragments.
        with self.runtime.toast_scope(obj):
            self.assertEqual(self.runtime.transform(['prefix ' + obj.name]), ['prefix ' + obj.name])
            duplicate = [obj.name, self.command, obj.name]
            self.assertIs(self.runtime.transform(duplicate), duplicate)
        self.assertIsNone(self.runtime.current_toast())

    def test_exception_and_nested_scope_reset(self):
        outer, inner = self.toast(), self.toast()
        with self.runtime.toast_scope(outer):
            self.assertIs(self.runtime.current_toast(), outer)
            with self.assertRaises(RuntimeError):
                with self.runtime.toast_scope(inner):
                    raise RuntimeError('native failure')
            self.assertIs(self.runtime.current_toast(), outer)
        self.assertIsNone(self.runtime.current_toast())

    def test_ordinary_speech_never_enters_toast_transform(self):
        with patch.object(self.runtime, 'compact_name', side_effect=AssertionError('not a toast')):
            self.plugin._filterSpeechSequence([self.name])

    def test_history_retains_original_name(self):
        self.plugin._record_history = Mock()
        self.toast().event_UIA_window_windowOpen()
        raw, emitted = self.plugin._record_history.call_args.args
        self.assertEqual(raw, [self.name, 'window', self.command])
        self.assertEqual(emitted[0], 'Example App\nKeep actions in this window')

    def test_removed_setting_is_not_registered_and_stale_values_are_ignored(self):
        config = importlib.import_module(self.module.__package__ + '._speech_core.plugin_config')
        self.assertNotIn('compactWindowsToasts', config._CLASSIC_SPEECH_SPEC)
        section = nvda.config.conf.profiles[0]['classicSpeech']
        section.pop('compactWindowsToasts', None)
        for value in (None, False, True, 'False', 'True', 'garbage'):
            with self.subTest(value=value):
                if value is not None:
                    section['compactWindowsToasts'] = value
                self.toast('Toast_win8').event_UIA_toolTipOpened()
                self.assertEqual(self.emitted[-1],
                                 ['Example App\nKeep actions in this window', 'window', self.command])

    def test_native_handler_exception_resets_wrapper_scope(self):
        obj = self.toast('Toast_win8')
        # This is the real extracted native event body, with its speech call failing.
        native = self.uia.Toast_win8.event_UIA_toolTipOpened.__wrapped__.__wrapped__
        with patch.object(native.__globals__['speech'], 'speakObject', side_effect=RuntimeError('native')):
            with self.assertRaises(RuntimeError):
                obj.event_UIA_toolTipOpened()
        self.assertIsNone(self.runtime.current_toast())

    def test_install_is_idempotent_and_reload_restores_identity(self):
        cls = self.uia.Toast_win8
        wrapper = cls.event_UIA_toolTipOpened
        original = wrapper.__wrapped__
        self.plugin._toastArrival.install()
        self.assertIs(cls.event_UIA_toolTipOpened, wrapper)
        self.plugin._toastArrival.restore()
        self.assertIs(cls.event_UIA_toolTipOpened, original)
        fresh = self.runtime.ToastArrivalRuntime(lambda: True, self.module.log)
        fresh.install()
        try:
            self.toast('Toast_win8').event_UIA_toolTipOpened()
            self.assertEqual(self.emitted[-1][0], 'Example App\nKeep actions in this window')
        finally:
            fresh.restore()
        self.assertIs(cls.event_UIA_toolTipOpened, original)

    def test_terminate_restores_both_wrappers_and_reload(self):
        originals = [(cls, event, original) for cls, event, marker, original, wrapper
                     in self.plugin._windowsToastRoutes]
        self.assertEqual({(cls.__name__, event) for cls, event, _ in originals},
                         {('Toast_win8', 'event_UIA_toolTipOpened'),
                          ('Toast_win10', 'event_UIA_window_windowOpen')})
        self.plugin.terminate()
        for cls, event, original in originals:
            self.assertIs(getattr(cls, event), original)
            self.assertFalse(hasattr(cls, '_classicSpeechToastRoute_' + event))
        self.plugin = self.module.GlobalPlugin()
        with patch.object(self.module, 'wrap_system_notification_sequence',
                          side_effect=lambda seq: ['system profile'] + list(seq)) as voice:
            self.toast('Toast_win8').event_UIA_toolTipOpened()
            voice.assert_called_once()
            self.assertEqual(self.emitted[-1][0:2],
                             ['system profile', 'Example App\nKeep actions in this window'])
        self.plugin.terminate()
        for cls, event, original in originals:
            self.assertIs(getattr(cls, event), original)

    def test_ordinary_notification_unchanged(self):
        with patch.object(self.module, 'wrap_system_notification_sequence',
                          side_effect=lambda seq: ['system profile'] + list(seq)) as voice:
            with self.module.system_notification_profile_routing():
                output = self.plugin._filterSpeechSequence([self.name, self.command])
            voice.assert_called_once_with([self.name, self.command])
        self.assertEqual(output, ['system profile', self.name, self.command])
        raw = [self.name, 'window', self.command]
        self.assertIs(self.runtime.transform(raw), raw)

    def test_message_end_and_profile_commands_keep_baseline_order(self):
        enter, exit = object(), object()
        end = self.module.message_priority.MessageSpoken(lambda token: None, 1)
        obj = self.toast()
        expected = 'Example App\nKeep actions in this window'
        with self.runtime.toast_scope(obj), self.module.system_notification_profile_routing(), \
             patch.object(self.module, 'wrap_system_notification_sequence',
                          side_effect=lambda seq: [enter] + list(seq) + [exit]) as voice, \
             patch.object(self.module.scheme_runtime, 'apply_schemes',
                          side_effect=lambda seq: seq) as schemes:
            output = self.plugin._filterSpeechSequence([self.name, self.command, end])
            self.assertEqual(output, [enter, expected, end, self.command, exit])
            voice.assert_called_once_with([expected, self.command])
            schemes.assert_called_once_with([enter, expected, self.command, exit])

    def test_toast_context_does_not_override_keyboard_route_precedence(self):
        with self.runtime.toast_scope(self.toast()), self.module.system_notification_profile_routing(), \
             self.module.keyboard_entry_profile_routing(), \
             patch.object(self.module, 'wrap_keyboard_entry_sequence',
                          side_effect=lambda seq: ['keyboard profile'] + list(seq)) as keyboard, \
             patch.object(self.module, 'wrap_system_notification_sequence') as system:
            self.assertEqual(self.plugin._filterSpeechSequence([self.name]),
                             ['keyboard profile', self.name])
            keyboard.assert_called_once_with([self.name])
            system.assert_not_called()

    def test_commands_and_crlf_body_are_preserved(self):
        self.name = 'New notification from App\r\n  message\r\nActions window  '
        obj = self.toast()
        with self.runtime.toast_scope(obj):
            raw = [self.command, obj.name, self.command]
            self.assertEqual(self.runtime.transform(raw),
                             [self.command, 'App\r\n  message\r\nActions window  ', self.command])
            self.assertEqual(raw[1], self.name)

    def test_restore_does_not_overwrite_later_wrapper(self):
        cls = self.uia.Toast_win8
        wrapped = cls.event_UIA_toolTipOpened
        def later(obj):
            return wrapped(obj)
        cls.event_UIA_toolTipOpened = later
        self.plugin.terminate()
        self.assertIs(cls.event_UIA_toolTipOpened, later)
        later(self.toast('Toast_win8'))
        self.assertIsNone(self.runtime.current_toast())


if __name__ == '__main__':
    unittest.main()
