# _speech_core/token_policy.py
from typing import List, Optional, Tuple

from .tokens import (
    SpeechToken,
    TOKEN_HOTKEY,
    TOKEN_NAME,
    TOKEN_POSITION,
    TOKEN_DESCRIPTION,
    TOKEN_TOOLTIP,
    TOKEN_ROLE,
    TOKEN_STATE,
    TOKEN_VALUE,
)


_SUBSTANTIVE_KINDS = {
    TOKEN_NAME,
    TOKEN_ROLE,
    TOKEN_VALUE,
    TOKEN_STATE,
    TOKEN_POSITION,
    TOKEN_DESCRIPTION,
    TOKEN_TOOLTIP,
}


def has_substantive_content(tokens: List[SpeechToken]) -> bool:
    """Return True if the sequence contains meaningful non-hotkey content."""
    return any(token.kind in _SUBSTANTIVE_KINDS for token in tokens)


def split_hotkeys(tokens: List[SpeechToken]) -> Tuple[List[SpeechToken], List[SpeechToken]]:
    """
    Split a token list into:
    - non-hotkey tokens
    - hotkey tokens

    Policy owns keep/defer behavior, so the processor/formatter can stay simple.
    """
    non_hotkeys: List[SpeechToken] = []
    hotkeys: List[SpeechToken] = []

    for token in tokens:
        if token.kind == TOKEN_HOTKEY:
            hotkeys.append(token)
        else:
            non_hotkeys.append(token)

    return non_hotkeys, hotkeys


def clone_hotkey_token(token: SpeechToken, *, deferred: bool = False) -> SpeechToken:
    """
    Re-emit a hotkey token while preserving its text and metadata.

    We keep hotkeys as tokens instead of collapsing them to raw strings so later
    formatter/policy decisions remain token-based.
    """
    meta = dict(getattr(token, "meta", {}) or {})
    if deferred:
        meta["deferred"] = True

    text = token.text() if hasattr(token, "text") and callable(token.text) else str(
        getattr(token, "spoken", "") or getattr(token, "raw", "") or ""
    ).strip()

    if hasattr(token, "clone") and callable(token.clone):
        return token.clone(
            kind=TOKEN_HOTKEY,
            raw=text,
            spoken=text,
            meta=meta,
        )

    return SpeechToken(
        kind=TOKEN_HOTKEY,
        raw=text,
        spoken=text,
        source=list(getattr(token, "source", []) or []),
        meta=meta,
    )


def pick_inline_hotkeys(hotkeys: List[SpeechToken]) -> List[SpeechToken]:
    """
    Return inline hotkey tokens to use from the current sequence.

    Keep multiple shortcuts as separate TOKEN_HOTKEY entries so the normal
    pause system can separate access keys from command shortcuts.
    """
    return [hotkey for hotkey in hotkeys if _token_text(hotkey)]


def _coerce_pending_hotkeys(pending_hotkey) -> List[SpeechToken]:
    if not pending_hotkey:
        return []
    if isinstance(pending_hotkey, list):
        return [hotkey for hotkey in pending_hotkey if _token_text(hotkey)]
    return [pending_hotkey] if _token_text(pending_hotkey) else []

def _token_text(token: SpeechToken) -> str:
    if hasattr(token, "text") and callable(token.text):
        return token.text().strip()
    return str(getattr(token, "spoken", "") or getattr(token, "raw", "") or "").strip()


def _is_selected_state_token(token: SpeechToken) -> bool:
    if getattr(token, "kind", None) != TOKEN_STATE:
        return False

    raw = str(getattr(token, "raw", "") or "").strip().lower()
    spoken = _token_text(token).lower()
    return raw == "selected" or spoken in {"selected", "not selected"}


def _is_blank_value_token(token: SpeechToken) -> bool:
    return getattr(token, "kind", None) == TOKEN_VALUE and _token_text(token).lower() in {"blank", "empty"}



def _strip_selected_value_prefix(text: str) -> str:
    value = str(text or "").strip()
    lower = value.lower()
    for prefix in ("selected ", "selected"):
        if lower.startswith(prefix):
            return value[len(prefix):].strip()
    return value


def _is_selected_prefixed_value_token(token: SpeechToken) -> bool:
    if getattr(token, "kind", None) != TOKEN_VALUE:
        return False
    return _token_text(token).lower().startswith("selected")


def _role_keys_in_sequence(tokens: List[SpeechToken]) -> set:
    roles = set()
    for current_token in tokens:
        if getattr(current_token, "kind", None) != TOKEN_ROLE:
            continue
        for value in (getattr(current_token, "raw", None), getattr(current_token, "spoken", None)):
            if value is None:
                continue
            text = str(value).strip().lower().replace(" ", "")
            if text:
                roles.add(text)
    return roles


def _sequence_is_editable_surface(tokens: List[SpeechToken]) -> bool:
    roles = _role_keys_in_sequence(tokens)
    return bool(roles & {"edit", "editabletext", "document", "editcombo"})


