"""Audited cross-category preset domains, exercised with real participating panels."""
import copy
import json
import unittest
from unittest.mock import patch
import classic_speech_presentation_presets_ui_harness as base


class PresentationDomainsTests(unittest.TestCase):
    setUp = base.PresetUITests.setUp
    tearDown = base.PresetUITests.tearDown
    section = base.PresetUITests.section
    event = base.PresetUITests.event

    def _controls(self):
        base.PresetUITests._controls(self)

    def dialog(self):
        return base.PresetUITests.dialog(self)

    general_dialog = base.PresetUITests.general_dialog

    def changed(self, current):
        result = copy.deepcopy(current)
        result['globalPause'] = 177
        for domain in ('menus', 'misc'):
            for key, value in result[domain].items():
                if type(value) is bool:
                    result[domain][key] = not value
                elif isinstance(value, str):
                    result[domain][key] = 'Custom ' + value
        result['hotkeys'].update(mode='off', format='expandedNoPlus', types='none', dialogAccessKeyOnly=True)
        result['keyLabels'].update(renames={'f1': 'help key'}, mutedLabels=['f2'])
        result['messages'].update(browseModeMessage='Web %(name)s 100%', focusModeMessage='Forms',
                                  passThroughAudioIndication=not result['messages']['passThroughAudioIndication'])
        v = result['verbosity']
        v['defaultProfile'] = 'Intermediate'
        for row in v['profiles'].values():
            row['enabledTokens'] = {k: not value for k, value in row['enabledTokens'].items()}
            row['readEditFieldContents'] = not row['readEditFieldContents']
            row['positionMode'] = 'off' if row['positionMode'] != 'off' else 'each'
        return result

    def load(self, d, snapshot, name='Work'):
        p = d.presentationPresetsPanel
        key = p.library.save_as(name + str(len(p.library.records)), snapshot)
        p.refresh_list(key)
        with patch.object(p, 'confirm', return_value=True):
            p.onLoad()
        return key

    def test_unsaved_outgoing_behavior_survives_switch_and_real_save_as(self):
        g = self.general_dialog()
        v = g.verbosityPanel
        v.readEditFieldContentsCheckBox.SetValue(False)
        v.onInlineProfileChanged()
        v.activeProfileChoice.SetSelection(1)
        v.onActiveProfileChanged()
        self.assertFalse(v.workingBehaviors['Beginner']['readEditFieldContents'])
        # General accepts all profiles before the independent manager reads them.
        self.assertTrue(g.onApply(None))
        p = self.dialog().presentationPresetsPanel
        with patch.object(p, 'prompt_name', return_value='Accepted profiles'): p.onSaveAs()
        saved = p.library.load(p.library.loaded)
        self.assertFalse(saved['verbosity']['profiles']['Beginner']['readEditFieldContents'])

    def test_unchecked_name_preview_is_runtime_not_saved_rebuild(self):
        d = self.general_dialog()
        v = d.verbosityPanel
        v.tokenList.Check(0, False)
        v.onInlineProfileChanged()
        self.assertFalse(v.get_working_profile_config()['enabledTokens']['name'])
        self.assertFalse(self.plugin.processor.verbosity.get_enabled_tokens()['name'])
        d.onCancel(None)
        self.assertTrue(self.plugin.processor.verbosity.get_enabled_tokens()['name'])

    def test_multi_profile_edits_update_apply_reload_and_cancel(self):
        from globalPlugins._speech_core import settings_file
        import tempfile
        from pathlib import Path
        from globalPlugins._speech_core.settings.config_core import _replace_section_contents
        for close in ('onCancel', 'onClose'):
            with self.subTest(close=close):
                d = self.general_dialog()
                v = d.verbosityPanel
                initial_raw = copy.deepcopy(self.section())
                with patch.object(settings_file, 'write_settings_file', side_effect=AssertionError('premature save')):
                    for index in range(3):
                        v.activeProfileChoice.SetSelection(index)
                        v.onActiveProfileChanged()
                        v.tokenList.Check(0, False)
                        v.tokenList.Check(4, True)
                        v.readEditFieldContentsCheckBox.SetValue(False)
                        v.onInlineProfileChanged()
                        self.assertFalse(self.plugin.processor.verbosity.get_enabled_tokens()['name'])
                        self.assertTrue(self.plugin.processor.verbosity.get_enabled_tokens()['tooltip'])
                    self.assertEqual(self.section().get('profileData'), initial_raw.get('profileData'))
                    self.assertEqual(self.section().get('profileBehaviorData'), initial_raw.get('profileBehaviorData'))
                    self.assertTrue(d.onApply(None))
                    applied = copy.deepcopy(self.section())
                    for index in range(3):
                        v.activeProfileChoice.SetSelection(index)
                        v.onActiveProfileChanged()
                        v.tokenList.Check(0, True)
                        v.onInlineProfileChanged()
                    getattr(d, close)(self.event())
                self.assertEqual(self.section(), applied)
                self.assertFalse(self.plugin.processor.verbosity.get_enabled_tokens()['name'])
                self.assertEqual(self.plugin.processor.verbosity.current_profile, 'Advanced')
                p = self.dialog().presentationPresetsPanel
                with patch.object(p, 'prompt_name', return_value='All profiles'): p.onSaveAs()
                expected = p.library.load(p.library.loaded)['verbosity']
                p.dialog.onOK(None)
                with tempfile.TemporaryDirectory() as folder:
                    path = str(Path(folder) / 'settings.ini')
                    with patch.object(settings_file, '_may_write_files', return_value=True):
                        self.assertTrue(settings_file.write_settings_file(self.section(), path))
                    _replace_section_contents(self.section(), settings_file.load_settings_file(path))
                    self.plugin.processor.verbosity.load_from_config()
                    self.assertEqual(self.dialog().get_working_presentation()['verbosity'], expected)

    def test_individual_domains_load_only_owned_values_both_directions(self):
        from globalPlugins._speech_core.settings.presets import domains
        from globalPlugins._speech_core.settings.presets.model import defaults
        import config
        for domain in domains.FIELDS:
            with self.subTest(domain=domain):
                d = self.dialog()
                initial = d.get_working_presentation()
                changed = self.changed(initial)
                unrelated = {'prioritizeMessages': True, 'preventAutomaticSpeechInterrupt': True,
                             'automaticSpeechInterruptFallbackMs': 2345, 'queryObjectSource': 'navigator',
                             'objectNavigationProcessing': True, 'voiceProfileData': {'keep': 'raw'},
                             'speechHookEnabled': False, 'future': ['keep']}
                self.section().update(copy.deepcopy(unrelated))
                config.conf.setdefault('presentation', {})['unrelated'] = 'keep'
                native_before = copy.deepcopy(config.conf['presentation'])
                # Legacy shape + one newly supported domain is a valid partial record.
                for index, source in enumerate((changed, initial)):
                    snap = dict(defaults(), **{domain: source[domain]})
                    self.load(d, snap, domain + str(index))
                    actual = d.get_working_presentation()
                    self.assertEqual(actual[domain], source[domain])
                    for other in domains.FIELDS.keys() - {domain}:
                        self.assertEqual(actual[other], initial[other])
                    for key, value in unrelated.items():
                        self.assertEqual(self.section()[key], value)
                    self.assertEqual(config.conf['presentation']['unrelated'], 'keep')
                    # Only verbosity/hotkeys intrinsically synchronize native leaves.
                    if domain not in ('verbosity', 'hotkeys'):
                        self.assertEqual(config.conf['presentation'], native_before)
                d.onCancel(None)

    def test_complete_load_runtime_controls_apply_cancel_and_disk_reload(self):
        import tempfile
        from pathlib import Path
        from globalPlugins._speech_core import settings_file
        from globalPlugins._speech_core.settings.config_core import _replace_section_contents
        from globalPlugins._speech_core.settings.presets import config_adapter as adapters
        from configobj import ConfigObj
        d = self.dialog()
        wanted = self.changed(d.get_working_presentation())
        key = self.load(d, wanted)
        self.assertEqual(d.get_working_presentation(), wanted)
        self.assertEqual(adapters.capture(), wanted)
        self.assertEqual(self.plugin.processor.verbosity.current_profile, 'Intermediate')
        self.assertTrue(self.plugin.processor.verbosity.announce_default_button)
        self.assertEqual(self.plugin.processor.verbosity.get_global_pause(), 177)
        import config
        import keyLabels
        self.assertEqual(keyLabels.localizedKeyLabels['f1'], 'help key')
        self.assertEqual(keyLabels.localizedKeyLabels['f2'], '')
        native_expected = {
            'reportKeyboardShortcuts': False,
            'reportObjectDescriptions': wanted['verbosity']['profiles']['Intermediate']['enabledTokens']['description'],
            'reportTooltips': wanted['verbosity']['profiles']['Intermediate']['enabledTokens']['tooltip'],
            'reportObjectPositionInformation': False,
        }
        for native_key, value in native_expected.items():
            self.assertEqual(config.conf['presentation'][native_key], value)
        self.assertNotIn('modified', d.presentationPresetsPanel.status.label)
        self.assertTrue(d.onApply(None))
        applied = copy.deepcopy(self.section())
        # Stale copies in every panel must not replay pre-load values at Apply.
        self.assertEqual(d.get_working_presentation(), wanted)
        self.load(d, self.changed(wanted), 'Later')
        d.onCancel(None)
        self.assertEqual(self.section(), applied)
        reopened = self.dialog()
        self.assertEqual(reopened.get_working_presentation(), wanted)
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'settings.ini')
            native = ConfigObj(encoding='UTF-8')
            native.filename = str(Path(folder) / 'nvda.ini')
            native['classicSpeech'] = copy.deepcopy(self.section())
            native['unrelated'] = {'keep': 'native'}
            settings_file._wrap_nvda_ini_write(native)
            import config
            # Model NVDA's save boundary with a real ConfigObj base write, not
            # a synthesized settings.ini or direct call to its writer.
            with patch.object(settings_file, '_may_write_files', return_value=True), \
                    patch.object(settings_file, 'settings_path', return_value=path), \
                    patch.object(config.conf, 'save', native.write, create=True):
                config.conf.save()
            native_saved = ConfigObj(native.filename, encoding='UTF-8')
            self.assertNotIn('classicSpeech', native_saved)
            self.assertEqual(native_saved['unrelated'], {'keep': 'native'})
            stored = ConfigObj(path, encoding='UTF-8')
            self.assertEqual(json.loads(stored['presentationPresets'])['loaded'], key)
            raw = settings_file.load_settings_file(path)
            _replace_section_contents(self.section(), raw)
            self.plugin.processor.verbosity.load_from_config()
            reloaded = self.dialog()
            self.assertEqual(reloaded.get_working_presentation(), wanted)
            self.assertNotIn('modified', reloaded.presentationPresetsPanel.status.label)

    def test_real_profile_switches_and_menu_hotkey_misc_events_after_load(self):
        import wx
        d = self.dialog()
        wanted = self.changed(d.get_working_presentation())
        self.load(d, wanted)
        d.onOK(None)
        g = self.general_dialog()
        v = g.verbosityPanel
        for index, name in enumerate(('Beginner', 'Intermediate', 'Advanced')):
            v.activeProfileChoice.SetSelection(index)
            v.activeProfileChoice.bindings[wx.EVT_CHOICE](self.event())
            self.assertEqual(v.get_working_profile_behavior(),
                             {k: wanted['verbosity']['profiles'][name][k] for k in ('positionMode', 'readEditFieldContents')})
        g.menusPanel.menuOpenMessage.ChangeValue('New menu')
        g.menusPanel.onChanged()
        g.hotkeysPanel.dialogAccessKeyOnlyCheck.SetValue(False)
        g.hotkeysPanel.onInlineChanged()
        g.miscPanel.includeWindowStateInTitle.SetValue(False)
        g.miscPanel.onChanged()
        self.assertEqual(self.plugin.processor.verbosity.get_global_pause(), 177)
        self.assertEqual(self.section()['menuOpenMessage'], 'New menu')
        self.assertFalse(self.section()['hotkeyDialogAccessKeyOnly'])
        self.assertFalse(self.section()['includeWindowStateInTitle'])
        self.assertTrue(g.onApply(None))
        reopened = self.dialog().get_working_presentation()
        self.assertEqual(reopened['verbosity']['profiles'], wanted['verbosity']['profiles'])

    def test_native_owned_leaves_and_presence_restore_on_cancel_close_and_apply(self):
        import config
        from globalPlugins._speech_core.settings import native_state
        for present in (False, True):
            for close in ('onCancel', 'onClose'):
                with self.subTest(present=present, close=close):
                    for section, keys in native_state.NATIVE_KEYS.items():
                        config.conf[section] = {'unrelated': 'keep'}
                        if present:
                            config.conf[section].update({k: i % 2 == 0 for i, k in enumerate(keys)})
                    before = {s: copy.deepcopy(config.conf[s]) for s in native_state.NATIVE_KEYS}
                    d = self.dialog()
                    self.load(d, self.changed(d.get_working_presentation()))
                    getattr(d, close)(self.event())
                    self.assertEqual({s: config.conf[s] for s in before}, before)
                    d = self.dialog()
                    self.load(d, self.changed(d.get_working_presentation()))
                    self.assertTrue(d.onApply(None))
                    baseline = {s: copy.deepcopy(config.conf[s]) for s in before}
                    self.load(d, self.changed(d.get_working_presentation()), 'Other')
                    getattr(d, close)(self.event())
                    self.assertEqual({s: config.conf[s] for s in before}, baseline)

    def test_opaque_nested_future_domains_and_library_version_preserved(self):
        from globalPlugins._speech_core.settings.presets.model import Library
        d = self.dialog()
        current = d.get_working_presentation()
        lib = Library('', current)
        key = lib.save_as('Future compatible', current)
        data = lib.records[key]['domains']
        data['verbosity']['profiles']['Advanced']['enabledTokens']['futureDetail'] = ['raw']
        data['verbosity']['profiles']['Advanced']['futureBehavior'] = {'raw': 1}
        data['misc']['futureFlag'] = ['raw']
        data['futureDomain'] = {'version': 99, 'raw': 'keep'}
        lib = Library(lib.serialize(), current)
        lib.update(key, self.changed(current))
        data = lib.records[key]['domains']
        self.assertEqual(data['verbosity']['profiles']['Advanced']['enabledTokens']['futureDetail'], ['raw'])
        self.assertEqual(data['verbosity']['profiles']['Advanced']['futureBehavior'], {'raw': 1})
        self.assertEqual(data['misc']['futureFlag'], ['raw'])
        data['misc']['version'] = 99
        raw_domain = copy.deepcopy(data['misc'])
        lib = Library(lib.serialize(), current)
        self.assertNotIn('misc', lib.load(key))
        lib.update(key, current)
        self.assertEqual(lib.records[key]['domains']['misc'], raw_domain)

    def test_defaults_all_domains_without_resetting_native_or_unseen_profiles(self):
        import config
        from globalPlugins._speech_core.settings.presets import domains
        from globalPlugins._speech_core.settings.presets.model import defaults
        self.section()['profileData']['Unseen future profile'] = {'raw': ['keep']}
        self.section()['profileData'].setdefault('Advanced', {})['futureField'] = {'raw': True}
        config.conf.setdefault('presentation', {})['unrelated'] = 'keep'
        d = self.dialog()
        self.load(d, self.changed(d.get_working_presentation()))
        p = d.presentationPresetsPanel
        p.refresh_list('defaults')
        with patch.object(p, 'confirm', return_value=True): p.onLoad()
        self.assertEqual(d.get_working_presentation(), dict(defaults(), **domains.defaults()))
        self.assertEqual(self.section()['profileData']['Unseen future profile'], {'raw': ['keep']})
        self.assertEqual(self.section()['profileData']['Advanced']['futureField'], {'raw': True})
        self.assertEqual(config.conf['presentation']['unrelated'], 'keep')
        self.assertNotIn('modified', p.status.label)

    def test_all_hotkey_enum_values_and_profile_flags_roundtrip(self):
        from globalPlugins._speech_core.settings.presets.model import defaults
        d = self.dialog()
        current = d.get_working_presentation()
        # Exercise every mode/type/format; both dependent checkbox values too.
        from itertools import product
        for mode, types, fmt, access_only in product(
                ('off', 'menus', 'dialogs', 'both'), ('none', 'access', 'command', 'both'),
                ('native', 'expandedNoPlus', 'abbreviatedNoPlus'), (False, True)):
            value = {'version': 1, 'mode': mode, 'types': types, 'format': fmt,
                     'dialogAccessKeyOnly': access_only}
            d.load_working_presentation(dict(defaults(), hotkeys=value))
            self.assertEqual(d.get_working_presentation()['hotkeys'], value)
        for boolean in (False, True):
            for position in ('off', 'first', 'each'):
                value = copy.deepcopy(current['verbosity'])
                for row in value['profiles'].values():
                    row['enabledTokens'] = {key: boolean for key in row['enabledTokens']}
                    row['readEditFieldContents'] = boolean
                    row['positionMode'] = position
                d.load_working_presentation(dict(defaults(), verbosity=value))
                self.assertEqual(d.get_working_presentation()['verbosity'], value)
                self.assertTrue(d.onApply(None))
                self.assertEqual(self.dialog().get_working_presentation()['verbosity'], value)

    def test_raw_profile_and_library_presence_restore_and_reload(self):
        from globalPlugins._speech_core import settings_file
        import tempfile
        from pathlib import Path
        import config
        for present in (False, True):
            for close in ('onCancel', 'onClose'):
                with self.subTest(present=present, close=close):
                    for key in ('profileData', 'profileBehaviorData', 'presentationPresets'):
                        self.section().pop(key, None)
                    if present:
                        self.section()['profileData'] = {'Advanced': {'enabledTokens': {'tooltip': True}, 'future': ['keep']}}
                        self.section()['profileBehaviorData'] = {'Intermediate': {'positionMode': 'off', 'readEditFieldContents': False}}
                        self.section()['presentationPresets'] = ''
                    before = copy.deepcopy(self.section())
                    d = self.dialog()
                    self.load(d, self.changed(d.get_working_presentation()))
                    getattr(d, close)(self.event())
                    self.assertEqual(self.section(), before)
                    with tempfile.TemporaryDirectory() as folder:
                        path = str(Path(folder) / 'settings.ini')
                        with patch.object(settings_file, '_may_write_files', return_value=True):
                            self.assertTrue(settings_file.write_settings_file(self.section(), path))
                        restored = settings_file.load_settings_file(path)
                        self.assertEqual('presentationPresets' in restored, present)
                        self.assertEqual('profileData' in restored, present)
                        self.assertEqual('profileBehaviorData' in restored, present)

    def test_all_new_domains_have_explicit_validated_allowlists(self):
        from globalPlugins._speech_core.settings.presets import domains
        from globalPlugins._speech_core.settings.presets.model import Library, defaults
        expected = {'verbosity', 'menus', 'hotkeys', 'keyLabels', 'misc', 'messages', 'speechHookAnnouncement'}
        self.assertEqual(set(domains.FIELDS), expected)
        current = dict(defaults(), **domains.defaults())
        lib = Library('', current)
        key = lib.save_as('Complete', current)
        self.assertTrue(expected <= lib.records[key]['domains'].keys())
        for domain in expected:
            bad = copy.deepcopy(current)
            bad[domain]['version'] = True
            with self.subTest(domain=domain), self.assertRaises(ValueError):
                lib.save_as('Invalid ' + domain, bad)

    def test_legacy_missing_domains_leave_current_and_status_unchanged(self):
        from globalPlugins._speech_core.settings.presets.model import Library, defaults
        lib = Library('', defaults())
        key = lib.save_as('Legacy', defaults())
        self.section()['presentationPresets'] = lib.serialize()
        self.section()['includeWindowStateInTitle'] = True
        self.section()['menuOpenMessage'] = 'x' * 501
        d = self.dialog()
        p = d.presentationPresetsPanel
        before = copy.deepcopy(d.get_working_presentation())
        p.refresh_list(key)
        with patch.object(p, 'confirm', return_value=True): p.onLoad()
        for name in ('verbosity', 'menus', 'hotkeys', 'keyLabels', 'misc', 'messages'):
            self.assertEqual(d.get_working_presentation()[name], before[name])
        self.assertNotIn('modified', p.status.label)
        with patch.object(p, 'confirm', side_effect=AssertionError('partial load should not discard unrelated edits')):
            p.onLoad()
        self.assertEqual(self.section()['menuOpenMessage'], 'x' * 501)
        self.section()['menuOpenMessage'] = 'Representable menu'
        with patch.object(p, 'confirm', return_value=True): p.onUpdate()
        self.assertTrue(set(before) - set(defaults()) <= p.library.snapshot(key).keys())


if __name__ == '__main__':
    unittest.main(verbosity=2)
