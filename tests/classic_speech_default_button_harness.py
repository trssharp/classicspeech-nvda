"""Regression harness for finding a dialog's default button (NVDA+E and focus speech).

ClassicSpeech 1.14 reported the wrong button in two common dialogs:

* NVDA's Speech settings: after Tab passed over "Change...", NVDA+E said
  "Default button Change...". wxWidgets makes a focused button the temporary
  default, and ClassicSpeech remembered that button for the whole dialog.
* The Windows file dialog LibreOffice uses: "No default button" in the file
  name field, because Open is a split button.

NVDA+E now deliberately prefers the focused eligible push or split button.
With focus elsewhere it retains the dialog-default detection. Automatic focus
speech still marks only the dialog's own default. These tests use fake window handles, fake wx windows and fake screen
pixels. A Windows-only test checks the Windows behavior they rely on with a
real dialog that is never shown.
"""
from __future__ import annotations

import os
import sys
import types
import unittest
from enum import Enum
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
	sys.path.insert(0, str(ROOT / "tests"))

import classic_speech_nvda_master_harness as nvda_harness  # noqa: E402
import api  # noqa: E402
import controlTypes  # noqa: E402
import globalPluginHandler  # noqa: E402
import speech  # noqa: E402


def _with_members(enumClass, names):
	"""Return ``enumClass`` with the missing ``names`` added (the harness stub lacks some roles)."""
	missing = [name for name in names if not hasattr(enumClass, name)]
	if not missing:
		return enumClass
	members = {member.name: member.value for member in enumClass}
	start = max(members.values()) + 1
	for offset, name in enumerate(missing):
		members[name] = start + offset
	return Enum(enumClass.__name__, members)


def _extend_control_types():
	role = _with_members(controlTypes.Role, ("SPLITBUTTON", "FORM", "PANE", "WINDOW", "GROUPING", "SLIDER", "LINK"))
	if role is not controlTypes.Role:
		labels = {role[member.name]: label for member, label in controlTypes.role._roleLabels.items()}
		labels.update(
			{
				role.SPLITBUTTON: "split button",
				role.FORM: "form",
				role.PANE: "pane",
				role.WINDOW: "window",
				role.GROUPING: "grouping",
				role.SLIDER: "slider",
				role.LINK: "link",
			}
		)
		controlTypes.Role = role
		controlTypes.role._roleLabels = labels
	state = _with_members(controlTypes.State, ("INVISIBLE", "OFFSCREEN", "UNAVAILABLE", "FOCUSED"))
	if state is not controlTypes.State:
		controlTypes.state._stateLabels = {
			state[member.name]: label for member, label in controlTypes.state._stateLabels.items()
		}
		controlTypes.state._negativeStateLabels = {
			state[member.name]: label for member, label in controlTypes.state._negativeStateLabels.items()
		}
		controlTypes.State = state


_extend_control_types()

STATE_SYSTEM_DEFAULT = 0x100
BS_PUSHBUTTON = 0x0
BS_DEFPUSHBUTTON = 0x1
BS_SPLITBUTTON = 0xC
BS_DEFSPLITBUTTON = 0xD
WS_EX_DLGMODALFRAME = 0x1
NVDA_PID = os.getpid()
APP_PID = 4242


class FakeObject:
	"""An NVDA object double."""

	def __init__(
		self,
		role,
		name="",
		*,
		hwnd=0,
		children=(),
		states=(),
		iaStates=0,
		processID=APP_PID,
		windowClassName="",
		location=None,
		**extra,
	):
		self.role = getattr(controlTypes.Role, role)
		self.name = name
		self.windowHandle = hwnd
		self.children = list(children)
		self.states = set(states)
		self.IAccessibleStates = iaStates
		self.IAccessibleChildID = 0
		self.processID = processID
		self.windowClassName = windowClassName
		self.location = location
		self.treeInterceptor = None
		self.value = ""
		self.parent = None
		self.childReads = 0
		for key, value in extra.items():
			setattr(self, key, value)

	def __getattribute__(self, name):
		if name == "children":
			object.__setattr__(self, "childReads", object.__getattribute__(self, "childReads") + 1)
		return object.__getattribute__(self, name)

	def __repr__(self):
		return f"<{self.role.name} {self.name!r}>"


class FakeIAccessible2:
	"""Stands in for an IAccessible2 COM object (browsers, LibreOffice, Qt)."""


def _install_fake_iaccessible_handler():
	module = types.ModuleType("IAccessibleHandler")
	module.IA2 = types.SimpleNamespace(IAccessible2=FakeIAccessible2)
	sys.modules["IAccessibleHandler"] = module


class FakeUser32:
	"""A window tree double with the calls ``win32_default_button`` makes."""

	def __init__(self):
		self.windows = {}
		self.defaultIds = {}
		self.calls = []
		self.foregroundHwnd = 0
		self.cursorPos = None

	def add(self, hwnd, cls, *, parent=0, text="", style=0, exStyle=0, ident=0, visible=True, enabled=True):
		self.windows[hwnd] = types.SimpleNamespace(
			cls=cls,
			parent=parent,
			text=text,
			style=style,
			exStyle=exStyle,
			ident=ident,
			visible=visible,
			enabled=enabled,
		)
		return hwnd

	def _log(self, name):
		self.calls.append(name)

	def root(self, hwnd):
		self._log("root")
		while hwnd in self.windows and self.windows[hwnd].parent:
			hwnd = self.windows[hwnd].parent
		return hwnd if hwnd in self.windows else 0

	def parent(self, hwnd):
		self._log("parent")
		window = self.windows.get(hwnd)
		return window.parent if window else 0

	def class_name(self, hwnd):
		self._log("class_name")
		return self.windows[hwnd].cls

	def text(self, hwnd):
		self._log("text")
		return self.windows[hwnd].text

	def style(self, hwnd):
		self._log("style")
		return self.windows[hwnd].style

	def ex_style(self, hwnd):
		self._log("ex_style")
		return self.windows[hwnd].exStyle

	def exists(self, hwnd):
		return hwnd in self.windows

	def visible(self, hwnd):
		self._log("visible")
		while hwnd in self.windows:
			if not self.windows[hwnd].visible:
				return False
			hwnd = self.windows[hwnd].parent
		return True

	def enabled(self, hwnd):
		self._log("enabled")
		return self.windows[hwnd].enabled

	def is_descendant(self, parent, child):
		self._log("is_descendant")
		child = self.windows[child].parent if child in self.windows else 0
		while child:
			if child == parent:
				return True
			child = self.windows[child].parent if child in self.windows else 0
		return False

	def control_id(self, hwnd):
		self._log("control_id")
		return self.windows[hwnd].ident

	def dialog_item(self, dialog, controlId):
		self._log("dialog_item")
		for hwnd, window in self.windows.items():
			if window.parent == dialog and window.ident == controlId:
				return hwnd
		return 0

	def descendants(self, hwnd, limit=600):
		self._log("descendants")
		found = []

		def walk(parent):
			for child, window in self.windows.items():
				if window.parent == parent and len(found) < limit:
					found.append(child)
					walk(child)

		walk(hwnd)
		return found

	def default_id(self, dialog):
		self._log("default_id")
		return self.defaultIds.get(dialog)

	def foreground(self):
		return self.foregroundHwnd

	def cursor(self):
		return self.cursorPos

	def process_id(self, hwnd):
		return APP_PID

	def move_focus(self, focused, permanentDefault):
		"""Move the default style the way Windows does when focus moves to ``focused``."""
		pushButtons = [
			hwnd
			for hwnd, window in self.windows.items()
			if "button" in window.cls.lower() and window.style & 0xF in (0x0, 0x1, 0xC, 0xD)
		]
		for hwnd in pushButtons:
			self.windows[hwnd].style &= ~0x1
		target = focused if focused in pushButtons else permanentDefault
		if target:
			self.windows[target].style |= 0x1


