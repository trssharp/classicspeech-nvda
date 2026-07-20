"""Number-processing settings helpers for ClassicSpeech."""

from .config_core import _ensure_classic_speech_section

NUMBER_PROCESSING_MODE_SYNTHESIZER = "synthesizer"
NUMBER_PROCESSING_MODE_SINGLE_DIGITS = "singleDigits"
NUMBER_PROCESSING_MODE_PAIRS = "pairs"
NUMBER_PROCESSING_MODE_FULL_NUMBERS = "fullNumbers"
NUMBER_PROCESSING_MODES = {
	NUMBER_PROCESSING_MODE_SYNTHESIZER,
	NUMBER_PROCESSING_MODE_SINGLE_DIGITS,
	NUMBER_PROCESSING_MODE_PAIRS,
	NUMBER_PROCESSING_MODE_FULL_NUMBERS,
}
SINGLE_DIGITS_THRESHOLD_SYNTHESIZER = "synthesizer"
SINGLE_DIGITS_THRESHOLDS = {
	SINGLE_DIGITS_THRESHOLD_SYNTHESIZER,
	"5",
	"6",
	"7",
	"8",
}
PHONE_NUMBER_PROCESSING_NATIVE = "native"
PHONE_NUMBER_PROCESSING_GROUPED_DIGITS = "groupedDigits"
PHONE_NUMBER_PROCESSING_MODES = {
	PHONE_NUMBER_PROCESSING_NATIVE,
	PHONE_NUMBER_PROCESSING_GROUPED_DIGITS,
}
CURRENCY_PROCESSING_NATIVE = "native"
CURRENCY_PROCESSING_DOLLARS_AND_CENTS = "dollarsAndCents"
CURRENCY_PROCESSING_MODES = {
	CURRENCY_PROCESSING_NATIVE,
	CURRENCY_PROCESSING_DOLLARS_AND_CENTS,
}
ORDINAL_PROCESSING_NATIVE = "native"
ORDINAL_PROCESSING_WORDS = "words"
ORDINAL_PROCESSING_MODES = {
	ORDINAL_PROCESSING_NATIVE,
	ORDINAL_PROCESSING_WORDS,
}
NUMERIC_DATE_PROCESSING_NATIVE = "native"
NUMERIC_DATE_PROCESSING_SOME = "some"
NUMERIC_DATE_PROCESSING_FULL = "full"
NUMERIC_DATE_PROCESSING_MODES = {
	NUMERIC_DATE_PROCESSING_NATIVE,
	NUMERIC_DATE_PROCESSING_SOME,
	NUMERIC_DATE_PROCESSING_FULL,
}
NUMERIC_DATE_FORMAT_MDY = "mdy"
NUMERIC_DATE_FORMAT_DMY = "dmy"
NUMERIC_DATE_FORMAT_YMD = "ymd"
NUMERIC_DATE_FORMATS = {
	NUMERIC_DATE_FORMAT_MDY,
	NUMERIC_DATE_FORMAT_DMY,
	NUMERIC_DATE_FORMAT_YMD,
}


def _ensure_number_processing_section():
	conf = _ensure_classic_speech_section()
	section = conf.get("numberProcessingData")
	if not isinstance(section, dict):
		section = {}
		conf["numberProcessingData"] = section
	return section


def _get_number_processing_mode():
	section = _ensure_number_processing_section()
	mode = str(section.get("numberProcessingMode", NUMBER_PROCESSING_MODE_SYNTHESIZER)).strip()
	return mode if mode in NUMBER_PROCESSING_MODES else NUMBER_PROCESSING_MODE_SYNTHESIZER


def get_number_processing_mode():
	return _get_number_processing_mode()


def _set_number_processing_mode(mode):
	section = _ensure_number_processing_section()
	mode = str(mode or NUMBER_PROCESSING_MODE_SYNTHESIZER).strip()
	if mode not in NUMBER_PROCESSING_MODES:
		mode = NUMBER_PROCESSING_MODE_SYNTHESIZER
	section["numberProcessingMode"] = mode
	return mode


def _get_single_digits_threshold():
	section = _ensure_number_processing_section()
	threshold = str(section.get("singleDigitsIfNumberContains", SINGLE_DIGITS_THRESHOLD_SYNTHESIZER)).strip()
	return threshold if threshold in SINGLE_DIGITS_THRESHOLDS else SINGLE_DIGITS_THRESHOLD_SYNTHESIZER


def get_single_digits_threshold():
	return _get_single_digits_threshold()


def _set_single_digits_threshold(threshold):
	section = _ensure_number_processing_section()
	threshold = str(threshold or SINGLE_DIGITS_THRESHOLD_SYNTHESIZER).strip()
	if threshold not in SINGLE_DIGITS_THRESHOLDS:
		threshold = SINGLE_DIGITS_THRESHOLD_SYNTHESIZER
	section["singleDigitsIfNumberContains"] = threshold
	return threshold


