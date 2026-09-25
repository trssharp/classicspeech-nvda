# -*- coding: UTF-8 -*-
from __future__ import annotations

from typing import Optional
import os
import re

import controlTypes
import logHandler

from . import default_button_appearance as appearance
from . import focus_ancestry
from . import win32_default_button as win32

log = logHandler.log


def clean_default_button_label(label: str) -> str:
	"""Return a raw button label safe for default-button query speech.

	ClassicSpeech may inject a speakable ``default`` state token into focus
	speech.  Manual query paths must never feed that decorated speech back as
	the button name, otherwise Insert+E can say things like
	``Default button OK default``.

	Windows labels mark the access key with ``&`` and write a literal ampersand
	as ``&&``.
	"""
	text = str(label or "").replace("&&", "\0").replace("&", "").replace("\0", "&").strip()
	# Be conservative: only remove a final standalone state/role suffix.
	text = re.sub(r"\s+default(?:\s+button)?\s*$", "", text, flags=re.IGNORECASE).strip()
	return text


def get_object_name(obj) -> str:
	try:
		name = getattr(obj, "name", None)
		if name:
			return clean_default_button_label(name)
	except Exception:
		pass
	return ""


def _find_dialog_in_lineage(lineage, start=0):
	for index in range(start, len(lineage)):
		try:
			if focus_ancestry.role_at(lineage, index) == controlTypes.Role.DIALOG:
				return lineage[index]
		except Exception:
			continue
	return None


def get_dialog_ancestor(obj):
	"""Return the nearest dialog containing ``obj`` (``obj`` included).

	For the focus object this reads NVDA's cached focus ancestors and
	remembers the answer until focus moves, instead of creating up to twenty
	parent objects for every speech sequence.
	"""
	if not obj:
		return None
	lineage = focus_ancestry.lineage_for(obj, 20)
	if not lineage:
		return None
	if focus_ancestry.is_focus(obj):
		# The focus itself may be a dialog; check it fresh, then reuse the
		# remembered ancestor answer.
		try:
			if getattr(obj, "role", None) == controlTypes.Role.DIALOG:
				return obj
		except Exception:
			pass
		return focus_ancestry.memoized_for_focus(
			"dialogAncestor",
			lambda: _find_dialog_in_lineage(lineage, start=1),
		)
	return _find_dialog_in_lineage(lineage)


def object_is_in_dialog(obj) -> bool:
	return get_dialog_ancestor(obj) is not None


def iter_dialog_children(container):
	if not container:
		return []
	try:
		children = getattr(container, "children", None)
		if children:
			return list(children)
	except Exception:
		pass
	return []


def _default_button_scan_skips(obj) -> bool:
	"""Return True for containers that never hold a dialog's default button.

	File dialogs expose Explorer's item list, navigation tree and preview
	document inside the dialog. Enumerating those children is slow and can
	touch hundreds of cross-process objects, so the default-button scan does
	not descend into them.
	"""
	try:
		role = getattr(obj, "role", None)
		return role in _DEFAULT_BUTTON_SCAN_SKIP_ROLES
	except Exception:
		return False


def _default_button_scan_skip_roles():
	names = (
		"LIST", "LISTITEM", "TREEVIEW", "TREEVIEWITEM", "TABLE", "TABLEROW",
		"TABLECELL", "DOCUMENT", "EDITABLETEXT", "MENU", "MENUBAR", "POPUPMENU",
		"DATAGRID", "DATAITEM", "TERMINAL", "RICHEDIT",
	)
	roles = set()
	for name in names:
		role = getattr(controlTypes.Role, name, None)
		if role is not None:
			roles.add(role)
	return frozenset(roles)


_DEFAULT_BUTTON_SCAN_SKIP_ROLES = _default_button_scan_skip_roles()


def iter_dialog_descendants(container, max_depth=8, max_objects=150):
	"""Yield descendants of a dialog without trusting one flat child list.

	Some toolkits expose buttons under panels/property pages rather than as direct
	children of the dialog.  Keep this bounded because accessibility trees can be
	weird little hedge mazes.
	"""
	if not container:
		return
	queue = [(child, 1) for child in iter_dialog_children(container)]
	seen = set()
	count = 0
	while queue and count < max_objects:
		obj, depth = queue.pop(0)
		try:
			key = (getattr(obj, "windowHandle", None), getattr(obj, "IAccessibleChildID", None), id(obj))
		except Exception:
			key = id(obj)
		if key in seen:
			continue
		seen.add(key)
		count += 1
		yield obj
		if depth >= max_depth or _default_button_scan_skips(obj):
			continue
		try:
			children = iter_dialog_children(obj)
		except Exception:
			children = []
		for child in children:
			queue.append((child, depth + 1))


