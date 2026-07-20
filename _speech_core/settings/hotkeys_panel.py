import wx
import logHandler

from .accessibility import _set_panel_description
from .hotkeys_config import (
	_get_hotkey_dialog_access_key_only,
	_get_hotkey_format,
	_get_hotkey_mode,
	_get_hotkey_types,
	_set_hotkey_dialog_access_key_only,
	_set_hotkey_format,
	_set_hotkey_mode,
	_set_hotkey_types,
)
from .constants import (
	HOTKEY_FORMAT_CHOICES,
	HOTKEY_FORMAT_NATIVE,
	HOTKEY_MODE_BOTH,
	HOTKEY_MODE_CHOICES,
	HOTKEY_TYPES_BOTH,
	HOTKEY_TYPES_CHOICES,
)

log = logHandler.log

class HotkeysPanel(wx.Panel):
	def __init__(self, parent):
		super().__init__(parent)

		self.hotkeyMode = _get_hotkey_mode()
		self.hotkeyFormat = _get_hotkey_format()
		self.hotkeyTypes = _get_hotkey_types()
		self.dialogAccessKeyOnly = _get_hotkey_dialog_access_key_only()
		self._description = (
			"Hotkey speech is separate from verbosity profiles. "
			"Choose where ClassicSpeech should announce keyboard shortcuts and how extracted shortcuts should be spoken. "
			"Object query always includes the shortcut when NVDA exposes one."
		)
		_set_panel_description(self, "Hotkeys", self._description)

		mainSizer = wx.BoxSizer(wx.VERTICAL)

		mainSizer.Add(
			wx.StaticText(self, label=self._description),
			0,
			wx.ALL | wx.EXPAND,
			8,
		)

		grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
		grid.AddGrowableCol(1, 1)
		grid.Add(wx.StaticText(self, label="Speak hotkeys:"), 0, wx.ALIGN_CENTER_VERTICAL)
		self.hotkeyModeChoice = wx.Choice(
			self,
			choices=[label for label, _value in HOTKEY_MODE_CHOICES],
		)
		self.hotkeyModeChoice.SetName("Speak hotkeys")
		grid.Add(self.hotkeyModeChoice, 1, wx.EXPAND)

		grid.Add(wx.StaticText(self, label="Shortcut formatting:"), 0, wx.ALIGN_CENTER_VERTICAL)
		self.hotkeyFormatChoice = wx.Choice(
			self,
			choices=[label for label, _value in HOTKEY_FORMAT_CHOICES],
		)
		self.hotkeyFormatChoice.SetName("Shortcut formatting")
		grid.Add(self.hotkeyFormatChoice, 1, wx.EXPAND)

		grid.Add(wx.StaticText(self, label="Which shortcuts to speak:"), 0, wx.ALIGN_CENTER_VERTICAL)
		self.hotkeyTypesChoice = wx.Choice(
			self,
			choices=[label for label, _value in HOTKEY_TYPES_CHOICES],
		)
		self.hotkeyTypesChoice.SetName("Which shortcuts to speak")
		grid.Add(self.hotkeyTypesChoice, 1, wx.EXPAND)
		mainSizer.Add(grid, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		self.dialogAccessKeyOnlyCheck = wx.CheckBox(
			self,
			label="For simple dialog Alt shortcuts, speak only the access key letter",
		)
		mainSizer.Add(self.dialogAccessKeyOnlyCheck, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)
		self.SetSizer(mainSizer)

		self._loadControlsFromConfig()
		self.hotkeyModeChoice.Bind(wx.EVT_CHOICE, self.onInlineChanged)
		self.hotkeyFormatChoice.Bind(wx.EVT_CHOICE, self.onInlineChanged)
		self.hotkeyTypesChoice.Bind(wx.EVT_CHOICE, self.onInlineChanged)
		self.dialogAccessKeyOnlyCheck.Bind(wx.EVT_CHECKBOX, self.onInlineChanged)

	def _loadControlsFromConfig(self):
		mode = str(self.hotkeyMode or HOTKEY_MODE_BOTH)
		for index, (_label, value) in enumerate(HOTKEY_MODE_CHOICES):
			if value == mode:
				self.hotkeyModeChoice.SetSelection(index)
				break
		else:
			self.hotkeyModeChoice.SetSelection(len(HOTKEY_MODE_CHOICES) - 1)

		format_value = str(self.hotkeyFormat or HOTKEY_FORMAT_NATIVE)
		for index, (_label, value) in enumerate(HOTKEY_FORMAT_CHOICES):
			if value == format_value:
				self.hotkeyFormatChoice.SetSelection(index)
				break
		else:
			self.hotkeyFormatChoice.SetSelection(0)

		types_value = str(self.hotkeyTypes or HOTKEY_TYPES_BOTH)
		for index, (_label, value) in enumerate(HOTKEY_TYPES_CHOICES):
			if value == types_value:
				self.hotkeyTypesChoice.SetSelection(index)
				break
		else:
			self.hotkeyTypesChoice.SetSelection(len(HOTKEY_TYPES_CHOICES) - 1)

		self.dialogAccessKeyOnlyCheck.SetValue(bool(self.dialogAccessKeyOnly))

	def _getModeFromChoice(self):
		selection = self.hotkeyModeChoice.GetSelection()
		if selection < 0 or selection >= len(HOTKEY_MODE_CHOICES):
			return HOTKEY_MODE_BOTH
		return HOTKEY_MODE_CHOICES[selection][1]

	def _getFormatFromChoice(self):
		selection = self.hotkeyFormatChoice.GetSelection()
		if selection < 0 or selection >= len(HOTKEY_FORMAT_CHOICES):
			return HOTKEY_FORMAT_NATIVE
		return HOTKEY_FORMAT_CHOICES[selection][1]

	def _getTypesFromChoice(self):
		selection = self.hotkeyTypesChoice.GetSelection()
		if selection < 0 or selection >= len(HOTKEY_TYPES_CHOICES):
			return HOTKEY_TYPES_BOTH
		return HOTKEY_TYPES_CHOICES[selection][1]

	def onInlineChanged(self, evt=None):
		try:
			self.hotkeyMode = self._getModeFromChoice()
			self.hotkeyFormat = self._getFormatFromChoice()
			self.hotkeyTypes = self._getTypesFromChoice()
			self.dialogAccessKeyOnly = self.dialogAccessKeyOnlyCheck.GetValue()
			self.apply_live(save=False)
			dlg = wx.GetTopLevelParent(self)
			if hasattr(dlg, "_markDirty"):
				dlg._markDirty()
		except Exception:
			log.exception("ClassicSpeech hotkey settings live apply failed")

	def apply_live(self, save=True):
		self.hotkeyMode = self._getModeFromChoice()
		self.hotkeyFormat = self._getFormatFromChoice()
		self.hotkeyTypes = self._getTypesFromChoice()
		self.dialogAccessKeyOnly = self.dialogAccessKeyOnlyCheck.GetValue()
		_set_hotkey_mode(self.hotkeyMode)
		_set_hotkey_format(self.hotkeyFormat)
		_set_hotkey_types(self.hotkeyTypes)
		_set_hotkey_dialog_access_key_only(self.dialogAccessKeyOnly)

	def get_working_hotkey_config(self):
		self.hotkeyMode = self._getModeFromChoice()
		self.hotkeyFormat = self._getFormatFromChoice()
		self.hotkeyTypes = self._getTypesFromChoice()
		self.dialogAccessKeyOnly = self.dialogAccessKeyOnlyCheck.GetValue()
		return {
			"mode": self.hotkeyMode,
			"format": self.hotkeyFormat,
			"types": self.hotkeyTypes,
			"dialogAccessKeyOnly": bool(self.dialogAccessKeyOnly),
		}

	def get_working_hotkey_mode(self):
		return self.get_working_hotkey_config()["mode"]
