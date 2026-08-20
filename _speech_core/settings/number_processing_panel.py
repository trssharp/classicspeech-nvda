from ..localization import _

import wx
import logHandler

from .accessibility import _set_panel_description
from .number_processing_config import (
	_get_currency_processing_mode,
	_get_friendly_toll_free_prefixes_enabled,
	_get_number_processing_mode,
	_get_numeric_date_format,
	_get_numeric_date_processing_mode,
	_get_ordinal_processing_mode,
	_get_phone_number_processing_mode,
	_get_recognize_iso_dates_enabled,
	_get_single_digits_threshold,
	_get_use_windows_date_format_enabled,
	_set_currency_processing_mode,
	_set_friendly_toll_free_prefixes_enabled,
	_set_number_processing_mode,
	_set_numeric_date_format,
	_set_numeric_date_processing_mode,
	_set_ordinal_processing_mode,
	_set_phone_number_processing_mode,
	_set_recognize_iso_dates_enabled,
	_set_single_digits_threshold,
	_set_use_windows_date_format_enabled,
)

log = logHandler.log

_NATIVE_LABEL = _("NVDA native")

_NUMBER_PROCESSING_CHOICES = [
	(_NATIVE_LABEL, "synthesizer"),
	(_("Single digits"), "singleDigits"),
	(_("Pairs"), "pairs"),
	(_("Full numbers"), "fullNumbers"),
]
_LABEL_TO_MODE = dict(_NUMBER_PROCESSING_CHOICES)
_MODE_TO_LABEL = {mode: label for label, mode in _NUMBER_PROCESSING_CHOICES}

_SINGLE_DIGITS_THRESHOLD_CHOICES = [
	(_NATIVE_LABEL, "synthesizer"),
	(_("Five or more digits"), "5"),
	(_("Six or more digits"), "6"),
	(_("Seven or more digits"), "7"),
	(_("Eight or more digits"), "8"),
]

_THRESHOLD_LABEL_TO_VALUE = dict(_SINGLE_DIGITS_THRESHOLD_CHOICES)
_THRESHOLD_VALUE_TO_LABEL = {value: label for label, value in _SINGLE_DIGITS_THRESHOLD_CHOICES}

_PHONE_NUMBER_PROCESSING_CHOICES = [
	(_NATIVE_LABEL, "native"),
	(_("Grouped digits"), "groupedDigits"),
]
_PHONE_LABEL_TO_MODE = dict(_PHONE_NUMBER_PROCESSING_CHOICES)
_PHONE_MODE_TO_LABEL = {mode: label for label, mode in _PHONE_NUMBER_PROCESSING_CHOICES}

_CURRENCY_PROCESSING_CHOICES = [
	(_NATIVE_LABEL, "native"),
	(_("Dollars and cents"), "dollarsAndCents"),
]
_CURRENCY_LABEL_TO_MODE = dict(_CURRENCY_PROCESSING_CHOICES)
_CURRENCY_MODE_TO_LABEL = {mode: label for label, mode in _CURRENCY_PROCESSING_CHOICES}

_ORDINAL_PROCESSING_CHOICES = [
	(_NATIVE_LABEL, "native"),
	(_("Ordinals as words"), "words"),
]
_ORDINAL_LABEL_TO_MODE = dict(_ORDINAL_PROCESSING_CHOICES)
_ORDINAL_MODE_TO_LABEL = {mode: label for label, mode in _ORDINAL_PROCESSING_CHOICES}

_NUMERIC_DATE_PROCESSING_CHOICES = [
	(_NATIVE_LABEL, "native"),
	(_("Some"), "some"),
	(_("Full"), "full"),
]
_DATE_LABEL_TO_MODE = dict(_NUMERIC_DATE_PROCESSING_CHOICES)
_DATE_MODE_TO_LABEL = {mode: label for label, mode in _NUMERIC_DATE_PROCESSING_CHOICES}

_NUMERIC_DATE_FORMAT_CHOICES = [
	(_("Month day year"), "mdy"),
	(_("Day month year"), "dmy"),
	(_("Year month day"), "ymd"),
]
_DATE_FORMAT_LABEL_TO_MODE = dict(_NUMERIC_DATE_FORMAT_CHOICES)
_DATE_FORMAT_MODE_TO_LABEL = {mode: label for label, mode in _NUMERIC_DATE_FORMAT_CHOICES}