# ---------------------------------------------------------------------------
# Default button
#
# NVDA+E first reports an eligible focused push/split button. Otherwise it
# uses the dialog's own default detection below, also used by automatic focus
# speech. These detectors ask, in this order:
#
# 1. NVDA's own wx dialogs, through wx (NVDA's settings dialogs press OK).
# 2. Standard Windows dialogs, with DM_GETDEFID.
# 3. The default push-button style of the window's buttons.
# 4. The accessibility tree: a button, or split button, that reports the
#    default state (MSAA, IAccessible2, or UI Automation's LegacyIAccessible),
#    in the dialog or, for web pages, the form around the focus.
# 5. For NVDA+E only, how the dialog's buttons look on screen.
#
# Many toolkits make a push button the default for as long as it has focus
# (Windows itself, wxWidgets, WinForms, Delphi, Qt, Microsoft Office). Such a
# focused button's default state says nothing about the dialog's own default,
# so it is only a guess and is never announced as "default" in focus speech.
# For these toolkits, the default seen while focus was on another control is
# remembered (remember_default_button_for_focus).
# ---------------------------------------------------------------------------

#: Where an answer came from.
SOURCE_FOCUS = "focus"
SOURCE_WX = "wx"
SOURCE_DIALOG = "dialog"
SOURCE_STYLE = "style"
SOURCE_ACCESSIBILITY = "accessibility"
SOURCE_APPEARANCE = "appearance"


class DefaultButton:
	"""A button selected by the query or dialog-default detection.

	``certain`` is False for guesses from the permanent-default lookup or
	appearance. The explicit query's focused-button choice is certain under
	its reporting policy, not a claim about the dialog's permanent default.
	"""

	__slots__ = ("name", "hwnd", "obj", "source", "certain")

	def __init__(self, name, *, hwnd=None, obj=None, source="", certain=True):
		self.name = clean_default_button_label(name)
		self.hwnd = int(hwnd) if hwnd else None
		self.obj = obj
		self.source = source
		self.certain = bool(certain)

	def __repr__(self):
		return (
			f"DefaultButton({self.name!r}, hwnd={self.hwnd!r}, source={self.source!r}, "
			f"certain={self.certain!r})"
		)


class DefaultButtonQuery:
	"""What NVDA+E reports: the default button, or why none was found."""

	__slots__ = ("button", "screenCurtainBlocked")

	def __init__(self, button=None, *, screenCurtainBlocked=False):
		self.button = button
		#: True when only the appearance check could have found the button, and
		#: NVDA's Screen Curtain kept it from seeing the screen.
		self.screenCurtainBlocked = bool(screenCurtainBlocked)


def _default_button_roles():
	roles = set()
	for name in ("BUTTON", "SPLITBUTTON"):
		role = getattr(controlTypes.Role, name, None)
		if role is not None:
			roles.add(role)
	return frozenset(roles)


#: Roles a default button can have: a push button, or a split button such as
#: the Open button of the Windows file dialog.
_DEFAULT_BUTTON_ROLES = _default_button_roles()


def is_button(obj) -> bool:
	"""True for a push button or a split button."""
	try:
		return getattr(obj, "role", None) in _DEFAULT_BUTTON_ROLES
	except Exception:
		return False


_STATE_SYSTEM_DEFAULT = 0x100
#: UIA_LegacyIAccessibleStatePropertyId, for NVDA builds whose UIAHandler lacks the name.
_UIA_LEGACY_STATE_PROPERTY_ID = 30096
#: NVDA has no default state today; a future one is used when it appears.
_NVDA_DEFAULT_STATES = tuple(
	state
	for state in (
		getattr(controlTypes.State, name, None) for name in ("DEFAULT", "DEFBUTTON", "DEFAULT_BUTTON")
	)
	if state is not None
)