class DefaultButtonTestBase(unittest.TestCase):
	def setUp(self):
		nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
		self.module = nvda_harness._import_classic_speech_like_nvda()
		from globalPlugins._speech_core import (
			default_button_appearance,
			dialog_helpers,
			focus_ancestry,
			win32_default_button,
		)

		self.helpers = dialog_helpers
		self.appearance = default_button_appearance
		self.win32 = win32_default_button
		self.focus_ancestry = focus_ancestry
		focus_ancestry.reset_cache()
		dialog_helpers.reset_default_button_cache()
		win32_default_button.set_api(False)
		self._original_get_focus = api.getFocusObject
		self._original_get_ancestors = getattr(api, "getFocusAncestors", None)
		self._original_wx = sys.modules.get("wx")
		self._original_uia = sys.modules.get("UIAHandler")
		self._original_ia = sys.modules.get("IAccessibleHandler")
		_install_fake_iaccessible_handler()

	def tearDown(self):
		api.getFocusObject = self._original_get_focus
		if self._original_get_ancestors is None:
			try:
				del api.getFocusAncestors
			except AttributeError:
				pass
		else:
			api.getFocusAncestors = self._original_get_ancestors
		for name, original in (
			("wx", self._original_wx),
			("UIAHandler", self._original_uia),
			("IAccessibleHandler", self._original_ia),
		):
			if original is None:
				sys.modules.pop(name, None)
			else:
				sys.modules[name] = original
		self.win32.set_api(False)
		self.appearance.set_capture(None)
		self.focus_ancestry.reset_cache()
		globalPluginHandler.runningPlugins.clear()
		speech.extensions.filter_speechSequence.callbacks.clear()
		nvda_harness._reset_global_plugin_imports()

	def _focus(self, focus, *ancestorsNearestFirst):
		ancestors = list(reversed(ancestorsNearestFirst))
		api.getFocusObject = lambda: focus
		api.getFocusAncestors = lambda: ancestors
		self.focus_ancestry.reset_cache()

	def _query_name(self, focus):
		query = self.helpers.query_default_button(focus)
		return query.button.name if query.button is not None else None

	def _message(self, focus):
		import ui

		spoken = []
		original = ui.message
		ui.message = spoken.append
		try:
			plugin = self.module.GlobalPlugin.__new__(self.module.GlobalPlugin)
			plugin.script_announceDefaultButton(None)
		finally:
			ui.message = original
		self.assertEqual(len(spoken), 1)
		return spoken[0]

	def _insert_default_token(self, focus, roleKey, roleLabel, name):
		from globalPlugins._speech_core.base_processor import BaseSpeechProcessor
		from globalPlugins._speech_core.tokens import TOKEN_NAME, TOKEN_ROLE, token

		processor = BaseSpeechProcessor()
		processor.verbosity.announce_default_button = True
		tokens = [token(TOKEN_NAME, raw=[name], spoken=name), token(TOKEN_ROLE, raw=roleKey, spoken=roleLabel)]
		return [tok.text() for tok in processor._insert_focused_default_button_token(tokens, focus)]


