import wx
import gui
import config
import logHandler
from gui import guiHelper, nvdaControls
from wx.lib import scrolledpanel

from ..web_summary import SUMMARY_ITEM_TYPES
from .web_summary_config import (
    PAGE_LOAD_SUMMARY_MODE_AFTER_READY,
    PAGE_LOAD_SUMMARY_MODE_NATIVE,
    PAGE_LOAD_SUMMARY_MODE_ORIENTATION,
    get_page_load_summary_mode,
    get_page_entry_summary_delay_seconds,
    get_notify_when_page_ready,
    get_page_ready_message,
    get_included_element_types,
    get_include_document_title,
    capture_page_summary_state,
    restore_page_summary_state,
    set_page_load_summary_mode,
    set_page_entry_summary_delay_seconds,
    set_notify_when_page_ready,
    set_page_ready_message,
    set_included_element_types,
    set_include_document_title,
)
from .web_formatting_config import (
	WEB_DOCUMENT_FORMATTING_KEYS,
	capture_web_browse_state,
	get_annotation_setting,
	get_virtual_buffer_setting,
	get_web_document_formatting_setting,
	restore_web_browse_state,
	set_annotation_setting,
	set_virtual_buffer_setting,
	set_web_document_formatting_setting,
)
from .edge_notifications_config import (
	capture_edge_notification_state,
	get_custom_messages,
	get_enabled_activity_ids,
	restore_edge_notification_state,
	set_custom_messages,
	set_enabled_activity_ids,
)
from .edge_notifications_panel import EdgeNotificationsPanel
from .dialog_transactions import SettingsDialogTransactionMixin

log = logHandler.log


def _is_checked(control):
	if hasattr(control, "IsChecked"):
		return control.IsChecked()
	return bool(control.GetValue())


def _checked_items(control):
	if hasattr(control, "GetCheckedItems"):
		return list(control.GetCheckedItems())
	if hasattr(control, "CheckedItems"):
		return list(control.CheckedItems)
	return [
		index
		for index in range(control.GetCount())
		if hasattr(control, "IsChecked") and control.IsChecked(index)
	]