def _uia_legacy_state(obj) -> int:
	try:
		element = getattr(obj, "UIAElement", None)
	except Exception:
		element = None
	if element is None:
		return 0
	try:
		import UIAHandler

		propertyId = getattr(UIAHandler, "UIA_LegacyIAccessibleStatePropertyId", _UIA_LEGACY_STATE_PROPERTY_ID)
		value = element.GetCurrentPropertyValue(propertyId)
		return value if isinstance(value, int) else 0
	except Exception:
		return 0


def _has_explicit_default_state(obj) -> bool:
	if _NVDA_DEFAULT_STATES:
		try:
			states = getattr(obj, "states", set()) or set()
		except Exception:
			states = set()
		if any(state in states for state in _NVDA_DEFAULT_STATES):
			return True
	try:
		if int(getattr(obj, "IAccessibleStates", 0) or 0) & _STATE_SYSTEM_DEFAULT:
			return True
	except Exception:
		pass
	return bool(_uia_legacy_state(obj) & _STATE_SYSTEM_DEFAULT)


def is_same_object(a, b) -> bool:
	if not a or not b:
		return False
	if a is b:
		return True

	def _sig(obj):
		try:
			return (
				getattr(obj, "windowHandle", None),
				getattr(obj, "IAccessibleChildID", None),
				getattr(obj, "role", None),
				get_object_name(obj),
				getattr(obj, "location", None),
			)
		except Exception:
			return None

	sig_a = _sig(a)
	sig_b = _sig(b)

	if sig_a is not None and sig_b is not None:
		return sig_a == sig_b

	return False


def _window_handle(obj) -> int:
	try:
		return int(getattr(obj, "windowHandle", 0) or 0)
	except Exception:
		return 0


def _is_nvda_process_object(obj) -> bool:
	try:
		return int(getattr(obj, "processID", 0) or 0) == os.getpid()
	except Exception:
		return False


def _is_qt(obj) -> bool:
	try:
		return str(getattr(obj, "windowClassName", "") or "").startswith("Qt")
	except Exception:
		return False


def _is_ia2_object(obj) -> bool:
	try:
		accessible = getattr(obj, "IAccessibleObject", None)
	except Exception:
		return False
	if accessible is None:
		return False
	try:
		import IAccessibleHandler

		return isinstance(accessible, IAccessibleHandler.IA2.IAccessible2)
	except Exception:
		return False


def _is_uia_object(obj) -> bool:
	try:
		return getattr(obj, "UIAElement", None) is not None
	except Exception:
		return False


def _default_state_follows_focus(obj) -> bool:
	"""True unless a focused button's default state is known to be the dialog's own.

	Windows push buttons and the toolkits built on them move the default
	style to the focused button, as Qt does with its auto-default buttons and
	Microsoft Office with its dialogs. Only IAccessible2 applications other
	than Qt, that is web browsers (a web form's first submit button) and
	LibreOffice, keep the default state on the dialog's own default button
	whatever has focus.
	"""
	return _is_qt(obj) or not _is_ia2_object(obj)


def _in_dialog(obj) -> bool:
	if object_is_in_dialog(obj):
		return True
	hwnd = _window_handle(obj)
	return bool(hwnd) and win32.looks_like_dialog(hwnd)


#: Seconds an empty default-button scan stays valid for one dialog. A dialog
#: without an exposed default button is otherwise rescanned on every keypress.
NEGATIVE_DEFAULT_SCAN_SECONDS = 10.0
#: Seconds before focus on the same window is looked at again for its default.
FOCUS_NOTE_SECONDS = 1.0

# The accessibility scan's last answer for one dialog: a certain DefaultButton,
# or None for "none found" (kept NEGATIVE_DEFAULT_SCAN_SECONDS).
_cached_dialog_key = None
_cached_default = None
_cached_scan_time = 0.0

# The default push button last seen in a top-level window while focus was on
# another kind of control, or None when it had none then.
_remembered_root = 0
_remembered_default = None
_noted_hwnd = 0
_noted_time = 0.0


def _monotonic():
	try:
		import time
		return time.monotonic()
	except Exception:
		return 0.0