class FileDialogTests(DefaultButtonTestBase):
	"""The Windows file dialog (LibreOffice, Notepad, most applications): a standard #32770 dialog."""

	DIALOG, SHELL, COMBO, EDIT, OPEN, CANCEL = 0x100, 0x110, 0x120, 0x121, 0x130, 0x140

	def setUp(self):
		super().setUp()
		self.user32 = user32 = FakeUser32()
		user32.add(self.DIALOG, "#32770", text="Open", exStyle=WS_EX_DLGMODALFRAME)
		user32.add(self.SHELL, "DUIViewWndClassName", parent=self.DIALOG)
		user32.add(self.COMBO, "ComboBoxEx32", parent=self.SHELL, ident=0x47C)
		user32.add(self.EDIT, "Edit", parent=self.COMBO, style=0x80)
		user32.add(self.OPEN, "Button", parent=self.DIALOG, text="&Open", style=BS_DEFSPLITBUTTON, ident=1)
		user32.add(self.CANCEL, "Button", parent=self.DIALOG, text="Cancel", style=BS_PUSHBUTTON, ident=2)
		user32.defaultIds[self.DIALOG] = 1
		self.win32.set_api(user32)
		self.edit = FakeObject("EDITABLETEXT", "File name:", hwnd=self.EDIT)
		self.open = FakeObject("SPLITBUTTON", "Open", hwnd=self.OPEN, iaStates=STATE_SYSTEM_DEFAULT)
		self.cancel = FakeObject("BUTTON", "Cancel", hwnd=self.CANCEL)
		self.dialog = FakeObject("DIALOG", "Open", hwnd=self.DIALOG, children=[self.edit, self.open, self.cancel])

	def test_file_name_field_reports_the_open_split_button(self):
		self._focus(self.edit, self.dialog)
		query = self.helpers.query_default_button(self.edit)
		self.assertEqual(query.button.name, "Open")
		self.assertTrue(query.button.certain)
		self.assertEqual(query.button.source, self.helpers.SOURCE_DIALOG)
		self.assertEqual(self._message(self.edit), "Default button Open")

	def test_cancel_focus_takes_priority_over_permanent_open(self):
		self.user32.move_focus(self.CANCEL, self.OPEN)
		self.cancel.IAccessibleStates = STATE_SYSTEM_DEFAULT
		self.open.IAccessibleStates = 0
		self._focus(self.cancel, self.dialog)
		self.assertEqual(self._message(self.cancel), "Default button Cancel")
		self.assertEqual(self.helpers.focused_button_default_status(self.cancel), (True, False, "Open"))

	def test_outlook_focused_cancel_overrides_details_permanent_default(self):
		self.user32.windows[self.OPEN].text = "Details"
		self.open.name = "Details"
		self.dialog.name = "Send/Receive"
		# No default state on Cancel is required.
		self._focus(self.cancel, self.dialog)
		self.assertEqual(self._message(self.cancel), "Default button Cancel")
		self._focus(self.edit, self.dialog)
		self.assertEqual(self._message(self.edit), "Default button Details")

	def test_focused_split_button_overrides_another_permanent_default(self):
		self.user32.defaultIds[self.DIALOG] = 2
		self.open.IAccessibleStates = 0
		self._focus(self.open, self.dialog)
		self.assertEqual(self._message(self.open), "Default button Open")

	def test_ineligible_focused_button_falls_back_to_dialog_default(self):
		for state in (controlTypes.State.UNAVAILABLE, controlTypes.State.INVISIBLE, controlTypes.State.OFFSCREEN):
			with self.subTest(state=state):
				self.cancel.states = {state}
				self._focus(self.cancel, self.dialog)
				self.assertEqual(self._message(self.cancel), "Default button Open")
		self.cancel.states = set()
		for attribute in ("enabled", "visible"):
			with self.subTest(windowAttribute=attribute):
				setattr(self.user32.windows[self.CANCEL], attribute, False)
				self.assertEqual(self._message(self.cancel), "Default button Open")
				setattr(self.user32.windows[self.CANCEL], attribute, True)

	def test_open_focus_is_the_default(self):
		self.user32.move_focus(self.OPEN, self.OPEN)
		self._focus(self.open, self.dialog)
		self.assertEqual(self.helpers.focused_button_default_status(self.open), (True, True, "Open"))

	def test_focus_speech_marks_the_open_split_button_default(self):
		self._focus(self.open, self.dialog)
		self.assertEqual(
			self._insert_default_token(self.open, "splitbutton", "split button", "Open"),
			["Open", "default", "split button"],
		)

	def test_focus_speech_leaves_cancel_alone(self):
		self.user32.move_focus(self.CANCEL, self.OPEN)
		self._focus(self.cancel, self.dialog)
		self.assertEqual(self._insert_default_token(self.cancel, "button", "button", "Cancel"), ["Cancel", "button"])

	def test_list_item_focus_reads_no_windows_and_no_buttons(self):
		item = FakeObject("LISTITEM", "report.odt", hwnd=self.SHELL)
		items = FakeObject("LIST", "Items View", hwnd=self.SHELL, children=[item])
		self._focus(item, items, self.dialog)
		self.user32.calls.clear()
		for _ in range(3):
			self.assertEqual(self.helpers.focused_button_default_status(item), (False, False, ""))
			self._insert_default_token(item, "listitem", "list item", "report.odt")
		self.assertEqual(self.user32.calls, [])
		# Moving through the file list notes the dialog's default from its
		# windows at most once a second, and never reads the list.
		for _ in range(5):
			self.helpers.remember_default_button_for_focus(item)
		self.assertEqual(self.user32.calls.count("descendants"), 1)
		self.assertEqual(self.dialog.childReads, 0)
		self.assertEqual(items.childReads, 0)

	def test_default_found_through_nested_windows(self):
		# Task dialogs keep their buttons inside other windows, not directly in the dialog.
		self.user32.windows[self.OPEN].parent = self.SHELL
		self._focus(self.edit, self.dialog)
		self.assertEqual(self._query_name(self.edit), "Open")

	def test_hidden_or_disabled_default_is_not_reported(self):
		self.user32.windows[self.OPEN].enabled = False
		self.open.states.add(controlTypes.State.UNAVAILABLE)
		self._focus(self.edit, self.dialog)
		self.assertIsNone(self.helpers.query_default_button(self.edit).button)
		self.user32.windows[self.OPEN].enabled = True
		self.user32.windows[self.OPEN].visible = False
		self.open.states = {controlTypes.State.INVISIBLE}
		self.open.IAccessibleStates = 0
		self.assertIsNone(self.helpers.query_default_button(self.edit).button)

	def test_property_sheet_uses_the_frame_default(self):
		frame, page, pageEdit, ok = 0x200, 0x210, 0x211, 0x220
		user32 = FakeUser32()
		user32.add(frame, "#32770", text="Properties")
		user32.add(page, "#32770", parent=frame)
		user32.add(pageEdit, "Edit", parent=page)
		user32.add(ok, "Button", parent=frame, text="OK", style=BS_DEFPUSHBUTTON, ident=1)
		user32.defaultIds[frame] = 1
		self.win32.set_api(user32)
		self.assertEqual(self.win32.dialog_windows(pageEdit), [frame, page])
		edit = FakeObject("EDITABLETEXT", "Name", hwnd=pageEdit)
		self._focus(edit, FakeObject("DIALOG", "Properties", hwnd=frame))
		self.assertEqual(self._query_name(edit), "OK")

	def test_nested_dialog_default_when_the_frame_has_none(self):
		frame, page, pageEdit, search = 0x300, 0x310, 0x311, 0x320
		user32 = FakeUser32()
		user32.add(frame, "MainFrame")
		user32.add(page, "#32770", parent=frame)
		user32.add(pageEdit, "Edit", parent=page)
		user32.add(search, "Button", parent=page, text="&Search", style=BS_DEFPUSHBUTTON, ident=7)
		user32.defaultIds[page] = 7
		self.win32.set_api(user32)
		edit = FakeObject("EDITABLETEXT", "Find", hwnd=pageEdit)
		self._focus(edit)
		self.assertEqual(self._query_name(edit), "Search")

	def test_ampersands_in_labels(self):
		clean = self.helpers.clean_default_button_label
		self.assertEqual(clean("&Open"), "Open")
		self.assertEqual(clean("Save && &Close"), "Save & Close")
		self.assertEqual(clean("OK default"), "OK")


