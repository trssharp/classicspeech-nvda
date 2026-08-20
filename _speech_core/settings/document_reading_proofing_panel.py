from ..localization import _

import wx
import logHandler
from gui import guiHelper, nvdaControls

from .accessibility import _set_panel_description
from .document_formatting_config import (
	FONT_ATTRIBUTE_REPORTING_CHOICES,
	REPORT_CELL_BORDERS_CHOICES,
	REPORT_LINE_INDENTATION_CHOICES,
	REPORT_SPELLING_ERRORS_FLAGS,
	REPORT_TABLE_HEADERS_CHOICES,
	_get_document_formatting_setting,
	_is_ignore_blank_lines_for_rli_enabled,
	_is_report_transparent_color_enabled,
	_set_document_formatting_setting,
)

log = logHandler.log


def _choice_labels(choices):
	return [choice_label for choice_label, _value in choices]


def _choice_selection_for_value(choices, value):
	for index, (_label, choice_value) in enumerate(choices):
		if choice_value == value:
			return index
	return 0


def _choice_value_from_selection(choices, control, default=0):
	try:
		selection = int(control.GetSelection())
	except Exception:
		return default
	if 0 <= selection < len(choices):
		return choices[selection][1]
	return default


def _is_checked(control):
	if hasattr(control, "IsChecked"):
		return control.IsChecked()
	return control.GetValue()