class WebBrowseSettingsDialog(SettingsDialogTransactionMixin, wx.Dialog):
	"""ClassicSpeech dialog for native NVDA web and browse-mode settings."""

	CATEGORY_NAMES = [
		"Browse Mode",
		"Web Element Reporting",
		"Page Summary",
		"Microsoft Edge Notifications",
	]

	def __init__(self, parent):
		super().__init__(
			parent,
			title="ClassicSpeech Web / Browse Mode Settings",
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX,
		)
		self.SetName("ClassicSpeechWebBrowseSettingsDialog")
		self._popupReleased = False
		self._committed = False
		self._initializeDialogTransaction()
		self._browseModeElements = self._get_browse_mode_touch_elements()

		outerSizer = wx.BoxSizer(wx.VERTICAL)
		contentSizer = wx.BoxSizer(wx.HORIZONTAL)

		leftSizer = wx.BoxSizer(wx.VERTICAL)
		self.categoryLabel = wx.StaticText(self, label="Categories")
		leftSizer.Add(self.categoryLabel, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		listClass = nvdaControls.AutoWidthColumnListCtrl if nvdaControls else wx.ListCtrl
		self.categoryList = listClass(
			self,
			style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER,
			size=(240, -1),
		)
		self.categoryList.SetName("Categories")
		self.categoryList.InsertColumn(0, "Categories")
		for categoryName in self.CATEGORY_NAMES:
			self.categoryList.Append((categoryName,))
		self.categoryList.Select(0)
		self.categoryList.Focus(0)
		leftSizer.Add(self.categoryList, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)
		contentSizer.Add(leftSizer, 0, wx.ALL | wx.EXPAND, 8)

		rightSizer = wx.BoxSizer(wx.VERTICAL)
		self.panelHost = wx.Panel(self, style=wx.TAB_TRAVERSAL | wx.BORDER_THEME)
		self.panelHostSizer = wx.BoxSizer(wx.VERTICAL)
		self.panelHost.SetSizer(self.panelHostSizer)

		self.browseModePanel = scrolledpanel.ScrolledPanel(self.panelHost, style=wx.TAB_TRAVERSAL)
		self.webReportingPanel = scrolledpanel.ScrolledPanel(self.panelHost, style=wx.TAB_TRAVERSAL)
		self.pageSummaryPanel = scrolledpanel.ScrolledPanel(self.panelHost, style=wx.TAB_TRAVERSAL)
		self.edgeNotificationsPanel = scrolledpanel.ScrolledPanel(self.panelHost, style=wx.TAB_TRAVERSAL)
		self._make_browse_mode_panel(self.browseModePanel)
		self._make_web_reporting_panel(self.webReportingPanel)
		self._make_page_summary_panel(self.pageSummaryPanel)
		self._make_edge_notifications_panel(self.edgeNotificationsPanel)
		self.dynamicPanels = [self.browseModePanel, self.webReportingPanel, self.pageSummaryPanel, self.edgeNotificationsPanel]

		for panel in self.dynamicPanels:
			self.panelHostSizer.Add(panel, 1, wx.EXPAND)
			panel.Hide()
		self.browseModePanel.Show()

		rightSizer.Add(self.panelHost, 1, wx.ALL | wx.EXPAND, 8)
		contentSizer.Add(rightSizer, 1, wx.ALL | wx.EXPAND, 8)
		outerSizer.Add(contentSizer, 1, wx.EXPAND)

		bottomRow = wx.BoxSizer(wx.HORIZONTAL)
		bottomRow.AddStretchSpacer()
		self.okBtn = wx.Button(self, wx.ID_OK, label="OK")
		self.cancelBtn = wx.Button(self, wx.ID_CANCEL, label="Cancel")
		self.applyBtn = wx.Button(self, label="Apply")
		self.applyBtn.Hide()
		self.okBtn.SetDefault()
		bottomRow.Add(self.okBtn, 0, wx.ALL, 8)
		bottomRow.Add(self.cancelBtn, 0, wx.ALL, 8)
		bottomRow.Add(self.applyBtn, 0, wx.ALL, 8)
		outerSizer.Add(bottomRow, 0, wx.EXPAND)

		self.SetSizer(outerSizer)
		self.SetEscapeId(wx.ID_CANCEL)
		self.SetMinSize((800, 560))
		self.SetSize((980, 700))
		self.CentreOnParent()

		self.categoryList.Bind(wx.EVT_LIST_ITEM_FOCUSED, self.onCategoryChanged)
		self.applyBtn.Bind(wx.EVT_BUTTON, self.onApply)
		self.okBtn.Bind(wx.EVT_BUTTON, self.onOK)
		self.cancelBtn.Bind(wx.EVT_BUTTON, self.onCancel)
		self.applyBtn.MoveAfterInTabOrder(self.cancelBtn)
		self.Bind(wx.EVT_CLOSE, self.onClose)
		self._clearDirty()
		wx.CallAfter(self._setInitialFocus)

	def _get_browse_mode_touch_elements(self):
		try:
			import browseMode

			return list(browseMode.BrowseModeTreeInterceptor._browseTouchNavRegistry)
		except Exception:
			return [
				("heading", "Headings"),
				("link", "Links"),
				("formField", "Form fields"),
				("list", "Lists"),
				("table", "Tables"),
			]

	def _add_static_box_group(self, panel, sHelper, label):
		groupSizer = wx.StaticBoxSizer(wx.VERTICAL, panel, label=label)
		groupBox = groupSizer.GetStaticBox()
		group = guiHelper.BoxSizerHelper(panel, sizer=groupSizer)
		sHelper.addItem(group)
		return group, groupBox

	def _make_browse_mode_panel(self, panel):
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		sHelper = guiHelper.BoxSizerHelper(panel, sizer=mainSizer)
		sHelper.addItem(wx.StaticText(
			panel,
			label="Configure native NVDA Browse Mode behavior. These settings write to NVDA's virtualBuffers configuration.",
		))
		group, box = self._add_static_box_group(panel, sHelper, "Browse Mode")

		self.maxLengthEdit = group.addLabeledControl(
			"&Maximum number of characters on one line",
			nvdaControls.SelectOnFocusSpinCtrl,
			min=10,
			max=250,
			initial=get_virtual_buffer_setting("maxLineLength"),
		)
		self.maxLengthEdit.Bind(wx.EVT_TEXT, self.onChanged)
		self.pageLinesEdit = group.addLabeledControl(
			"&Number of lines per page",
			nvdaControls.SelectOnFocusSpinCtrl,
			min=5,
			max=150,
			initial=get_virtual_buffer_setting("linesPerPage"),
		)
		self.pageLinesEdit.Bind(wx.EVT_TEXT, self.onChanged)
		self.useScreenLayoutCheckBox = self._add_browse_checkbox(group, box, "Use &screen layout (when supported)", "useScreenLayout")
		self.enableOnPageLoadCheckBox = self._add_browse_checkbox(group, box, "&Enable browse mode on page load", "enableOnPageLoad")
		self.autoSayAllCheckBox = self._add_browse_checkbox(group, box, "Automatic &Say All on page load", "autoSayAllOnPageLoad")
		self.autoPassThroughOnFocusChangeCheckBox = self._add_browse_checkbox(group, box, "Automatic focus mode for focus changes", "autoPassThroughOnFocusChange")
		self.autoPassThroughOnCaretMoveCheckBox = self._add_browse_checkbox(group, box, "Automatic focus mode for caret movement", "autoPassThroughOnCaretMove")
		self.passThroughAudioIndicationCheckBox = self._add_browse_checkbox(group, box, "Audio indication of focus and browse modes", "passThroughAudioIndication")
		self.trapNonCommandGesturesCheckBox = self._add_browse_checkbox(group, box, "&Trap all non-command gestures from reaching the document", "trapNonCommandGestures")

		self.browseModeTouchNavigationList = group.addLabeledControl(
			"T&ouch navigation elements:",
			nvdaControls.CustomCheckListBox,
			choices=[label for _itemType, label in self._browseModeElements],
		)
		self.browseModeTouchNavigationList.Bind(wx.EVT_CHECKLISTBOX, self.onTouchNavigationChanged)
		try:
			import touchHandler

			self.browseModeTouchNavigationList.Enable(touchHandler.touchSupported())
		except Exception:
			pass
		enabledTypes = set(get_virtual_buffer_setting("browseModeTouchNavigationElements"))
		for index, (itemType, _label) in enumerate(self._browseModeElements):
			self.browseModeTouchNavigationList.Check(index, itemType in enabledTypes)
		self.loadChromiumBusyCombo = group.addLabeledControl(
			"Load Chromium virtual buffer when document busy.",
			nvdaControls.FeatureFlagCombo,
			keyPath=["virtualBuffers", "loadChromiumVBufOnBusyState"],
			conf=config.conf,
			onChoiceEventHandler=self.onChanged,
		)
		panel.SetSizer(mainSizer)
		panel.SetupScrolling(scroll_x=False)

	def _make_web_reporting_panel(self, panel):
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		sHelper = guiHelper.BoxSizerHelper(panel, sizer=mainSizer)
		sHelper.addItem(wx.StaticText(
			panel,
			label="Configure web-related native NVDA documentFormatting announcements.",
		))
		group, box = self._add_static_box_group(panel, sHelper, "Web Element Reporting")
		self.annotationDetailsCheckBox = self._add_annotation_checkbox(
			group,
			box,
			"Report 'has details' for structured annotations",
			"reportDetails",
		)
		self.ariaDescriptionCheckBox = self._add_annotation_checkbox(
			group,
			box,
			"Report aria-description always",
			"reportAriaDescription",
		)
		self.layoutTablesCheckBox = self._add_web_checkbox(group, box, "Include l&ayout tables", "includeLayoutTables")
		self.headingsCheckBox = self._add_web_checkbox(group, box, "&Headings", "reportHeadings")
		self.linksCheckBox = self._add_web_checkbox(group, box, "Lin&ks", "reportLinks")
		self.linkTypeCheckBox = self._add_web_checkbox(group, box, "Link type", "reportLinkType")
		self.graphicsCheckBox = self._add_web_checkbox(group, box, "&Graphics", "reportGraphics")
		self.listsCheckBox = self._add_web_checkbox(group, box, "&Lists", "reportLists")
		self.blockQuotesCheckBox = self._add_web_checkbox(group, box, "Block &quotes", "reportBlockQuotes")
		self.groupingsCheckBox = self._add_web_checkbox(group, box, "&Groupings", "reportGroupings")
		self.landmarksCheckBox = self._add_web_checkbox(group, box, "Lan&dmarks", "reportLandmarks")
		self.articlesCheckBox = self._add_web_checkbox(group, box, "Arti&cles", "reportArticles")
		self.framesCheckBox = self._add_web_checkbox(group, box, "Fra&mes", "reportFrames")
		self.figuresCheckBox = self._add_web_checkbox(group, box, "Fi&gures", "reportFigures")
		self.clickableCheckBox = self._add_web_checkbox(group, box, "&Clickable", "reportClickable")
		self.brailleLiveRegionsCombo = group.addLabeledControl(
			"Braille report live regions:",
			nvdaControls.FeatureFlagCombo,
			keyPath=["braille", "reportLiveRegions"],
			conf=config.conf,
			onChoiceEventHandler=self.onChanged,
		)
		panel.SetSizer(mainSizer)
		panel.SetupScrolling(scroll_x=False)

	def _make_page_summary_panel(self, panel):
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		sHelper = guiHelper.BoxSizerHelper(panel, sizer=mainSizer)
		sHelper.addItem(wx.StaticText(
			panel,
			label="Choose the Browse Mode element types included when you press NVDA+Shift+U. Checked items are included.",
		))
		group, box = self._add_static_box_group(panel, sHelper, "Page Summary")
		self.notifyWhenPageReadyCheckBox = group.addItem(
			wx.CheckBox(box, label="Notify when page is ready")
		)
		self.notifyWhenPageReadyCheckBox.SetValue(get_notify_when_page_ready())
		self.notifyWhenPageReadyCheckBox.Bind(wx.EVT_CHECKBOX, self.onPageReadyChanged)
		self.pageReadyMessageRow = wx.Panel(box, style=wx.TAB_TRAVERSAL)
		pageReadyMessageSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.pageReadyMessageLabel = wx.StaticText(
			self.pageReadyMessageRow,
			label="Page ready message:",
		)
		self.pageReadyMessageEdit = wx.TextCtrl(
			self.pageReadyMessageRow,
			value=get_page_ready_message(),
		)
		self.pageReadyMessageEdit.SetName("Page ready message:")
		pageReadyMessageSizer.Add(
			self.pageReadyMessageLabel,
			0,
			wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
			8,
		)
		pageReadyMessageSizer.Add(self.pageReadyMessageEdit, 1, wx.EXPAND)
		self.pageReadyMessageRow.SetSizer(pageReadyMessageSizer)
		group.addItem(self.pageReadyMessageRow, flag=wx.EXPAND)
		if not _is_checked(self.notifyWhenPageReadyCheckBox):
			self.pageReadyMessageRow.Hide()
		self.pageReadyMessageEdit.Bind(wx.EVT_TEXT, self.onChanged)
		self.pageLoadSummaryMode = group.addLabeledControl(
		    "Page-load summary:",
		    wx.Choice,
		    choices=[
		        "NVDA native, no summary",
		        "Summary after page is ready",
		        "Replace initial page speech with summary",
		    ],
		)
		self._pageLoadSummaryModes = (
		    PAGE_LOAD_SUMMARY_MODE_NATIVE,
		    PAGE_LOAD_SUMMARY_MODE_AFTER_READY,
		    PAGE_LOAD_SUMMARY_MODE_ORIENTATION,
		)
		self.pageLoadSummaryMode.SetSelection(
		    self._pageLoadSummaryModes.index(get_page_load_summary_mode())
		)
		self.pageLoadSummaryMode.Bind(wx.EVT_CHOICE, self.onPageLoadSummaryModeChanged)
		self._pageEntrySummaryDelaySeconds = (0, 1, 2, 3, 4, 5)
		self.pageEntrySummaryDelayChoice = group.addLabeledControl(
			"Automatic page-entry summary delay:",
			wx.Choice,
			choices=(
				"No additional delay",
				"1 second",
				"2 seconds",
				"3 seconds",
				"4 seconds",
				"5 seconds",
			),
		)
		self.pageEntrySummaryDelayChoice.SetName("Automatic page-entry summary delay")
		self.pageEntrySummaryDelayChoice.SetSelection(
			self._pageEntrySummaryDelaySeconds.index(get_page_entry_summary_delay_seconds())
		)
		self.pageEntrySummaryDelayChoice.Bind(wx.EVT_CHOICE, self.onChanged)
		self._update_page_entry_summary_delay_enabled()
		self._pageSummaryElements = [("documentTitle", "Title")] + [
			(item.item_type, item.plural_label)
			for item in SUMMARY_ITEM_TYPES
		]
		self.pageSummaryElementList = group.addLabeledControl(
			"Page Summary choices:",
			nvdaControls.CustomCheckListBox,
			choices=[label for _itemType, label in self._pageSummaryElements],
		)
		self.pageSummaryElementList.SetName("Included page summary element types")
		self.pageSummaryElementList.Bind(wx.EVT_CHECKLISTBOX, self.onPageSummaryChanged)
		enabledTypes = set(get_included_element_types())
		if get_include_document_title():
			enabledTypes.add("documentTitle")
		for index, (itemType, _label) in enumerate(self._pageSummaryElements):
			self.pageSummaryElementList.Check(index, itemType in enabledTypes)
		panel.SetSizer(mainSizer)
		panel.SetupScrolling(scroll_x=False)

	def _make_edge_notifications_panel(self, panel):
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		self.edgeNotificationsEditor = EdgeNotificationsPanel(
			panel,
			onChange=self.onChanged,
		)
		self.edgeNotificationsEditor.loadData(
			get_enabled_activity_ids(),
			get_custom_messages(),
		)
		mainSizer.Add(self.edgeNotificationsEditor, 1, wx.EXPAND)
		panel.SetSizer(mainSizer)
		self.edgeNotificationsPanel.SetupScrolling(scroll_x=False)

	def _add_browse_checkbox(self, group, parent, label, key):
		control = group.addItem(wx.CheckBox(parent, label=label))
		control.SetValue(get_virtual_buffer_setting(key))
		control.Bind(wx.EVT_CHECKBOX, self.onChanged)
		return control

	def _add_web_checkbox(self, group, parent, label, key):
		control = group.addItem(wx.CheckBox(parent, label=label))
		control.SetValue(get_web_document_formatting_setting(key))
		control.Bind(wx.EVT_CHECKBOX, self.onChanged)
		return control

	def _add_annotation_checkbox(self, group, parent, label, key):
		control = group.addItem(wx.CheckBox(parent, label=label))
		control.SetValue(get_annotation_setting(key))
		control.Bind(wx.EVT_CHECKBOX, self.onChanged)
		return control

	def _markDirty(self):
		try:
			self.applyBtn.Show()
			self.applyBtn.Enable(True)
			self.Layout()
		except Exception:
			pass

	def _clearDirty(self):
		try:
			self.applyBtn.Hide()
			self.applyBtn.Enable(False)
			self.Layout()
		except Exception:
			pass

	def _setInitialFocus(self):
		try:
			self.categoryList.SetFocus()
		except Exception:
			pass

	def _showPanelByIndex(self, index):
		for i, panel in enumerate(self.dynamicPanels):
			panel.Show(i == index)
		self.panelHost.Layout()
		self.Layout()
		wx.CallAfter(self._setInitialFocus)

	def _update_page_ready_message_row_visibility(self):
		self.pageReadyMessageRow.Show(_is_checked(self.notifyWhenPageReadyCheckBox))
		self.pageSummaryPanel.Layout()
		self.pageSummaryPanel.SetupScrolling(scroll_x=False)
		self.panelHost.Layout()
		self.Layout()

	def _update_page_entry_summary_delay_enabled(self):
		try:
			mode = self._pageLoadSummaryModes[self.pageLoadSummaryMode.GetSelection()]
			self.pageEntrySummaryDelayChoice.Enable(mode != PAGE_LOAD_SUMMARY_MODE_NATIVE)
		except Exception:
			pass

	def onPageLoadSummaryModeChanged(self, evt=None):
		self._update_page_entry_summary_delay_enabled()
		self.onChanged(evt)

	def _releaseTransactionPopup(self):
		if self._popupReleased:
			return
		self._popupReleased = True
		try:
			gui.mainFrame.postPopup()
		except Exception:
			log.exception("ClassicSpeech: postPopup failed during web/browse dialog close")

	def _captureTransactionBaseline(self):
		self._originalWebBrowse = capture_web_browse_state()
		self._originalPageSummary = capture_page_summary_state()
		self._originalPageSummaryTypes = get_included_element_types()
		self._originalPageSummaryTitle = get_include_document_title()
		self._originalPageLoadSummaryMode = get_page_load_summary_mode()
		self._originalNotifyWhenPageReady = get_notify_when_page_ready()
		self._originalPageReadyMessage = get_page_ready_message()
		self._originalEdgeNotifications = capture_edge_notification_state()

	def _restoreTransactionBaseline(self):
		try:
			restore_web_browse_state(self._originalWebBrowse)
			page_summary = getattr(self, "_originalPageSummary", None)
			if hasattr(page_summary, "get") and "hasPageSummaryData" in page_summary:
				restore_page_summary_state(page_summary)
			else:
				# Compatibility for lightweight older dialog fakes / partial baselines.
				set_included_element_types(self._originalPageSummaryTypes)
				set_include_document_title(self._originalPageSummaryTitle)
				set_page_load_summary_mode(self._originalPageLoadSummaryMode)
				set_notify_when_page_ready(self._originalNotifyWhenPageReady)
				set_page_ready_message(self._originalPageReadyMessage)
			if hasattr(self, "_originalEdgeNotifications"):
				restore_edge_notification_state(self._originalEdgeNotifications)
		except Exception:
			log.exception("ClassicSpeech: failed to restore original web/browse dialog state")

	def _saveTransaction(self):
		set_virtual_buffer_setting("maxLineLength", self.maxLengthEdit.GetValue())
		set_virtual_buffer_setting("linesPerPage", self.pageLinesEdit.GetValue())
		set_virtual_buffer_setting("useScreenLayout", _is_checked(self.useScreenLayoutCheckBox))
		set_virtual_buffer_setting("enableOnPageLoad", _is_checked(self.enableOnPageLoadCheckBox))
		set_virtual_buffer_setting("autoSayAllOnPageLoad", _is_checked(self.autoSayAllCheckBox))
		set_virtual_buffer_setting("autoPassThroughOnFocusChange", _is_checked(self.autoPassThroughOnFocusChangeCheckBox))
		set_virtual_buffer_setting("autoPassThroughOnCaretMove", _is_checked(self.autoPassThroughOnCaretMoveCheckBox))
		set_virtual_buffer_setting("passThroughAudioIndication", _is_checked(self.passThroughAudioIndicationCheckBox))
		set_virtual_buffer_setting("trapNonCommandGestures", _is_checked(self.trapNonCommandGesturesCheckBox))
		set_virtual_buffer_setting(
			"browseModeTouchNavigationElements",
			[
				itemType
				for index, (itemType, _label) in enumerate(self._browseModeElements)
				if index in _checked_items(self.browseModeTouchNavigationList)
			],
		)
		self.loadChromiumBusyCombo.saveCurrentValueToConf()
		set_annotation_setting("reportDetails", _is_checked(self.annotationDetailsCheckBox))
		set_annotation_setting("reportAriaDescription", _is_checked(self.ariaDescriptionCheckBox))
		set_web_document_formatting_setting("includeLayoutTables", _is_checked(self.layoutTablesCheckBox))
		set_web_document_formatting_setting("reportHeadings", _is_checked(self.headingsCheckBox))
		set_web_document_formatting_setting("reportLinks", _is_checked(self.linksCheckBox))
		set_web_document_formatting_setting("reportLinkType", _is_checked(self.linkTypeCheckBox))
		set_web_document_formatting_setting("reportGraphics", _is_checked(self.graphicsCheckBox))
		set_web_document_formatting_setting("reportLists", _is_checked(self.listsCheckBox))
		set_web_document_formatting_setting("reportBlockQuotes", _is_checked(self.blockQuotesCheckBox))
		set_web_document_formatting_setting("reportGroupings", _is_checked(self.groupingsCheckBox))
		set_web_document_formatting_setting("reportLandmarks", _is_checked(self.landmarksCheckBox))
		set_web_document_formatting_setting("reportArticles", _is_checked(self.articlesCheckBox))
		set_web_document_formatting_setting("reportFrames", _is_checked(self.framesCheckBox))
		set_web_document_formatting_setting("reportFigures", _is_checked(self.figuresCheckBox))
		set_web_document_formatting_setting("reportClickable", _is_checked(self.clickableCheckBox))
		if not hasattr(config.conf.get("braille"), "get"):
			config.conf["braille"] = {}
		self.brailleLiveRegionsCombo.saveCurrentValueToConf()
		if hasattr(self, "notifyWhenPageReadyCheckBox"):
			set_notify_when_page_ready(_is_checked(self.notifyWhenPageReadyCheckBox))
		if hasattr(self, "pageReadyMessageEdit"):
			set_page_ready_message(self.pageReadyMessageEdit.GetValue())
		if hasattr(self, "pageLoadSummaryMode"):
		    set_page_load_summary_mode(
		        self._pageLoadSummaryModes[self.pageLoadSummaryMode.GetSelection()]
		    )
		delayChoice = self.__dict__.get("pageEntrySummaryDelayChoice")
		delaySeconds = self.__dict__.get("_pageEntrySummaryDelaySeconds")
		if delayChoice is not None and delaySeconds is not None:
			set_page_entry_summary_delay_seconds(
				delaySeconds[delayChoice.GetSelection()]
			)
		if hasattr(self, "pageSummaryElementList"):
			selectedTypes = [
				itemType
				for index, (itemType, _label) in enumerate(self._pageSummaryElements)
				if index in _checked_items(self.pageSummaryElementList)
			]
			set_include_document_title("documentTitle" in selectedTypes)
			set_included_element_types(
				itemType for itemType in selectedTypes if itemType != "documentTitle"
			)
		edgeEditor = self.__dict__.get("edgeNotificationsEditor")
		if hasattr(self, "edgeNotificationsEditor") and edgeEditor is not None:
			# The registry setter deliberately accepts persisted-list shape only.
			# The editor exposes its normalized IDs as a tuple, so serialize it.
			set_enabled_activity_ids(list(edgeEditor.getEnabledActivityIds()))
			set_custom_messages(edgeEditor.getCustomMessages())

	def onCategoryChanged(self, evt):
		self._showPanelByIndex(evt.GetIndex())

	def onPageSummaryChanged(self, evt=None):
		if evt is not None and hasattr(evt, "Skip"):
			evt.Skip()
		self.onChanged(evt)

	def onPageReadyChanged(self, evt=None):
		self._update_page_ready_message_row_visibility()
		self.onChanged(evt)

	def onTouchNavigationChanged(self, evt=None):
		# CustomCheckListBox uses EVT_CHECKLISTBOX for keyboard and mouse
		# toggles.  Propagate the event so its accessibility state-change handler
		# can notify NVDA after ClassicSpeech marks the dialog dirty.
		if evt is not None and hasattr(evt, "Skip"):
			evt.Skip()
		self.onChanged(evt)

	def onChanged(self, evt=None):
		try:
			self._saveTransaction()
			self._markDirty()
		except Exception:
			log.exception("ClassicSpeech web/browse settings live apply failed")



# Backward-compatible name used by early v3/v02 work-in-progress notes.
WebSettingsDialog = WebBrowseSettingsDialog


