from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


TOKEN_NAME = "name"
TOKEN_ROLE = "role"
TOKEN_VALUE = "value"
TOKEN_STATE = "state"
TOKEN_POSITION = "position"
TOKEN_DESCRIPTION = "description"
TOKEN_TOOLTIP = "tooltip"
TOKEN_HOTKEY = "hotkey"

DEFAULT_TOKEN_ORDER = [
    TOKEN_NAME,
    TOKEN_ROLE,
    TOKEN_VALUE,
    TOKEN_STATE,
    TOKEN_POSITION,
    TOKEN_DESCRIPTION,
    TOKEN_TOOLTIP,
    TOKEN_HOTKEY,
]

TOKEN_KINDS = tuple(DEFAULT_TOKEN_ORDER)
TOKEN_KIND_SET = set(TOKEN_KINDS)


@dataclass(slots=True)
class SpeechToken:
    """Structured semantic token used by the speech formatting pipeline.

    raw:
        Canonical semantic value, such as "checked" or ["Save"] depending on token type.
    spoken:
        The currently preferred spoken text for this token before final rename rules are applied.
    source:
        Original speech fragments that contributed to this token.
    meta:
        Extra token metadata for future processors without changing the public shape.
    """

    kind: str
    raw: Any = None
    spoken: Optional[str] = None
    source: List[Any] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    def text(self) -> str:
        """Return the currently speakable text for this token."""
        if self.spoken is not None:
            return str(self.spoken)
        if self.raw is None:
            return ""
        if isinstance(self.raw, (list, tuple)):
            return " ".join(str(part) for part in self.raw if part is not None)
        return str(self.raw)

    def clone(self, **changes: Any) -> "SpeechToken":
        """Return a copy with optional field overrides."""
        return replace(self, **changes)

    def with_spoken(self, spoken: Optional[str]) -> "SpeechToken":
        return replace(self, spoken=spoken)

    def with_meta(self, **meta_updates: Any) -> "SpeechToken":
        merged = dict(self.meta)
        merged.update(meta_updates)
        return replace(self, meta=merged)

    def is_empty(self) -> bool:
        return not self.text().strip()

    def as_dict(self) -> Dict[str, Any]:
        """Useful for debugging, logging, and future settings UIs."""
        return {
            "kind": self.kind,
            "raw": self.raw,
            "spoken": self.spoken,
            "source": list(self.source),
            "meta": dict(self.meta),
        }


def token(
    kind: str,
    raw: Any = None,
    spoken: Optional[str] = None,
    source: Optional[Iterable[Any]] = None,
    meta: Optional[Mapping[str, Any]] = None,
) -> SpeechToken:
    """Canonical token factory so callers do not hand-roll token dict-ish shapes."""
    return SpeechToken(
        kind=kind,
        raw=raw,
        spoken=spoken,
        source=list(source) if source is not None else [],
        meta=dict(meta) if meta is not None else {},
    )


def clone_token(tok: SpeechToken, **changes: Any) -> SpeechToken:
    return tok.clone(**changes)


def clone_tokens(tokens: Iterable[SpeechToken]) -> List[SpeechToken]:
    return [t.clone() for t in tokens]


def normalize_kind(kind: Any) -> str:
    return str(kind or "").strip().lower()


def is_token_kind(kind: Any) -> bool:
    return normalize_kind(kind) in TOKEN_KIND_SET


def coerce_token(obj: Any) -> SpeechToken:
    """Convert common token-like inputs to SpeechToken.

    Accepts:
    - SpeechToken
    - dict with token fields
    - plain string, treated as a value token
    """
    if isinstance(obj, SpeechToken):
        return obj

    if isinstance(obj, dict):
        return token(
            kind=normalize_kind(obj.get("kind") or TOKEN_VALUE),
            raw=obj.get("raw"),
            spoken=obj.get("spoken"),
            source=obj.get("source") or [],
            meta=obj.get("meta") or {},
        )

    if isinstance(obj, str):
        return token(TOKEN_VALUE, raw=obj, spoken=obj, source=[obj])

    return token(TOKEN_VALUE, raw=obj, spoken=str(obj), source=[obj])


def coerce_tokens(items: Sequence[Any]) -> List[SpeechToken]:
    return [coerce_token(item) for item in items]


def group_tokens_by_kind(tokens: Iterable[SpeechToken]) -> Dict[str, List[SpeechToken]]:
    grouped: Dict[str, List[SpeechToken]] = {}
    for tok in tokens:
        grouped.setdefault(tok.kind, []).append(tok)
    return grouped


__all__ = [
    "TOKEN_NAME",
    "TOKEN_ROLE",
    "TOKEN_VALUE",
    "TOKEN_STATE",
    "TOKEN_POSITION",
    "TOKEN_DESCRIPTION",
    "TOKEN_TOOLTIP",
    "TOKEN_HOTKEY",
    "DEFAULT_TOKEN_ORDER",
    "TOKEN_KINDS",
    "TOKEN_KIND_SET",
    "SpeechToken",
    "token",
    "clone_token",
    "clone_tokens",
    "normalize_kind",
    "is_token_kind",
    "coerce_token",
    "coerce_tokens",
    "group_tokens_by_kind",
]
