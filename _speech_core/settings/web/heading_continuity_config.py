"""Persistent opt-in settings for heading-continuity presentation."""
from __future__ import annotations

import copy

import config

HEADING_CONTINUITY_DATA_KEY = "headingContinuityData"
ENABLED_KEY = "enabled"
DEFAULT_ENABLED = False


def _get_base_conf():
	try:
		return config.conf.profiles[0]
	except Exception:
		return config.conf


def _normalize_explicit_boolean(value: object) -> bool:
	if isinstance(value, bool):
		return value
	if isinstance(value, str):
		value = value.strip().lower()
		if value == "true":
			return True
		if value == "false":
			return False
	return False


def _get_data():
	try:
		section = _get_base_conf().get("classicSpeech")
		data = section.get(HEADING_CONTINUITY_DATA_KEY) if hasattr(section, "get") else None
		return data if hasattr(data, "get") else None
	except Exception:
		return None


def _ensure_data():
	base_conf = _get_base_conf()
	section = base_conf.get("classicSpeech") if hasattr(base_conf, "get") else None
	if not hasattr(section, "get"):
		section = {}
		base_conf["classicSpeech"] = section
	data = section.get(HEADING_CONTINUITY_DATA_KEY)
	if not hasattr(data, "get"):
		data = {}
		section[HEADING_CONTINUITY_DATA_KEY] = data
	return data


def get_heading_continuity_enabled() -> bool:
	data = _get_data()
	return _normalize_explicit_boolean(data.get(ENABLED_KEY, DEFAULT_ENABLED) if data is not None else DEFAULT_ENABLED)


def set_heading_continuity_enabled(enabled: object) -> bool:
	normalized = _normalize_explicit_boolean(enabled)
	_ensure_data()[ENABLED_KEY] = normalized
	return normalized


def capture_heading_continuity_state() -> dict:
	"""Capture exact presence/data without materializing ClassicSpeech config."""
	base_conf = _get_base_conf()
	section = base_conf.get("classicSpeech") if hasattr(base_conf, "get") else None
	has_section = hasattr(section, "get")
	has_data = has_section and HEADING_CONTINUITY_DATA_KEY in section
	return {
		"hasClassicSpeechSection": has_section,
		"hasHeadingContinuityData": has_data,
		"headingContinuityData": copy.deepcopy(section.get(HEADING_CONTINUITY_DATA_KEY)) if has_data else None,
	}


def restore_heading_continuity_state(snapshot: object) -> None:
	"""Restore this data exactly, preserving unrelated ClassicSpeech entries."""
	if not hasattr(snapshot, "get") or "hasHeadingContinuityData" not in snapshot:
		return
	base_conf = _get_base_conf()
	section = base_conf.get("classicSpeech") if hasattr(base_conf, "get") else None
	if snapshot.get("hasHeadingContinuityData"):
		if not hasattr(section, "get"):
			section = {}
			base_conf["classicSpeech"] = section
		section[HEADING_CONTINUITY_DATA_KEY] = copy.deepcopy(snapshot.get("headingContinuityData"))
		return
	if hasattr(section, "__delitem__") and HEADING_CONTINUITY_DATA_KEY in section:
		del section[HEADING_CONTINUITY_DATA_KEY]
	if not snapshot.get("hasClassicSpeechSection") and hasattr(section, "__len__") and not section:
		try:
			del base_conf["classicSpeech"]
		except Exception:
			pass
