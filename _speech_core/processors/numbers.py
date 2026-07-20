"""Opt-in number processing helpers for ClassicSpeech v2.

This module intentionally handles only conservative, standalone integer
strings. Currency, dates, times, phone-like strings, fractions, and
alphanumeric data are left untouched so native NVDA/synth behavior remains the
safe default.
"""
from __future__ import annotations

import calendar
import re

import config
import logHandler

log = logHandler.log

_NUMBER_CONFIG_KEY = "numberProcessingData"
_NUMBER_PROCESSING_MODE_KEY = "numberProcessingMode"
_SINGLE_DIGITS_THRESHOLD_KEY = "singleDigitsIfNumberContains"
_PHONE_NUMBER_PROCESSING_KEY = "phoneNumberProcessing"
_FRIENDLY_TOLL_FREE_PREFIXES_KEY = "friendlyTollFreePrefixes"
_CURRENCY_PROCESSING_KEY = "currencyProcessing"
_ORDINAL_PROCESSING_KEY = "ordinalProcessing"
_NUMERIC_DATE_PROCESSING_KEY = "numericDateProcessing"
_NUMERIC_DATE_FORMAT_KEY = "numericDateFormat"
_RECOGNIZE_ISO_DATES_KEY = "recognizeIsoDates"
_USE_WINDOWS_DATE_FORMAT_KEY = "useWindowsDateFormat"
THRESHOLD_SYNTHESIZER = "synthesizer"
SINGLE_DIGITS_THRESHOLDS = {THRESHOLD_SYNTHESIZER, "5", "6", "7", "8"}
PHONE_NATIVE = "native"
PHONE_GROUPED_DIGITS = "groupedDigits"
PHONE_NUMBER_PROCESSING_MODES = {PHONE_NATIVE, PHONE_GROUPED_DIGITS}
CURRENCY_NATIVE = "native"
CURRENCY_DOLLARS_AND_CENTS = "dollarsAndCents"
CURRENCY_PROCESSING_MODES = {CURRENCY_NATIVE, CURRENCY_DOLLARS_AND_CENTS}
ORDINAL_NATIVE = "native"
ORDINAL_WORDS = "words"
ORDINAL_PROCESSING_MODES = {ORDINAL_NATIVE, ORDINAL_WORDS}
MODE_SYNTHESIZER = "synthesizer"
MODE_SINGLE_DIGITS = "singleDigits"
MODE_PAIRS = "pairs"
MODE_FULL_NUMBERS = "fullNumbers"
NUMBER_PROCESSING_MODES = {
	MODE_SYNTHESIZER,
	MODE_SINGLE_DIGITS,
	MODE_PAIRS,
	MODE_FULL_NUMBERS,
}
DATE_NATIVE = "native"
DATE_SOME = "some"
DATE_FULL = "full"
NUMERIC_DATE_PROCESSING_MODES = {DATE_NATIVE, DATE_SOME, DATE_FULL}
DATE_FORMAT_MDY = "mdy"
DATE_FORMAT_DMY = "dmy"
DATE_FORMAT_YMD = "ymd"
NUMERIC_DATE_FORMATS = {DATE_FORMAT_MDY, DATE_FORMAT_DMY, DATE_FORMAT_YMD}

