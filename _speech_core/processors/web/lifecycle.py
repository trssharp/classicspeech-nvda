"""Automatic ClassicSpeech Page Summary/Page Ready lifecycle.

This collaborator owns deferred automatic web reporting.  It deliberately has
no dependency on the GlobalPlugin class: the plugin supplies only the narrow
summary-reporting and debug-log callbacks it needs.
"""
from __future__ import annotations

import api
import ui
import wx

from ...settings.web.summary_config import (
    get_automatic_reporting_enabled,
    get_notify_when_page_ready,
    get_page_entry_summary_delay_seconds,
    get_page_orientation_enabled,
    get_page_ready_message,
)


class WebPageLifecycle:
    """Keep automatic page reporting scoped to the current VBuf generation."""

    _AUTOMATIC_PAGE_SUMMARY_RETRY_DELAY_MS = 50
    _AUTOMATIC_PAGE_SUMMARY_MAX_RETRIES = 8

    def __init__(self, report_summary, debug_log):
        self._report_summary = report_summary
        self._debug_log = debug_log
        self._automaticSummaryPending = None
        self._automaticSummaryReported = None
        self._automaticSummaryTerminated = False
        self._pageOrientationSummaryPending = None

    @property
    def automatic_summary_pending(self):
        return self._automaticSummaryPending

    @property
    def automatic_summary_reported(self):
        return self._automaticSummaryReported

    def _automatic_summary_document_for_event(self, obj):
        try:
            focus = api.getFocusObject()
            document = getattr(focus, "treeInterceptor", None)
            event_document = obj if hasattr(obj, "_iterNodesByType") else getattr(obj, "treeInterceptor", None)
            if document is None or document is not event_document:
                return None
            return document if hasattr(document, "_iterNodesByType") else None
        except Exception:
            return None

    def _automatic_summary_load_cycle_marker(self, document, event_obj=None):
        """Return the NVDA virtual-buffer generation for one document load."""
        try:
            handle = getattr(document, "VBufHandle", None)
            if handle is not None:
                return ("buffer", id(handle))
        except Exception:
            pass
        return ("event", id(event_obj)) if event_obj is not None else None

    def _stop_pending(self):
        """Clear references before stopping callbacks so stale work cannot win."""
        pending = self._automaticSummaryPending
        orientation_pending = self._pageOrientationSummaryPending
        self._automaticSummaryPending = None
        self._pageOrientationSummaryPending = None
        for pending_item in (pending, orientation_pending):
            if pending_item is None:
                continue
            try:
                pending_item[2].Stop()
            except Exception:
                pass

    def cancel(self):
        self._automaticSummaryTerminated = True
        self._stop_pending()
        self._automaticSummaryReported = None

    def handle_focus_change(self, focus):
        """Preserve same-document deferred work; cancel only when focus leaves."""
        pending = self._automaticSummaryPending or self._pageOrientationSummaryPending
        if pending is None:
            return
        try:
            focus_document = getattr(focus, "treeInterceptor", None)
        except Exception:
            focus_document = None
        if pending[0] is not focus_document:
            self._stop_pending()

    def _queue_automatic_page_summary(self, document, cycle_marker, attempt=0, settling=False):
        def callback():
            self._run_automatic_page_summary(document, cycle_marker, attempt, settling)
        try:
            delay_ms = (
                get_page_entry_summary_delay_seconds() * 1000
                if settling else self._AUTOMATIC_PAGE_SUMMARY_RETRY_DELAY_MS
            )
            later = wx.CallLater(delay_ms, callback)
        except Exception:
            self._debug_log("failed to defer automatic page summary")
            return
        self._automaticSummaryPending = (document, cycle_marker, later, attempt, settling)

    def _run_automatic_page_summary(self, document, cycle_marker, attempt, settling=False):
        pending = self._automaticSummaryPending
        if (
            pending is None
            or pending[0] is not document
            or pending[1] != cycle_marker
            or pending[3] != attempt
            or pending[4] != settling
        ):
            return
        self._automaticSummaryPending = None

        if self._automaticSummaryTerminated:
            return

        try:
            summary_enabled = get_automatic_reporting_enabled()
            ready_enabled = get_notify_when_page_ready()
            if (
                not (summary_enabled or ready_enabled)
                or self._automatic_summary_document_for_event(document) is not document
            ):
                return
            if not callable(getattr(document, "_iterNodesByType", None)):
                return
            if getattr(document, "isReady", False) is not True:
                if attempt < self._AUTOMATIC_PAGE_SUMMARY_MAX_RETRIES:
                    self._queue_automatic_page_summary(document, cycle_marker, attempt + 1)
                return
            ready_cycle_marker = self._automatic_summary_load_cycle_marker(document)
            if cycle_marker[0] == "buffer" and ready_cycle_marker != cycle_marker:
                return
            if not settling and summary_enabled and get_page_entry_summary_delay_seconds() > 0:
                if ready_enabled:
                    ui.message(get_page_ready_message())
                self._queue_automatic_page_summary(document, ready_cycle_marker, settling=True)
                return
            if self._automaticSummaryReported == (document, ready_cycle_marker):
                return
            self._automaticSummaryReported = (document, ready_cycle_marker)
            if ready_enabled and not settling:
                ui.message(get_page_ready_message())
            if summary_enabled:
                self._report_summary(document)
        except Exception:
            self._debug_log("automatic page summary failed")

    def handle_document_load_complete(self, obj):
        """Schedule one current-document automatic report after native loading."""
        try:
            if self._automaticSummaryTerminated:
                return
            document = self._automatic_summary_document_for_event(obj)
            if document is None:
                return
            cycle_marker = self._automatic_summary_load_cycle_marker(document, obj)
            pending = self._automaticSummaryPending
            if pending is not None and (pending[0] is not document or pending[1] != cycle_marker):
                self._stop_pending()
                pending = None
            summary_enabled = get_automatic_reporting_enabled()
            ready_enabled = get_notify_when_page_ready()
            if get_page_orientation_enabled():
                if pending is not None:
                    self._stop_pending()
                return
            if not (summary_enabled or ready_enabled):
                if pending is not None:
                    self._stop_pending()
                return
            if pending is not None:
                return
            if self._automaticSummaryReported != (document, cycle_marker):
                self._automaticSummaryReported = None
            if self._automaticSummaryReported == (document, cycle_marker) and not getattr(document, "isLoading", False):
                return
            self._queue_automatic_page_summary(document, cycle_marker)
        except Exception:
            self._debug_log("automatic page summary event handling failed")

    def report_page_orientation(self, document, on_summary=None, on_fallback=None):
        """Own Page Orientation presentation, including Page Ready ordering."""
        try:
            if (
                not get_page_orientation_enabled()
                or self._automatic_summary_document_for_event(document) is not document
                or getattr(document, "isReady", False) is not True
            ):
                return False
            cycle_marker = self._automatic_summary_load_cycle_marker(document)
            if get_notify_when_page_ready() and self._automaticSummaryReported != (document, cycle_marker):
                import ui
                ui.message(get_page_ready_message())
            delay_ms = get_page_entry_summary_delay_seconds() * 1000
            if delay_ms:
                self._queue_page_orientation_summary(document, cycle_marker, delay_ms, on_summary, on_fallback)
                return True
            self._automaticSummaryReported = (document, cycle_marker)
            self._report_summary(document)
            if on_summary is not None:
                on_summary()
            return True
        except Exception:
            self._debug_log("Page Orientation summary failed")
            return False

    def _queue_page_orientation_summary(self, document, cycle_marker, delay_ms, on_summary, on_fallback):
        def callback():
            pending = self._pageOrientationSummaryPending
            self._pageOrientationSummaryPending = None
            is_current_document = self._automatic_summary_document_for_event(document) is document
            if (
                pending is None
                or pending[0] is not document
                or pending[1] != cycle_marker
                or not get_page_orientation_enabled()
                or not is_current_document
                or getattr(document, "isReady", False) is not True
                or self._automatic_summary_load_cycle_marker(document) != cycle_marker
            ):
                if is_current_document and on_fallback is not None:
                    on_fallback()
                return
            self._automaticSummaryReported = (document, cycle_marker)
            self._report_summary(document)
            if on_summary is not None:
                on_summary()
        later = wx.CallLater(delay_ms, callback)
        self._pageOrientationSummaryPending = (document, cycle_marker, later)