class DocumentReadingProofingPanel(wx.Panel):
	"""Expose selected native NVDA documentFormatting options."""

	def __init__(self, parent):
		super().__init__(parent)
		_set_panel_description(
			self,
			_("Document Reading / Proofing"),
			_("Configure selected native NVDA document formatting and proofing announcements. This panel wraps NVDA settings and does not add a ClassicSpeech document processor."),
		)

		mainSizer = wx.BoxSizer(wx.VERTICAL)
		sHelper = guiHelper.BoxSizerHelper(self, sizer=mainSizer)
		sHelper.addItem(wx.StaticText(self, label=self.panelDescription))
		self._add_font_group(sHelper)
		self._add_document_information_group(sHelper)
		self._add_pages_and_spacing_group(sHelper)
		self._add_table_information_group(sHelper)
		self._add_advanced_group(sHelper)
		self.SetSizer(mainSizer)
		self._bind_controls()
		self._sync_spelling_errors_checks()
		self._sync_line_indentation_dependency()
		self._sync_transparent_color_dependency()

	def _add_static_box_group(self, sHelper, label):
		groupSizer = wx.StaticBoxSizer(wx.VERTICAL, self, label=label)
		groupBox = groupSizer.GetStaticBox()
		group = guiHelper.BoxSizerHelper(self, sizer=groupSizer)
		sHelper.addItem(group)
		return group, groupBox

	def _add_checkbox(self, group, parent, attr, key, label):
		control = group.addItem(wx.CheckBox(parent, label=label))
		control.SetValue(_get_document_formatting_setting(key))
		setattr(self, attr, control)
		return control

	def _add_choice(self, group, attr, key, label, choices):
		control = group.addLabeledControl(label, wx.Choice, choices=_choice_labels(choices))
		control.SetSelection(_choice_selection_for_value(choices, _get_document_formatting_setting(key)))
		setattr(self, attr, control)
		return control

	def _add_font_group(self, sHelper):
		group, box = self._add_static_box_group(sHelper, _("Font"))
		self._add_checkbox(group, box, "fontNameCheckBox", "reportFontName", _("&Font name"))
		self._add_checkbox(group, box, "fontSizeCheckBox", "reportFontSize", _("Font &size"))
		self._add_choice(
			group,
			"fontAttrsList",
			"fontAttributeReporting",
			_("Font attrib&utes"),
			FONT_ATTRIBUTE_REPORTING_CHOICES,
		)
		self._add_checkbox(
			group,
			box,
			"superscriptsAndSubscriptsCheckBox",
			"reportSuperscriptsAndSubscripts",
			_("Su&perscripts and subscripts"),
		)
		self._add_checkbox(group, box, "emphasisCheckBox", "reportEmphasis", _("E&mphasis"))
		self._add_checkbox(group, box, "highlightCheckBox", "reportHighlight", _("Highlighted (mar&ked) text"))
		self._add_checkbox(group, box, "styleCheckBox", "reportStyle", _("St&yle"))
		self._add_checkbox(group, box, "colorCheckBox", "reportColor", _("&Colors"))
		self._add_checkbox(
			group,
			box,
			"transparentColorCheckBox",
			"reportTransparentColor",
			_("Report transparent color values"),
		)

	def _add_document_information_group(self, sHelper):
		group, box = self._add_static_box_group(sHelper, _("Document information"))
		self._add_checkbox(group, box, "commentsCheckBox", "reportComments", _("Commen&ts"))
		self._add_checkbox(group, box, "bookmarksCheckBox", "reportBookmarks", _("&Bookmarks"))
		self._add_checkbox(group, box, "revisionsCheckBox", "reportRevisions", _("&Editor revisions"))
		self.reportSpellingErrors2 = group.addLabeledControl(
			_("Spelling or grammar e&rrors"),
			nvdaControls.CustomCheckListBox,
			choices=_choice_labels(REPORT_SPELLING_ERRORS_FLAGS),
		)

	def _add_pages_and_spacing_group(self, sHelper):
		group, box = self._add_static_box_group(sHelper, _("Pages and spacing"))
		self._add_checkbox(group, box, "pageCheckBox", "reportPage", _("&Pages"))
		self._add_checkbox(group, box, "lineNumberCheckBox", "reportLineNumber", _("Line &numbers"))
		self._add_choice(
			group,
			"lineIndentationCombo",
			"reportLineIndentation",
			_("Line &indentation reporting:"),
			REPORT_LINE_INDENTATION_CHOICES,
		)
		self._add_checkbox(
			group,
			box,
			"ignoreBlankLinesRLICheckbox",
			"ignoreBlankLinesForRLI",
			_("Ignore &blank lines for line indentation reporting"),
		)
		self._add_checkbox(
			group,
			box,
			"paragraphIndentationCheckBox",
			"reportParagraphIndentation",
			_("&Paragraph indentation"),
		)
		self._add_checkbox(group, box, "lineSpacingCheckBox", "reportLineSpacing", _("&Line spacing"))
		self._add_checkbox(group, box, "alignmentCheckBox", "reportAlignment", _("&Alignment"))

	def _add_table_information_group(self, sHelper):
		group, box = self._add_static_box_group(sHelper, _("Table information"))
		self._add_checkbox(group, box, "tablesCheckBox", "reportTables", _("&Tables"))
		self._add_choice(group, "tableHeadersComboBox", "reportTableHeaders", _("H&eaders"), REPORT_TABLE_HEADERS_CHOICES)
		self._add_checkbox(group, box, "tableCellCoordsCheckBox", "reportTableCellCoords", _("Cell c&oordinates"))
		self._add_choice(group, "borderComboBox", "reportCellBorders", _("Cell &borders:"), REPORT_CELL_BORDERS_CHOICES)

	def _add_advanced_group(self, sHelper):
		group, box = self._add_static_box_group(sHelper, _("Advanced"))
		self._add_checkbox(
			group,
			box,
			"detectFormatAfterCursorCheckBox",
			"detectFormatAfterCursor",
			_("Report formatting chan&ges after the cursor (can cause a lag)"),
		)

	def _bind_controls(self):
		for control in (
			self.fontNameCheckBox,
			self.fontSizeCheckBox,
			self.superscriptsAndSubscriptsCheckBox,
			self.emphasisCheckBox,
			self.highlightCheckBox,
			self.styleCheckBox,
			self.transparentColorCheckBox,
			self.commentsCheckBox,
			self.bookmarksCheckBox,
			self.revisionsCheckBox,
			self.pageCheckBox,
			self.lineNumberCheckBox,
			self.ignoreBlankLinesRLICheckbox,
			self.paragraphIndentationCheckBox,
			self.lineSpacingCheckBox,
			self.alignmentCheckBox,
			self.tablesCheckBox,
			self.tableCellCoordsCheckBox,
			self.detectFormatAfterCursorCheckBox,
		):
			control.Bind(wx.EVT_CHECKBOX, self.onChanged)

		for control in (
			self.fontAttrsList,
			self.tableHeadersComboBox,
			self.borderComboBox,
		):
			control.Bind(wx.EVT_CHOICE, self.onChanged)
		self.reportSpellingErrors2.Bind(wx.EVT_CHECKLISTBOX, self.onSpellingErrorsChanged)
		self.lineIndentationCombo.Bind(wx.EVT_CHOICE, self.onLineIndentationChanged)
		self.colorCheckBox.Bind(wx.EVT_CHECKBOX, self.onColorChanged)

	def _sync_spelling_errors_checks(self):
		value = _get_document_formatting_setting("reportSpellingErrors2")
		indices = [index for index, (_label, flag) in enumerate(REPORT_SPELLING_ERRORS_FLAGS) if value & flag]
		if hasattr(self.reportSpellingErrors2, "SetCheckedItems"):
			self.reportSpellingErrors2.SetCheckedItems(indices)
		elif hasattr(self.reportSpellingErrors2, "CheckedItems"):
			self.reportSpellingErrors2.CheckedItems = indices
		else:
			for index in indices:
				if hasattr(self.reportSpellingErrors2, "Check"):
					self.reportSpellingErrors2.Check(index, True)
		if hasattr(self.reportSpellingErrors2, "Select"):
			self.reportSpellingErrors2.Select(0)

	def _get_spelling_errors_value(self):
		if hasattr(self.reportSpellingErrors2, "GetCheckedItems"):
			checked = self.reportSpellingErrors2.GetCheckedItems()
		elif hasattr(self.reportSpellingErrors2, "CheckedItems"):
			checked = self.reportSpellingErrors2.CheckedItems
		else:
			checked = [
				index
				for index, _choice in enumerate(REPORT_SPELLING_ERRORS_FLAGS)
				if hasattr(self.reportSpellingErrors2, "IsChecked") and self.reportSpellingErrors2.IsChecked(index)
			]
		value = 0
		for index in checked or []:
			try:
				value |= int(REPORT_SPELLING_ERRORS_FLAGS[int(index)][1])
			except Exception:
				continue
		return value

	def _sync_line_indentation_dependency(self):
		self.ignoreBlankLinesRLICheckbox.Enable(_is_ignore_blank_lines_for_rli_enabled())

	def _sync_transparent_color_dependency(self):
		self.transparentColorCheckBox.Enable(_is_report_transparent_color_enabled())

	def onColorChanged(self, evt=None):
		try:
			self.apply_live(save=False)
			self._sync_transparent_color_dependency()
			self._mark_dialog_dirty()
		except Exception:
			log.exception("ClassicSpeech color document setting update failed")

	def onLineIndentationChanged(self, evt=None):
		try:
			self.apply_live(save=False)
			if evt is not None and hasattr(evt, "GetSelection"):
				self.ignoreBlankLinesRLICheckbox.Enable(evt.GetSelection() != 0)
			else:
				self._sync_line_indentation_dependency()
			self._mark_dialog_dirty()
		except Exception:
			log.exception("ClassicSpeech line-indentation document setting update failed")

	def onSpellingErrorsChanged(self, evt=None):
		try:
			if evt is not None and hasattr(evt, "Skip"):
				evt.Skip()
			self.apply_live(save=False)
			self._mark_dialog_dirty()
		except Exception:
			log.exception("ClassicSpeech spelling-errors document setting update failed")

	def onChanged(self, evt=None):
		try:
			self.apply_live(save=False)
			self._mark_dialog_dirty()
		except Exception:
			log.exception("ClassicSpeech document reading/proofing settings live apply failed")

	def _mark_dialog_dirty(self):
		dlg = wx.GetTopLevelParent(self)
		if hasattr(dlg, "_markDirty"):
			dlg._markDirty()

	def apply_live(self, save=True):
		_set_document_formatting_setting("reportFontName", _is_checked(self.fontNameCheckBox))
		_set_document_formatting_setting("reportFontSize", _is_checked(self.fontSizeCheckBox))
		_set_document_formatting_setting(
			"fontAttributeReporting",
			_choice_value_from_selection(FONT_ATTRIBUTE_REPORTING_CHOICES, self.fontAttrsList, 0),
		)
		_set_document_formatting_setting("reportSuperscriptsAndSubscripts", _is_checked(self.superscriptsAndSubscriptsCheckBox))
		_set_document_formatting_setting("reportEmphasis", _is_checked(self.emphasisCheckBox))
		_set_document_formatting_setting("reportHighlight", _is_checked(self.highlightCheckBox))
		_set_document_formatting_setting("reportStyle", _is_checked(self.styleCheckBox))
		_set_document_formatting_setting("reportColor", _is_checked(self.colorCheckBox))
		_set_document_formatting_setting("reportTransparentColor", _is_checked(self.transparentColorCheckBox))
		_set_document_formatting_setting("reportComments", _is_checked(self.commentsCheckBox))
		_set_document_formatting_setting("reportBookmarks", _is_checked(self.bookmarksCheckBox))
		_set_document_formatting_setting("reportRevisions", _is_checked(self.revisionsCheckBox))
		_set_document_formatting_setting("reportSpellingErrors2", self._get_spelling_errors_value())
		_set_document_formatting_setting("reportPage", _is_checked(self.pageCheckBox))
		_set_document_formatting_setting("reportLineNumber", _is_checked(self.lineNumberCheckBox))
		_set_document_formatting_setting(
			"reportLineIndentation",
			_choice_value_from_selection(REPORT_LINE_INDENTATION_CHOICES, self.lineIndentationCombo, 0),
		)
		_set_document_formatting_setting("ignoreBlankLinesForRLI", _is_checked(self.ignoreBlankLinesRLICheckbox))
		_set_document_formatting_setting("reportParagraphIndentation", _is_checked(self.paragraphIndentationCheckBox))
		_set_document_formatting_setting("reportLineSpacing", _is_checked(self.lineSpacingCheckBox))
		_set_document_formatting_setting("reportAlignment", _is_checked(self.alignmentCheckBox))
		_set_document_formatting_setting("reportTables", _is_checked(self.tablesCheckBox))
		_set_document_formatting_setting(
			"reportTableHeaders",
			_choice_value_from_selection(REPORT_TABLE_HEADERS_CHOICES, self.tableHeadersComboBox, 1),
		)
		_set_document_formatting_setting("reportTableCellCoords", _is_checked(self.tableCellCoordsCheckBox))
		_set_document_formatting_setting(
			"reportCellBorders",
			_choice_value_from_selection(REPORT_CELL_BORDERS_CHOICES, self.borderComboBox, 0),
		)
		_set_document_formatting_setting("detectFormatAfterCursor", _is_checked(self.detectFormatAfterCursorCheckBox))
		self._sync_line_indentation_dependency()
		self._sync_transparent_color_dependency()
		if save:
			return