_DIGIT_WORDS = [
	"zero",
	"one",
	"two",
	"three",
	"four",
	"five",
	"six",
	"seven",
	"eight",
	"nine",
]
_TEENS = {
	10: "ten",
	11: "eleven",
	12: "twelve",
	13: "thirteen",
	14: "fourteen",
	15: "fifteen",
	16: "sixteen",
	17: "seventeen",
	18: "eighteen",
	19: "nineteen",
}
_TENS = {
	20: "twenty",
	30: "thirty",
	40: "forty",
	50: "fifty",
	60: "sixty",
	70: "seventy",
	80: "eighty",
	90: "ninety",
}
_TOLL_FREE_PREFIX_WORDS = {
	"800": "eight hundred",
	"888": "eight eighty eight",
	"877": "eight seventy seven",
	"866": "eight sixty six",
	"855": "eight fifty five",
	"844": "eight forty four",
	"833": "eight thirty three",
}
_NUMBER_TOKEN_RE = re.compile(r"\d+(?:,\d+)*")
_ORDINAL_TOKEN_RE = re.compile(r"(?<![\w/-])(\d+(?:,\d+)*)(st|nd|rd|th)(?![\w/-])", re.IGNORECASE)
_PAREN_PHONE_RE = re.compile(r"(?<![\w/-])\((\d{3})\)\s*(\d{3})[- ]?(\d{4})(?![\w/-])")
_SEPARATED_PHONE_RE = re.compile(r"(?<![\w/-])(?:(1)[- .])?(\d{3})[- .](\d{3})[- .](\d{4})(?![\w/-])")
_TEN_DIGIT_PHONE_RE = re.compile(r"(?<![\w/-])(\d{3})(\d{3})(\d{4})(?![\w/-])")
_DOLLAR_AMOUNT_RE = re.compile(r"(?<![\w/-])\$((?:\d{1,3}(?:,\d{3})+)|\d+)(?:\.(\d{2}))?(?![\w/.,-])")
_FULL_DATE_RE = re.compile(r"(?<![\w/-])(\d{1,2})([-/])(\d{1,2})\2(\d{2}|\d{4})(?![\w/-])")
_YMD_FULL_DATE_RE = re.compile(r"(?<![\w/-])(\d{4})([-/])(\d{1,2})\2(\d{1,2})(?![\w/-])")
_PARTIAL_DATE_RE = re.compile(r"(?<![\w/-])(\d{1,2})([-/])(\d{1,2})(?![\w/-])")
_MAX_FULL_NUMBER_DIGITS = 18
_SCALE_WORDS = ["", "thousand", "million", "billion", "trillion", "quadrillion"]
_CURRENCY_PREFIXES = "$€£¥₹¢"
_PROTECTED_ADJACENT_CHARS = set("-:/.\\") | set(_CURRENCY_PREFIXES)
_MONTH_NAMES = [
	"",
	"January",
	"February",
	"March",
	"April",
	"May",
	"June",
	"July",
	"August",
	"September",
	"October",
	"November",
	"December",
]
_ORDINAL_DAYS = {
	1: "first",
	2: "second",
	3: "third",
	4: "fourth",
	5: "fifth",
	6: "sixth",
	7: "seventh",
	8: "eighth",
	9: "ninth",
	10: "tenth",
	11: "eleventh",
	12: "twelfth",
	13: "thirteenth",
	14: "fourteenth",
	15: "fifteenth",
	16: "sixteenth",
	17: "seventeenth",
	18: "eighteenth",
	19: "nineteenth",
	20: "twentieth",
	21: "twenty first",
	22: "twenty second",
	23: "twenty third",
	24: "twenty fourth",
	25: "twenty fifth",
	26: "twenty sixth",
	27: "twenty seventh",
	28: "twenty eighth",
	29: "twenty ninth",
	30: "thirtieth",
	31: "thirty first",
}


def _classic_speech_conf() -> dict:
	try:
		try:
			base_conf = config.conf.profiles[0]
		except Exception:
			base_conf = config.conf
		if "classicSpeech" not in base_conf:
			base_conf["classicSpeech"] = {}
		return base_conf["classicSpeech"]
	except Exception:
		log.debug("ClassicSpeech: failed reading number processor config", exc_info=True)
		return {}


def _number_conf() -> dict:
	conf = _classic_speech_conf()
	try:
		return conf.setdefault(_NUMBER_CONFIG_KEY, {})
	except Exception:
		return {}


def get_number_processing_mode() -> str:
	"""Return the active JFW-style number processing mode."""
	mode = str(_number_conf().get(_NUMBER_PROCESSING_MODE_KEY, MODE_SYNTHESIZER)).strip()
	return mode if mode in NUMBER_PROCESSING_MODES else MODE_SYNTHESIZER


def get_single_digits_threshold() -> str:
	"""Return the active long-number digit-spelling threshold."""
	threshold = str(_number_conf().get(_SINGLE_DIGITS_THRESHOLD_KEY, THRESHOLD_SYNTHESIZER)).strip()
	return threshold if threshold in SINGLE_DIGITS_THRESHOLDS else THRESHOLD_SYNTHESIZER


def get_phone_number_processing_mode() -> str:
	"""Return the active phone number processing mode."""
	mode = str(_number_conf().get(_PHONE_NUMBER_PROCESSING_KEY, PHONE_NATIVE)).strip()
	return mode if mode in PHONE_NUMBER_PROCESSING_MODES else PHONE_NATIVE


def get_friendly_toll_free_prefixes() -> bool:
	"""Return whether toll-free prefixes should be spoken in friendly form."""
	return bool(_number_conf().get(_FRIENDLY_TOLL_FREE_PREFIXES_KEY, True))


