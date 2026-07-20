"""Misc panel settings helpers."""

import logHandler

from .config_core import (
	_ensure_classic_speech_section,
	_get_live_verbosity_manager,
	_get_nvda_setting,
	_set_nvda_setting,
)
from .constants import QUERY_OBJECT_SOURCE_FOCUS, QUERY_OBJECT_SOURCE_NATIVE, QUERY_OBJECT_SOURCE_NAVIGATOR

log = logHandler.log


def _get_default_button_enabled():
	conf = _ensure_classic_speech_section()
	return bool(conf.get("announceDefaultButton", False))


def _set_default_button_enabled(enabled: bool):
	conf = _ensure_classic_speech_section()
	conf["announceDefaultButton"] = bool(enabled)

	verbosity = _get_live_verbosity_manager()
	if verbosity is not None:
		try:
			verbosity.announce_default_button = bool(enabled)
		except Exception:
			log.exception("Failed to live-apply announceDefaultButton")



_FALLBACK_SPEECH_DELAY_CHOICES = [250, 500, 750, 1000, 1500, 2000, 3000, 4000]


def _fallback_delay_to_choice_string(value):
	try:
		value = int(value)
	except Exception:
		value = 1000
	if value not in _FALLBACK_SPEECH_DELAY_CHOICES:
		value = 1000
	return f"{value} ms"


def _choice_string_to_fallback_delay(choice):
	try:
		return int(str(choice).split()[0])
	except Exception:
		return 1000

def _get_prevent_automatic_speech_interrupt_enabled():
	conf = _ensure_classic_speech_section()
	return bool(conf.get("preventAutomaticSpeechInterrupt", False))


def _set_prevent_automatic_speech_interrupt_enabled(enabled: bool):
	conf = _ensure_classic_speech_section()
	conf["preventAutomaticSpeechInterrupt"] = bool(enabled)


def _get_speech_interrupt_for_typed_characters_enabled():
	return _get_nvda_setting("keyboard", "speechInterruptForCharacters", True)


def _set_speech_interrupt_for_typed_characters_enabled(enabled: bool):
	_set_nvda_setting("keyboard", "speechInterruptForCharacters", bool(enabled))


def _get_speech_interrupt_for_enter_enabled():
	return _get_nvda_setting("keyboard", "speechInterruptForEnter", True)


def _set_speech_interrupt_for_enter_enabled(enabled: bool):
	_set_nvda_setting("keyboard", "speechInterruptForEnter", bool(enabled))


def _get_automatic_speech_interrupt_fallback_ms():
	conf = _ensure_classic_speech_section()
	try:
		value = int(conf.get("automaticSpeechInterruptFallbackMs", 1000))
	except Exception:
		value = 1000
	return max(250, min(value, 4000))


def _set_automatic_speech_interrupt_fallback_ms(value):
	conf = _ensure_classic_speech_section()
	try:
		value = int(value)
	except Exception:
		value = 1000
	conf["automaticSpeechInterruptFallbackMs"] = max(250, min(value, 4000))



def _get_query_object_source():
	conf = _ensure_classic_speech_section()
	value = str(conf.get("queryObjectSource", QUERY_OBJECT_SOURCE_FOCUS)).strip().lower()
	if value not in {QUERY_OBJECT_SOURCE_FOCUS, QUERY_OBJECT_SOURCE_NAVIGATOR, QUERY_OBJECT_SOURCE_NATIVE}:
		value = QUERY_OBJECT_SOURCE_FOCUS
	return value


def _set_query_object_source(value):
	conf = _ensure_classic_speech_section()
	value = str(value or QUERY_OBJECT_SOURCE_FOCUS).strip().lower()
	if value not in {QUERY_OBJECT_SOURCE_FOCUS, QUERY_OBJECT_SOURCE_NAVIGATOR, QUERY_OBJECT_SOURCE_NATIVE}:
		value = QUERY_OBJECT_SOURCE_FOCUS
	conf["queryObjectSource"] = value


def get_query_object_source():
	return _get_query_object_source()


def _get_object_navigation_processing_enabled():
	conf = _ensure_classic_speech_section()
	return bool(conf.get("objectNavigationProcessing", False))


def _set_object_navigation_processing_enabled(enabled: bool):
	conf = _ensure_classic_speech_section()
	conf["objectNavigationProcessing"] = bool(enabled)


def get_object_navigation_processing_enabled():
	return _get_object_navigation_processing_enabled()


def _get_guess_object_position_information_when_unavailable():
	return _get_nvda_setting(
		"presentation",
		"guessObjectPositionInformationWhenUnavailable",
		False,
	)


def _set_guess_object_position_information_when_unavailable(enabled: bool):
	_set_nvda_setting(
		"presentation",
		"guessObjectPositionInformationWhenUnavailable",
		bool(enabled),
	)
