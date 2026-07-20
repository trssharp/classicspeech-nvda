import copy

import wx
import logHandler

from ..key_labels import get_known_key_labels
from .accessibility import _set_panel_description
from .key_labels_config import (
	_clone_key_label_config,
	_preview_key_label_config,
	_save_key_label_config,
)
from .rename_list_panel import RenameListPanel

log = logHandler.log

class KeyLabelsPanel(wx.Panel):
	def __init__(self, parent):
		super().__init__(parent)

		self.keyLabelConfig = _clone_key_label_config()
		self._description = (
			"Key labels control what ClassicSpeech changes for normal keyboard speech. "
			"Input help is left native and does not use these key-label changes. "
			"They are separate from object speech tokens and hotkey tokens.\n"
			"Space: mute or unmute. F2: rename. Delete: clear rename. Shift+F10: menu."
		)
		_set_panel_description(self, "Key Labels", self._description)
		self.keyRows = get_known_key_labels()
		self.keyNames = [key for key, _label in self.keyRows]
		self.defaultLabels = {key: label for key, label in self.keyRows}

		mainSizer = wx.BoxSizer(wx.VERTICAL)

		mainSizer.Add(
			wx.StaticText(self, label=self._description),
			0,
			wx.ALL | wx.EXPAND,
			8,
		)

		self.keyPanel = RenameListPanel(
			self,
			title="Key labels",
			labels=self.keyNames,
			renames={},
			mutedLabels=[],
			onChange=self.onInlineChanged,
			displayLabels=self.defaultLabels,
		)
		mainSizer.Add(self.keyPanel, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)
		self.SetSizer(mainSizer)

		self._loadEditorsFromConfig()

	def _loadEditorsFromConfig(self):
		renames = dict(self.keyLabelConfig.get("renames", {}))
		muted = list(self.keyLabelConfig.get("mutedLabels", []))
		self.keyPanel.loadData(renames, muted)

	def _refreshWorkingConfigFromControls(self):
		self.keyLabelConfig = {
			"renames": self.keyPanel.getRenames(),
			"mutedLabels": self.keyPanel.getMutedLabels(),
		}

	def onInlineChanged(self, evt=None):
		try:
			self._refreshWorkingConfigFromControls()
			self.apply_live(save=False)
			dlg = wx.GetTopLevelParent(self)
			if hasattr(dlg, "_markDirty"):
				dlg._markDirty()
		except Exception:
			log.exception("ClassicSpeech key label settings live apply failed")

	def apply_live(self, save=True):
		self._refreshWorkingConfigFromControls()
		if save:
			_save_key_label_config(self.keyLabelConfig)
		else:
			_preview_key_label_config(self.keyLabelConfig)

	def reset_key_labels_to_defaults(self):
		message = (
			"Reset key label settings to defaults now?"
			"\n\nThis will immediately clear all custom key renames and muted keys."
			"\n\nCancel will not undo this reset."
			"\n\nChoose Yes to reset now, or No to keep your current settings."
		)
		result = wx.MessageBox(
			message,
			"Reset Key Labels to Defaults",
			wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
			self,
		)
		if result != wx.YES:
			return

		self.keyLabelConfig = {"renames": {}, "mutedLabels": []}
		self._loadEditorsFromConfig()
		self.apply_live(save=True)

	def get_working_key_label_config(self):
		self._refreshWorkingConfigFromControls()
		return copy.deepcopy(self.keyLabelConfig)