def get_currency_processing_mode() -> str:
	"""Return the active currency processing mode."""
	mode = str(_number_conf().get(_CURRENCY_PROCESSING_KEY, CURRENCY_NATIVE)).strip()
	return mode if mode in CURRENCY_PROCESSING_MODES else CURRENCY_NATIVE


def get_ordinal_processing_mode() -> str:
	"""Return the active ordinal number processing mode."""
	mode = str(_number_conf().get(_ORDINAL_PROCESSING_KEY, ORDINAL_NATIVE)).strip()
	return mode if mode in ORDINAL_PROCESSING_MODES else ORDINAL_NATIVE


def get_numeric_date_processing_mode() -> str:
	"""Return the active numeric date processing mode."""
	mode = str(_number_conf().get(_NUMERIC_DATE_PROCESSING_KEY, DATE_NATIVE)).strip()
	return mode if mode in NUMERIC_DATE_PROCESSING_MODES else DATE_NATIVE


def get_numeric_date_format() -> str:
	"""Return the explicit fallback format for numeric dates."""
	date_format = str(_number_conf().get(_NUMERIC_DATE_FORMAT_KEY, DATE_FORMAT_MDY)).strip().lower()
	return date_format if date_format in NUMERIC_DATE_FORMATS else DATE_FORMAT_MDY


def get_recognize_iso_dates() -> bool:
	"""Return whether strict ISO-style year-first dates should be recognized."""
	return bool(_number_conf().get(_RECOGNIZE_ISO_DATES_KEY, True))


def get_use_windows_date_format() -> bool:
	"""Return whether Windows short-date order should be tried first."""
	return bool(_number_conf().get(_USE_WINDOWS_DATE_FORMAT_KEY, False))


def is_number_processing_active() -> bool:
	return (
		get_number_processing_mode() != MODE_SYNTHESIZER
		or get_single_digits_threshold() != THRESHOLD_SYNTHESIZER
		or get_phone_number_processing_mode() != PHONE_NATIVE
		or get_currency_processing_mode() != CURRENCY_NATIVE
		or get_ordinal_processing_mode() != ORDINAL_NATIVE
		or get_numeric_date_processing_mode() != DATE_NATIVE
	)


def _is_position_count_token(text: str, match: re.Match[str]) -> bool:
	"""Return True for numbers that are part of an NVDA position string.

	Examples: ``1 of 10``, ``Verbosity 1 of 10``, ``1,234 of 5,678``.
	These must stay numeric so later semantic position filtering can still
	recognize and suppress repeated positions when requested.
	"""
	start, end = match.span()
	if re.match(r"\s+of\s+\d", text[end:]):
		return True
	if re.search(r"\d(?:,\d+)*\s+of\s+$", text[:start]):
		return True
	return False


def _is_protected_integer_match(text: str, match: re.Match[str]) -> bool:
	"""Return True if the integer is part of a format we must not rewrite."""
	if _is_position_count_token(text, match):
		return True
	start, end = match.span()
	previous_char = text[start - 1] if start > 0 else ""
	next_char = text[end] if end < len(text) else ""
	if previous_char and (previous_char.isalnum() or previous_char in _PROTECTED_ADJACENT_CHARS):
		return True
	if next_char and (next_char.isalnum() or next_char in _PROTECTED_ADJACENT_CHARS):
		return True
	if previous_char == "," and start > 1 and text[start - 2].isdigit():
		return True
	if next_char == "," and end + 1 < len(text) and text[end + 1].isdigit():
		return True
	return False


def _normalize_number_token(number_text: str) -> str:
	return number_text.replace(",", "")


def _is_supported_whole_number_token(number_text: str) -> bool:
	"""Return True when a token is safe to rewrite as a whole number."""
	normalized = _normalize_number_token(number_text)
	if not normalized.isdigit():
		return False
	if len(normalized) > _MAX_FULL_NUMBER_DIGITS:
		return False
	if len(normalized) > 1 and normalized.startswith("0"):
		return False
	return True


def _spell_single_digits(number_text: str) -> str:
	normalized = _normalize_number_token(number_text)
	return " ".join(_DIGIT_WORDS[int(character)] for character in normalized)


def _spell_digit_group(digits: str) -> str:
	return " ".join(_DIGIT_WORDS[int(character)] for character in digits)