def reset_default_button_cache() -> None:
	"""Forget every remembered default button (tests and plugin reload)."""
	global _cached_dialog_key, _cached_default, _cached_scan_time
	global _remembered_root, _remembered_default, _noted_hwnd, _noted_time
	_cached_dialog_key = None
	_cached_default = None
	_cached_scan_time = 0.0
	_remembered_root = 0
	_remembered_default = None
	_noted_hwnd = 0
	_noted_time = 0.0


# --- 1. NVDA's own wx windows ----------------------------------------------


def _wx_top_level_for(obj):
	"""Return NVDA's wx top-level window that holds ``obj``, or None."""
	if not _is_nvda_process_object(obj):
		return None
	try:
		import wx

		if not wx.IsMainThread():
			return None
		focusWin = wx.Window.FindFocus()
		if not focusWin:
			return None
		top = wx.GetTopLevelParent(focusWin)
		if not top or not isinstance(top, wx.TopLevelWindow):
			return None
		# A native message box NVDA shows is not wx; its owner frame must not answer for it.
		root = win32.root_window(_window_handle(obj))
		if root and int(top.GetHandle()) != root:
			return None
		return top
	except Exception:
		return None


def _wx_permanent_default_item(top):
	"""Return ``top``'s own default item, never a button that is default only while focused.

	wxWidgets on Windows makes a focused button the temporary default
	(``wxButton::SetTmpDefault``), and ``GetDefaultItem()`` returns it.
	ClassicSpeech 1.14 remembered that button, so NVDA+E in NVDA's Speech
	settings reported "Change..." once Tab had passed over it.
	"""
	getTmp = getattr(top, "GetTmpDefaultItem", None)
	setTmp = getattr(top, "SetTmpDefaultItem", None)
	tmp = getTmp() if callable(getTmp) else None
	if tmp is None:
		return top.GetDefaultItem()
	if not callable(setTmp):
		return None
	# Only a pointer in wxTopLevelWindow changes, and it is put back at once;
	# no button style or event is involved.
	setTmp(None)
	try:
		return top.GetDefaultItem()
	finally:
		setTmp(tmp)


def _wx_default_item(top):
	# NVDA's settings dialogs press OK for Enter in any control
	# (SettingsDialog._enterActivatesOk_ctrlSActivatesApply).
	if callable(getattr(top, "_enterActivatesOk_ctrlSActivatesApply", None)):
		try:
			import wx

			ok = top.FindWindow(wx.ID_OK)
		except Exception:
			ok = None
		if ok is not None and callable(getattr(ok, "GetLabel", None)):
			return ok
	return _wx_permanent_default_item(top)


def _wx_default_button(obj):
	"""Return ``(True, DefaultButton or None)`` for NVDA's own wx windows, else ``(False, None)``."""
	top = _wx_top_level_for(obj)
	if top is None:
		return False, None
	try:
		item = _wx_default_item(top)
		if item is None:
			return True, None
		shown = getattr(item, "IsShownOnScreen", None) or getattr(item, "IsShown", None)
		if (callable(shown) and not shown()) or not item.IsEnabled():
			return True, None
		try:
			label = item.GetLabelText()
		except Exception:
			label = item.GetLabel()
		try:
			hwnd = int(item.GetHandle())
		except Exception:
			hwnd = None
		return True, DefaultButton(label, hwnd=hwnd, source=SOURCE_WX)
	except Exception:
		log.debugWarning("ClassicSpeech: wx default button lookup failed", exc_info=True)
		return False, None


# --- 2 and 3. Windows dialogs and default push-button styles ----------------


def _accessible_name_for_window(hwnd) -> str:
	try:
		import winUser
		from NVDAObjects.IAccessible import getNVDAObjectFromEvent

		obj = getNVDAObjectFromEvent(hwnd, winUser.OBJID_CLIENT, 0)
		return str(getattr(obj, "name", "") or "") if obj else ""
	except Exception:
		return ""


def _win32_button_info(hwnd, source, certain=True):
	if not hwnd:
		return None
	name = win32.button_text(hwnd)
	if not clean_default_button_label(name):
		# A button that shows a picture has no text, only an accessible name, if any.
		name = _accessible_name_for_window(hwnd)
	return DefaultButton(name, hwnd=hwnd, source=source, certain=certain)


def _remember(root, info) -> None:
	global _remembered_root, _remembered_default
	_remembered_root = root
	_remembered_default = info


