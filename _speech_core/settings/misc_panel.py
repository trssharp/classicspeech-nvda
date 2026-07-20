import wx
import logHandler

from .misc_config import (
	_choice_string_to_fallback_delay,
	_fallback_delay_to_choice_string,
	_get_automatic_speech_interrupt_fallback_ms,
	_get_default_button_enabled,
	_get_guess_object_position_information_when_unavailable,
	_get_object_navigation_processing_enabled,
	_get_prevent_automatic_speech_interrupt_enabled,
	_get_query_object_source,
	_get_speech_interrupt_for_enter_enabled,
	_get_speech_interrupt_for_typed_characters_enabled,
	_set_automatic_speech_interrupt_fallback_ms,
	_set_default_button_enabled,
	_set_guess_object_position_information_when_unavailable,
	_set_object_navigation_processing_enabled,
	_set_prevent_automatic_speech_interrupt_enabled,
	_set_query_object_source,
	_set_speech_interrupt_for_enter_enabled,
	_set_speech_interrupt_for_typed_characters_enabled,
)
from .constants import _FALLBACK_SPEECH_DELAY_CHOICES, QUERY_OBJECT_SOURCE_CHOICES

log = logHandler.log

class MiscPanel(wx.Panel):
	def __init__(self, parent):
		super().__init__(parent)

		mainSizer = wx.BoxSizer(wx.VERTICAL)

		self.announceDefaultButton = wx.CheckBox(
			self,
			label="Announce default button in dialogs",
		)
		self.announceDefaultButton.SetValue(_get_default_button_enabled())
		mainSizer.Add(self.announceDefaultButton, 0, wx.ALL | wx.EXPAND, 8)

		self.guessObjectPositionInformationWhenUnavailable = wx.CheckBox(
			self,
			label="Guess object position information when unavailable",
		)
		self.guessObjectPositionInformationWhenUnavailable.SetValue(
			_get_guess_object_position_information_when_unavailable()
		)
		mainSizer.Add(self.guessObjectPositionInformationWhenUnavailable, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		querySourceSizer = wx.BoxSizer(wx.HORIZONTAL)
		querySourceLabel = wx.StaticText(
			self,
			label="Insert+Tab reports",
		)
		querySourceSizer.Add(querySourceLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
		self.queryObjectSourceChoice = wx.Choice(
			self,
			choices=[label for label, _value in QUERY_OBJECT_SOURCE_CHOICES],
		)
		currentQuerySource = _get_query_object_source()
		for index, (_label, value) in enumerate(QUERY_OBJECT_SOURCE_CHOICES):
			if value == currentQuerySource:
				self.queryObjectSourceChoice.SetSelection(index)
				break
		else:
			self.queryObjectSourceChoice.SetSelection(0)
		self.queryObjectSourceChoice.SetName("Insert+Tab reports")
		querySourceSizer.Add(self.queryObjectSourceChoice, 0, wx.ALIGN_CENTER_VERTICAL)
		mainSizer.Add(querySourceSizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		self.objectNavigationProcessing = wx.CheckBox(
			self,
			label="Object navigation processing",
		)
		self.objectNavigationProcessing.SetValue(_get_object_navigation_processing_enabled())
		mainSizer.Add(self.objectNavigationProcessing, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		self.preventAutomaticSpeechInterrupt = wx.CheckBox(
			self,
			label="Prevent automatic speech interruptions",
		)
		self.preventAutomaticSpeechInterrupt.SetValue(_get_prevent_automatic_speech_interrupt_enabled())
		mainSizer.Add(self.preventAutomaticSpeechInterrupt, 0, wx.ALL | wx.EXPAND, 8)

		self.speechInterruptForCharacters = wx.CheckBox(
			self,
			label="Speech interrupt for typed characters",
		)
		self.speechInterruptForCharacters.SetValue(_get_speech_interrupt_for_typed_characters_enabled())
		mainSizer.Add(self.speechInterruptForCharacters, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		self.speechInterruptForEnter = wx.CheckBox(
			self,
			label="Speech interrupt for Enter key",
		)
		self.speechInterruptForEnter.SetValue(_get_speech_interrupt_for_enter_enabled())
		mainSizer.Add(self.speechInterruptForEnter, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		fallbackSizer = wx.BoxSizer(wx.HORIZONTAL)
		fallbackLabel = wx.StaticText(
			self,
			label="Fallback speech delay when completion is unavailable, milliseconds",
		)
		fallbackSizer.Add(fallbackLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
		self.automaticSpeechInterruptFallbackMs = wx.Choice(
			self,
			choices=[f"{value} ms" for value in _FALLBACK_SPEECH_DELAY_CHOICES],
		)
		self.automaticSpeechInterruptFallbackMs.SetStringSelection(
			_fallback_delay_to_choice_string(_get_automatic_speech_interrupt_fallback_ms())
		)
		self.automaticSpeechInterruptFallbackMs.SetName("Fallback speech delay")
		fallbackSizer.Add(self.automaticSpeechInterruptFallbackMs, 0, wx.ALIGN_CENTER_VERTICAL)
		mainSizer.Add(fallbackSizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		self.SetSizer(mainSizer)

		self.announceDefaultButton.Bind(wx.EVT_CHECKBOX, self.onChanged)
		self.guessObjectPositionInformationWhenUnavailable.Bind(wx.EVT_CHECKBOX, self.onChanged)
		self.queryObjectSourceChoice.Bind(wx.EVT_CHOICE, self.onChanged)
		self.objectNavigationProcessing.Bind(wx.EVT_CHECKBOX, self.onChanged)
		self.preventAutomaticSpeechInterrupt.Bind(wx.EVT_CHECKBOX, self.onChanged)
		self.speechInterruptForCharacters.Bind(wx.EVT_CHECKBOX, self.onChanged)
		self.speechInterruptForEnter.Bind(wx.EVT_CHECKBOX, self.onChanged)
		self.automaticSpeechInterruptFallbackMs.Bind(wx.EVT_CHOICE, self.onChanged)

	def onChanged(self, evt=None):
		try:
			self.apply_live(save=False)
			dlg = wx.GetTopLevelParent(self)
			if hasattr(dlg, "_markDirty"):
				dlg._markDirty()
		except Exception:
			log.exception("ClassicSpeech misc settings live apply failed")

	def apply_live(self, save=True):
		default_button = self.announceDefaultButton.GetValue()
		guess_position = self.guessObjectPositionInformationWhenUnavailable.GetValue()
		query_source = QUERY_OBJECT_SOURCE_CHOICES[self.queryObjectSourceChoice.GetSelection()][1]
		object_nav_processing = self.objectNavigationProcessing.GetValue()
		prevent_interrupt = self.preventAutomaticSpeechInterrupt.GetValue()
		interrupt_for_characters = self.speechInterruptForCharacters.GetValue()
		interrupt_for_enter = self.speechInterruptForEnter.GetValue()
		fallback_ms = _choice_string_to_fallback_delay(
			self.automaticSpeechInterruptFallbackMs.GetStringSelection()
		)
		_set_default_button_enabled(default_button)
		_set_guess_object_position_information_when_unavailable(guess_position)
		_set_query_object_source(query_source)
		_set_object_navigation_processing_enabled(object_nav_processing)
		_set_prevent_automatic_speech_interrupt_enabled(prevent_interrupt)
		_set_speech_interrupt_for_typed_characters_enabled(interrupt_for_characters)
		_set_speech_interrupt_for_enter_enabled(interrupt_for_enter)
		_set_automatic_speech_interrupt_fallback_ms(fallback_ms)
		if save:
			return
