from ..localization import _

import copy

import wx
import logHandler

try:
	from gui import nvdaControls
except Exception:
	nvdaControls = None

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
	PROFILE_NAME_CHOICES,
	PROFILE_NAMES,
)

log = logHandler.log


def _profile_name_from_choice(choice, currentProfile):
	selection = choice.GetSelection()
	if selection < 0 or selection >= len(PROFILE_NAME_CHOICES):
		return currentProfile
	return PROFILE_NAME_CHOICES[selection][1]

class VerbosityPanel(wx.Panel):
	TOKEN_DEFS = [
		("name", _("Name")),
		("role", _("Role")),
		("state", _("State")),
		("description", _("Description")),
		("tooltip", _("Tooltip")),
	]

	def __init__(self, parent):
		super().__init__(parent)

		self.currentEditProfile = _get_active_profile_name()
		self.profileConfig = _clone_profile_from_manager(self.currentEditProfile)
		self.profileBehavior = _get_profile_behavior(self.currentEditProfile)
		self._description = (
			_("Choose the active verbosity profile and which object details ClassicSpeech speaks for that profile.")
		)
		_set_panel_description(self, _("Verbosity"), self._description)

		mainSizer = wx.BoxSizer(wx.VERTICAL)

		mainSizer.Add(
			wx.StaticText(self, label=self._description),
			0,
			wx.ALL | wx.EXPAND,
			8,
		)

		grid = wx.FlexGridSizer(cols=2, vgap=10, hgap=10)
		grid.AddGrowableCol(1, 1)

		grid.Add(wx.StaticText(self, label=_("Active profile:")), 0, wx.ALIGN_CENTER_VERTICAL)
		self.activeProfileChoice = wx.Choice(
			self,
			choices=[label for label, _profileName in PROFILE_NAME_CHOICES],
		)
		self.activeProfileChoice.SetName(_("Active profile"))
		self.activeProfileChoice.SetSelection(PROFILE_NAMES.index(self.currentEditProfile))
		grid.Add(self.activeProfileChoice, 1, wx.EXPAND)

		mainSizer.Add(grid, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		tokenInfo = wx.StaticText(self, label=_("Spoken object details:"))
		mainSizer.Add(tokenInfo, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 8)

		checkListClass = nvdaControls.CustomCheckListBox if nvdaControls else wx.CheckListBox
		self.tokenList = checkListClass(
			self,
			choices=[label for _tokenKind, label in self.TOKEN_DEFS],
		)
		self.tokenList.SetName(_("Spoken object details"))
		mainSizer.Add(self.tokenList, 0, wx.ALL | wx.EXPAND, 8)

		positionGrid = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
		positionGrid.AddGrowableCol(1, 1)
		positionGrid.Add(wx.StaticText(self, label=_("Position announcements:")), 0, wx.ALIGN_CENTER_VERTICAL)
		self.positionModeChoice = wx.Choice(
			self,
			choices=[
				_("Off"),
				_("Announce only first item"),
				_("Announce on every move"),
			],
		)
		self.positionModeChoice.SetName(_("Position announcements"))
		self._loadPositionModeChoice()
		positionGrid.Add(self.positionModeChoice, 1, wx.EXPAND)
		mainSizer.Add(positionGrid, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)
		self.SetSizer(mainSizer)

		self._loadEditorsFromProfileConfig()

		self.activeProfileChoice.Bind(wx.EVT_CHOICE, self.onActiveProfileChanged)
		self.positionModeChoice.Bind(wx.EVT_CHOICE, self.onInlineProfileChanged)
		self.tokenList.Bind(wx.EVT_CHECKLISTBOX, self.onTokenListChanged)

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
		enabled["position"] = True
		enabled["value"] = True
		checkedItems = set(self.tokenList.GetCheckedItems())
		for index, (tokenKind, _label) in enumerate(VerbosityPanel.TOKEN_DEFS):
			enabled[tokenKind] = index in checkedItems
		profile["enabledTokens"] = enabled
		self.profileConfig = profile

		behavior = dict(self.profileBehavior)
		behavior["positionMode"] = self._getPositionModeFromChoice()
		self.profileBehavior = behavior

	def _loadEditorsFromProfileConfig(self):
		enabled = self.profileConfig.get("enabledTokens", {})
		for index, (tokenKind, _label) in enumerate(VerbosityPanel.TOKEN_DEFS):
			self.tokenList.Check(index, check=bool(enabled.get(tokenKind, True)))

		self._loadPositionModeChoice()

	def onActiveProfileChanged(self, evt=None):
		self.currentEditProfile = _profile_name_from_choice(
			self.activeProfileChoice,
			self.currentEditProfile,
		)
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

	def onTokenListChanged(self, evt=None):
		# Preserve CustomCheckListBox's accessibility state-change notification.
		if evt is not None and hasattr(evt, "Skip"):
			evt.Skip()
		# NVDA's checklist updates its checked state after this event. Defer the
		# live profile update so it reads the new state, not the previous state.
		wx.CallAfter(self.onInlineProfileChanged)

	def apply_live(self, save=True):
		self.currentEditProfile = _profile_name_from_choice(
			self.activeProfileChoice,
			self.currentEditProfile,
		)

		if save:
			_set_active_profile_name(self.currentEditProfile)
			_save_profile_config(self.currentEditProfile, self.profileConfig)
			_save_profile_behavior(self.currentEditProfile, self.profileBehavior)

		_preview_profile_config(self.currentEditProfile, self.profileConfig)
		_apply_profile_behavior_runtime(self.profileConfig, self.profileBehavior)
		_apply_profile_live(self.currentEditProfile)

	def reset_current_profile(self):
		message = _(
			"Reset the {profile} profile to its default settings now?"
			"\n\nThis will immediately clear saved overrides for this profile."
			"\n\nCancel will not undo this reset."
			"\n\nChoose Yes to reset now, or No to keep your current settings."
		).format(profile=self.currentEditProfile)
		result = wx.MessageBox(
			message,
			_("Reset Profile"),
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
		return _profile_name_from_choice(
			self.activeProfileChoice,
			self.currentEditProfile,
		)

	def get_working_profile_config(self):
		self._refreshWorkingConfigFromControls()
		return copy.deepcopy(self.profileConfig)

	def get_working_profile_behavior(self):
		self._refreshWorkingConfigFromControls()
		return copy.deepcopy(self.profileBehavior)
