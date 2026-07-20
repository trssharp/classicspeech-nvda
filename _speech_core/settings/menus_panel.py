import wx
import logHandler

from .accessibility import _set_panel_description
from .menus_config import (
	_ensure_classic_speech_section,
	_get_menu_bar_focus_enabled,
	_get_menu_bar_focus_message,
	_get_menu_bar_leave_enabled,
	_get_menu_bar_leave_message,
	_get_menu_close_enabled,
	_get_menu_close_message,
	_get_menu_open_enabled,
	_get_menu_open_message,
)

log = logHandler.log

class MenusPanel(wx.Panel):
	def __init__(self, parent):
		super().__init__(parent)

		_set_panel_description(self, "Menus", "Configure menu open, close, menu bar focus, and menu bar leave announcements.")

		mainSizer = wx.BoxSizer(wx.VERTICAL)

		self.announceMenuOpen = wx.CheckBox(self, label="Announce menu open")
		self.announceMenuOpen.SetValue(_get_menu_open_enabled())
		mainSizer.Add(self.announceMenuOpen, 0, wx.ALL | wx.EXPAND, 8)

		openGrid = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
		openGrid.AddGrowableCol(1, 1)
		openGrid.Add(wx.StaticText(self, label="Menu open message:"), 0, wx.ALIGN_CENTER_VERTICAL)
		self.menuOpenMessage = wx.TextCtrl(self, value=_get_menu_open_message())
		self.menuOpenMessage.SetName("Menu open message")
		openGrid.Add(self.menuOpenMessage, 1, wx.EXPAND)
		mainSizer.Add(openGrid, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		self.announceMenuClose = wx.CheckBox(self, label="Announce menu close")
		self.announceMenuClose.SetValue(_get_menu_close_enabled())
		mainSizer.Add(self.announceMenuClose, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		closeGrid = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
		closeGrid.AddGrowableCol(1, 1)
		closeGrid.Add(wx.StaticText(self, label="Menu close message:"), 0, wx.ALIGN_CENTER_VERTICAL)
		self.menuCloseMessage = wx.TextCtrl(self, value=_get_menu_close_message())
		self.menuCloseMessage.SetName("Menu close message")
		closeGrid.Add(self.menuCloseMessage, 1, wx.EXPAND)
		mainSizer.Add(closeGrid, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		self.announceMenuBarFocus = wx.CheckBox(self, label="Announce menu bar focus")
		self.announceMenuBarFocus.SetValue(_get_menu_bar_focus_enabled())
		mainSizer.Add(self.announceMenuBarFocus, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		barFocusGrid = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
		barFocusGrid.AddGrowableCol(1, 1)
		barFocusGrid.Add(wx.StaticText(self, label="Menu bar focus message:"), 0, wx.ALIGN_CENTER_VERTICAL)
		self.menuBarFocusMessage = wx.TextCtrl(self, value=_get_menu_bar_focus_message())
		self.menuBarFocusMessage.SetName("Menu bar focus message")
		barFocusGrid.Add(self.menuBarFocusMessage, 1, wx.EXPAND)
		mainSizer.Add(barFocusGrid, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		self.announceMenuBarLeave = wx.CheckBox(self, label="Announce leaving menu bar")
		self.announceMenuBarLeave.SetValue(_get_menu_bar_leave_enabled())
		mainSizer.Add(self.announceMenuBarLeave, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

		barLeaveGrid = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
		barLeaveGrid.AddGrowableCol(1, 1)
		barLeaveGrid.Add(wx.StaticText(self, label="Menu bar leave message:"), 0, wx.ALIGN_CENTER_VERTICAL)
		self.menuBarLeaveMessage = wx.TextCtrl(self, value=_get_menu_bar_leave_message())
		self.menuBarLeaveMessage.SetName("Menu bar leave message")
		barLeaveGrid.Add(self.menuBarLeaveMessage, 1, wx.EXPAND)
		mainSizer.Add(barLeaveGrid, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)
		self.SetSizer(mainSizer)

		for ctrl in (
			self.announceMenuOpen,
			self.announceMenuClose,
			self.announceMenuBarFocus,
			self.announceMenuBarLeave,
		):
			ctrl.Bind(wx.EVT_CHECKBOX, self.onChanged)
		for ctrl in (
			self.menuOpenMessage,
			self.menuCloseMessage,
			self.menuBarFocusMessage,
			self.menuBarLeaveMessage,
		):
			ctrl.Bind(wx.EVT_TEXT, self.onChanged)

	def onChanged(self, evt=None):
		try:
			self.apply_live(save=False)
			dlg = wx.GetTopLevelParent(self)
			if hasattr(dlg, "_markDirty"):
				dlg._markDirty()
		except Exception:
			log.exception("ClassicSpeech menu settings live apply failed")

	def apply_live(self, save=True):
		open_enabled = self.announceMenuOpen.GetValue()
		close_enabled = self.announceMenuClose.GetValue()
		bar_focus_enabled = self.announceMenuBarFocus.GetValue()
		bar_leave_enabled = self.announceMenuBarLeave.GetValue()
		open_message = self.menuOpenMessage.GetValue().strip() or "Entering menu"
		close_message = self.menuCloseMessage.GetValue().strip() or "Leaving menu"
		bar_focus_message = self.menuBarFocusMessage.GetValue().strip() or "Menu bar"
		bar_leave_message = self.menuBarLeaveMessage.GetValue().strip() or "Leaving menu bar"

		conf = _ensure_classic_speech_section()
		conf["announceMenuOpen"] = bool(open_enabled)
		conf["announceMenuClose"] = bool(close_enabled)
		conf["announceMenuBarFocus"] = bool(bar_focus_enabled)
		conf["announceMenuBarLeave"] = bool(bar_leave_enabled)
		conf["menuOpenMessage"] = str(open_message)
		conf["menuCloseMessage"] = str(close_message)
		conf["menuBarFocusMessage"] = str(bar_focus_message)
		conf["menuBarLeaveMessage"] = str(bar_leave_message)

		if save:
			return
