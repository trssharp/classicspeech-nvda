"""Exercise real Presets, Token Editor, Timing and General transaction methods."""
import copy
import sys
import types
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import classic_speech_nvda_master_harness as harness


class PresetUITests(unittest.TestCase):
    def setUp(self):
        harness.ClassicSpeechNVDAConfigStartupTests().setUp()
        module = harness._import_classic_speech_like_nvda()
        self.plugin = module.GlobalPlugin()
        import globalPluginHandler
        globalPluginHandler.runningPlugins.append(self.plugin)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self._controls()

    def tearDown(self):
        import globalPluginHandler
        self.plugin.terminate()
        globalPluginHandler.runningPlugins.clear()
        harness._reset_global_plugin_imports()

    def _controls(self):
        import wx
        base = wx.Panel.__mro__[1]
        original_init = base.__init__
        def init(c, *args, **kwargs):
            original_init(c, *args, **kwargs)
            c.__dict__['value'] = kwargs.get('value', False)
            c.__dict__['items'] = [(s, None) for s in kwargs.get('choices', [])]
        self.stack.enter_context(patch.object(base, '__init__', init))
        def state(c):
            return c.__dict__
        def append(c, text, clientData=None):
            state(c).setdefault('items', []).append((text, clientData))
        def bind(c, kind, handler, *a, **kw):
            state(c).setdefault('bindings', {})[kind] = handler
        methods = {
            'ChangeValue': lambda c, v: state(c).update(value=v),
            'Bind': bind,
            'Check': lambda c, i, check=True: state(c).setdefault('checked', set()).add(i) if check else state(c).setdefault('checked', set()).discard(i),
            'GetCheckedItems': lambda c: tuple(state(c).get('checked', set())),
            'SetCheckedItems': lambda c, rows: state(c).update(checked=set(rows)),
            'Append': append,
            'Clear': lambda c: state(c).update(items=[]),
            'DeleteAllItems': lambda c: state(c).update(items=[]),
            'SetItems': lambda c, items: state(c).update(items=[(t, None) for t in items]),
            'GetCount': lambda c: len(state(c).get('items', [])),
            'GetClientData': lambda c, i: c.items[i][1],
            'GetString': lambda c, i: c.items[i][0],
            'SetSelection': lambda c, i: state(c).update(selection=i),
            'Select': lambda c, i: state(c).update(selection=i),
            'GetSelection': lambda c: state(c).get('selection', -1),
            'GetFirstSelected': lambda c: state(c).get('selection', -1),
            'SetValue': lambda c, v: state(c).update(value=v),
            'GetValue': lambda c: state(c).get('value', False),
            'SetLabel': lambda c, s: state(c).update(label=s),
            'Enable': lambda c, v=True: state(c).update(enabled=v),
            'Hide': lambda c: state(c).update(shown=False),
            'Show': lambda c, v=True: state(c).update(shown=v),
            'SetupScrolling': lambda c, **kw: state(c).update(scrolling=kw),
        }
        for name, method in methods.items():
            self.stack.enter_context(patch.object(base, name, method, create=True))
        for name in ('EVT_WINDOW_DESTROY', 'OK', 'ICON_ERROR', 'ALIGN_TOP'):
            self.stack.enter_context(patch.object(wx, name, 0, create=True))

    def section(self):
        import config
        return config.conf.profiles[0]['classicSpeech']

    def dialog(self):
        import wx
        from globalPlugins._speech_core.settings.presets.dialog import PresentationPresetsDialog
        d = object.__new__(PresentationPresetsDialog)
        self.stack.enter_context(patch.object(wx, 'GetTopLevelParent', lambda p: d, create=True))
        PresentationPresetsDialog.__init__(d, None)
        d.Destroy = Mock()
        return d

    def general_dialog(self):
        import wx
        from globalPlugins._speech_core.settings import dialog as module
        d = object.__new__(module.ClassicSpeechDialog)
        self.stack.enter_context(patch.object(wx, 'GetTopLevelParent', lambda p: d, create=True))
        for name in ('TextProcessingPanel', 'NumberProcessingPanel',
                     'DocumentReadingProofingPanel', 'AdvancedPanel'):
            self.stack.enter_context(patch.object(module, name, wx.Panel))
        module.ClassicSpeechDialog.__init__(d, None)
        d.Destroy = Mock()
        return d

    def event(self):
        return types.SimpleNamespace(Skip=Mock())

    def shape_only(self, presentation):
        from globalPlugins._speech_core.settings.presets.model import FIELDS
        return {k: presentation[k] for k in FIELDS}

    def test_future_library_is_read_only_through_real_actions_and_transactions(self):
        import wx
        from globalPlugins._speech_core.settings.presets.model import defaults
        for version in (2, 99):
            raw = ' {"version":%d, "records":{"future":{"opaque":[1,2]}}, "extra":"100%%"} ' % version
            for terminal in ('onApply', 'onOK', 'onCancel', 'onClose'):
                with self.subTest(version=version, terminal=terminal):
                    self.section()['presentationPresets'] = raw
                    original = defaults()
                    original['globalPause'] = 333
                    self.plugin.processor.verbosity.set_shape_config(original, save=True)
                    d = self.dialog()
                    p = d.presentationPresetsPanel
                    self.assertFalse(p.saveAsBtn.enabled)
                    self.assertIn('read-only', p.status.label)
                    with patch.object(p, 'prompt_name', return_value='Must not save') as prompt, patch.object(wx, 'MessageBox') as error:
                        p.onSaveAs()
                        prompt.assert_not_called()
                        self.assertIn('read-only', error.call_args.args[0])
                    self.assertEqual(p.library.records, {})
                    with patch.object(p, 'confirm', return_value=True): p.onLoad()
                    self.assertEqual(self.plugin.processor.verbosity.get_shape_config(), defaults())
                    self.assertFalse(p.libraryChanged)
                    # Ordinary control changes must not authorize a library rewrite either.
                    current = d.get_working_presentation()
                    current['globalPause'] = 0
                    d.load_working_presentation(current)
                    getattr(d, terminal)(self.event())
                    self.assertEqual(self.section()['presentationPresets'], raw)
                    self.assertEqual(self.dialog().presentationPresetsPanel.library.serialize(), raw)

    def test_real_verbosity_events_cannot_replay_stale_shape_after_load_or_edit(self):
        import wx
        d = self.dialog()
        shape = d.get_working_presentation()
        shape.update(globalPause=333, renames={'button': 'push'})
        d.load_working_presentation(shape)
        d.onOK(None)
        g = self.general_dialog()
        self.assertNotIn('presentationPresetsPanel', g.__dict__)
        v = g.verbosityPanel
        v.readEditFieldContentsCheckBox.SetValue(False)
        v.readEditFieldContentsCheckBox.bindings[wx.EVT_CHECKBOX](self.event())
        self.assertEqual(self.plugin.processor.verbosity.get_shape_config(), self.shape_only(shape))
        self.assertEqual(g.get_working_shape(), self.shape_only(shape))
        self.assertTrue(g.onApply(None))
        applied = copy.deepcopy(self.section())
        g.tokenEditorPanel.rolePanel._workingRenames['button'] = 'edited'
        g.tokenEditorPanel.onInlineChanged()
        expected = g.get_working_shape()
        v.positionModeChoice.SetSelection(1)
        v.positionModeChoice.bindings[wx.EVT_CHOICE](self.event())
        self.assertEqual(self.plugin.processor.verbosity.get_shape_config(), expected)
        g.onCancel(None)
        self.assertEqual(self.section(), applied)
        self.assertEqual(self.plugin.processor.verbosity.get_shape_config(), self.shape_only(shape))

    def test_update_confirmation_names_selected_not_loaded_preset(self):
        d = self.dialog()
        p = d.presentationPresetsPanel
        selected = p.library.save_as('Exact selected target', d.get_working_presentation())
        p.library.save_as('Different loaded target', d.get_working_presentation())
        p.refresh_list(selected)
        with patch.object(p, 'confirm', return_value=False) as confirm:
            p.onUpdate()
        self.assertIn('Exact selected target', confirm.call_args.args[0])
        self.assertNotIn('Different loaded target', confirm.call_args.args[0])

    def test_real_controls_first_category_selection_does_not_load_and_buttons_native(self):
        import wx
        d = self.dialog()
        p = d.presentationPresetsPanel
        self.assertNotIn('dynamicPanels', d.__dict__)
        self.assertFalse(d.applyBtn.shown)
        self.assertEqual(d.panelHost.scrolling, {'scroll_x': False})
        before = d.get_working_presentation()
        e = self.event()
        p.presetList.bindings[wx.EVT_LIST_ITEM_FOCUSED](e)
        e.Skip.assert_called_once()
        self.assertEqual(d.get_working_presentation(), before)
        self.assertEqual(p.presetList.bindings[wx.EVT_CHAR_HOOK], d.onCategoryCharHook)
        for attr, handler in (('loadBtn', p.onLoad), ('saveAsBtn', p.onSaveAs),
                              ('updateBtn', p.onUpdate), ('renameBtn', p.onRename), ('deleteBtn', p.onDelete)):
            self.assertEqual(getattr(p, attr).bindings[wx.EVT_BUTTON], handler)
        self.assertFalse(p.updateBtn.enabled)
        self.assertFalse(p.renameBtn.enabled)
        self.assertFalse(p.deleteBtn.enabled)

    def test_load_updates_both_editors_repeated_load_and_cross_panel_live_edits(self):
        d = self.dialog()
        p = d.presentationPresetsPanel
        shape = d.get_working_presentation()
        shape.update(globalPause=160, pausePlacement='after', pauseAfterFinalToken=False, pauseMode='perToken',
                     renames={'button': 'btn'}, mutedLabels=['checked'], order=list(reversed(shape['order'])))
        shape['pauses']['role'] = 120
        key = p.library.save_as('Work', shape)
        p.refresh_list(key)
        with patch.object(p, 'confirm', return_value=True): p.onLoad()
        self.assertEqual(d.get_working_presentation(), shape)
        with patch.object(p, 'confirm', side_effect=AssertionError('unchanged load must not prompt')): p.onLoad()
        d.onOK(None)
        g = self.general_dialog()
        self.assertEqual(g.get_working_shape(), self.shape_only(shape))
        g.tokenEditorPanel.rolePanel._workingRenames['button'] = 'push'
        g.tokenEditorPanel.onInlineChanged()
        self.assertEqual(self.plugin.processor.verbosity.get_global_pause(), 160)
        g.speechTimingPanel.globalPauseChoice.SetSelection(0)
        g.speechTimingPanel.onInlineChanged()
        self.assertEqual(self.plugin.processor.verbosity.get_shape_config()['renames'], {'button': 'push'})
        g.onOK(None)
        d = self.dialog()
        p = d.presentationPresetsPanel
        self.assertIn('modified', p.status.label)
        current = d.get_working_presentation()
        with patch.object(p, 'confirm', return_value=False): p.onLoad()
        self.assertEqual(d.get_working_presentation(), current)
        with patch.object(p, 'confirm', return_value=True): p.onLoad()
        self.assertEqual(d.get_working_presentation(), shape)

    def test_load_cancel_restores_exact_raw_shape_and_no_library_disk_write(self):
        from globalPlugins._speech_core import settings_file
        d = self.dialog()
        before = copy.deepcopy(self.section())
        shape = d.get_working_presentation()
        shape['globalPause'] = 400
        p = d.presentationPresetsPanel
        key = p.library.save_as('Work', shape)
        p.refresh_list(key)
        with patch.object(settings_file, 'write_settings_file', side_effect=AssertionError('immediate disk write')):
            with patch.object(p, 'confirm', return_value=True): p.onLoad()
            self.assertEqual(self.plugin.processor.verbosity.get_global_pause(), 400)
            d.onCancel(None)
            self.assertEqual(self.section(), before)
            self.assertEqual(self.plugin.processor.verbosity.get_global_pause(), 80)

    def test_crud_staged_apply_cancel_close_ok_and_raw_library_presence(self):
        import wx
        for close in ('onCancel', 'onClose'):
            with self.subTest(close=close):
                self.section().pop('presentationPresets', None)
                d = self.dialog()
                p = d.presentationPresetsPanel
                with patch.object(p, 'prompt_name', return_value='Work'): p.onSaveAs()
                self.assertNotIn('presentationPresets', self.section())
                self.assertTrue(d.onApply(None))
                applied = self.section()['presentationPresets']
                with patch.object(p, 'prompt_name', return_value='Office'): p.onRename()
                with patch.object(p, 'confirm', return_value=True): p.onUpdate(); p.onDelete()
                self.assertEqual(self.section()['presentationPresets'], applied)
                getattr(d, close)(self.event())
                self.assertEqual(self.section()['presentationPresets'], applied)
                reopened = self.dialog()
                self.assertEqual([r['name'] for r in reopened.presentationPresetsPanel.library.records.values()], ['Work'])
                with patch.object(reopened.presentationPresetsPanel, 'prompt_name', return_value='Office'):
                    reopened.presentationPresetsPanel.onRename()
                reopened.onOK(None)
                reopened.Destroy.assert_called_once()
                reopened.onClose(self.event())
                self.assertIn('Office', self.section()['presentationPresets'])
        self.section().pop('presentationPresets', None)
        d = self.dialog()
        with patch.object(d.presentationPresetsPanel, 'prompt_name', return_value='Temporary'):
            d.presentationPresetsPanel.onSaveAs()
        d.onCancel(None)
        self.assertNotIn('presentationPresets', self.section())

    def test_unknown_domains_preserved_ignored_and_narrow_shape_save(self):
        from globalPlugins._speech_core.settings.presets.model import Library, defaults
        lib = Library('', defaults())
        key = lib.save_as('Work', defaults())
        lib.records[key]['domains']['futureMenus'] = {'enabled': True, 'text': ['hello']}
        lib = Library(lib.serialize(), defaults())
        self.assertNotIn('futureMenus', lib.load(key))
        lib.update(key, defaults())
        self.assertEqual(lib.records[key]['domains']['futureMenus']['text'], ['hello'])
        section = self.section()
        section['profileData'] = {'Beginner': {'enabledTokens': {'role': False}}, 'Advanced': {'future': 'keep'}}
        section['unrelated'] = {'future': 'keep'}
        section['shapeData']['future'] = {'keep': ['x']}
        before = copy.deepcopy(section['profileData'])
        self.plugin.processor.verbosity.set_shape_config(defaults(), save=True)
        self.assertEqual(section['profileData'], before)
        self.assertEqual(section['unrelated'], {'future': 'keep'})
        self.assertEqual(section['shapeData']['future'], {'keep': ['x']})

    def test_native_name_modal_validation_cancel_and_duplicate_retry(self):
        import wx
        d = self.dialog()
        p = d.presentationPresetsPanel
        p.library.save_as('Work', d.get_working_presentation())
        dialogs = []
        def modal(*args, **kwargs):
            value = ('WORK', 'Office')[len(dialogs)]
            fake = types.SimpleNamespace(ShowModal=lambda: wx.ID_OK, GetValue=lambda: value, Destroy=Mock())
            dialogs.append(fake)
            return fake
        with patch.object(wx, 'TextEntryDialog', side_effect=modal), patch.object(wx, 'MessageBox') as error:
            self.assertEqual(p.prompt_name('Save preset as'), 'Office')
            self.assertEqual(error.call_count, 1)
        for dialog in dialogs: dialog.Destroy.assert_called_once()
        cancel = types.SimpleNamespace(ShowModal=lambda: wx.ID_CANCEL, Destroy=Mock())
        with patch.object(wx, 'TextEntryDialog', return_value=cancel):
            self.assertIsNone(p.prompt_name('Save preset as'))
        cancel.Destroy.assert_called_once()

    def test_update_delete_apply_reopen_preserve_other_profiles_and_unknown_data(self):
        self.section()['profileData']['Advanced'] = {'enabledTokens': {'role': False}, 'future': ['keep']}
        self.section()['unrelated'] = {'future': 'keep'}
        d = self.dialog()
        p = d.presentationPresetsPanel
        with patch.object(p, 'prompt_name', return_value='Work'): p.onSaveAs()
        changed = d.get_working_presentation()
        changed['globalPause'] = 0
        d.load_working_presentation(changed)
        p.refresh_status()
        self.assertIn('modified', p.status.label)
        with patch.object(p, 'confirm', return_value=True): p.onUpdate()
        self.assertTrue(d.onApply(None))
        self.assertEqual(self.section()['profileData']['Advanced']['future'], ['keep'])
        self.assertEqual(self.section()['unrelated'], {'future': 'keep'})
        p = self.dialog().presentationPresetsPanel
        self.assertEqual(p.library.snapshot(p.selected())['globalPause'], 0)
        with patch.object(p, 'confirm', return_value=True): p.onDelete()
        p.dialog.onOK(None)
        self.assertEqual(self.dialog().presentationPresetsPanel.library.records, {})


if __name__ == '__main__':
    unittest.main(verbosity=2)
