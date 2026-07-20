import wx
import logHandler

from .accessibility import _set_panel_description
from .advanced_config import (
	_get_announce_speech_hook_loaded_enabled,
	_get_debug_logging_enabled,
	_get_speech_hook_enabled,
	_get_speech_hook_loaded_message,
	_set_announce_speech_hook_loaded_enabled,
	_set_debug_logging_enabled,
	_set_speech_hook_enabled,
	_set_speech_hook_loaded_message,
)

log = logHandler.log


class AdvancedPanel(wx.Panel):
	"""Advanced ClassicSpeech diagnostics and runtime controls."""

	def __init__(self, parent):
		super().__init__(parent)

		_set_panel_description(
			self,
			"Advanced",
			"Configure ClassicSpeech diagnostic logging and the speech processing hook.",
		)

		mainSizer = wx.BoxSizer(wx.VERTICAL)

		self.debugLogging = wx.CheckBox(
			self,
			label="Enable ClassicSpeech diagnostic logging",
		)
		self.debugLogging.SetValue(_get_debug_logging_enabled())
		mainSizer.Add(self.debugLogging, 0, wx.ALL | wx.EXPAND, 8)

		self.speechHookEnabled = wx.CheckBox(
			self,
			label="Enable ClassicSpeech speech processing hook",
		)
		self.speechHookEnabled.SetValue(_get_speech_hook_enabled())
		mainSizer.Add(self.speechHookEnabled, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		self.announceSpeechHookLoaded = wx.CheckBox(
			self,
			label="Speak a message when the speech hook loads",
		)
		self.announceSpeechHookLoaded.SetValue(_get_announce_speech_hook_loaded_enabled())
		mainSizer.Add(self.announceSpeechHookLoaded, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		hookMessageGrid = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
		hookMessageGrid.AddGrowableCol(1, 1)
		hookMessageGrid.Add(
			wx.StaticText(self, label="Speech hook loaded message:"),
			0,
			wx.ALIGN_CENTER_VERTICAL,
		)
		self.speechHookLoadedMessage = wx.TextCtrl(
			self,
			value=_get_speech_hook_loaded_message(),
		)
		self.speechHookLoadedMessage.SetName("Speech hook loaded message")
		hookMessageGrid.Add(self.speechHookLoadedMessage, 1, wx.EXPAND)
		mainSizer.Add(hookMessageGrid, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		note = wx.StaticText(
			self,
			label=(
				"Turning the speech hook off leaves ClassicSpeech commands available, "
				"but lets NVDA speech pass through without ClassicSpeech processing."
			),
		)
		mainSizer.Add(note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		self.SetSizer(mainSizer)
		self.debugLogging.Bind(wx.EVT_CHECKBOX, self.onChanged)
		self.speechHookEnabled.Bind(wx.EVT_CHECKBOX, self.onChanged)
		self.announceSpeechHookLoaded.Bind(wx.EVT_CHECKBOX, self.onChanged)
		self.speechHookLoadedMessage.Bind(wx.EVT_TEXT, self.onChanged)

	def onChanged(self, evt=None):
		try:
			self.apply_live(save=False)
			dlg = wx.GetTopLevelParent(self)
			if hasattr(dlg, "_markDirty"):
				dlg._markDirty()
		except Exception:
			log.exception("ClassicSpeech advanced settings live apply failed")

	def apply_live(self, save=True):
		_set_debug_logging_enabled(self.debugLogging.GetValue())
		_set_announce_speech_hook_loaded_enabled(self.announceSpeechHookLoaded.GetValue())
		_set_speech_hook_loaded_message(self.speechHookLoadedMessage.GetValue())
		_set_speech_hook_enabled(self.speechHookEnabled.GetValue())
		if save:
			return