class NumberProcessingPanel(wx.Panel):
	"""ClassicSpeech number/date/currency options."""

	def __init__(self, parent):
		super().__init__(parent)

		_set_panel_description(
			self,
			_("Number Processing"),
			_("Configure opt-in ClassicSpeech handling for standalone numbers. Currency, dates, times, and phone-like strings are preserved by default."),
		)

		mainSizer = wx.BoxSizer(wx.VERTICAL)
		modeLabel = wx.StaticText(self, label=_("Number processing:"))
		mainSizer.Add(modeLabel, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		self.numberProcessingMode = wx.ComboBox(
			self,
			choices=[label for label, _mode in _NUMBER_PROCESSING_CHOICES],
			style=wx.CB_READONLY,
		)
		self.numberProcessingMode.SetName(_("Number processing"))
		self.numberProcessingMode.SetValue(
			_MODE_TO_LABEL.get(_get_number_processing_mode(), _NATIVE_LABEL)
		)
		mainSizer.Add(self.numberProcessingMode, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		thresholdLabel = wx.StaticText(self, label=_("Speak single digits if number contains:"))
		mainSizer.Add(thresholdLabel, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		self.singleDigitsThreshold = wx.ComboBox(
			self,
			choices=[label for label, _value in _SINGLE_DIGITS_THRESHOLD_CHOICES],
			style=wx.CB_READONLY,
		)
		self.singleDigitsThreshold.SetName(_("Speak single digits if number contains"))
		self.singleDigitsThreshold.SetValue(
			_THRESHOLD_VALUE_TO_LABEL.get(_get_single_digits_threshold(), _NATIVE_LABEL)
		)
		mainSizer.Add(self.singleDigitsThreshold, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		phoneLabel = wx.StaticText(self, label=_("Phone number processing:"))
		mainSizer.Add(phoneLabel, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		self.phoneNumberProcessing = wx.ComboBox(
			self,
			choices=[label for label, _mode in _PHONE_NUMBER_PROCESSING_CHOICES],
			style=wx.CB_READONLY,
		)
		self.phoneNumberProcessing.SetName(_("Phone number processing"))
		self.phoneNumberProcessing.SetValue(
			_PHONE_MODE_TO_LABEL.get(_get_phone_number_processing_mode(), _NATIVE_LABEL)
		)
		mainSizer.Add(self.phoneNumberProcessing, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		self.friendlyTollFreePrefixes = wx.CheckBox(
			self,
			label=_("Use friendly toll-free prefixes"),
		)
		self.friendlyTollFreePrefixes.SetName(_("Use friendly toll-free prefixes"))
		self.friendlyTollFreePrefixes.SetValue(_get_friendly_toll_free_prefixes_enabled())
		mainSizer.Add(self.friendlyTollFreePrefixes, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		currencyLabel = wx.StaticText(self, label=_("Currency processing:"))
		mainSizer.Add(currencyLabel, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		self.currencyProcessing = wx.ComboBox(
			self,
			choices=[label for label, _mode in _CURRENCY_PROCESSING_CHOICES],
			style=wx.CB_READONLY,
		)
		self.currencyProcessing.SetName(_("Currency processing"))
		self.currencyProcessing.SetValue(
			_CURRENCY_MODE_TO_LABEL.get(_get_currency_processing_mode(), _NATIVE_LABEL)
		)
		mainSizer.Add(self.currencyProcessing, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		ordinalLabel = wx.StaticText(self, label=_("Ordinal processing:"))
		mainSizer.Add(ordinalLabel, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		self.ordinalProcessing = wx.ComboBox(
			self,
			choices=[label for label, _mode in _ORDINAL_PROCESSING_CHOICES],
			style=wx.CB_READONLY,
		)
		self.ordinalProcessing.SetName(_("Ordinal processing"))
		self.ordinalProcessing.SetValue(
			_ORDINAL_MODE_TO_LABEL.get(_get_ordinal_processing_mode(), _NATIVE_LABEL)
		)
		mainSizer.Add(self.ordinalProcessing, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		dateLabel = wx.StaticText(self, label=_("Numeric date processing:"))
		mainSizer.Add(dateLabel, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		self.numericDateProcessing = wx.ComboBox(
			self,
			choices=[label for label, _mode in _NUMERIC_DATE_PROCESSING_CHOICES],
			style=wx.CB_READONLY,
		)
		self.numericDateProcessing.SetName(_("Numeric date processing"))
		self.numericDateProcessing.SetValue(
			_DATE_MODE_TO_LABEL.get(_get_numeric_date_processing_mode(), _NATIVE_LABEL)
		)
		mainSizer.Add(self.numericDateProcessing, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		dateFormatLabel = wx.StaticText(self, label=_("Numeric date format:"))
		mainSizer.Add(dateFormatLabel, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		self.numericDateFormat = wx.ComboBox(
			self,
			choices=[label for label, _mode in _NUMERIC_DATE_FORMAT_CHOICES],
			style=wx.CB_READONLY,
		)
		self.numericDateFormat.SetName(_("Numeric date format"))
		self.numericDateFormat.SetValue(
			_DATE_FORMAT_MODE_TO_LABEL.get(_get_numeric_date_format(), "Month day year")
		)
		mainSizer.Add(self.numericDateFormat, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		self.recognizeIsoDates = wx.CheckBox(
			self,
			label=_("Recognize ISO year-first dates"),
		)
		self.recognizeIsoDates.SetName(_("Recognize ISO year-first dates"))
		self.recognizeIsoDates.SetValue(_get_recognize_iso_dates_enabled())
		mainSizer.Add(self.recognizeIsoDates, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		self.useWindowsDateFormat = wx.CheckBox(
			self,
			label=_("Use Windows locale for date format"),
		)
		self.useWindowsDateFormat.SetName(_("Use Windows locale for date format"))
		self.useWindowsDateFormat.SetValue(_get_use_windows_date_format_enabled())
		mainSizer.Add(self.useWindowsDateFormat, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		note = wx.StaticText(
			self,
			label=(
				_("NVDA native is the safe default and leaves numbers unchanged for NVDA and the active synthesizer. "
				"Threshold digit spelling only rewrites standalone integer strings at the selected length or longer. "
				"Phone number processing handles common U.S.-style phone numbers as grouped digits when enabled. "
				"Friendly toll-free prefixes say numbers like 1-800 as one eight hundred. "
				"Currency processing can say simple dollar amounts as dollars and cents for synths that do not. "
				"Ordinal processing can say standalone tokens such as 1st and 22nd as words. "
				"ISO year-first recognition handles strict four-digit year-first dates such as 2026-09-05 without changing the selected numeric date format. "
				"When Windows locale is enabled, unsupported Windows date formats fall back to the selected numeric date format. "
				"Currency, times, non-phone codes, and alphanumeric strings are left unchanged.")
			),
		)
		mainSizer.Add(note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		self.SetSizer(mainSizer)
		self.numberProcessingMode.Bind(wx.EVT_COMBOBOX, self.onChanged)
		self.singleDigitsThreshold.Bind(wx.EVT_COMBOBOX, self.onChanged)
		self.phoneNumberProcessing.Bind(wx.EVT_COMBOBOX, self.onChanged)
		self.friendlyTollFreePrefixes.Bind(wx.EVT_CHECKBOX, self.onChanged)
		self.currencyProcessing.Bind(wx.EVT_COMBOBOX, self.onChanged)
		self.ordinalProcessing.Bind(wx.EVT_COMBOBOX, self.onChanged)
		self.numericDateProcessing.Bind(wx.EVT_COMBOBOX, self.onChanged)
		self.numericDateFormat.Bind(wx.EVT_COMBOBOX, self.onChanged)
		self.recognizeIsoDates.Bind(wx.EVT_CHECKBOX, self.onChanged)
		self.useWindowsDateFormat.Bind(wx.EVT_CHECKBOX, self.onChanged)

	def onChanged(self, evt=None):
		try:
			self.apply_live(save=False)
			dlg = wx.GetTopLevelParent(self)
			if hasattr(dlg, "_markDirty"):
				dlg._markDirty()
		except Exception:
			log.exception("ClassicSpeech number processing settings live apply failed")

	def apply_live(self, save=True):
		_set_number_processing_mode(
			_LABEL_TO_MODE.get(self.numberProcessingMode.GetValue(), "synthesizer")
		)
		_set_single_digits_threshold(
			_THRESHOLD_LABEL_TO_VALUE.get(self.singleDigitsThreshold.GetValue(), "synthesizer")
		)
		_set_phone_number_processing_mode(
			_PHONE_LABEL_TO_MODE.get(self.phoneNumberProcessing.GetValue(), "native")
		)
		_set_friendly_toll_free_prefixes_enabled(self.friendlyTollFreePrefixes.GetValue())
		_set_currency_processing_mode(
			_CURRENCY_LABEL_TO_MODE.get(self.currencyProcessing.GetValue(), "native")
		)
		_set_ordinal_processing_mode(
			_ORDINAL_LABEL_TO_MODE.get(self.ordinalProcessing.GetValue(), "native")
		)
		_set_numeric_date_processing_mode(
			_DATE_LABEL_TO_MODE.get(self.numericDateProcessing.GetValue(), "native")
		)
		_set_numeric_date_format(
			_DATE_FORMAT_LABEL_TO_MODE.get(self.numericDateFormat.GetValue(), "mdy")
		)
		_set_recognize_iso_dates_enabled(self.recognizeIsoDates.GetValue())
		_set_use_windows_date_format_enabled(self.useWindowsDateFormat.GetValue())
		if save:
			return