class NvdaDialogTests(DefaultButtonTestBase):
	"""NVDA's own wx dialogs: NVDA's Speech settings reported "Change..." in 1.14."""

	CHANGE_HWND, OK_HWND, DIALOG_HWND, SLIDER_HWND = 0x500, 0x501, 0x502, 0x503

	def setUp(self):
		super().setUp()
		test = self

		class TopLevelWindow:
			pass

		class Dialog(TopLevelWindow):
			def __init__(self, default, *, settings=False, ok=None):
				self._default = default
				self._tmp = None
				self._ok = ok
				if settings:
					self._enterActivatesOk_ctrlSActivatesApply = lambda evt: None

			def GetDefaultItem(self):
				return self._tmp or self._default

			def GetTmpDefaultItem(self):
				return self._tmp

			def SetTmpDefaultItem(self, win):
				old = self.GetDefaultItem()
				self._tmp = win
				return old

			def FindWindow(self, ident):
				return self._ok if ident == wx.ID_OK else None

			def GetHandle(self):
				return test.DIALOG_HWND

		class Button:
			def __init__(self, label, hwnd, enabled=True):
				self.label = label
				self.hwnd = hwnd
				self.enabled = enabled

			def GetLabelText(self):
				return self.label.replace("&", "")

			def GetLabel(self):
				return self.label

			def IsShownOnScreen(self):
				return True

			def IsEnabled(self):
				return self.enabled

			def GetHandle(self):
				return self.hwnd

		self.state = types.SimpleNamespace(focusWin=object(), top=None)
		wx = types.ModuleType("wx")
		wx.ID_OK = 5100
		wx.TopLevelWindow = TopLevelWindow
		wx.IsMainThread = lambda: True
		wx.Window = types.SimpleNamespace(FindFocus=lambda: self.state.focusWin)
		wx.GetTopLevelParent = lambda win: self.state.top
		sys.modules["wx"] = wx
		self.Dialog = Dialog
		self.ok = Button("OK", self.OK_HWND)
		self.change = Button("C&hange...", self.CHANGE_HWND)
		self.dialogObj = FakeObject("DIALOG", "NVDA Settings: Speech", hwnd=self.DIALOG_HWND, processID=NVDA_PID)
		self.slider = FakeObject("SLIDER", "Pitch", hwnd=self.SLIDER_HWND, processID=NVDA_PID)
		self.changeObj = FakeObject("BUTTON", "Change...", hwnd=self.CHANGE_HWND, processID=NVDA_PID)
		self.okObj = FakeObject("BUTTON", "OK", hwnd=self.OK_HWND, processID=NVDA_PID)

	def test_speech_settings_report_ok_after_tab_passed_over_change(self):
		dialog = self.Dialog(self.ok, settings=True, ok=self.ok)
		self.state.top = dialog
		# Tab reaches Change...: wx makes it the temporary default while it has focus.
		dialog.SetTmpDefaultItem(self.change)
		self._focus(self.changeObj, self.dialogObj)
		# Query priority intentionally also applies to NVDA settings, despite
		# their application-specific Enter handler; automatic speech is unchanged.
		self.assertEqual(self._message(self.changeObj), "Default button Change...")
		self.assertEqual(self.helpers.focused_button_default_status(self.changeObj), (True, False, "OK"))
		self.assertEqual(
			self._insert_default_token(self.changeObj, "button", "button", "Change..."), ["Change...", "button"]
		)
		# Then the pitch slider: NVDA+E names OK, which Enter presses.
		dialog.SetTmpDefaultItem(None)
		self._focus(self.slider, self.dialogObj)
		self.assertEqual(self._message(self.slider), "Default button OK")

	def test_classicspeech_categories_report_ok_but_focused_cancel_reports_cancel(self):
		for title in ("ClassicSpeech Settings", "ClassicSpeech Web / Browse Mode Settings", "ClassicSpeech Voice Profiles"):
			with self.subTest(dialog=title):
				# These are plain wx dialogs, not NVDA SettingsDialog subclasses.
				dialog = self.Dialog(self.ok)
				self.state.top = dialog
				self.dialogObj.name = title
				list_name = "Voice profiles" if title == "ClassicSpeech Voice Profiles" else "Categories"
				category = FakeObject("LISTITEM", list_name, hwnd=self.SLIDER_HWND, processID=NVDA_PID)
				cancel = type(self.ok)("Cancel", self.CHANGE_HWND)
				cancel_obj = FakeObject("BUTTON", "Cancel", hwnd=self.CHANGE_HWND, processID=NVDA_PID)
				self._focus(category, self.dialogObj)
				self.assertEqual(self._message(category), "Default button OK")
				dialog.SetTmpDefaultItem(cancel)
				self._focus(cancel_obj, self.dialogObj)
				self.assertEqual(self._message(cancel_obj), "Default button Cancel")
				self.assertEqual(self.helpers.focused_button_default_status(cancel_obj), (True, False, "OK"))
				dialog.SetTmpDefaultItem(None)
				self._focus(category, self.dialogObj)
				self.assertEqual(self._message(category), "Default button OK")

	def test_plain_wx_dialog_reports_focused_button_before_its_own_default(self):
		dialog = self.Dialog(self.ok)
		self.state.top = dialog
		dialog.SetTmpDefaultItem(self.change)
		self._focus(self.changeObj, self.dialogObj)
		self.assertEqual(self._message(self.changeObj), "Default button Change...")
		# The temporary default is put back.
		self.assertIs(dialog.GetTmpDefaultItem(), self.change)

	def test_focused_default_button_is_default(self):
		dialog = self.Dialog(self.ok, settings=True, ok=self.ok)
		self.state.top = dialog
		dialog.SetTmpDefaultItem(self.ok)
		self._focus(self.okObj, self.dialogObj)
		self.assertEqual(self.helpers.focused_button_default_status(self.okObj), (True, True, "OK"))

	def test_wx_dialog_without_a_default_says_so(self):
		self.state.top = self.Dialog(None)
		self._focus(self.slider, self.dialogObj)
		query = self.helpers.query_default_button(self.slider)
		self.assertIsNone(query.button)
		self.assertFalse(query.screenCurtainBlocked)

	def test_disabled_default_is_not_reported(self):
		self.state.top = self.Dialog(type(self.ok)("OK", self.OK_HWND, enabled=False))
		self._focus(self.slider, self.dialogObj)
		self.assertEqual(self._message(self.slider), "No default button")

	def test_other_applications_never_use_nvdas_wx_window(self):
		self.state.top = self.Dialog(self.ok)
		other = FakeObject("SLIDER", "Volume", hwnd=0x900)
		self._focus(other, FakeObject("DIALOG", "Mixer", hwnd=0x901))
		self.assertIsNone(self.helpers.query_default_button(other).button)


