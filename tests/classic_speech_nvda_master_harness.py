"""ClassicSpeech NVDA-master-aware regression harness.

This is the middle layer between the tiny pure/stub harness and live NVDA.
It does not start NVDA, move focus, inject keys, or touch the user's running
configuration. Instead it anchors ClassicSpeech assumptions against Tim's local
NVDA master checkout and verifies that ClassicSpeech config/startup remains
compatible with an NVDA-like base config shape.
"""
from __future__ import annotations

import importlib
import os
import re
import subprocess
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _find_nvda_master(addon_root: Path) -> Path:
	"""Locate NVDA master from an explicit path or Tim's local layout."""
	explicit_path = os.environ.get("CLASSICSPEECH_NVDA_MASTER", "").strip()
	if explicit_path:
		candidate = Path(explicit_path).expanduser()
		if (candidate / "source").is_dir():
			return candidate
		raise AssertionError(
			"CLASSICSPEECH_NVDA_MASTER does not contain an NVDA source directory: "
			f"{candidate}"
		)

	for ancestor in addon_root.parents:
		candidate = ancestor / "nvda master"
		if (candidate / "source").is_dir():
			return candidate
	raise AssertionError(
		"NVDA master checkout not found above "
		f"{addon_root}; set CLASSICSPEECH_NVDA_MASTER to an NVDA checkout"
	)


NVDA_MASTER = _find_nvda_master(ROOT)
NVDA_SOURCE = NVDA_MASTER / "source"
NVDA_CONFIG_SPEC = NVDA_SOURCE / "config" / "configSpec.py"

if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
	sys.path.insert(0, str(ROOT / "tests"))

# Reuse the established outside-NVDA stubs so both harnesses agree on the
# minimum NVDA surface ClassicSpeech expects.
import classic_speech_core_harness as core_harness  # noqa: E402

core_harness._install_nvda_stubs()

import api  # noqa: E402
import config  # noqa: E402
import globalPluginHandler  # noqa: E402
import speech  # noqa: E402
from speech.commands import CharacterModeCommand, IndexCommand  # noqa: E402


class _HarnessBaseConfig(dict):
	def validate(self, *args, **kwargs):
		return True


def _read_nvda_config_spec() -> str:
	if not NVDA_CONFIG_SPEC.exists():
		raise AssertionError(f"NVDA master config spec not found: {NVDA_CONFIG_SPEC}")
	return NVDA_CONFIG_SPEC.read_text(encoding="utf-8")


def _extract_config_spec_string(source_text: str) -> str:
	match = re.search(r'configSpecString = f"""(.*?)"""', source_text, re.DOTALL)
	if not match:
		raise AssertionError("Could not extract NVDA configSpecString")
	return match.group(1)


def _section_body(config_spec: str, section: str) -> str:
	pattern = rf"^\[{re.escape(section)}\]\n(.*?)(?=^\[[^\[]|\Z)"
	match = re.search(pattern, config_spec, re.DOTALL | re.MULTILINE)
	if not match:
		raise AssertionError(f"NVDA config section [{section}] not found")
	return match.group(1)


def _section_keys(config_spec: str, section: str) -> set[str]:
	body = _section_body(config_spec, section)
	keys: set[str] = set()
	for line in body.splitlines():
		stripped = line.strip()
		if not stripped or stripped.startswith("#") or stripped.startswith("["):
			continue
		if "=" not in stripped:
			continue
		keys.add(stripped.split("=", 1)[0].strip())
	return keys


def _top_level_sections(config_spec: str) -> set[str]:
	return set(re.findall(r"^\[([^\[\]\n]+)\]$", config_spec, re.MULTILINE))


def _reset_global_plugin_imports() -> None:
	for name in list(sys.modules):
		if name == "globalPlugins.classicSpeech" or name.startswith("globalPlugins._speech_core"):
			del sys.modules[name]


def _import_classic_speech_like_nvda():
	package = types.ModuleType("globalPlugins")
	package.__path__ = [str(ROOT)]
	sys.modules["globalPlugins"] = package
	_reset_global_plugin_imports()
	return importlib.import_module("globalPlugins.classicSpeech")


