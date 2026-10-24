"""Apply label/transaction contracts; native wx owns mnemonic dispatch, not a hook."""
from contextlib import ExitStack
from pathlib import Path
import ast
import sys
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import classic_speech_settings_transactions_harness as transactions


def mnemonics(label):
    result = []
    index = 0
    while index < len(label) - 1:
        if label[index] == '&':
            index += 1
            if label[index] != '&':
                result.append(label[index].casefold())
        index += 1
    return result


def translated_strings(path):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    return [node.args[0].value for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == '_' and node.args
            and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)]


class ApplyMnemonicTests(unittest.TestCase):
    def setUp(self):
        self.fixture = transactions.SettingsDialogTransactionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def test_actual_general_web_constructors_label_and_existing_binding(self):
        import wx
        for dialog_type in self.fixture.dialog_types:
            with self.subTest(dialog=dialog_type.__name__):
                with patch.object(wx.Button, '__init__', autospec=True, return_value=None) as init:
                    dialog = self.fixture._make_bound_dialog(dialog_type)
                labels = [call.kwargs.get('label') for call in init.call_args_list]
                self.assertIn('&Apply', labels)
                self.assertEqual(dialog.bindings[id(dialog.applyBtn)][wx.EVT_BUTTON], [dialog.onApply])
                self.assertNotIn(wx.EVT_CHAR_HOOK, dialog.bindings.get(id(dialog), {}))

    def test_actual_voice_constructor_uses_apply_mnemonic(self):
        import wx
        fixture = transactions.VoiceProfileListEnterTests()
        with patch.object(wx.Button, '__init__', autospec=True, return_value=None) as init:
            dialog = fixture._make_bound_dialog()
        self.assertIn('&Apply', [call.kwargs.get('label') for call in init.call_args_list])
        self.assertEqual(dialog.bindings[id(dialog.applyBtn)][wx.EVT_BUTTON], [dialog.onApply])
        dialog.Destroy.assert_not_called()
        dialog.store.apply.assert_not_called()

    def test_presets_and_schemes_actual_constructor_apply_labels(self):
        import wx
        from globalPlugins._speech_core.settings.presets import dialog as presets
        from globalPlugins._speech_core.settings import schemes_dialog as schemes
        with ExitStack() as stack:
            stack.enter_context(patch.object(wx, 'EVT_WINDOW_DESTROY', object(), create=True))
            stack.enter_context(patch.object(wx, 'ID_APPLY', 5102, create=True))
            stack.enter_context(patch.object(wx, 'StdDialogButtonSizer', Mock(), create=True))
            stack.enter_context(patch.object(wx, 'ALIGN_RIGHT', 0, create=True))
            stack.enter_context(patch.object(presets.PresentationPresetsDialog, '_initializeDialogTransaction'))
            panel = stack.enter_context(patch.object(presets, 'PresentationPresetsPanel'))
            panel.return_value.presetList = wx.ListCtrl(None)
            stack.enter_context(patch.object(schemes, 'SchemeItemsPanel'))
            store = stack.enter_context(patch.object(schemes.schemeStore, 'SchemeStore')).return_value
            store.scheme_names = ['Default']
            store.active_scheme = 'Default'
            with patch.object(wx.Button, '__init__', autospec=True, return_value=None) as init:
                presets.PresentationPresetsDialog(None)
                schemes.SpeechSoundSchemesDialog(None)
            self.assertEqual([call.kwargs.get('label') for call in init.call_args_list].count('&Apply'), 2)

    def test_all_existing_apply_constructors_and_no_new_apply_dialog(self):
        expected = {'ClassicSpeechDialog', 'WebBrowseSettingsDialog', 'VoiceProfilesDialog',
                    'PresentationPresetsDialog', 'SpeechSoundSchemesDialog'}
        actual = set()
        all_dialogs = set()
        for path in (ROOT / '_speech_core').rglob('*.py'):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)
                        and any('Dialog' in ast.unparse(b) for b in n.bases)]:
                all_dialogs.add(cls.name)
                for node in ast.walk(cls):
                    if not isinstance(node, ast.Call) or ast.unparse(node.func) != 'wx.Button':
                        continue
                    for kw in node.keywords:
                        if kw.arg == 'label' and ast.unparse(kw.value) in ("_('Apply')", "_('&Apply')"):
                            actual.add(cls.name)
                            self.assertEqual(ast.literal_eval(kw.value.args[0]), '&Apply', cls.name)
        self.assertEqual(actual, expected)
        self.assertEqual(all_dialogs - actual, {'SpeechHistoryDialog', 'UpdateOfferDialog'})

    def test_active_fixed_panels_do_not_compete_for_alt_a(self):
        # Includes shared formatting/scheme panel and both ways of opening presets.
        paths = [str(path.relative_to(ROOT)) for path in (ROOT / '_speech_core/settings').rglob('*.py')]
        for path in paths:
            labels = [s for s in translated_strings(path) if 'a' in mnemonics(s) and s != '&Apply']
            self.assertEqual(labels, [], path)

    def test_dynamic_driver_alt_a_is_reserved_without_changing_visible_text(self):
        from globalPlugins._speech_core.settings.voice_profile_controls import _label
        for original in ('V&ariant', '&Automatic pause', '日本語 &Alpha', 'R&&D &Audio'):
            result = _label(types.SimpleNamespace(id='custom', displayNameWithAccelerator=original))
            self.assertNotIn('a', mnemonics(result))
            # Literal ampersands, Unicode and display text must survive the reservation.
            self.assertEqual(result.replace('&&', '\0').replace('&', '').replace('\0', '&'),
                             original.replace('&&', '\0').replace('&', '').replace('\0', '&'))
        for original in ('&Rate', 'R&&D', '日本語', 'Volume'):
            self.assertEqual(_label(types.SimpleNamespace(id='custom', displayNameWithAccelerator=original)), original)

    def test_general_web_native_button_command_keeps_apply_transaction_not_ok(self):
        import wx
        for dialog_type in self.fixture.dialog_types:
            dialog = self.fixture._make_bound_dialog(dialog_type)
            dialog.pending = 'applied by native button command'
            handler, = dialog.bindings[id(dialog.applyBtn)][wx.EVT_BUTTON]
            with patch.object(dialog, 'onOK') as ok:
                self.assertTrue(handler(None))
                ok.assert_not_called()
            self.assertEqual(dialog.state, dialog.pending)
            self.assertEqual(dialog.baseline, dialog.pending)
            self.assertEqual(dialog.destroy_count, 0)
            dialog.state = 'later live edit'
            dialog.onCancel(None)
            self.assertEqual(dialog.state, 'applied by native button command')

    def test_voice_native_apply_command_does_not_close_or_force_disk_save(self):
        import wx
        import config
        dialog = transactions.VoiceProfileListEnterTests()._make_bound_dialog()
        with patch.object(config.conf, 'save', create=True) as disk_save:
            handler, = dialog.bindings[id(dialog.applyBtn)][wx.EVT_BUTTON]
            self.assertTrue(handler(None))
            dialog.store.apply.assert_called_once_with()
            dialog.schemeStore.apply.assert_called_once_with()
            dialog.Destroy.assert_not_called()
            disk_save.assert_not_called()

    def test_presets_schemes_bound_apply_commands_keep_existing_transactions(self):
        import wx
        import config
        from globalPlugins._speech_core.settings.presets import dialog as presets
        from globalPlugins._speech_core.settings import schemes_dialog as schemes
        bindings = {}
        def bind(control, kind, handler, *args, **kwargs):
            bindings.setdefault(id(control), {})[kind] = handler
        with ExitStack() as stack:
            stack.enter_context(patch.object(wx.Button, 'Bind', bind, create=True))
            stack.enter_context(patch.object(wx, 'EVT_WINDOW_DESTROY', object(), create=True))
            stack.enter_context(patch.object(wx, 'ID_APPLY', 5102, create=True))
            stack.enter_context(patch.object(wx, 'StdDialogButtonSizer', Mock(), create=True))
            stack.enter_context(patch.object(wx, 'ALIGN_RIGHT', 0, create=True))
            stack.enter_context(patch.object(presets.PresentationPresetsDialog, '_captureTransactionBaseline'))
            stack.enter_context(patch.object(presets.PresentationPresetsDialog, '_saveTransaction'))
            panel = stack.enter_context(patch.object(presets, 'PresentationPresetsPanel'))
            panel.return_value.presetList = wx.ListCtrl(None)
            stack.enter_context(patch.object(schemes, 'SchemeItemsPanel'))
            store = stack.enter_context(patch.object(schemes.schemeStore, 'SchemeStore')).return_value
            store.scheme_names = ['Default']
            store.active_scheme = 'Default'
            for dialog, attr in ((presets.PresentationPresetsDialog(None), 'applyBtn'),
                                 (schemes.SpeechSoundSchemesDialog(None), 'applyButton')):
                with patch.object(config.conf, 'save', create=True) as disk_save, patch.object(dialog, 'Destroy') as close:
                    self.assertTrue(bindings[id(getattr(dialog, attr))][wx.EVT_BUTTON](None))
                    close.assert_not_called()
                    disk_save.assert_not_called()
            store.apply.assert_called_once_with()
            store.mark_applied.assert_called_once_with()

    def test_dirty_visibility_and_last_tab_contracts_unchanged(self):
        import wx
        from globalPlugins._speech_core.settings.presets.dialog import PresentationPresetsDialog
        from globalPlugins._speech_core.settings.voice_profiles_dialog import VoiceProfilesDialog
        from globalPlugins._speech_core.settings.schemes_dialog import SpeechSoundSchemesDialog
        for cls in (*self.fixture.dialog_types, PresentationPresetsDialog, VoiceProfilesDialog, SpeechSoundSchemesDialog):
            dialog = object.__new__(cls)
            button = Mock()
            dialog.applyBtn = dialog.applyButton = button
            dialog.Layout = Mock()
            dialog._markDirty()
            if cls is SpeechSoundSchemesDialog:
                button.Enable.assert_called_once_with()
            else:
                button.Enable.assert_called_once_with(True)
                button.reset_mock()
                dialog._clearDirty()
                button.Enable.assert_called_once_with(False)
            if cls in (PresentationPresetsDialog, VoiceProfilesDialog):
                button.Hide.assert_called_once_with()
            path = ROOT / Path(sys.modules[cls.__module__].__file__)
            if cls is not SpeechSoundSchemesDialog:
                self.assertIn('self.applyBtn.MoveAfterInTabOrder(self.cancelBtn)', path.read_text(encoding='utf-8'))

    def test_category_edit_and_unicode_input_are_not_intercepted(self):
        for cls in self.fixture.dialog_types:
            dialog = self.fixture._make_bound_dialog(cls)
            for key, modifiers in ((65, 1), (65, 0), (0x00e9, 0), (0x3042, 0), (83, 2)):
                event = self.fixture._dispatch_key(dialog, dialog.categoryList, key, modifiers)
                self.assertEqual(event.skips, 1)
            self.assertEqual(dialog.destroy_count, 0)
            self.assertEqual(dialog.state, 'original')


if __name__ == '__main__':
    unittest.main()
