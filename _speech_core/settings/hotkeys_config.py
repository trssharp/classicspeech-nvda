"""Hotkeys panel settings helpers."""

from .config_core import _ensure_classic_speech_section, _set_nvda_setting
from .constants import (
	HOTKEY_FORMAT_ABBREVIATED_NO_PLUS,
	HOTKEY_FORMAT_EXPANDED_NO_PLUS,
	HOTKEY_FORMAT_NATIVE,
	HOTKEY_MODE_BOTH,
	HOTKEY_MODE_CHOICES,
	HOTKEY_MODE_DIALOGS,
	HOTKEY_MODE_MENUS,
	HOTKEY_MODE_OFF,
	HOTKEY_TYPES_ACCESS,
	HOTKEY_TYPES_BOTH,
	HOTKEY_TYPES_COMMAND,
)


def _get_hotkey_mode():
	conf = _ensure_classic_speech_section()
	try:
		mode = str(conf.get("hotkeyMode", HOTKEY_MODE_BOTH))
	except Exception:
		mode = HOTKEY_MODE_BOTH
	valid = {HOTKEY_MODE_OFF, HOTKEY_MODE_DIALOGS, HOTKEY_MODE_MENUS, HOTKEY_MODE_BOTH}
	if mode not in valid:
		mode = HOTKEY_MODE_BOTH
	return mode


def _set_hotkey_mode(mode: str):
	conf = _ensure_classic_speech_section()
	mode = str(mode or HOTKEY_MODE_BOTH)
	valid = {HOTKEY_MODE_OFF, HOTKEY_MODE_DIALOGS, HOTKEY_MODE_MENUS, HOTKEY_MODE_BOTH}
	if mode not in valid:
		mode = HOTKEY_MODE_BOTH
	conf["hotkeyMode"] = mode
	_set_nvda_setting(
		"presentation",
		"reportKeyboardShortcuts",
		mode != HOTKEY_MODE_OFF,
	)
	return mode


def _get_hotkey_mode_label(mode: str):
	mode = str(mode or HOTKEY_MODE_BOTH)
	for label, value in HOTKEY_MODE_CHOICES:
		if value == mode:
			return label
	return "Both"


def _get_hotkey_format():
	conf = _ensure_classic_speech_section()
	try:
		format_value = str(conf.get("hotkeyFormat", HOTKEY_FORMAT_NATIVE))
	except Exception:
		format_value = HOTKEY_FORMAT_NATIVE
	valid = {
		HOTKEY_FORMAT_NATIVE,
		HOTKEY_FORMAT_EXPANDED_NO_PLUS,
		HOTKEY_FORMAT_ABBREVIATED_NO_PLUS,
	}
	if format_value not in valid:
		format_value = HOTKEY_FORMAT_NATIVE
	return format_value


def _set_hotkey_format(format_value: str):
	conf = _ensure_classic_speech_section()
	format_value = str(format_value or HOTKEY_FORMAT_NATIVE)
	valid = {
		HOTKEY_FORMAT_NATIVE,
		HOTKEY_FORMAT_EXPANDED_NO_PLUS,
		HOTKEY_FORMAT_ABBREVIATED_NO_PLUS,
	}
	if format_value not in valid:
		format_value = HOTKEY_FORMAT_NATIVE
	conf["hotkeyFormat"] = format_value
	return format_value



def _get_hotkey_types():
	conf = _ensure_classic_speech_section()
	try:
		types_value = str(conf.get("hotkeyTypes", HOTKEY_TYPES_BOTH))
	except Exception:
		types_value = HOTKEY_TYPES_BOTH
	valid = {HOTKEY_TYPES_ACCESS, HOTKEY_TYPES_COMMAND, HOTKEY_TYPES_BOTH}
	if types_value not in valid:
		types_value = HOTKEY_TYPES_BOTH
	return types_value


def _set_hotkey_types(types_value: str):
	conf = _ensure_classic_speech_section()
	types_value = str(types_value or HOTKEY_TYPES_BOTH)
	valid = {HOTKEY_TYPES_ACCESS, HOTKEY_TYPES_COMMAND, HOTKEY_TYPES_BOTH}
	if types_value not in valid:
		types_value = HOTKEY_TYPES_BOTH
	conf["hotkeyTypes"] = types_value
	return types_value

def _get_hotkey_dialog_access_key_only():
	conf = _ensure_classic_speech_section()
	try:
		return bool(conf.get("hotkeyDialogAccessKeyOnly", False))
	except Exception:
		return False


def _set_hotkey_dialog_access_key_only(enabled):
	conf = _ensure_classic_speech_section()
	conf["hotkeyDialogAccessKeyOnly"] = bool(enabled)
	return bool(enabled)

