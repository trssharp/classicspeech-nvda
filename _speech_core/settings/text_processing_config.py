"""Text-processing settings helpers for ClassicSpeech."""

from .config_core import _ensure_classic_speech_section


def _ensure_text_processing_section():
	conf = _ensure_classic_speech_section()
	section = conf.get("textProcessingData")
	if not isinstance(section, dict):
		section = {}
		conf["textProcessingData"] = section
	return section


REPEATED_CHARACTER_MODE_NATIVE = "native"
REPEATED_CHARACTER_MODE_3 = "3"
REPEATED_CHARACTER_MODE_4 = "4"
REPEATED_CHARACTER_MODE_5 = "5"
REPEATED_CHARACTER_MODE_6 = "6"
REPEATED_CHARACTER_MODE_ALL = "all"
REPEATED_CHARACTER_MODE_COUNT = "count"
REPEATED_CHARACTER_MODES = {
	REPEATED_CHARACTER_MODE_NATIVE,
	REPEATED_CHARACTER_MODE_3,
	REPEATED_CHARACTER_MODE_4,
	REPEATED_CHARACTER_MODE_5,
	REPEATED_CHARACTER_MODE_6,
	REPEATED_CHARACTER_MODE_ALL,
	REPEATED_CHARACTER_MODE_COUNT,
}

SPELL_ALPHANUMERIC_DATA_OFF = "off"
SPELL_ALPHANUMERIC_DATA_SPELL = "spell"
SPELL_ALPHANUMERIC_DATA_PHONETIC = "phonetic"
SPELL_ALPHANUMERIC_DATA_MODES = {
	SPELL_ALPHANUMERIC_DATA_OFF,
	SPELL_ALPHANUMERIC_DATA_SPELL,
	SPELL_ALPHANUMERIC_DATA_PHONETIC,
}

LIST_ITEM_STATE_REPORTING_NATIVE = "native"
LIST_ITEM_STATE_REPORTING_NONE = "none"
LIST_ITEM_STATE_REPORTING_SELECTED = "selected"
LIST_ITEM_STATE_REPORTING_NOT_SELECTED = "notSelected"
LIST_ITEM_STATE_REPORTING_BOTH = "both"
LIST_ITEM_STATE_REPORTING_MODES = {
	LIST_ITEM_STATE_REPORTING_NATIVE,
	LIST_ITEM_STATE_REPORTING_NONE,
	LIST_ITEM_STATE_REPORTING_SELECTED,
	LIST_ITEM_STATE_REPORTING_NOT_SELECTED,
	LIST_ITEM_STATE_REPORTING_BOTH,
}
def _get_announce_new_lines_during_say_all_enabled():
	section = _ensure_text_processing_section()
	return bool(section.get("announceNewLinesDuringSayAll", False))


def get_announce_new_lines_during_say_all_enabled():
	return _get_announce_new_lines_during_say_all_enabled()


def _set_announce_new_lines_during_say_all_enabled(enabled: bool):
	section = _ensure_text_processing_section()
	section["announceNewLinesDuringSayAll"] = bool(enabled)
	return bool(enabled)


def _get_new_line_message():
	section = _ensure_text_processing_section()
	message = str(section.get("newLineMessage", "new line") or "").strip()
	return message or "new line"


def get_new_line_message():
	return _get_new_line_message()


def _set_new_line_message(message: str):
	section = _ensure_text_processing_section()
	message = str(message or "").strip()
	section["newLineMessage"] = message
	return message


def _get_split_mixed_case_words_enabled():
	section = _ensure_text_processing_section()
	return bool(section.get("splitMixedCaseWords", False))


def get_split_mixed_case_words_enabled():
	return _get_split_mixed_case_words_enabled()


def _set_split_mixed_case_words_enabled(enabled: bool):
	section = _ensure_text_processing_section()
	section["splitMixedCaseWords"] = bool(enabled)
	return bool(enabled)


def _get_suppress_word_internal_dashes_enabled():
	section = _ensure_text_processing_section()
	return bool(section.get("suppressWordInternalDashes", False))


def get_suppress_word_internal_dashes_enabled():
	return _get_suppress_word_internal_dashes_enabled()