class OtherWindowsToolkitTests(DefaultButtonTestBase):
	"""WinForms, wxWidgets in other programs, Delphi: only the default style marks the default button."""

	FORM, EDIT, OK, CANCEL = 0x600, 0x601, 0x602, 0x603

	def setUp(self):
		super().setUp()
		self.user32 = user32 = FakeUser32()
		user32.add(self.FORM, "WindowsForms10.Window.8.app.0.1", text="Rename", exStyle=WS_EX_DLGMODALFRAME)
		user32.add(self.EDIT, "WindowsForms10.EDIT.app.0.1", parent=self.FORM)
		user32.add(self.OK, "WindowsForms10.BUTTON.app.0.1", parent=self.FORM, text="OK", style=BS_DEFPUSHBUTTON)
		user32.add(self.CANCEL, "WindowsForms10.BUTTON.app.0.1", parent=self.FORM, text="Cancel", style=BS_PUSHBUTTON)
		self.win32.set_api(user32)
		self.edit = FakeObject("EDITABLETEXT", "New name", hwnd=self.EDIT)
		self.okObj = FakeObject("BUTTON", "OK", hwnd=self.OK)
		self.cancelObj = FakeObject("BUTTON", "Cancel", hwnd=self.CANCEL)
		self.formObj = FakeObject("WINDOW", "Rename", hwnd=self.FORM, children=[self.edit, self.okObj, self.cancelObj])

	def test_edit_field_reads_the_default_style(self):
		self._focus(self.edit, self.formObj)
		query = self.helpers.query_default_button(self.edit)
		self.assertEqual((query.button.name, query.button.certain), ("OK", True))

	def test_focused_cancel_overrides_remembered_default_only_for_query(self):
		self._focus(self.edit, self.formObj)
		self.helpers.remember_default_button_for_focus(self.edit)
		self.user32.move_focus(self.CANCEL, self.OK)
		self._focus(self.cancelObj, self.formObj)
		self.assertEqual(self._message(self.cancelObj), "Default button Cancel")
		self.assertEqual(self.helpers.focused_button_default_status(self.cancelObj), (True, False, "OK"))
		self.user32.move_focus(self.OK, self.OK)
		self._focus(self.okObj, self.formObj)
		self.assertEqual(self.helpers.focused_button_default_status(self.okObj), (True, True, "OK"))

	def test_focused_button_without_a_remembered_default_is_reported(self):
		self.user32.move_focus(self.CANCEL, self.OK)
		self._focus(self.cancelObj, self.formObj)
		self.assertEqual(self._message(self.cancelObj), "Default button Cancel")
		self.assertEqual(self.helpers.focused_button_default_status(self.cancelObj), (True, False, ""))

	def test_focused_button_overrides_remembered_absence(self):
		self.user32.windows[self.OK].style = BS_PUSHBUTTON
		self._focus(self.edit, self.formObj)
		self.helpers.remember_default_button_for_focus(self.edit)
		self.user32.move_focus(self.CANCEL, 0)
		self._focus(self.cancelObj, self.formObj)
		self.assertEqual(self._message(self.cancelObj), "Default button Cancel")

	def test_focus_note_is_limited_to_dialogs_and_throttled(self):
		self._focus(self.edit, self.formObj)
		self.helpers.remember_default_button_for_focus(self.edit)
		calls = len(self.user32.calls)
		self.assertGreater(calls, 0)
		self.helpers.remember_default_button_for_focus(self.edit)
		self.assertEqual(len(self.user32.calls), calls)
		# Not a dialog: a main window without a dialog frame is never read.
		self.user32.windows[self.FORM].exStyle = 0
		self.helpers.reset_default_button_cache()
		self.user32.calls.clear()
		self.helpers.remember_default_button_for_focus(self.edit)
		self.assertNotIn("descendants", self.user32.calls)

	def test_styles_of_other_window_classes_are_ignored(self):
		# A centered static text has the same low style bit as a default push button.
		self.user32.add(0x610, "Static", parent=self.FORM, text="Name:", style=0x1)
		self.assertEqual(self.win32.default_styled_buttons(self.EDIT), [self.OK])

	def test_nearest_default_button_wins(self):
		group, groupEdit, groupButton = 0x620, 0x621, 0x622
		self.user32.add(group, "WindowsForms10.Window.8.app.0.1", parent=self.FORM)
		self.user32.add(groupEdit, "WindowsForms10.EDIT.app.0.1", parent=group)
		self.user32.add(groupButton, "WindowsForms10.BUTTON.app.0.1", parent=group, text="Find", style=BS_DEFPUSHBUTTON)
		buttons = self.win32.default_styled_buttons(groupEdit)
		self.assertEqual(sorted(buttons), sorted([self.OK, groupButton]))
		self.assertEqual(self.win32.nearest_button(groupEdit, buttons), groupButton)
		self.assertEqual(self.win32.nearest_button(self.EDIT, buttons), self.OK)


