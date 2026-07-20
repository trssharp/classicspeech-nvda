import copy

import wx
import logHandler

from .accessibility import _set_panel_description
from .shape_config import (
	_clone_shape_from_manager,
	_get_live_verbosity_manager,
	_preview_shape_config,
	_save_shape_config,
)
from .constants import (
	GLOBAL_PAUSE_CHOICES,
	PAUSE_MODE_GLOBAL,
	PAUSE_PLACEMENT_BEFORE,
	PAUSE_PLACEMENT_CHOICES,
	TOKEN_ORDER_ITEMS,
	TOKEN_ORDER_KINDS,
	TOKEN_PAUSE_CHOICES,
	TOKEN_PAUSE_USE_GLOBAL,
)

log = logHandler.log

class SpeechTimingPanel(wx.Panel):
	def __init__(self, parent):
		super().__init__(parent)

		self.shapeConfig = _clone_shape_from_manager()
		self.tokenPauseChoices = {}
		self._description = (
			"Global pause is the default silence used between spoken items. "
			"Per-token pauses can override it for specific tokens, such as position."
		)
		_set_panel_description(self, "Speech Timing", self._description)

		mainSizer = wx.BoxSizer(wx.VERTICAL)

		mainSizer.Add(
			wx.StaticText(self, label=self._description),
			0,
			wx.ALL | wx.EXPAND,
			8,
		)

		grid = wx.FlexGridSizer(cols=2, vgap=10, hgap=10)
		grid.AddGrowableCol(1, 1)

		grid.Add(wx.StaticText(self, label="Global pause:"), 0, wx.ALIGN_CENTER_VERTICAL)
		self.globalPauseChoice = wx.Choice(
			self,
			choices=[label for label, _value in GLOBAL_PAUSE_CHOICES],
		)
		self.globalPauseChoice.SetName("Global pause")
		grid.Add(self.globalPauseChoice, 1, wx.EXPAND)

		grid.Add(wx.StaticText(self, label="Pause placement:"), 0, wx.ALIGN_CENTER_VERTICAL)
		self.pausePlacementChoice = wx.Choice(
			self,
			choices=[label for label, _value in PAUSE_PLACEMENT_CHOICES],
		)
		self.pausePlacementChoice.SetName("Pause placement")
		grid.Add(self.pausePlacementChoice, 1, wx.EXPAND)

		for tokenKind, tokenLabel in TOKEN_ORDER_ITEMS:
			grid.Add(wx.StaticText(self, label=f"{tokenLabel} pause:"), 0, wx.ALIGN_CENTER_VERTICAL)
			choice = wx.Choice(
				self,
				choices=[label for label, _value in TOKEN_PAUSE_CHOICES],
			)
			choice.SetName(f"{tokenLabel} pause")
			self.tokenPauseChoices[tokenKind] = choice
			grid.Add(choice, 1, wx.EXPAND)

		mainSizer.Add(grid, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		self.pauseAfterFinalToken = wx.CheckBox(
			self,
			label="Pause after final spoken token",
		)
		mainSizer.Add(self.pauseAfterFinalToken, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)
		self.SetSizer(mainSizer)

		self._loadControlsFromShape()

		self.globalPauseChoice.Bind(wx.EVT_CHOICE, self.onInlineChanged)
		self.pausePlacementChoice.Bind(wx.EVT_CHOICE, self.onInlineChanged)
		self.pauseAfterFinalToken.Bind(wx.EVT_CHECKBOX, self.onInlineChanged)
		for choice in self.tokenPauseChoices.values():
			choice.Bind(wx.EVT_CHOICE, self.onInlineChanged)

	def _findPauseChoiceIndex(self, pause_ms: int):
		for index, (_label, value) in enumerate(GLOBAL_PAUSE_CHOICES):
			if int(value) == int(pause_ms):
				return index
		return 1

	def _findTokenPauseChoiceIndex(self, pause_ms: int):
		for index, (_label, value) in enumerate(TOKEN_PAUSE_CHOICES):
			if int(value) == int(pause_ms):
				return index
		return 0

	def _findPausePlacementChoiceIndex(self, placement: str):
		for index, (_label, value) in enumerate(PAUSE_PLACEMENT_CHOICES):
			if value == placement:
				return index
		return 0

	def _getPauseValueFromChoice(self):
		selection = self.globalPauseChoice.GetSelection()
		if selection < 0 or selection >= len(GLOBAL_PAUSE_CHOICES):
			return 80
		return int(GLOBAL_PAUSE_CHOICES[selection][1])

	def _getTokenPauseValueFromChoice(self, choice):
		selection = choice.GetSelection()
		if selection < 0 or selection >= len(TOKEN_PAUSE_CHOICES):
			return 0
		return int(TOKEN_PAUSE_CHOICES[selection][1])

	def _getPausePlacementFromChoice(self):
		selection = self.pausePlacementChoice.GetSelection()
		if selection < 0 or selection >= len(PAUSE_PLACEMENT_CHOICES):
			return PAUSE_PLACEMENT_BEFORE
		return str(PAUSE_PLACEMENT_CHOICES[selection][1])

	def _refreshShapeFromControls(self):
		shape = copy.deepcopy(self.shapeConfig)
		shape["pauseMode"] = PAUSE_MODE_GLOBAL
		shape["globalPause"] = self._getPauseValueFromChoice()
		shape["pausePlacement"] = self._getPausePlacementFromChoice()
		shape["pauseAfterFinalToken"] = bool(self.pauseAfterFinalToken.GetValue())

		pauses = dict(shape.get("pauses", {}))
		for tokenKind, choice in self.tokenPauseChoices.items():
			pauses[tokenKind] = self._getTokenPauseValueFromChoice(choice)
		shape["pauses"] = pauses
		# Hybrid timing: global pause stays the baseline. Each token either uses
		# global (-1), turns pause off (0), or overrides with an explicit value.
		shape["pauseMode"] = PAUSE_MODE_GLOBAL
		self.shapeConfig = shape

	def _loadControlsFromShape(self):
		self.globalPauseChoice.SetSelection(
			self._findPauseChoiceIndex(int(self.shapeConfig.get("globalPause", 80)))
		)
		self.pausePlacementChoice.SetSelection(
			self._findPausePlacementChoiceIndex(
				str(self.shapeConfig.get("pausePlacement", PAUSE_PLACEMENT_BEFORE))
			)
		)
		pauses = dict(self.shapeConfig.get("pauses", {}))
		for tokenKind, choice in self.tokenPauseChoices.items():
			pauseValue = pauses.get(tokenKind, TOKEN_PAUSE_USE_GLOBAL)
			choice.SetSelection(
				self._findTokenPauseChoiceIndex(int(pauseValue))
			)
		self.pauseAfterFinalToken.SetValue(
			bool(self.shapeConfig.get("pauseAfterFinalToken", True))
		)

	def onInlineChanged(self, evt=None):
		try:
			self._refreshShapeFromControls()
			self.apply_live(save=False)
			dlg = wx.GetTopLevelParent(self)
			if hasattr(dlg, "_markDirty"):
				dlg._markDirty()
		except Exception:
			log.exception("ClassicSpeech speech timing live apply failed")

	def get_working_shape_config(self):
		self._refreshShapeFromControls()
		return copy.deepcopy(self.shapeConfig)

	def apply_live(self, save=False):
		_save_shape_config(self.shapeConfig) if save else _preview_shape_config(self.shapeConfig)

	def reset_to_defaults(self):
		verbosity = _get_live_verbosity_manager()
		if verbosity is not None and hasattr(verbosity, "reset_shape_config"):
			self.shapeConfig = verbosity.reset_shape_config(save=False)
		else:
			self.shapeConfig = _clone_shape_from_manager()
		self.shapeConfig["pauseMode"] = PAUSE_MODE_GLOBAL
		self.shapeConfig["pausePlacement"] = PAUSE_PLACEMENT_BEFORE
		self.shapeConfig["pauses"] = {tokenKind: TOKEN_PAUSE_USE_GLOBAL for tokenKind in TOKEN_ORDER_KINDS}
		self._loadControlsFromShape()
		self.apply_live(save=False)