def _set_suppress_word_internal_dashes_enabled(enabled: bool):
	section = _ensure_text_processing_section()
	section["suppressWordInternalDashes"] = bool(enabled)
	return bool(enabled)


def _get_spell_alphanumeric_data_mode():
	section = _ensure_text_processing_section()
	mode = str(section.get("spellAlphanumericData", SPELL_ALPHANUMERIC_DATA_OFF)).strip().lower()
	if mode not in SPELL_ALPHANUMERIC_DATA_MODES:
		mode = SPELL_ALPHANUMERIC_DATA_OFF
	return mode


def get_spell_alphanumeric_data_mode():
	return _get_spell_alphanumeric_data_mode()


def _set_spell_alphanumeric_data_mode(mode):
	section = _ensure_text_processing_section()
	mode = str(mode or SPELL_ALPHANUMERIC_DATA_OFF).strip().lower()
	if mode not in SPELL_ALPHANUMERIC_DATA_MODES:
		mode = SPELL_ALPHANUMERIC_DATA_OFF
	section["spellAlphanumericData"] = mode
	return mode


def _get_list_item_state_reporting_mode():
	section = _ensure_text_processing_section()
	mode = str(section.get("listItemStateReporting", LIST_ITEM_STATE_REPORTING_NOT_SELECTED)).strip()
	return mode if mode in LIST_ITEM_STATE_REPORTING_MODES else LIST_ITEM_STATE_REPORTING_NOT_SELECTED


def get_list_item_state_reporting_mode():
	return _get_list_item_state_reporting_mode()


def _set_list_item_state_reporting_mode(mode):
	section = _ensure_text_processing_section()
	mode = str(mode or LIST_ITEM_STATE_REPORTING_NOT_SELECTED).strip()
	if mode not in LIST_ITEM_STATE_REPORTING_MODES:
		mode = LIST_ITEM_STATE_REPORTING_NOT_SELECTED
	section["listItemStateReporting"] = mode
	return mode



def _get_repeated_character_mode():
	section = _ensure_text_processing_section()
	mode = str(section.get("repeatedCharacterMode", REPEATED_CHARACTER_MODE_3)).strip().lower()
	# Compatibility for the brief checkbox/text-field experiment.
	if "repeatedCharacterMode" not in section:
		if section.get("filterRepeatedCharacters") is False:
			# New v2 default intentionally moves to JFW-like 3; explicit native now
			# lives in repeatedCharacterMode.
			mode = REPEATED_CHARACTER_MODE_3
		else:
			try:
				limit = int(section.get("repeatedCharacterLimit", 3))
			except Exception:
				limit = 3
			mode = str(limit) if limit in {3, 4, 5, 6} else REPEATED_CHARACTER_MODE_3
	if mode not in REPEATED_CHARACTER_MODES:
		mode = REPEATED_CHARACTER_MODE_3
	return mode


def get_repeated_character_mode():
	return _get_repeated_character_mode()


def _set_repeated_character_mode(mode):
	section = _ensure_text_processing_section()
	mode = str(mode or REPEATED_CHARACTER_MODE_3).strip().lower()
	if mode not in REPEATED_CHARACTER_MODES:
		mode = REPEATED_CHARACTER_MODE_3
	section["repeatedCharacterMode"] = mode
	return mode


# Compatibility helpers kept for older tests/callers during v2 development.
def _get_repeated_character_filter_enabled():
	return _get_repeated_character_mode() != REPEATED_CHARACTER_MODE_NATIVE


def get_repeated_character_filter_enabled():
	return _get_repeated_character_filter_enabled()


def _set_repeated_character_filter_enabled(enabled: bool):
	return _set_repeated_character_mode(
		REPEATED_CHARACTER_MODE_3 if enabled else REPEATED_CHARACTER_MODE_NATIVE
	)


def _get_repeated_character_limit():
	mode = _get_repeated_character_mode()
	if mode in {REPEATED_CHARACTER_MODE_3, REPEATED_CHARACTER_MODE_4, REPEATED_CHARACTER_MODE_5, REPEATED_CHARACTER_MODE_6}:
		return int(mode)
	return 3


def _set_repeated_character_limit(value):
	try:
		value = int(value)
	except Exception:
		value = 3
	value = max(1, min(value, 20))
	if value in {3, 4, 5, 6}:
		_set_repeated_character_mode(str(value))
	return value


