"""Native NVDA documentFormatting helpers for ClassicSpeech v3.

These helpers intentionally wrap selected NVDA-native settings only. They do
not add document speech processing or duplicate NVDA's formatting logic.
"""
from __future__ import annotations

import copy

import config
import logHandler

log = logHandler.log

DOCUMENT_READING_PROOFING_KEYS = (
	"reportFontName",
	"reportFontSize",
	"fontAttributeReporting",
	"reportSuperscriptsAndSubscripts",
	"reportEmphasis",
	"reportHighlight",
	"reportStyle",
	"reportColor",
	"reportTransparentColor",
	"reportComments",
	"reportBookmarks",
	"reportRevisions",
	"reportSpellingErrors2",
	"reportPage",
	"reportLineNumber",
	"reportLineIndentation",
	"ignoreBlankLinesForRLI",
	"reportParagraphIndentation",
	"reportLineSpacing",
	"reportAlignment",
	"reportTables",
	"reportTableHeaders",
	"reportTableCellCoords",
	"reportCellBorders",
	"detectFormatAfterCursor",
)


def _enum_choices(enum_name: str, fallback, *, include_members=False):
	"""Return native NVDA enum display strings when available.

	The live add-on runs inside NVDA, where ``config.configFlags`` is present and
	localized. The harness uses a smaller config stub, so fallback strings are kept
	identical to NVDA master rather than simplified.
	"""
	try:
		from config import configFlags

		enum_cls = getattr(configFlags, enum_name)
		members = enum_cls.__members__.values() if include_members else enum_cls
		return tuple((member.displayString, int(member.value)) for member in members)
	except Exception:
		return fallback


def _spelling_error_flags():
	"""Return exactly the native checklist flags for reportSpellingErrors2.

	NVDA master's Document Formatting dialog iterates ReportSpellingErrors for the
	checklist, which yields the real flag entries: Speech, Sound, Braille. Do not
	use ``__members__`` here because that can expose Off/composite aliases such as
	Speech and sound in live NVDA.
	"""
	try:
		from config.configFlags import ReportSpellingErrors

		members = (
			ReportSpellingErrors.SPEECH,
			ReportSpellingErrors.SOUND,
			ReportSpellingErrors.BRAILLE,
		)
		return tuple((member.displayString, int(member.value)) for member in members)
	except Exception:
		return (
			("Speech", 1),
			("Sound", 2),
			("Braille", 4),
		)


FONT_ATTRIBUTE_REPORTING_CHOICES = _enum_choices(
	"OutputMode",
	(
		("Off", 0),
		("Speech", 1),
		("Braille", 2),
		("Speech and braille", 3),
	),
	include_members=True,
)
REPORT_SPELLING_ERRORS_FLAGS = _spelling_error_flags()
REPORT_LINE_INDENTATION_CHOICES = _enum_choices(
	"ReportLineIndentation",
	(
		("Off", 0),
		("Speech", 1),
		("Tones", 2),
		("Both Speech and Tones", 3),
	),
)
REPORT_TABLE_HEADERS_CHOICES = _enum_choices(
	"ReportTableHeaders",
	(
		("Off", 0),
		("Rows and columns", 1),
		("Rows", 2),
		("Columns", 3),
	),
)
REPORT_CELL_BORDERS_CHOICES = _enum_choices(
	"ReportCellBorders",
	(
		("Off", 0),
		("Styles", 1),
		("Both Colors and Styles", 2),
	),
)

# Fallbacks mirror NVDA master source/config/configSpec.py for included keys.
_DEFAULTS = {
	"reportFontName": False,
	"reportFontSize": False,
	"fontAttributeReporting": 0,
	"reportSuperscriptsAndSubscripts": False,
	"reportEmphasis": False,
	"reportHighlight": True,
	"reportStyle": False,
	"reportColor": False,
	"reportTransparentColor": False,
	"reportComments": True,
	"reportBookmarks": True,
	"reportRevisions": True,
	"reportSpellingErrors2": 1,
	"reportPage": True,
	"reportLineNumber": False,
	"reportLineIndentation": 0,
	"ignoreBlankLinesForRLI": False,
	"reportParagraphIndentation": False,
	"reportLineSpacing": False,
	"reportAlignment": False,
	"reportTables": True,
	"reportTableHeaders": 1,
	"reportTableCellCoords": True,
	"reportCellBorders": 0,
	"detectFormatAfterCursor": False,
}
_INTEGER_KEYS = {
	"fontAttributeReporting",
	"reportSpellingErrors2",
	"reportLineIndentation",
	"reportTableHeaders",
	"reportCellBorders",
}
_RANGES = {
	"fontAttributeReporting": (0, 3),
	"reportSpellingErrors2": (0, 7),
	"reportLineIndentation": (0, 3),
	"reportTableHeaders": (0, 3),
	"reportCellBorders": (0, 2),
}


def _ensure_document_formatting_section():
	if "documentFormatting" not in config.conf:
		config.conf["documentFormatting"] = {}
	return config.conf["documentFormatting"]


def _coerce_document_formatting_value(key: str, value):
	if key in _INTEGER_KEYS:
		try:
			coerced = int(value)
		except Exception:
			coerced = int(_DEFAULTS.get(key, 0))
		minimum, maximum = _RANGES[key]
		return max(minimum, min(maximum, coerced))
	return bool(value)


def _get_document_formatting_setting(key: str):
	if key not in DOCUMENT_READING_PROOFING_KEYS:
		raise KeyError(key)
	section = _ensure_document_formatting_section()
	value = section.get(key, _DEFAULTS.get(key, False))
	return _coerce_document_formatting_value(key, value)


def _set_document_formatting_setting(key: str, value) -> None:
	if key not in DOCUMENT_READING_PROOFING_KEYS:
		raise KeyError(key)
	section = _ensure_document_formatting_section()
	section[key] = _coerce_document_formatting_value(key, value)


def _capture_document_formatting_state() -> dict:
	section = _ensure_document_formatting_section()
	return {
		key: copy.deepcopy(section.get(key, _DEFAULTS.get(key, False)))
		for key in DOCUMENT_READING_PROOFING_KEYS
	}


def _restore_document_formatting_state(state: dict) -> None:
	section = _ensure_document_formatting_section()
	for key in DOCUMENT_READING_PROOFING_KEYS:
		if key in state:
			section[key] = _coerce_document_formatting_value(key, state[key])


def _is_ignore_blank_lines_for_rli_enabled() -> bool:
	return _get_document_formatting_setting("reportLineIndentation") != 0


def _is_report_transparent_color_enabled() -> bool:
	return _get_document_formatting_setting("reportColor")
