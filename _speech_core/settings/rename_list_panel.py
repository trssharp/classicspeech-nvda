import wx

from ..localization import _

try:
	from gui import nvdaControls
except Exception:
	nvdaControls = None



class RenameListPanel(wx.Panel):
	def __init__(
		self,
		parent,
		title,
		labels,
		renames,
		mutedLabels=None,
		onChange=None,
		displayLabels=None,
		helpText=None,
		compactDisplay=False,
		renamePromptTitle=None,
		renamePromptMessage=None,
		renameMenuLabel=_("Rename	F2"),
		clearRenameMenuLabel=_("Clear Rename	Delete"),
		checkedActionCaption=_("Unmute"),
		uncheckedActionCaption=_("Mute"),
		customDisplaySuffix=_("renamed to {text}"),
	):
		super().__init__(parent)

		self._labels = list(labels)
		self._workingRenames = dict(renames)
		self._workingMuted = set(mutedLabels or [])
		self._displayLabels = dict(displayLabels or {})
		self._onChange = onChange
		self._suspendEvents = False
		# Deferred native checklist reads must belong to the current population.
		# A queued callback may otherwise run after a dialog reload or destruction.
		self._checklistSyncGeneration = 0
		self._checklistSyncDestroyed = False
		self._compactDisplay = bool(compactDisplay)
		self._renamePromptTitle = renamePromptTitle
		self._renamePromptMessage = renamePromptMessage
		self._renameMenuLabel = renameMenuLabel
		self._clearRenameMenuLabel = clearRenameMenuLabel
		self._checkedActionCaption = checkedActionCaption
		self._uncheckedActionCaption = uncheckedActionCaption
		self._customDisplaySuffix = customDisplaySuffix

		mainSizer = wx.BoxSizer(wx.VERTICAL)

		labelCtrl = wx.StaticText(self, label=title)
		mainSizer.Add(labelCtrl, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 6)
		if helpText:
			mainSizer.Add(
				wx.StaticText(self, label=helpText),
				0,
				wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND,
				6,
			)

		checkListClass = nvdaControls.CustomCheckListBox if nvdaControls else wx.CheckListBox
		self.listCtrl = checkListClass(self)
		self.listCtrl.SetName(title)
		mainSizer.Add(self.listCtrl, 1, wx.ALL | wx.EXPAND, 6)

		self.SetSizer(mainSizer)

		self.listCtrl.Bind(wx.EVT_LISTBOX, self.onItemSelected)
		self.listCtrl.Bind(wx.EVT_CHECKLISTBOX, self.onChecklistToggled)
		self.listCtrl.Bind(wx.EVT_KEY_DOWN, self.onListKeyDown)
		self.listCtrl.Bind(wx.EVT_CONTEXT_MENU, self.onListContextMenu)
		self.Bind(wx.EVT_WINDOW_DESTROY, self._onChecklistDestroy)
		self.populate()

	def _statusFor(self, label):
		return _("Muted") if label in self._workingMuted else _("Spoken")

	def _spokenBaseFor(self, label):
		return self._displayLabels.get(label, label)

	def _displayTextFor(self, label):
		"""
		Always expose a stable, speakable editor label.

		Do not return the raw canonical label by itself here, because muted labels
		are also used by the runtime speech formatter. If the editor row text is
		exactly the muted label (for example "editable"), the addon can silence the
		management UI itself. Adding lightweight editor context keeps items readable
		inside the list while leaving runtime muting behavior unchanged.
		"""
		status = self._statusFor(label).lower()
		display = self._spokenBaseFor(label)
		rename = self._workingRenames.get(label, "").strip()
		if self._compactDisplay:
			if rename:
				return f"{display}, {self._customDisplaySuffix.format(text=rename)}"
			return display
		if rename:
			return f"{display}, {status}, {self._customDisplaySuffix.format(text=rename)}"
		return f"{display}, {status}"

	def _invalidateChecklistSync(self):
		self._checklistSyncGeneration = self.__dict__.get("_checklistSyncGeneration", 0) + 1

	def _onChecklistDestroy(self, evt):
		# EVT_WINDOW_DESTROY can be delivered while wx is tearing down the panel.
		# Never let a callback queued before that point touch the dead checklist.
		if evt is None or not hasattr(evt, "GetEventObject") or evt.GetEventObject() is self:
			self._checklistSyncDestroyed = True
			self._invalidateChecklistSync()
		if evt is not None and hasattr(evt, "Skip"):
			evt.Skip()

	def populate(self):
		self._invalidateChecklistSync()
		selection = self.listCtrl.GetSelection()
		self._suspendEvents = True
		try:
			self.listCtrl.Clear()
			for idx, label in enumerate(self._labels):
				self.listCtrl.Append(self._displayTextFor(label))
				self.listCtrl.Check(idx, check=(label not in self._workingMuted))
			if self._labels:
				if selection == wx.NOT_FOUND or selection >= len(self._labels):
					selection = 0
				self.listCtrl.SetSelection(selection)
		finally:
			self._suspendEvents = False

	def loadData(self, renames: dict, mutedLabels=None):
		self._invalidateChecklistSync()
		self._workingRenames = dict(renames)
		self._workingMuted = set(mutedLabels or [])
		self.populate()

	def _getSelectedIndex(self):
		idx = self.listCtrl.GetSelection()
		return -1 if idx == wx.NOT_FOUND else idx

	def _getSelectedLabel(self):
		idx = self._getSelectedIndex()
		if idx == -1 or idx >= len(self._labels):
			return None
		return self._labels[idx]

	def onItemSelected(self, evt):
		# Selection alone does not change data, but keeping the handler makes future hooks easier.
		if evt:
			evt.Skip()

	def _selectIndex(self, idx):
		if idx < 0 or idx >= len(self._labels):
			return
		self.listCtrl.SetSelection(idx)
		self.listCtrl.SetFocus()

	def _promptForRename(self, label):
		current = self._workingRenames.get(label, "")
		display = self._spokenBaseFor(label)
		message = self._renamePromptMessage or "Rename the spoken label for '{display}'. Leave blank to clear the rename."
		if callable(message):
			message = message(display)
		else:
			message = message.format(display=display)
		title = self._renamePromptTitle or f"Rename {display}"
		if callable(title):
			title = title(display)
		else:
			title = title.format(display=display)
		dlg = wx.TextEntryDialog(
			self,
			message,
			title,
			value=current,
		)
		try:
			if dlg.ShowModal() != wx.ID_OK:
				return False
			newValue = dlg.GetValue().strip()
		finally:
			dlg.Destroy()

		if newValue:
			self._workingRenames[label] = newValue
		else:
			self._workingRenames.pop(label, None)

		idx = self._getSelectedIndex()
		self.populate()
		if idx != -1:
			self._selectIndex(idx)
		self._notifyChanged()
		return True

	def onRenameFromList(self, evt):
		label = self._getSelectedLabel()
		if not label:
			wx.Bell()
			return
		self._promptForRename(label)

	def onListKeyDown(self, evt):
		key = evt.GetKeyCode()
		if key == wx.WXK_DELETE:
			self.onClearRename(None)
			return
		if key == wx.WXK_F2:
			self.onRenameFromList(None)
			return
		# Let the native checklistbox handle Space so EVT_CHECKLISTBOX fires.
		evt.Skip()

	def onListContextMenu(self, evt):
		label = self._getSelectedLabel()
		if not label:
			return

		menu = wx.Menu()
		renameItem = menu.Append(wx.ID_ANY, self._renameMenuLabel)
		clearItem = menu.Append(wx.ID_ANY, self._clearRenameMenuLabel)
		toggleLabel = self._checkedActionCaption if label in self._workingMuted else self._uncheckedActionCaption
		muteItem = menu.Append(wx.ID_ANY, toggleLabel)

		menu.Bind(wx.EVT_MENU, lambda e: self.onRenameFromList(None), renameItem)
		menu.Bind(wx.EVT_MENU, lambda e: self.onClearRename(None), clearItem)
		menu.Bind(wx.EVT_MENU, lambda e: self.onToggleMute(None), muteItem)
		try:
			self.PopupMenu(menu)
		finally:
			menu.Destroy()

	def _notifyChanged(self):
		if self._onChange:
			self._onChange()

	def onClearRename(self, evt):
		label = self._getSelectedLabel()
		if not label:
			wx.Bell()
			return

		self._workingRenames.pop(label, None)
		idx = self._getSelectedIndex()
		self.populate()
		if idx != -1:
			self._selectIndex(idx)
		self._notifyChanged()

	def _refreshSingleRow(self, idx):
		if idx < 0 or idx >= len(self._labels):
			return
		label = self._labels[idx]
		# Update the existing row in place instead of rebuilding/reselecting the
		# checklist. Native checkbox state announcement is sufficient here.
		self._suspendEvents = True
		try:
			self.listCtrl.SetString(idx, self._displayTextFor(label))
			self.listCtrl.Check(idx, check=(label not in self._workingMuted))
		finally:
			self._suspendEvents = False

	def _setMutedState(self, label, muted):
		if muted:
			self._workingMuted.add(label)
		else:
			self._workingMuted.discard(label)
		idx = self._labels.index(label)
		self._refreshSingleRow(idx)
		self._selectIndex(idx)
		self._notifyChanged()

	def onChecklistToggled(self, evt):
		# CustomCheckListBox also handles this event to emit NVDA accessibility
		# state-change notifications. Propagate it even while programmatic updates
		# are suspended; suspension only suppresses ClassicSpeech state changes.
		if evt is not None and hasattr(evt, "Skip"):
			evt.Skip()
		if self._suspendEvents:
			return
		idx = evt.GetInt() if evt else self._getSelectedIndex()
		# NVDA's CustomCheckListBox receives this event before its native checked
		# state has flipped. Reading IsChecked here loses a just-checked item when
		# the parent dialog saves its live transaction. Let the native handler run
		# first, then synchronize ClassicSpeech state and notify exactly once.
		generation = self.__dict__.get("_checklistSyncGeneration", 0)
		wx.CallAfter(self._syncChecklistToggled, idx, generation)

	def _syncChecklistToggled(self, idx, generation):
		# Deferred work can outlive a repopulation, reload, or window teardown.
		# Only the exact checklist generation that queued the work may synchronize.
		if (
			self.__dict__.get("_checklistSyncDestroyed", False)
			or generation != self.__dict__.get("_checklistSyncGeneration", 0)
			or self._suspendEvents
		):
			return
		if idx == -1 or idx >= len(self._labels):
			return
		try:
			checked = bool(self.listCtrl.IsChecked(idx))
		except Exception:
			# wx may have deleted the native control before its destroy event reaches
			# this panel. A stale callback must not escape into the event loop.
			return
		if (
			self.__dict__.get("_checklistSyncDestroyed", False)
			or generation != self.__dict__.get("_checklistSyncGeneration", 0)
			or self._suspendEvents
		):
			return
		label = self._labels[idx]
		if checked:
			self._workingMuted.discard(label)
		else:
			self._workingMuted.add(label)
		# Refresh only this row. A full populate/reselect makes NVDA speak the row
		# immediately after the explicit confirmation, which sounds like a double
		# announcement.
		self._refreshSingleRow(idx)
		self._notifyChanged()

	def onToggleMute(self, evt):
		label = self._getSelectedLabel()
		if not label:
			wx.Bell()
			return
		self._setMutedState(label, muted=(label not in self._workingMuted))

	def getRenames(self):
		return dict(self._workingRenames)

	def getMutedLabels(self):
		return sorted(self._workingMuted, key=str.lower)
