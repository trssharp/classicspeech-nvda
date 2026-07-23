"""Persistent ClassicSpeech Page Summary and page-load presentation settings."""
from __future__ import annotations

from collections.abc import Iterable

from ..web_summary import normalize_selected_item_types
from .config_core import _ensure_classic_speech_section

PAGE_SUMMARY_DATA_KEY = "pageSummaryData"
INCLUDED_ELEMENT_TYPES_KEY = "includedElementTypes"
INCLUDE_DOCUMENT_TITLE_KEY = "includeDocumentTitle"
# Legacy setting retained only for migration from the released Automatic Summary.
AUTOMATIC_REPORT_ON_PAGE_LOAD_KEY = "automaticReportOnPageLoad"
PAGE_LOAD_SUMMARY_MODE_KEY = "pageLoadSummaryMode"
NOTIFY_WHEN_PAGE_READY_KEY = "notifyWhenPageReady"
PAGE_READY_MESSAGE_KEY = "pageReadyMessage"

DEFAULT_NOTIFY_WHEN_PAGE_READY = False
DEFAULT_PAGE_READY_MESSAGE = "Page ready"

PAGE_LOAD_SUMMARY_MODE_NATIVE = "native"
PAGE_LOAD_SUMMARY_MODE_AFTER_READY = "afterReady"
PAGE_LOAD_SUMMARY_MODE_ORIENTATION = "orientation"
PAGE_LOAD_SUMMARY_MODES = (
    PAGE_LOAD_SUMMARY_MODE_NATIVE,
    PAGE_LOAD_SUMMARY_MODE_AFTER_READY,
    PAGE_LOAD_SUMMARY_MODE_ORIENTATION,
)


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
    _get_page_summary_data()[INCLUDED_ELEMENT_TYPES_KEY] = list(normalized)
    return normalized


def get_include_document_title() -> bool:
    return _normalize_explicit_boolean(
        _get_page_summary_data().get(INCLUDE_DOCUMENT_TITLE_KEY, False)
    )


def set_include_document_title(enabled: object) -> bool:
    normalized = _normalize_explicit_boolean(enabled)
    _get_page_summary_data()[INCLUDE_DOCUMENT_TITLE_KEY] = normalized
    return normalized


def _normalize_explicit_boolean(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "true": return True
        if normalized == "false": return False
    return False


def _normalize_message(value: object, default: str) -> str:
    if isinstance(value, str):
        normalized = value.strip()
        if normalized:
            return normalized
    return default


def get_notify_when_page_ready() -> bool:
    return _normalize_explicit_boolean(
        _get_page_summary_data().get(
            NOTIFY_WHEN_PAGE_READY_KEY,
            DEFAULT_NOTIFY_WHEN_PAGE_READY,
        )
    )


def set_notify_when_page_ready(enabled: object) -> bool:
    normalized = _normalize_explicit_boolean(enabled)
    _get_page_summary_data()[NOTIFY_WHEN_PAGE_READY_KEY] = normalized
    return normalized


def get_page_ready_message() -> str:
    return _normalize_message(
        _get_page_summary_data().get(PAGE_READY_MESSAGE_KEY),
        DEFAULT_PAGE_READY_MESSAGE,
    )


def set_page_ready_message(message: object) -> str:
    normalized = _normalize_message(message, DEFAULT_PAGE_READY_MESSAGE)
    _get_page_summary_data()[PAGE_READY_MESSAGE_KEY] = normalized
    return normalized


def get_page_load_summary_mode() -> str:
    """Return the one mutually exclusive page-load summary presentation mode.

    Existing releases store only the legacy automatic-report boolean. Preserve a
    user's enabled release setting as ``afterReady`` until they select a mode.
    """
    data = _get_page_summary_data()
    saved = data.get(PAGE_LOAD_SUMMARY_MODE_KEY)
    if isinstance(saved, str) and saved in PAGE_LOAD_SUMMARY_MODES:
        return saved
    if PAGE_LOAD_SUMMARY_MODE_KEY not in data and _normalize_explicit_boolean(
        data.get(AUTOMATIC_REPORT_ON_PAGE_LOAD_KEY, False)
    ):
        return PAGE_LOAD_SUMMARY_MODE_AFTER_READY
    return PAGE_LOAD_SUMMARY_MODE_NATIVE


def set_page_load_summary_mode(mode: object) -> str:
    normalized = mode if isinstance(mode, str) and mode in PAGE_LOAD_SUMMARY_MODES else PAGE_LOAD_SUMMARY_MODE_NATIVE
    data = _get_page_summary_data()
    data[PAGE_LOAD_SUMMARY_MODE_KEY] = normalized
    # Retain a coherent legacy value for old config readers and downgrade paths.
    data[AUTOMATIC_REPORT_ON_PAGE_LOAD_KEY] = normalized == PAGE_LOAD_SUMMARY_MODE_AFTER_READY
    return normalized


def get_automatic_reporting_enabled() -> bool:
    return get_page_load_summary_mode() == PAGE_LOAD_SUMMARY_MODE_AFTER_READY


def set_automatic_reporting_enabled(enabled: object) -> bool:
    if _normalize_explicit_boolean(enabled):
        return set_page_load_summary_mode(PAGE_LOAD_SUMMARY_MODE_AFTER_READY) == PAGE_LOAD_SUMMARY_MODE_AFTER_READY
    if get_page_load_summary_mode() == PAGE_LOAD_SUMMARY_MODE_AFTER_READY:
        set_page_load_summary_mode(PAGE_LOAD_SUMMARY_MODE_NATIVE)
    return False


def get_page_orientation_enabled() -> bool:
    return get_page_load_summary_mode() == PAGE_LOAD_SUMMARY_MODE_ORIENTATION


def set_page_orientation_enabled(enabled: object) -> bool:
    if _normalize_explicit_boolean(enabled):
        return set_page_load_summary_mode(PAGE_LOAD_SUMMARY_MODE_ORIENTATION) == PAGE_LOAD_SUMMARY_MODE_ORIENTATION
    if get_page_load_summary_mode() == PAGE_LOAD_SUMMARY_MODE_ORIENTATION:
        set_page_load_summary_mode(PAGE_LOAD_SUMMARY_MODE_NATIVE)
    return False
