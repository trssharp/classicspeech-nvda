from ...localization import _

import wx
import logHandler

from ..accessibility import _set_panel_description
from .config import (
	_get_announce_new_lines_during_say_all_enabled,
	_get_list_item_state_reporting_mode,
	_get_new_line_message,
	_get_repeated_character_mode,
	_get_spell_alphanumeric_data_mode,
	_get_split_mixed_case_words_enabled,
	_get_suppress_word_internal_dashes_enabled,
	_set_announce_new_lines_during_say_all_enabled,
	_set_list_item_state_reporting_mode,
	_set_new_line_message,
	_set_repeated_character_mode,
	_set_spell_alphanumeric_data_mode,
	_set_split_mixed_case_words_enabled,
	_set_suppress_word_internal_dashes_enabled,
)

log = logHandler.log

_ALPHANUMERIC_DATA_CHOICES = [
	(_("Off"), "off"),
	(_("Spell mixed letters and numbers"), "spell"),
	(_("Spell mixed letters and numbers phonetically"), "phonetic"),
]
_ALPHANUMERIC_LABEL_TO_MODE = dict(_ALPHANUMERIC_DATA_CHOICES)
_ALPHANUMERIC_MODE_TO_LABEL = {mode: label for label, mode in _ALPHANUMERIC_DATA_CHOICES}

_LIST_ITEM_STATE_REPORTING_CHOICES = [
	(_("NVDA native"), "native"),
	(_("Say not selected"), "notSelected"),
	(_("Say none"), "none"),
	(_("Say selected"), "selected"),
	(_("Say both"), "both"),
]
_LIST_ITEM_STATE_REPORTING_LABEL_TO_MODE = dict(_LIST_ITEM_STATE_REPORTING_CHOICES)
_LIST_ITEM_STATE_REPORTING_MODE_TO_LABEL = {mode: label for label, mode in _LIST_ITEM_STATE_REPORTING_CHOICES}

_REPEATED_CHARACTER_CHOICES = [
	(_("NVDA native"), "native"),
	(_("3 repeated characters"), "3"),
	(_("4 repeated characters"), "4"),
	(_("5 repeated characters"), "5"),
	(_("6 repeated characters"), "6"),
	(_("All repeated characters"), "all"),
	(_("Count repeated characters and spaces"), "count"),
]
_LABEL_TO_MODE = dict(_REPEATED_CHARACTER_CHOICES)
_MODE_TO_LABEL = {mode: label for label, mode in _REPEATED_CHARACTER_CHOICES}


