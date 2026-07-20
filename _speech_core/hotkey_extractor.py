# _speech_core/hotkey_extractor.py
from speech.commands import CharacterModeCommand
import logHandler

log = logHandler.log


_VALID_SINGLE_KEYS = {
    "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
    "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "`", "-", "=", "[", "]", "\\", ";", "'", ".", ",", "/", "space",
    "tab", "enter", "escape", "esc", "backspace", "delete", "del",
    "insert", "ins", "home", "end", "pageup", "pagedown",
    "leftarrow", "rightarrow", "uparrow", "downarrow",
    "left", "right", "up", "down",
    "comma", "period", "dot", "slash", "backslash", "minus", "dash", "hyphen",
    "plus", "equals", "equal", "semicolon", "quote", "apostrophe",
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
}

_MENU_ROLE_MARKERS = {
    "submenu",
    "sub menu",
    "menuitem",
    "menu item",
    "checkmenuitem",
    "check menu item",
    "radiomenuitem",
    "radio menu item",
}


def _normalize_key_token(tok):
    return str(tok).strip().lower().replace(" ", "")


def _normalize_text(tok):
    return str(tok).strip().lower()


def _looks_like_hotkey_prefix(tok):
    if not isinstance(tok, str):
        return False

    lower = tok.lower().strip()

    # Standard NVDA shortcut prefixes, e.g. "Ctrl+", "Ctrl+Shift+", "Alt+".
    if "+" in lower and any(
        mod in lower for mod in ("ctrl+", "alt+", "shift+", "win+", "windows+", "nvda+")
    ):
        return True

    # Some UIA menu bars expose accelerators as fragmented text:
    #   "Alt, " + CharacterModeCommand(True) + "F" + CharacterModeCommand(False)
    # Treat the comma form as a hotkey prefix only when a valid key follows.
    return lower in {"ctrl,", "alt,", "shift,", "win,", "windows,", "nvda,"}


def _normalize_hotkey_prefix(tok):
    text = str(tok).strip()

    # Convert UIA/NVDA comma-style prefixes such as "Alt," to "Alt+".
    text = text.replace(",", "+")
    text = text.replace(" +", "+").replace("+ ", "+")

    while "++" in text:
        text = text.replace("++", "+")

    if not text.endswith("+"):
        text += "+"

    return text


def _looks_like_key_name(tok):
    if not isinstance(tok, str):
        return False

    normalized = _normalize_key_token(tok)

    if normalized in _VALID_SINGLE_KEYS:
        return True

    if len(tok.strip()) == 1:
        return True

    return False


def _looks_like_single_visible_accelerator(tok):
    """
    Very conservative fallback for menu accelerators.
    This is intentionally single-character only so labels like
    'Insert' are never mistaken for an accelerator.
    """
    if not isinstance(tok, str):
        return False
    stripped = tok.strip()
    return len(stripped) == 1 and stripped.lower() in _VALID_SINGLE_KEYS


def _looks_like_menu_role_marker(tok):
    if not isinstance(tok, str):
        return False
    return _normalize_text(tok) in _MENU_ROLE_MARKERS


def _is_menu_context(context):
    return isinstance(context, str) and context.strip().lower() == "menu"


def _consume_character_mode_key(tokens, start_index):
    """
    Consume a key expressed in NVDA character mode, e.g.:
        CharacterModeCommand(True), 'p', CharacterModeCommand(False)

    Also tolerates a plain visible key token without command wrappers.
    Returns (key, new_index) or (None, start_index)
    """
    if start_index >= len(tokens):
        return None, start_index

    j = start_index

    if isinstance(tokens[j], CharacterModeCommand):
        j += 1

    if j >= len(tokens):
        return None, start_index

    key_tok = tokens[j]
    if not (isinstance(key_tok, str) and _looks_like_key_name(key_tok)):
        return None, start_index

    key = key_tok.strip()
    j += 1

    if j < len(tokens) and isinstance(tokens[j], CharacterModeCommand):
        j += 1

    return key, j


def _sequence_contains_prefixed_hotkey(tokens, start_index):
    """
    Used to stop fallback menu-accelerator logic from stealing the menu item
    name when a real explicit hotkey such as Alt+I already exists later in
    the same sequence.
    """
    j = start_index
    while j < len(tokens):
        if _looks_like_hotkey_prefix(tokens[j]):
            key, new_index = _consume_character_mode_key(tokens, j + 1)
            if key:
                return True
            j = new_index if new_index > j else j + 1
            continue
        j += 1
    return False


def _extract_prefixed_hotkey(tokens, start_index):
    """
    Handles patterns like:
        'Alt+' + CharacterModeCommand + 'F'
        'Ctrl+Shift+' + 'T'
        'NVDA+' + 'R'
    """
    tok = tokens[start_index]
    if not _looks_like_hotkey_prefix(tok):
        return None, start_index

    # A complete shortcut may arrive as one token, e.g. "Ctrl+N" or "Alt, N".
    # Older logic only handled a prefix token followed by a character-mode key.
    full_from_token = _normalize_full_hotkey_text(tok)
    if full_from_token:
        log.debug(f"Extracted hotkey: {full_from_token}")
        return full_from_token, start_index + 1

    prefix = _normalize_hotkey_prefix(tok)
    key, new_index = _consume_character_mode_key(tokens, start_index + 1)
    if not key:
        return None, start_index

    full_hotkey = f"{prefix}{key}".replace(" +", "+").replace("+ ", "+").strip()
    while "++" in full_hotkey:
        full_hotkey = full_hotkey.replace("++", "+")
    log.debug(f"Extracted hotkey: {full_hotkey}")
    return full_hotkey, new_index


def _extract_menu_accelerator(tokens, start_index, context=None):
    """
    Handles menu accelerator patterns like:
        'subMenu', CharacterModeCommand(True), 'p', CharacterModeCommand(False)
        or in known menu context:
        CharacterModeCommand(True), 'p', CharacterModeCommand(False)

    Important:
    - the role marker itself is NOT consumed
    - only the accelerator fragment is consumed
    - plain text labels like 'Insert' are never consumed as accelerators
    - if a real prefixed hotkey (e.g. Alt+i) exists later in the sequence,
      fallback menu accelerator extraction is skipped
    """
    if start_index >= len(tokens):
        return None, start_index

    prev_is_menu_marker = (
        start_index > 0 and _looks_like_menu_role_marker(tokens[start_index - 1])
    )
    menu_context = _is_menu_context(context)

    if not prev_is_menu_marker and not menu_context:
        return None, start_index

    # If there is an explicit hotkey later, do not let fallback menu
    # accelerator logic consume anything at the front of the sequence.
    if _sequence_contains_prefixed_hotkey(tokens, start_index):
        # Still allow extraction when the current token really is the
        # character-mode key itself, e.g. after 'subMenu'.
        if not isinstance(tokens[start_index], CharacterModeCommand):
            if not _looks_like_single_visible_accelerator(tokens[start_index]):
                return None, start_index

    # Strong path: current position is a character-mode key sequence.
    if isinstance(tokens[start_index], CharacterModeCommand):
        key, new_index = _consume_character_mode_key(tokens, start_index)
        if key:
            accelerator = key.strip()
            log.debug(f"Extracted menu accelerator: {accelerator}")
            return accelerator, new_index
        return None, start_index

    # Conservative fallback:
    # only allow a single visible character token in menu context.
    tok = tokens[start_index]
    if _looks_like_single_visible_accelerator(tok):
        accelerator = tok.strip()
        log.debug(f"Extracted menu accelerator: {accelerator}")
        return accelerator, start_index + 1

    return None, start_index



def _normalize_full_hotkey_text(text):
    """Normalize a complete shortcut string without requiring a following key token.

    This must only accept strings that are pure shortcuts, such as
    ``Ctrl+Shift+N``.  A menu item label such as ``New Window Ctrl+Shift+N``
    is not a pure shortcut; older logic accepted it because it only required
    *one* modifier-looking segment. That caused three-part accelerators in
    menus to be consumed as hotkey-only speech with no name.
    """
    if not isinstance(text, str):
        return None
    text = text.strip()
    if not text:
        return None

    # NVDA can expose access keys as "Alt, N" and accelerator keys as "Ctrl+N".
    normalized = text.replace(" +", "+").replace("+ ", "+")
    normalized = normalized.replace(", ", "+").replace(",", "+")
    while "++" in normalized:
        normalized = normalized.replace("++", "+")

    parts = [part.strip() for part in normalized.split("+") if part.strip()]
    if len(parts) < 2:
        return None

    modifiers = parts[:-1]
    key = parts[-1]
    if not _looks_like_key_name(key):
        return None

    valid_modifiers = {"ctrl", "control", "alt", "shift", "win", "windows", "nvda"}
    # Every pre-key segment must be a real modifier. This prevents compact
    # menu labels like "New Window Ctrl+Shift+N" from being misclassified as
    # a pure shortcut just because the middle segment is "Shift".
    if not modifiers or not all(mod.lower() in valid_modifiers for mod in modifiers):
        return None

    return "+".join(modifiers + [key])


def parse_trailing_label_shortcut(text):
    """Parse menu labels with a trailing accelerator in the same string.

    Common Chromium/Electron/Firefox menu patterns include:
        "New Window Ctrl+Shift+N"
        "Quick Chat Alt+Ctrl+N"
        "Clear Recent History... Ctrl+Shift+Del"
        "Settings... Ctrl+Comma"

    Returns (label, shortcut) or (None, None). The parser is intentionally
    right-biased: it only treats the final whitespace-delimited chunk as a
    shortcut, so ordinary labels containing words like "Control" are safe.
    """
    if not isinstance(text, str):
        return None, None

    raw = text.strip()
    if not raw or " " not in raw or "+" not in raw:
        return None, None

    label, shortcut = raw.rsplit(None, 1)
    label = label.strip()
    shortcut = shortcut.strip()
    if not label or not shortcut:
        return None, None

    normalized = _normalize_full_hotkey_text(shortcut)
    if not normalized:
        return None, None

    return label, normalized


def parse_shortcut_list(text):
    """
    Parse an NVDA keyboardShortcut string that may contain multiple shortcuts.

    NVDA joins UIA accessKey and acceleratorKey values with two spaces, e.g.:
        "Alt, N  Ctrl+N"
    Return a list of normalized shortcut strings, or [] when the text is not
    purely a shortcut list.
    """
    if not isinstance(text, str):
        return []
    raw = text.strip()
    if not raw:
        return []

    # Keep NVDA's two-space separator semantics. Also tolerate wider spacing.
    chunks = [chunk.strip() for chunk in raw.replace("\u00a0", " ").split("  ") if chunk.strip()]
    if len(chunks) < 2:
        full = _normalize_full_hotkey_text(raw)
        return [full] if full else []

    parsed = []
    for chunk in chunks:
        full = _normalize_full_hotkey_text(chunk)
        if not full:
            return []
        parsed.append(full)
    return parsed


def parse_compact_label_shortcut(text):
    """
    Parse compact menu/control labels shaped like:
        "Settings	Ctrl+S"
        "Refresh	F5"

    Returns (label, shortcut) or (None, None).
    """
    if not isinstance(text, str) or "	" not in text:
        return None, None

    label, shortcut = text.split("	", 1)
    label = label.strip()
    shortcut = shortcut.strip()
    if not label or not shortcut:
        return None, None

    normalized = _normalize_key_token(shortcut)
    if _looks_like_hotkey_prefix(shortcut):
        return label, shortcut

    if normalized in _VALID_SINGLE_KEYS and len(normalized) > 1:
        return label, shortcut

    if normalized.startswith("f") and normalized[1:].isdigit():
        return label, shortcut

    return None, None


def consume_character_mode_echo(tokens, start_index):
    """
    Consume a trailing character-mode mnemonic/accelerator echo if present.
    Returns the next index to continue scanning from.
    """
    key, new_index = _consume_character_mode_key(tokens, start_index)
    return new_index if key else start_index


def extract_hotkey(tokens, start_index, context=None):
    """
    Returns (hotkey_string, new_index) or (None, start_index)

    Supports two families:

    1. Full shortcuts:
        'Alt+' + CharacterModeCommand + 'F'
        'Ctrl+Shift+' + 'T'
        'NVDA+' + 'R'

    2. Menu accelerators:
        'subMenu' + CharacterModeCommand + 'p'
        'menu item' + CharacterModeCommand + 't'

    For menu accelerators, the role token is preserved in the stream.

    The optional `context` argument may be:
        None
        'menu'
        'dialog'
    """
    if start_index >= len(tokens):
        return None, start_index

    hotkey, new_index = _extract_prefixed_hotkey(tokens, start_index)
    if hotkey:
        return hotkey, new_index

    hotkey, new_index = _extract_menu_accelerator(tokens, start_index, context=context)
    if hotkey:
        return hotkey, new_index

    return None, start_index