def _format_phone_groups(groups: tuple[str, ...]) -> str:
	if get_friendly_toll_free_prefixes():
		leading_one = len(groups) == 4 and groups[0] == "1"
		area_index = 1 if leading_one else 0
		area = groups[area_index] if len(groups) > area_index else ""
		if area in _TOLL_FREE_PREFIX_WORDS:
			prefix = _TOLL_FREE_PREFIX_WORDS[area]
			if leading_one:
				prefix = "one " + prefix
			return ", ".join([prefix] + [_spell_digit_group(group) for group in groups[area_index + 1:]])
	return ", ".join(_spell_digit_group(group) for group in groups if group)


def _replace_phone_match(match: re.Match[str]) -> str:
	return _format_phone_groups(tuple(group for group in match.groups() if group))


def _process_phone_numbers(text: str, mode: str) -> str:
	if mode == PHONE_NATIVE:
		return text
	text = _PAREN_PHONE_RE.sub(_replace_phone_match, text)
	text = _SEPARATED_PHONE_RE.sub(_replace_phone_match, text)
	return _TEN_DIGIT_PHONE_RE.sub(_replace_phone_match, text)


def _format_dollars_and_cents(match: re.Match[str]) -> str:
	dollars = int(_normalize_number_token(match.group(1)))
	cents_text = match.group(2)
	cents = int(cents_text) if cents_text is not None else 0
	parts: list[str] = []
	if dollars:
		parts.extend([_spell_full_number(str(dollars)), "dollar" if dollars == 1 else "dollars"])
	if cents:
		cent_prefix = "and " if dollars else ""
		parts.extend([cent_prefix + _spell_under_hundred(cents), "cent" if cents == 1 else "cents"])
	if not parts:
		return "zero dollars"
	return " ".join(parts)


def _process_currency(text: str, mode: str) -> str:
	if mode == CURRENCY_NATIVE:
		return text
	return _DOLLAR_AMOUNT_RE.sub(_format_dollars_and_cents, text)


def _spell_under_hundred(value: int) -> str:
	if value < 10:
		return _DIGIT_WORDS[value]
	if value < 20:
		return _TEENS[value]
	tens, ones = divmod(value, 10)
	words = [_TENS[tens * 10]]
	if ones:
		words.append(_DIGIT_WORDS[ones])
	return " ".join(words)


def _spell_under_thousand(value: int) -> str:
	if value < 100:
		return _spell_under_hundred(value)
	hundreds, remainder = divmod(value, 100)
	words = [_DIGIT_WORDS[hundreds], "hundred"]
	if remainder:
		words.append(_spell_under_hundred(remainder))
	return " ".join(words)


def _spell_full_number(number_text: str) -> str:
	normalized = _normalize_number_token(number_text)
	value = int(normalized)
	if value < 1000:
		return _spell_under_thousand(value)

	chunks: list[int] = []
	remaining = value
	while remaining:
		remaining, chunk = divmod(remaining, 1000)
		chunks.append(chunk)

	words: list[str] = []
	for scale_index in range(len(chunks) - 1, -1, -1):
		chunk = chunks[scale_index]
		if not chunk:
			continue
		words.append(_spell_under_thousand(chunk))
		scale_word = _SCALE_WORDS[scale_index]
		if scale_word:
			words.append(scale_word)
	return " ".join(words)


_ORDINAL_WORD_OVERRIDES = {
	"zero": "zeroth",
	"one": "first",
	"two": "second",
	"three": "third",
	"four": "fourth",
	"five": "fifth",
	"six": "sixth",
	"seven": "seventh",
	"eight": "eighth",
	"nine": "ninth",
	"ten": "tenth",
	"eleven": "eleventh",
	"twelve": "twelfth",
	"thirteen": "thirteenth",
	"fourteen": "fourteenth",
	"fifteen": "fifteenth",
	"sixteen": "sixteenth",
	"seventeen": "seventeenth",
	"eighteen": "eighteenth",
	"nineteen": "nineteenth",
	"twenty": "twentieth",
	"thirty": "thirtieth",
	"forty": "fortieth",
	"fifty": "fiftieth",
	"sixty": "sixtieth",
	"seventy": "seventieth",
	"eighty": "eightieth",
	"ninety": "ninetieth",
	"hundred": "hundredth",
	"thousand": "thousandth",
	"million": "millionth",
	"billion": "billionth",
	"trillion": "trillionth",
	"quadrillion": "quadrillionth",
}


