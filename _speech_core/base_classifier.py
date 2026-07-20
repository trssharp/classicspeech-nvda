# _speech_core/base_classifier.py
import re

import logHandler

from .hotkey_extractor import (
    consume_character_mode_echo,
    extract_hotkey,
    parse_compact_label_shortcut,
    parse_shortcut_list,
    parse_trailing_label_shortcut,
)
from .maps import (
    ALL_SPOKEN_ROLES_LOWER,
    ALL_SPOKEN_STATES_LOWER,
    ROLE_LABEL_ALIASES,
    SPOKEN_TO_ROLE,
    SPOKEN_TO_STATE,
)
from .tokens import (
    SpeechToken,
    TOKEN_HOTKEY,
    TOKEN_NAME,
    TOKEN_POSITION,
    TOKEN_ROLE,
    TOKEN_STATE,
    TOKEN_VALUE,
)

log = logHandler.log


def _normalize_lookup_text(text):
    if text is None:
        return ""
    return str(text).lower().strip().rstrip(".:")


def _find_spoken_key(mapping, normalized_text):
    """
    Resolve a normalized spoken label back to the original mapping key.

    We keep this helper so token.spoken can preserve the human-facing label
    while token.raw stores the canonical semantic value.
    """
    for spoken in mapping:
        if _normalize_lookup_text(spoken) == normalized_text:
            return spoken
    return None


def _looks_like_position(text):
    """
    Conservative position detector for standalone strings like:
        '1 of 5'
        '12 of 30'

    Do not classify combined list-item speech such as
    'Recycle Bin 1 of 17' as position. Some wx list controls expose the
    display text and position as a single string; treating that whole string
    as TOKEN_POSITION can cause the actual item text to disappear when
    position handling/filtering is applied.
    """
    if not isinstance(text, str):
        return False

    normalized = _normalize_lookup_text(text)
    if len(normalized) >= 30:
        return False
    return bool(re.fullmatch(r"\d+\s+of\s+\d+", normalized))


def _make_name_token(parts):
    if not parts:
        return None
    return SpeechToken(
        kind=TOKEN_NAME,
        raw=list(parts),
        spoken=" ".join(parts).strip(),
        source=list(parts),
    )


def _make_value_token(parts):
    if not parts:
        return None
    return SpeechToken(
        kind=TOKEN_VALUE,
        raw=list(parts),
        spoken=" ".join(parts).strip(),
        source=list(parts),
    )


