import api
import browseMode
import config
import logHandler

log = logHandler.log

CONTEXT_NONE = "none"
CONTEXT_MENUBAR = "menubar"
CONTEXT_MENU = "menu"

MENU_ITEM_ROLE_KEYS = {
    "menuitem",
    "checkmenuitem",
    "radiomenuitem",
}

MENU_CONTEXT_ROLE_KEYS = {
    "menu",
    "menubar",
    "menuitem",
    "checkmenuitem",
    "radiomenuitem",
}

ROLE_ALIASES = {
    "menu bar": "menubar",
    "menu item": "menuitem",
    "popup menu": "menu",
    "popupmenu": "menu",
    "check menu item": "checkmenuitem",
    "radio menu item": "radiomenuitem",
}

# Root popup menus with these names already identify themselves clearly.
# Adding the generic open hint produces awkward output such as
# "menu active. NVDA" or "menu active. Context". Keep this as a small
# table so future root-menu exceptions can be added in one place.
ROOT_MENU_HINT_BYPASS_NAMES = {
    "context",
    "nvda",
}


def _normalize_role_key(value):
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        value = " ".join(str(v) for v in value if v is not None)
    key = str(value).strip().lower()
    if not key:
        return None
    key = key.replace("_", " ").replace("-", " ")
    key = " ".join(key.split())
    key = ROLE_ALIASES.get(key, key)
    return key.replace(" ", "")


def _safe_obj_attr(obj, attr, default=None):
    try:
        return getattr(obj, attr, default)
    except Exception:
        return default


def _get_object_role_key(obj):
    if not obj:
        return None
    role = _safe_obj_attr(obj, "role", None)
    if role is None:
        return None
    role_name = getattr(role, "name", None)
    if role_name:
        return _normalize_role_key(role_name)
    return _normalize_role_key(role)


def _is_unknown_focus(obj):
    role_key = _get_object_role_key(obj)
    return role_key in {"unknown", "", None}


def _focus_signature(obj):
    if obj is None:
        return None
    return (
        id(obj),
        _safe_obj_attr(obj, "windowHandle", None),
        _safe_obj_attr(obj, "processID", None),
        _get_object_role_key(obj),
        _safe_obj_attr(obj, "name", None),
    )


def _normalize_name_key(value):
    key = str(value or "").strip().lower()
    if not key:
        return ""
    return " ".join(key.replace("_", " ").replace("-", " ").split())


def should_bypass_root_menu_hint(obj):
    """Return True for named root popup menus that should not get the
    generic menu-open prefix. This is intentionally narrow: it only applies
    to actual root popup menu objects, not menu items or menubars.
    """
    if _get_object_role_key(obj) != "menu":
        return False
    return _normalize_name_key(_safe_obj_attr(obj, "name", "")) in ROOT_MENU_HINT_BYPASS_NAMES


def _string_items(sequence):
    return [item.strip() for item in sequence if isinstance(item, str) and item.strip()]


def is_structural_menubar_sequence(sequence):
    """
    Some apps expose menubars as a tiny structural utterance such as
    "Menu Bar, tool bar".  That is not user-facing content; we normalize it
    to the explicit menubar hint and suppress the raw container wording.
    """
    strings = [s.lower() for s in _string_items(sequence)]
    if not strings:
        return False

    has_menu_bar = any(s in {"menu bar", "menubar"} for s in strings)
    has_toolbar = any(s in {"tool bar", "toolbar"} for s in strings)
    if has_menu_bar and has_toolbar:
        return True

    # Do NOT treat a bare literal "menu bar" string as structural here.
    # Text review / browse review can legitimately emit exactly that text.
    # Suppressing bare strings here causes review commands to go silent.
    return False



def is_top_level_menubar_item_sequence(sequence):
    """Detect transient top-level menubar item speech such as
    "File, sub menu, Alt+F, 1 of 8".
    """
    strings = [s.strip().lower() for s in _string_items(sequence)]
    if not strings:
        return False
    has_submenu = any(s in {"submenu", "sub menu"} for s in strings)
    has_alt_prefix = any(s == "alt+" or s.startswith("alt+") for s in strings)
    has_position = any(" of " in s for s in strings)
    has_structural_container = any(s in {"menu bar", "menubar", "tool bar", "toolbar"} for s in strings)
    return has_submenu and has_alt_prefix and has_position and not has_structural_container

def _object_menu_context(obj):
    """
    Return a coarse menu state for the focus ancestry.

    MENU wins over MENUBAR.  A menuitem directly in a menubar is treated as
    MENUBAR until a popup/root menu ancestor appears.  This keeps Alt-alone as
    "menu bar" and reserves "menu active" for an actual opened menu.
    """
    current = obj
    depth = 0
    saw_menubar = False
    saw_menuitem = False

    while current is not None and depth < 10:
        role_key = _get_object_role_key(current)
        if role_key == "menu":
            return CONTEXT_MENU
        if role_key == "menubar":
            saw_menubar = True
        elif role_key in MENU_ITEM_ROLE_KEYS:
            saw_menuitem = True
        current = _safe_obj_attr(current, "parent", None)
        depth += 1

    if saw_menubar or saw_menuitem:
        return CONTEXT_MENUBAR
    return CONTEXT_NONE


def _is_browse_mode_active(obj):
    ti = _safe_obj_attr(obj, "treeInterceptor", None)
    return bool(ti and isinstance(ti, browseMode.BrowseModeDocumentTreeInterceptor) and not _safe_obj_attr(ti, "passThrough", False))


