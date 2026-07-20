import copy

import wx
import logHandler

from .accessibility import _set_panel_description
from .profile_config import (
	_apply_profile_behavior_runtime,
	_apply_profile_live,
	_clear_profile_behavior_override,
	_clear_profile_override,
	_clone_profile_from_manager,
	_get_active_profile_name,
	_get_profile_behavior,
	_preview_profile_config,
	_save_profile_behavior,
	_save_profile_config,
	_set_active_profile_name,
)
from .constants import (
	POSITION_MODE_EACH,
	POSITION_MODE_FIRST,
	POSITION_MODE_OFF,
	PROFILE_NAMES,
)

log = logHandler.log

class VerbosityPanel(wx.Panel):
	TOKEN_DEFS = [
		("role", "Role"),
		("state", "State"),
		("description", "Description"),
		("tooltip", "Tooltip"),
	]

	def __init__(self, parent):
		super().__init__(parent)

		self.currentEditProfile = _get_active_profile_name()
		self.profileConfig = _clone_profile_from_manager(self.currentEditProfile)
		self.profileBehavior = _get_profile_behavior(self.currentEditProfile)
		self._description = (
			"Choose the active verbosity profile and which object details ClassicSpeech speaks for that profile."
		)
		_set_panel_description(self, "Verbosity", self._description)

		mainSizer = wx.BoxSizer(wx.VERTICAL)

		mainSizer.Add(
			wx.StaticText(self, label=self._description),
			0,
			wx.ALL | wx.EXPAND,
			8,
		)

		grid = wx.FlexGridSizer(cols=2, vgap=10, hgap=10)
		grid.AddGrowableCol(1, 1)

		grid.Add(wx.StaticText(self, label="Active profile:"), 0, wx.ALIGN_CENTER_VERTICAL)
		self.activeProfileChoice = wx.Choice(self, choices=PROFILE_NAMES)
		self.activeProfileChoice.SetName("Active profile")
		self.activeProfileChoice.SetStringSelection(self.currentEditProfile)
		grid.Add(self.activeProfileChoice, 1, wx.EXPAND)

		mainSizer.Add(grid, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		tokenInfo = wx.StaticText(
			self,
			label="Select the items you want spoken for the selected profile.",
		)
		mainSizer.Add(tokenInfo, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 8)

		self.tokenChecks = {}
		tokenGrid = wx.GridSizer(rows=0, cols=2, vgap=6, hgap=20)
		for tokenKind, label in self.TOKEN_DEFS:
			chk = wx.CheckBox(self, label=label)
			self.tokenChecks[tokenKind] = chk
			tokenGrid.Add(chk, 0, wx.EXPAND)

		mainSizer.Add(tokenGrid, 0, wx.ALL | wx.EXPAND, 8)

		positionGrid = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
		positionGrid.AddGrowableCol(1, 1)
		positionGrid.Add(wx.StaticText(self, label="Position announcements:"), 0, wx.ALIGN_CENTER_VERTICAL)
		self.positionModeChoice = wx.Choice(
			self,
			choices=[
				"Off",
				"Announce only first item",
				"Announce on every move",
			],
		)
		self.positionModeChoice.SetName("Position announcements")
		self._loadPositionModeChoice()
		positionGrid.Add(self.positionModeChoice, 1, wx.EXPAND)
		mainSizer.Add(positionGrid, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)
		self.SetSizer(mainSizer)

		self._loadEditorsFromProfileConfig()

		self.activeProfileChoice.Bind(wx.EVT_CHOICE, self.onActiveProfileChanged)
		self.positionModeChoice.Bind(wx.EVT_CHOICE, self.onInlineProfileChanged)
		for chk in self.tokenChecks.values():
			chk.Bind(wx.EVT_CHECKBOX, self.onInlineProfileChanged)

	def _getPositionModeFromChoice(self):
		selection = self.positionModeChoice.GetSelection()
		if selection == 0:
			return POSITION_MODE_OFF
		if selection == 1:
			return POSITION_MODE_FIRST
		return POSITION_MODE_EACH

	def _loadPositionModeChoice(self):
		mode = str(self.profileBehavior.get("positionMode", POSITION_MODE_EACH))
		if mode == POSITION_MODE_OFF:
			self.positionModeChoice.SetSelection(0)
		elif mode == POSITION_MODE_FIRST:
			self.positionModeChoice.SetSelection(1)
		else:
			self.positionModeChoice.SetSelection(2)

	def _refreshWorkingConfigFromControls(self):
		profile = copy.deepcopy(self.profileConfig)
		enabled = dict(profile.get("enabledTokens", {}))
		enabled["name"] = True
		enabled["position"] = True
		enabled["value"] = True
		for tokenKind, chk in self.tokenChecks.items():
			enabled[tokenKind] = chk.GetValue()
		profile["enabledTokens"] = enabled
		self.profileConfig = profile

		behavior = dict(self.profileBehavior)
		behavior["positionMode"] = self._getPositionModeFromChoice()
		self.profileBehavior = behavior

	def _loadEditorsFromProfileConfig(self):
		enabled = self.profileConfig.get("enabledTokens", {})
		for tokenKind, chk in self.tokenChecks.items():
			chk.SetValue(bool(enabled.get(tokenKind, True)))

		self._loadPositionModeChoice()

	def onActiveProfileChanged(self, evt=None):
		self.currentEditProfile = self.activeProfileChoice.GetStringSelection()
		self.profileConfig = _clone_profile_from_manager(self.currentEditProfile)
		self.profileBehavior = _get_profile_behavior(self.currentEditProfile)
		self._loadEditorsFromProfileConfig()

		try:
			dlg = wx.GetTopLevelParent(self)
			if hasattr(dlg, "sync_edit_profile"):
				dlg.sync_edit_profile(self.currentEditProfile)
		except Exception:
			log.exception("ClassicSpeech: failed to sync active profile to token editor")

		try:
			self.apply_live(save=False)
			dlg = wx.GetTopLevelParent(self)
			if hasattr(dlg, "_markDirty"):
				dlg._markDirty()
		except Exception:
			log.exception("ClassicSpeech active profile switch failed")

	def onInlineProfileChanged(self, evt=None):
		try:
			self._refreshWorkingConfigFromControls()
			self.apply_live(save=False)
			dlg = wx.GetTopLevelParent(self)
			if hasattr(dlg, "_markDirty"):
				dlg._markDirty()
		except Exception:
			log.exception("ClassicSpeech verbosity settings live apply failed")

	def apply_live(self, save=True):
		self.currentEditProfile = self.activeProfileChoice.GetStringSelection()

		if save:
			_set_active_profile_name(self.currentEditProfile)
			_save_profile_config(self.currentEditProfile, self.profileConfig)
			_save_profile_behavior(self.currentEditProfile, self.profileBehavior)

		_preview_profile_config(self.currentEditProfile, self.profileConfig)
		_apply_profile_behavior_runtime(self.profileConfig, self.profileBehavior)
		_apply_profile_live(self.currentEditProfile)

	def reset_current_profile(self):
		message = (
			f"Reset the {self.currentEditProfile} profile to its default settings now?"
			"\n\nThis will immediately clear saved overrides for this profile."
			"\n\nCancel will not undo this reset."
			"\n\nChoose Yes to reset now, or No to keep your current settings."
		)
		result = wx.MessageBox(
			message,
			"Reset Profile",
			wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
			self,
		)
		if result != wx.YES:
			return

		_clear_profile_override(self.currentEditProfile)
		_clear_profile_behavior_override(self.currentEditProfile)
		self.profileConfig = _clone_profile_from_manager(self.currentEditProfile)
		self.profileBehavior = _get_profile_behavior(self.currentEditProfile)
		self._loadEditorsFromProfileConfig()
		self.apply_live(save=True)

	def get_working_profile_name(self):
		return self.activeProfileChoice.GetStringSelection()

	def get_working_profile_config(self):
		self._refreshWorkingConfigFromControls()
		return copy.deepcopy(self.profileConfig)

	def get_working_profile_behavior(self):
		self._refreshWorkingConfigFromControls()
		return copy.deepcopy(self.profileBehavior)