def classify_tokens(tokens, context=None, protect_first_name=False):
    """
    Convert plain text fragments into structured semantic SpeechToken objects.

    Ownership split:
    - hotkey_extractor.py owns hotkey parsing
    - base_classifier.py owns semantic token creation
    - token_policy.py owns hotkey defer/append behavior
    - formatter.py owns final output order and rendering
    """
    semantic_tokens = []

    name_parts = []
    value_parts = []
    role_seen = False
    position_token = None

    protected_first_name_consumed = False

    i = 0
    while i < len(tokens):
        tok = tokens[i]

        if not isinstance(tok, str):
            i += 1
            continue

        normalized = _normalize_lookup_text(tok)
        if not normalized:
            i += 1
            continue

        # =====================
        # MULTI SHORTCUT STRING
        # =====================
        shortcut_list = parse_shortcut_list(tok)
        if shortcut_list:
            consumed_slice = [tok]
            for shortcut in shortcut_list:
                semantic_tokens.append(
                    SpeechToken(
                        kind=TOKEN_HOTKEY,
                        raw=shortcut,
                        spoken=shortcut,
                        source=consumed_slice,
                        meta={
                            "extracted": True,
                            "multiShortcutString": True,
                            "startIndex": i,
                            "endIndex": i + 1,
                        },
                    )
                )
            i += 1
            continue


        # =====================
        # TRAILING LABEL SHORTCUT
        # =====================
        trailing_label, trailing_hotkey = parse_trailing_label_shortcut(tok)
        if trailing_hotkey:
            if not role_seen:
                name_parts.append(trailing_label)
            else:
                value_parts.append(trailing_label)

            consumed = consume_character_mode_echo(tokens, i + 1)
            consumed_slice = list(tokens[i:consumed])
            semantic_tokens.append(
                SpeechToken(
                    kind=TOKEN_HOTKEY,
                    raw=trailing_hotkey,
                    spoken=trailing_hotkey,
                    source=consumed_slice,
                    meta={
                        "extracted": True,
                        "trailingLabelShortcut": True,
                        "startIndex": i,
                        "endIndex": consumed,
                    },
                )
            )
            i = consumed
            continue

        # =====================
        # COMPACT LABEL	SHORTCUT
        # =====================
        compact_label, compact_hotkey = parse_compact_label_shortcut(tok)
        if compact_hotkey:
            if not role_seen:
                name_parts.append(compact_label)
            else:
                value_parts.append(compact_label)

            consumed = consume_character_mode_echo(tokens, i + 1)
            consumed_slice = list(tokens[i:consumed])
            semantic_tokens.append(
                SpeechToken(
                    kind=TOKEN_HOTKEY,
                    raw=compact_hotkey,
                    spoken=compact_hotkey,
                    source=consumed_slice,
                    meta={
                        "extracted": True,
                        "compactLabelShortcut": True,
                        "startIndex": i,
                        "endIndex": consumed,
                    },
                )
            )
            i = consumed
            continue

        # =====================
        # HOTKEY
        # =====================
        hotkey, consumed = extract_hotkey(tokens, i, context=context)
        if hotkey:
            consumed_slice = list(tokens[i:consumed])
            semantic_tokens.append(
                SpeechToken(
                    kind=TOKEN_HOTKEY,
                    raw=hotkey,
                    spoken=hotkey,
                    source=consumed_slice,
                    meta={
                        "extracted": True,
                        "startIndex": i,
                        "endIndex": consumed,
                    },
                )
            )
            i = consumed
            continue

        # =====================
        # PROTECTED LEADING CONTROL NAME
        # =====================
        if protect_first_name and not protected_first_name_consumed and not role_seen:
            # In dialog/form controls, the accessible name can be plain English
            # that also exists in NVDA's role vocabulary (for example
            # "Style", "Font name", or "Font size"). Treat the first real
            # string as the control name so the following native role
            # ("check box", "combo box", etc.) can still be classified normally.
            protected_first_name_consumed = True
            name_parts.append(tok)
            i += 1
            continue

        # =====================
        # ROLE
        # =====================
        if not role_seen and normalized in ALL_SPOKEN_ROLES_LOWER:
            role_lookup = ROLE_LABEL_ALIASES.get(normalized, normalized)
            spoken_key = _find_spoken_key(SPOKEN_TO_ROLE, role_lookup)
            if spoken_key:
                role_seen = True
                semantic_tokens.append(
                    SpeechToken(
                        kind=TOKEN_ROLE,
                        raw=SPOKEN_TO_ROLE[spoken_key],
                        spoken=spoken_key,
                        source=[tok],
                    )
                )
                i += 1
                continue

        # =====================
        # STATE
        # =====================
        if normalized in ALL_SPOKEN_STATES_LOWER:
            spoken_key = _find_spoken_key(SPOKEN_TO_STATE, normalized)
            if spoken_key:
                semantic_tokens.append(
                    SpeechToken(
                        kind=TOKEN_STATE,
                        raw=SPOKEN_TO_STATE[spoken_key],
                        spoken=spoken_key,
                        source=[tok],
                    )
                )
                i += 1
                continue

        # =====================
        # POSITION
        # =====================
        if position_token is None and _looks_like_position(tok):
            position_token = SpeechToken(
                kind=TOKEN_POSITION,
                raw=tok,
                spoken=tok,
                source=[tok],
            )
            i += 1
            continue

        # =====================
        # NAME / VALUE
        # =====================
        if not role_seen:
            name_parts.append(tok)
        else:
            value_parts.append(tok)

        i += 1

    # Safety fallback for anything absurd that slipped through as a position token.
    if position_token and len(position_token.text()) > 60:
        name_parts.append(position_token.text())
        position_token = None

    name_token = _make_name_token(name_parts)
    if name_token:
        semantic_tokens.insert(0, name_token)

    value_token = _make_value_token(value_parts)
    if value_token:
        semantic_tokens.append(value_token)

    if position_token:
        semantic_tokens.append(position_token)

    return semantic_tokens