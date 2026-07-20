import copy

import wx
import logHandler

from ..maps import SPOKEN_TO_ROLE, SPOKEN_TO_STATE
from .accessibility import _set_panel_description
from .profile_config import (
	_apply_profile_live,
	_get_active_profile_name,
)
from .shape_config import (
	_clone_shape_from_manager,
	_preview_shape_config,
	_save_shape_config,
)
from .constants import TOKEN_ORDER_ITEMS, TOKEN_ORDER_KINDS, TOKEN_ORDER_LABELS
from .rename_list_panel import RenameListPanel

log = logHandler.log

class TokenEditorPanel(wx.Panel):
	def __init__(self, parent):
		super().__init__(parent)

		self.shapeConfig = _clone_shape_from_manager()
		self._description = (
			"The token editor is global. Use it to rename or mute individual role and state labels "
			"for all verbosity profiles.\n"
			"Use Control+Up and Control+Down to reorder the spoken token sequence.\n"
			"Space: mute or unmute. F2: rename. Delete: clear rename. Shift+F10: menu."
		)
		_set_panel_description(self, "Token Editor", self._description)

		self.roleLabels = sorted(SPOKEN_TO_ROLE.keys(), key=str.lower)
		self.stateLabels = sorted(SPOKEN_TO_STATE.keys(), key=str.lower)

		mainSizer = wx.BoxSizer(wx.VERTICAL)

		mainSizer.Add(
			wx.StaticText(self, label=self._description),
			0,
			wx.ALL | wx.EXPAND,
			8,
		)

		mainSizer.Add(
			wx.StaticText(self, label="Spoken token sequence"),
			0,
			wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND,
			8,
		)
		self.tokenOrderList = wx.ListBox(self, style=wx.LB_SINGLE)
		self.tokenOrderList.SetName("Spoken token sequence")
		mainSizer.Add(self.tokenOrderList, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)
		self.tokenOrderList.Bind(wx.EVT_KEY_DOWN, self.onTokenOrderKeyDown)

		renameRow = wx.BoxSizer(wx.HORIZONTAL)

		self.rolePanel = RenameListPanel(
			self,
			title="Roles",
			labels=self.roleLabels,
			renames={},
			mutedLabels=[],
			onChange=self.onInlineChanged,
		)
		renameRow.Add(self.rolePanel, 1, wx.ALL | wx.EXPAND, 4)

		self.statePanel = RenameListPanel(
			self,
			title="States",
			labels=self.stateLabels,
			renames={},
			mutedLabels=[],
			onChange=self.onInlineChanged,
		)
		renameRow.Add(self.statePanel, 1, wx.ALL | wx.EXPAND, 4)

		mainSizer.Add(renameRow, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)
		self.SetSizer(mainSizer)

		self._loadEditorsFromShapeConfig()

	def _normalizeOrder(self, order):
		clean = []
		seen = set()
		for tokenKind in list(order or []):
			if tokenKind in TOKEN_ORDER_KINDS and tokenKind not in seen:
				clean.append(tokenKind)
				seen.add(tokenKind)
		for tokenKind in TOKEN_ORDER_KINDS:
			if tokenKind not in seen:
				clean.append(tokenKind)
		return clean

	def _loadTokenOrderList(self, order=None):
		order = self._normalizeOrder(order if order is not None else self.shapeConfig.get("order", TOKEN_ORDER_KINDS))
		selection = self.tokenOrderList.GetSelection()
		self.tokenOrderList.Clear()
		for tokenKind in order:
			self.tokenOrderList.Append(TOKEN_ORDER_LABELS.get(tokenKind, tokenKind), clientData=tokenKind)
		if order:
			if selection == wx.NOT_FOUND or selection >= len(order):
				selection = 0
			self.tokenOrderList.SetSelection(selection)

	def _getTokenOrderFromList(self):
		order = []
		for idx in range(self.tokenOrderList.GetCount()):
			tokenKind = self.tokenOrderList.GetClientData(idx)
			if tokenKind is None:
				tokenKind = str(self.tokenOrderList.GetString(idx)).strip().lower()
			order.append(tokenKind)
		return self._normalizeOrder(order)

	def _moveSelectedOrderItem(self, direction):
		idx = self.tokenOrderList.GetSelection()
		if idx == wx.NOT_FOUND:
			return
		target = idx + int(direction)
		count = self.tokenOrderList.GetCount()
		if target < 0 or target >= count:
			return
		order = self._getTokenOrderFromList()
		order[idx], order[target] = order[target], order[idx]
		self._loadTokenOrderList(order)
		self.tokenOrderList.SetSelection(target)
		self.tokenOrderList.SetFocus()
		self.onInlineChanged()

	def onTokenOrderKeyDown(self, evt):
		key = evt.GetKeyCode()
		controlDown = evt.ControlDown() or evt.CmdDown()
		if controlDown and key == wx.WXK_UP:
			self._moveSelectedOrderItem(-1)
			return
		if controlDown and key == wx.WXK_DOWN:
			self._moveSelectedOrderItem(1)
			return
		evt.Skip()

	def _rebuildMergedRenames(self):
		merged = dict(self.shapeConfig.get("renames", {}))

		for key in list(merged.keys()):
			if key in SPOKEN_TO_ROLE or key in SPOKEN_TO_STATE:
				merged.pop(key, None)

		merged.update(self.rolePanel.getRenames())
		merged.update(self.statePanel.getRenames())
		return merged

	def _rebuildMutedLabels(self):
		muted = set(self.shapeConfig.get("mutedLabels", []))

		for label in list(muted):
			if label in SPOKEN_TO_ROLE or label in SPOKEN_TO_STATE:
				muted.discard(label)

		muted.update(self.rolePanel.getMutedLabels())
		muted.update(self.statePanel.getMutedLabels())
		return sorted(muted, key=str.lower)

	def _refreshWorkingConfigFromControls(self):
		shape = copy.deepcopy(self.shapeConfig)
		shape["order"] = self._getTokenOrderFromList()
		shape["renames"] = self._rebuildMergedRenames()
		shape["mutedLabels"] = self._rebuildMutedLabels()
		self.shapeConfig = shape

	def _loadEditorsFromShapeConfig(self):
		renames = dict(self.shapeConfig.get("renames", {}))
		mutedLabels = set(self.shapeConfig.get("mutedLabels", []))
		roleRenames = {k: v for k, v in renames.items() if k in SPOKEN_TO_ROLE}
		stateRenames = {k: v for k, v in renames.items() if k in SPOKEN_TO_STATE}
		roleMuted = [label for label in mutedLabels if label in SPOKEN_TO_ROLE]
		stateMuted = [label for label in mutedLabels if label in SPOKEN_TO_STATE]
		self._loadTokenOrderList(self.shapeConfig.get("order", TOKEN_ORDER_KINDS))
		self.rolePanel.loadData(roleRenames, roleMuted)
		self.statePanel.loadData(stateRenames, stateMuted)

	def refresh_from_global_shape(self):
		self.shapeConfig = _clone_shape_from_manager()
		self._loadEditorsFromShapeConfig()
		self.Layout()

	def onInlineChanged(self, evt=None):
		try:
			self._refreshWorkingConfigFromControls()
			self.apply_live(save=False)
			dlg = wx.GetTopLevelParent(self)
			if hasattr(dlg, "_markDirty"):
				dlg._markDirty()
		except Exception:
			log.exception("ClassicSpeech token editor live apply failed")

	def apply_live(self, save=True):
		self._refreshWorkingConfigFromControls()
		order = self._getTokenOrderFromList()
		renames = self._rebuildMergedRenames()
		mutedLabels = self._rebuildMutedLabels()

		self.shapeConfig["order"] = list(order)
		self.shapeConfig["renames"] = dict(renames)
		self.shapeConfig["mutedLabels"] = list(mutedLabels)

		if save:
			_save_shape_config(self.shapeConfig)
			_apply_profile_live(_get_active_profile_name())
		else:
			_preview_shape_config(self.shapeConfig)

	def reset_tokens_to_defaults(self):
		message = (
			"Reset token editor settings to defaults now?"
			"\n\nThis will immediately clear all global token renames and muted labels, "
			"and restore the default token order."
			"\n\nCancel will not undo this reset."
			"\n\nChoose Yes to reset now, or No to keep your current settings."
		)
		result = wx.MessageBox(
			message,
			"Reset Tokens to Defaults",
			wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
			self,
		)
		if result != wx.YES:
			return

		shape = copy.deepcopy(self.shapeConfig)
		shape["order"] = list(TOKEN_ORDER_KINDS)
		shape["renames"] = {}
		shape["mutedLabels"] = []
		self.shapeConfig = shape
		self._loadEditorsFromShapeConfig()
		self.apply_live(save=True)

	def get_working_order(self):
		self._refreshWorkingConfigFromControls()
		return list(self.shapeConfig.get("order", TOKEN_ORDER_KINDS))

	def get_working_renames(self):
		self._refreshWorkingConfigFromControls()
		return dict(self.shapeConfig.get("renames", {}))

	def get_working_muted_labels(self):
		self._refreshWorkingConfigFromControls()
		return list(self.shapeConfig.get("mutedLabels", []))