def _is_native_menu_context(obj, max_depth=10):
    """Native-only menu check for the browse guard.

    Web/ARIA menus in the virtual buffer often expose menu roles, but they
    are still owned by a BrowseModeDocumentTreeInterceptor.  Those should not
    update native menu state or receive native menu hints.
    """
    current = obj
    depth = 0
    while current is not None and depth < max_depth:
        role_key = _get_object_role_key(current)
        if role_key in MENU_CONTEXT_ROLE_KEYS:
            ti = _safe_obj_attr(current, "treeInterceptor", None)
            if ti and isinstance(ti, browseMode.BrowseModeDocumentTreeInterceptor):
                return False
            return True
        current = _safe_obj_attr(current, "parent", None)
        depth += 1
    return False


def _config_value(name, default=None):
    try:
        return config.conf["classicSpeech"].get(name, default)
    except Exception:
        return default


def _configured_message(name, default):
    msg = str(_config_value(name, default) or default).strip()
    return msg


def _menu_close_message_for_context(context):
    if context == CONTEXT_MENUBAR:
        if not bool(_config_value("announceMenuBarLeave", False)):
            return ""
        return _configured_message("menuBarLeaveMessage", "Leaving menu bar")
    if context == CONTEXT_MENU:
        if not bool(_config_value("announceMenuClose", True)):
            return ""
        return _configured_message("menuCloseMessage", "Leaving menu")
    return ""


class MenuHintHelper:
    def __init__(self):
        self._last_focus_signature = None
        self._last_context = CONTEXT_NONE
        self._pending_prefix = []

    def reset(self):
        self._last_focus_signature = None
        self._last_context = CONTEXT_NONE
        self._pending_prefix = []

    def has_active_menu_context(self):
        return self._last_context in {CONTEXT_MENU, CONTEXT_MENUBAR}

    def force_exit(self, speak=True):
        previous = self._last_context
        self._last_focus_signature = None
        self._last_context = CONTEXT_NONE
        self._pending_prefix = []
        if not speak or previous not in {CONTEXT_MENU, CONTEXT_MENUBAR}:
            return []
        msg = _menu_close_message_for_context(previous)
        return [msg] if msg else []

    def get_prefix_sequence(self, speechSequence=None):
        try:
            focus = api.getFocusObject()
        except Exception:
            return []
        if not focus:
            return []

        signature = _focus_signature(focus)
        context = _object_menu_context(focus)

        # Some frameworks briefly return focus to an UNKNOWN object when a menu
        # closes.  If we keep walking ancestors, stale menu ancestry can delay
        # the close hint until the next meaningful focus move.  Treat UNKNOWN
        # after menu activity as an immediate exit and let the normal close
        # message speak now.
        unknown_focus_after_menu = (
            self._last_context in {CONTEXT_MENU, CONTEXT_MENUBAR}
            and _is_unknown_focus(focus)
        )
        if unknown_focus_after_menu:
            context = CONTEXT_NONE

        # In browse mode, ARIA/web menus can expose menu/menuitem/menubar roles
        # while focus remains inside the virtual buffer.  Do not let those roles
        # update native menu state or receive native menu hints.  Still allow the
        # normal native-menu close message when focus returns from a real menu to
        # browse content.
        browse_active = _is_browse_mode_active(focus)
        native_menu = _is_native_menu_context(focus)
        if browse_active and not native_menu:
            if context != CONTEXT_NONE:
                return []
            if self._last_context not in {CONTEXT_MENU, CONTEXT_MENUBAR}:
                return []

        raw_structural_menubar = speechSequence is not None and is_structural_menubar_sequence(speechSequence)

        # Prefer the speech sequence for anonymous structural menubar objects
        # such as Firefox/Notepad exposing "Menu Bar, tool bar", but only when
        # the actual focus ancestry is already menu-related. Some browse-mode
        # apps can emit structural menubar-ish speech while focus remains in an
        # editable/document object; treating that as a real menu transition
        # pollutes state and causes later speech to get chopped.
        structural_menubar = raw_structural_menubar and context != CONTEXT_NONE
        if raw_structural_menubar and context == CONTEXT_NONE:
            return []

        if structural_menubar:
            context = CONTEXT_MENUBAR

        previous = self._last_context
        prefix = []
        bypass_open_hint = context == CONTEXT_MENU and should_bypass_root_menu_hint(focus)

        if previous != context:
            if previous == CONTEXT_NONE and context == CONTEXT_MENUBAR:
                if bool(_config_value("announceMenuBarFocus", True)):
                    msg = _configured_message("menuBarFocusMessage", "Menu bar")
                    if msg:
                        prefix = [msg]
                log.debug(f"Menu hints: entering menubar for focus {signature!r}")
            elif previous in {CONTEXT_NONE, CONTEXT_MENUBAR} and context == CONTEXT_MENU:
                if bypass_open_hint:
                    prefix = []
                    log.debug(f"Menu hints: bypassing root menu open hint for focus {signature!r}")
                elif bool(_config_value("announceMenuOpen", True)):
                    msg = _configured_message("menuOpenMessage", "Entering menu")
                    if msg:
                        prefix = [msg]
                        log.debug(f"Menu hints: opening menu for focus {signature!r}")
            elif previous == CONTEXT_MENU and context == CONTEXT_MENUBAR:
                # Returning from a popup to the menubar is not a full menu exit.
                prefix = []
            elif previous in {CONTEXT_MENU, CONTEXT_MENUBAR} and context == CONTEXT_NONE:
                msg = _menu_close_message_for_context(previous)
                if msg:
                    prefix = [msg]
                    log.debug(f"Menu hints: closing menu for focus {signature!r}")

        self._last_focus_signature = signature
        self._last_context = context

        if structural_menubar:
            if prefix:
                self._pending_prefix = list(prefix)
            return []

        if self._pending_prefix:
            queued = list(self._pending_prefix)
            self._pending_prefix = []
            if prefix:
                queued.extend(prefix)
            return queued

        return prefix
