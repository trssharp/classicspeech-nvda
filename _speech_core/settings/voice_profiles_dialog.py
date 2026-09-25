"""Accessible, transactional editor for ClassicSpeech Voice Profiles.

The dialog edits stored snapshots. Selecting a row never changes the live
synthesizer; explicit preview temporarily applies and then restores a snapshot.
"""
from __future__ import annotations
from ..localization import _


import wx
import logHandler
from gui import guiHelper, nvdaControls
from wx.lib import scrolledpanel

from .file_choosers import choose_export_path, choose_import_path
from .voice_profile_controls import VoiceProfileControls
from .voice_profile_packages import (
	VOICES_EXTENSION,
	VoiceProfilesFileError,
	read_voice_profiles,
	write_voice_profiles,
)
from .voice_profiles_config import VoiceProfileStore
from ..schemes import store as schemeStore
from .voice_profiles_preview import (
	DEFAULT_PREVIEW_TEXT,
	PreviewEvents,
	VoiceProfilePreviewController,
)

log = logHandler.log


#: List row after the synthesizer profiles: voices for document formatting and
#: web elements, stored in Speech and Sound Schemes.
FORMATTING_ROW_LABEL = _("Document and web formatting")


class VoiceProfilesDialog(wx.Dialog):
	"""Edit synthesizer-specific ClassicSpeech voice snapshots."""

	# Like NVDA's own settings dialogs: while this dialog is open, NVDA and
	# ClassicSpeech keep their configuration profiles as they were, so changed
	# settings are saved in the profile the user was using (gui.shouldConfigProfileTriggersBeSuspended).
	shouldSuspendConfigProfileTriggers = True

	def __init__(self, parent, driver=None):
		super().__init__(
			parent,
			title=_("ClassicSpeech Voice Profiles"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX,
		)
		self.SetName("ClassicSpeechVoiceProfilesDialog")
		if driver is None:
			from synthDriverHandler import getSynth
			driver = getSynth()
		self.store = VoiceProfileStore(driver)
		self.schemeStore = schemeStore.SchemeStore()
		self.formattingPanel = None
		self.currentProfileId = None
		self.currentControls = None
		self._previewController = None
		self._previewToken = 0

		outer = wx.BoxSizer(wx.VERTICAL)
		content = wx.BoxSizer(wx.HORIZONTAL)
		self._build_profile_list(content)
		self._build_editor(content)
		outer.Add(content, 1, wx.EXPAND)
		self._build_buttons(outer)
		self.SetSizer(outer)
		self.SetEscapeId(wx.ID_CANCEL)
		self.SetMinSize((800, 560))
		self.SetSize((980, 700))
		self.CentreOnParent()

		self.profileList.Bind(wx.EVT_LIST_ITEM_FOCUSED, self.onProfileChanged)
		self.profileList.Bind(wx.EVT_CHAR_HOOK, self.onProfileListCharHook)
		self.applyBtn.Bind(wx.EVT_BUTTON, self.onApply)
		self.okBtn.Bind(wx.EVT_BUTTON, self.onOK)
		self.cancelBtn.Bind(wx.EVT_BUTTON, self.onCancel)
		self.previewBtn.Bind(wx.EVT_BUTTON, self.onPreview)
		self.resetBtn.Bind(wx.EVT_BUTTON, self.onResetAllOverrides)
		self.exportBtn.Bind(wx.EVT_BUTTON, self.onExportProfiles)
		self.importBtn.Bind(wx.EVT_BUTTON, self.onImportProfiles)
		self.Bind(wx.EVT_CLOSE, self.onClose)
		self._select_profile(0)
		self._clearDirty()
		wx.CallAfter(self.profileList.SetFocus)

	def _build_profile_list(self, content):
		left = wx.BoxSizer(wx.VERTICAL)
		left.Add(wx.StaticText(self, label=_("Voice profiles")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		list_class = nvdaControls.AutoWidthColumnListCtrl
		self.profileList = list_class(
			self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER, size=(280, -1),
		)
		self.profileList.SetName(_("Voice profiles"))
		self.profileList.InsertColumn(0, _("Voice profiles"))
		for index, row in enumerate(self.store.rows):
			self.profileList.InsertItem(index, row.label)
		self.profileList.InsertItem(len(self.store.rows), FORMATTING_ROW_LABEL)
		left.Add(self.profileList, 1, wx.ALL | wx.EXPAND, 8)
		content.Add(left, 0, wx.EXPAND)

	def _build_editor(self, content):
		right = wx.BoxSizer(wx.VERTICAL)
		self.editorPanel = scrolledpanel.ScrolledPanel(self, style=wx.TAB_TRAVERSAL | wx.BORDER_THEME)
		self.editorSizer = wx.BoxSizer(wx.VERTICAL)
		self.editorPanel.SetSizer(self.editorSizer)
		self.editorPanel.SetupScrolling(scroll_x=False)
		right.Add(self.editorPanel, 1, wx.ALL | wx.EXPAND, 8)
		content.Add(right, 1, wx.EXPAND)

	def _build_buttons(self, outer):
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		previewControls = wx.BoxSizer(wx.VERTICAL)
		self.previewTextLabel = wx.StaticText(self, label=_("Preview &text:"))
		self.previewText = wx.TextCtrl(self, value=DEFAULT_PREVIEW_TEXT)
		self.previewText.SetName(_("Preview text:"))
		self.previewStatus = wx.StaticText(self, label="")
		previewControls.Add(self.previewTextLabel, 0, wx.BOTTOM, 2)
		previewControls.Add(self.previewText, 0, wx.EXPAND)
		previewControls.Add(self.previewStatus, 0, wx.TOP, 2)
		self.previewBtn = wx.Button(self, label=_("Pre&view selected profile"))
		self.previewBtn.Disable()
		self.resetBtn = wx.Button(self, label=_("Reset all Voice Profile overrides"))
		self.resetBtn.SetName(_("Reset all Voice Profile overrides"))
		self.exportBtn = wx.Button(self, label=_("E&xport voice profiles..."))
		self.importBtn = wx.Button(self, label=_("I&mport voice profiles..."))
		self.okBtn = wx.Button(self, wx.ID_OK, label=_("OK"))
		self.cancelBtn = wx.Button(self, wx.ID_CANCEL, label=_("Cancel"))
		self.applyBtn = wx.Button(self, label=_("Apply"))
		self.applyBtn.Hide()
		self.okBtn.SetDefault()
		buttons.Add(previewControls, 1, wx.ALL | wx.EXPAND, 8)
		buttons.Add(self.previewBtn, 0, wx.ALL | wx.ALIGN_BOTTOM, 8)
		buttons.Add(self.resetBtn, 0, wx.ALL | wx.ALIGN_BOTTOM, 8)
		buttons.Add(self.exportBtn, 0, wx.ALL | wx.ALIGN_BOTTOM, 8)
		buttons.Add(self.importBtn, 0, wx.ALL | wx.ALIGN_BOTTOM, 8)
		buttons.AddStretchSpacer()
		buttons.Add(self.okBtn, 0, wx.ALL, 8)
		buttons.Add(self.cancelBtn, 0, wx.ALL, 8)
		buttons.Add(self.applyBtn, 0, wx.ALL, 8)
		outer.Add(buttons, 0, wx.EXPAND)
		self.applyBtn.MoveAfterInTabOrder(self.cancelBtn)

	def _select_profile(self, index):
		if index < 0 or index > len(self.store.rows):
			return
		self.profileList.Select(index)
		self.profileList.Focus(index)
		if index == len(self.store.rows):
			self._show_formatting_voices()
		else:
			self._show_profile(self.store.rows[index])

	def _clear_editor(self):
		if self.formattingPanel is not None:
			try:
				self.formattingPanel.cleanup()
			except Exception:
				log.debug("ClassicSpeech Voice Profiles: formatting panel cleanup failed", exc_info=True)
			self.formattingPanel = None
		self.editorSizer.Clear(delete_windows=True)
		self.currentControls = None

	def _show_formatting_voices(self):
		"""Per-item voices for NVDA's document formatting and web elements."""
		from .schemes_panel import SchemeItemsPanel

		self.currentProfileId = None
		self._clear_editor()
		self.editorPanel.Show()
		self.editorSizer.Add(
			wx.StaticText(
				self.editorPanel,
				label=_(
					"Choose a voice for any document formatting or web element NVDA reports, such as bold text, "
					"a font, headings or links. The voice is used for the announcement and for the text itself. "
					"Sounds for these items are set in Speech and Sound Schemes."
				),
			),
			0, wx.ALL | wx.EXPAND, 6,
		)
		self.formattingPanel = SchemeItemsPanel(
			self.editorPanel,
			self.schemeStore,
			formatting_only=True,
			show_sounds=False,
			on_change=self._markDirty,
		)
		self.editorSizer.Add(self.formattingPanel, 1, wx.EXPAND | wx.ALL, 4)
		self.editorPanel.Layout()
		self.editorPanel.SetupScrolling(scroll_x=False)
		self.previewBtn.Disable()
		self.Layout()

	def _show_profile(self, row):
		self.currentProfileId = row.profile_id
		self._clear_editor()
		self.editorPanel.Show()
		snapshot = self.store.get_snapshot(row.profile_id)
		self.currentControls = VoiceProfileControls(
			self.store.driver,
			snapshot,
			lambda setting_id, value, profile_id=row.profile_id: self._profile_value_changed(
				profile_id, setting_id, value,
			),
		)
		if self.currentControls.settings:
			self.currentControls.build(self.editorPanel, self.editorSizer)
		else:
			self.editorSizer.Add(
				wx.StaticText(self.editorPanel, label=_("The active synthesizer exposes no editable settings.")),
				0, wx.ALL, 10,
			)
		self.editorPanel.Layout()
		self.editorPanel.SetupScrolling(scroll_x=False)
		self.previewBtn.Enable(row.editable and not self._preview_is_active())
		self.Layout()

	def onProfileListCharHook(self, event):
		"""Accept from the main profile list without changing editor key handling."""
		if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and not event.HasAnyModifiers():
			# Keep the voice/scheme save and preview cleanup lifecycle in onOK.
			# Consume failures too, avoiding a second native default activation.
			self.onOK(event)
		else:
			event.Skip()

	def onProfileChanged(self, event):
		if self._preview_is_active():
			return
		index = event.GetIndex()
		if index == len(self.store.rows):
			if self.formattingPanel is None:
				self._show_formatting_voices()
			return
		next_profile_id = self.store.rows[index].profile_id
		if next_profile_id != self.currentProfileId:
			self._markDirty()
		self._show_profile(self.store.rows[index])

	def _markDirty(self):
		self.applyBtn.Show()
		self.applyBtn.Enable(True)
		self.Layout()

	def _profile_value_changed(self, profile_id, setting_id, value):
		"""Commit an editor change without applying it to the live synthesizer."""
		self.store.set_value(profile_id, setting_id, value)
		self._markDirty()
		if setting_id in {"voice", "variant"}:
			# Native selector changes can reset dependent engine defaults. Refresh the
			# selected profile's existing controls in place without mutating live speech.
			if self.currentProfileId == profile_id and self.currentControls is not None:
				# ``get_snapshot`` returns a newly resolved baseline+override mapping.
				# The existing controls otherwise retain the old mapping from before
				# Voice selection and would display the prior voice's Pitch/Rate/etc.
				self.currentControls.snapshot = self.store.get_snapshot(profile_id)
				if self.currentControls.refresh_snapshot_values(skip_setting_id="voice"):
					return
			# A driver may expose a changed supported schema. Only in that unusual
			# case rebuild and restore focus to the replacement Voice control.
			self._show_profile(next(row for row in self.store.rows if row.profile_id == profile_id))
			wx.CallAfter(self._focus_editor_control, "Voice")

	def _focus_editor_control(self, name):
		"""Focus a rebuilt named editor control, if the dialog is still alive."""
		if self.IsBeingDeleted():
			return
		pending = list(self.editorPanel.GetChildren())
		while pending:
			control = pending.pop(0)
			if control.GetName() == name and control.IsShown() and control.IsEnabled():
				control.SetFocus()
				return
			pending.extend(control.GetChildren())

	def _clearDirty(self):
		self.applyBtn.Hide()
		self.applyBtn.Enable(False)
		self.Layout()

	def onPreview(self, event):
		if self._preview_is_active():
			return
		try:
			# Import the live speech surface only when Preview is explicitly used.
			# This keeps settings-package imports viable in the outside-NVDA harness.
			import speech
			from speech import extensions as speechExtensions
			from speech.commands import IndexCommand
			import synthDriverHandler
			from ..prosody_routing import suppress_profile_prosody_routing

			if synthDriverHandler.getSynth() is not self.store.driver:
				raise RuntimeError("The active synthesizer changed; reopen Voice Profiles before previewing")

			self._previewController = VoiceProfilePreviewController(
				self.store.get_preview_snapshot(self.currentProfileId),
				self.previewText.GetValue(),
				speak=speech.speak,
				index_command_factory=IndexCommand,
				events=PreviewEvents(
					synthDriverHandler.synthIndexReached,
					synthDriverHandler.synthDoneSpeaking,
					synthDriverHandler.synthChanged,
					speechExtensions.speechCanceled,
				),
				scheduler=lambda seconds, callback: wx.CallLater(seconds * 1000, callback),
				token_factory=self._nextPreviewToken,
				active_synth_getter=synthDriverHandler.getSynth,
				on_restore_error=lambda setting_id: log.error(
					"ClassicSpeech Voice Profiles failed to restore %s", setting_id,
				),
				on_finished=self._onPreviewFinished,
			)
			self._setPreviewBusy(True)
			# Preview applies its working snapshot directly. The persisted profile
			# router must not add stale commands around this one utterance.
			with suppress_profile_prosody_routing():
				self._previewController.start()
		except Exception:
			self._setPreviewBusy(False)
			log.exception("ClassicSpeech Voice Profiles preview failed")

	def _nextPreviewToken(self):
		self._previewToken += 1
		return self._previewToken

	def _preview_is_active(self):
		return self._previewController is not None and self._previewController.active

	def _setPreviewBusy(self, busy):
		self.profileList.Enable(not busy)
		self.editorPanel.Enable(not busy)
		self.previewText.Enable(not busy)
		self.previewBtn.Enable(not busy and self.formattingPanel is None)
		self.previewBtn.SetLabel(
			_("Previewing selected profile...") if busy else _("Pre&view selected profile")
		)
		self.previewStatus.SetLabel(_("Previewing selected profile.") if busy else "")
		self.Layout()

	def _onPreviewFinished(self, reason):
		# NVDA's notifications are delivered on its main event loop. CallAfter
		# keeps the dialog safe if a third-party driver invokes one from elsewhere.
		if not self.IsBeingDeleted():
			wx.CallAfter(self._setPreviewBusy, False)

	def onResetAllOverrides(self, event):
		self._cancelPreview()
		answer = wx.MessageBox(
			_("Remove every saved ClassicSpeech Voice Profile override for the active synthesizer? "
			"NVDA's native Voice Settings will be used until you save a new profile."),
			_("Reset all Voice Profile overrides"),
			wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
			parent=self,
		)
		if answer != wx.YES:
			return
		try:
			self.store.reset_all_overrides()
			self.store.apply()
			self.store.mark_applied()
			if self.currentProfileId is not None:
				self._show_profile(next(row for row in self.store.rows if row.profile_id == self.currentProfileId))
			self._clearDirty()
		except Exception:
			log.exception("ClassicSpeech Voice Profiles reset failed")

	def _message(self, text, title, icon=None):
		if icon is None:
			icon = wx.ICON_INFORMATION
		wx.MessageBox(text, title, wx.OK | icon, self)

	def onExportProfiles(self, event):
		self._cancelPreview()
		title = _("Export voice profiles")
		profiles = self.store.shareable_profiles()
		if not profiles:
			self._message(_("There are no voice profiles to export."), title)
			return
		path = choose_export_path(
			self, title, _("ClassicSpeech voice profiles"), VOICES_EXTENSION, _("ClassicSpeech voice profiles"),
		)
		if not path:
			return
		try:
			write_voice_profiles(path, profiles)
		except Exception:
			log.exception("ClassicSpeech Voice Profiles export failed")
			self._message(_("The voice profiles could not be exported. See the NVDA log for details."), title, wx.ICON_ERROR)
			return
		self._message(_("Exported voice profiles to {path}.").format(path=path), title)

	def onImportProfiles(self, event):
		self._cancelPreview()
		title = _("Import voice profiles")
		path = choose_import_path(self, title, _("ClassicSpeech voice profiles"), VOICES_EXTENSION)
		if not path:
			return
		try:
			synthesizers = read_voice_profiles(path)
		except VoiceProfilesFileError:
			self._message(_("This file is not a ClassicSpeech voice profiles file, or it has no voice profiles."), title, wx.ICON_ERROR)
			return
		except Exception:
			log.exception("ClassicSpeech Voice Profiles import failed")
			self._message(_("The voice profiles could not be imported. See the NVDA log for details."), title, wx.ICON_ERROR)
			return
		names = self.store.import_profiles(synthesizers)
		self._markDirty()
		if self.currentProfileId is not None:
			self._show_profile(next(row for row in self.store.rows if row.profile_id == self.currentProfileId))
		text = _("Imported voice profiles for {synthesizers}. Press OK or Apply to keep them.").format(
			synthesizers=", ".join(names),
		)
		if self.store.synth_id not in names:
			text += " " + _("The file has no voice profiles for your current synthesizer. They are used when you switch to one of those synthesizers.")
		self._message(text, title)

	def onApply(self, event):
		# Saving NVDA's configuration also saves the synthesizer's current
		# settings, so a preview still speaking would become the NVDA voice.
		self._cancelPreview()
		try:
			self.store.apply()
			self.store.mark_applied()
			self.schemeStore.apply()
			self.schemeStore.mark_applied()
			self._clearDirty()
			return True
		except Exception:
			log.exception("ClassicSpeech Voice Profiles apply failed")
			return False

	def onOK(self, event):
		self._cancelPreview()
		if self.onApply(event):
			self._clear_editor()
			self.Destroy()

	def onCancel(self, event):
		self._cancelPreview()
		self.schemeStore.cancel()
		self.store.cancel()
		self._clear_editor()
		self.Destroy()

	def onClose(self, event):
		self._cancelPreview()
		self.schemeStore.cancel()
		self.store.cancel()
		self._clear_editor()
		event.Skip()

	def _cancelPreview(self):
		if self._previewController is not None:
			self._previewController.cancel()