class AccessibilityTreeTests(DefaultButtonTestBase):
	"""Toolkits without window handles for their buttons: LibreOffice, Qt, web pages, UI Automation."""

	def _dialog(self, windowClassName="SALFRAME", ia2=True):
		def make(role, name):
			obj = FakeObject(role, name, hwnd=0x700, windowClassName=windowClassName)
			if ia2:
				obj.IAccessibleObject = FakeIAccessible2()
			return obj

		self.okObj = make("BUTTON", "OK")
		self.cancelObj = make("BUTTON", "Cancel")
		self.edit = make("EDITABLETEXT", "Name")
		panel = FakeObject("PANE", "", hwnd=0x700, children=[self.okObj, self.cancelObj])
		self.dialogObj = FakeObject("DIALOG", "Insert Table", hwnd=0x700, children=[self.edit, panel])

	def _dialog_window(self, windowClassName):
		user32 = FakeUser32()
		user32.add(0x700, windowClassName, exStyle=WS_EX_DLGMODALFRAME)
		self.win32.set_api(user32)
		return user32

	def test_libreoffice_dialog_default_state_holds_whatever_has_focus(self):
		self._dialog()
		self.okObj.IAccessibleStates = STATE_SYSTEM_DEFAULT
		self._focus(self.cancelObj, self.dialogObj)
		self.assertEqual(self._message(self.cancelObj), "Default button Cancel")
		self._focus(self.okObj, self.dialogObj)
		self.assertEqual(self.helpers.focused_button_default_status(self.okObj), (True, True, "OK"))

	def test_libreoffice_dialogs_need_no_note(self):
		self._dialog()
		self._dialog_window("SALFRAME")
		self._focus(self.edit, self.dialogObj)
		reads = self.dialogObj.childReads
		self.helpers.remember_default_button_for_focus(self.edit)
		self.assertEqual(self.dialogObj.childReads, reads)

	def test_office_dialog_default_is_noted_while_focus_is_in_a_field(self):
		# Microsoft Office dialogs are neither IAccessible2 nor a window per
		# button, and give the default state to the focused button.
		self._dialog("bosa_sdm_msword", ia2=False)
		self.okObj.IAccessibleStates = STATE_SYSTEM_DEFAULT
		self._dialog_window("bosa_sdm_msword")
		self._focus(self.edit, self.dialogObj)
		self.helpers.remember_default_button_for_focus(self.edit)
		self.okObj.IAccessibleStates = 0
		self.cancelObj.IAccessibleStates = STATE_SYSTEM_DEFAULT
		self._focus(self.cancelObj, self.dialogObj)
		self.assertEqual(self.helpers.focused_button_default_status(self.cancelObj), (True, False, "OK"))
		self.assertEqual(self._message(self.cancelObj), "Default button Cancel")
		self.cancelObj.IAccessibleStates = 0
		self.okObj.IAccessibleStates = STATE_SYSTEM_DEFAULT
		self._focus(self.okObj, self.dialogObj)
		self.assertEqual(self.helpers.focused_button_default_status(self.okObj), (True, True, "OK"))

	def test_office_dialog_note_scans_once_per_dialog(self):
		self._dialog("bosa_sdm_msword", ia2=False)
		self._dialog_window("bosa_sdm_msword")
		self._focus(self.edit, self.dialogObj)
		self.helpers.remember_default_button_for_focus(self.edit)
		reads = self.dialogObj.childReads
		self.assertGreater(reads, 0)
		other = FakeObject("EDITABLETEXT", "Size", hwnd=0x700, windowClassName="bosa_sdm_msword")
		self.helpers._noted_hwnd = 0  # as if focus came from another window
		self._focus(other, self.dialogObj)
		self.helpers.remember_default_button_for_focus(other)
		self.assertEqual(self.dialogObj.childReads, reads)

	def test_office_focused_button_without_a_note_is_reported(self):
		self._dialog("bosa_sdm_msword", ia2=False)
		self.cancelObj.IAccessibleStates = STATE_SYSTEM_DEFAULT
		self._focus(self.cancelObj, self.dialogObj)
		self.assertEqual(self.helpers.focused_button_default_status(self.cancelObj), (True, False, ""))
		self.assertEqual(self._message(self.cancelObj), "Default button Cancel")

	def test_qt_query_prefers_focus_without_changing_default_status(self):
		# Qt uses IAccessible2, but makes the focused button the default.
		self._dialog("Qt6QWindowIcon")
		self.okObj.IAccessibleStates = STATE_SYSTEM_DEFAULT
		self._focus(self.edit, self.dialogObj)
		self.assertEqual(self._message(self.edit), "Default button OK")
		# Tab to Cancel: Qt makes it the default while it has focus.
		self.okObj.IAccessibleStates = 0
		self.cancelObj.IAccessibleStates = STATE_SYSTEM_DEFAULT
		self._focus(self.cancelObj, self.dialogObj)
		self.assertEqual(self.helpers.focused_button_default_status(self.cancelObj), (True, False, "OK"))
		self.assertEqual(self._message(self.cancelObj), "Default button Cancel")

	def test_qt_focused_button_without_an_earlier_answer(self):
		self._dialog("Qt6QWindowIcon")
		self.cancelObj.IAccessibleStates = STATE_SYSTEM_DEFAULT
		self._focus(self.cancelObj, self.dialogObj)
		self.assertEqual(self._message(self.cancelObj), "Default button Cancel")
		self.assertEqual(
			self._insert_default_token(self.cancelObj, "button", "button", "Cancel"), ["Cancel", "button"]
		)

	def test_ui_automation_legacy_default_state(self):
		self._dialog("Windows.UI.Core.CoreWindow", ia2=False)
		uia = types.ModuleType("UIAHandler")
		uia.UIA_LegacyIAccessibleStatePropertyId = 30096
		sys.modules["UIAHandler"] = uia

		class Element:
			def __init__(self, state):
				self.state = state

			def GetCurrentPropertyValue(self, propertyId):
				return self.state if propertyId == 30096 else 0

		self.okObj.UIAElement = Element(STATE_SYSTEM_DEFAULT)
		self.cancelObj.UIAElement = Element(0)
		self.edit.UIAElement = Element(0)
		self._focus(self.edit, self.dialogObj)
		self.assertEqual(self._query_name(self.edit), "OK")
		# UI Automation dialogs are not scanned on focus changes.
		self.helpers.reset_default_button_cache()
		self._dialog_window("Windows.UI.Core.CoreWindow")
		reads = self.dialogObj.childReads
		self.helpers.remember_default_button_for_focus(self.edit)
		self.assertEqual(self.dialogObj.childReads, reads)

	def test_web_form_default_submit_button(self):
		search = FakeObject("EDITABLETEXT", "Search", hwnd=0x800, IAccessibleObject=FakeIAccessible2())
		clear = FakeObject("BUTTON", "Clear", hwnd=0x800, IAccessibleObject=FakeIAccessible2())
		submit = FakeObject(
			"BUTTON", "Search", hwnd=0x800, iaStates=STATE_SYSTEM_DEFAULT, IAccessibleObject=FakeIAccessible2()
		)
		form = FakeObject("GROUPING", "", hwnd=0x800, children=[search, clear, submit], IA2Attributes={"tag": "form"})
		document = FakeObject("DOCUMENT", "Results", hwnd=0x800, children=[form])
		self._focus(search, form, document)
		self.assertEqual(self._message(search), "Default button Search")
		# On the submit button itself, its own default state answers at once.
		self._focus(submit, form, document)
		self.assertEqual(self._message(submit), "Default button Search")
		# Focus speech announces default buttons only in dialogs.
		self.assertEqual(self._insert_default_token(submit, "button", "button", "Search"), ["Search", "button"])

	def test_unresolved_query_keeps_exact_existing_message(self):
		self._focus(None)
		self.assertEqual(self._message(None), "No default button")
		guess = self.helpers.DefaultButton("Cancel", certain=False)
		query = self.helpers.DefaultButtonQuery(guess)
		self.assertEqual(self.module.GlobalPlugin._defaultButtonMessage(query), "No default button")

	def test_unnamed_focused_button_keeps_existing_unknown_label(self):
		button = FakeObject("BUTTON", "")
		self._focus(button)
		self.assertEqual(self._message(button), "Default button unknown")

	def test_web_page_without_a_form_or_dialog(self):
		link = FakeObject("LINK", "Home", hwnd=0x800)
		document = FakeObject("DOCUMENT", "Page", hwnd=0x800, children=[link])
		self._focus(link, document)
		self.assertEqual(self._message(link), "No default button")

	def test_negative_scan_is_remembered_for_focus_speech(self):
		self._dialog()
		self._focus(self.cancelObj, self.dialogObj)
		self.helpers.focused_button_default_status(self.cancelObj)
		reads = self.dialogObj.childReads
		self.helpers.focused_button_default_status(self.cancelObj)
		self.assertEqual(self.dialogObj.childReads, reads)


