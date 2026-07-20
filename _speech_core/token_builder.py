# _speech_core/token_builder.py
from speech.commands import BreakCommand

from .tokens import (
    TOKEN_HOTKEY,
    TOKEN_NAME,
    TOKEN_POSITION,
    TOKEN_DESCRIPTION,
    TOKEN_TOOLTIP,
    TOKEN_ROLE,
    TOKEN_STATE,
    TOKEN_VALUE,
)

DEFAULT_ORDER = [
    TOKEN_NAME,
    TOKEN_ROLE,
    TOKEN_VALUE,
    TOKEN_STATE,
    TOKEN_POSITION,
    TOKEN_DESCRIPTION,
    TOKEN_TOOLTIP,
    TOKEN_HOTKEY,
]

RENAMEABLE_TOKEN_KINDS = {
    TOKEN_ROLE,
    TOKEN_STATE,
}


def _is_hotkey_like(text: str) -> bool:
    lowered = text.lower()
    return any(k in lowered for k in ("alt+", "ctrl+", "shift+", "win+"))


def _normalize_candidate(value):
    if value is None:
        return ""

    if isinstance(value, (list, tuple)):
        parts = [str(part).strip() for part in value if str(part).strip()]
        return " ".join(parts).strip()

    return str(value).strip()


def _find_token_rename(token, renames):
    """
    Only semantic token kinds should be renameable.
    Prefer raw semantic identity first, then spoken text.
    """
    if token.kind not in RENAMEABLE_TOKEN_KINDS:
        return None

    lower_map = {
        str(key).strip().lower(): str(value)
        for key, value in renames.items()
        if str(key).strip()
    }

    candidates = []

    raw_text = _normalize_candidate(getattr(token, "raw", None))
    if raw_text:
        candidates.append(raw_text)

    spoken_text = token.text().strip()
    if spoken_text:
        candidates.append(spoken_text)

    seen = set()
    for candidate in candidates:
        candidate_lower = candidate.lower()
        if candidate_lower in seen:
            continue
        seen.add(candidate_lower)

        if candidate in renames:
            return str(renames[candidate])

        if candidate_lower in lower_map:
            return lower_map[candidate_lower]

    return None


def build_speech_sequence(tokens, profile_config):
    """
    Render SpeechToken objects into an NVDA speech sequence.
    """
    enabled_tokens = profile_config.get("enabledTokens", {})
    order = profile_config.get("order", DEFAULT_ORDER)
    pauses = profile_config.get("pauses", {})
    pause_placement = str(profile_config.get("pausePlacement", "before"))
    if pause_placement not in {"after", "before"}:
        pause_placement = "after"
    pause_after_final = bool(profile_config.get("pauseAfterFinalToken", True))
    global_pause = int(profile_config.get("globalPause", 80))
    renames = profile_config.get("renames", {})

    grouped = {kind: [] for kind in order}
    extras = []

    for token in tokens:
        if token.kind in grouped:
            grouped[token.kind].append(token)
        else:
            extras.append(token)

    out = []

    render_items = []
    for kind in order:
        if not enabled_tokens.get(kind, True):
            continue

        for token in grouped.get(kind, []):
            text = token.text().strip()
            if not text:
                continue

            # Do not let hotkey-like strings leak through the value token.
            if kind == TOKEN_VALUE and _is_hotkey_like(text):
                continue

            replacement = _find_token_rename(token, renames)
            if replacement is not None:
                text = replacement

            try:
                pause_value = int(pauses.get(kind, -1))
            except (TypeError, ValueError):
                pause_value = -1
            if pause_value < 0:
                pause = global_pause
            else:
                pause = max(0, pause_value)

            render_items.append((text, pause))

    for index, (text, pause) in enumerate(render_items):
        is_first = index == 0
        is_last = index == len(render_items) - 1

        if pause_placement == "before" and pause and not is_first:
            out.append(BreakCommand(time=pause))

        out.append(text)

        if pause_placement == "after" and pause and not is_last:
            out.append(BreakCommand(time=pause))

        if is_last and pause_after_final and pause:
            out.append(BreakCommand(time=pause))

    # Unknown future token kinds can still render at the end.
    for token in extras:
        text = token.text().strip()
        if not text:
            continue
        out.append(text)

    return out