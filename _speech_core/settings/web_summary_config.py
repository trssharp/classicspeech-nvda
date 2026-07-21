"""Persistent ClassicSpeech configuration for on-demand Web Summary choices."""
from __future__ import annotations

from collections.abc import Iterable

from ..web_summary import normalize_selected_item_types
from .config_core import _ensure_classic_speech_section


PAGE_SUMMARY_DATA_KEY = "pageSummaryData"
INCLUDED_ELEMENT_TYPES_KEY = "includedElementTypes"
INCLUDE_DOCUMENT_TITLE_KEY = "includeDocumentTitle"


def _get_page_summary_data():
    section = _ensure_classic_speech_section()
    data = section.get(PAGE_SUMMARY_DATA_KEY)
    if not hasattr(data, "get"):
        data = {}
        section[PAGE_SUMMARY_DATA_KEY] = data
    return data


def get_included_element_types() -> tuple[str, ...]:
    """Return selected summary item types in the stable ClassicSpeech order."""

    data = _get_page_summary_data()
    if INCLUDED_ELEMENT_TYPES_KEY not in data:
        return normalize_selected_item_types(None)
    saved = data.get(INCLUDED_ELEMENT_TYPES_KEY)
    if not isinstance(saved, (list, tuple, set)):
        saved = []
    return normalize_selected_item_types(saved)


def set_included_element_types(item_types: Iterable[object] | None) -> tuple[str, ...]:
    """Normalize and persist selected item types, retaining deliberate emptiness."""

    normalized = normalize_selected_item_types(item_types)
    data = _get_page_summary_data()
    data[INCLUDED_ELEMENT_TYPES_KEY] = list(normalized)
    return normalized


def get_include_document_title() -> bool:
    """Return whether Page Summary should include the current document title."""

    return bool(_get_page_summary_data().get(INCLUDE_DOCUMENT_TITLE_KEY, False))


def set_include_document_title(enabled: object) -> bool:
    """Persist whether Page Summary should include the current document title."""

    normalized = bool(enabled)
    _get_page_summary_data()[INCLUDE_DOCUMENT_TITLE_KEY] = normalized
    return normalized
