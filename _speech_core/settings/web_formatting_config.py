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
	if section_name not in config.conf:
		config.conf[section_name] = {}
	return config.conf[section_name]


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


def get_virtual_buffer_setting(key: str):
	if key not in VIRTUAL_BUFFER_KEYS:
		raise KeyError(key)
	section = _ensure_section("virtualBuffers")
	value = section.get(key, copy.deepcopy(VIRTUAL_BUFFER_DEFAULTS[key]))
	return _coerce_virtual_buffer_value(key, value)


def set_virtual_buffer_setting(key: str, value) -> None:
	if key not in VIRTUAL_BUFFER_KEYS:
		raise KeyError(key)
	section = _ensure_section("virtualBuffers")
	section[key] = _coerce_virtual_buffer_value(key, value)


def get_web_document_formatting_setting(key: str):
	if key not in WEB_DOCUMENT_FORMATTING_KEYS:
		raise KeyError(key)
	section = _ensure_section("documentFormatting")
	value = section.get(key, WEB_DOCUMENT_FORMATTING_DEFAULTS[key])
	return _coerce_document_formatting_value(key, value)


def set_web_document_formatting_setting(key: str, value) -> None:
	if key not in WEB_DOCUMENT_FORMATTING_KEYS:
		raise KeyError(key)
	section = _ensure_section("documentFormatting")
	section[key] = _coerce_document_formatting_value(key, value)


def get_annotation_setting(key: str):
	if key not in ANNOTATION_KEYS:
		raise KeyError(key)
	section = _ensure_section("annotations")
	return bool(section.get(key, ANNOTATION_DEFAULTS[key]))


def set_annotation_setting(key: str, value) -> None:
	if key not in ANNOTATION_KEYS:
		raise KeyError(key)
	section = _ensure_section("annotations")
	section[key] = bool(value)


def capture_web_browse_state() -> dict:
	virtual_buffers = _ensure_section("virtualBuffers")
	document_formatting = _ensure_section("documentFormatting")
	annotations = _ensure_section("annotations")
	braille = _ensure_section("braille")
	return {
		"virtualBuffers": {
			key: copy.deepcopy(virtual_buffers.get(key, VIRTUAL_BUFFER_DEFAULTS[key]))
			for key in VIRTUAL_BUFFER_KEYS
		},
		"documentFormatting": {
			key: copy.deepcopy(document_formatting.get(key, WEB_DOCUMENT_FORMATTING_DEFAULTS[key]))
			for key in WEB_DOCUMENT_FORMATTING_KEYS
		},
		"annotations": {
			key: copy.deepcopy(annotations.get(key, ANNOTATION_DEFAULTS[key]))
			for key in ANNOTATION_KEYS
		},
		"braille": {
			key: copy.deepcopy(braille.get(key, FEATURE_FLAG_DEFAULTS[key]))
			for key in BRAILLE_WEB_KEYS
		},
	}


def restore_web_browse_state(state: dict) -> None:
	virtual_buffers = _ensure_section("virtualBuffers")
	document_formatting = _ensure_section("documentFormatting")
	annotations = _ensure_section("annotations")
	braille = _ensure_section("braille")
	for key in VIRTUAL_BUFFER_KEYS:
		if key in state.get("virtualBuffers", {}):
			virtual_buffers[key] = _coerce_virtual_buffer_value(
				key,
				state["virtualBuffers"][key],
			)
	for key in WEB_DOCUMENT_FORMATTING_KEYS:
		if key in state.get("documentFormatting", {}):
			document_formatting[key] = _coerce_document_formatting_value(
				key,
				state["documentFormatting"][key],
			)
	for key in ANNOTATION_KEYS:
		if key in state.get("annotations", {}):
			annotations[key] = bool(state["annotations"][key])
	for key in BRAILLE_WEB_KEYS:
		if key in state.get("braille", {}):
			braille[key] = copy.deepcopy(state["braille"][key])
