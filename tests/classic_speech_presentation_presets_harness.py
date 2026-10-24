"""Presentation preset domain, working controls and persistence regressions."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
import classic_speech_nvda_master_harness as harness


class PresetsTests(unittest.TestCase):
    def setUp(self):
        harness.ClassicSpeechNVDAConfigStartupTests().setUp()
        harness._import_classic_speech_like_nvda()
        from globalPlugins._speech_core.settings.presets import model
        self.m = model
        self.shape = model.defaults()

    def tearDown(self):
        harness._reset_global_plugin_imports()

    def test_unknown_fields_in_known_domains_survive_known_field_replacement(self):
        lib = self.m.Library('', self.shape)
        key = lib.save_as('Work', self.shape)
        domains = lib.records[key]['domains']
        domains['tokens']['futureField'] = {'opaque': ['keep']}
        domains['timing']['futureTiming'] = [1, {'keep': True}]
        domains['futureDomain'] = {'keep': 9}
        lib = self.m.Library(lib.serialize(), self.shape)
        changed = copy.deepcopy(self.shape)
        changed.update(renames={'button': 'push'}, mutedLabels=['checked'], globalPause=333)
        lib.update(key, changed)
        lib.update(key, self.shape)
        domains = lib.records[key]['domains']
        self.assertEqual(domains['tokens']['futureField'], {'opaque': ['keep']})
        self.assertEqual(domains['timing']['futureTiming'], [1, {'keep': True}])
        self.assertEqual(domains['futureDomain'], {'keep': 9})
        self.assertEqual(lib.snapshot(key), self.shape)

    def test_unsupported_library_preserves_raw_and_blocks_every_mutator(self):
        raw = ' {"version":2,"records":{},"future":["opaque"]} '
        lib = self.m.Library(raw, self.shape)
        for action in (lambda: lib.save_as('New', self.shape),
                       lambda: lib.update('future', self.shape),
                       lambda: lib.rename('future', 'New'), lambda: lib.delete('future')):
            with self.assertRaisesRegex(ValueError, 'read-only'): action()
        self.assertEqual(lib.load('defaults'), self.shape)
        self.assertEqual(lib.serialize(), raw)

    def test_default_is_canonical_and_capture_is_narrow(self):
        from globalPlugins._speech_core.verbosity import VerbosityManager
        self.assertEqual(self.shape, VerbosityManager.DEFAULT_SHAPE)
        source = dict(copy.deepcopy(self.shape), voices={'secret': 1}, enabledTokens={'role': False})
        self.assertEqual(self.m.capture(source), self.shape)
        source['renames']['button'] = 'btn'
        self.assertNotEqual(self.shape, self.m.capture(source))

    def test_crud_protected_duplicate_and_content_modified(self):
        lib = self.m.Library('', self.shape)
        self.assertFalse(lib.modified(self.shape))
        changed = copy.deepcopy(self.shape)
        changed['globalPause'] = 160
        self.assertTrue(lib.modified(changed))
        key = lib.save_as('Work', changed)
        self.assertFalse(lib.modified(changed))
        lib.rename(key, 'Office')
        self.assertEqual(lib.records[key]['name'], 'Office')
        for name in ('', '  ', 'OFFICE', 'ClassicSpeech defaults', 'x' * 81):
            with self.assertRaises(ValueError): lib.save_as(name, changed)
        for operation in (lambda: lib.update('defaults', changed),
                          lambda: lib.rename('defaults', 'Other'),
                          lambda: lib.delete('defaults')):
            with self.assertRaises(ValueError): operation()
        lib.update(key, self.shape)
        self.assertFalse(lib.modified(self.shape))
        lib.delete(key)
        self.assertEqual(lib.records, {})

    def test_version_and_malformed_fail_closed_without_mutating_current(self):
        for raw in ('oops', '{}', '{"version":99}', '[]', 'x' * 600001):
            with self.subTest(raw=raw[:30]):
                lib = self.m.Library(raw, self.shape)
                self.assertEqual(lib.records, {})
                self.assertFalse(lib.modified(self.shape))
        lib = self.m.Library('', self.shape)
        key = lib.save_as('Good', self.shape)
        encoded = json.loads(lib.serialize())
        encoded['records']['bad'] = {'name': 'Bad', 'domains': {'timing': {'globalPause': -200}}}
        recovered = self.m.Library(json.dumps(encoded), self.shape)
        self.assertEqual(list(recovered.records), [key])
        self.assertEqual(recovered.serialize(), lib.serialize())
        for field, value in (('globalPause', True), ('pauseAfterFinalToken', 'False'),
                             ('order', ['name']), ('renames', {'a': []}),
                             ('pauseMode', 'invalid'), ('pauses', {'role': -3})):
            bad = dict(self.shape, **{field: value})
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.m.capture(bad)

    def test_roundtrip_and_merge_preserve_unrelated(self):
        lib = self.m.Library('', self.shape)
        key = lib.save_as('Work', self.shape)
        loaded = self.m.Library(lib.serialize(), self.shape)
        self.assertEqual(loaded.records, lib.records)
        current = dict(self.shape, future={'unknown': [1]}, enabledTokens={'role': False})
        result = self.m.merge(current, loaded.load(key))
        self.assertEqual(result['future'], current['future'])
        self.assertEqual(result['enabledTokens'], current['enabledTokens'])
        result['future']['unknown'].append(2)
        self.assertEqual(current['future'], {'unknown': [1]})

    def test_settings_file_roundtrip_with_real_configobj_and_interpolation_text(self):
        import tempfile
        from unittest.mock import patch
        from globalPlugins._speech_core import settings_file
        from configobj import ConfigObj
        lib = self.m.Library('', self.shape)
        self.shape['renames'] = {'button': '%(notAVariable)s "quoted" café'}
        key = lib.save_as('100% %(notAVariable)s', self.shape)
        data = {'presentationPresets': lib.serialize(), 'other': {'keep': 'untouched'}}
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'settings.ini')
            with patch.object(settings_file, '_may_write_files', return_value=True):
                self.assertTrue(settings_file.write_settings_file(data, path))
            stored = ConfigObj(path, encoding='UTF-8')
            restored = self.m.Library(stored['presentationPresets'], self.m.defaults())
            self.assertEqual(restored.load(key), self.shape)
            self.assertEqual(stored['other'], {'keep': 'untouched'})
            self.assertEqual(settings_file.load_settings_file(path)['presentationPresets'], lib.serialize())

    def test_existing_out_of_format_settings_stay_current_and_library_is_bounded(self):
        current = copy.deepcopy(self.shape)
        current['globalPause'] = 5000
        before = copy.deepcopy(current)
        lib = self.m.Library('malformed', current)
        self.assertEqual(current, before)
        self.assertIsNone(lib.loaded)
        self.assertTrue(lib.modified(current))
        with self.assertRaises(ValueError): lib.save_as('Too long', current)
        self.assertEqual(lib.records, {})
        lib = self.m.Library('', self.shape)
        for index in range(self.m.MAX_RECORDS): lib.save_as(str(index), self.shape)
        with self.assertRaises(ValueError): lib.save_as('Overflow', self.shape)
        self.assertEqual(len(lib.records), self.m.MAX_RECORDS)


if __name__ == '__main__':
    unittest.main(verbosity=2)
