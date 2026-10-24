"""Persistent dialog-owned audition, with no real NVDA speech or configuration."""
from __future__ import annotations
import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from classic_speech_voice_profiles_harness import VoiceDefaultDriver, FakeAction, NumericSetting
import classic_speech_nvda_master_harness as nvda_harness


class AuditionFixture:
    def setUp(self):
        nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
        nvda_harness._import_classic_speech_like_nvda()
        from globalPlugins._speech_core.settings.voice_profiles_audition import VoiceProfileAudition
        from globalPlugins._speech_core.settings.voice_profiles_audition import VoiceProfileAuditionOverlay
        self.driver = VoiceDefaultDriver()
        # Deliberately non-default, with Variant listed AFTER numeric settings.
        self.driver.variant = "variantB"
        self.driver.rate, self.driver.pitch, self.driver.breath = 43, 23, 4
        self.original = self.values()
        self.active = self.driver
        self.queue = []
        self.pre, self.post, self.changed = FakeAction(), FakeAction(), FakeAction()
        self.cancel_count = 0
        self.errors = []
        outer = self

        class Manager:
            def __init__(self):
                self.profiles = [{"speech": {"voiceDefaults": {"rate": 19, "unknown": "retain"}}}]
                self.saved = None
            def _handleProfileSwitch(self, **kwargs): pass
            def __getitem__(self, key): return self.profiles[-1].setdefault(key, {})
            def __contains__(self, key): return key in self.profiles[-1]
            def __setitem__(self, key, value): self.profiles[-1][key] = value
            def save(self, fail=False):
                # NVDA's already-registered driver callback runs before ours.
                self.profiles[-1].setdefault("speech", {})["voiceDefaults"] = outer.values()
                outer.pre.emit()
                if fail: raise OSError("disk full")
                self.saved = copy.deepcopy(self.profiles[0])
                outer.post.emit()
        self.manager = Manager()
        self.raw = copy.deepcopy(self.manager.profiles[0])
        self.session = VoiceProfileAudition(
            self.driver, active_synth_getter=lambda: self.active,
            cancel_speech=self.cancel,
            overlay_factory=lambda snapshot: VoiceProfileAuditionOverlay(
                self.manager, self.driver.name, snapshot, profile_factory=dict),
            pre_save=self.pre, post_save=self.post, synth_changed=self.changed,
            schedule=self.queue.append, on_error=self.errors.append, config_manager=self.manager,
        )

    def tearDown(self):
        if hasattr(self, "session"): self.session.close()
        nvda_harness._reset_global_plugin_imports()

    def cancel(self): self.cancel_count += 1
    def values(self):
        return {s.id: getattr(self.driver, s.id) for s in self.driver.supportedSettings}
    def select(self, **snapshot): self.session.select(snapshot)
    def drain(self):
        callbacks, self.queue = self.queue, []
        for callback in callbacks: callback()

