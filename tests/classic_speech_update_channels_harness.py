"""Channel policy, public discovery and native settings regressions; no network."""
import importlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import classic_speech_update_check_harness as baseline
from classic_speech_update_check_harness import FakeResponse, FakeSession, _github_release

ROOT = Path(__file__).resolve().parents[1]
REPO = "trssharp/classicspeech-nvda"


def dev_release(version="20260928.1", **extra):
    tag = "dev-" + version
    name = f"ClassicSpeech-{version}.nvda-addon"
    prefix = f"https://github.com/{REPO}/releases/download/{tag}/"
    data = _github_release(tag=tag, prerelease=True, draft=False)
    data["assets"] = [
        {"name": name, "browser_download_url": prefix + name, "size": 16},
        {"name": name + ".sha256", "browser_download_url": prefix + name + ".sha256"},
    ]
    data.update(extra)
    return data


class ChannelTests(unittest.TestCase):
    setUp = baseline.UpdateCheckTests.setUp
    tearDown = baseline.UpdateCheckTests.tearDown
    _checker = baseline.UpdateCheckTests._checker

    def test_preference_defaults_and_normalization(self):
        self.assertEqual(self.updates.preferred_channel(), "stable")
        for value, expected in [("dev", "dev"), ("stable", "stable"), ("nightly", "stable"), (None, "stable")]:
            self.updates.set_preferred_channel(value)
            self.assertEqual(self.updates.preferred_channel(), expected)

    def _build_metadata(self, channel="dev"):
        channels = importlib.import_module("globalPlugins._speech_core.update_channels")
        addon = Path(self.folder) / "addon"
        path = addon / "globalPlugins" / "_speech_core" / "build_info.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"channel": channel, "version": "20260928.1"}), encoding="utf-8")
        (addon / "manifest.ini").write_text("name = classicSpeech\nversion = 20260928.1\n", encoding="utf-8")
        return channels, path

    def test_build_defaults_and_saved_choices_with_real_configobj(self):
        import config
        from configobj import ConfigObj
        from validate import Validator
        from types import SimpleNamespace
        settings = importlib.import_module("globalPlugins._speech_core.settings_file")
        backup = importlib.import_module("globalPlugins._speech_core.nvda_settings_backup")
        plugin = importlib.import_module("globalPlugins._speech_core.plugin_config")
        for build in ("dev", "stable", "unknown"):
            channels, path = self._build_metadata(build)
            for saved in (None, "stable", "dev", "nightly", ["dev", "stable"]):
                for injected in (False, True):
                    with self.subTest(build=build, saved=saved, injected=injected), patch.object(
                        channels, "METADATA_PATH", path
                    ), patch.object(backup, "_CONFIG_FOLDER_OVERRIDE", self.folder):
                        importlib.reload(plugin)
                        spec = ConfigObj({"classicSpeech": plugin._CLASSIC_SPEECH_SPEC})
                        base = ConfigObj(configspec=spec)
                        base.filename = str(Path(self.folder) / "nvda.ini")
                        if injected:
                            base.validate(Validator())
                            self.assertIn("updateChannel", base["classicSpeech"].defaults)
                            self.assertEqual(base["classicSpeech"]["updateChannel"], "dev" if build == "dev" else "stable")
                        settings.write_settings_file({} if saved is None else {"updateChannel": saved})
                        before = Path(settings.settings_path()).read_bytes()
                        conf = SimpleNamespace(profiles=[base], spec=spec, BASE_ONLY_SECTIONS=set())
                        with patch.object(config, "conf", conf):
                            plugin._initClassicSpeechConfig()
                            expected = saved if saved in ("stable", "dev") else (
                                "dev" if saved is None and build == "dev" else "stable"
                            )
                            self.assertEqual(self.updates.preferred_channel(), expected)
                            self.assertEqual(Path(settings.settings_path()).read_bytes(), before)
                            base.write()  # Only the existing NVDA save route writes.
                            conf.profiles = [ConfigObj(base.filename, encoding="utf-8", configspec=spec)]
                            plugin._initClassicSpeechConfig()
                            self.assertEqual(self.updates.preferred_channel(), expected)
                            # Factory defaults use this build, not a previous saved preference.
                            conf.profiles = [ConfigObj(configspec=spec)]
                            conf.profiles[0].validate(Validator())
                            settings.load_into_nvda(conf, factory_defaults=True)
                            self.assertEqual(self.updates.preferred_channel(), "dev" if build == "dev" else "stable")
        importlib.reload(plugin)

    def test_metadata_default_fails_closed_without_version_inference(self):
        channels, path = self._build_metadata()
        with patch.object(channels, "METADATA_PATH", path):
            self.assertEqual(channels.default_update_channel(), "dev")
            for raw in ("{", "[]", "null", '{}', '{"channel":"nightly"}',
                        '{"channel":"dev","version":"wrong"}'):
                path.write_text(raw, encoding="utf-8")
                self.assertEqual(channels.default_update_channel(), "stable")
            path.unlink()
            self.assertEqual(channels.default_update_channel(), "stable")
            self._build_metadata()
            manifest = path.parents[2] / "manifest.ini"
            manifest.write_text("[broken", encoding="utf-8")
            self.assertEqual(channels.default_update_channel(), "stable")
            manifest.unlink()
            self.assertEqual(channels.default_update_channel(), "stable")

    def test_fresh_dev_dialog_ok_apply_cancel_do_not_add_disk_writes(self):
        import config
        from configobj import ConfigObj
        from validate import Validator
        settings = importlib.import_module("globalPlugins._speech_core.settings_file")
        backup = importlib.import_module("globalPlugins._speech_core.nvda_settings_backup")
        plugin = importlib.import_module("globalPlugins._speech_core.plugin_config")
        module = importlib.import_module("globalPlugins._speech_core.settings.dialog")
        channels, path = self._build_metadata()
        with patch.object(channels, "METADATA_PATH", path), patch.object(
            backup, "_CONFIG_FOLDER_OVERRIDE", self.folder
        ):
            importlib.reload(plugin)
            base = ConfigObj(configspec=ConfigObj({"classicSpeech": plugin._CLASSIC_SPEECH_SPEC}))
            base.validate(Validator())
            base.filename = str(Path(self.folder) / "nvda.ini")
            conf = config.conf
            conf.profiles = [base]
            conf.spec = {}
            with patch.object(config, "conf", conf), patch.object(
                settings, "write_settings_file", wraps=settings.write_settings_file
            ) as writer:
                plugin._initClassicSpeechConfig()
                self.assertEqual(self.updates.preferred_channel(), "dev")
                self.assertNotIn("updateChannel", settings._stored_values(base["classicSpeech"]))
                for accept in ("onApply", "onOK"):
                    self.updates.set_preferred_channel("dev")
                    dialog = object.__new__(module.ClassicSpeechDialog)
                    dialog._popupReleased = False
                    dialog._committed = False
                    dialog._initializeDialogTransaction()
                    class Choice(self.wx.Choice):
                        def SetSelection(self, value):
                            self.selection = value

                        def GetSelection(self):
                            return self.selection

                    with patch.object(self.wx, "Choice", Choice):
                        panel = dialog.advancedPanel = module.AdvancedPanel(None)
                    self.assertEqual(panel.updateChannel.GetSelection(), 1)
                    dialog._saveTransaction = lambda: panel.apply_live()
                    dialog._clearDirty = lambda: None
                    panel.updateChannel.GetSelection = lambda: 0
                    panel.onChanged()
                    getattr(dialog, accept)(None)
                    self.assertEqual(self.updates.preferred_channel(), "stable")
                    panel.updateChannel.GetSelection = lambda: 1
                    panel.onChanged()
                    dialog.onCancel(None)
                    self.assertEqual(self.updates.preferred_channel(), "stable")
                writer.assert_not_called()
                self.assertFalse(Path(settings.settings_path()).exists())
                base.write()
                writer.assert_called_once()
                conf.profiles = [ConfigObj(base.filename, encoding="utf-8")]
                plugin._initClassicSpeechConfig()
                self.assertEqual(self.updates.preferred_channel(), "stable")
        importlib.reload(plugin)

    def test_dev_release_contract(self):
        parse = self.updates.release_from_github
        good = dev_release()
        release = parse(good, channel="dev", repository=REPO)
        self.assertEqual((release.version, release.channel), ("20260928.1", "dev"))
        self.assertIsNone(parse(good))
        for extra in [dict(prerelease=False), dict(draft=True), dict(tag_name="nightly"),
                      dict(tag_name="dev-20260230.1"), dict(tag_name="dev-20260928.0"), dict(assets=[])]:
            self.assertIsNone(parse(dev_release(**extra), channel="dev", repository=REPO))
        self.assertIsNone(parse(good, channel="dev", repository="attacker/fork"))
        good["assets"][0]["browser_download_url"] = "https://evil.example/addon"
        self.assertIsNone(parse(good, channel="dev", repository=REPO))

    def test_dev_paginates_and_selects_newest_not_first(self):
        url = f"https://api.github.com/repos/{REPO}/releases?per_page=100&page="
        session = FakeSession({
            url + "1": FakeResponse(data=[_github_release()] * 99 + [dev_release("20260928.1")]),
            url + "2": FakeResponse(data=[dev_release("20260928.2"), dev_release("20260927.9")]),
        })
        result = self.updates.fetch_latest_release("2.0", REPO, session=session, channel="dev")
        self.assertEqual(result.version, "20260928.2")
        self.assertEqual(len(session.requests), 2)
        self.assertTrue(all("Authorization" not in kwargs["headers"] for _, kwargs in session.requests))

    def test_empty_dev_is_honest_and_errors_do_not_fall_back(self):
        url = f"https://api.github.com/repos/{REPO}/releases?per_page=100&page=1"
        result = self.updates.fetch_latest_release("2.0", REPO, session=FakeSession({url: FakeResponse(data=[])}), channel="dev")
        self.assertIsNone(result)
        checker = self._checker()
        checker._checked(None, "2.0", REPO, manual=True, channel="dev")
        self.assertIn("No development release", checker.messages[-1])
        for response in [FakeResponse(status_code=401), FakeResponse(data={}), OSError("offline")]:
            with self.assertRaises(self.updates.UpdateError):
                self.updates.fetch_latest_release("2.0", REPO, session=FakeSession({url: response}), channel="dev")

    def test_switch_to_lower_stable_is_manual_and_explicit(self):
        release = self.updates.release_from_github(_github_release(tag="v2.0"))
        checker = self._checker()
        with patch.object(self.updates, "installed_channel", return_value="dev"):
            checker._checked(release, "20260928.1", REPO, manual=False)
            self.assertEqual(checker.offers, [])
            checker._checked(release, "20260928.1", REPO, manual=True)
        self.assertEqual(len(checker.offers), 1)
        self.assertIn("Switch", checker.offers[0][0])
        self.assertIn("lower", checker.offers[0][0])
        self.assertEqual(checker.downloads, [])

    def test_same_channel_never_offers_equal_or_older(self):
        release = self.updates.release_from_github(dev_release(), channel="dev", repository=REPO)
        with patch.object(self.updates, "installed_channel", return_value="dev"):
            for manual in (False, True):
                for version in ("20260928.1", "20260928.2"):
                    checker = self._checker()
                    checker._checked(release, version, REPO, manual=manual, channel="dev")
                    self.assertEqual(checker.offers, [])

    def test_metadata_is_version_bound_and_legacy_dates_unknown(self):
        channels = importlib.import_module("globalPlugins._speech_core.update_channels")
        path = Path(self.folder) / "build_info.json"
        with patch.object(channels, "METADATA_PATH", path):
            self.assertEqual(self.updates.installed_channel("2.0"), "stable")
            self.assertEqual(self.updates.installed_channel("20260928.1"), "unknown")
            path.write_text(json.dumps({"channel": "dev", "version": "20260928.1"}), encoding="utf-8")
            self.assertEqual(self.updates.installed_channel("20260928.1"), "dev")
            self.assertEqual(self.updates.installed_channel("20260929.1"), "unknown")

    def test_manual_and_automatic_use_preference_but_opt_out_stops_only_auto(self):
        self.updates.set_preferred_channel("dev")
        checker = self._checker()
        calls = []
        with patch.object(self.updates, "installed_addon", return_value=("2.0", REPO)), patch.object(
            self.updates, "fetch_latest_release", side_effect=lambda *a, **kw: calls.append(kw["channel"])
        ):
            checker._run = lambda work, done: (work(), setattr(checker, "_busy", False))
            checker.check(manual=False)
            self.updates.set_automatic_checks_enabled(False)
            checker.check(manual=False)
            checker.check(manual=True)
        self.assertEqual(calls, ["dev", "dev"])

    def test_stale_or_stopped_callback_never_offers(self):
        checker = self._checker()
        self.updates.set_preferred_channel("dev")
        checker._checked_current(self.release, "1.0", REPO, True, "stable")
        self.assertEqual(checker.offers, [])
        checker.stop()
        checker._checked(self.release, "1.0", REPO, True)
        self.assertEqual(checker.offers, [])

    def test_automatic_delay_due_and_disabled_timer_callback(self):
        checker = self._checker()
        scheduled = []
        with patch.object(self.updates, "installed_addon", return_value=("2.0", REPO)), patch.object(
            self.wx, "CallLater", side_effect=lambda *a, **kw: scheduled.append((a, kw)), create=True
        ):
            checker.schedule_automatic_check()
            self.assertEqual(scheduled[0][0][0], 30000)
            self.updates.set_automatic_checks_enabled(False)
            checker._run = lambda *args: self.fail("disabled timer reached network")
            scheduled[0][0][1](**scheduled[0][1])
            self.updates.set_automatic_checks_enabled(True)
            self.updates._remember_check()
            checker.schedule_automatic_check()
            self.assertEqual(len(scheduled), 1)

    def test_stable_latest_rejects_draft_and_prerelease(self):
        url = self.updates.API_URL.format(repository=REPO)
        for flags in [dict(prerelease=True), dict(draft=True)]:
            with self.assertRaises(self.updates.UpdateError):
                self.updates.fetch_latest_release("2.0", REPO, session=FakeSession({url: FakeResponse(data=_github_release(**flags))}))

    def test_unknown_legacy_date_does_not_auto_switch_or_repeat_same_build(self):
        checker = self._checker()
        release = self.updates.release_from_github(dev_release(), channel="dev", repository=REPO)
        checker._checked(release, release.version, REPO, True, "dev")
        checker._checked(release, "20260927.1", REPO, False, "dev")
        self.assertEqual(checker.offers, [])
        checker._checked(release, "20260927.1", REPO, True, "dev")
        self.assertIn("unknown", checker.offers[0][0])

    def test_cross_channel_install_requires_affirmative_response(self):
        checker = self._checker()
        self.updates.set_preferred_channel("dev")
        release = self.updates.release_from_github(dev_release(), channel="dev", repository=REPO)
        checker._checked(release, "2.0", REPO, True, "dev")
        self.assertEqual(checker.downloads, [])
        checker._show_offer = lambda *a, **kw: self.wx.ID_YES
        checker._checked(release, "2.0", REPO, True, "dev")
        self.assertEqual(checker.downloads, [release.version])

    def test_download_rejects_foreign_source_and_unsafe_names_before_network(self):
        from dataclasses import replace
        for fields in [dict(addon_url="https://evil.example/addon"),
                       dict(checksum_url="http://github.com/trssharp/classicspeech-nvda/sha"),
                       dict(addon_name="../escape.nvda-addon"), dict(addon_name="C:\\escape.nvda-addon")]:
            session = FakeSession({})
            with self.assertRaises(self.updates.UpdateError):
                self.updates.download_release(replace(self.release, **fields), "1.0", REPO, self.folder, session)
            self.assertEqual(session.requests, [])

    def test_channel_settings_survive_real_configobj_save_reload(self):
        import config
        from configobj import ConfigObj
        from types import SimpleNamespace
        settings = importlib.import_module("globalPlugins._speech_core.settings_file")
        backup = importlib.import_module("globalPlugins._speech_core.nvda_settings_backup")
        base = ConfigObj()
        base.filename = str(Path(self.folder) / "nvda.ini")
        conf = SimpleNamespace(profiles=[base])
        with patch.object(backup, "_CONFIG_FOLDER_OVERRIDE", self.folder), patch.object(config, "conf", conf):
            settings.load_into_nvda(conf)
            self.updates.set_preferred_channel("dev")
            self.updates.set_automatic_checks_enabled(False)
            base.write()
            self.assertNotIn(b"updateChannel", Path(base.filename).read_bytes())
            reloaded = ConfigObj(base.filename, encoding="utf-8")
            conf.profiles = [reloaded]
            settings.load_into_nvda(conf)
            self.assertEqual(self.updates.preferred_channel(), "dev")
            self.assertFalse(self.updates.automatic_checks_enabled())

    def test_ok_and_close_commit_and_restore_channel_controls(self):
        module = importlib.import_module("globalPlugins._speech_core.settings.dialog")
        dialog = object.__new__(module.ClassicSpeechDialog)
        dialog._popupReleased = False
        dialog._committed = False
        dialog._initializeDialogTransaction()
        panel = dialog.advancedPanel = module.AdvancedPanel(None)
        dialog._saveTransaction = lambda: panel.apply_live()
        dialog._clearDirty = lambda: None
        panel.updateChannel.GetSelection = lambda: 1
        panel.checkForUpdates.SetValue(False)
        panel.onChanged()
        dialog.onOK(None)
        self.assertEqual(self.updates.preferred_channel(), "dev")
        self.assertFalse(self.updates.automatic_checks_enabled())
        panel.updateChannel.GetSelection = lambda: 0
        panel.checkForUpdates.SetValue(True)
        panel.onChanged()
        skipped = []
        from types import SimpleNamespace
        dialog.onClose(SimpleNamespace(Skip=lambda: skipped.append(True)))
        self.assertEqual(skipped, [True])
        self.assertEqual(self.updates.preferred_channel(), "dev")
        self.assertFalse(self.updates.automatic_checks_enabled())

    def test_native_advanced_controls_and_transaction(self):
        module = importlib.import_module("globalPlugins._speech_core.settings.dialog")
        dialog = object.__new__(module.ClassicSpeechDialog)
        dialog._popupReleased = False
        dialog._committed = False
        dialog._initializeDialogTransaction()
        dialog.advancedPanel = module.AdvancedPanel(None)
        dialog._saveTransaction = lambda: dialog.advancedPanel.apply_live()
        dialog._clearDirty = lambda: None
        panel = dialog.advancedPanel
        self.assertEqual(panel.checkForUpdates.ctorKwargs["label"], "Check for updates automatically:")
        self.assertEqual(panel.updateChannel.GetSelection(), 0)
        panel.checkForUpdates.SetValue(False)
        panel.updateChannel.SetSelection(1)
        panel.updateChannel.GetSelection = lambda: 1
        panel.onChanged()
        self.assertFalse(self.updates.automatic_checks_enabled())
        self.assertEqual(self.updates.preferred_channel(), "dev")
        dialog.onCancel(None)
        self.assertTrue(self.updates.automatic_checks_enabled())
        self.assertEqual(self.updates.preferred_channel(), "stable")
        dialog = object.__new__(module.ClassicSpeechDialog)
        dialog._popupReleased = False
        dialog._committed = False
        dialog._initializeDialogTransaction()
        dialog.advancedPanel = module.AdvancedPanel(None)
        dialog._saveTransaction = lambda: dialog.advancedPanel.apply_live()
        dialog._clearDirty = lambda: None
        panel = dialog.advancedPanel
        panel.updateChannel.SetSelection(1)
        panel.updateChannel.GetSelection = lambda: 1
        panel.onChanged()
        self.assertTrue(dialog.onApply(None))
        panel.updateChannel.SetSelection(0)
        panel.updateChannel.GetSelection = lambda: 0
        panel.onChanged()
        self.assertEqual(self.updates.preferred_channel(), "stable")
        dialog.onCancel(None)
        self.assertEqual(self.updates.preferred_channel(), "dev")


if __name__ == "__main__":
    unittest.main()