def _expected_ordinal_suffix(value: int) -> str:
	if 10 <= value % 100 <= 20:
		return "th"
	return {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")


def _spell_full_ordinal(number_text: str) -> str:
	normalized = _normalize_number_token(number_text)
	if not _is_supported_whole_number_token(number_text):
		return number_text
	cardinal = _spell_full_number(normalized)
	words = cardinal.split()
	if not words:
		return number_text
	words[-1] = _ORDINAL_WORD_OVERRIDES.get(words[-1], words[-1] + "th")
	return " ".join(words)


def _replace_ordinal_match(match: re.Match[str]) -> str:
	number_text = match.group(1)
	suffix = match.group(2).lower()
	if not _is_supported_whole_number_token(number_text):
		return match.group()
	value = int(_normalize_number_token(number_text))
	if suffix != _expected_ordinal_suffix(value):
		return match.group()
	return _spell_full_ordinal(number_text)


def _process_ordinals(text: str, mode: str) -> str:
	if mode == ORDINAL_NATIVE:
		return text
	return _ORDINAL_TOKEN_RE.sub(_replace_ordinal_match, text)


def _spell_pair(pair_text: str):
	if pair_text.startswith("0"):
		return "oh " + _DIGIT_WORDS[int(pair_text[1])]
	return _spell_under_hundred(int(pair_text))


def _spell_pairs(number_text: str) -> str:
	normalized = _normalize_number_token(number_text)
	if len(normalized) == 1:
		return _DIGIT_WORDS[int(normalized)]
	parts: list[str] = []
	index = 0
	if len(normalized) % 2:
		parts.append(_DIGIT_WORDS[int(normalized[0])])
		index = 1
	while index < len(normalized):
		parts.append(_spell_pair(normalized[index:index + 2]))
		index += 2
	return " ".join(parts)


def _date_year_value(year_text: str) -> int:
	value = int(year_text)
	if len(year_text) == 2:
		return 2000 + value if value <= 68 else 1900 + value
	return value


def _is_valid_month_day_year(month: int, day: int, year: int) -> bool:
	if month < 1 or month > 12:
		return False
	try:
		return 1 <= day <= calendar.monthrange(year, month)[1]
	except Exception:
		return False


def _date_parts(first: str, second: str, date_format: str) -> tuple[int, int]:
	if date_format == DATE_FORMAT_DMY:
		return int(second), int(first)
	return int(first), int(second)


def _windows_date_order_from_pattern(pattern: str) -> str | None:
	"""Return a supported order from a Windows short-date pattern."""
	fields = []
	for field in re.findall(r"[dMy]+", pattern or "", re.IGNORECASE):
		kind = field[0].lower()
		if kind in {"m", "d", "y"} and (not fields or fields[-1] != kind):
			fields.append(kind)
	if fields[:3] == ["m", "d", "y"]:
		return DATE_FORMAT_MDY
	if fields[:3] == ["d", "m", "y"]:
		return DATE_FORMAT_DMY
	if fields[:3] == ["y", "m", "d"]:
		return DATE_FORMAT_YMD
	return None


def _get_windows_short_date_pattern() -> str | None:
	"""Read the current Windows user's short date pattern, if available."""
	try:
		import ctypes
		from ctypes import wintypes

		get_locale_info = ctypes.WinDLL("kernel32", use_last_error=True).GetLocaleInfoEx
		get_locale_info.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPWSTR, ctypes.c_int]
		get_locale_info.restype = ctypes.c_int
		buffer = ctypes.create_unicode_buffer(100)
		if get_locale_info(None, 0x0000001F, buffer, len(buffer)):
			return buffer.value
	except Exception:
		log.debug("ClassicSpeech: failed reading Windows short date format", exc_info=True)
	return None


def _effective_numeric_date_format() -> str:
	fallback = get_numeric_date_format()
	if not get_use_windows_date_format():
		return fallback
	windows_format = _windows_date_order_from_pattern(_get_windows_short_date_pattern() or "")
	return windows_format or fallback


def _spell_year(year: int) -> str:
	if year == 2000:
		return "two thousand"
	if 2001 <= year <= 2009:
		return "two thousand " + _spell_under_hundred(year % 100)
	if 2010 <= year <= 2099:
		return "twenty " + _spell_under_hundred(year % 100)
	if 1900 <= year <= 1999:
		remainder = year % 100
		return "nineteen hundred" if remainder == 0 else "nineteen " + _spell_under_hundred(remainder)
	return _spell_full_number(str(year))


def _spell_month_day(month: int, day: int) -> str:
	return f"{_MONTH_NAMES[month]} {_ORDINAL_DAYS[day]}"


