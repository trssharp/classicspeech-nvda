"""Literal text processing helpers for ClassicSpeech v2.

This module is intentionally narrow. It handles transformations of literal
speech text, not object semantics, document roles, web annotations, or number
parsing.
"""
from __future__ import annotations

import re

import config
import logHandler
import speech

from ..hotkey_extractor import parse_shortcut_list, parse_trailing_label_shortcut
from .numbers import NumberProcessor, is_number_processing_active

log = logHandler.log

_TEXT_CONFIG_KEY = "textProcessingData"
_ANNOUNCE_SAY_ALL_NEW_LINES_KEY = "announceNewLinesDuringSayAll"
_NEW_LINE_MESSAGE_KEY = "newLineMessage"
_SPLIT_MIXED_CASE_KEY = "splitMixedCaseWords"
_SUPPRESS_WORD_INTERNAL_DASHES_KEY = "suppressWordInternalDashes"
_REPEATED_CHARACTER_MODE_KEY = "repeatedCharacterMode"
_SPELL_ALPHANUMERIC_DATA_KEY = "spellAlphanumericData"
_DEFAULT_NEW_LINE_MESSAGE = "new line"


def _classic_speech_conf() -> dict:
	try:
		try:
			baseConf = config.conf.profiles[0]
		except Exception:
			baseConf = config.conf
		if "classicSpeech" not in baseConf:
			baseConf["classicSpeech"] = {}
		return baseConf["classicSpeech"]
	except Exception:
		log.debug("ClassicSpeech: failed reading text processor config", exc_info=True)
		return {}


def _text_conf() -> dict:
	conf = _classic_speech_conf()
	try:
		return conf.setdefault(_TEXT_CONFIG_KEY, {})
	except Exception:
		return {}


def get_announce_new_lines_during_say_all() -> bool:
	"""Return whether literal newlines should be announced during Say All."""
	return bool(_text_conf().get(_ANNOUNCE_SAY_ALL_NEW_LINES_KEY, False))


def get_split_mixed_case_words() -> bool:
	"""Return whether CamelCase-like words should be split for speech."""
	return bool(_text_conf().get(_SPLIT_MIXED_CASE_KEY, False))


def get_suppress_word_internal_dashes() -> bool:
	"""Return whether letter-to-letter dashes should be suppressed."""
	return bool(_text_conf().get(_SUPPRESS_WORD_INTERNAL_DASHES_KEY, False))


_REPEATED_CHARACTER_MODES = {"native", "3", "4", "5", "6", "all", "count"}
_SPELL_ALPHANUMERIC_DATA_MODES = {"off", "spell", "phonetic"}


def get_spell_alphanumeric_data_mode() -> str:
	"""Return whether mixed letter/digit tokens should be spelled."""
	mode = str(_text_conf().get(_SPELL_ALPHANUMERIC_DATA_KEY, "off")).strip().lower()
	return mode if mode in _SPELL_ALPHANUMERIC_DATA_MODES else "off"


def get_repeated_character_mode() -> str:
	"""Return JFW-style repeated-character mode for literal text."""
	mode = str(_text_conf().get(_REPEATED_CHARACTER_MODE_KEY, "3")).strip().lower()
	return mode if mode in _REPEATED_CHARACTER_MODES else "3"


def get_new_line_message() -> str:
	"""Return the spoken message inserted for literal newline characters."""
	message = str(_text_conf().get(_NEW_LINE_MESSAGE_KEY, _DEFAULT_NEW_LINE_MESSAGE))
	message = message.strip()
	return message or _DEFAULT_NEW_LINE_MESSAGE


def _is_say_all_running() -> bool:
	try:
		handler = speech.sayAll.SayAllHandler
		return bool(handler.isRunning())
	except Exception:
		return False


_MIXED_CASE_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_WORD_INTERNAL_DASH_RE = re.compile(r"(?<=[^\W\d_])[-‐](?=[^\W\d_])")


_PHONETIC_LETTER_NAMES = {
	"a": "Alpha",
	"b": "Bravo",
	"c": "Charlie",
	"d": "Delta",
	"e": "Echo",
	"f": "Foxtrot",
	"g": "Golf",
	"h": "Hotel",
	"i": "India",
	"j": "Juliet",
	"k": "Kilo",
	"l": "Lima",
	"m": "Mike",
	"n": "November",
	"o": "Oscar",
	"p": "Papa",
	"q": "Quebec",
	"r": "Romeo",
	"s": "Sierra",
	"t": "Tango",
	"u": "Uniform",
	"v": "Victor",
	"w": "Whiskey",
	"x": "X ray",
	"y": "Yankee",
	"z": "Zulu",
}


