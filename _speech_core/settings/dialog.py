import copy

import wx
from wx.lib import scrolledpanel
import gui
import logHandler

try:
	from gui import nvdaControls
except Exception:
	nvdaControls = None

from ..key_labels import apply_key_labels_live, get_key_label_config
from .config import (
	_apply_profile_behavior_runtime,
	_apply_profile_live,
	_clone_profile_from_manager,
	_ensure_classic_speech_section,
	_get_active_profile_name,
	_get_default_button_enabled,
	_get_nvda_setting,
	_get_profile_behavior,
	_get_speech_hook_enabled,
	_replace_section_contents,
	_save_key_label_config,
	_save_profile_behavior,
	_save_profile_config,
	_save_shape_config,
	_set_active_profile_name,
	_set_default_button_enabled,
	_set_hotkey_dialog_access_key_only,
	_set_hotkey_format,
	_set_hotkey_mode,
	_set_hotkey_types,
	_set_nvda_setting,
	_set_speech_hook_enabled,
	_to_plain_data,
)
from .constants import PAUSE_MODE_GLOBAL, PAUSE_PLACEMENT_BEFORE
from .dialog_transactions import SettingsDialogTransactionMixin
from .advanced_panel import AdvancedPanel
from .document_formatting_config import (
	_capture_document_formatting_state,
	_restore_document_formatting_state,
)
from .document_reading_proofing_panel import DocumentReadingProofingPanel
from .hotkeys_panel import HotkeysPanel
from .key_labels_panel import KeyLabelsPanel
from .menus_panel import MenusPanel
from .misc_panel import MiscPanel
from .number_processing_panel import NumberProcessingPanel
from .speech_timing_panel import SpeechTimingPanel
from .text.panel import TextProcessingPanel
from .token_editor_panel import TokenEditorPanel
from .verbosity_panel import VerbosityPanel


log = logHandler.log