def _replace_full_date(match: re.Match[str], date_format: str) -> str:
	month, day = _date_parts(match.group(1), match.group(3), date_format)
	year = _date_year_value(match.group(4))
	if not _is_valid_month_day_year(month, day, year):
		return match.group()
	return f"{_spell_month_day(month, day)}, {_spell_year(year)}"


def _replace_year_month_day_date(match: re.Match[str]) -> str:
	year = int(match.group(1))
	month = int(match.group(3))
	day = int(match.group(4))
	if not _is_valid_month_day_year(month, day, year):
		return match.group()
	return f"{_spell_month_day(month, day)}, {_spell_year(year)}"


def _replace_partial_date(match: re.Match[str], date_format: str) -> str:
	month, day = _date_parts(match.group(1), match.group(3), date_format)
	# Use a leap year so 2/29 can be spoken in Full mode; full dates still use
	# their actual year for validation.
	if not _is_valid_month_day_year(month, day, 2000):
		return match.group()
	return _spell_month_day(month, day)


def _process_numeric_dates(text: str, mode: str) -> str:
	if mode == DATE_NATIVE:
		return text
	date_format = _effective_numeric_date_format()
	if get_recognize_iso_dates() and date_format != DATE_FORMAT_YMD:
		text = _YMD_FULL_DATE_RE.sub(_replace_year_month_day_date, text)
	if date_format == DATE_FORMAT_YMD:
		return _YMD_FULL_DATE_RE.sub(_replace_year_month_day_date, text)
	text = _FULL_DATE_RE.sub(lambda match: _replace_full_date(match, date_format), text)
	if mode == DATE_FULL:
		text = _PARTIAL_DATE_RE.sub(lambda match: _replace_partial_date(match, date_format), text)
	return text


def _threshold_requires_single_digits(number_text: str, threshold: str) -> bool:
	if threshold == THRESHOLD_SYNTHESIZER:
		return False
	return len(_normalize_number_token(number_text)) >= int(threshold)


def _convert_integer(number_text: str, mode: str, threshold: str) -> str:
	if not _is_supported_whole_number_token(number_text):
		return number_text
	if _threshold_requires_single_digits(number_text, threshold):
		return _spell_single_digits(number_text)
	if mode == MODE_SINGLE_DIGITS:
		return _spell_single_digits(number_text)
	if mode == MODE_PAIRS:
		return _spell_pairs(number_text)
	if mode == MODE_FULL_NUMBERS:
		return _spell_full_number(number_text)
	return number_text


def process_number_text(text: str, allow_number_modes: bool = True) -> str:
	"""Apply opt-in number, phone, currency, and numeric date processing to literal strings."""
	mode = get_number_processing_mode() if allow_number_modes else MODE_SYNTHESIZER
	threshold = get_single_digits_threshold()
	phone_mode = get_phone_number_processing_mode()
	currency_mode = get_currency_processing_mode()
	ordinal_mode = get_ordinal_processing_mode() if allow_number_modes else ORDINAL_NATIVE
	date_mode = get_numeric_date_processing_mode()
	if (
		mode == MODE_SYNTHESIZER
		and threshold == THRESHOLD_SYNTHESIZER
		and phone_mode == PHONE_NATIVE
		and currency_mode == CURRENCY_NATIVE
		and ordinal_mode == ORDINAL_NATIVE
		and date_mode == DATE_NATIVE
	) or not text:
		return text
	text = _process_phone_numbers(text, phone_mode)
	text = _process_currency(text, currency_mode)
	text = _process_numeric_dates(text, date_mode)
	text = _process_ordinals(text, ordinal_mode)
	if mode == MODE_SYNTHESIZER and threshold == THRESHOLD_SYNTHESIZER:
		return text

	parts: list[str] = []
	last_end = 0
	for match in _NUMBER_TOKEN_RE.finditer(text):
		parts.append(text[last_end:match.start()])
		if _is_protected_integer_match(text, match):
			parts.append(match.group())
		else:
			parts.append(_convert_integer(match.group(), mode, threshold))
		last_end = match.end()
	parts.append(text[last_end:])
	return "".join(parts)


class NumberProcessor:
	"""Conservative opt-in number processor for literal speech text."""

	def process_literal_sequence(self, speech_sequence, allow_number_modes: bool = True):
		if not is_number_processing_active():
			return list(speech_sequence)
		processed = []
		for item in speech_sequence:
			processed.append(
				process_number_text(item, allow_number_modes=allow_number_modes)
				if isinstance(item, str)
				else item
			)
		return processed