class NVDAMasterConfigShapeTests(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.source_text = _read_nvda_config_spec()
		cls.config_spec = _extract_config_spec_string(cls.source_text)

	def test_nvda_master_checkout_is_present_and_identifiable(self):
		self.assertTrue(NVDA_MASTER.exists(), NVDA_MASTER)
		self.assertTrue(NVDA_SOURCE.exists(), NVDA_SOURCE)
		result = subprocess.run(
			["git", "rev-parse", "--abbrev-ref", "HEAD"],
			cwd=NVDA_MASTER,
			text=True,
			capture_output=True,
			check=True,
		)
		self.assertEqual(result.stdout.strip(), "master")

	def test_classic_speech_uses_own_top_level_config_section(self):
		sections = _top_level_sections(self.config_spec)
		self.assertNotIn("classicSpeech", sections)
		for native_section in ("speech", "presentation", "keyboard", "documentFormatting"):
			self.assertIn(native_section, sections)

	def test_native_duplicate_settings_still_exist_in_nvda_master(self):
		self.assertGreaterEqual(int(re.search(r"latestSchemaVersion = (\d+)", self.source_text).group(1)), 23)
		speech_keys = _section_keys(self.config_spec, "speech")
		presentation_keys = _section_keys(self.config_spec, "presentation")
		keyboard_keys = _section_keys(self.config_spec, "keyboard")
		document_keys = _section_keys(self.config_spec, "documentFormatting")

		for key in {
			"autoLanguageSwitching",
			"autoDialectSwitching",
			"reportLanguage",
			"delayedCharacterDescriptions",
		}:
			self.assertIn(key, speech_keys)
		for key in {"reportDynamicContentChanges", "reportObjectPositionInformation"}:
			self.assertIn(key, presentation_keys)
		for key in {"speakTypedCharacters", "speakTypedWords", "alertForSpellingErrors"}:
			self.assertIn(key, keyboard_keys)
		for key in {
			"reportSpellingErrors2",
			"reportComments",
			"reportRevisions",
			"reportHighlight",
			"reportLineIndentation",
			"reportClickable",
		}:
			self.assertIn(key, document_keys)


class ClassicSpeechNVDAConfigStartupTests(unittest.TestCase):
	def test_preferences_menu_includes_voice_profiles_with_reload_safe_tracking(self):
		module = _import_classic_speech_like_nvda()

		class FakeItem:
			def __init__(self, item_id, label):
				self.Id = item_id
				self.label = label

		class FakeMenu:
			def __init__(self):
				self.items = []
			def Append(self, item_id, label):
				item = FakeItem(len(self.items) + 1, label)
				self.items.append(item)
				return item
			def Destroy(self): pass

		class FakePreferencesMenu:
			def AppendSubMenu(self, menu, label):
				return FakeItem(99, label)

		bindings = []
		module.wx.ID_ANY = -1
		module.wx.EVT_MENU = object()
		module.wx.Menu = FakeMenu
		sys_tray_icon = types.SimpleNamespace(
			preferencesMenu=FakePreferencesMenu(),
			Bind=lambda event, handler, item: bindings.append((handler.__name__, item.label)),
		)
		module.gui.mainFrame.sysTrayIcon = sys_tray_icon
		plugin = object.__new__(module.GlobalPlugin)
		plugin._is_secure_context = lambda: False
		plugin._installClassicSpeechMenu()

		self.assertEqual([item.label for item in plugin._classicSpeechMenuItems], [
			"General Settings...", "Web / Browse Mode Settings...", "Voice Profiles...",
		])
		self.assertIn(("onClassicSpeechVoiceProfilesMenu", "Voice Profiles..."), bindings)
		self.assertEqual(plugin._classicSpeechMenuItem.label, "ClassicSpeech")

	def test_preferences_submenu_cleanup_removes_and_destroys_classic_speech_item(self):
		module = _import_classic_speech_like_nvda()

		class FakeMenuItem:
			def __init__(self, item_id, label):
				self.Id = item_id
				self._label = label
				self.destroyed = False
			def GetItemLabelText(self): return self._label
			def GetLabel(self): return self._label
			def Destroy(self): self.destroyed = True

		class FakePreferencesMenu:
			def __init__(self, items):
				self.items = list(items)
				self.removed_ids = []
			def GetMenuItems(self): return list(self.items)
			def Remove(self, item_id):
				self.removed_ids.append(item_id)
				self.items = [item for item in self.items if item.Id != item_id]

		class FakeSubmenu:
			def Destroy(self): pass

		old_item = FakeMenuItem(601, "ClassicSpeech")
		other_item = FakeMenuItem(602, "Other")
		preferences_menu = FakePreferencesMenu([old_item, other_item])
		module.gui.mainFrame.sysTrayIcon = types.SimpleNamespace(preferencesMenu=preferences_menu)
		plugin = object.__new__(module.GlobalPlugin)
		plugin._classicSpeechPreferencesMenu = preferences_menu
		plugin._classicSpeechMenuItem = old_item
		plugin._classicSpeechMenu = FakeSubmenu()
		plugin._classicSpeechMenuItems = []
		plugin._removeClassicSpeechMenu()
		self.assertEqual(preferences_menu.removed_ids, [601])
		self.assertEqual([item.Id for item in preferences_menu.items], [602])
		self.assertTrue(old_item.destroyed)
		self.assertIsNone(plugin._classicSpeechMenu)

	def setUp(self):
		# Reset the stub config to an NVDA-like shape before importing the plugin.
		config.conf.clear()
		config.conf.BASE_ONLY_SECTIONS = set()
		config.conf.spec = {}
		config.conf.validator = object()
		config.conf.profiles = [_HarnessBaseConfig()]
		config.conf["presentation"] = {
			"reportKeyboardShortcuts": True,
			"reportObjectPositionInformation": True,
			"guessObjectPositionInformationWhenUnavailable": False,
			"reportObjectDescriptions": True,
			"reportTooltips": False,
			"reportDynamicContentChanges": True,
		}
		config.conf["keyboard"] = {
			"speakTypedCharacters": 1,
			"speakTypedWords": 0,
			"alertForSpellingErrors": True,
		}
		config.conf["documentFormatting"] = {
			"reportSpellingErrors2": 1,
			"reportComments": True,
			"reportRevisions": True,
			"reportHighlight": True,
			"reportLineIndentation": 0,
			"reportClickable": True,
		}
		speech.extensions.filter_speechSequence.callbacks.clear()
		globalPluginHandler.runningPlugins.clear()
		api.getFocusObject = lambda: None

	def tearDown(self):
		_reset_global_plugin_imports()
		speech.extensions.filter_speechSequence.callbacks.clear()
		globalPluginHandler.runningPlugins.clear()
		api.getFocusObject = lambda: None

	def test_plugin_registers_classic_speech_spec_without_touching_native_sections(self):
		module = _import_classic_speech_like_nvda()
		plugin = module.GlobalPlugin()
		try:
			self.assertIn("classicSpeech", config.conf.BASE_ONLY_SECTIONS)
			self.assertIn("classicSpeech", config.conf.spec)
			self.assertIn("presentation", config.conf)
			self.assertIn("keyboard", config.conf)
			self.assertIn("documentFormatting", config.conf)
			classic_spec = config.conf.spec["classicSpeech"]
			self.assertEqual(classic_spec["speechHookEnabled"], "boolean(default=True)")
			self.assertEqual(classic_spec["announceSpeechHookLoaded"], "boolean(default=False)")
			self.assertEqual(
				classic_spec["speechHookLoadedMessage"],
				"string(default='ClassicSpeech hook loaded')",
			)
			self.assertEqual(classic_spec["debugLogging"], "boolean(default=False)")
			self.assertEqual(classic_spec["voiceProfileData"], "string(default='{}')")
			self.assertIn("textProcessingData", classic_spec)
			self.assertEqual(
				classic_spec["textProcessingData"]["announceNewLinesDuringSayAll"],
				"boolean(default=False)",
			)
			self.assertEqual(
				classic_spec["textProcessingData"]["splitMixedCaseWords"],
				"boolean(default=False)",
			)
			self.assertEqual(
				classic_spec["textProcessingData"]["suppressWordInternalDashes"],
				"boolean(default=False)",
			)
			self.assertEqual(
				classic_spec["textProcessingData"]["spellAlphanumericData"],
				"string(default='off')",
			)
			self.assertEqual(
				classic_spec["textProcessingData"]["listItemStateReporting"],
				"string(default='notSelected')",
			)
			self.assertEqual(
				classic_spec["textProcessingData"]["repeatedCharacterMode"],
				"string(default='3')",
			)
			self.assertEqual(
				classic_spec["textProcessingData"]["filterRepeatedCharacters"],
				"boolean(default=False)",
			)
			self.assertEqual(
				classic_spec["textProcessingData"]["repeatedCharacterLimit"],
				"integer(default=3, min=1, max=20)",
			)
			self.assertIn("numberProcessingData", classic_spec)
			self.assertEqual(
				classic_spec["numberProcessingData"]["numberProcessingMode"],
				"string(default='synthesizer')",
			)
			self.assertEqual(
				classic_spec["numberProcessingData"]["singleDigitsIfNumberContains"],
				"string(default='synthesizer')",
			)
			self.assertEqual(classic_spec["numberProcessingData"]["phoneNumberProcessing"], "string(default='native')")
			self.assertEqual(classic_spec["numberProcessingData"]["friendlyTollFreePrefixes"], "boolean(default=True)")
			self.assertEqual(classic_spec["numberProcessingData"]["currencyProcessing"], "string(default='native')")
			self.assertEqual(classic_spec["numberProcessingData"]["ordinalProcessing"], "string(default='native')")
			self.assertEqual(
				classic_spec["numberProcessingData"]["numericDateProcessing"],
				"string(default='native')",
			)
			self.assertEqual(
				classic_spec["numberProcessingData"]["numericDateFormat"],
				"string(default='mdy')",
			)
			self.assertEqual(
				classic_spec["numberProcessingData"]["recognizeIsoDates"],
				"boolean(default=True)",
			)
			self.assertEqual(
				classic_spec["numberProcessingData"]["useWindowsDateFormat"],
				"boolean(default=False)",
			)
		finally:
			plugin.terminate()

	def test_startup_normalizes_late_false_default_button_value(self):
		config.conf.profiles[0]["classicSpeech"] = {
			"defaultProfile": "Beginner",
			"announceDefaultButton": "False",
		}
		module = _import_classic_speech_like_nvda()
		plugin = module.GlobalPlugin()
		try:
			self.assertIs(plugin.processor.verbosity.announce_default_button, False)
		finally:
			plugin.terminate()

	def test_text_processing_panel_imports_and_category_is_registered(self):
		module = _import_classic_speech_like_nvda()
		from globalPlugins._speech_core.settings.dialog import ClassicSpeechDialog
		from globalPlugins._speech_core.settings.text import TextProcessingPanel as ExportedTextProcessingPanel
		from globalPlugins._speech_core.settings.text import panel as text_processing_panel
		from globalPlugins._speech_core.settings.text.panel import TextProcessingPanel

		self.assertIn("Text Processing", ClassicSpeechDialog.CATEGORY_NAMES)
		self.assertIs(ExportedTextProcessingPanel, TextProcessingPanel)
		self.assertTrue(hasattr(TextProcessingPanel, "apply_live"))
		self.assertEqual(text_processing_panel._LIST_ITEM_STATE_REPORTING_CHOICES[0], ("NVDA native", "native"))
		self.assertIn(("Say not selected", "notSelected"), text_processing_panel._LIST_ITEM_STATE_REPORTING_CHOICES)

	def test_number_processing_panel_imports_and_category_is_registered(self):
		_import_classic_speech_like_nvda()
		from globalPlugins._speech_core.settings.dialog import ClassicSpeechDialog
		from globalPlugins._speech_core.settings import number_processing_panel
		from globalPlugins._speech_core.settings.number_processing_panel import NumberProcessingPanel

		self.assertIn("Number Processing", ClassicSpeechDialog.CATEGORY_NAMES)
		self.assertTrue(hasattr(NumberProcessingPanel, "apply_live"))
		self.assertEqual(number_processing_panel._NUMBER_PROCESSING_CHOICES[0], ("NVDA native", "synthesizer"))
		self.assertEqual(number_processing_panel._SINGLE_DIGITS_THRESHOLD_CHOICES[0], ("NVDA native", "synthesizer"))
		self.assertEqual(number_processing_panel._PHONE_NUMBER_PROCESSING_CHOICES, [("NVDA native", "native"), ("Grouped digits", "groupedDigits")])
		self.assertIn("Use friendly toll-free prefixes", Path(number_processing_panel.__file__).read_text())
		self.assertEqual(number_processing_panel._CURRENCY_PROCESSING_CHOICES, [("NVDA native", "native"), ("Dollars and cents", "dollarsAndCents")])
		self.assertEqual(number_processing_panel._ORDINAL_PROCESSING_CHOICES, [("NVDA native", "native"), ("Ordinals as words", "words")])
		self.assertEqual(
			number_processing_panel._NUMERIC_DATE_PROCESSING_CHOICES,
			[("NVDA native", "native"), ("Some", "some"), ("Full", "full")],
		)
		self.assertEqual(
			number_processing_panel._NUMERIC_DATE_FORMAT_CHOICES,
			[("Month day year", "mdy"), ("Day month year", "dmy"), ("Year month day", "ymd")],
		)
		self.assertNotIn(
			"Controlled by synthesizer",
			[label for label, _value in number_processing_panel._NUMBER_PROCESSING_CHOICES],
		)

	def test_misc_insert_tab_native_option_is_first(self):
		_import_classic_speech_like_nvda()
		from globalPlugins._speech_core.settings.constants import QUERY_OBJECT_SOURCE_CHOICES

		self.assertEqual(QUERY_OBJECT_SOURCE_CHOICES[0], ("NVDA native", "native"))

	def test_settings_input_controls_have_accessible_names(self):
		settings_dir = ROOT / "_speech_core" / "settings"
		widget_pattern = re.compile(
			r"self\.(\w+)\s*=\s*wx\.(Choice|ComboBox|TextCtrl|ListBox|CheckListBox)\b"
		)
		unnamed = []
		for path in sorted(settings_dir.rglob("*.py")):
			lines = path.read_text(encoding="utf-8").splitlines()
			for index, line in enumerate(lines):
				match = widget_pattern.search(line)
				if not match:
					continue
				control_name = match.group(1)
				# Constructors may span several lines; the SetName normally appears
				# immediately after construction but before the next control.
				window = "\n".join(lines[index:index + 20])
				if f"self.{control_name}.SetName(" not in window:
					unnamed.append(f"{path.relative_to(settings_dir)}:{index + 1}:{control_name}")
		self.assertEqual([], unnamed)

	def test_text_processing_setting_helpers_update_config(self):
		_import_classic_speech_like_nvda()
		from globalPlugins._speech_core.settings.text.config import (
			_get_announce_new_lines_during_say_all_enabled,
			_get_list_item_state_reporting_mode,
			_get_new_line_message,
			_get_repeated_character_mode,
			_get_spell_alphanumeric_data_mode,
			_get_split_mixed_case_words_enabled,
			_get_suppress_word_internal_dashes_enabled,
			_set_announce_new_lines_during_say_all_enabled,
			_set_list_item_state_reporting_mode,
			_set_new_line_message,
			_set_repeated_character_mode,
			_set_spell_alphanumeric_data_mode,
			_set_split_mixed_case_words_enabled,
			_set_suppress_word_internal_dashes_enabled,
		)

		self.assertFalse(_get_split_mixed_case_words_enabled())
		self.assertFalse(_get_announce_new_lines_during_say_all_enabled())
		self.assertEqual(_get_new_line_message(), "new line")
		_set_announce_new_lines_during_say_all_enabled(True)
		_set_new_line_message("line break")
		self.assertTrue(_get_announce_new_lines_during_say_all_enabled())
		self.assertEqual(_get_new_line_message(), "line break")
		self.assertTrue(
			config.conf.profiles[0]["classicSpeech"]["textProcessingData"]["announceNewLinesDuringSayAll"]
		)
		self.assertEqual(
			config.conf.profiles[0]["classicSpeech"]["textProcessingData"]["newLineMessage"],
			"line break",
		)

		_set_split_mixed_case_words_enabled(True)
		self.assertTrue(_get_split_mixed_case_words_enabled())
		self.assertTrue(config.conf.profiles[0]["classicSpeech"]["textProcessingData"]["splitMixedCaseWords"])

		self.assertFalse(_get_suppress_word_internal_dashes_enabled())
		_set_suppress_word_internal_dashes_enabled(True)
		self.assertTrue(_get_suppress_word_internal_dashes_enabled())
		self.assertTrue(config.conf.profiles[0]["classicSpeech"]["textProcessingData"]["suppressWordInternalDashes"])

		self.assertEqual(_get_spell_alphanumeric_data_mode(), "off")
		_set_spell_alphanumeric_data_mode("spell")
		self.assertEqual(_get_spell_alphanumeric_data_mode(), "spell")
		self.assertEqual(config.conf.profiles[0]["classicSpeech"]["textProcessingData"]["spellAlphanumericData"], "spell")
		_set_spell_alphanumeric_data_mode("phonetic")
		self.assertEqual(_get_spell_alphanumeric_data_mode(), "phonetic")
		self.assertEqual(config.conf.profiles[0]["classicSpeech"]["textProcessingData"]["spellAlphanumericData"], "phonetic")
		_set_spell_alphanumeric_data_mode("not-valid")
		self.assertEqual(_get_spell_alphanumeric_data_mode(), "off")

		self.assertEqual(_get_list_item_state_reporting_mode(), "notSelected")
		_set_list_item_state_reporting_mode("selected")
		self.assertEqual(_get_list_item_state_reporting_mode(), "selected")
		self.assertEqual(
			config.conf.profiles[0]["classicSpeech"]["textProcessingData"]["listItemStateReporting"],
			"selected",
		)
		_set_list_item_state_reporting_mode("not-valid")
		self.assertEqual(_get_list_item_state_reporting_mode(), "notSelected")


		self.assertEqual(_get_repeated_character_mode(), "3")
		_set_repeated_character_mode("count")
		self.assertEqual(_get_repeated_character_mode(), "count")
		self.assertEqual(config.conf.profiles[0]["classicSpeech"]["textProcessingData"]["repeatedCharacterMode"], "count")
		_set_repeated_character_mode("not-valid")
		self.assertEqual(_get_repeated_character_mode(), "3")

	def test_number_processing_setting_helpers_update_config(self):
		_import_classic_speech_like_nvda()
		from globalPlugins._speech_core.settings.config import (
			_get_currency_processing_mode,
			_get_friendly_toll_free_prefixes_enabled,
			_get_number_processing_mode,
			_get_numeric_date_format,
			_get_numeric_date_processing_mode,
			_get_phone_number_processing_mode,
			_get_recognize_iso_dates_enabled,
			_get_single_digits_threshold,
			_get_use_windows_date_format_enabled,
			_set_currency_processing_mode,
			_set_friendly_toll_free_prefixes_enabled,
			_set_number_processing_mode,
			_set_numeric_date_format,
			_set_numeric_date_processing_mode,
			_set_phone_number_processing_mode,
			_set_recognize_iso_dates_enabled,
			_set_single_digits_threshold,
			_set_use_windows_date_format_enabled,
		)

		self.assertEqual(_get_number_processing_mode(), "synthesizer")
		_set_number_processing_mode("singleDigits")
		self.assertEqual(_get_number_processing_mode(), "singleDigits")
		self.assertEqual(
			config.conf.profiles[0]["classicSpeech"]["numberProcessingData"]["numberProcessingMode"],
			"singleDigits",
		)
		_set_number_processing_mode("not-valid")
		self.assertEqual(_get_number_processing_mode(), "synthesizer")

		self.assertEqual(_get_single_digits_threshold(), "synthesizer")
		_set_single_digits_threshold("5")
		self.assertEqual(_get_single_digits_threshold(), "5")
		self.assertEqual(
			config.conf.profiles[0]["classicSpeech"]["numberProcessingData"]["singleDigitsIfNumberContains"],
			"5",
		)
		_set_single_digits_threshold("not-valid")
		self.assertEqual(_get_single_digits_threshold(), "synthesizer")

		self.assertEqual(_get_phone_number_processing_mode(), "native")
		_set_phone_number_processing_mode("groupedDigits")
		self.assertEqual(_get_phone_number_processing_mode(), "groupedDigits")
		self.assertEqual(
			config.conf.profiles[0]["classicSpeech"]["numberProcessingData"]["phoneNumberProcessing"],
			"groupedDigits",
		)
		_set_phone_number_processing_mode("not-valid")
		self.assertEqual(_get_phone_number_processing_mode(), "native")
		self.assertTrue(_get_friendly_toll_free_prefixes_enabled())
		_set_friendly_toll_free_prefixes_enabled(False)
		self.assertFalse(_get_friendly_toll_free_prefixes_enabled())
		self.assertEqual(_get_currency_processing_mode(), "native")
		_set_currency_processing_mode("dollarsAndCents")
		self.assertEqual(_get_currency_processing_mode(), "dollarsAndCents")
		self.assertEqual(_get_numeric_date_processing_mode(), "native")
		_set_numeric_date_processing_mode("some")
		self.assertEqual(_get_numeric_date_processing_mode(), "some")
		self.assertEqual(
			config.conf.profiles[0]["classicSpeech"]["numberProcessingData"]["numericDateProcessing"],
			"some",
		)
		_set_numeric_date_processing_mode("full")
		self.assertEqual(_get_numeric_date_processing_mode(), "full")
		_set_numeric_date_processing_mode("not-valid")
		self.assertEqual(_get_numeric_date_processing_mode(), "native")

		self.assertEqual(_get_numeric_date_format(), "mdy")
		_set_numeric_date_format("dmy")
		self.assertEqual(_get_numeric_date_format(), "dmy")
		self.assertEqual(
			config.conf.profiles[0]["classicSpeech"]["numberProcessingData"]["numericDateFormat"],
			"dmy",
		)
		_set_numeric_date_format("ymd")
		self.assertEqual(_get_numeric_date_format(), "ymd")
		self.assertEqual(
			config.conf.profiles[0]["classicSpeech"]["numberProcessingData"]["numericDateFormat"],
			"ymd",
		)
		_set_numeric_date_format("not-valid")
		self.assertEqual(_get_numeric_date_format(), "mdy")

		self.assertTrue(_get_recognize_iso_dates_enabled())
		_set_recognize_iso_dates_enabled(False)
		self.assertFalse(_get_recognize_iso_dates_enabled())
		self.assertFalse(
			config.conf.profiles[0]["classicSpeech"]["numberProcessingData"]["recognizeIsoDates"]
		)

		self.assertFalse(_get_use_windows_date_format_enabled())
		_set_use_windows_date_format_enabled(True)
		self.assertTrue(_get_use_windows_date_format_enabled())
		self.assertTrue(
			config.conf.profiles[0]["classicSpeech"]["numberProcessingData"]["useWindowsDateFormat"]
		)

	def test_text_processing_reads_base_config_when_layered_config_disagrees(self):
		_import_classic_speech_like_nvda()
		from globalPlugins._speech_core.processors.text import TextProcessor
		from globalPlugins._speech_core.settings.text.config import _get_repeated_character_mode

		config.conf["classicSpeech"] = {
			"textProcessingData": {"repeatedCharacterMode": "3"},
		}
		config.conf.profiles[0]["classicSpeech"] = {
			"textProcessingData": {"repeatedCharacterMode": "count"},
		}
		self.assertEqual(_get_repeated_character_mode(), "count")
		self.assertEqual(
			TextProcessor().process_literal_sequence(["wait!!!!!!"]),
			["wait", "6 exclamation marks"],
		)


	def test_config_can_start_with_speech_hook_disabled(self):
		config.conf.profiles[0]["classicSpeech"] = {
			"speechHookEnabled": False,
			"debugLogging": False,
		}
		module = _import_classic_speech_like_nvda()
		plugin = module.GlobalPlugin()
		try:
			self.assertFalse(plugin._speechHookRegistered)
			self.assertNotIn(plugin._filterSpeechSequence, speech.extensions.filter_speechSequence.callbacks)
		finally:
			plugin.terminate()

	def test_advanced_hook_loaded_message_helpers_update_config(self):
		module = _import_classic_speech_like_nvda()
		plugin = module.GlobalPlugin()
		try:
			from globalPlugins._speech_core.settings.config import (
				_get_announce_speech_hook_loaded_enabled,
				_get_speech_hook_loaded_message,
				_set_announce_speech_hook_loaded_enabled,
				_set_speech_hook_loaded_message,
			)

			self.assertFalse(_get_announce_speech_hook_loaded_enabled())
			self.assertEqual(_get_speech_hook_loaded_message(), "ClassicSpeech hook loaded")
			_set_announce_speech_hook_loaded_enabled(True)
			_set_speech_hook_loaded_message("Hook ready")
			self.assertTrue(_get_announce_speech_hook_loaded_enabled())
			self.assertEqual(_get_speech_hook_loaded_message(), "Hook ready")
			self.assertTrue(config.conf.profiles[0]["classicSpeech"]["announceSpeechHookLoaded"])
			self.assertEqual(
				config.conf.profiles[0]["classicSpeech"]["speechHookLoadedMessage"],
				"Hook ready",
			)
		finally:
			plugin.terminate()

	def test_speech_hook_loaded_message_is_spoken_on_initial_hook_registration(self):
		import ui

		ui.messages.clear()
		config.conf.profiles[0]["classicSpeech"] = {
			"speechHookEnabled": True,
			"announceSpeechHookLoaded": True,
			"speechHookLoadedMessage": "Hook ready",
			"debugLogging": False,
		}
		module = _import_classic_speech_like_nvda()
		plugin = module.GlobalPlugin()
		try:
			self.assertIn(plugin._filterSpeechSequence, speech.extensions.filter_speechSequence.callbacks)
			self.assertEqual(ui.messages, ["Hook ready"])
		finally:
			plugin.terminate()

	def test_speech_hook_loaded_message_is_spoken_when_hook_is_reenabled(self):
		import ui

		ui.messages.clear()
		config.conf.profiles[0]["classicSpeech"] = {
			"speechHookEnabled": False,
			"announceSpeechHookLoaded": True,
			"speechHookLoadedMessage": "Hook reloaded",
			"debugLogging": False,
		}
		module = _import_classic_speech_like_nvda()
		plugin = module.GlobalPlugin()
		globalPluginHandler.runningPlugins.append(plugin)
		try:
			from globalPlugins._speech_core.settings.config import _set_speech_hook_enabled

			self.assertNotIn(plugin._filterSpeechSequence, speech.extensions.filter_speechSequence.callbacks)
			self.assertEqual(ui.messages, [])
			_set_speech_hook_enabled(True)
			self.assertIn(plugin._filterSpeechSequence, speech.extensions.filter_speechSequence.callbacks)
			self.assertEqual(ui.messages, ["Hook reloaded"])
			_set_speech_hook_enabled(True)
			self.assertEqual(ui.messages, ["Hook reloaded"])
		finally:
			plugin.terminate()

	def test_hook_setting_live_toggles_registered_filter(self):
		module = _import_classic_speech_like_nvda()
		plugin = module.GlobalPlugin()
		globalPluginHandler.runningPlugins.append(plugin)
		try:
			from globalPlugins._speech_core.settings.config import _set_speech_hook_enabled

			self.assertIn(plugin._filterSpeechSequence, speech.extensions.filter_speechSequence.callbacks)
			_set_speech_hook_enabled(False)
			self.assertNotIn(plugin._filterSpeechSequence, speech.extensions.filter_speechSequence.callbacks)
			_set_speech_hook_enabled(True)
			self.assertIn(plugin._filterSpeechSequence, speech.extensions.filter_speechSequence.callbacks)
		finally:
			plugin.terminate()

	def test_hook_toggle_owns_independent_interrupt_and_key_label_runtime(self):
		module = _import_classic_speech_like_nvda()
		calls = []

		class Runtime:
			def install(self):
				calls.append("install")
			def uninstall(self):
				calls.append("uninstall")
			def terminate(self):
				calls.append("terminate")

		plugin = object.__new__(module.GlobalPlugin)
		plugin._interruptController = Runtime()
		plugin._keyLabelRuntime = Runtime()
		plugin._speechHookRegistered = False
		plugin._register_speech_hook = lambda: calls.append("register")
		plugin._unregister_speech_hook = lambda: calls.append("unregister")
		plugin._clear_hotkey_carryover = lambda: calls.append("clear-hotkeys")
		plugin._cancel_pending_container_flush = lambda: calls.append("cancel-flush")
		plugin._pendingContainerSequence = object()
		plugin.processor = types.SimpleNamespace(_bypass_next_sequence=True)

		plugin.set_speech_hook_enabled(False)
		self.assertEqual(
			calls,
			["unregister", "uninstall", "terminate", "clear-hotkeys", "cancel-flush"],
		)
		self.assertFalse(plugin.processor._bypass_next_sequence)
		self.assertIsNone(plugin._pendingContainerSequence)

		calls.clear()
		plugin.set_speech_hook_enabled(True)
		self.assertEqual(calls, ["install", "install", "register"])

	def test_advanced_panel_round_trips_every_control_through_live_config(self):
		module = _import_classic_speech_like_nvda()
		plugin = module.GlobalPlugin()
		globalPluginHandler.runningPlugins.append(plugin)
		try:
			from globalPlugins._speech_core.settings.advanced_panel import AdvancedPanel

			class Control:
				def __init__(self, value):
					self.value = value
				def GetValue(self):
					return self.value

			panel = types.SimpleNamespace(
				debugLogging=Control(True),
				speechHookEnabled=Control(False),
				announceSpeechHookLoaded=Control(True),
				speechHookLoadedMessage=Control("Ready for testing"),
			)
			AdvancedPanel.apply_live(panel, save=True)

			section = config.conf.profiles[0]["classicSpeech"]
			self.assertTrue(section["debugLogging"])
			self.assertFalse(section["speechHookEnabled"])
			self.assertTrue(section["announceSpeechHookLoaded"])
			self.assertEqual(section["speechHookLoadedMessage"], "Ready for testing")
			self.assertFalse(plugin._speechHookRegistered)
		finally:
			plugin.terminate()

	def test_nvda_control_c_save_route_calls_real_save_and_preserves_confirmation(self):
		import queueHandler
		import ui

		module = _import_classic_speech_like_nvda()
		original_main_frame = module.gui.mainFrame
		saves = []
		ui.messages.clear()
		config.conf.save = lambda: saves.append("saved")

		def native_save_command(event):
			config.conf.save()
			queueHandler.queueFunction(queueHandler.eventQueue, ui.message, "Configuration saved")

		def native_revert_command(event):
			queueHandler.queueFunction(queueHandler.eventQueue, ui.message, "Configuration applied")

		module.gui.ui = ui
		module.gui.mainFrame = types.SimpleNamespace(
			onSaveConfigurationCommand=native_save_command,
			onRevertToSavedConfigurationCommand=native_revert_command,
		)
		plugin = module.GlobalPlugin()
		try:
			module.gui.mainFrame.onSaveConfigurationCommand(None)
			self.assertEqual(saves, ["saved"])
			self.assertEqual(ui.messages, ["Configuration saved"])
		finally:
			plugin.terminate()
			module.gui.mainFrame = original_main_frame

	def test_hotkey_access_key_only_reads_base_config_when_layered_config_disagrees(self):
		_import_classic_speech_like_nvda()
		from globalPlugins._speech_core.base_processor.hotkeys import HotkeyProcessor

		config.conf["classicSpeech"] = {"hotkeyDialogAccessKeyOnly": False}
		config.conf.profiles[0]["classicSpeech"] = {"hotkeyDialogAccessKeyOnly": True}

		processor = HotkeyProcessor()
		self.assertTrue(processor._get_dialog_access_key_only())
		self.assertEqual(processor._format_hotkey_text("Alt+F", "dialog"), "F")
		config.conf.profiles[0]["classicSpeech"]["hotkeyDialogAccessKeyOnly"] = "False"
		self.assertFalse(processor._get_dialog_access_key_only())
		config.conf.profiles[0]["classicSpeech"].update({
			"announceMenuOpen": "False", "speechHookEnabled": "False",
			"textProcessingData": {"splitMixedCaseWords": "False"},
		})
		from globalPlugins._speech_core.settings.config_core import _ensure_classic_speech_section
		normalized = _ensure_classic_speech_section()
		self.assertIs(normalized["announceMenuOpen"], False)
		self.assertIs(normalized["speechHookEnabled"], False)
		self.assertIs(normalized["textProcessingData"]["splitMixedCaseWords"], False)

	def test_hotkeys_apply_save_command_and_fresh_reload_preserve_every_control(self):
		import copy
		import queueHandler
		import ui
		from globalPlugins._speech_core.settings.hotkeys_panel import HotkeysPanel

		module = _import_classic_speech_like_nvda()
		original_main_frame = module.gui.mainFrame
		original_save = getattr(config.conf, "save", None)
		persisted = {}
		ui.messages.clear()

		class Control:
			def __init__(self, value): self.value = value
			def GetValue(self): return self.value
			def GetSelection(self): return self.value

		panel = types.SimpleNamespace(
			hotkeyModeChoice=Control(3), hotkeyFormatChoice=Control(1),
			hotkeyTypesChoice=Control(0), dialogAccessKeyOnlyCheck=Control(True),
		)
		panel._getModeFromChoice = lambda: HotkeysPanel._getModeFromChoice(panel)
		panel._getFormatFromChoice = lambda: HotkeysPanel._getFormatFromChoice(panel)
		panel._getTypesFromChoice = lambda: HotkeysPanel._getTypesFromChoice(panel)
		HotkeysPanel.apply_live(panel)

		def save():
			persisted["base"] = copy.deepcopy(config.conf.profiles[0])

		def native_save_command(event):
			config.conf.save()
			queueHandler.queueFunction(queueHandler.eventQueue, ui.message, "Configuration saved")

		config.conf.save = save
		module.gui.ui = ui
		module.gui.mainFrame = types.SimpleNamespace(onSaveConfigurationCommand=native_save_command)
		plugin = module.GlobalPlugin()
		try:
			module.gui.mainFrame.onSaveConfigurationCommand(None)
			self.assertEqual(ui.messages, ["Configuration saved"])
			config.conf.profiles[0].clear()
			config.conf.profiles[0].update(copy.deepcopy(persisted["base"]))
			config.conf["classicSpeech"] = {}
			_reset_global_plugin_imports()
			_import_classic_speech_like_nvda()
			from globalPlugins._speech_core.settings.hotkeys_config import (
				_get_hotkey_dialog_access_key_only, _get_hotkey_format,
				_get_hotkey_mode, _get_hotkey_types,
			)
			self.assertEqual(_get_hotkey_mode(), "both")
			self.assertEqual(_get_hotkey_format(), "expandedNoPlus")
			self.assertEqual(_get_hotkey_types(), "access")
			self.assertTrue(_get_hotkey_dialog_access_key_only())
		finally:
			plugin.terminate()
			if original_save is None:
				delattr(config.conf, "save")
			else:
				config.conf.save = original_save
			module.gui.mainFrame = original_main_frame

	def test_classic_speech_config_spec_declares_every_written_hook_timing_and_hotkey_key(self):
		module = _import_classic_speech_like_nvda()
		plugin = module.GlobalPlugin()
		try:
			spec = config.conf.spec["classicSpeech"]
			self.assertEqual(spec["hotkeyTypes"], "string(default='both')")
			self.assertEqual(spec["shapeData"]["pausePlacement"], "string(default='before')")
		finally:
			plugin.terminate()

	def test_filter_path_leaves_literal_text_unchanged_by_default(self):
		plugin = _import_classic_speech_like_nvda().GlobalPlugin()
		try:
			sequence = ["SayAll"]
			result = plugin._filterSpeechSequence(sequence)
			self.assertIs(result, sequence)
			self.assertEqual([item for item in sequence if isinstance(item, str)], ["SayAll"])
			self.assertEqual([item.time for item in sequence if hasattr(item, "time")], [80])
		finally:
			plugin.terminate()

	def test_filter_preserves_terminal_index_command_after_preview_text(self):
		"""Terminal commands must remain after the text they terminate."""
		plugin = _import_classic_speech_like_nvda().GlobalPlugin()
		try:
			terminal_index = IndexCommand(1)
			sequence = ["Preview text", terminal_index]
			plugin._filterSpeechSequence(sequence)
			self.assertEqual(sequence[0], "Preview text")
			self.assertIs(sequence[1], terminal_index)
		finally:
			plugin.terminate()

	def test_filter_path_applies_enabled_mixed_case_literal_text(self):
		config.conf.profiles[0]["classicSpeech"] = {
			"speechHookEnabled": True,
			"debugLogging": False,
			"textProcessingData": {"splitMixedCaseWords": True},
		}
		api.getFocusObject = lambda: types.SimpleNamespace(
			role=types.SimpleNamespace(name="EDITABLETEXT"),
			name="Editor",
			parent=None,
		)
		module = _import_classic_speech_like_nvda()
		plugin = module.GlobalPlugin()
		try:
			sequence = ["SayAll"]
			plugin._filterSpeechSequence(sequence)
			self.assertEqual(sequence, ["Say All"])
		finally:
			plugin.terminate()

	def test_filter_path_applies_enabled_word_internal_dash_suppression(self):
		config.conf.profiles[0]["classicSpeech"] = {
			"speechHookEnabled": True,
			"debugLogging": False,
			"textProcessingData": {
				"suppressWordInternalDashes": True,
				"repeatedCharacterMode": "native",
			},
		}
		api.getFocusObject = lambda: types.SimpleNamespace(
			role=types.SimpleNamespace(name="EDITABLETEXT"),
			name="Editor",
			parent=None,
		)
		module = _import_classic_speech_like_nvda()
		plugin = module.GlobalPlugin()
		try:
			sequence = ["sister-in-law 1-800-444-4443 03-16-00 A-123"]
			plugin._filterSpeechSequence(sequence)
			self.assertEqual(sequence, ["sister in law 1-800-444-4443 03-16-00 A-123"])
		finally:
			plugin.terminate()

	def test_filter_path_applies_enabled_alphanumeric_spelling(self):
		config.conf.profiles[0]["classicSpeech"] = {
			"speechHookEnabled": True,
			"debugLogging": False,
			"textProcessingData": {
				"spellAlphanumericData": "spell",
				"repeatedCharacterMode": "native",
			},
		}
		api.getFocusObject = lambda: types.SimpleNamespace(
			role=types.SimpleNamespace(name="EDITABLETEXT"),
			name="Editor",
			parent=None,
		)
		module = _import_classic_speech_like_nvda()
		plugin = module.GlobalPlugin()
		try:
			sequence = ["license 123RON 2026 03-16-00"]
			plugin._filterSpeechSequence(sequence)
			self.assertEqual(sequence, ["license 1 2 3 R O N 2026 03-16-00"])
		finally:
			plugin.terminate()

	def test_filter_path_applies_enabled_alphanumeric_phonetic_spelling(self):
		config.conf.profiles[0]["classicSpeech"] = {
			"speechHookEnabled": True,
			"debugLogging": False,
			"textProcessingData": {
				"spellAlphanumericData": "phonetic",
				"repeatedCharacterMode": "native",
			},
		}
		api.getFocusObject = lambda: types.SimpleNamespace(
			role=types.SimpleNamespace(name="EDITABLETEXT"),
			name="Editor",
			parent=None,
		)
		module = _import_classic_speech_like_nvda()
		plugin = module.GlobalPlugin()
		try:
			sequence = ["license 123RON 2026 03-16-00"]
			plugin._filterSpeechSequence(sequence)
			self.assertEqual(sequence, ["license 1 2 3 Romeo Oscar November 2026 03-16-00"])
		finally:
			plugin.terminate()

	def test_filter_path_applies_enabled_repeated_character_literal_text(self):
		config.conf.profiles[0]["classicSpeech"] = {
			"speechHookEnabled": True,
			"debugLogging": False,
			"textProcessingData": {
				"repeatedCharacterMode": "3",
			},
		}
		api.getFocusObject = lambda: types.SimpleNamespace(
			role=types.SimpleNamespace(name="EDITABLETEXT"),
			name="Editor",
			parent=None,
		)
		module = _import_classic_speech_like_nvda()
		plugin = module.GlobalPlugin()
		try:
			sequence = ["wait!!!!!!"]
			plugin._filterSpeechSequence(sequence)
			self.assertEqual(sequence, ["wait!!!"])
		finally:
			plugin.terminate()

	def test_filter_path_count_mode_reports_repeated_spaces(self):
		config.conf.profiles[0]["classicSpeech"] = {
			"speechHookEnabled": True,
			"debugLogging": False,
			"textProcessingData": {
				"repeatedCharacterMode": "count",
			},
		}
		api.getFocusObject = lambda: types.SimpleNamespace(
			role=types.SimpleNamespace(name="EDITABLETEXT"),
			name="Editor",
			parent=None,
		)
		module = _import_classic_speech_like_nvda()
		plugin = module.GlobalPlugin()
		try:
			sequence = ["    indent"]
			plugin._filterSpeechSequence(sequence)
			self.assertEqual(sequence, ["4 spaces", "indent"])
		finally:
			plugin.terminate()

	def test_filter_path_all_mode_speaks_each_repeated_symbol(self):
		config.conf.profiles[0]["classicSpeech"] = {
			"speechHookEnabled": True,
			"debugLogging": False,
			"textProcessingData": {
				"repeatedCharacterMode": "all",
			},
		}
		api.getFocusObject = lambda: types.SimpleNamespace(
			role=types.SimpleNamespace(name="EDITABLETEXT"),
			name="Editor",
			parent=None,
		)
		module = _import_classic_speech_like_nvda()
		plugin = module.GlobalPlugin()
		try:
			sequence = ["!!!!!!    indent"]
			plugin._filterSpeechSequence(sequence)
			self.assertEqual(
				sequence,
				[
					"exclamation mark exclamation mark exclamation mark exclamation mark exclamation mark exclamation mark",
					"    indent",
				],
			)
		finally:
			plugin.terminate()

	def test_filter_path_repeated_processing_ignores_letters_and_numbers(self):
		config.conf.profiles[0]["classicSpeech"] = {
			"speechHookEnabled": True,
			"debugLogging": False,
			"textProcessingData": {
				"repeatedCharacterMode": "3",
			},
		}
		api.getFocusObject = lambda: types.SimpleNamespace(
			role=types.SimpleNamespace(name="EDITABLETEXT"),
			name="Editor",
			parent=None,
		)
		module = _import_classic_speech_like_nvda()
		plugin = module.GlobalPlugin()
		try:
			sequence = ["letter bookkeeper 1000!!!!"]
			plugin._filterSpeechSequence(sequence)
			self.assertEqual(sequence, ["letter bookkeeper 1000!!!"])
		finally:
			plugin.terminate()

	def test_filter_path_text_processing_runs_before_literal_bypass_with_commands(self):
		config.conf.profiles[0]["classicSpeech"] = {
			"speechHookEnabled": True,
			"debugLogging": False,
			"textProcessingData": {
				"repeatedCharacterMode": "4",
			},
		}
		api.getFocusObject = lambda: types.SimpleNamespace(
			role=types.SimpleNamespace(name="EDITABLETEXT"),
			name="Editor",
			parent=None,
		)
		module = _import_classic_speech_like_nvda()
		plugin = module.GlobalPlugin()
		try:
			sequence = [CharacterModeCommand(True), "----------\r", CharacterModeCommand(False)]
			plugin._filterSpeechSequence(sequence)
			self.assertTrue(any(item == "dash dash dash dash" for item in sequence))
		finally:
			plugin.terminate()

	def test_filter_path_number_mode_rewrites_line_review_numbers(self):
		config.conf.profiles[0]["classicSpeech"] = {
			"speechHookEnabled": True,
			"debugLogging": False,
			"numberProcessingData": {
				"numberProcessingMode": "singleDigits",
				"singleDigitsIfNumberContains": "synthesizer",
			},
		}
		api.getFocusObject = lambda: types.SimpleNamespace(
			role=types.SimpleNamespace(name="EDITABLETEXT"),
			name="Editor",
			parent=None,
		)
		module = _import_classic_speech_like_nvda()
		plugin = module.GlobalPlugin()
		try:
			sequence = ["1234567890\r"]
			plugin._filterSpeechSequence(sequence)
			self.assertEqual(sequence, ["one two three four five six seven eight nine zero\r"])
		finally:
			plugin.terminate()

	def test_filter_path_numeric_date_processing_rewrites_month_day_year(self):
		config.conf.profiles[0]["classicSpeech"] = {
			"speechHookEnabled": True,
			"debugLogging": False,
			"numberProcessingData": {"numericDateProcessing": "some"},
		}
		api.getFocusObject = lambda: types.SimpleNamespace(
			role=types.SimpleNamespace(name="EDITABLETEXT"), name="Editor", parent=None
		)
		module = _import_classic_speech_like_nvda()
		plugin = module.GlobalPlugin()
		try:
			sequence = ["Due 5/9/2026 and 5/9."]
			plugin._filterSpeechSequence(sequence)
			self.assertEqual(sequence, ["Due May ninth, twenty twenty six and 5/9."])
		finally:
			plugin.terminate()

	def test_filter_path_phone_number_processing_rewrites_common_us_numbers(self):
		config.conf.profiles[0]["classicSpeech"] = {
			"speechHookEnabled": True,
			"debugLogging": False,
			"numberProcessingData": {"phoneNumberProcessing": "groupedDigits"},
		}
		api.getFocusObject = lambda: types.SimpleNamespace(
			role=types.SimpleNamespace(name="EDITABLETEXT"), name="Editor", parent=None
		)
		module = _import_classic_speech_like_nvda()
		plugin = module.GlobalPlugin()
		try:
			sequence = ["Call 555-123-4567, 1-800-444-4443, or 03-16-00."]
			plugin._filterSpeechSequence(sequence)
			self.assertEqual(sequence, [
				"Call five five five, one two three, four five six seven, "
				"one eight hundred, four four four, four four four three, or 03-16-00."
			])
		finally:
			plugin.terminate()

	def test_filter_path_number_mode_does_not_rewrite_character_navigation_numbers(self):
		for mode in ("singleDigits", "pairs", "fullNumbers"):
			with self.subTest(mode=mode):
				config.conf.profiles[0]["classicSpeech"] = {
					"speechHookEnabled": True,
					"debugLogging": False,
					"numberProcessingData": {
						"numberProcessingMode": mode,
						"singleDigitsIfNumberContains": "synthesizer",
					},
				}
				api.getFocusObject = lambda: types.SimpleNamespace(
					role=types.SimpleNamespace(name="EDITABLETEXT"),
					name="Editor",
					parent=None,
				)
				module = _import_classic_speech_like_nvda()
				plugin = module.GlobalPlugin()
				try:
					sequence = [CharacterModeCommand(True), "1", CharacterModeCommand(False)]
					plugin._filterSpeechSequence(sequence)
					self.assertEqual(sequence[1], "1")
					self.assertEqual(
						[getattr(sequence[0], "state", None), getattr(sequence[2], "state", None)],
						[True, False],
					)
				finally:
					plugin.terminate()

	def test_filter_path_single_digits_threshold_still_applies_to_cursor_review_numbers(self):
		config.conf.profiles[0]["classicSpeech"] = {
			"speechHookEnabled": True,
			"debugLogging": False,
			"numberProcessingData": {
				"numberProcessingMode": "synthesizer",
				"singleDigitsIfNumberContains": "5",
			},
		}
		api.getFocusObject = lambda: types.SimpleNamespace(
			role=types.SimpleNamespace(name="EDITABLETEXT"),
			name="Editor",
			parent=None,
		)
		module = _import_classic_speech_like_nvda()
		plugin = module.GlobalPlugin()
		try:
			sequence = ["1234567890\r"]
			plugin._filterSpeechSequence(sequence)
			self.assertEqual(
				sequence,
				["one two three four five six seven eight nine zero\r"],
			)
		finally:
			plugin.terminate()

	def test_diagnostic_logging_only_logs_when_enabled(self):
		import logHandler

		module = _import_classic_speech_like_nvda()
		plugin = module.GlobalPlugin()
		try:
			logHandler.log.messages.clear()
			plugin._debug_log("quiet")
			self.assertEqual(logHandler.log.messages, [])
			config.conf.profiles[0]["classicSpeech"]["debugLogging"] = True
			plugin._debug_log("loud")
			self.assertTrue(any("ClassicSpeech debug: loud" in text for _level, text in logHandler.log.messages))
		finally:
			plugin.terminate()


	def test_plugin_registers_and_unregisters_speech_filter(self):
		module = _import_classic_speech_like_nvda()
		plugin = module.GlobalPlugin()
		hook = plugin._filterSpeechSequence
		try:
			self.assertIn(hook, speech.extensions.filter_speechSequence.callbacks)
		finally:
			plugin.terminate()
		self.assertNotIn(hook, speech.extensions.filter_speechSequence.callbacks)


class ClassicSpeechConfigInitializationTests(unittest.TestCase):
	def test_late_registered_base_section_does_not_call_configobj_section_validation(self):
		source = (ROOT / "_speech_core" / "plugin_config.py").read_text(encoding="utf-8")
		self.assertNotIn("baseConf.validate(config.conf.validator, section=sect)", source)


class NVDAMasterFullSynthOverlayContractTests(unittest.TestCase):
	def test_speech_manager_and_synth_handler_preserve_same_synth_profile_switch_contract(self):
		manager = (NVDA_SOURCE / "speech" / "manager.py").read_text(encoding="utf-8")
		synth_handler = (NVDA_SOURCE / "synthDriverHandler.py").read_text(encoding="utf-8")
		self.assertIn("isinstance(command, ConfigProfileTriggerCommand)", manager)
		self.assertIn("handlePostConfigProfileSwitch(resetSpeechIfNeeded=False)", manager)
		self.assertIn("while queue.pendingSequences and isinstance(", manager)
		self.assertIn("if conf[\"synth\"] != _curSynth.name", synth_handler)
		self.assertIn("_curSynth.loadSettings(onlyChanged=True)", synth_handler)


if __name__ == "__main__":
	unittest.main(verbosity=2)