def _remembered_for(hwnd):
	"""Return ``(known, DefaultButton or None)`` remembered for ``hwnd``'s top-level window."""
	root = win32.root_window(hwnd)
	if not root or root != _remembered_root:
		return False, None
	info = _remembered_default
	if info is None:
		return True, None
	if not info.hwnd or not win32.is_usable(info.hwnd):
		return False, None
	return True, info


def _win32_default_button(obj):
	"""Return ``(answer, guess)`` from window handles.

	``answer`` is a DefaultButton, ``False`` when ClassicSpeech knows the window
	has no default button, or None when window handles cannot tell.
	"""
	hwnd = _window_handle(obj)
	if not hwnd or not win32.get_api():
		return None, None
	button = win32.dialog_default_button(hwnd)
	if button:
		info = _win32_button_info(button, SOURCE_DIALOG)
		if info is not None:
			return info, None
	focusButton = hwnd if win32.is_push_button_window(hwnd) else 0
	styled = win32.default_styled_buttons(hwnd)
	others = [button for button in styled if button != focusButton]
	if others:
		info = _win32_button_info(win32.nearest_button(hwnd, others), SOURCE_STYLE)
		if info is not None:
			if not focusButton:
				_remember(win32.root_window(hwnd), info)
			return info, None
	if focusButton and focusButton in styled:
		# The focused button has the default style because it has focus.
		known, remembered = _remembered_for(hwnd)
		if known:
			return (remembered if remembered is not None else False), None
		return None, _win32_button_info(focusButton, SOURCE_STYLE, certain=False)
	return None, None


def remember_default_button_for_focus(obj) -> None:
	"""Note a dialog's default button while focus is on another kind of control.

	Called for every focus change. Once focus is on a push button, Windows and
	most toolkits make that button the default, so a dialog's own default can
	only be seen while focus is elsewhere. This runs only in dialogs, at most
	once a second for the same window, and reads window styles; for buttons
	without windows of their own, see ``_note_accessible_default``.
	"""
	global _noted_hwnd, _noted_time
	try:
		if obj is None or is_button(obj) or not win32.get_api():
			return
		hwnd = _window_handle(obj)
		if not hwnd:
			return
		now = _monotonic()
		if hwnd == _noted_hwnd and now - _noted_time < FOCUS_NOTE_SECONDS:
			return
		_noted_hwnd = hwnd
		_noted_time = now
		# NVDA's own dialogs answer through wx, and a push button's own style is temporary.
		if _is_nvda_process_object(obj) or win32.is_push_button_window(hwnd):
			return
		if not _in_dialog(obj):
			return
		root = win32.root_window(hwnd)
		if not root:
			return
		styled = win32.default_styled_buttons(hwnd)
		info = _win32_button_info(win32.nearest_button(hwnd, styled), SOURCE_STYLE) if styled else None
		_remember(root, info)
		if info is None and not win32.dialog_windows(hwnd):
			_note_accessible_default(obj)
	except Exception:
		log.debugWarning("ClassicSpeech: noting the default button failed", exc_info=True)


def _note_accessible_default(obj) -> None:
	"""Read the default state of a dialog's buttons that have no windows of their own.

	Only for toolkits whose focused button becomes the default (Office, Qt, and
	others without IAccessible2): with focus on another control the default
	state is on the dialog's own default button. At most one bounded scan per
	dialog every NEGATIVE_DEFAULT_SCAN_SECONDS. UI Automation applications
	report no default state, so they are not scanned.
	"""
	if not _default_state_follows_focus(obj) or _is_uia_object(obj):
		return
	dialog = get_dialog_ancestor(obj)
	if dialog is None:
		return
	key = _container_key(dialog)
	if key == _cached_dialog_key and _monotonic() - _cached_scan_time < NEGATIVE_DEFAULT_SCAN_SECONDS:
		return
	button = _scan_for_default_button(dialog)
	_store_scan(key, DefaultButton(get_object_name(button), obj=button, source=SOURCE_ACCESSIBILITY) if button else None)


# --- 4. The accessibility tree ----------------------------------------------


def _is_html_form(obj) -> bool:
	try:
		attributes = getattr(obj, "IA2Attributes", None)
		return bool(attributes) and str(attributes.get("tag", "")).lower() == "form"
	except Exception:
		return False


