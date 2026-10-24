"""Standalone construction and cross-dialog preset transaction regressions."""
import unittest
import copy
import types
from unittest.mock import Mock, patch
import classic_speech_presentation_presets_ui_harness as base


class StandaloneTests(unittest.TestCase):
    setUp = base.PresetUITests.setUp
    tearDown = base.PresetUITests.tearDown
    _controls = base.PresetUITests._controls
    section = base.PresetUITests.section
    event = base.PresetUITests.event
    dialog = base.PresetUITests.dialog
    general_dialog = base.PresetUITests.general_dialog

    def _queued_dialog(self):
        import wx
        queued = []
        self.stack.enter_context(patch.object(wx.ListCtrl, 'SetFocus', lambda c: c.__dict__['_focusSpy'](), create=True))
        with patch.object(wx, 'CallAfter', side_effect=lambda cb, *a, **kw: queued.append(lambda: cb(*a, **kw))):
            d = self.dialog()
        d.presentationPresetsPanel.presetList._focusSpy = Mock()
        del d.Destroy  # Exercise the real owner's teardown, not the fixture shortcut.
        self.stack.enter_context(patch.object(wx.Dialog, 'Destroy', Mock(), create=True))
        d.IsBeingDeleted = Mock(return_value=False)
        return d, queued

    def test_deferred_focus_runs_once_for_live_owner(self):
        d, queued = self._queued_dialog()
        focus = d.presentationPresetsPanel.presetList._focusSpy
        self.assertEqual(len(queued), 1)
        queued[0]()
        queued[0]()  # A replay cannot reuse the consumed request.
        focus.assert_called_once()

    def test_deferred_focus_close_cancel_destroy_unload_never_access_control(self):
        for terminal in ('onCancel', 'onClose', 'Destroy', 'destroyEvent', 'unload'):
            with self.subTest(terminal=terminal):
                d, queued = self._queued_dialog()
                baseline = copy.deepcopy(self.section())
                wanted = d.get_working_presentation()
                wanted['globalPause'] = 500
                d.load_working_presentation(wanted)
                # Poison the panel as soon as teardown begins, including during restore.
                panel = d.presentationPresetsPanel
                poison = Mock()
                type(poison).presetList = property(lambda _: self.fail('destroyed control accessed'))
                d.presentationPresetsPanel = poison
                if terminal == 'unload':
                    self.plugin._presentationPresetsDialog = d
                    self.plugin.terminate()
                    self.assertIsNone(self.plugin._presentationPresetsDialog)
                elif terminal == 'destroyEvent':
                    d._onWindowDestroyed(types.SimpleNamespace(GetEventObject=lambda: d, Skip=Mock()))
                else:
                    getattr(d, terminal)(self.event()) if terminal != 'Destroy' else d.Destroy()
                panel.presetList._focusSpy.side_effect = RuntimeError('wrapped C/C++ object of type ListCtrl has been deleted')
                queued[0]()
                panel.presetList._focusSpy.assert_not_called()
                if terminal != 'Destroy':
                    self.assertEqual(self.section(), baseline)
                d.presentationPresetsPanel = panel

    def test_deferred_focus_invalidated_before_transaction_restore(self):
        for terminal in ('onCancel', 'onClose', 'destroyEvent'):
            with self.subTest(terminal=terminal):
                d, queued = self._queued_dialog()
                focus = d.presentationPresetsPanel.presetList._focusSpy
                restore = d._restoreTransactionBaselineSafely
                def drain_during_restore():
                    queued[0]()
                    focus.assert_not_called()
                    restore()
                with patch.object(d, '_restoreTransactionBaselineSafely', side_effect=drain_during_restore):
                    if terminal == 'destroyEvent':
                        d._onWindowDestroyed(types.SimpleNamespace(GetEventObject=lambda: d, Skip=Mock()))
                    else:
                        getattr(d, terminal)(self.event())

    def test_deferred_focus_child_destroy_preserves_owner_request(self):
        d, queued = self._queued_dialog()
        focus = d.presentationPresetsPanel.presetList._focusSpy
        event = types.SimpleNamespace(GetEventObject=lambda: object(), Skip=Mock())
        d._onWindowDestroyed(event)
        event.Skip.assert_called_once()
        queued[0]()
        focus.assert_called_once()

    def test_deferred_focus_native_deleted_race_only_is_ignored(self):
        for message in ('wrapped C/C++ object of type ListCtrl has been deleted', 'unexpected focus failure'):
            with self.subTest(message=message):
                d, queued = self._queued_dialog()
                with patch.object(d.presentationPresetsPanel.presetList._focusSpy, 'side_effect', RuntimeError(message)):
                    if message.startswith('wrapped C/C++'):
                        queued[0]()
                    else:
                        with self.assertRaisesRegex(RuntimeError, 'unexpected focus failure'):
                            queued[0]()

    def test_deferred_focus_native_owner_deleting_never_access_control(self):
        d, queued = self._queued_dialog()
        d.IsBeingDeleted.return_value = True
        focus = d.presentationPresetsPanel.presetList._focusSpy
        queued[0]()
        focus.assert_not_called()

    def test_open_and_unchanged_apply_do_not_materialize_sections(self):
        import config
        section = self.section()
        for key in ('profileData', 'profileBehaviorData', 'keyLabelData', 'modeIndicationData', 'presentationPresets'):
            section.pop(key, None)
        before = copy.deepcopy(section)
        d = self.dialog()
        self.assertEqual(section, before)
        self.assertTrue(d.onApply(None))
        self.assertEqual(section, before)
        config.conf.profiles[0].pop('classicSpeech', None)
        d = self.dialog()
        self.assertNotIn('classicSpeech', config.conf.profiles[0])
        d.onCancel(None)
        self.assertNotIn('classicSpeech', config.conf.profiles[0])

    def test_messages_audio_cancel_close_apply_native_presence_and_unrelated(self):
        import config
        for present in (False, True):
            for terminal in ('onCancel', 'onClose'):
                for audio in (False, True):
                    with self.subTest(present=present, terminal=terminal, audio=audio):
                        config.conf['virtualBuffers'] = {'unrelated': 'keep'}
                        if present:
                            config.conf['virtualBuffers']['passThroughAudioIndication'] = not audio
                        self.section()['modeIndicationData'] = {'browseModeMessage': 'Original browse',
                                                               'focusModeMessage': 'Original focus', 'future': ['keep']}
                        before = copy.deepcopy(self.section())
                        native = copy.deepcopy(config.conf['virtualBuffers'])
                        d = self.dialog()
                        wanted = d.get_working_presentation()
                        wanted['messages'].update(browseModeMessage='Custom browse', focusModeMessage='Custom focus',
                                                  passThroughAudioIndication=audio)
                        d.load_working_presentation(wanted)
                        self.assertEqual(d.get_working_presentation()['messages'], wanted['messages'])
                        self.assertEqual(self.section()['modeIndicationData']['future'], ['keep'])
                        self.section()['unrelatedAfterOpen'] = 'keep'
                        getattr(d, terminal)(self.event())
                        self.assertEqual(self.section(), dict(before, unrelatedAfterOpen='keep'))
                        self.assertEqual(config.conf['virtualBuffers'], native)
                        d = self.dialog()
                        d.load_working_presentation(wanted)
                        self.assertTrue(d.onApply(None))
                        applied = copy.deepcopy(self.section())
                        wanted['messages'].update(browseModeMessage='', focusModeMessage='', passThroughAudioIndication=not audio)
                        d.load_working_presentation(wanted)
                        getattr(d, terminal)(self.event())
                        self.assertEqual(self.section(), applied)
                        self.assertEqual(config.conf['virtualBuffers']['passThroughAudioIndication'], audio)

    def test_messages_legacy_and_future_domain_opaque_update(self):
        from globalPlugins._speech_core.settings.presets.model import Library, defaults
        d = self.dialog()
        current = d.get_working_presentation()
        current['messages'].update(browseModeMessage='Web', focusModeMessage='Forms', passThroughAudioIndication=False)
        d.load_working_presentation(current)
        legacy = Library('', defaults())
        key = legacy.save_as('Legacy', defaults())
        d.load_working_presentation(legacy.load(key))
        self.assertEqual(d.get_working_presentation()['messages'], current['messages'])
        legacy.update(key, current)
        self.assertEqual(legacy.load(key)['messages'], current['messages'])
        legacy.records[key]['domains']['messages']['future'] = {'keep': [1]}
        legacy.update(key, current)
        self.assertEqual(legacy.records[key]['domains']['messages']['future'], {'keep': [1]})
        legacy.records[key]['domains']['messages']['version'] = 99
        opaque = copy.deepcopy(legacy.records[key]['domains']['messages'])
        legacy = Library(legacy.serialize(), current)
        self.assertNotIn('messages', legacy.load(key))
        legacy.update(key, current)
        self.assertEqual(legacy.records[key]['domains']['messages'], opaque)

    def test_native_defaults_blank_messages_and_sound_retains_custom_text(self):
        from globalPlugins._speech_core.settings.presets import domains
        from globalPlugins._speech_core.settings.presets.model import DEFAULT_ID
        from globalPlugins._speech_core.settings.web import mode_indication_config as messages
        d = self.dialog()
        current = d.get_working_presentation()
        current['messages'].update(browseModeMessage='Web', focusModeMessage='Forms', passThroughAudioIndication=True)
        d.load_working_presentation(current)
        self.assertEqual(messages.get_custom_browse_mode_message(), 'Web')
        self.assertEqual(messages.get_custom_focus_mode_message(), 'Forms')
        d.load_working_presentation(d.presentationPresetsPanel.library.load(DEFAULT_ID))
        self.assertEqual(d.get_working_presentation()['messages'], {'version': 1, **domains.MESSAGE_DEFAULTS})
        self.assertIsNone(messages.get_custom_browse_mode_message())
        self.assertIsNone(messages.get_custom_focus_mode_message())

    def test_popup_guard_bidirectional_only_overlaps_and_unbound_script(self):
        import gui, queueHandler
        p = self.plugin
        for slot in ('_settingsDialog', '_webBrowseDialog', '_presentationPresetsDialog'):
            existing = Mock()
            setattr(p, slot, existing)
            with patch.object(gui.mainFrame, 'prePopup') as pre:
                p._openPresentationPresets()
                pre.assert_not_called()
            existing.Raise.assert_called_once()
            setattr(p, slot, None)
        for opener in (p._openSettings, p._openWebBrowseSettings):
            p._presentationPresetsDialog = Mock()
            with patch.object(gui.mainFrame, 'prePopup') as pre:
                opener()
                pre.assert_not_called()
            p._presentationPresetsDialog = None
        p._voiceProfilesDialog = Mock()
        p._schemesDialog = Mock()
        d = Mock()
        module = __import__(p.__class__.__module__, fromlist=['PresentationPresetsDialog'])
        with patch.object(module, 'PresentationPresetsDialog', return_value=d), patch.object(gui.mainFrame, 'prePopup') as pre:
            p._openPresentationPresets()
            pre.assert_called_once()
            d.Show.assert_called_once()
            self.assertIs(p._presentationPresetsDialog, d)
        p._onPresentationPresetsDestroyed(types.SimpleNamespace(GetEventObject=lambda: object(), Skip=Mock()))
        self.assertIs(p._presentationPresetsDialog, d)
        p._onPresentationPresetsDestroyed(types.SimpleNamespace(GetEventObject=lambda: d, Skip=Mock()))
        self.assertIsNone(p._presentationPresetsDialog)
        with patch.object(queueHandler, 'queueFunction') as queue:
            p.script_openClassicSpeechPresentationPresets(None)
            queue.assert_called_once_with(queueHandler.eventQueue, p._openPresentationPresets)
        self.assertNotIn('openClassicSpeechPresentationPresets', p._GlobalPlugin__gestures.values())
        p._voiceProfilesDialog = p._schemesDialog = None

    def test_destroy_close_release_once_and_restore_runtime(self):
        import gui
        d = self.dialog()
        baseline = copy.deepcopy(self.section())
        runtime = copy.deepcopy(self.plugin.processor.verbosity.get_profile_config())
        wanted = d.get_working_presentation()
        wanted['globalPause'] = 500
        d.load_working_presentation(wanted)
        child = types.SimpleNamespace(GetEventObject=lambda: object(), Skip=Mock())
        event = types.SimpleNamespace(GetEventObject=lambda: d, Skip=Mock())
        with patch.object(gui.mainFrame, 'postPopup') as post:
            d._onWindowDestroyed(child)
            post.assert_not_called()
            d._onWindowDestroyed(event)
            d.onClose(self.event())
            post.assert_called_once()
        self.assertEqual(self.section(), baseline)
        self.assertEqual(self.plugin.processor.verbosity.get_profile_config(), runtime)

    def test_web_cancel_independently_restores_accepted_preset_messages(self):
        import wx
        from globalPlugins._speech_core.settings.web.dialog import WebBrowseSettingsDialog
        d = self.dialog()
        wanted = d.get_working_presentation()
        wanted['messages'].update(browseModeMessage='Web', focusModeMessage='Forms', passThroughAudioIndication=False)
        d.load_working_presentation(wanted)
        d.onOK(None)
        web = object.__new__(WebBrowseSettingsDialog)
        self.stack.enter_context(patch.object(wx, 'GetTopLevelParent', lambda p: web, create=True))
        from gui import nvdaControls
        for name, value in (('StaticBoxSizer', wx.BoxSizer), ('EXPAND', wx.EXPAND)):
            self.stack.enter_context(patch.object(wx, name, value, create=True))
        self.stack.enter_context(patch.object(nvdaControls, 'FeatureFlagCombo', wx.Choice, create=True))
        self.stack.enter_context(patch.object(nvdaControls, 'SelectOnFocusSpinCtrl', wx.TextCtrl, create=True))
        WebBrowseSettingsDialog.__init__(web, None)
        web.Destroy = Mock()
        web.browseModeMessageEdit.SetValue('Different browse')
        web.focusModeMessageEdit.SetValue('Different focus')
        web.passThroughAudioIndicationCheckBox.SetValue(True)
        web.onChanged()
        from globalPlugins._speech_core.settings.web import mode_indication_config as messages
        self.assertEqual(messages.get_custom_browse_mode_message(), 'Different browse')
        web.onCancel(None)
        self.assertEqual(self.dialog().get_working_presentation()['messages'], wanted['messages'])

    def test_library_record_and_root_future_fields_survive_real_update(self):
        import json
        d = self.dialog()
        p = d.presentationPresetsPanel
        key = p.library.save_as('Existing', d.get_working_presentation())
        payload = json.loads(p.library.serialize())
        payload['futureLibrary'] = {'opaque': ['keep']}
        payload['records'][key]['futureRecord'] = {'opaque': [2]}
        self.section()['presentationPresets'] = json.dumps(payload)
        reopened = self.dialog()
        p = reopened.presentationPresetsPanel
        with patch.object(p, 'confirm', return_value=True): p.onUpdate()
        self.assertTrue(reopened.onApply(None))
        stored = json.loads(self.section()['presentationPresets'])
        self.assertEqual(stored['futureLibrary'], payload['futureLibrary'])
        self.assertEqual(stored['records'][key]['futureRecord'], payload['records'][key]['futureRecord'])

    def test_audio_raw_leaf_rollback_targets_original_selected_native_profile(self):
        import config
        from globalPlugins._speech_core.settings import native_state
        from globalPlugins._speech_core.settings.presets.transaction import NATIVE_KEYS
        class Profile(dict):
            def __init__(self, name, **data):
                super().__init__(data)
                self.name = name
                self.filename = name + '.ini' if name else 'nvda.ini'
        class Layered:
            BASE_ONLY_SECTIONS = {'classicSpeech'}
            def __init__(self, profiles):
                self.profiles = profiles
                self._dirtyProfiles = set()
        for present in (False, True):
            base_profile = Profile(None, virtualBuffers={'passThroughAudioIndication': True, 'baseOnly': 'keep'})
            active = Profile('Work', virtualBuffers={'unrelated': 'keep'})
            if present:
                active['virtualBuffers']['passThroughAudioIndication'] = False
            before = copy.deepcopy(active)
            conf = Layered([base_profile, active])
            with patch.object(config, 'conf', conf):
                captured = native_state.capture(NATIVE_KEYS)
                active['virtualBuffers']['passThroughAudioIndication'] = True
                native_state.restore(captured)
            self.assertEqual(active, before)
            self.assertEqual(base_profile['virtualBuffers'], {'passThroughAudioIndication': True, 'baseOnly': 'keep'})
            self.assertIn('Work', conf._dirtyProfiles)

    def test_standalone_constructor_no_hidden_general_panels(self):
        import wx
        d = self.dialog()
        self.assertNotIn(wx.EVT_CHAR_HOOK, d.__dict__.get('bindings', {}))
        self.assertEqual(d.presentationPresetsPanel.presetList.bindings[wx.EVT_CHAR_HOOK], d.onCategoryCharHook)
        with patch.object(d, 'Layout') as layout:
            d._markDirty()
            self.assertTrue(d.applyBtn.shown)
            self.assertTrue(d.applyBtn.enabled)
            layout.assert_called_once()
            d._clearDirty()
            self.assertEqual(layout.call_count, 2)
        g = self.general_dialog()
        self.assertEqual(g.CATEGORY_NAMES[0], 'Verbosity')
        self.assertEqual(len(g.CATEGORY_NAMES), 11)
        self.assertNotIn('presentationPresetsPanel', g.__dict__)
        self.assertTrue(g.resetActionBtn.enabled)
        self.assertNotIn('verbosityPanel', d.__dict__)
        self.assertNotIn('tokenEditorPanel', d.__dict__)
        self.assertEqual(d.panelHost.scrolling, {'scroll_x': False})
        self.assertFalse(d.applyBtn.shown)
        self.assertIn('messages', d.get_working_presentation())


if __name__ == '__main__':
    unittest.main(verbosity=2)