def _solid_button(fill, edge=None, label=(20, 20, 20), width=80, height=24):
	edge = edge or fill
	rows = []
	for y in range(height):
		row = []
		for x in range(width):
			if x in (0, width - 1) or y in (0, height - 1):
				row.append(edge)
			elif height // 3 <= y < 2 * height // 3 and width // 3 <= x < width // 2:
				row.append(label)
			else:
				row.append(fill)
		rows.append(row)
	return rows


class AppearanceTests(DefaultButtonTestBase):
	"""NVDA+E's last resort: the button drawn as the default one, as a sighted user sees it."""

	HOST = 0xA00
	GRAY = (251, 251, 251)
	BORDER_GRAY = (173, 173, 173)
	ACCENT = (0, 103, 192)

	def setUp(self):
		super().setUp()
		self.user32 = FakeUser32()
		self.user32.add(self.HOST, "WinUIDesktopWin32WindowClass", text="Notepad")
		self.user32.foregroundHwnd = self.HOST
		self.win32.set_api(self.user32)
		self.appearance.screen_curtain_active = lambda: False
		self.looks = {}
		self.appearance.set_capture(lambda left, top, width, height: self.looks[(left, top)])
		self.save = self._button("Save", 10, fill=self.ACCENT)
		self.dontSave = self._button("Don't save", 100, fill=self.GRAY, edge=self.BORDER_GRAY)
		self.cancel = self._button("Cancel", 190, fill=self.GRAY, edge=self.BORDER_GRAY)
		self.text = FakeObject("STATICTEXT", "Save your changes?", hwnd=self.HOST)
		self.dialogObj = FakeObject("DIALOG", "Notepad", hwnd=self.HOST, children=[self.text, self.save, self.dontSave, self.cancel])

	def _button(self, name, left, *, fill, edge=None):
		self.looks[(left, 400)] = _solid_button(fill, edge)
		return FakeObject("BUTTON", name, hwnd=self.HOST, location=(left, 400, 80, 24))

	def test_accent_filled_button_is_reported_by_appearance(self):
		self._focus(self.text, self.dialogObj)
		self.assertEqual(self._message(self.text), "Default button Save, by appearance")

	def test_focused_button_takes_priority_over_appearance(self):
		self._focus(self.cancel, self.dialogObj)
		self.assertEqual(self._message(self.cancel), "Default button Cancel")

	def test_focused_button_needs_no_screen_capture_even_with_curtain(self):
		self.appearance.screen_curtain_active = lambda: True
		def forbidden_capture(*args):
			self.fail("Focused button query must not capture screen pixels")
		self.appearance.set_capture(forbidden_capture)
		self._focus(self.cancel, self.dialogObj)
		self.assertEqual(self._message(self.cancel), "Default button Cancel")

	def test_accent_border_counts_only_away_from_buttons(self):
		self.looks[(10, 400)] = _solid_button(self.GRAY, (0, 120, 215))
		self._focus(self.text, self.dialogObj)
		self.assertEqual(self._query_name(self.text), "Save")
		# With focus on a button, the query does not need appearance.
		self._focus(self.cancel, self.dialogObj)
		self.assertEqual(self._message(self.cancel), "Default button Cancel")

	def test_two_colored_buttons_are_not_guessed(self):
		self.looks[(190, 400)] = _solid_button((196, 43, 28))
		self._focus(self.text, self.dialogObj)
		self.assertEqual(self._message(self.text), "No default button")

	def test_button_under_the_mouse_pointer_is_not_guessed(self):
		self.user32.cursorPos = (20, 410)
		self._focus(self.text, self.dialogObj)
		self.assertIsNone(self.helpers.query_default_button(self.text).button)

	def test_unavailable_buttons_do_not_count(self):
		self.save.states.add(controlTypes.State.UNAVAILABLE)
		self._focus(self.text, self.dialogObj)
		self.assertIsNone(self.helpers.query_default_button(self.text).button)

	def test_screen_curtain_is_named_when_it_hides_the_buttons(self):
		self.appearance.screen_curtain_active = lambda: True
		self._focus(self.text, self.dialogObj)
		query = self.helpers.query_default_button(self.text)
		self.assertIsNone(query.button)
		self.assertTrue(query.screenCurtainBlocked)
		self.assertEqual(
			self._message(self.text),
			"No default button found. Turn off Screen Curtain so ClassicSpeech can check how the buttons look.",
		)

	def test_screen_curtain_is_not_named_without_buttons_to_compare(self):
		self.appearance.screen_curtain_active = lambda: True
		self.dialogObj.children = [self.text, self.save]
		self._focus(self.text, self.dialogObj)
		self.assertEqual(self._message(self.text), "No default button")

	def test_black_screen_is_not_guessed(self):
		for key in self.looks:
			self.looks[key] = _solid_button((0, 0, 0))
		self._focus(self.text, self.dialogObj)
		query = self.helpers.query_default_button(self.text)
		self.assertIsNone(query.button)
		self.assertFalse(query.screenCurtainBlocked)

	def test_dialog_behind_another_window_is_not_guessed(self):
		self.user32.add(0xB00, "Chrome_WidgetWin_1")
		self.user32.foregroundHwnd = 0xB00
		self._focus(self.text, self.dialogObj)
		self.assertIsNone(self.helpers.query_default_button(self.text).button)

	def test_reported_default_buttons_are_not_second_guessed(self):
		self.cancel.IAccessibleStates = STATE_SYSTEM_DEFAULT
		self._focus(self.text, self.dialogObj)
		self.assertEqual(self._message(self.text), "Default button Cancel")

	def test_focus_speech_never_uses_appearance(self):
		self._focus(self.save, self.dialogObj)
		self.assertEqual(self.helpers.focused_button_default_status(self.save), (True, False, ""))