def apply_value_suppression_rules(
    tokens: List[SpeechToken],
    *,
    focus_role_key: Optional[str] = None,
    context: str = "dialog",
    suppress_editable_text_value: bool = True,
    selected_text: Optional[str] = None,
) -> List[SpeechToken]:
    """
    Targeted value handling for text-entry/document surfaces.

    Rules for editable text / document focus speech:
    - if text is highlighted, speak that text as the value
    - if no text is highlighted, suppress value chatter such as "blank"
    - always remove the focus-time "selected" state token for these controls

    Description and tooltip tokens are not part of this rule and continue
    through the normal verbosity / NVDA presentation paths. Literal review and
    standard selection commands bypass semantic processing before this policy.
    """
    if focus_role_key not in {"editabletext", "editcombo", "document"}:
        return tokens

    if context == "menu":
        return tokens

    if not suppress_editable_text_value:
        return tokens

    clean_selected_text = str(selected_text or "").strip()
    has_selected_state = any(_is_selected_state_token(token) for token in tokens)
    sequence_is_editable = _sequence_is_editable_surface(tokens)

    # api.getFocusObject() can already be the edit field while NVDA is still
    # emitting surrounding dialog/label speech, e.g. Save As -> File name combo
    # -> edit selected filename.  Only inject selected text into sequences that
    # actually represent the editable surface, otherwise the edit value bleeds
    # into the dialog and label announcements.
    if clean_selected_text and not sequence_is_editable and not has_selected_state:
        clean_selected_text = ""

    has_selected_value = any(_is_selected_prefixed_value_token(token) for token in tokens)
    allow_value = (
        (bool(clean_selected_text) and sequence_is_editable)
        or has_selected_state
        or (sequence_is_editable and has_selected_value)
    )

    filtered: List[SpeechToken] = []
    inserted_selected_value = False

    for current_token in tokens:
        if _is_selected_state_token(current_token):
            continue

        if getattr(current_token, "kind", None) == TOKEN_VALUE:
            if not allow_value:
                continue

            if clean_selected_text:
                if inserted_selected_value:
                    continue
                filtered.append(
                    current_token.clone(
                        raw=clean_selected_text,
                        spoken=clean_selected_text,
                        source=[clean_selected_text],
                        meta={**(getattr(current_token, "meta", {}) or {}), "selectedTextValue": True},
                    )
                )
                inserted_selected_value = True
                continue

            if _is_blank_value_token(current_token):
                continue

            if not clean_selected_text and _is_selected_prefixed_value_token(current_token):
                selected_value = _strip_selected_value_prefix(_token_text(current_token))
                if not selected_value:
                    continue
                filtered.append(
                    current_token.clone(
                        raw=selected_value,
                        spoken=selected_value,
                        source=[selected_value],
                        meta={**(getattr(current_token, "meta", {}) or {}), "selectedTextValue": True},
                    )
                )
                continue

        filtered.append(current_token)

    if clean_selected_text and not inserted_selected_value:
        filtered.append(
            SpeechToken(
                kind=TOKEN_VALUE,
                raw=clean_selected_text,
                spoken=clean_selected_text,
                source=[clean_selected_text],
                meta={"selectedTextValue": True},
            )
        )

    return filtered


def resolve_pending_hotkey(
    tokens: List[SpeechToken],
    pending_hotkey: Optional[SpeechToken] = None,
) -> Tuple[List[SpeechToken], Optional[SpeechToken]]:
    """
    Hotkey policy:

    - If a sequence contains substantive content and an inline hotkey, keep the
      hotkey in this sequence.
    - If a sequence contains only a hotkey, defer it.
    - If a sequence contains substantive content and there is a deferred hotkey,
      append that deferred hotkey.
    - If both an inline hotkey and a deferred hotkey exist, the inline hotkey
      wins and the deferred one is cleared.

    This file owns hotkey keep/defer behavior only.
    Placement and final speech ordering remain formatter concerns.
    """
    resolved_tokens, inline_hotkeys = split_hotkeys(tokens)
    substantive = has_substantive_content(resolved_tokens)
    current_hotkeys = pick_inline_hotkeys(inline_hotkeys)
    pending_hotkeys = _coerce_pending_hotkeys(pending_hotkey)

    if substantive and current_hotkeys:
        for hotkey in current_hotkeys:
            resolved_tokens.append(clone_hotkey_token(hotkey))
        return resolved_tokens, None

    if current_hotkeys and not substantive:
        return resolved_tokens, [clone_hotkey_token(hotkey, deferred=True) for hotkey in current_hotkeys]

    if substantive and pending_hotkeys:
        for hotkey in pending_hotkeys:
            resolved_tokens.append(clone_hotkey_token(hotkey, deferred=True))
        return resolved_tokens, None

    return resolved_tokens, pending_hotkey


def apply_token_policy(
    tokens: List[SpeechToken],
    *,
    context: str = "dialog",
    focus_role_key: Optional[str] = None,
    pending_hotkey: Optional[SpeechToken] = None,
    suppress_editable_text_value: bool = True,
    selected_text: Optional[str] = None,
) -> Tuple[List[SpeechToken], Optional[SpeechToken]]:
    """
    Central semantic-token policy pass.

    Current responsibilities:
    1. targeted value suppression
    2. deferred hotkey resolution

    Processor stays orchestration-only.
    Formatter stays rendering-only.
    """
    tokens = apply_value_suppression_rules(
        tokens,
        focus_role_key=focus_role_key,
        context=context,
        suppress_editable_text_value=suppress_editable_text_value,
        selected_text=selected_text,
    )

    tokens, pending_hotkey = resolve_pending_hotkey(
        tokens,
        pending_hotkey,
    )

    return tokens, pending_hotkey