def _spell_character(character: str, mode: str) -> str:
	if mode == "phonetic" and character.isalpha():
		return _PHONETIC_LETTER_NAMES.get(character.lower(), character)
	return character


def _spell_alphanumeric_data_in_text(text: str, mode: str) -> str:
	"""Spell plain alphanumeric tokens that contain both letters and digits."""
	parts: list[str] = []
	index = 0
	while index < len(text):
		character = text[index]
		if not character.isalnum():
			parts.append(character)
			index += 1
			continue
		end = index + 1
		while end < len(text) and text[end].isalnum():
			end += 1
		token = text[index:end]
		if any(ch.isalpha() for ch in token) and any(ch.isdigit() for ch in token):
			parts.append(" ".join(_spell_character(ch, mode) for ch in token))
		else:
			parts.append(token)
		index = end
	return "".join(parts)


def _split_mixed_case_in_text(text: str) -> str:
	"""Insert spaces at conservative CamelCase boundaries.

	This intentionally only splits lower/digit -> upper boundaries. It leaves
	acronyms such as NVDA and HTTP unchanged.
	"""
	return _MIXED_CASE_BOUNDARY_RE.sub(" ", text)


def _suppress_word_internal_dashes_in_text(text: str) -> str:
	"""Replace dashes between letters with word breaks.

	This intentionally avoids number and serial patterns such as 03-16-00,
	1-800-444-4443, and A-123. Those belong to number/data processors.
	"""
	return _WORD_INTERNAL_DASH_RE.sub(" ", text)


_COUNT_LABELS = {
	" ": "space",
	"!": "exclamation mark",
	"?": "question mark",
	".": "period",
	",": "comma",
	":": "colon",
	";": "semicolon",
	"=": "equals",
	"-": "dash",
	"_": "underscore",
	"*": "asterisk",
	"#": "number sign",
	"/": "slash",
	"\\": "backslash",
}

_PLURAL_LABEL_OVERRIDES = {
	"dash": "dashes",
	"slash": "slashes",
	"backslash": "backslashes",
	"equals": "equals signs",
}


def _pluralize(label: str, count: int) -> str:
	if count == 1:
		return label
	return _PLURAL_LABEL_OVERRIDES.get(label, f"{label}s")


def _looks_like_shortcut_text(text: str) -> bool:
	"""Return True when a text token should stay raw for hotkey extraction."""
	try:
		if parse_shortcut_list(text):
			return True
		_label, shortcut = parse_trailing_label_shortcut(text)
		return bool(shortcut)
	except Exception:
		return False


def _count_label_for_character(character: str) -> str:
	return _COUNT_LABELS.get(character, character)


def _is_repeatable_punctuation(character: str) -> bool:
	"""Return True for punctuation/symbol repeats this feature should handle."""
	if character in {"\n", "\r"}:
		return False
	if character.isspace():
		return False
	return not character.isalnum()


def _is_countable_repeated_character(character: str) -> bool:
	"""Return True for count mode: punctuation/symbols plus indentation spaces."""
	if character in {"\n", "\r"}:
		return False
	if character == " ":
		return True
	if character.isspace():
		return False
	return not character.isalnum()


def _shorten_repeated_punctuation(text: str, limit: int) -> str:
	parts: list[str] = []
	index = 0
	while index < len(text):
		character = text[index]
		end = index + 1
		while end < len(text) and text[end] == character:
			end += 1
		count = end - index
		if count > limit and _is_repeatable_punctuation(character):
			parts.append(character * limit)
		else:
			parts.append(text[index:end])
		index = end
	return "".join(parts)


def _spoken_repeated_punctuation(character: str, count: int) -> str:
	"""Return explicit words for repeated punctuation so synths do not count them."""
	label = _count_label_for_character(character)
	return " ".join(label for _ in range(count))


def _speak_repeated_punctuation(text: str, min_repeat: int, limit: int | None = None) -> list[str]:
	"""Replace repeated punctuation runs with explicit symbol names.

	Some synthesizers collapse raw punctuation runs into counted phrases like
	"4 dash". Emit the symbol name once per spoken character instead, e.g.
	"dash dash dash dash".
	"""
	parts: list[str] = []
	buffer: list[str] = []
	index = 0
	while index < len(text):
		character = text[index]
		end = index + 1
		while end < len(text) and text[end] == character:
			end += 1
		count = end - index
		if count >= min_repeat and _is_repeatable_punctuation(character):
			if buffer:
				parts.append("".join(buffer))
				buffer = []
			spoken_count = min(count, limit) if limit is not None else count
			parts.append(_spoken_repeated_punctuation(character, spoken_count))
		else:
			buffer.append(text[index:end])
		index = end
	if buffer:
		parts.append("".join(buffer))
	return parts or [text]