class AuditionTests(AuditionFixture, unittest.TestCase):
    def test_nvda_source_save_does_not_serialize_or_lookup_unnamed_audition(self):
        import ast
        from unittest.mock import Mock
        from configobj import ConfigObj
        # Exercise actual reference ConfigManager.save, not an invented save
        # implementation. Only disk I/O and global actions are injected.
        tree = ast.parse((nvda_harness.NVDA_SOURCE / "config" / "__init__.py").read_text(encoding="utf-8"))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ConfigManager")
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "save")
        native = ast.Module(body=[method], type_ignores=[])
        env = {"pre_configSave": SimpleNamespace(notify=self.pre.emit),
               "post_configSave": SimpleNamespace(notify=self.post.emit),
               "NVDAState": SimpleNamespace(shouldWriteToDisk=lambda: True), "log": Mock()}
        exec(compile(native, "NVDA.ConfigManager.save", "exec"), env)
        base = ConfigObj(self.raw)
        base.filename = "not-a-real-file.ini"
        self.manager.profiles = [base]
        self.manager._dirtyProfiles = set()
        self.manager._profileCache = {}
        saved = []
        self.manager._writeProfileToFile = lambda filename, profile: saved.append(copy.deepcopy(dict(profile)))
        self.select(voice="voiceB", rate=97)
        self.manager.profiles[-1]["keyboard"] = {"speakTypedWords": True}
        self.manager._dirtyProfiles.add(None)  # AggregatedSection write-target name
        def driver_save():
            self.manager.profiles[-1]["speech"][self.driver.name] = self.values()
            self.manager._dirtyProfiles.add(None)
        self.pre.handlers.insert(0, driver_save)
        env["save"](self.manager)
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["speech"], self.raw["speech"])
        self.assertEqual(saved[0]["keyboard"], {"speakTypedWords": True})
        self.assertNotIn(None, self.manager._dirtyProfiles)
        self.drain()
        self.assertEqual(self.driver.rate, 97)

    def _nested_preview_returns_to_entire_audition(self, cancel):
        from globalPlugins._speech_core.settings.voice_profiles_preview import VoiceProfilePreviewController, PreviewEvents
        from unittest.mock import Mock
        self.select(voice="voiceB", variant="variantB", rate=81, breath=17)
        expected = self.values()
        overlay = self.session._overlay
        actions = [FakeAction() for _ in range(4)]
        timers = []
        def schedule(seconds, callback):
            handle = Mock()
            timers.append((handle, callback))
            return handle
        preview = VoiceProfilePreviewController(
            {"voice": "voiceA", "variant": "variantA"}, "sample",
            speak=lambda seq: None, index_command_factory=lambda token: token,
            events=PreviewEvents(*actions), scheduler=schedule,
            token_factory=lambda: 73, active_synth_getter=lambda: self.active)
        preview.start()
        if cancel:
            preview.cancel()
        else:
            actions[0].emit(synth=self.driver, index=73)
            actions[1].emit(synth=self.driver)
        self.assertEqual(self.values(), expected)
        self.assertTrue(self.session.active)
        self.assertIs(self.session._overlay, overlay)
        self.assertEqual(self.manager.profiles[-1]["speech"][self.driver.name], expected)
        timers[0][0].Stop.assert_called_once_with()
        for action in actions:
            self.assertFalse(action.handlers)
            action.emit(synth=self.driver, index=73)
        timers[0][1]()  # Already queued timeout must be inert.
        self.drain()
        self.assertEqual(self.values(), expected)
        self.assertEqual(self.manager.profiles[-1]["speech"][self.driver.name], expected)

    def test_nested_preview_completion_restores_entire_active_audition(self):
        self._nested_preview_returns_to_entire_audition(cancel=False)

    def test_nested_preview_cancel_restores_entire_active_audition(self):
        self._nested_preview_returns_to_entire_audition(cancel=True)

    def _native_save_fixture(self):
        import ast
        from types import MethodType
        from unittest.mock import Mock
        from configobj import ConfigObj
        self.session.close()
        tree = ast.parse((nvda_harness.NVDA_SOURCE / "config" / "__init__.py").read_text(encoding="utf-8"))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ConfigManager")
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "save")
        env = {"pre_configSave": SimpleNamespace(notify=self.pre.emit),
               "post_configSave": SimpleNamespace(notify=self.post.emit),
               "NVDAState": SimpleNamespace(shouldWriteToDisk=lambda: True), "log": Mock()}
        exec(compile(ast.Module(body=[method], type_ignores=[]), "NVDA.ConfigManager.save", "exec"), env)
        base = ConfigObj(self.raw)
        base.filename = "not-a-real-file.ini"
        other = ConfigObj({"speech": {"otherSynth": {"rate": 31}}, "custom": {"retain": "yes"}})
        other.filename = "unrelated-profile.ini"
        self.manager.profiles = [base]
        self.manager._dirtyProfiles = {"unrelated"}
        self.manager._profileCache = {None: base, "unrelated": other}
        saved = []
        self.manager._writeProfileToFile = lambda filename, profile: saved.append((filename, copy.deepcopy(dict(profile))))
        self.manager.save = MethodType(env["save"], self.manager)
        original_save = self.manager.save
        def driver_save():
            self.manager.profiles[-1].setdefault("speech", {})[self.driver.name] = self.values()
            if len(self.manager.profiles) > 1:
                self.manager._dirtyProfiles.add(None)
        self.pre.register(driver_save)
        from globalPlugins._speech_core.settings.voice_profiles_audition import VoiceProfileAudition, VoiceProfileAuditionOverlay
        self.session = VoiceProfileAudition(
            self.driver, active_synth_getter=lambda: self.active, cancel_speech=self.cancel,
            overlay_factory=lambda snapshot: VoiceProfileAuditionOverlay(
                self.manager, self.driver.name, snapshot, profile_factory=dict),
            pre_save=self.pre, post_save=self.post, synth_changed=self.changed,
            schedule=self.queue.append, on_error=self.errors.append, config_manager=self.manager)
        observed = []
        def late_handler():
            observed.append((len(self.manager.profiles), self.values()))
            self.manager["keyboard"]["speakTypedWords"] = True
        self.pre.register(late_handler)
        return saved, observed, base, other, original_save

    def test_native_save_late_handler_writes_same_payload_and_repeated_saves(self):
        saved, observed, base, other, original_save = self._native_save_fixture()
        self.select(voice="voiceB", variant="variantB", rate=81, breath=17)
        expected = self.values()
        self.manager.save()
        self.assertEqual(saved[0][1]["keyboard"], {"speakTypedWords": True})
        self.assertEqual(observed, [(1, self.original)])
        self.assertEqual(saved[0][1]["speech"], self.raw["speech"])
        self.assertEqual(saved[1], (other.filename, dict(other)))
        self.assertEqual(len(saved), 2)  # No extra unnamed/base profile write.
        self.assertEqual(self.manager._profileCache, {None: base, "unrelated": other})
        self.assertFalse(self.manager._dirtyProfiles)
        self.assertFalse(self.session.active)
        self.manager.save()  # Driver save before deferred audition resumption.
        self.assertEqual(saved[2][1], saved[0][1])
        self.assertEqual(len(saved), 3)
        self.assertEqual(observed, [(1, self.original)] * 2)
        self.drain()
        self.assertEqual(self.values(), expected)
        self.assertTrue(self.session.active)
        self.manager.save()
        self.session.close()
        self.drain()
        self.assertEqual(self.values(), self.original)
        self.assertEqual(self.manager.profiles, [base])
        self.assertEqual(self.manager.save, original_save)

    def test_failed_native_save_then_repeated_save_keeps_native_raw_presence(self):
        saved, observed, base, other, original_save = self._native_save_fixture()
        self.select(voice="voiceB", rate=96, breath=17)
        write = self.manager._writeProfileToFile
        def fail(filename, profile):
            raise OSError("disk full")
        self.manager._writeProfileToFile = fail
        with self.assertRaises(OSError):
            self.manager.save()
        self.assertEqual(self.values(), self.original)
        self.assertFalse(self.session.active)
        self.assertEqual(base["speech"], self.raw["speech"])
        self.assertFalse(self.queue)
        self.manager._writeProfileToFile = write
        self.manager.save()
        self.assertEqual(saved[0][1]["speech"], self.raw["speech"])
        self.assertEqual(saved[0][1]["keyboard"], {"speakTypedWords": True})
        self.assertEqual(observed, [(1, self.original)] * 2)
        self.drain()
        self.assertEqual(self.driver.rate, 96)
        self.session.close()
        self.assertEqual(self.manager.save, original_save)

    def test_save_wrapper_cleanup_does_not_overwrite_a_later_owner(self):
        from unittest.mock import Mock
        later_save = Mock()
        self.manager.save = later_save
        self.session.close()
        self.assertIs(self.manager.save, later_save)

    def test_preview_restores_other_selectors_before_numeric_and_boolean(self):
        from classic_speech_voice_profiles_harness import ChoiceSetting, BooleanSetting
        from globalPlugins._speech_core.settings.voice_profiles_preview import VoiceProfilePreviewController, PreviewEvents
        class Driver(VoiceDefaultDriver):
            @property
            def style(self): return self._style
            @style.setter
            def style(self, value):
                self._style = value
                self.breath = 3
                self.rateBoost = False
        driver = Driver()
        driver.supportedSettings += (BooleanSetting("rateBoost", "Boost"), ChoiceSetting("style", "Style"))
        driver.style, driver.rateBoost, driver.breath = "original", True, 17
        expected = {s.id: getattr(driver, s.id) for s in driver.supportedSettings}
        actions = [FakeAction() for _ in range(4)]
        preview = VoiceProfilePreviewController(
            {"voice": "voiceB", "style": "preview"}, "sample", speak=lambda seq: None,
            index_command_factory=lambda token: token, events=PreviewEvents(*actions),
            scheduler=lambda *args: None, token_factory=lambda: 1,
            active_synth_getter=lambda: driver)
        preview.start()
        preview.cancel()
        self.assertEqual({s.id: getattr(driver, s.id) for s in driver.supportedSettings}, expected)

    def test_selection_persists_through_ordinary_speech_and_cancellation(self):
        self.select(voice="voiceB", variant="variantA", rate=64)
        self.assertEqual((self.driver.voice, self.driver.rate, self.driver.breath), ("voiceB", 64, 9))
        self.cancel()  # ordinary key interruption must not end ownership
        self.assertEqual(self.driver.voice, "voiceB")
        self.assertTrue(self.session.active)
        self.session.close()
        self.assertEqual(self.values(), self.original)
        self.assertEqual(self.manager.profiles, [self.raw])

    def test_switch_starts_from_original_not_previous_override(self):
        self.select(voice="voiceB", rate=99, breath=17)
        self.select(voice="voiceA", variant="variantA")
        self.assertEqual((self.driver.rate, self.driver.breath), (40, 1))
        self.assertEqual(len(self.manager.profiles), 2)
        self.session.close()
        self.assertEqual(self.values(), self.original)

    def test_live_edit_reapplies_selected_record_and_restores_all_public_settings(self):
        self.select(voice="voiceB", variant="variantB", rate=72)
        self.select(voice="voiceB", variant="variantB", rate=81)
        self.assertEqual(self.driver.rate, 81)
        self.session.close()
        self.session.close()
        self.assertEqual(self.values(), self.original)

    def test_external_save_never_serializes_audition_and_resumes_identity_guarded(self):
        self.select(voice="voiceB", rate=88)
        self.manager.save()
        self.assertEqual(self.manager.saved, self.raw)
        self.assertEqual(self.values(), self.original)
        self.drain()
        self.assertEqual(self.driver.rate, 88)
        self.assertEqual(self.manager.profiles[0], self.raw)

    def test_rapid_selection_invalidates_queued_save_resume(self):
        self.select(voice="voiceB", rate=88)
        self.manager.save()
        self.select(voice="voiceA", rate=57)
        self.drain()
        self.assertEqual((self.driver.voice, self.driver.rate), ("voiceA", 57))
        self.assertEqual(len(self.manager.profiles), 2)

    def test_close_invalidates_callbacks_and_unregisters_actions(self):
        self.select(voice="voiceB")
        self.manager.save()
        self.session.close()
        self.drain()
        self.assertEqual(self.values(), self.original)
        self.assertEqual(self.manager.profiles, [self.raw])
        self.assertFalse(self.pre.handlers or self.post.handlers or self.changed.handlers)

    def test_save_failure_fails_native_until_next_explicit_selection(self):
        self.select(voice="voiceB")
        with self.assertRaises(OSError): self.manager.save(fail=True)
        self.assertEqual(self.values(), self.original)
        self.select(voice="voiceB", rate=53)
        self.assertEqual(self.driver.rate, 53)

    def test_driver_error_restores_and_removes_overlay(self):
        with self.assertRaises(KeyError): self.select(voice="invalid")
        self.assertEqual(self.values(), self.original)
        self.assertEqual(self.manager.profiles, [self.raw])

    def test_changed_synth_never_switches_or_mutates_replacement(self):
        self.select(voice="voiceB")
        replacement = VoiceDefaultDriver()
        self.active = replacement
        self.changed.emit()
        self.assertEqual(self.values(), self.original)
        self.assertEqual(replacement.voice, "voiceA")
        self.assertFalse(self.session.active)
        with self.assertRaises(RuntimeError): self.select(voice="voiceA")

    def test_preview_nested_restore_cannot_clobber_next_selection(self):
        from globalPlugins._speech_core.settings.voice_profiles_preview import VoiceProfilePreviewController, PreviewEvents
        actions = [FakeAction() for _ in range(4)]
        self.select(voice="voiceB", rate=61)
        preview = VoiceProfilePreviewController(
            {"voice": "voiceA", "rate": 77}, "sample", speak=lambda seq: None,
            index_command_factory=lambda token: token, events=PreviewEvents(*actions),
            scheduler=lambda *args: None, token_factory=lambda: 1,
            active_synth_getter=lambda: self.active)
        preview.start()
        preview.cancel()  # dialog cancels explicit Preview BEFORE changing audition
        self.select(voice="voiceA", rate=52)
        for action in actions: action.emit(synth=self.driver, index=1)
        self.assertEqual((self.driver.voice, self.driver.rate), ("voiceA", 52))

    def test_numeric_invalid_values_rejected_before_driver_assignment(self):
        for value in (True, "fast", -1, 101):
            with self.subTest(value=value):
                with self.assertRaises(ValueError): self.select(voice="voiceB", rate=value)
                self.assertEqual(self.values(), self.original)

    def test_unrelated_overlay_writes_carried_before_external_save(self):
        self.select(voice="voiceB")
        self.manager.profiles[-1]["keyboard"] = {"speakTypedWords": True}
        self.manager.save()
        self.assertEqual(self.manager.saved["keyboard"], {"speakTypedWords": True})
        self.assertEqual(self.manager.saved["speech"], self.raw["speech"])


    def test_repeated_saves_before_queued_resume_keep_raw_native_leaves(self):
        self.select(voice="voiceB", rate=96)
        self.manager.save()
        self.manager.save()
        self.assertEqual(self.manager.saved, self.raw)
        self.drain()
        self.assertEqual(self.driver.rate, 96)
        self.assertEqual(len(self.manager.profiles), 2)

    def test_restore_failure_continues_other_settings_and_retry_is_safe(self):
        from unittest.mock import patch
        self.select(voice="voiceB", rate=91)
        driver_type = type(self.driver)
        original_setattr = driver_type.__setattr__
        failed = []
        def setter(driver, key, value):
            if key == "rate" and value == self.original["rate"] and not failed:
                failed.append(key)
                raise RuntimeError("transient restore failure")
            return original_setattr(driver, key, value)
        with patch.object(driver_type, "__setattr__", setter):
            self.session.close()
            self.assertEqual(self.driver.pitch, self.original["pitch"])
            self.assertEqual(self.driver.breath, self.original["breath"])
            self.assertEqual(self.errors, ["rate"])
            self.session.close()
        self.assertEqual(self.values(), self.original)
        self.assertEqual(self.manager.profiles, [self.raw])

    def test_cancel_error_does_not_skip_restoration(self):
        self.select(voice="voiceB", rate=99)
        self.session._cancel_speech = lambda: (_ for _ in ()).throw(RuntimeError("cancel failed"))
        self.session.close()
        self.assertEqual(self.values(), self.original)
        self.assertEqual(self.manager.profiles, [self.raw])
        self.assertEqual(self.errors, ["cancelSpeech"])

    def test_synchronous_synth_change_during_assignment_stops_later_writes(self):
        from unittest.mock import patch
        driver_type = type(self.driver)
        original_setattr = driver_type.__setattr__
        def setter(driver, key, value):
            result = original_setattr(driver, key, value)
            if key == "voice" and value == "voiceB":
                self.active = VoiceDefaultDriver()
                self.changed.emit()
            return result
        with patch.object(driver_type, "__setattr__", setter):
            with self.assertRaises(RuntimeError): self.select(voice="voiceB", rate=99)
        self.assertEqual(self.values(), self.original)
        self.assertEqual(self.manager.profiles, [self.raw])
        self.assertEqual(self.active.rate, 40)


