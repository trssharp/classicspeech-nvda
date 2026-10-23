"""ClassicSpeech settings storage, reset and removal.

ClassicSpeech keeps its settings in ClassicSpeech/settings.ini, not nvda.ini
(``_speech_core/settings_file.py``). It records NVDA's own settings before it
first changes them (``_speech_core/nvda_settings_backup.py``), so Reset All
ClassicSpeech Settings and removing the add-on (``installTasks.py``) put NVDA
back as it was. Scheme voices for other synthesizers must never be saved as the
user's NVDA voice settings.

These tests use temporary folders, never NVDA's real configuration.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tests") not in sys.path:
	sys.path.insert(0, str(ROOT / "tests"))

import classic_speech_nvda_master_harness as nvda_harness  # noqa: E402
import config  # noqa: E402
import globalPluginHandler  # noqa: E402
import speech  # noqa: E402

try:
	import configobj  # noqa: F401

	HAVE_CONFIGOBJ = True
except ImportError:
	HAVE_CONFIGOBJ = False

_MISSING = object()


class FakeProfile(dict):
	"""An NVDA configuration profile: nested dicts, plus the name and file of a named profile."""

	def __init__(self, sections=None, name=None, filename=None):
		super().__init__(sections or {})
		self.name = name
		self.filename = filename


class FakeSection:
	"""``config.conf[section]`` in NVDA: reads the newest profile that has a key, writes the newest profile."""

	def __init__(self, manager, path):
		self.manager = manager
		self.path = path

	def _profile_section(self, profile, create=False):
		section = profile
		for part in self.path:
			if part not in section:
				if not create:
					return None
				section[part] = {}
			section = section[part]
		return section

	def __getitem__(self, key):
		for profile in reversed(self.manager.profiles):
			section = self._profile_section(profile)
			if section is not None and key in section:
				value = section[key]
				return FakeSection(self.manager, self.path + (key,)) if isinstance(value, dict) else value
		raise KeyError(key)

	def get(self, key, default=None):
		try:
			return self[key]
		except KeyError:
			return default

	def __contains__(self, key):
		return self.get(key, _MISSING) is not _MISSING

	def __setitem__(self, key, value):
		current = self.get(key, _MISSING)
		if current is not _MISSING and not isinstance(current, FakeSection) and str(current) == str(value):
			return  # NVDA does not write an unchanged value.
		self._profile_section(self.manager.profiles[-1], create=True)[key] = value


class FakeConfigManager:
	"""The parts of NVDA's ConfigManager that ClassicSpeech's settings backup uses."""

	def __init__(self, base, saved_profiles=None):
		self.profiles = [base]
		self.BASE_ONLY_SECTIONS = set()
		self._profileCache = {None: base}
		self._dirtyProfiles = set()
		self._saved_profiles = dict(saved_profiles or {})
		self.saves = 0
		self.refreshes = 0

	def __getitem__(self, key):
		# Every NVDA section exists, as its configuration spec defines it.
		return FakeSection(self, (key,))

	def __contains__(self, key):
		return True

	def __setitem__(self, key, value):
		FakeSection(self, ())[key] = value

	def _getProfile(self, name):
		if name not in self._profileCache:
			self._profileCache[name] = self._saved_profiles[name]
		return self._profileCache[name]

	def _handleProfileSwitch(self, shouldNotify=True):
		self.refreshes += 1

	def save(self):
		self.saves += 1


def _load_backup_module():
	"""Load the backup module on its own, the way installTasks.py does."""
	path = ROOT / "_speech_core" / "nvda_settings_backup.py"
	spec = importlib.util.spec_from_file_location("classicSpeechSettingsBackupUnderTest", path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


class NVDASettingsBackupTests(unittest.TestCase):
	def setUp(self):
		self.folder = tempfile.mkdtemp()
		self.backup = _load_backup_module()
		self.backup._CONFIG_FOLDER_OVERRIDE = self.folder
		self.base = FakeProfile({
			"presentation": {"reportObjectDescriptions": "False"},
			"classicSpeech": {"defaultProfile": "Advanced"},
		})
		self.conf = FakeConfigManager(self.base)

	def tearDown(self):
		shutil.rmtree(self.folder, ignore_errors=True)

	def _entries(self):
		with open(self.backup.backup_path(), encoding="utf-8") as stream:
			return json.load(stream)["settings"]

	def test_first_change_records_the_earlier_value_and_later_changes_only_the_new_one(self):
		self.backup.set_nvda_setting(("presentation",), "reportTooltips", True, conf=self.conf)
		self.backup.set_nvda_setting(("presentation",), "reportTooltips", False, conf=self.conf)
		self.backup.set_nvda_setting(("presentation",), "reportObjectDescriptions", True, conf=self.conf)
		entries = {entry["key"]: entry for entry in self._entries()}
		self.assertEqual(entries["reportTooltips"]["before"], {"set": False})
		self.assertEqual(entries["reportTooltips"]["after"], {"set": True, "value": False})
		self.assertEqual(entries["reportObjectDescriptions"]["before"], {"set": True, "value": "False"})
		self.assertIsNone(entries["reportTooltips"]["profile"])
		self.assertEqual(entries["reportTooltips"]["section"], ["presentation"])

	def test_an_unchanged_value_is_not_recorded(self):
		self.backup.set_nvda_setting(("presentation",), "reportObjectDescriptions", "False", conf=self.conf)
		self.assertFalse(os.path.exists(self.backup.backup_path()))

	def test_restore_puts_back_earlier_values_and_removes_added_ones(self):
		self.backup.set_nvda_setting(("presentation",), "reportTooltips", True, conf=self.conf)
		self.backup.set_nvda_setting(("presentation",), "reportObjectDescriptions", True, conf=self.conf)
		self.backup.set_nvda_setting(("virtualBuffers",), "linesPerPage", 50, conf=self.conf)
		result = self.backup.restore_nvda_settings(conf=self.conf)
		self.assertEqual(len(result["restored"]), 3)
		self.assertEqual(result["kept"], [])
		self.assertEqual(self.base["presentation"], {"reportObjectDescriptions": "False"})
		self.assertNotIn("linesPerPage", self.base["virtualBuffers"])
		self.assertGreaterEqual(self.conf.refreshes, 1)

	def test_a_setting_changed_later_in_nvda_is_kept(self):
		self.backup.set_nvda_setting(("presentation",), "reportTooltips", True, conf=self.conf)
		# The user changes the same setting in NVDA's own settings afterwards.
		self.base["presentation"]["reportTooltips"] = "False"
		result = self.backup.restore_nvda_settings(conf=self.conf)
		self.assertEqual(result["restored"], [])
		self.assertEqual(len(result["kept"]), 1)
		self.assertEqual(self.base["presentation"]["reportTooltips"], "False")

	def test_values_saved_as_text_by_nvda_still_match(self):
		self.backup.set_nvda_setting(("virtualBuffers",), "browseModeTouchNavigationElements", ["heading", "list"], conf=self.conf)
		self.backup.set_nvda_setting(("documentFormatting",), "reportLineIndentation", 2, conf=self.conf)
		# After NVDA saves and restarts, nvda.ini gives text back.
		self.base["documentFormatting"]["reportLineIndentation"] = "2"
		result = self.backup.restore_nvda_settings(conf=self.conf)
		self.assertEqual(len(result["restored"]), 2)
		self.assertNotIn("reportLineIndentation", self.base["documentFormatting"])

	def test_a_change_in_a_named_profile_is_restored_in_that_profile(self):
		profile = FakeProfile({}, name="Firefox", filename="Firefox.ini")
		self.conf.profiles.append(profile)
		self.conf._profileCache["Firefox"] = profile
		self.backup.set_nvda_setting(("documentFormatting",), "reportFontName", True, conf=self.conf)
		self.assertEqual(self._entries()[0]["profile"], "Firefox")
		# Later, with the profile no longer active and not loaded:
		self.conf.profiles.pop()
		del self.conf._profileCache["Firefox"]
		self.conf._saved_profiles["Firefox"] = profile
		self.backup.restore_nvda_settings(conf=self.conf)
		self.assertNotIn("reportFontName", profile["documentFormatting"])
		self.assertIn("Firefox", self.conf._dirtyProfiles)

	def test_a_deleted_profile_is_skipped(self):
		profile = FakeProfile({}, name="Gone", filename="Gone.ini")
		self.conf.profiles.append(profile)
		self.backup.set_nvda_setting(("documentFormatting",), "reportFontName", True, conf=self.conf)
		self.conf.profiles.pop()
		result = self.backup.restore_nvda_settings(conf=self.conf)
		self.assertEqual(len(result["kept"]), 1)

	def test_a_change_while_a_voice_overlay_speaks_reaches_the_saved_configuration(self):
		overlay = FakeProfile({"speech": {"espeak": {"rate": "30"}}})  # unnamed, in memory only
		self.conf.profiles.append(overlay)
		self.backup.set_nvda_setting(("presentation",), "reportTooltips", True, conf=self.conf)
		self.assertEqual(self.base["presentation"]["reportTooltips"], True)
		self.assertNotIn("presentation", overlay)
		self.assertIs(self.conf.profiles[-1], overlay, "the overlay goes back on top")
		self.assertEqual(self._entries()[0]["before"], {"set": False})
		self.assertIsNone(self._entries()[0]["profile"])

	def test_legacy_changes_are_recorded_once_and_only_when_they_match(self):
		self.base["presentation"].update({"reportObjectPositionInformation": "False", "reportTooltips": "True"})
		implied = {
			(("presentation",), "reportObjectPositionInformation"): False,
			(("presentation",), "reportTooltips"): False,  # the user's own value differs: not ClassicSpeech's
			(("presentation",), "reportKeyboardShortcuts"): True,  # not set in nvda.ini
		}
		recorded = self.backup.record_legacy_changes(implied, conf=self.conf)
		self.assertEqual(recorded, [(("presentation",), "reportObjectPositionInformation")])
		self.assertTrue(self.backup.legacy_checked())
		self.assertEqual(self.backup.record_legacy_changes(implied, conf=self.conf), [])
		self.backup.restore_nvda_settings(conf=self.conf)
		self.assertNotIn("reportObjectPositionInformation", self.base["presentation"])
		self.assertEqual(self.base["presentation"]["reportTooltips"], "True")

	def test_reset_all_restores_then_deletes_the_section_and_folder_and_saves(self):
		schemes = Path(self.folder, "ClassicSpeech", "Schemes", "Default")
		schemes.mkdir(parents=True)
		(schemes / "scheme.json").write_text("{}", encoding="utf-8")
		Path(self.folder, "ClassicSpeech", "settings.ini").write_text("defaultProfile = Advanced\n", encoding="utf-8")
		self.backup.set_nvda_setting(("presentation",), "reportTooltips", True, conf=self.conf)
		result = self.backup.reset_all(conf=self.conf, save=True)
		self.assertEqual(len(result["restored"]), 1)
		self.assertIsNone(result["notDeleted"])
		self.assertNotIn("classicSpeech", self.base)
		self.assertNotIn("reportTooltips", self.base["presentation"])
		self.assertFalse(os.path.exists(os.path.join(self.folder, "ClassicSpeech")))
		self.assertEqual(self.conf.saves, 1)

	def test_nothing_is_written_without_an_nvda_configuration_folder(self):
		self.backup._CONFIG_FOLDER_OVERRIDE = None
		self.backup.set_nvda_setting(("presentation",), "reportTooltips", True, conf=self.conf)
		self.assertEqual(self.base["presentation"]["reportTooltips"], True)
		self.assertEqual(os.listdir(self.folder), [])


class InstallTasksTests(unittest.TestCase):
	def setUp(self):
		self.root = tempfile.mkdtemp()
		self.addons = os.path.join(self.root, "addons")
		self.addon = os.path.join(self.addons, "ClassicSpeech")
		core = os.path.join(self.addon, "globalPlugins", "_speech_core")
		os.makedirs(core)
		shutil.copy(ROOT / "_speech_core" / "nvda_settings_backup.py", core)
		shutil.copy(ROOT / "installTasks.py", self.addon)
		spec = importlib.util.spec_from_file_location("classicSpeechInstallTasksUnderTest", os.path.join(self.addon, "installTasks.py"))
		self.tasks = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(self.tasks)
		self.config_folder = os.path.join(self.root, "config")
		os.makedirs(os.path.join(self.config_folder, "ClassicSpeech", "Schemes"))
		self._saved_modules = {name: sys.modules.get(name) for name in ("NVDAState", "config")}
		nvda_state = types.ModuleType("NVDAState")
		nvda_state.WritePaths = types.SimpleNamespace(configDir=self.config_folder)
		nvda_state.shouldWriteToDisk = lambda: True
		sys.modules["NVDAState"] = nvda_state
		self.base = FakeProfile({"classicSpeech": {"defaultProfile": "Advanced"}, "presentation": {}})
		self.conf = FakeConfigManager(self.base)
		fake_config = types.ModuleType("config")
		fake_config.conf = self.conf
		sys.modules["config"] = fake_config

	def tearDown(self):
		for name, module in self._saved_modules.items():
			if module is None:
				sys.modules.pop(name, None)
			else:
				sys.modules[name] = module
		shutil.rmtree(self.root, ignore_errors=True)

	def test_removal_restores_nvda_and_deletes_every_classic_speech_setting(self):
		backup_file = os.path.join(self.config_folder, "ClassicSpeech", "nvda-settings-backup.json")
		with open(backup_file, "w", encoding="utf-8") as stream:
			json.dump({"settings": [{
				"profile": None,
				"section": ["presentation"],
				"key": "reportTooltips",
				"before": {"set": False},
				"after": {"set": True, "value": True},
			}]}, stream)
		self.base["presentation"]["reportTooltips"] = "True"
		self.tasks.onUninstall()
		self.assertNotIn("classicSpeech", self.base)
		self.assertNotIn("reportTooltips", self.base["presentation"])
		self.assertFalse(os.path.exists(os.path.join(self.config_folder, "ClassicSpeech")))
		self.assertEqual(self.conf.saves, 1)

	def test_an_update_keeps_the_settings(self):
		os.makedirs(os.path.join(self.addons, "ClassicSpeech.pendingInstall"))
		self.tasks.onUninstall()
		self.assertIn("classicSpeech", self.base)
		self.assertTrue(os.path.exists(os.path.join(self.config_folder, "ClassicSpeech")))
		self.assertEqual(self.conf.saves, 0)

	def test_a_copy_discarded_before_installation_keeps_the_settings(self):
		pending = os.path.join(self.addons, "ClassicSpeech.pendingInstall")
		self.assertTrue(self.tasks._is_replaced_or_discarded(pending))
		self.assertFalse(self.tasks._is_replaced_or_discarded(self.addon))


@unittest.skipUnless(HAVE_CONFIGOBJ, "needs configobj, which NVDA bundles")
class SettingsFileTests(unittest.TestCase):
	def setUp(self):
		from configobj import ConfigObj

		self.ConfigObj = ConfigObj
		nvda_harness._import_classic_speech_like_nvda()
		self.backup = importlib.import_module("globalPlugins._speech_core.nvda_settings_backup")
		self.settings_file = importlib.import_module("globalPlugins._speech_core.settings_file")
		self.folder = tempfile.mkdtemp()
		self.backup._CONFIG_FOLDER_OVERRIDE = self.folder
		self.nvda_ini = os.path.join(self.folder, "nvda.ini")
		self.settings_ini = os.path.join(self.folder, "ClassicSpeech", "settings.ini")

	def tearDown(self):
		self.backup._CONFIG_FOLDER_OVERRIDE = None
		shutil.rmtree(self.folder, ignore_errors=True)
		nvda_harness._reset_global_plugin_imports()

	def _base(self, text):
		Path(self.nvda_ini).write_text(text, encoding="utf-8")
		base = self.ConfigObj(self.nvda_ini, indent_type="\t", encoding="UTF-8")
		base.newlines = "\r\n"
		return base, types.SimpleNamespace(profiles=[base])

	def test_settings_move_out_of_nvda_ini_and_stay_out(self):
		base, conf = self._base(
			"[general]\n\tlanguage = en\n"
			"[classicSpeech]\n\tdefaultProfile = Advanced\n\tvoiceProfileData = '{\"espeak\": {}}'\n"
			"\t[[keyLabelData]]\n\t\tmutedLabels = a, b\n"
		)
		self.assertTrue(self.settings_file.load_into_nvda(conf))
		section = base["classicSpeech"]
		section["defaultProfile"] = "Intermediate"
		base.write()
		nvda_ini = Path(self.nvda_ini).read_text(encoding="utf-8")
		self.assertNotIn("classicSpeech", nvda_ini)
		self.assertIn("language = en", nvda_ini)
		saved = self.ConfigObj(self.settings_ini, encoding="UTF-8")
		self.assertEqual(saved["defaultProfile"], "Intermediate")
		self.assertEqual(saved["voiceProfileData"], '{"espeak": {}}')
		self.assertEqual(saved["keyLabelData"]["mutedLabels"], ["a", "b"])
		# ClassicSpeech keeps using the very same section object after the save.
		self.assertIs(base["classicSpeech"], section)
		self.assertIn("classicSpeech", base.sections)

	def test_nvda_saving_through_a_file_object_leaves_the_section_out(self):
		# NVDA's ConfigManager.save writes nvda.ini through FaultTolerantFile, a binary temporary file.
		base, conf = self._base("[general]\n\tlanguage = en\n[classicSpeech]\n\tdefaultProfile = Advanced\n")
		self.settings_file.load_into_nvda(conf)
		with tempfile.NamedTemporaryFile(dir=self.folder, prefix="nvda.ini", suffix=".tmp", delete=False) as stream:
			base.write(stream)
		os.replace(stream.name, self.nvda_ini)
		self.assertNotIn("classicSpeech", Path(self.nvda_ini).read_text(encoding="utf-8"))
		self.assertEqual(self.ConfigObj(self.settings_ini)["defaultProfile"], "Advanced")

	def test_revert_to_saved_configuration_reloads_settings_ini(self):
		base, conf = self._base("[classicSpeech]\n\tdefaultProfile = Advanced\n")
		self.settings_file.load_into_nvda(conf)
		base.write()
		reverted, reverted_conf = self._base(Path(self.nvda_ini).read_text(encoding="utf-8"))
		self.assertFalse(self.settings_file.load_into_nvda(reverted_conf))
		self.assertEqual(reverted["classicSpeech"]["defaultProfile"], "Advanced")

	def test_plugin_reload_keeps_unsaved_settings(self):
		base, conf = self._base("[classicSpeech]\n\tdefaultProfile = Advanced\n")
		self.settings_file.load_into_nvda(conf)
		base["classicSpeech"]["defaultProfile"] = "Beginner"
		self.settings_file.load_into_nvda(conf)
		self.assertEqual(base["classicSpeech"]["defaultProfile"], "Beginner")

	def test_factory_defaults_do_not_load_settings_ini(self):
		os.makedirs(os.path.dirname(self.settings_ini))
		Path(self.settings_ini).write_text("defaultProfile = Advanced\n", encoding="utf-8")
		base, conf = self._base("")
		self.settings_file.load_into_nvda(conf, factory_defaults=True)
		self.assertNotIn("classicSpeech", base)

	def test_an_old_nvda_ini_section_does_not_replace_newer_settings(self):
		base, conf = self._base("[classicSpeech]\n\tdefaultProfile = Advanced\n")
		os.makedirs(os.path.dirname(self.settings_ini))
		Path(self.settings_ini).write_text("defaultProfile = Intermediate\n", encoding="utf-8")
		old = os.path.getmtime(self.settings_ini) - 60
		os.utime(self.nvda_ini, (old, old))
		self.assertFalse(self.settings_file.load_into_nvda(conf))
		self.assertEqual(base["classicSpeech"]["defaultProfile"], "Intermediate")

	def test_section_headers_without_values_are_not_moved(self):
		os.makedirs(os.path.dirname(self.settings_ini))
		Path(self.settings_ini).write_text("defaultProfile = Advanced\n", encoding="utf-8")
		base, conf = self._base("[classicSpeech]\n\t[[profileData]]\n")
		self.assertFalse(self.settings_file.load_into_nvda(conf))
		self.assertEqual(base["classicSpeech"]["defaultProfile"], "Advanced")

	def test_settings_stay_in_nvda_ini_when_settings_ini_cannot_be_written(self):
		base, conf = self._base("[classicSpeech]\n\tdefaultProfile = Advanced\n")
		self.settings_file.load_into_nvda(conf)
		original = self.settings_file.write_settings_file

		def fail(*args, **kwargs):
			raise OSError("disk full")

		self.settings_file.write_settings_file = fail
		try:
			base.write()
		finally:
			self.settings_file.write_settings_file = original
		self.assertIn("[classicSpeech]", Path(self.nvda_ini).read_text(encoding="utf-8"))

	def test_an_unreadable_settings_file_is_kept_and_defaults_are_used(self):
		os.makedirs(os.path.dirname(self.settings_ini))
		Path(self.settings_ini).write_text("[broken\n", encoding="utf-8")
		base, conf = self._base("")
		self.settings_file.load_into_nvda(conf)
		self.assertNotIn("classicSpeech", base)
		self.assertTrue(os.path.exists(self.settings_ini + ".corrupted.bak"))


class _FakeDriver:
	name = "ibmeci"

	def __init__(self):
		self.saved = 0
		self.unregistered = 0

	def saveSettings(self):
		self.saved += 1

	def _unregisterConfigSaveAction(self):
		self.unregistered += 1

	def terminate(self):
		# NVDA's Driver.terminate saves settings, then stops saving on configuration saves.
		self.saveSettings()


class VoiceSettingsLeakTests(unittest.TestCase):
	def setUp(self):
		nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
		nvda_harness._import_classic_speech_like_nvda()
		self.trigger_module = importlib.import_module("globalPlugins._speech_core.voice_profile_trigger")

	def tearDown(self):
		nvda_harness._reset_global_plugin_imports()

	def _manager(self):
		manager = types.SimpleNamespace(profiles=[{}], switches=0)
		manager._handleProfileSwitch = lambda shouldNotify=True: setattr(manager, "switches", manager.switches + 1)
		return manager

	def test_the_other_synthesizer_never_saves_its_settings_when_nvda_unloads_it(self):
		user, other = types.SimpleNamespace(name="espeak"), _FakeDriver()
		active = [user]
		trigger = self.trigger_module.CrossSynthProfileTrigger(
			"role.LINK", "ibmeci", {"rate": 80}, config_manager=self._manager(),
			profile_factory=FakeProfile, active_synth_getter=lambda: active[0],
		)
		trigger.enter()
		active[0] = other  # NVDA loads the item's synthesizer.
		trigger.exit()
		other.terminate()  # NVDA loads the user's synthesizer again.
		self.assertEqual(other.saved, 0)
		self.assertEqual(other.unregistered, 1)

	def test_the_users_own_synthesizer_is_never_stopped_from_saving(self):
		user = _FakeDriver()
		trigger = self.trigger_module.CrossSynthProfileTrigger(
			"role.LINK", "ibmeci", {}, config_manager=self._manager(),
			profile_factory=FakeProfile, active_synth_getter=lambda: user,
		)
		trigger.enter()
		trigger.exit()
		user.saveSettings()
		self.assertEqual(user.saved, 1)
		self.assertEqual(user.unregistered, 0)

	def test_a_synthesizer_loaded_for_editing_scheme_voices_keeps_out_of_nvda_settings(self):
		from globalPlugins._speech_core.settings import schemes_panel

		probe = _FakeDriver()
		created = {}

		def get_synth_instance(name):
			# NVDA creates default settings the first time a synthesizer loads.
			config.conf.profiles[0].setdefault("speech", {})[name] = {"rate": "50"}
			created["name"] = name
			return probe

		saved = sys.modules.get("synthDriverHandler")
		sys.modules["synthDriverHandler"] = types.SimpleNamespace(getSynthInstance=get_synth_instance)
		try:
			self.assertIs(schemes_panel.load_editing_synthesizer("ibmeci"), probe)
		finally:
			if saved is None:
				sys.modules.pop("synthDriverHandler", None)
			else:
				sys.modules["synthDriverHandler"] = saved
		probe.terminate()
		self.assertEqual(created, {"name": "ibmeci"})
		self.assertEqual(probe.saved, 0)
		self.assertEqual(probe.unregistered, 1)

	def test_voice_profiles_apply_stops_a_preview_before_saving(self):
		from globalPlugins._speech_core.settings.voice_profiles_dialog import VoiceProfilesDialog

		events = []
		dialog = object.__new__(VoiceProfilesDialog)
		dialog._previewController = types.SimpleNamespace(cancel=lambda: events.append("preview canceled"))
		store = types.SimpleNamespace(apply=lambda: events.append("saved"), mark_applied=lambda: None)
		dialog.store = store
		dialog.schemeStore = types.SimpleNamespace(apply=lambda: None, mark_applied=lambda: None)
		dialog._clearDirty = lambda: None
		self.assertTrue(dialog.onApply(None))
		self.assertEqual(events, ["preview canceled", "saved"])


class ResetCommandTests(unittest.TestCase):
	def setUp(self):
		nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
		self.module = nvda_harness._import_classic_speech_like_nvda()
		self.backup = importlib.import_module("globalPlugins._speech_core.nvda_settings_backup")
		self.folder = tempfile.mkdtemp()
		self.backup._CONFIG_FOLDER_OVERRIDE = self.folder
		from globalPlugins._speech_core.schemes import store

		self.store = store
		store._ROOT_OVERRIDE = os.path.join(self.folder, "ClassicSpeech", "Schemes")
		for number, name in enumerate(
			("OK", "YES", "NO", "YES_NO", "NO_DEFAULT", "ICON_WARNING", "ICON_INFORMATION", "ICON_ERROR"), start=1
		):
			if not isinstance(getattr(self.module.wx, name, None), int):
				setattr(self.module.wx, name, 1 << number)

	def tearDown(self):
		self.store._ROOT_OVERRIDE = None
		self.backup._CONFIG_FOLDER_OVERRIDE = None
		globalPluginHandler.runningPlugins.clear()
		speech.extensions.filter_speechSequence.callbacks.clear()
		nvda_harness._reset_global_plugin_imports()
		shutil.rmtree(self.folder, ignore_errors=True)

	def test_reset_removes_classic_speech_settings_and_starts_from_defaults(self):
		config.conf.profiles[0]["classicSpeech"] = {"defaultProfile": "Advanced", "debugLogging": True}
		plugin = self.module.GlobalPlugin()
		globalPluginHandler.runningPlugins.append(plugin)
		try:
			self.assertEqual(plugin.processor.verbosity.current_profile, "Advanced")
			Path(self.folder, "ClassicSpeech", "Schemes", "Old").mkdir(parents=True)
			plugin.reset_all_settings()
			section = config.conf.profiles[0]["classicSpeech"]
			self.assertNotIn("debugLogging", section)
			self.assertEqual(section.get("defaultProfile"), "Beginner")
			self.assertEqual(plugin.processor.verbosity.current_profile, "Beginner")
			self.assertFalse(Path(self.folder, "ClassicSpeech", "Schemes", "Old").exists())
			self.assertTrue(self.backup.legacy_checked())
		finally:
			plugin.terminate()

	def test_reset_waits_until_classic_speech_dialogs_are_closed(self):
		plugin = self.module.GlobalPlugin()
		try:
			messages = []
			plugin._show_message = lambda message, title, style: messages.append(message)
			plugin._settingsDialog = object()
			plugin.reset_all_settings = lambda: self.fail("reset while a dialog is open")
			plugin._confirmResetAllSettings()
			self.assertEqual(len(messages), 1)
			self.assertIn("Close the ClassicSpeech settings dialogs first", messages[0])
		finally:
			plugin._settingsDialog = None
			plugin.terminate()

	def test_reset_asks_first_and_does_nothing_on_no(self):
		plugin = self.module.GlobalPlugin()
		try:
			answers = []

			def show(message, title, style):
				answers.append(message)
				return self.module.wx.NO

			plugin._show_message = show
			plugin.reset_all_settings = lambda: self.fail("reset without confirmation")
			plugin._confirmResetAllSettings()
			self.assertEqual(len(answers), 1)
			self.assertTrue(answers[0].startswith("Do you really want to reset all ClassicSpeech settings?"))
			self.assertIn("You can't undo a reset", answers[0])
		finally:
			plugin.terminate()

	def test_the_question_is_a_yes_no_box_that_defaults_to_no(self):
		plugin = self.module.GlobalPlugin()
		try:
			styles = []

			def show(message, title, style):
				styles.append(style)
				return self.module.wx.NO

			plugin._show_message = show
			plugin._confirmResetAllSettings()
			wx = self.module.wx
			self.assertEqual(styles[0] & (wx.YES_NO | wx.NO_DEFAULT), wx.YES_NO | wx.NO_DEFAULT)
		finally:
			plugin.terminate()

	def test_yes_resets(self):
		plugin = self.module.GlobalPlugin()
		try:
			calls = []
			plugin._show_message = lambda message, title, style: self.module.wx.YES
			plugin.reset_all_settings = lambda: calls.append("reset") or {"restored": [], "kept": [], "notDeleted": None}
			plugin._confirmResetAllSettings()
			self.assertEqual(calls, ["reset"])
		finally:
			plugin.terminate()

	def test_settings_from_an_earlier_version_are_recorded_at_startup(self):
		config.conf.profiles[0]["classicSpeech"] = {"defaultProfile": "Advanced", "positionMode": "off", "hotkeyMode": "both"}
		# The test configuration keeps NVDA's own settings in config.conf itself.
		config.conf["presentation"] = {"reportObjectPositionInformation": "False"}
		plugin = self.module.GlobalPlugin()
		try:
			with open(self.backup.backup_path(), encoding="utf-8") as stream:
				entries = json.load(stream)["settings"]
			self.assertEqual(
				[(entry["key"], entry["before"], entry.get("assumed")) for entry in entries],
				[("reportObjectPositionInformation", {"set": False}, True)],
			)
		finally:
			plugin.terminate()

	def test_a_new_installation_records_nothing_and_checks_only_once(self):
		config.conf.profiles[0].pop("classicSpeech", None)
		plugin = self.module.GlobalPlugin()
		try:
			self.assertTrue(self.backup.legacy_checked())
			with open(self.backup.backup_path(), encoding="utf-8") as stream:
				self.assertEqual(json.load(stream)["settings"], [])
		finally:
			plugin.terminate()


class DialogsOutsideTheCoreQueueTests(unittest.TestCase):
	"""A modal dialog opened inside NVDA's core queue freezes NVDA: it can't even speak the dialog.

	Scripts and queueHandler functions run inside NVDA's core pump. The reset's
	Yes/No question once opened there, and NVDA froze until it was restarted.
	"""

	def setUp(self):
		nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
		self.module = nvda_harness._import_classic_speech_like_nvda()
		self.after, self.queued = [], []
		self._saved = (self.module.wx.CallAfter, self.module.queueHandler.queueFunction)
		self.module.wx.CallAfter = lambda function, *args, **kwargs: self.after.append(getattr(function, "__name__", function))
		self.module.queueHandler.queueFunction = lambda queue, function, *args, **kwargs: self.queued.append(
			getattr(function, "__name__", function)
		)

	def tearDown(self):
		self.module.wx.CallAfter, self.module.queueHandler.queueFunction = self._saved
		globalPluginHandler.runningPlugins.clear()
		speech.extensions.filter_speechSequence.callbacks.clear()
		nvda_harness._reset_global_plugin_imports()

	def test_reset_and_update_commands_ask_from_wx_not_from_nvdas_core_queue(self):
		plugin = object.__new__(self.module.GlobalPlugin)
		plugin.onClassicSpeechResetMenu(None)
		plugin.script_resetAllClassicSpeechSettings(None)
		plugin.onClassicSpeechUpdateMenu(None)
		plugin.script_checkForClassicSpeechUpdates(None)
		self.assertEqual(
			self.after,
			["_confirmResetAllSettings", "_confirmResetAllSettings", "_checkForUpdates", "_checkForUpdates"],
		)
		self.assertEqual(self.queued, [])

	def test_only_dialogs_that_do_not_wait_are_opened_from_nvdas_core_queue(self):
		import ast

		tree = ast.parse((ROOT / "classicSpeech.py").read_text(encoding="utf-8"))
		queued = set()
		for node in ast.walk(tree):
			if (
				isinstance(node, ast.Call)
				and isinstance(node.func, ast.Attribute)
				and node.func.attr == "queueFunction"
				and len(node.args) >= 2
				and isinstance(node.args[1], ast.Attribute)
			):
				queued.add(node.args[1].attr)
		# Each of these opens a dialog with Show(), which returns at once.
		self.assertLessEqual(queued, {"_openSettings", "_openPresentationPresets", "_openWebBrowseSettings", "_openVoiceProfiles", "_openSpeechSchemes"})

	def test_an_update_check_without_a_github_page_does_not_block_its_caller(self):
		updates = importlib.import_module("globalPlugins._speech_core.update_check")
		checker = updates.UpdateChecker()
		checker._message = lambda *args, **kwargs: self.fail("message box opened in the caller")
		saved = sys.modules.get("addonHandler")
		sys.modules.pop("addonHandler", None)
		try:
			checker.check(manual=True)
		finally:
			if saved is not None:
				sys.modules["addonHandler"] = saved
		self.assertEqual(self.after, ["<lambda>"])


class PackagingAndGuideTests(unittest.TestCase):
	def test_install_tasks_is_packaged_at_the_add_on_root(self):
		spec = importlib.util.spec_from_file_location("classicspeech_package_addon_removal", ROOT / "scripts" / "package_addon.py")
		packager = importlib.util.module_from_spec(spec)
		sys.modules[spec.name] = packager
		spec.loader.exec_module(packager)
		self.assertIn("installTasks.py", packager.ROOT_FILES)

	def test_install_tasks_loads_the_backup_module_from_the_packaged_location(self):
		text = (ROOT / "installTasks.py").read_text(encoding="utf-8")
		self.assertIn('"globalPlugins", "_speech_core", "nvda_settings_backup.py"', text)
		self.assertIn("def onUninstall", text)

	def test_backup_module_imports_no_other_classic_speech_module(self):
		text = (ROOT / "_speech_core" / "nvda_settings_backup.py").read_text(encoding="utf-8")
		self.assertNotIn("from .", text)
		self.assertNotIn("import _speech_core", text)

	def test_guide_says_where_settings_are_and_how_to_remove_them(self):
		guide = (ROOT / "doc" / "en" / "readme.html").read_text(encoding="utf-8")
		for text in (
			r"%APPDATA%\nvda\ClassicSpeech\settings.ini",
			"nvda-settings-backup.json",
			"Reset All ClassicSpeech Settings",
			"[classicSpeech]",
			"Check for Updates",
		):
			self.assertIn(text, guide)


if __name__ == "__main__":
	unittest.main()