def _filter_repeated_characters_in_text(text: str, mode: str) -> list[str]:
	"""Apply JFW-style repeated punctuation handling to one text token."""
	if not text or mode == "native":
		return [text]
	if mode == "all":
		return _speak_repeated_punctuation(text, min_repeat=2)
	if mode == "3":
		# Mode 3 can safely use raw punctuation: synths tested by Tim speak it as
		# three individual symbols.
		return [_shorten_repeated_punctuation(text, 3)]
	if mode in {"4", "5", "6"}:
		# Four or more raw punctuation characters may be collapsed by synthesizers
		# as "4 dash" etc. Emit explicit labels so the user hears each character.
		return _speak_repeated_punctuation(text, min_repeat=4, limit=int(mode))
	if mode != "count":
		return [text]

	parts: list[str] = []
	buffer: list[str] = []
	index = 0
	while index < len(text):
		character = text[index]
		end = index + 1
		while end < len(text) and text[end] == character:
			end += 1
		count = end - index
		if count > 1 and _is_countable_repeated_character(character):
			if buffer:
				parts.append("".join(buffer))
				buffer = []
			label = _count_label_for_character(character)
			parts.append(f"{count} {_pluralize(label, count)}")
		else:
			buffer.append(text[index:end])
		index = end
	if buffer:
		parts.append("".join(buffer))
	return parts or [text]


def _expand_newlines_in_text(text: str, message: str) -> list[str]:
	"""Split one string token and insert message for each newline character."""
	if "\n" not in text and "\r" not in text:
		return [text]

	normalized = text.replace("\r\n", "\n").replace("\r", "\n")
	parts: list[str] = []
	segments = normalized.split("\n")
	for index, segment in enumerate(segments):
		if segment:
			parts.append(segment)
		if index < len(segments) - 1:
			parts.append(message)
	return parts


class TextProcessor:
	"""Small literal text processor used before semantic classification."""

	def get_repeated_character_mode(self) -> str:
		"""Expose the active repeated-character mode for diagnostics."""
		return get_repeated_character_mode()

	def process_literal_sequence(self, speech_sequence, allow_number_modes: bool = True):
		"""Return a processed copy of a literal speech sequence.

		The first v2 feature is intentionally tiny: if Say All is running and a
		string token contains literal newline characters, insert a configurable
		"new line" announcement. Normal caret/review line navigation remains
		unchanged because this only runs when Say All is active.
		"""
		spell_alphanumeric_mode = get_spell_alphanumeric_data_mode()
		spell_alphanumeric = spell_alphanumeric_mode != "off"
		process_numbers = is_number_processing_active()
		suppress_word_internal_dashes = get_suppress_word_internal_dashes()
		split_mixed_case = get_split_mixed_case_words()
		repeated_mode = get_repeated_character_mode()
		filter_repeated = repeated_mode != "native"
		announce_newlines = (
			get_announce_new_lines_during_say_all()
			and _is_say_all_running()
		)
		if not spell_alphanumeric and not process_numbers and not suppress_word_internal_dashes and not split_mixed_case and not filter_repeated and not announce_newlines:
			return list(speech_sequence)

		number_processor = NumberProcessor() if process_numbers else None
		message = get_new_line_message()
		processed = []

		for item in speech_sequence:
			if isinstance(item, str):
				shortcut_like = _looks_like_shortcut_text(item)
				text = item
				if not shortcut_like:
					text = _spell_alphanumeric_data_in_text(text, spell_alphanumeric_mode) if spell_alphanumeric else text
					text = number_processor.process_literal_sequence([text], allow_number_modes=allow_number_modes)[0] if number_processor else text
					text = _suppress_word_internal_dashes_in_text(text) if suppress_word_internal_dashes else text
					text = _split_mixed_case_in_text(text) if split_mixed_case else text
				text_parts = _filter_repeated_characters_in_text(text, repeated_mode) if filter_repeated else [text]
				for text_part in text_parts:
					if announce_newlines:
						processed.extend(_expand_newlines_in_text(text_part, message))
					else:
						processed.append(text_part)
			else:
				processed.append(item)
		return processed
