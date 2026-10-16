"""Execute NVDA master's actual native title command, without UI or live config."""
import ast
import importlib
import types
import unittest
from unittest.mock import patch

import classic_speech_nvda_master_harness as nvda


class TitleWindowStateTests(unittest.TestCase):
    def setUp(self):
        nvda.ClassicSpeechNVDAConfigStartupTests().setUp()
        self.pluginModule = nvda._import_classic_speech_like_nvda()
        self.runtime = importlib.import_module('globalPlugins._speech_core.title_window_state')
        self.config = importlib.import_module('globalPlugins._speech_core.settings.misc_config')
        self.section = nvda.config.conf.profiles[0].setdefault('classicSpeech', {})
        self.messages = []
        self.spelled = []
        self.copied = []
        self.lookups = []
        self.queries = []
        self.repeat = 0
        self.locked = False
        self.obj = types.SimpleNamespace(name='normal report maximized', windowHandle=123,
                                         appModule=types.SimpleNamespace(appName='fallback app'))
        def foreground():
            self.lookups.append(self.obj)
            return self.obj
        tree = ast.parse((nvda.NVDA_SOURCE / 'globalCommands.py').read_text(encoding='utf-8-sig'))
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'GlobalCommands')
        method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == 'script_title')
        method.decorator_list = []
        method.returns = None
        for arg in method.args.args:
            arg.annotation = None
        self.ui = types.SimpleNamespace(message=lambda text, *a, **k: self.messages.append(text))
        self.api = types.SimpleNamespace(getForegroundObject=foreground,
            copyToClip=lambda text, **kw: self.copied.append((text, kw)))
        env = dict(api=self.api, ui=self.ui,
            speech=types.SimpleNamespace(speakSpelling=self.spelled.append),
            getLastScriptRepeatCount=lambda: self.repeat,
            objectBelowLockScreenAndWindowsIsLocked=lambda obj: self.locked,
            gui=types.SimpleNamespace(blockAction=types.SimpleNamespace(Context=types.SimpleNamespace(
                WINDOWS_LOCKED=types.SimpleNamespace(translatedMessage='locked')))), _=lambda text: text)
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<native title>', 'exec'), env)
        self.original = env['script_title']
        self.original.gestures = ['kb:NVDA+t']
        self.target = type('Commands', (), {'script_title': self.original})
        self.state = 'maximized'
        def query(handle):
            self.queries.append(handle)
            return self.state
        self.queryPatch = patch.object(self.runtime, 'get_window_state', query)
        self.queryPatch.start()
        self.commands = self.target()
        # NVDA binds function identities at instance construction, before plugins load.
        self.commands._gestureMap = {'kb:nvda+t': self.original, 'kb:custom': self.original,
                                    'kb:unrelated': lambda: None}
        self.route = self.runtime.TitleWindowStateRuntime(self.target, self.commands)
        self.route.install()

    def tearDown(self):
        self.route.restore()
        self.queryPatch.stop()
        nvda._reset_global_plugin_imports()

    def runTitle(self):
        return self.commands._gestureMap['kb:nvda+t'].__get__(self.commands, self.target)(None)

    def enable(self, value=True):
        self.config._set_include_window_state_in_title(value)

    def test_default_off_native_identity_and_no_query(self):
        self.runTitle()
        self.assertEqual(self.messages, [self.obj.name])
        self.assertIs(self.messages[0], self.obj.name)
        self.assertEqual(self.queries, [])
        self.assertEqual(self.target.script_title.gestures, ['kb:NVDA+t'])
        self.assertEqual(self.target.script_title.__name__, 'script_title')

    def test_states_preserve_literal_title_and_same_native_object(self):
        self.enable()
        for state in ('normal', 'maximized', 'minimized'):
            self.state = state
            self.runTitle()
            self.assertEqual(self.messages[-1], self.obj.name + ', ' + state)
        self.assertEqual(self.lookups, [self.obj] * 3)
        self.assertEqual(self.queries, [123] * 3)

    def test_unknown_failure_and_invalid_handle_native(self):
        self.enable()
        for state in (None, 'unknown'):
            self.state = state
            self.runTitle()
            self.assertEqual(self.messages[-1], self.obj.name)
        with patch.object(self.runtime, 'get_window_state', side_effect=OSError('failure')):
            self.runTitle()
            self.assertEqual(self.messages[-1], self.obj.name)
        for handle in (None, 0, -1, '123'):
            self.obj.windowHandle = handle
            self.runTitle()
            self.assertEqual(self.messages[-1], self.obj.name)
        del self.obj.windowHandle
        self.runTitle()
        self.assertEqual(self.messages[-1], self.obj.name)

    def test_repeat_spelling_and_copy_remain_native_title_only(self):
        self.enable()
        for repeat in (1, 2, 3):
            self.repeat = repeat
            self.runTitle()
        self.assertEqual(self.spelled, [self.obj.name])
        self.assertEqual(self.copied, [(self.obj.name, {'notify': True})] * 2)
        self.assertEqual(self.messages, [])
        self.assertEqual(self.queries, [])

    def test_lock_screen_native_guard_never_queries_or_formats(self):
        self.enable()
        self.locked = True
        self.runTitle()
        self.assertEqual(self.messages, ['locked'])
        self.assertEqual(self.queries, [])

    def test_native_fallback_app_and_no_title(self):
        self.enable()
        self.obj.name = ' '
        self.runTitle()
        self.assertEqual(self.messages[-1], 'fallback app, maximized')
        self.obj.appModule = None
        self.runTitle()
        self.assertEqual(self.messages[-1], 'No title, maximized')

    def test_no_shared_patch_and_exception_cleanup(self):
        self.enable()
        originalMessage = self.ui.message
        originalForeground = self.api.getForegroundObject
        def reentrant(handle):
            self.ui.message('unrelated normal maximized')
            self.assertIs(self.ui.message, originalMessage)
            self.assertIs(self.api.getForegroundObject, originalForeground)
            return 'normal'
        with patch.object(self.runtime, 'get_window_state', reentrant):
            self.runTitle()
        self.assertEqual(self.messages, ['unrelated normal maximized', self.obj.name + ', normal'])
        with patch.object(self.ui, 'message', side_effect=RuntimeError('native failure')):
            with self.assertRaises(RuntimeError):
                self.runTitle()
        self.assertIs(self.ui.message, originalMessage)
        self.runTitle()
        self.assertEqual(self.messages[-1], self.obj.name + ', maximized')

    def test_live_setting_and_string_false_reload(self):
        for value, expected in ((True, ', maximized'), (False, ''), ('False', ''), ('True', ', maximized')):
            self.section['includeWindowStateInTitle'] = value
            self.runTitle()
            self.assertEqual(self.messages[-1], self.obj.name + expected)
        nvda.config.conf.profiles[0]['classicSpeech'] = {'includeWindowStateInTitle': 'False'}
        self.runTitle()
        self.assertEqual(self.messages[-1], self.obj.name)

    def test_identity_safe_reload_and_later_patch(self):
        second = self.runtime.TitleWindowStateRuntime(self.target, self.commands)
        second.install()
        self.route.restore()
        self.enable()
        self.runTitle()
        self.assertEqual(self.messages[-1], self.obj.name + ', maximized')
        second.restore()
        self.assertIs(self.target.script_title, self.original)
        self.assertIs(self.commands._gestureMap['kb:nvda+t'], self.original)
        self.assertIs(self.commands._gestureMap['kb:custom'], self.original)
        self.route.install()
        later = lambda *args: None
        self.target.script_title = later
        self.route.restore()
        self.assertIs(self.target.script_title, later)

    def test_win32_mapping_failure_is_not_normal(self):
        self.queryPatch.stop()
        try:
            for show, expected in ((1, 'normal'), (2, 'minimized'), (3, 'maximized'),
                                   (6, 'minimized'), (7, 'minimized'), (11, 'minimized'), (99, None)):
                def placement(handle, pointer):
                    pointer._obj.showCmd = show
                    return 1
                with patch.object(self.runtime, '_get_window_placement', placement):
                    self.assertEqual(self.runtime.get_window_state(123), expected)
            with patch.object(self.runtime, '_get_window_placement', lambda *args: 0):
                self.assertIsNone(self.runtime.get_window_state(123))
            with patch.object(self.runtime, '_get_window_placement', None):
                self.assertIsNone(self.runtime.get_window_state(123))
        finally:
            self.queryPatch.start()

    def test_plugin_installs_existing_native_binding_and_terminates(self):
        import globalCommands
        self.route.restore()
        with patch.object(globalCommands, 'GlobalCommands', self.target, create=True), patch.object(
            globalCommands, 'commands', self.commands
        ):
            plugin = self.pluginModule.GlobalPlugin()
            try:
                self.enable()
                self.runTitle()
                self.assertEqual(self.messages[-1], self.obj.name + ', maximized')
            finally:
                plugin.terminate()
            self.assertIs(self.target.script_title, self.original)
            self.assertIs(self.commands._gestureMap['kb:nvda+t'], self.original)

    def test_misc_real_checkbox_dirty_apply_ok_cancel_close_and_reload(self):
        import os
        import tempfile
        from pathlib import Path
        from contextlib import ExitStack
        from configobj import ConfigObj
        import wx
        module = importlib.import_module('globalPlugins._speech_core.settings.dialog')
        settings = importlib.import_module('globalPlugins._speech_core.settings_file')
        backup = importlib.import_module('globalPlugins._speech_core.nvda_settings_backup')
        class CheckBox:
            def __init__(self, parent, label):
                self.label, self.value, self.bindings = label, False, {}
            def SetValue(self, value): self.value = value
            def GetValue(self): return self.value
            def Bind(self, event, callback): self.bindings[event] = callback
        scratch = Path(os.environ.get('LOCALAPPDATA', tempfile.gettempdir())) / 'hermes/cache/scratch'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as folder, ExitStack() as stack:
            stack.enter_context(patch.object(backup, '_CONFIG_FOLDER_OVERRIDE', folder))
            stack.enter_context(patch.object(wx, 'CheckBox', CheckBox))
            writer = stack.enter_context(patch.object(settings, 'write_settings_file', wraps=settings.write_settings_file))
            for accept in ('onApply', 'onOK'):
                for close in ('onCancel', 'onClose'):
                    self.enable(False)
                    dialog = object.__new__(module.ClassicSpeechDialog)
                    dialog._popupReleased = False
                    dialog._committed = False
                    dialog._initializeDialogTransaction()
                    dialog.dirty = 0
                    dialog._markDirty = lambda: setattr(dialog, 'dirty', dialog.dirty + 1)
                    dialog._clearDirty = lambda: None
                    dialog.Destroy = lambda: None
                    stack.enter_context(patch.object(wx, 'GetTopLevelParent', lambda panel: dialog, create=True))
                    panel = module.MiscPanel(None)
                    dialog._saveTransaction = lambda: panel.apply_live()
                    checkbox = panel.includeWindowStateInTitle
                    self.assertEqual(checkbox.label, 'Include window state when reporting the title')
                    self.assertIs(checkbox.GetValue(), False)
                    def toggle(value):
                        checkbox.SetValue(value)
                        checkbox.bindings[wx.EVT_CHECKBOX](None)
                        self.runTitle()
                        self.assertEqual(self.messages[-1], self.obj.name + (', maximized' if value else ''))
                    toggle(True)
                    self.assertEqual(dialog.dirty, 1)
                    getattr(dialog, close)(types.SimpleNamespace(Skip=lambda: None))
                    self.runTitle()
                    self.assertEqual(self.messages[-1], self.obj.name)
                    toggle(True)
                    getattr(dialog, accept)(None)
                    toggle(False)
                    getattr(dialog, close)(types.SimpleNamespace(Skip=lambda: None))
                    self.runTitle()
                    self.assertEqual(self.messages[-1], self.obj.name + ', maximized')
                    self.assertEqual(writer.call_count, 0, 'Apply/OK must not force disk persistence')
            # NVDA's external save invokes the registered settings-file boundary.
            base = ConfigObj()
            base.filename = str(Path(folder) / 'nvda.ini')
            conf = types.SimpleNamespace(profiles=[base])
            with patch.object(nvda.config, 'conf', conf):
                settings.load_into_nvda(conf)
                self.enable(True)
                base.write()
                self.assertNotIn(b'includeWindowStateInTitle', Path(base.filename).read_bytes())
                conf.profiles = [ConfigObj(base.filename, encoding='utf-8')]
                settings.load_into_nvda(conf)
                self.runTitle()
                self.assertEqual(self.messages[-1], self.obj.name + ', maximized')
                self.enable(False)
                conf.profiles[0].write()
                conf.profiles = [ConfigObj(base.filename, encoding='utf-8')]
                settings.load_into_nvda(conf)
                self.runTitle()
                self.assertEqual(self.messages[-1], self.obj.name)


if __name__ == '__main__':
    unittest.main()