class TextProcessingPanel(wx.Panel):
	"""ClassicSpeech text processor options."""

	def __init__(self, parent):
		super().__init__(parent)

		_set_panel_description(
			self,
			_("Text Processing"),
			_("Configure ClassicSpeech literal text transformations before speech reaches the synthesizer."),
		)

		mainSizer = wx.BoxSizer(wx.VERTICAL)

		self.announceNewLinesDuringSayAll = wx.CheckBox(
			self,
			label=_("Announce new lines during Say All"),
		)
		self.announceNewLinesDuringSayAll.SetValue(
			_get_announce_new_lines_during_say_all_enabled()
		)
		mainSizer.Add(self.announceNewLinesDuringSayAll, 0, wx.ALL | wx.EXPAND, 8)

		newLineGrid = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
		newLineGrid.AddGrowableCol(1, 1)
		newLineGrid.Add(
			wx.StaticText(self, label=_("New line message:")),
			0,
			wx.ALIGN_CENTER_VERTICAL,
		)
		self.newLineMessage = wx.TextCtrl(self, value=_get_new_line_message())
		self.newLineMessage.SetName(_("New line message"))
		newLineGrid.Add(self.newLineMessage, 1, wx.EXPAND)
		mainSizer.Add(newLineGrid, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		self.splitMixedCaseWords = wx.CheckBox(
			self,
			label=_("Split mixed-case words, such as SayAll into Say All"),
		)
		self.splitMixedCaseWords.SetValue(_get_split_mixed_case_words_enabled())
		mainSizer.Add(self.splitMixedCaseWords, 0, wx.ALL | wx.EXPAND, 8)

		self.suppressWordInternalDashes = wx.CheckBox(
			self,
			label=_("Suppress dashes inside words, such as sister-in-law"),
		)
		self.suppressWordInternalDashes.SetValue(_get_suppress_word_internal_dashes_enabled())
		mainSizer.Add(self.suppressWordInternalDashes, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		alphanumericLabel = wx.StaticText(self, label=_("Spell alphanumeric data:"))
		mainSizer.Add(alphanumericLabel, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		self.spellAlphanumericData = wx.ComboBox(
			self,
			choices=[label for label, _mode in _ALPHANUMERIC_DATA_CHOICES],
			style=wx.CB_READONLY,
		)
		self.spellAlphanumericData.SetName(_("Spell alphanumeric data"))
		self.spellAlphanumericData.SetValue(
			_ALPHANUMERIC_MODE_TO_LABEL.get(_get_spell_alphanumeric_data_mode(), "Off")
		)
		mainSizer.Add(self.spellAlphanumericData, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		listItemStateLabel = wx.StaticText(self, label=_("List item state reporting:"))
		mainSizer.Add(listItemStateLabel, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		self.listItemStateReporting = wx.ComboBox(
			self,
			choices=[label for label, _mode in _LIST_ITEM_STATE_REPORTING_CHOICES],
			style=wx.CB_READONLY,
		)
		self.listItemStateReporting.SetName(_("List item state reporting"))
		self.listItemStateReporting.SetValue(
			_LIST_ITEM_STATE_REPORTING_MODE_TO_LABEL.get(
				_get_list_item_state_reporting_mode(),
				"Say not selected",
			)
		)
		mainSizer.Add(self.listItemStateReporting, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)


		repeatedLabel = wx.StaticText(self, label=_("Repeated characters:"))
		mainSizer.Add(repeatedLabel, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		self.repeatedCharacterMode = wx.ComboBox(
			self,
			choices=[label for label, _mode in _REPEATED_CHARACTER_CHOICES],
			style=wx.CB_READONLY,
		)
		self.repeatedCharacterMode.SetName(_("Repeated characters"))
		self.repeatedCharacterMode.SetValue(
			_MODE_TO_LABEL.get(_get_repeated_character_mode(), "3 repeated characters")
		)
		mainSizer.Add(self.repeatedCharacterMode, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		note = wx.StaticText(
			self,
			label=(
				_("Modes 3, 4, 5, 6, and All do not report repeated spaces. "
				"Count repeated characters and spaces reports space runs, which can help with indentation.")
			),
		)
		mainSizer.Add(note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		self.SetSizer(mainSizer)
		self.announceNewLinesDuringSayAll.Bind(wx.EVT_CHECKBOX, self.onChanged)
		self.newLineMessage.Bind(wx.EVT_TEXT, self.onChanged)
		self.splitMixedCaseWords.Bind(wx.EVT_CHECKBOX, self.onChanged)
		self.suppressWordInternalDashes.Bind(wx.EVT_CHECKBOX, self.onChanged)
		self.spellAlphanumericData.Bind(wx.EVT_COMBOBOX, self.onChanged)
		self.spellAlphanumericData.Bind(wx.EVT_TEXT, self.onChanged)
		self.listItemStateReporting.Bind(wx.EVT_COMBOBOX, self.onChanged)
		self.listItemStateReporting.Bind(wx.EVT_TEXT, self.onChanged)
		self.repeatedCharacterMode.Bind(wx.EVT_COMBOBOX, self.onChanged)
		self.repeatedCharacterMode.Bind(wx.EVT_TEXT, self.onChanged)

	def onChanged(self, evt=None):
		try:
			self.apply_live(save=False)
			dlg = wx.GetTopLevelParent(self)
			if hasattr(dlg, "_markDirty"):
				dlg._markDirty()
		except Exception:
			log.exception("ClassicSpeech text processing settings live apply failed")

	def apply_live(self, save=True):
		_set_announce_new_lines_during_say_all_enabled(
			self.announceNewLinesDuringSayAll.GetValue()
		)
		_set_new_line_message(self.newLineMessage.GetValue())
		_set_split_mixed_case_words_enabled(self.splitMixedCaseWords.GetValue())
		_set_suppress_word_internal_dashes_enabled(self.suppressWordInternalDashes.GetValue())
		_set_spell_alphanumeric_data_mode(
			_ALPHANUMERIC_LABEL_TO_MODE.get(self.spellAlphanumericData.GetValue(), "off")
		)
		_set_list_item_state_reporting_mode(
			_LIST_ITEM_STATE_REPORTING_LABEL_TO_MODE.get(self.listItemStateReporting.GetValue(), "notSelected")
		)
		_set_repeated_character_mode(
			_LABEL_TO_MODE.get(self.repeatedCharacterMode.GetValue(), "3")
		)
		if save:
			return