class AuditionDialogTests(AuditionFixture, unittest.TestCase):
    """Real dialog methods, working store and audition, fake native controls."""
    def make_dialog(self):
        from unittest.mock import Mock, patch
        from globalPlugins._speech_core.settings import voice_profiles_dialog as module
        from globalPlugins._speech_core.settings.voice_profiles_config import VoiceProfileStore
        import wx
        for target, name, value in (
            (module.nvdaControls, "EnhancedInputSlider", wx.TextCtrl),
            (wx, "EVT_SLIDER", object()),
            (wx.Dialog, "Destroy", lambda owner: True),
        ):
            stub = patch.object(target, name, value, create=True)
            stub.start()
            self.addCleanup(stub.stop)
        self.section = {"voiceProfileData": "{}"}
        store = VoiceProfileStore(self.driver, section=self.section)
        with patch.object(module.VoiceProfilesDialog, "_createAudition", return_value=self.session), \
             patch.object(module, "VoiceProfileStore", return_value=store), \
             patch.object(module.schemeStore, "SchemeStore"), \
             patch.object(wx, "ALIGN_BOTTOM", 0, create=True), \
             patch.object(wx, "CallAfter", side_effect=lambda callback, *args: self.queue.append(lambda: callback(*args))):
            dialog = module.VoiceProfilesDialog(None, self.driver)
        dialog.Destroy = Mock(wraps=dialog.Destroy)
        self.dialog = dialog
        return dialog

    def test_actual_constructor_selection_edit_switch_and_close(self):
        dialog = self.make_dialog()
        self.assertTrue(self.session.active)
        dialog._profile_value_changed("focusNavigation", "voice", "voiceB")
        dialog._profile_value_changed("focusNavigation", "rate", 65)
        self.assertEqual((self.driver.voice, self.driver.rate), ("voiceB", 65))
        dialog.onProfileChanged(SimpleNamespace(GetIndex=lambda: 1))
        self.assertEqual((self.driver.voice, self.driver.rate), ("voiceA", 40))
        dialog.onProfileChanged(SimpleNamespace(GetIndex=lambda: 0))
        self.assertEqual((self.driver.voice, self.driver.rate), ("voiceB", 65))
        dialog.onCancel(None)
        self.drain()
        self.assertEqual(self.values(), self.original)
        self.assertEqual(self.section["voiceProfileData"], "{}")
        self.assertEqual(self.manager.profiles, [self.raw])

    def test_actual_apply_then_later_edit_cancel_keeps_applied_registry_only(self):
        from unittest.mock import patch
        import config
        dialog = self.make_dialog()
        dialog._profile_value_changed("focusNavigation", "rate", 66)
        with patch.object(config, "conf", self.manager):
            self.assertTrue(dialog.onApply(None))
        applied = self.section["voiceProfileData"]
        self.assertEqual(self.driver.rate, 66)
        self.assertEqual(self.manager.saved["speech"], self.raw["speech"])
        dialog._profile_value_changed("focusNavigation", "rate", 89)
        dialog.onCancel(None)
        self.drain()
        self.assertEqual(self.section["voiceProfileData"], applied)
        self.assertEqual(self.values(), self.original)
        # Reopen uses the accepted record, not the canceled edit.
        from globalPlugins._speech_core.settings.voice_profiles_config import VoiceProfileStore
        reopened = VoiceProfileStore(self.driver, section=self.section)
        self.assertEqual(reopened.get_snapshot("focusNavigation")["rate"], 66)

    def test_actual_ok_saves_profile_and_restores_native(self):
        from unittest.mock import patch
        import config
        dialog = self.make_dialog()
        dialog._profile_value_changed("focusNavigation", "rate", 73)
        with patch.object(config, "conf", self.manager): dialog.onOK(None)
        self.assertIn('"rate":73', self.section["voiceProfileData"])
        self.assertEqual(self.values(), self.original)
        self.assertEqual(self.manager.saved["speech"], self.raw["speech"])
        self.drain()
        self.assertEqual(self.values(), self.original)

    def test_close_and_destroy_are_idempotent_and_invalidate_control_callbacks(self):
        from unittest.mock import Mock, patch
        import wx
        dialog = self.make_dialog()
        focus = Mock()
        with patch.object(wx, "CallAfter", side_effect=self.queue.append):
            dialog._deferOwned(focus)
        event = Mock()
        dialog.onClose(event)
        dialog.Destroy()
        self.drain()
        focus.assert_not_called()
        event.Skip.assert_called_once_with()
        self.assertEqual(self.values(), self.original)
        self.assertFalse(self.pre.handlers or self.post.handlers or self.changed.handlers)

    def test_stale_editor_event_cannot_mutate_new_profile_or_closed_dialog(self):
        dialog = self.make_dialog()
        dialog.onProfileChanged(SimpleNamespace(GetIndex=lambda: 1))
        before = copy.deepcopy(dialog.store._working_registry)
        dialog._profile_value_changed("focusNavigation", "rate", 91)
        self.assertEqual(dialog.store._working_registry, before)
        dialog.onCancel(None)
        before = copy.deepcopy(dialog.store._working_registry)
        dialog._profile_value_changed("reviewObjectNavigation", "rate", 93)
        self.assertEqual(dialog.store._working_registry, before)
        self.assertEqual(self.values(), self.original)

    def test_queued_preview_busy_release_does_not_outlive_dialog(self):
        from unittest.mock import Mock, patch
        import wx
        dialog = self.make_dialog()
        dialog._setPreviewBusy = Mock()
        with patch.object(wx, "CallAfter", side_effect=self.queue.append):
            dialog._onPreviewFinished("canceled")
        dialog.onCancel(None)
        self.drain()
        dialog._setPreviewBusy.assert_not_called()

    def test_failed_apply_leaves_native_and_cancel_restores_prior_registry(self):
        from unittest.mock import patch
        import config
        dialog = self.make_dialog()
        dialog._profile_value_changed("focusNavigation", "rate", 71)
        with patch.object(config, "conf", self.manager), patch.object(
            self.manager, "save", side_effect=lambda: self.manager.__class__.save(self.manager, fail=True)):
            self.assertFalse(dialog.onApply(None))
        self.assertEqual(self.values(), self.original)
        dialog.onCancel(None)
        self.assertEqual(self.section["voiceProfileData"], "{}")
        self.assertEqual(len(self.manager.profiles), 1)
        self.assertEqual(self.manager.profiles[0]["speech"], self.raw["speech"])

    def test_plugin_unload_closes_actual_dialog_and_restores_before_other_cleanup(self):
        from unittest.mock import Mock
        import ast
        dialog = self.make_dialog()
        dialog._profile_value_changed("focusNavigation", "rate", 75)
        tree = ast.parse((ROOT / "classicSpeech.py").read_text(encoding="utf-8"))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "GlobalPlugin")
        terminate = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "terminate")
        # Exercise the real unload prefix, without unrelated native hook teardown.
        prefix = ast.Module(body=terminate.body[:2], type_ignores=[])
        plugin = SimpleNamespace(_voiceProfilesDialog=dialog)
        exec(compile(prefix, "classicSpeech.terminate", "exec"), {"self": plugin, "log": Mock()})
        self.drain()
        self.assertIsNone(plugin._voiceProfilesDialog)
        self.assertEqual(self.values(), self.original)
        self.assertFalse(self.pre.handlers or self.post.handlers or self.changed.handlers)


    def test_controls_show_actual_defaults_and_historical_baseline_edit_is_explicit(self):
        dialog = self.make_dialog()
        # Opening baseline Rate=43, but native selector application resolves 40.
        self.assertEqual(dialog.currentControls.snapshot["rate"], self.driver.rate)
        self.assertEqual(self.driver.rate, 40)
        before = copy.deepcopy(dialog.store._working_registry)
        dialog.onProfileChanged(SimpleNamespace(GetIndex=lambda: 1))
        dialog.onProfileChanged(SimpleNamespace(GetIndex=lambda: 0))
        self.assertEqual(dialog.store._working_registry, before)
        dialog._profile_value_changed("focusNavigation", "rate", 43)
        self.assertEqual(self.driver.rate, 43)
        self.assertEqual(dialog.store.get_preview_snapshot("focusNavigation")["rate"], 43)
        dialog.onCancel(None)

    def test_dependent_choice_refresh_uses_new_values_without_replacing_voice_control(self):
        from globalPlugins._speech_core.settings.voice_profile_controls import VoiceProfileControls
        from classic_speech_voice_profiles_harness import ChoiceSetting, ChoiceInfo
        from unittest.mock import Mock
        driver = self.driver
        driver.availableVariants = {"old": ChoiceInfo("old", "Old")}
        adapter = VoiceProfileControls(driver, {"voice": "voiceA", "variant": "old"}, Mock())
        controls = {s.setting_id: Mock() for s in adapter.settings}
        for control in controls.values(): control.IsBeingDeleted.return_value = False
        adapter._controls_by_setting_id = controls
        voice_control = controls["voice"]
        driver.availableVariants = {"new": ChoiceInfo("new", "New")}
        adapter.snapshot = {**self.original, "variant": "new"}
        self.assertTrue(adapter.refresh_snapshot_values(skip_setting_id="voice"))
        self.assertIs(adapter._controls_by_setting_id["voice"], voice_control)
        controls["variant"].SetItems.assert_called_once_with(["New"])
        adapter._choice_changed(SimpleNamespace(GetSelection=lambda: 0), "variant")
        adapter.on_change.assert_called_once_with("variant", "new")

    def test_stale_preview_finished_callback_cannot_release_new_preview_busy_state(self):
        from unittest.mock import Mock, patch
        import wx
        dialog = self.make_dialog()
        dialog._previewController = SimpleNamespace(active=False)
        dialog._setPreviewBusy = Mock()
        with patch.object(wx, "CallAfter", side_effect=self.queue.append):
            dialog._onPreviewFinished("completed")
        dialog._previewController = SimpleNamespace(active=True, cancel=lambda: None)
        self.drain()
        dialog._setPreviewBusy.assert_not_called()
        dialog._previewController = None
        dialog.onCancel(None)

    def test_close_exception_still_restores_native_and_propagates_close_event(self):
        from unittest.mock import Mock
        dialog = self.make_dialog()
        dialog.schemeStore.cancel.side_effect = RuntimeError("scheme cancel failed")
        event = Mock()
        with self.assertRaises(RuntimeError): dialog.onClose(event)
        self.assertEqual(self.values(), self.original)
        event.Skip.assert_called_once_with()
        self.assertEqual(self.section["voiceProfileData"], "{}")


if __name__ == "__main__": unittest.main()
