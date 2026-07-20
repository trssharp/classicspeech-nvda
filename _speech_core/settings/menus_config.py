"""Menus panel settings helpers."""

from .config_core import _ensure_classic_speech_section


def _get_menu_open_enabled():
	conf = _ensure_classic_speech_section()
	return bool(conf.get("announceMenuOpen", True))


def _set_menu_open_enabled(enabled: bool):
	conf = _ensure_classic_speech_section()
	conf["announceMenuOpen"] = bool(enabled)


def _get_menu_close_enabled():
	conf = _ensure_classic_speech_section()
	return bool(conf.get("announceMenuClose", True))


def _set_menu_close_enabled(enabled: bool):
	conf = _ensure_classic_speech_section()
	conf["announceMenuClose"] = bool(enabled)


def _get_menu_open_message():
	conf = _ensure_classic_speech_section()
	return str(conf.get("menuOpenMessage", "Entering menu"))


def _set_menu_open_message(message: str):
	conf = _ensure_classic_speech_section()
	conf["menuOpenMessage"] = str(message or "Entering menu")



def _get_menu_close_message():
	conf = _ensure_classic_speech_section()
	return str(conf.get("menuCloseMessage", "Leaving menu"))


def _set_menu_close_message(message: str):
	conf = _ensure_classic_speech_section()
	conf["menuCloseMessage"] = str(message or "Leaving menu")


def _get_menu_bar_focus_enabled():
	conf = _ensure_classic_speech_section()
	return bool(conf.get("announceMenuBarFocus", True))


def _set_menu_bar_focus_enabled(enabled: bool):
	conf = _ensure_classic_speech_section()
	conf["announceMenuBarFocus"] = bool(enabled)


def _get_menu_bar_leave_enabled():
	conf = _ensure_classic_speech_section()
	return bool(conf.get("announceMenuBarLeave", False))


def _set_menu_bar_leave_enabled(enabled: bool):
	conf = _ensure_classic_speech_section()
	conf["announceMenuBarLeave"] = bool(enabled)


def _get_menu_bar_focus_message():
	conf = _ensure_classic_speech_section()
	return str(conf.get("menuBarFocusMessage", "Menu bar"))


def _set_menu_bar_focus_message(message: str):
	conf = _ensure_classic_speech_section()
	conf["menuBarFocusMessage"] = str(message or "Menu bar")


def _get_menu_bar_leave_message():
	conf = _ensure_classic_speech_section()
	return str(conf.get("menuBarLeaveMessage", "Leaving menu bar"))


def _set_menu_bar_leave_message(message: str):
	conf = _ensure_classic_speech_section()
	conf["menuBarLeaveMessage"] = str(message or "Leaving menu bar")


