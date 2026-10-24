"""Concrete preset-list acceptance and explicit Load feedback regressions."""
import copy
import types
import unittest
from unittest.mock import Mock, patch
import classic_speech_presentation_presets_ui_harness as base


class PresetInputTests(unittest.TestCase):
    setUp = base.PresetUITests.setUp
    tearDown = base.PresetUITests.tearDown
    _controls = base.PresetUITests._controls
    section = base.PresetUITests.section
    dialog = base.PresetUITests.dialog
    event = base.PresetUITests.event

    def key(self, control, code, modifiers=0):
        import wx
        event = types.SimpleNamespace(GetKeyCode=lambda: code,
                                      HasAnyModifiers=lambda: bool(modifiers), Skip=Mock())
        with patch.object(wx, 'WXK_RETURN', 13, create=True), patch.object(
                wx, 'WXK_NUMPAD_ENTER', 370, create=True):
            control.bindings[wx.EVT_CHAR_HOOK](event)
        return event

    def test_list_enter_accepts_current_working_state_not_selected_preset(self):
        import wx
        from globalPlugins._speech_core.settings.dialog_transactions import SettingsDialogTransactionMixin
        for code in (13, 370):
            with self.subTest(code=code):
                d = self.dialog()
                p = d.presentationPresetsPanel
                selected = d.get_working_presentation()
                selected['globalPause'] = 111
                key = p.library.save_as('Selected, not loaded ' + str(code), selected)
                p.refresh_list(key)
                p.changed()
                working = d.get_working_presentation()
                working['globalPause'] = 222
                d.load_working_presentation(working)
                self.assertEqual(p.presetList.bindings[wx.EVT_CHAR_HOOK], d.onCategoryCharHook)
                self.assertIs(type(d).onCategoryCharHook, SettingsDialogTransactionMixin.onCategoryCharHook)
                with patch.object(d, 'onOK', wraps=d.onOK) as ok, patch.object(
                        p, 'onLoad', side_effect=AssertionError('Enter must not load')), patch.object(
                        p.library, 'load', side_effect=AssertionError('Enter must not load')):
                    event = self.key(p.presetList, code)
                    ok.assert_called_once_with(event)
                event.Skip.assert_not_called()
                d.Destroy.assert_called_once()
                accepted = copy.deepcopy(self.section())
                self.assertIn('Selected, not loaded', accepted['presentationPresets'])
                self.assertEqual(d.get_working_presentation(), working)
                close = self.event()
                d.onClose(close)
                close.Skip.assert_called_once()
                self.assertEqual(self.section(), accepted)
                self.assertEqual(self.dialog().get_working_presentation(), working)

    def test_modified_enter_space_navigation_and_nonlist_controls_stay_native(self):
        import wx
        d = self.dialog()
        p = d.presentationPresetsPanel
        with patch.object(d, 'onOK') as ok:
            for code, modifiers in ((13, 1), (13, 2), (13, 4), (13, 8), (370, 1),
                                    (370, 2), (370, 4), (370, 8), (32, 0), (315, 0),
                                    (317, 0), (9, 0), (27, 0), (65, 0), (83, 2)):
                self.key(p.presetList, code, modifiers).Skip.assert_called_once()
            ok.assert_not_called()
        for control in (d, d.panelHost, p, d.okBtn, d.cancelBtn, d.applyBtn,
                        p.loadBtn, p.saveAsBtn, p.updateBtn, p.renameBtn, p.deleteBtn):
            self.assertNotIn(wx.EVT_CHAR_HOOK, control.__dict__.get('bindings', {}))
        for control, handler in ((d.okBtn, d.onOK), (d.cancelBtn, d.onCancel),
                                 (d.applyBtn, d.onApply), (p.loadBtn, p.onLoad),
                                 (p.saveAsBtn, p.onSaveAs), (p.updateBtn, p.onUpdate),
                                 (p.renameBtn, p.onRename), (p.deleteBtn, p.onDelete)):
            self.assertEqual(control.bindings[wx.EVT_BUTTON], handler)
        self.assertEqual(set(p.presetList.bindings), {wx.EVT_CHAR_HOOK, wx.EVT_LIST_ITEM_FOCUSED})
        event = self.event()
        p.presetList.bindings[wx.EVT_LIST_ITEM_FOCUSED](event)
        event.Skip.assert_called_once()

    def test_failed_enter_consumed_and_native_cancel_restores_applied_baseline(self):
        import wx
        for code in (13, 370):
            d = self.dialog()
            p = d.presentationPresetsPanel
            working = d.get_working_presentation()
            working['globalPause'] = 333
            d.load_working_presentation(working)
            self.assertTrue(d.applyBtn.bindings[wx.EVT_BUTTON](None))
            applied = copy.deepcopy(self.section())
            working['globalPause'] = 444
            d.load_working_presentation(working)
            with patch.object(d, '_saveTransaction', side_effect=ValueError('save rejected')), patch.object(
                    d, 'onOK', wraps=d.onOK) as ok:
                event = self.key(p.presetList, code)
                ok.assert_called_once_with(event)
            event.Skip.assert_not_called()
            d.Destroy.assert_not_called()
            d.cancelBtn.bindings[wx.EVT_BUTTON](None)
            d.Destroy.assert_called_once()
            self.assertEqual(self.section(), applied)
            self.assertEqual(self.dialog().get_working_presentation()['globalPause'], 333)

    def test_explicit_load_announces_selected_name_once_including_defaults(self):
        from globalPlugins._speech_core import message_priority
        from globalPlugins._speech_core.settings.presets.model import DEFAULT_ID, DEFAULT_NAME
        d = self.dialog()
        p = d.presentationPresetsPanel
        key = p.library.save_as('Named presentation', d.get_working_presentation())
        for selected, name in ((key, 'Named presentation'), (DEFAULT_ID, DEFAULT_NAME)):
            p.refresh_list(selected)
            with patch.object(message_priority, 'speak_message') as message, patch.object(
                    p, 'confirm', return_value=True):
                p.onLoad()
                message.assert_called_once_with(name + ' preset loaded')
                self.assertEqual(p.selected(), selected)

    def test_selection_cancel_rejected_load_and_other_actions_do_not_announce_loaded(self):
        import wx
        from globalPlugins._speech_core import message_priority
        d = self.dialog()
        p = d.presentationPresetsPanel
        key = p.library.save_as('Named presentation', d.get_working_presentation())
        p.refresh_list(key)
        with patch.object(message_priority, 'speak_message') as message:
            p.presetList.bindings[wx.EVT_LIST_ITEM_FOCUSED](self.event())
            working = d.get_working_presentation()
            working['globalPause'] = 555
            d.load_working_presentation(working)
            with patch.object(p, 'confirm', return_value=False):
                p.onLoad()
            p.refresh_list(key)
            with patch.object(p, 'prompt_name', return_value='New name'):
                p.onSaveAs()
            with patch.object(p, 'confirm', return_value=True):
                p.onUpdate()
            message.assert_not_called()


    def test_failed_load_reports_once_and_restores_partial_config_and_runtime(self):
        import config
        from globalPlugins._speech_core import message_priority
        from globalPlugins._speech_core.settings.presets import config_adapter
        for failure in ('missingRecord', 'invalidDomain', 'partialApply'):
            with self.subTest(failure=failure):
                d = self.dialog()
                p = d.presentationPresetsPanel
                wanted = d.get_working_presentation()
                wanted['globalPause'] = 777
                wanted['messages']['browseModeMessage'] = 'Changed browse'
                key = p.library.save_as('Broken', wanted)
                p.refresh_list(key)
                prior_metadata = (p.library.loaded, copy.deepcopy(p.library.reference), p.libraryChanged)
                if failure == 'missingRecord':
                    del p.library.records[key]
                elif failure == 'invalidDomain':
                    p.library.records[key]['domains'] = {}
                before = copy.deepcopy(self.section())
                native = copy.deepcopy(config.conf.get('virtualBuffers'))
                runtime = copy.deepcopy(self.plugin.processor.verbosity.get_profile_config())
                def partial(snapshot):
                    config_adapter.apply(snapshot)
                    raise RuntimeError('native setting failed after changes')
                with patch.object(message_priority, 'speak_message') as message, patch.object(
                        p, 'confirm', return_value=True):
                    if failure == 'partialApply':
                        with patch.object(d, 'load_working_presentation', side_effect=partial):
                            p.onLoad()
                    else:
                        p.onLoad()
                    message.assert_called_once()
                    self.assertIn('Could not load', message.call_args.args[0])
                    self.assertNotIn('preset loaded', message.call_args.args[0])
                self.assertEqual(self.section(), before)
                self.assertEqual(config.conf.get('virtualBuffers'), native)
                self.assertEqual(self.plugin.processor.verbosity.get_profile_config(), runtime)
                self.assertEqual((p.library.loaded, p.library.reference, p.libraryChanged), prior_metadata)
                d.Destroy.assert_not_called()

    def test_missing_selection_reports_failure_not_success(self):
        from globalPlugins._speech_core import message_priority
        d = self.dialog()
        p = d.presentationPresetsPanel
        p.presetList.Select(-1)
        with patch.object(message_priority, 'speak_message') as message:
            p.onLoad()
            message.assert_called_once_with('Could not load preset: no preset selected.')


if __name__ == '__main__':
    unittest.main(verbosity=2)