def _find_form_in_lineage(lineage, start=0):
	formRole = getattr(controlTypes.Role, "FORM", None)
	documentRole = getattr(controlTypes.Role, "DOCUMENT", None)
	for index in range(start, len(lineage)):
		try:
			role = focus_ancestry.role_at(lineage, index)
		except Exception:
			continue
		if formRole is not None and role == formRole:
			return lineage[index]
		if documentRole is not None and role == documentRole:
			# A web form ends at its document.
			return None
		if _is_html_form(lineage[index]):
			return lineage[index]
	return None


def get_form_ancestor(obj):
	"""Return the web form that holds ``obj``, whose Enter key uses its default button."""
	if not obj:
		return None
	lineage = focus_ancestry.lineage_for(obj, 20)
	if not lineage:
		return None
	if focus_ancestry.is_focus(obj):
		return focus_ancestry.memoized_for_focus(
			"formAncestor",
			lambda: _find_form_in_lineage(lineage, start=1),
		)
	return _find_form_in_lineage(lineage, start=1)


def _default_button_container(obj):
	"""Return the dialog, or else the web form, whose default button ``obj`` uses."""
	dialog = get_dialog_ancestor(obj)
	if dialog is not None:
		return dialog
	return get_form_ancestor(obj)


def _container_key(container):
	try:
		return (
			getattr(container, "windowHandle", None),
			getattr(container, "IAccessibleChildID", None),
			getattr(container, "role", None),
			get_object_name(container),
		)
	except Exception:
		return (id(container),)


def get_dialog_key(obj):
	"""Return a key for the dialog, or web form, around ``obj``, or None."""
	container = _default_button_container(obj)
	if container is None:
		return None
	return _container_key(container)


_UNAVAILABLE_STATE = getattr(controlTypes.State, "UNAVAILABLE", None)


def _is_unavailable(obj) -> bool:
	if _UNAVAILABLE_STATE is None:
		return False
	try:
		return _UNAVAILABLE_STATE in (getattr(obj, "states", set()) or set())
	except Exception:
		return False


def _is_default_candidate(obj) -> bool:
	# Enter cannot press a disabled button, whatever state it reports.
	return is_button(obj) and _has_explicit_default_state(obj) and not _is_unavailable(obj)


def _scan_for_default_button(container):
	"""Return the first button or split button in ``container`` that reports the default state."""
	# First pass: direct children.  This preserves the old behavior for simple
	# dialogs and avoids diving into larger trees unless needed.
	for child in iter_dialog_children(container):
		if _is_default_candidate(child):
			return child
	# Second pass: descendants.  wx and UIA often hide the real buttons under
	# panels or property pages.
	for child in iter_dialog_descendants(container):
		if _is_default_candidate(child):
			return child
	return None


def _store_scan(key, info) -> None:
	global _cached_dialog_key, _cached_default, _cached_scan_time
	_cached_dialog_key = key
	_cached_default = info
	_cached_scan_time = _monotonic()


def _accessible_default_button(obj, use_negative_cache):
	"""Return ``(answer, guess)`` from the accessibility tree; see ``_win32_default_button``."""
	# A focused button that reports the default state, in a toolkit where that
	# does not just follow focus, is the default button (a web form's first
	# submit button, for example).
	if is_button(obj) and _has_explicit_default_state(obj) and not _default_state_follows_focus(obj):
		return DefaultButton(get_object_name(obj), obj=obj, source=SOURCE_ACCESSIBILITY), None
	container = _default_button_container(obj)
	if container is None:
		return None, None
	key = _container_key(container)
	if use_negative_cache and key == _cached_dialog_key:
		if _cached_default is not None:
			return _cached_default, None
		if _monotonic() - _cached_scan_time < NEGATIVE_DEFAULT_SCAN_SECONDS:
			return False, None
	button = _scan_for_default_button(container)
	if button is None:
		_store_scan(key, None)
		return False, None
	info = DefaultButton(get_object_name(button), obj=button, source=SOURCE_ACCESSIBILITY)
	if is_same_object(button, obj) and _default_state_follows_focus(obj):
		# Default only while it has focus: keep a certain earlier answer.
		if key == _cached_dialog_key and _cached_default is not None:
			return _cached_default, None
		info.certain = False
		return None, info
	_store_scan(key, info)
	return info, None