class Win32ApiTests(DefaultButtonTestBase):
	def test_windows_calls_stay_off_outside_nvda(self):
		self.win32.set_api(None)
		fakeGlobalVars = types.ModuleType("globalVars")
		fakeGlobalVars.appPid = 0
		original = sys.modules.get("globalVars")
		sys.modules["globalVars"] = fakeGlobalVars
		try:
			self.assertIsNone(self.win32.get_api())
		finally:
			if original is None:
				sys.modules.pop("globalVars", None)
			else:
				sys.modules["globalVars"] = original
			self.win32.set_api(False)

	@unittest.skipUnless(sys.platform == "win32", "needs Windows")
	def test_real_dialog_keeps_its_default_id_while_cancel_has_focus(self):
		"""A real, never shown #32770 dialog: DM_GETDEFID and the moving default style."""
		import ctypes
		import struct
		from ctypes import wintypes

		user32 = ctypes.WinDLL("user32")
		DLGPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
		create = ctypes.WINFUNCTYPE(wintypes.HWND, wintypes.HINSTANCE, ctypes.c_void_p, wintypes.HWND, DLGPROC, wintypes.LPARAM)(
			("CreateDialogIndirectParamW", user32)
		)
		destroy = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND)(("DestroyWindow", user32))
		send = ctypes.WINFUNCTYPE(wintypes.LPARAM, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)(
			("SendMessageW", user32)
		)
		getItem = ctypes.WINFUNCTYPE(wintypes.HWND, wintypes.HWND, ctypes.c_int)(("GetDlgItem", user32))

		def text(value):
			return value.encode("utf-16-le") + b"\0\0"

		def align(data):
			return data + b"\0" * (-len(data) % 4)

		def item(style, y, ident, atom, label):
			data = struct.pack("<IIhhhhH", 0x50010000 | style, 0, 10, y, 60, 14, ident)
			return align(data + struct.pack("<HH", 0xFFFF, atom) + text(label) + struct.pack("<H", 0))

		# WS_POPUP | WS_CAPTION | DS_MODALFRAME | DS_SETFONT, without WS_VISIBLE: never shown.
		header = struct.pack("<IIHhhhh", 0x80C000C0, 0, 3, 0, 0, 100, 80)
		header += struct.pack("<HH", 0, 0) + text("Open") + struct.pack("<H", 8) + text("MS Shell Dlg")
		template = align(header)
		template += item(0x80, 10, 100, 0x0081, "")
		template += item(BS_DEFSPLITBUTTON, 30, 1, 0x0080, "&Open")
		template += item(BS_PUSHBUTTON, 50, 2, 0x0080, "Cancel")
		buffer = ctypes.create_string_buffer(template)
		proc = DLGPROC(lambda hwnd, msg, wParam, lParam: 1 if msg == 0x0110 else 0)
		dialog = create(None, buffer, None, proc, 0)
		self.assertTrue(dialog)
		try:
			api = self.win32._User32()
			edit, ok, cancel = (int(getItem(dialog, ident) or 0) for ident in (100, 1, 2))
			dialog = int(dialog)
			self.assertEqual(api.class_name(dialog), "#32770")
			self.assertEqual(self.win32.dialog_windows(edit, api), [dialog])
			self.assertEqual(api.default_id(dialog), 1)
			self.assertEqual(api.text(ok), "&Open")
			self.assertTrue(self.win32.is_push_button_window(ok, api))
			self.assertFalse(self.win32.is_push_button_window(edit, api))
			self.assertEqual(api.style(ok) & 0xF, BS_DEFSPLITBUTTON)
			send(dialog, 0x0028, cancel, 1)  # WM_NEXTDLGCTL: focus Cancel, as Tab does
			self.assertEqual(api.style(cancel) & 0xF, BS_DEFPUSHBUTTON)
			self.assertEqual(api.style(ok) & 0xF, BS_SPLITBUTTON)
			self.assertEqual(api.default_id(dialog), 1)
			send(dialog, 0x0028, edit, 1)
			self.assertEqual(api.style(ok) & 0xF, BS_DEFSPLITBUTTON)
			self.assertEqual(api.style(cancel) & 0xF, BS_PUSHBUTTON)
		finally:
			destroy(dialog)


if __name__ == "__main__":
	unittest.main(verbosity=2)
