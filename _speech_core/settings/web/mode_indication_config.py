"""Persistent custom text for Browse and Focus Mode indication."""
from __future__ import annotations

import copy

import config

MODE_INDICATION_DATA_KEY = "modeIndicationData"
BROWSE_MODE_MESSAGE_KEY = "browseModeMessage"
FOCUS_MODE_MESSAGE_KEY = "focusModeMessage"
DEFAULT_BROWSE_MODE_MESSAGE = "Browse mode"
DEFAULT_FOCUS_MODE_MESSAGE = "Focus mode"


def _get_base_conf():
	try:
		return config.conf.profiles[0]
	except Exception:
		return config.conf


def _get_data():
	"""Read custom messages without creating ClassicSpeech configuration."""
	try:
		section = _get_base_conf().get("classicSpeech")
		data = section.get(MODE_INDICATION_DATA_KEY) if hasattr(section, "get") else None
		return data if hasattr(data, "get") else None
	except Exception:
		return None


def _ensure_data():
	base_conf = _get_base_conf()
	section = base_conf.get("classicSpeech") if hasattr(base_conf, "get") else None
	if not hasattr(section, "get"):
		section = {}
		base_conf["classicSpeech"] = section
	data = section.get(MODE_INDICATION_DATA_KEY)
	if not hasattr(data, "get"):
		data = {}
		section[MODE_INDICATION_DATA_KEY] = data
	return data


def _normalize_custom_message(value: object) -> str:
	return value.strip() if isinstance(value, str) else ""


def _get_custom_message(key: str) -> str | None:
	data = _get_data()
	message = _normalize_custom_message(data.get(key) if data is not None else None)
	return message or None


def _set_custom_message(key: str, message: object) -> str:
	normalized = _normalize_custom_message(message)
	_ensure_data()[key] = normalized
	return normalized


def get_browse_mode_message() -> str:
	return _get_custom_message(BROWSE_MODE_MESSAGE_KEY) or DEFAULT_BROWSE_MODE_MESSAGE


def set_browse_mode_message(message: object) -> str:
	normalized = _normalize_custom_message(message)
	if normalized == DEFAULT_BROWSE_MODE_MESSAGE:
		normalized = ""
	return _set_custom_message(BROWSE_MODE_MESSAGE_KEY, normalized) or DEFAULT_BROWSE_MODE_MESSAGE


def get_focus_mode_message() -> str:
	return _get_custom_message(FOCUS_MODE_MESSAGE_KEY) or DEFAULT_FOCUS_MODE_MESSAGE


def set_focus_mode_message(message: object) -> str:
	normalized = _normalize_custom_message(message)
	if normalized == DEFAULT_FOCUS_MODE_MESSAGE:
		normalized = ""
	return _set_custom_message(FOCUS_MODE_MESSAGE_KEY, normalized) or DEFAULT_FOCUS_MODE_MESSAGE


def get_custom_browse_mode_message() -> str | None:
	return _get_custom_message(BROWSE_MODE_MESSAGE_KEY)


def get_custom_focus_mode_message() -> str | None:
	return _get_custom_message(FOCUS_MODE_MESSAGE_KEY)


def capture_mode_indication_state() -> dict:
	"""Capture exact presence/data without materializing ClassicSpeech config."""
	base_conf = _get_base_conf()
	section = base_conf.get("classicSpeech") if hasattr(base_conf, "get") else None
	has_section = hasattr(section, "get")
	has_data = has_section and MODE_INDICATION_DATA_KEY in section
	return {
		"hasClassicSpeechSection": has_section,
		"hasModeIndicationData": has_data,
		"modeIndicationData": copy.deepcopy(section.get(MODE_INDICATION_DATA_KEY)) if has_data else None,
	}


def restore_mode_indication_state(snapshot: object) -> None:
	"""Restore this data exactly, preserving unrelated ClassicSpeech entries."""
	if not hasattr(snapshot, "get") or "hasModeIndicationData" not in snapshot:
		return
	base_conf = _get_base_conf()
	section = base_conf.get("classicSpeech") if hasattr(base_conf, "get") else None
	if snapshot.get("hasModeIndicationData"):
		if not hasattr(section, "get"):
			section = {}
			base_conf["classicSpeech"] = section
		section[MODE_INDICATION_DATA_KEY] = copy.deepcopy(snapshot.get("modeIndicationData"))
		return
	if hasattr(section, "__delitem__") and MODE_INDICATION_DATA_KEY in section:
		del section[MODE_INDICATION_DATA_KEY]
	if not snapshot.get("hasClassicSpeechSection") and hasattr(section, "__len__") and not section:
		try:
			del base_conf["classicSpeech"]
		except Exception:
			pass