class ClassicSpeechDialog(SettingsDialogTransactionMixin, wx.Dialog):
	"""Main ClassicSpeech settings dialog with category list and dynamic panel area."""

	CATEGORY_NAMES = [
		"Verbosity",
		"Token Editor",
		"Speech Timing",
		"Text Processing",
		"Number Processing",
		"Document Reading / Proofing",
		"Menus",
		"Key Labels",
		"Hotkeys",
		"Misc",
		"Advanced",
	]

	def __init__(self, parent):
		super().__init__(
			parent,
			title="ClassicSpeech Settings",
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX,
		)

		self.SetName("ClassicSpeechSettingsDialog")
		self._popupReleased = False
		self._committed = False

		self._initializeDialogTransaction()

		outerSizer = wx.BoxSizer(wx.VERTICAL)
		contentSizer = wx.BoxSizer(wx.HORIZONTAL)

		leftSizer = wx.BoxSizer(wx.VERTICAL)

		self.categoryLabel = wx.StaticText(self, label="Categories")
		leftSizer.Add(self.categoryLabel, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)

		listClass = nvdaControls.AutoWidthColumnListCtrl if nvdaControls else wx.ListCtrl
		self.categoryList = listClass(
			self,
			style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER,
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

		self.panelHost = scrolledpanel.ScrolledPanel(
			self,
			style=wx.TAB_TRAVERSAL | wx.BORDER_THEME,
		)
		self.panelHostSizer = wx.BoxSizer(wx.VERTICAL)
		self.panelHost.SetSizer(self.panelHostSizer)

		self.verbosityPanel = VerbosityPanel(self.panelHost)
		self.tokenEditorPanel = TokenEditorPanel(self.panelHost)
		self.speechTimingPanel = SpeechTimingPanel(self.panelHost)
		self.textProcessingPanel = TextProcessingPanel(self.panelHost)
		self.numberProcessingPanel = NumberProcessingPanel(self.panelHost)
		self.documentReadingProofingPanel = DocumentReadingProofingPanel(self.panelHost)
		self.menusPanel = MenusPanel(self.panelHost)
		self.keyLabelsPanel = KeyLabelsPanel(self.panelHost)
		self.hotkeysPanel = HotkeysPanel(self.panelHost)
		self.miscPanel = MiscPanel(self.panelHost)
		self.advancedPanel = AdvancedPanel(self.panelHost)

		self.dynamicPanels = [
			self.verbosityPanel,
			self.tokenEditorPanel,
			self.speechTimingPanel,
			self.textProcessingPanel,
			self.numberProcessingPanel,
			self.documentReadingProofingPanel,
			self.menusPanel,
			self.keyLabelsPanel,
			self.hotkeysPanel,
			self.miscPanel,
			self.advancedPanel,
		]

		for panel in self.dynamicPanels:
			self.panelHostSizer.Add(panel, 1, wx.EXPAND)
			panel.Hide()

		self.verbosityPanel.Show()

		rightSizer.Add(self.panelHost, 1, wx.ALL | wx.EXPAND, 8)
		contentSizer.Add(rightSizer, 1, wx.ALL | wx.EXPAND, 8)

		outerSizer.Add(contentSizer, 1, wx.EXPAND)

		bottomRow = wx.BoxSizer(wx.HORIZONTAL)

		self.resetActionBtn = wx.Button(self, label="Reset Profile Now")
		bottomRow.Add(self.resetActionBtn, 0, wx.ALL, 8)

		bottomRow.AddStretchSpacer()

		self.applyBtn = wx.Button(self, label="Apply")
		self.okBtn = wx.Button(self, wx.ID_OK, label="OK")
		self.cancelBtn = wx.Button(self, wx.ID_CANCEL, label="Cancel")
		self.okBtn.SetDefault()

		bottomRow.Add(self.applyBtn, 0, wx.ALL, 8)
		bottomRow.Add(self.okBtn, 0, wx.ALL, 8)
		bottomRow.Add(self.cancelBtn, 0, wx.ALL, 8)

		outerSizer.Add(bottomRow, 0, wx.EXPAND)

		self.SetSizer(outerSizer)
		self.SetEscapeId(wx.ID_CANCEL)
		self.SetMinSize((800, 480))
		self.SetSize((900, 560))
		self.CentreOnParent()

		self.categoryList.Bind(wx.EVT_LIST_ITEM_FOCUSED, self.onCategoryChanged)
		self.resetActionBtn.Bind(wx.EVT_BUTTON, self.onResetCurrentProfile)
		self.applyBtn.Bind(wx.EVT_BUTTON, self.onApply)
		self.okBtn.Bind(wx.EVT_BUTTON, self.onOK)
		self.cancelBtn.Bind(wx.EVT_BUTTON, self.onCancel)
		self.Bind(wx.EVT_CLOSE, self.onClose)

		self.applyBtn.MoveAfterInTabOrder(self.cancelBtn)
		self._clearDirty()

		wx.CallAfter(self._setInitialFocus)

	def _captureTransactionBaseline(self):
		conf = _ensure_classic_speech_section()
		self._originalClassicSpeech = _to_plain_data(conf)
		self._originalDocumentFormatting = _capture_document_formatting_state()
		self._originalPresentation = {
			"reportKeyboardShortcuts": _get_nvda_setting(
				"presentation", "reportKeyboardShortcuts", True
			),
			"reportObjectPositionInformation": _get_nvda_setting(
				"presentation", "reportObjectPositionInformation", True
			),
			"guessObjectPositionInformationWhenUnavailable": _get_nvda_setting(
				"presentation", "guessObjectPositionInformationWhenUnavailable", False
			),
			"reportObjectDescriptions": _get_nvda_setting(
				"presentation", "reportObjectDescriptions", True
			),
			"reportTooltips": _get_nvda_setting(
				"presentation", "reportTooltips", False
			),
		}

	def _restoreTransactionBaseline(self):
		try:
			conf = _ensure_classic_speech_section()
			_replace_section_contents(conf, self._originalClassicSpeech)

			_set_nvda_setting(
				"presentation",
				"reportKeyboardShortcuts",
				self._originalPresentation["reportKeyboardShortcuts"],
			)
			_set_nvda_setting(
				"presentation",
				"reportObjectPositionInformation",
				self._originalPresentation["reportObjectPositionInformation"],
			)
			_set_nvda_setting(
				"presentation",
				"guessObjectPositionInformationWhenUnavailable",
				self._originalPresentation["guessObjectPositionInformationWhenUnavailable"],
			)
			_set_nvda_setting(
				"presentation",
				"reportObjectDescriptions",
				self._originalPresentation["reportObjectDescriptions"],
			)
			_set_nvda_setting(
				"presentation",
				"reportTooltips",
				self._originalPresentation["reportTooltips"],
			)
			_restore_document_formatting_state(self._originalDocumentFormatting)

			self._applyRuntimeFromCurrentConfig()
		except Exception:
			log.exception("ClassicSpeech: failed to restore original dialog state")

	def _applyRuntimeFromCurrentConfig(self):
		"""Re-apply live state after restoring the saved dialog snapshot."""
		_set_speech_hook_enabled(_get_speech_hook_enabled())
		apply_key_labels_live(get_key_label_config())

		active = _get_active_profile_name()
		profile_config = _clone_profile_from_manager(active)
		profile_behavior = _get_profile_behavior(active)
		_apply_profile_behavior_runtime(profile_config, profile_behavior)
		_apply_profile_live(active)
		_set_default_button_enabled(_get_default_button_enabled())


	def _markDirty(self):
		try:
			self.applyBtn.Enable(True)
		except Exception:
			pass

	def _clearDirty(self):
		try:
			self.applyBtn.Enable(False)
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

		if index == 0:
			self.resetActionBtn.Show()
			self.resetActionBtn.SetLabel("Reset Profile Now")
			self.resetActionBtn.Enable(True)
		elif index == 1:
			self.resetActionBtn.Show()
			self.resetActionBtn.SetLabel("Reset Tokens to Defaults Now")
			self.resetActionBtn.Enable(True)
		elif index == 7:
			self.resetActionBtn.Show()
			self.resetActionBtn.SetLabel("Reset Key Labels to Defaults Now")
			self.resetActionBtn.Enable(True)
		else:
			self.resetActionBtn.Hide()
			self.resetActionBtn.Enable(False)

		self.panelHost.Layout()
		self.panelHost.SetupScrolling()
		self.Layout()

		wx.CallAfter(self._setInitialFocus)

	def sync_edit_profile(self, profile_name: str):
		# Token editor is global now; keep method as a harmless compatibility stub.
		return

	def _releaseTransactionPopup(self):
		if self._popupReleased:
			return
		self._popupReleased = True
		try:
			gui.mainFrame.postPopup()
		except Exception:
			log.exception("ClassicSpeech: postPopup failed during dialog close")

	def _saveTransaction(self):
		profile_name = self.verbosityPanel.get_working_profile_name()

		profile_config = self.verbosityPanel.get_working_profile_config()
		profile_behavior = self.verbosityPanel.get_working_profile_behavior()
		shape_config = self.speechTimingPanel.get_working_shape_config()
		key_label_config = self.keyLabelsPanel.get_working_key_label_config()
		hotkey_config = self.hotkeysPanel.get_working_hotkey_config()
		hotkey_mode = hotkey_config["mode"]

		token_order = self.tokenEditorPanel.get_working_order()
		token_renames = self.tokenEditorPanel.get_working_renames()
		token_muted = self.tokenEditorPanel.get_working_muted_labels()
		shape_config["order"] = list(token_order)
		shape_config["renames"] = dict(token_renames)
		shape_config["mutedLabels"] = list(token_muted)

		# Keep the merged working view coherent for any code paths that still
		# consume a single combined profile config. Shape ownership remains global.
		profile_config["renames"] = dict(token_renames)
		profile_config["mutedLabels"] = list(token_muted)
		profile_config["pauseMode"] = shape_config.get("pauseMode", PAUSE_MODE_GLOBAL)
		profile_config["globalPause"] = shape_config.get("globalPause", 80)
		profile_config["pauseAfterFinalToken"] = shape_config.get("pauseAfterFinalToken", True)
		profile_config["pausePlacement"] = shape_config.get("pausePlacement", PAUSE_PLACEMENT_BEFORE)
		profile_config["pauses"] = dict(shape_config.get("pauses", {}))
		profile_config["order"] = list(shape_config.get("order", []))

		_set_active_profile_name(profile_name)
		_save_profile_config(profile_name, profile_config)
		_save_shape_config(shape_config)
		_save_key_label_config(key_label_config)
		_set_hotkey_mode(hotkey_mode)
		_set_hotkey_format(hotkey_config["format"])
		_set_hotkey_types(hotkey_config["types"])
		_set_hotkey_dialog_access_key_only(hotkey_config["dialogAccessKeyOnly"])
		_save_profile_behavior(profile_name, profile_behavior)
		_apply_profile_behavior_runtime(profile_config, profile_behavior)
		_apply_profile_live(profile_name)

		self.menusPanel.apply_live(save=True)
		self.textProcessingPanel.apply_live(save=True)
		self.numberProcessingPanel.apply_live(save=True)
		self.documentReadingProofingPanel.apply_live(save=True)
		self.miscPanel.apply_live(save=True)
		self.advancedPanel.apply_live(save=True)

		self.verbosityPanel.currentEditProfile = profile_name
		self.verbosityPanel.profileConfig = copy.deepcopy(profile_config)
		self.verbosityPanel.profileBehavior = copy.deepcopy(profile_behavior)

		self.speechTimingPanel.shapeConfig = copy.deepcopy(shape_config)
		self.speechTimingPanel._loadControlsFromShape()

		self.tokenEditorPanel.shapeConfig = copy.deepcopy(shape_config)
		self.tokenEditorPanel._loadEditorsFromShapeConfig()

		self.keyLabelsPanel.keyLabelConfig = copy.deepcopy(key_label_config)
		self.keyLabelsPanel._loadEditorsFromConfig()

		self.hotkeysPanel.hotkeyMode = hotkey_mode
		self.hotkeysPanel.hotkeyFormat = hotkey_config["format"]
		self.hotkeysPanel.hotkeyTypes = hotkey_config["types"]
		self.hotkeysPanel.dialogAccessKeyOnly = hotkey_config["dialogAccessKeyOnly"]
		self.hotkeysPanel._loadControlsFromConfig()

	def _getSelectedCategoryIndex(self):
		try:
			index = self.categoryList.GetFirstSelected()
		except Exception:
			index = 0
		return index if index != -1 else 0

	def onCategoryChanged(self, evt):
		self._showPanelByIndex(evt.GetIndex())

	def onResetCurrentProfile(self, evt):
		index = self._getSelectedCategoryIndex()
		if index == 0:
			self.verbosityPanel.reset_current_profile()
			self._captureTransactionBaseline()
		elif index == 1:
			self.tokenEditorPanel.reset_tokens_to_defaults()
			self._captureTransactionBaseline()
		elif index == 7:
			self.keyLabelsPanel.reset_key_labels_to_defaults()
			self._captureTransactionBaseline()