# --- Putting it together ------------------------------------------------------


def _lookup(obj, *, use_negative_cache=True):
	"""Return ``(answer, guess, settled)``.

	``answer`` is a certain DefaultButton or None, and ``guess`` an uncertain
	one. ``settled`` is True when nothing else could do better, even without an
	answer: NVDA's own dialogs, whose default wx reports exactly, or a window
	seen to have no default button while focus was on another control.
	"""
	if not obj:
		return None, None, True
	applies, info = _wx_default_button(obj)
	if applies:
		return info, None, True
	answer, guess = _win32_default_button(obj)
	if answer is False:
		return None, None, True
	if answer is not None:
		return answer, None, True
	answer, scanGuess = _accessible_default_button(obj, use_negative_cache)
	if answer:
		return answer, None, True
	return None, guess or scanGuess, False


def find_default_button_info(obj, *, use_negative_cache=True):
	"""Return the ``DefaultButton`` for ``obj``'s dialog, a guess, or None."""
	answer, guess, _settled = _lookup(obj, use_negative_cache=use_negative_cache)
	return answer or guess


def _dialog_buttons(dialog):
	buttons = []
	for child in iter_dialog_descendants(dialog):
		if is_button(child):
			buttons.append(child)
			if len(buttons) >= appearance.MAX_BUTTONS:
				break
	return buttons


def query_default_button(obj) -> DefaultButtonQuery:
	"""Answer NVDA+E: prefer the focused button, then use dialog-default detection.

	This query policy does not change automatic focus speech or its cache.
	It is not a resolver for application-specific Enter-key handlers.
	"""
	if is_button(obj):
		try:
			states = getattr(obj, "states", set()) or set()
			eligible = not any(
				getattr(controlTypes.State, name, None) in states
				for name in ("UNAVAILABLE", "INVISIBLE", "OFFSCREEN")
			)
		except Exception:
			eligible = False
		hwnd = _window_handle(obj)
		# Only a native button's own HWND can supply its enabled/visible state;
		# Office/UIA children may share their containing window's handle.
		if eligible and hwnd and win32.is_push_button_window(hwnd):
			eligible = win32.is_usable(hwnd)
		if eligible:
			return DefaultButtonQuery(DefaultButton(get_object_name(obj), obj=obj, source=SOURCE_FOCUS))
	answer, guess, settled = _lookup(obj, use_negative_cache=False)
	if answer is not None:
		return DefaultButtonQuery(answer)
	if guess is not None:
		return DefaultButtonQuery(guess)
	if settled:
		return DefaultButtonQuery()
	dialog = get_dialog_ancestor(obj)
	if dialog is None:
		return DefaultButtonQuery()
	result = appearance.pick_default_button(_dialog_buttons(dialog), focusIsButton=is_button(obj))
	if result.button is not None:
		return DefaultButtonQuery(
			DefaultButton(get_object_name(result.button), obj=result.button, source=SOURCE_APPEARANCE, certain=False)
		)
	return DefaultButtonQuery(screenCurtainBlocked=result.screenCurtainBlocked)


def get_default_button_name(obj, *, use_negative_cache=True) -> str:
	info = find_default_button_info(obj, use_negative_cache=use_negative_cache)
	return info.name if info is not None else ""


def _is_that_button(obj, info) -> bool:
	if info.hwnd:
		hwnd = _window_handle(obj)
		if hwnd:
			return hwnd == info.hwnd
	if info.obj is not None:
		return is_same_object(info.obj, obj)
	name = get_object_name(obj)
	return bool(name and info.name and name.lower() == info.name.lower())


def focused_button_default_status(obj):
	"""Return (isButton, isDefault, defaultName) for the focused object.

	Only a certain answer counts. A button that is the default only while it
	has focus never sounds default, or every focused button would.

	The dialog scan only runs when focus is actually on a button in a dialog.
	Focus speech for list items, edit fields and other controls never pays
	for it.
	"""
	if not is_button(obj):
		return False, False, ""
	if not _in_dialog(obj):
		return True, False, ""
	answer, _guess, _settled = _lookup(obj)
	if answer is None:
		return True, False, ""
	return True, _is_that_button(obj, answer), answer.name
