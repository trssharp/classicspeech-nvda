import wx

try:
	from gui import nvdaControls
except Exception:
	nvdaControls = None



class RenameListPanel(wx.Panel):
	def __init__(self, parent, title, labels, renames, mutedLabels=None, onChange=None, displayLabels=None, helpText=None):
		super().__init__(parent)

		self._labels = list(labels)
		self._workingRenames = dict(renames)
		self._workingMuted = set(mutedLabels or [])
		self._displayLabels = dict(displayLabels or {})
		self._onChange = onChange
		self._suspendEvents = False

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
		self.populate()

	def _statusFor(self, label):
		return "Muted" if label in self._workingMuted else "Spoken"

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
		if rename:
			return f"{display}, {status}, renamed to {rename}"
		return f"{display}, {status}"

	def populate(self):
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
		dlg = wx.TextEntryDialog(
			self,
			f"Rename the spoken label for '{display}'. Leave blank to clear the rename.",
			f"Rename {display}",
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
		renameItem = menu.Append(wx.ID_ANY, "Rename	F2")
		clearItem = menu.Append(wx.ID_ANY, "Clear Rename	Delete")
		muteLabel = "Unmute" if label in self._workingMuted else "Mute"
		muteItem = menu.Append(wx.ID_ANY, muteLabel)

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
		if self._suspendEvents:
			return
		idx = evt.GetInt() if evt else self._getSelectedIndex()
		if idx == -1 or idx >= len(self._labels):
			return
		label = self._labels[idx]
		checked = bool(self.listCtrl.IsChecked(idx))
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
