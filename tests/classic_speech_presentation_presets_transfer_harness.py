"""Single-preset portable JSON and real bound manager transfer transactions."""
import copy
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
import classic_speech_presentation_presets_ui_harness as base


class TransferTests(unittest.TestCase):
    setUp = base.PresetUITests.setUp
    tearDown = base.PresetUITests.tearDown
    _controls = base.PresetUITests._controls
    section = base.PresetUITests.section
    event = base.PresetUITests.event
    dialog = base.PresetUITests.dialog

    def transfer(self):
        from globalPlugins._speech_core.settings.presets import transfer
        return transfer

    def record(self):
        from globalPlugins._speech_core.settings.presets.model import to_domains
        return {'name': 'Portable', 'domains': to_domains(self.dialog().get_working_presentation()),
                'future': {'opaque': [None, True, 'hello']}}

    def test_round_trip_opaque_and_no_runtime_or_library_metadata(self):
        t = self.transfer()
        record = self.record()
        record['domains']['future'] = {'opaque': True}
        record['domains']['tokens']['future'] = [1, 2]
        self.assertEqual(t.decode(t.encode(record)), record)
        data = json.loads(t.encode(record))
        self.assertEqual(set(data), {'format', 'version', 'preset'})
        self.assertNotIn('loaded', data)

    def test_reject_invalid_bounded_json_and_versions(self):
        t = self.transfer()
        good = json.loads(t.encode(self.record()))
        cases = [b'\xff', b'{', b'{}', b'[]', b'null', b'x' * (t.MAX_FILE_BYTES + 1),
                 b'{"version":1,"version":1}', b'{"x":NaN}']
        for version in (None, True, 0, 2, '1'):
            cases.append(json.dumps(dict(good, version=version)).encode())
        for value in (None, [], True):
            cases.append(json.dumps(dict(good, preset=value)).encode())
        broken = copy.deepcopy(good)
        broken['preset']['domains']['timing']['globalPause'] = True
        cases.append(json.dumps(broken).encode())
        cases.append(t.encode(self.record()).replace(b'"version": 1', b'"version": true', 1))
        cases.append(t.encode(self.record()).replace(b'"name": "Portable"', b'"name": "Portable", "name": "Other"'))
        cases.append(t.encode(self.record()).replace(b'"hello"', b'1e999'))
        cases.append(b'[' * 1500 + b'0' + b']' * 1500)
        for data in cases:
            with self.subTest(data=data[:80]), self.assertRaises(ValueError):
                t.decode(data)

    def test_atomic_replace_failure_keeps_existing_and_cleans_temp(self):
        t = self.transfer()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'preset.json'
            path.write_bytes(b'original')
            with patch.object(t.os, 'replace', side_effect=OSError('denied')):
                with self.assertRaises(OSError): t.write(path, self.record())
            self.assertEqual(path.read_bytes(), b'original')
            self.assertEqual([p.name for p in Path(folder).iterdir()], ['preset.json'])
            t.write(path, self.record())
            self.assertEqual(t.read(path), self.record())
            path.write_bytes(b' ' * (t.MAX_FILE_BYTES + 1))
            with self.assertRaises(ValueError): t.read(path)

    def file_dialog(self, path, accepted=True):
        import wx
        fake = types.SimpleNamespace(ShowModal=lambda: wx.ID_OK if accepted else wx.ID_CANCEL,
                                     GetPath=lambda: str(path), Destroy=Mock())
        for name, value in (('FD_OPEN', 1), ('FD_FILE_MUST_EXIST', 2), ('FD_SAVE', 4), ('FD_OVERWRITE_PROMPT', 8)):
            self.stack.enter_context(patch.object(wx, name, value, create=True))
        factory = self.stack.enter_context(patch.object(wx, 'FileDialog', return_value=fake, create=True))
        return fake, factory

    def speak(self):
        return self.stack.enter_context(patch('globalPlugins._speech_core.message_priority.speak_message'))

    def test_bound_import_staged_not_loaded_apply_cancel_ok_and_crud(self):
        import wx
        t = self.transfer()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'preset.json'
            record = self.record()
            record['domains']['timing']['globalPause'] = 321
            t.write(path, record)
            self.file_dialog(path)
            speak = self.speak()
            d = self.dialog(); p = d.presentationPresetsPanel
            before = copy.deepcopy(self.section()); live = d.get_working_presentation()
            loaded, reference = p.library.loaded, copy.deepcopy(p.library.reference)
            p.importBtn.bindings[wx.EVT_BUTTON](None)
            key = p.selected()
            self.assertEqual(p.library.records[key], record)
            self.assertEqual((p.library.loaded, p.library.reference), (loaded, reference))
            self.assertEqual(d.get_working_presentation(), live)
            self.assertEqual(self.section(), before)
            self.assertTrue(p.libraryChanged)
            self.assertEqual(speak.call_count, 1)
            d.onCancel(None)
            self.assertEqual(self.dialog().presentationPresetsPanel.library.records, {})
            d = self.dialog(); p = d.presentationPresetsPanel; p.onImport()
            self.assertTrue(d.onApply(None)); applied = self.section()['presentationPresets']
            with patch.object(p, 'prompt_name', return_value='Renamed'): p.onRename()
            with patch.object(p, 'confirm', return_value=True): p.onUpdate(); p.onDelete()
            d.onCancel(None)
            self.assertEqual(self.section()['presentationPresets'], applied)
            d = self.dialog(); p = d.presentationPresetsPanel
            p.refresh_list(next(iter(p.library.records)))
            with patch.object(p, 'prompt_name', return_value='Accepted'): p.onRename()
            d.onOK(None)
            self.assertIn('Accepted', self.section()['presentationPresets'])

    def test_collision_cancel_and_file_cancel_no_mutation(self):
        t = self.transfer()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'preset.json'; t.write(path, self.record())
            self.file_dialog(path)
            speak = self.speak()
            d = self.dialog(); p = d.presentationPresetsPanel
            p.library.save_as('Portable', d.get_working_presentation()); p.refresh_list()
            before = copy.deepcopy(p.library.__dict__)
            with patch.object(p, 'prompt_name', return_value=None) as prompt:
                p.onImport(); prompt.assert_called_once()
            self.assertEqual(p.library.__dict__, before); self.assertFalse(p.libraryChanged)
            speak.assert_not_called()
            with patch.object(p, 'prompt_name', return_value='Different'): p.onImport()
            self.assertEqual(len(p.library.records), 2)
            before = copy.deepcopy(p.library.__dict__)
            self.file_dialog(path, False); speak.reset_mock()
            p.onImport(); p.onExport()
            self.assertEqual(p.library.__dict__, before); speak.assert_not_called()

    def test_bound_export_saved_selection_not_live_and_survives_cancel(self):
        import wx
        t = self.transfer()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'export.json'; fake, factory = self.file_dialog(path)
            self.speak()
            d = self.dialog(); p = d.presentationPresetsPanel
            key = p.library.save_as('Saved', d.get_working_presentation()); p.refresh_list(key)
            saved = copy.deepcopy(p.library.records[key])
            live = d.get_working_presentation(); live['globalPause'] = 555; d.load_working_presentation(live)
            before = copy.deepcopy(p.library.__dict__)
            p.exportBtn.bindings[wx.EVT_BUTTON](None)
            self.assertEqual(t.read(path), saved)
            self.assertEqual(p.library.__dict__, before)
            self.assertFalse(p.libraryChanged)
            self.assertEqual(factory.call_args.kwargs['style'], wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
            fake.Destroy.assert_called_once()
            d.onCancel(None); self.assertTrue(path.exists())

    def test_future_read_only_import_and_defaults_export_disabled_and_rejected(self):
        self.transfer()
        self.section()['presentationPresets'] = '{"version":99,"records":{}}'
        d = self.dialog(); p = d.presentationPresetsPanel
        self.assertFalse(p.importBtn.enabled); self.assertFalse(p.exportBtn.enabled)
        before = copy.deepcopy(p.library.__dict__); speak = self.speak()
        p.onImport(); p.onExport()
        self.assertEqual(p.library.__dict__, before); self.assertEqual(speak.call_count, 2)

    def test_import_errors_once_without_dirty_or_metadata_mutation(self):
        self.transfer()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'invalid.json'; path.write_text('{}')
            self.file_dialog(path); speak = self.speak()
            d = self.dialog(); p = d.presentationPresetsPanel
            before = copy.deepcopy(p.library.__dict__)
            p.onImport()
            self.assertEqual(speak.call_count, 1); self.assertEqual(p.library.__dict__, before)
            self.assertFalse(p.libraryChanged)
            path.unlink(); speak.reset_mock(); p.onImport()
            self.assertEqual(speak.call_count, 1); self.assertEqual(p.library.__dict__, before)


    def test_accepted_import_native_write_boundary_and_settings_ini_reload(self):
        from configobj import ConfigObj
        from globalPlugins._speech_core import settings_file, nvda_settings_backup
        from globalPlugins._speech_core.settings.presets.model import Library
        t = self.transfer()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'preset.json'; t.write(path, self.record())
            self.file_dialog(path); self.speak()
            with patch.object(nvda_settings_backup, '_CONFIG_FOLDER_OVERRIDE', folder), patch.object(settings_file, '_may_write_files', return_value=True):
                settings_path = Path(settings_file.settings_path())
                d = self.dialog(); p = d.presentationPresetsPanel
                p.onImport(); key = p.selected()
                self.assertFalse(settings_path.exists())
                d.onOK(None)
                self.assertFalse(settings_path.exists())
                # Exercise the real base.write wrapper used by NVDA config save.
                native = ConfigObj(encoding='UTF-8')
                native.filename = str(Path(folder) / 'nvda.ini')
                native['classicSpeech'] = copy.deepcopy(self.section())
                settings_file._wrap_nvda_ini_write(native)
                native.write()
                stored = ConfigObj(str(settings_path), encoding='UTF-8')
                restored = Library(stored['presentationPresets'], d.get_working_presentation())
                self.assertEqual(restored.records[key], self.record())
                self.assertNotIn('classicSpeech', Path(native.filename).read_text(encoding='utf-8'))

    def test_stage_full_oversized_read_only_collision_and_bad_data_are_atomic(self):
        t = self.transfer()
        d = self.dialog(); library = d.presentationPresetsPanel.library
        record = self.record()
        for fault in ('full', 'oversized', 'future', 'collision', 'invalid'):
            with self.subTest(fault=fault):
                candidate = copy.deepcopy(library)
                source = copy.deepcopy(record)
                if fault == 'full':
                    candidate.records = {str(i): dict(record, name='Item ' + str(i)) for i in range(100)}
                elif fault == 'oversized':
                    candidate._extra['opaque'] = 'x' * 600001
                elif fault == 'future':
                    candidate.read_only = True
                elif fault == 'collision':
                    candidate.records['existing'] = record
                else:
                    source['domains']['messages']['passThroughAudioIndication'] = 1
                before = copy.deepcopy(candidate.__dict__)
                with self.assertRaises(ValueError): t.stage(candidate, source, 'Portable')
                self.assertEqual(candidate.__dict__, before)

    def test_legacy_partial_and_future_domains_are_passive_and_opaque(self):
        t = self.transfer()
        from globalPlugins._speech_core.settings.presets.model import DEFAULT_NAME
        d = self.dialog(); p = d.presentationPresetsPanel
        record = self.record()
        record['name'] = DEFAULT_NAME
        record['domains'] = {k: v for k, v in record['domains'].items() if k in ('tokens', 'timing')}
        record['domains']['messages'] = {'version': 99, 'opaque': {'run': 'never'}}
        decoded = t.decode(t.encode(record))
        before = d.get_working_presentation()
        with self.assertRaises(ValueError): t.stage(p.library, decoded, DEFAULT_NAME)
        key = t.stage(p.library, decoded, 'Imported defaults copy')
        self.assertEqual(d.get_working_presentation(), before)
        self.assertNotIn('messages', p.library.snapshot(key))
        p.library.update(key, before)
        self.assertEqual(p.library.records[key]['domains']['messages'], record['domains']['messages'])

    def test_import_close_and_export_errors_preserve_all_state(self):
        t = self.transfer()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'preset.json'; t.write(path, self.record())
            self.file_dialog(path); speak = self.speak()
            d = self.dialog(); p = d.presentationPresetsPanel
            before = copy.deepcopy(self.section())
            p.onImport(); d.onClose(self.event())
            self.assertEqual(self.section(), before)
            self.assertEqual(self.dialog().presentationPresetsPanel.library.records, {})
            d = self.dialog(); p = d.presentationPresetsPanel
            p.onImport(); before = copy.deepcopy(p.library.__dict__)
            changed = p.libraryChanged; speak.reset_mock()
            with patch.object(t.os, 'replace', side_effect=OSError('denied')): p.onExport()
            self.assertEqual(speak.call_count, 1)
            self.assertEqual(p.library.__dict__, before); self.assertEqual(p.libraryChanged, changed)
            self.assertEqual(t.read(path), self.record())

    def test_owner_teardown_during_file_or_name_modal_does_not_mutate(self):
        import wx
        t = self.transfer()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'preset.json'; t.write(path, self.record())
            for operation in ('import', 'export', 'name'):
                with self.subTest(operation=operation):
                    d = self.dialog(); p = d.presentationPresetsPanel
                    key = p.library.save_as('Portable', d.get_working_presentation()); p.refresh_list(key)
                    before = copy.deepcopy(p.library.__dict__)
                    fake, factory = self.file_dialog(path)
                    if operation != 'name':
                        def close_during_modal():
                            d._beginDestroy()
                            return wx.ID_OK
                        fake.ShowModal = close_during_modal
                        fake.GetPath = Mock(side_effect=AssertionError('path read after teardown'))
                    else:
                        def close_during_name(*args):
                            d._beginDestroy()
                            return 'New name'
                        self.stack.enter_context(patch.object(p, 'prompt_name', side_effect=close_during_name))
                    speak = self.speak()
                    p.onExport() if operation == 'export' else p.onImport()
                    self.assertEqual(p.library.__dict__, before)
                    speak.assert_not_called()
                    self.assertFalse(p.libraryChanged)

    def test_import_file_dialog_style_cleanup_and_cancel_before_io(self):
        import wx
        self.transfer()
        fake, factory = self.file_dialog('not-read.json', False)
        d = self.dialog(); p = d.presentationPresetsPanel
        with patch('globalPlugins._speech_core.settings.presets.transfer.read') as read:
            p.onImport(); read.assert_not_called()
        self.assertEqual(factory.call_args.kwargs['style'], wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        fake.Destroy.assert_called_once()
        for button in (p.importBtn, p.exportBtn):
            self.assertNotIn(wx.EVT_CHAR_HOOK, button.bindings)


if __name__ == '__main__':
    unittest.main(verbosity=2)