def _get_phone_number_processing_mode():
	section = _ensure_number_processing_section()
	mode = str(section.get("phoneNumberProcessing", PHONE_NUMBER_PROCESSING_NATIVE)).strip()
	return mode if mode in PHONE_NUMBER_PROCESSING_MODES else PHONE_NUMBER_PROCESSING_NATIVE


def get_phone_number_processing_mode():
	return _get_phone_number_processing_mode()


def _set_phone_number_processing_mode(mode):
	section = _ensure_number_processing_section()
	mode = str(mode or PHONE_NUMBER_PROCESSING_NATIVE).strip()
	if mode not in PHONE_NUMBER_PROCESSING_MODES:
		mode = PHONE_NUMBER_PROCESSING_NATIVE
	section["phoneNumberProcessing"] = mode
	return mode


def _get_friendly_toll_free_prefixes_enabled():
	section = _ensure_number_processing_section()
	return bool(section.get("friendlyTollFreePrefixes", True))


def get_friendly_toll_free_prefixes_enabled():
	return _get_friendly_toll_free_prefixes_enabled()


def _set_friendly_toll_free_prefixes_enabled(enabled: bool):
	section = _ensure_number_processing_section()
	section["friendlyTollFreePrefixes"] = bool(enabled)
	return bool(enabled)


def _get_currency_processing_mode():
	section = _ensure_number_processing_section()
	mode = str(section.get("currencyProcessing", CURRENCY_PROCESSING_NATIVE)).strip()
	return mode if mode in CURRENCY_PROCESSING_MODES else CURRENCY_PROCESSING_NATIVE


def get_currency_processing_mode():
	return _get_currency_processing_mode()


def _set_currency_processing_mode(mode):
	section = _ensure_number_processing_section()
	mode = str(mode or CURRENCY_PROCESSING_NATIVE).strip()
	if mode not in CURRENCY_PROCESSING_MODES:
		mode = CURRENCY_PROCESSING_NATIVE
	section["currencyProcessing"] = mode
	return mode


def _get_ordinal_processing_mode():
	section = _ensure_number_processing_section()
	mode = str(section.get("ordinalProcessing", ORDINAL_PROCESSING_NATIVE)).strip()
	return mode if mode in ORDINAL_PROCESSING_MODES else ORDINAL_PROCESSING_NATIVE


def get_ordinal_processing_mode():
	return _get_ordinal_processing_mode()


def _set_ordinal_processing_mode(mode):
	section = _ensure_number_processing_section()
	mode = str(mode or ORDINAL_PROCESSING_NATIVE).strip()
	if mode not in ORDINAL_PROCESSING_MODES:
		mode = ORDINAL_PROCESSING_NATIVE
	section["ordinalProcessing"] = mode
	return mode


def _get_numeric_date_processing_mode():
	section = _ensure_number_processing_section()
	mode = str(section.get("numericDateProcessing", NUMERIC_DATE_PROCESSING_NATIVE)).strip()
	return mode if mode in NUMERIC_DATE_PROCESSING_MODES else NUMERIC_DATE_PROCESSING_NATIVE


def get_numeric_date_processing_mode():
	return _get_numeric_date_processing_mode()


def _set_numeric_date_processing_mode(mode):
	section = _ensure_number_processing_section()
	mode = str(mode or NUMERIC_DATE_PROCESSING_NATIVE).strip()
	if mode not in NUMERIC_DATE_PROCESSING_MODES:
		mode = NUMERIC_DATE_PROCESSING_NATIVE
	section["numericDateProcessing"] = mode
	return mode


def _get_numeric_date_format():
	section = _ensure_number_processing_section()
	date_format = str(section.get("numericDateFormat", NUMERIC_DATE_FORMAT_MDY)).strip().lower()
	return date_format if date_format in NUMERIC_DATE_FORMATS else NUMERIC_DATE_FORMAT_MDY


def get_numeric_date_format():
	return _get_numeric_date_format()


def _set_numeric_date_format(date_format):
	section = _ensure_number_processing_section()
	date_format = str(date_format or NUMERIC_DATE_FORMAT_MDY).strip().lower()
	if date_format not in NUMERIC_DATE_FORMATS:
		date_format = NUMERIC_DATE_FORMAT_MDY
	section["numericDateFormat"] = date_format
	return date_format


def _get_recognize_iso_dates_enabled():
	section = _ensure_number_processing_section()
	return bool(section.get("recognizeIsoDates", True))


def get_recognize_iso_dates_enabled():
	return _get_recognize_iso_dates_enabled()


def _set_recognize_iso_dates_enabled(enabled: bool):
	section = _ensure_number_processing_section()
	section["recognizeIsoDates"] = bool(enabled)
	return bool(enabled)


def _get_use_windows_date_format_enabled():
	section = _ensure_number_processing_section()
	return bool(section.get("useWindowsDateFormat", False))


def get_use_windows_date_format_enabled():
	return _get_use_windows_date_format_enabled()


def _set_use_windows_date_format_enabled(enabled: bool):
	section = _ensure_number_processing_section()
	section["useWindowsDateFormat"] = bool(enabled)
	return bool(enabled)
