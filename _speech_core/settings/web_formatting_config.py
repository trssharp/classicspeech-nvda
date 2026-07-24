"""Native NVDA web and browse-mode settings helpers for ClassicSpeech v3.

These helpers wrap native NVDA ``virtualBuffers`` settings plus the
web-oriented ``documentFormatting`` settings that were intentionally excluded
from the Document Reading / Proofing panel. They do not add web speech
processing or browse-mode rewriting.
"""
from __future__ import annotations

import copy

import config
import logHandler

log = logHandler.log

VIRTUAL_BUFFER_KEYS = (
	"maxLineLength",
	"linesPerPage",
	"useScreenLayout",
	"enableOnPageLoad",
	"autoSayAllOnPageLoad",
	"autoPassThroughOnFocusChange",
	"autoPassThroughOnCaretMove",
	"passThroughAudioIndication",
	"trapNonCommandGestures",
	"loadChromiumVBufOnBusyState",
	"browseModeTouchNavigationElements",
)

ANNOTATION_KEYS = (
	"reportDetails",
	"reportAriaDescription",
)

BRAILLE_WEB_KEYS = (
	"reportLiveRegions",
)

WEB_DOCUMENT_FORMATTING_KEYS = (
	"includeLayoutTables",
	"reportHeadings",
	"reportLinks",
	"reportLinkType",
	"reportGraphics",
	"reportLists",
	"reportBlockQuotes",
	"reportGroupings",
	"reportLandmarks",
	"reportArticles",
	"reportFrames",
	"reportFigures",
	"reportClickable",
)

VIRTUAL_BUFFER_DEFAULTS = {
	"maxLineLength": 100,
	"linesPerPage": 25,
	"useScreenLayout": True,
	"enableOnPageLoad": True,
	"autoSayAllOnPageLoad": True,
	"autoPassThroughOnFocusChange": True,
	"autoPassThroughOnCaretMove": False,
	"passThroughAudioIndication": True,
	"trapNonCommandGestures": True,
	"loadChromiumVBufOnBusyState": "DEFAULT",
	"browseModeTouchNavigationElements": ["heading", "link", "formField", "list", "table"],
}

ANNOTATION_DEFAULTS = {
	"reportDetails": True,
	"reportAriaDescription": True,
}

FEATURE_FLAG_DEFAULTS = {
	"loadChromiumVBufOnBusyState": "DEFAULT",
	"reportLiveRegions": "DEFAULT",
}

WEB_DOCUMENT_FORMATTING_DEFAULTS = {
	"includeLayoutTables": False,
	"reportHeadings": True,
	"reportLinks": True,
	"reportLinkType": True,
	"reportGraphics": True,
	"reportLists": True,
	"reportBlockQuotes": True,
	"reportGroupings": True,
	"reportLandmarks": True,
	"reportArticles": False,
	"reportFrames": True,
	"reportFigures": True,
	"reportClickable": True,
}

_INTEGER_VIRTUAL_BUFFER_KEYS = {"maxLineLength", "linesPerPage"}
_LIST_VIRTUAL_BUFFER_KEYS = {"browseModeTouchNavigationElements"}
_FEATURE_FLAG_VIRTUAL_BUFFER_KEYS = {"loadChromiumVBufOnBusyState"}


def _ensure_section(section_name: str):
	section = _get_section(section_name)
	if section is None:
		config.conf[section_name] = {}
		section = config.conf[section_name]
	return section


def _coerce_virtual_buffer_value(key: str, value):
	if key in _INTEGER_VIRTUAL_BUFFER_KEYS:
		try:
			return int(value)
		except Exception:
			return int(VIRTUAL_BUFFER_DEFAULTS[key])
	if key in _LIST_VIRTUAL_BUFFER_KEYS:
		if isinstance(value, (list, tuple, set)):
			return [str(item) for item in value]
		return list(VIRTUAL_BUFFER_DEFAULTS[key])
	if key in _FEATURE_FLAG_VIRTUAL_BUFFER_KEYS:
		return copy.deepcopy(value)
	return bool(value)


def _coerce_document_formatting_value(key: str, value):
	return bool(value)


def _get_section(section_name: str):
	"""Read a config section without materializing a default section."""
	try:
		section = config.conf.get(section_name)
	except Exception:
		return None
	return section if hasattr(section, "get") else None


def get_virtual_buffer_setting(key: str):
	if key not in VIRTUAL_BUFFER_KEYS:
		raise KeyError(key)
	section = _get_section("virtualBuffers")
	value = section.get(key, copy.deepcopy(VIRTUAL_BUFFER_DEFAULTS[key])) if section is not None else copy.deepcopy(VIRTUAL_BUFFER_DEFAULTS[key])
	return _coerce_virtual_buffer_value(key, value)


def set_virtual_buffer_setting(key: str, value) -> None:
	if key not in VIRTUAL_BUFFER_KEYS:
		raise KeyError(key)
	section = _ensure_section("virtualBuffers")
	section[key] = _coerce_virtual_buffer_value(key, value)


def get_web_document_formatting_setting(key: str):
	if key not in WEB_DOCUMENT_FORMATTING_KEYS:
		raise KeyError(key)
	section = _get_section("documentFormatting")
	value = section.get(key, WEB_DOCUMENT_FORMATTING_DEFAULTS[key]) if section is not None else WEB_DOCUMENT_FORMATTING_DEFAULTS[key]
	return _coerce_document_formatting_value(key, value)


def set_web_document_formatting_setting(key: str, value) -> None:
	if key not in WEB_DOCUMENT_FORMATTING_KEYS:
		raise KeyError(key)
	section = _ensure_section("documentFormatting")
	section[key] = _coerce_document_formatting_value(key, value)


def get_annotation_setting(key: str):
	if key not in ANNOTATION_KEYS:
		raise KeyError(key)
	section = _get_section("annotations")
	return bool(section.get(key, ANNOTATION_DEFAULTS[key])) if section is not None else ANNOTATION_DEFAULTS[key]


def set_annotation_setting(key: str, value) -> None:
	if key not in ANNOTATION_KEYS:
		raise KeyError(key)
	section = _ensure_section("annotations")
	section[key] = bool(value)


def _capture_section(section_name: str) -> dict:
	try:
		present = section_name in config.conf
		data = config.conf.get(section_name) if present else None
	except Exception:
		present, data = False, None
	return {"present": present, "data": copy.deepcopy(data)}


def capture_web_browse_state() -> dict:
	"""Capture each complete native section without creating defaults.

	Whole raw sections are retained because this dialog only owns selected keys;
	Cancel must put malformed legacy values and forward-compatible siblings back
	exactly as it found them.
	"""
	return {
		section_name: _capture_section(section_name)
		for section_name in ("virtualBuffers", "documentFormatting", "annotations", "braille")
	}


def restore_web_browse_state(state: dict) -> None:
	"""Restore exact section presence and raw data from a transaction snapshot."""
	if not hasattr(state, "get"):
		return
	for section_name in ("virtualBuffers", "documentFormatting", "annotations", "braille"):
		snapshot = state.get(section_name)
		if not hasattr(snapshot, "get") or "present" not in snapshot:
			continue
		if snapshot.get("present"):
			config.conf[section_name] = copy.deepcopy(snapshot.get("data"))
		else:
			try:
				if section_name in config.conf:
					del config.conf[section_name]
			except Exception:
				pass
