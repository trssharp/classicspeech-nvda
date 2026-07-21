"""Pure model helpers for the on-demand ClassicSpeech Web Summary feature.

This module deliberately has no NVDA UI, speech, or plugin imports. It counts
Browse Mode quick-navigation iterators without calling item reporting or
movement methods, so callers can present a summary without moving the user.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol


@dataclass(frozen=True)
class SummaryItemType:
    """One user-selectable, countable NVDA Browse Mode quick-navigation type."""

    item_type: str
    key: str
    singular_label: str
    plural_label: str


# Stable ClassicSpeech display order. The types and gestures are verified against
# NVDA master browseMode.py's quick-navigation registry.
SUMMARY_ITEM_TYPES: tuple[SummaryItemType, ...] = (
    SummaryItemType("annotation", "A", "annotation", "Annotations"),
    SummaryItemType("button", "B", "button", "Buttons"),
    SummaryItemType("comboBox", "C", "combo box", "Combo boxes"),
    SummaryItemType("landmark", "D", "landmark", "Landmarks"),
    SummaryItemType("edit", "E", "edit field", "Edit fields"),
    SummaryItemType("formField", "F", "form field", "Form fields"),
    SummaryItemType("graphic", "G", "graphic", "Graphics"),
    SummaryItemType("heading", "H", "heading", "Headings"),
    SummaryItemType("link", "K", "link", "Links"),
    SummaryItemType("list", "L", "list", "Lists"),
    SummaryItemType("frame", "M", "frame", "Frames"),
    SummaryItemType("embeddedObject", "O", "embedded object", "Embedded objects"),
    SummaryItemType("blockQuote", "Q", "block quote", "Block quotes"),
    SummaryItemType("radioButton", "R", "radio button", "Radio buttons"),
    SummaryItemType("separator", "S", "separator", "Separators"),
    SummaryItemType("table", "T", "table", "Tables"),
    SummaryItemType("error", "W", "error", "Errors"),
    SummaryItemType("checkBox", "X", "check box", "Check boxes"),
)

DEFAULT_INCLUDED_ITEM_TYPES: tuple[str, ...] = (
    "heading",
    "landmark",
    "link",
    "formField",
    "button",
    "table",
)

_EMPTY_SUMMARY_MESSAGE = "No selected element types found."
_ITEM_BY_TYPE = {item.item_type: item for item in SUMMARY_ITEM_TYPES}


class BrowseSummaryDocument(Protocol):
    """The small Browse Mode surface required for safe count-only summaries."""

    def _iterNodesByType(
        self,
        item_type: str,
        direction: str = "next",
        pos: object | None = None,
    ) -> Iterable[object]: ...


def normalize_selected_item_types(selected_item_types: Iterable[object] | None) -> tuple[str, ...]:
    """Return known selected types once, in the stable display order.

    ``None`` means no saved choice exists yet and receives product defaults.
    An explicit empty iterable remains empty so future settings code can retain
    a user's deliberate choice to include no types.
    """

    if selected_item_types is None:
        return DEFAULT_INCLUDED_ITEM_TYPES
    requested = {
        item_type
        for item_type in selected_item_types
        if isinstance(item_type, str)
    }
    return tuple(item.item_type for item in SUMMARY_ITEM_TYPES if item.item_type in requested)


def collect_summary_counts(
    document: BrowseSummaryDocument,
    selected_item_types: Iterable[object] | None,
) -> tuple[tuple[SummaryItemType, int], ...]:
    """Count selected quick-navigation types without reporting or moving items.

    A concrete virtual buffer may not implement every NVDA quick-navigation
    type. An unsupported type is omitted from the result instead of making the
    complete summary fail.
    """

    counts: list[tuple[SummaryItemType, int]] = []
    for item_type in normalize_selected_item_types(selected_item_types):
        item = _ITEM_BY_TYPE[item_type]
        try:
            count = sum(1 for _quick_nav_item in document._iterNodesByType(item_type, "next", None))
        except NotImplementedError:
            continue
        counts.append((item, count))
    return tuple(counts)


def format_summary_counts(counts: Iterable[tuple[SummaryItemType, int]]) -> str:
    """Format selected non-zero counts as a concise natural-language sentence."""

    phrases = []
    for item, count in counts:
        if count <= 0:
            continue
        label = item.singular_label if count == 1 else item.plural_label.lower()
        phrases.append(f"{count} {label}")
    if not phrases:
        return _EMPTY_SUMMARY_MESSAGE
    return f"{', '.join(phrases)}."


def format_summary_with_document_title(document_title: object, summary: str) -> str:
    """Prefix a nonblank document title without changing the count-only model."""

    if not isinstance(document_title, str):
        return summary
    title = document_title.strip()
    if not title:
        return summary
    return f"Title: {title}. {summary}"


def build_summary(
    document: BrowseSummaryDocument,
    selected_item_types: Iterable[object] | None,
) -> str:
    """Build one spoken result for a Browse Mode document without side effects."""

    return format_summary_counts(collect_summary_counts(document, selected_item_types))
