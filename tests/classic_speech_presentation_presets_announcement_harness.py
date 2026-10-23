"""Narrow startup-announcement ownership; real adapters and Advanced controls."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import classic_speech_presentation_presets_ui_harness as base


class AnnouncementTests(unittest.TestCase):
    setUp = base.PresetUITests.setUp
    tearDown = base.PresetUITests.tearDown
    _controls = base.PresetUITests._controls
    section = base.PresetUITests.section
    event = base.PresetUITests.event
    dialog = base.PresetUITests.dialog
    general_dialog = base.PresetUITests.general_dialog

    def wanted(self, message='Ready'):
        result = self.dialog().get_working_presentation()
        result['speechHookAnnouncement'] = {'version': 1, 'announceSpeechHookLoaded': True,
                                            'speechHookLoadedMessage': message}
        return result

    def test_capture_raw_defaults_blank_and_boolean_without_materializing(self):
        from globalPlugins._speech_core.settings.presets import config_adapter
        for raw, expected in (({}, 'ClassicSpeech hook loaded'),
                              ({'speechHookLoadedMessage': ''}, ''),
                              ({'speechHookLoadedMessage': '  Ready  ', 'announceSpeechHookLoaded': 'False'}, '  Ready  ')):
            for key in ('announceSpeechHookLoaded', 'speechHookLoadedMessage'):
                self.section().pop(key, None)
            self.section().update(raw)
            before = copy.deepcopy(self.section())
            domain = config_adapter.capture()['speechHookAnnouncement']
            self.assertEqual(domain, {'version': 1, 'announceSpeechHookLoaded': False,
                                      'speechHookLoadedMessage': expected})
            self.assertEqual(self.section(), before)

    def test_defaults_and_strict_known_types(self):
        from globalPlugins._speech_core.settings.presets import model, domains
        wanted = self.wanted()
        self.assertEqual(domains.defaults()['speechHookAnnouncement'],
                         {'version': 1, 'announceSpeechHookLoaded': False,
                          'speechHookLoadedMessage': 'ClassicSpeech hook loaded'})
        for key, values in (('version', (True, '1', None)),
                            ('announceSpeechHookLoaded', (1, 'False', None)),
                            ('speechHookLoadedMessage', (False, 3, None, [], {}))):
            for value in values:
                bad = copy.deepcopy(wanted)
                bad['speechHookAnnouncement'][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    model.capture(bad)
        del wanted['speechHookAnnouncement']['speechHookLoadedMessage']
        with self.assertRaises(ValueError): model.capture(wanted)

    def test_absent_section_capture_and_cancel_remain_absent(self):
        import config
        from globalPlugins._speech_core.settings.presets import config_adapter, transaction
        root = config.conf.profiles[0]
        root.pop('classicSpeech', None)
        baseline = transaction.Transaction()
        self.assertFalse(config_adapter.capture()['speechHookAnnouncement']['announceSpeechHookLoaded'])
        self.assertNotIn('classicSpeech', root)
        config_adapter.apply(self.wanted())
        baseline.restore()
        self.assertNotIn('classicSpeech', root)

    def test_save_as_update_import_and_native_save_reload(self):
        from configobj import ConfigObj
        from globalPlugins._speech_core import settings_file, nvda_settings_backup
        from globalPlugins._speech_core.settings.presets import model, transfer
        d = self.dialog()
        d.load_working_presentation(self.wanted('Saved announcement'))
        p = d.presentationPresetsPanel
        with patch.object(p, 'prompt_name', return_value='Saved'):
            p.onSaveAs()
        key = p.selected()
        self.assertEqual(p.library.snapshot(key)['speechHookAnnouncement']['speechHookLoadedMessage'], 'Saved announcement')
        d.load_working_presentation(self.wanted('Updated announcement'))
        with patch.object(p, 'confirm', return_value=True): p.onUpdate()
        record = transfer.decode(transfer.encode(p.library.records[key]))
        imported = transfer.stage(p.library, record, 'Imported announcement')
        p.changed()
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(nvda_settings_backup, '_CONFIG_FOLDER_OVERRIDE', folder), \
                patch.object(settings_file, '_may_write_files', return_value=True):
            path = Path(settings_file.settings_path())
            d.onOK(None)
            self.assertFalse(path.exists())
            native = ConfigObj(encoding='UTF-8')
            native.filename = str(Path(folder) / 'nvda.ini')
            native['classicSpeech'] = copy.deepcopy(self.section())
            settings_file._wrap_nvda_ini_write(native)
            native.write()
            stored = ConfigObj(str(path), encoding='UTF-8')
            lib = model.Library(stored['presentationPresets'], d.get_working_presentation())
            self.assertEqual(lib.records[imported], record | {'name': 'Imported announcement'})
            self.assertEqual(stored['speechHookLoadedMessage'], 'Updated announcement')
            self.assertEqual(lib.snapshot(key)['speechHookAnnouncement']['speechHookLoadedMessage'], 'Updated announcement')

    def test_partial_legacy_unchanged_modified_and_update_expands_scope(self):
        from globalPlugins._speech_core.settings.presets import model, config_adapter
        current = self.wanted()
        config_adapter.apply(current)
        old = {k: current[k] for k in model.FIELDS}
        lib = model.Library('', old)
        key = lib.save_as('Legacy', old)
        config_adapter.apply(lib.load(key))
        self.assertEqual(config_adapter.capture()['speechHookAnnouncement'], current['speechHookAnnouncement'])
        changed = copy.deepcopy(current)
        changed['speechHookAnnouncement']['speechHookLoadedMessage'] = 'Other'
        self.assertFalse(lib.modified(changed))
        lib.update(key, changed)
        self.assertEqual(lib.snapshot(key)['speechHookAnnouncement'], changed['speechHookAnnouncement'])

    def test_explicit_load_speaks_only_loaded_feedback_and_preserves_operational_keys(self):
        from globalPlugins._speech_core import message_priority
        self.section().update(speechHookEnabled=False, debugLogging=True, prioritizeMessages=True,
                              voiceProfileData={'opaque': 'keep'})
        d = self.dialog()
        p = d.presentationPresetsPanel
        key = p.library.save_as('Announcement', self.wanted())
        p.refresh_list(key)
        with patch.object(p, 'confirm', return_value=True), \
                patch.object(message_priority, 'speak_message') as speak, \
                patch.object(self.plugin, 'set_speech_hook_enabled') as hook:
            p.onLoad()
            hook.assert_not_called()
            speak.assert_called_once_with('Announcement preset loaded')
        self.assertFalse(self.section()['speechHookEnabled'])
        self.assertTrue(self.section()['debugLogging'])
        self.assertTrue(self.section()['prioritizeMessages'])
        self.assertEqual(self.section()['voiceProfileData'], {'opaque': 'keep'})
        self.assertEqual(d.get_working_presentation()['speechHookAnnouncement'], self.wanted()['speechHookAnnouncement'])

    def test_cancel_close_apply_baseline_exact_raw_presence(self):
        for terminal in ('onCancel', 'onClose'):
            for present in (False, True):
                for key in ('announceSpeechHookLoaded', 'speechHookLoadedMessage'):
                    self.section().pop(key, None)
                if present:
                    self.section().update(announceSpeechHookLoaded='False', speechHookLoadedMessage='')
                before = copy.deepcopy(self.section())
                d = self.dialog()
                d.load_working_presentation(self.wanted())
                self.section()['unrelatedAnnouncementTest'] = 'keep'
                getattr(d, terminal)(self.event())
                before['unrelatedAnnouncementTest'] = 'keep'
                self.assertEqual(self.section(), before)
                d = self.dialog()
                d.load_working_presentation(self.wanted('Applied'))
                self.assertTrue(d.onApply(None))
                applied = copy.deepcopy(self.section())
                d.load_working_presentation(self.wanted('Cancelled'))
                getattr(d, terminal)(self.event())
                self.assertEqual(self.section(), applied)

    def test_failed_load_rolls_back_new_leaves(self):
        from globalPlugins._speech_core.settings.presets import config_adapter
        d = self.dialog()
        p = d.presentationPresetsPanel
        key = p.library.save_as('Broken', self.wanted())
        p.refresh_list(key)
        before = copy.deepcopy(self.section())
        def fail(snapshot):
            config_adapter.apply(snapshot)
            raise RuntimeError('injected after mutation')
        with patch.object(p, 'confirm', return_value=True), patch.object(d, 'load_working_presentation', side_effect=fail):
            p.onLoad()
        self.assertEqual(self.section(), before)

    def test_transfer_roundtrip_validation_future_and_opaque_fields(self):
        from globalPlugins._speech_core.settings.presets import model, transfer
        lib = model.Library('', self.wanted(''))
        key = lib.save_as('Portable', self.wanted(''))
        domain = lib.records[key]['domains']['speechHookAnnouncement']
        domain['opaque'] = {'keep': [1]}
        restored = transfer.decode(transfer.encode(lib.records[key]))
        self.assertEqual(restored, lib.records[key])
        other = model.Library('', self.wanted())
        imported = transfer.stage(other, restored, 'Imported')
        self.assertEqual(other.snapshot(imported)['speechHookAnnouncement']['speechHookLoadedMessage'], '')
        for field, value in (('announceSpeechHookLoaded', 'False'), ('speechHookLoadedMessage', 10)):
            bad = copy.deepcopy(restored)
            bad['domains']['speechHookAnnouncement'][field] = value
            payload = {'format': transfer.FORMAT, 'version': 1, 'preset': bad}
            with self.assertRaises(ValueError): transfer.decode(json.dumps(payload).encode())
        lib.update(key, self.wanted())
        self.assertEqual(domain['opaque'], {'keep': [1]})
        domain['version'] = 99
        self.assertNotIn('speechHookAnnouncement', lib.snapshot(key))
        lib.update(key, self.wanted())
        self.assertEqual(domain['version'], 99)

    def test_real_advanced_after_accepted_load_and_overlap_guard(self):
        from globalPlugins._speech_core.settings.advanced_panel import AdvancedPanel
        # Standalone owns no Advanced instance; the opener prevents stale open
        # General controls from coexisting with its transaction.
        self.plugin._settingsDialog = Mock()
        self.plugin._openPresentationPresets()
        self.plugin._settingsDialog.Raise.assert_called_once()
        self.plugin._settingsDialog = None
        d = self.dialog()
        d.load_working_presentation(self.wanted('Fresh preference'))
        d.onOK(None)
        g = self.general_dialog()
        g.advancedPanel = AdvancedPanel(g.panelHost)
        a = g.advancedPanel
        self.assertTrue(a.announceSpeechHookLoaded.GetValue())
        self.assertEqual(a.speechHookLoadedMessage.GetValue(), 'Fresh preference')
        self.assertTrue(a.speechHookLoadedMessage.enabled)
        a.debugLogging.SetValue(True)
        a.onChanged(self.event())
        self.assertTrue(g.onApply(None))
        self.assertEqual(self.section()['speechHookLoadedMessage'], 'Fresh preference')
        a.speechHookLoadedMessage.SetValue('Discard')
        a.onChanged(self.event())
        g.onCancel(None)
        self.assertEqual(self.section()['speechHookLoadedMessage'], 'Fresh preference')


if __name__ == '__main__':
    unittest.main(verbosity=2)
