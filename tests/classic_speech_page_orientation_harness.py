"""Focused harness for the opt-in Page Orientation virtual-buffer wrapper."""
from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Reuse the repository's NVDA-shaped module stubs before importing add-on code.
import classic_speech_core_harness  # noqa: F401

import api
import braille
import browseMode
import config
from speech import sayAll

package = types.ModuleType("globalPlugins")
package.__path__ = [str(ROOT)]
sys.modules["globalPlugins"] = package
from globalPlugins import page_orientation_runtime as page_orientation
from _speech_core.settings.web_summary_config import (
    PAGE_LOAD_SUMMARY_MODE_NATIVE,
    PAGE_LOAD_SUMMARY_MODE_ORIENTATION,
    set_page_load_summary_mode,
)


class _BaseBrowseDocument:
    def event_treeInterceptor_gainFocus(self):
        self.native_calls += 1


class _Info:
    isCollapsed = True
    text = ""

    def expand(self, unit):
        self.expanded_unit = unit


class _Document(_BaseBrowseDocument):
    def __init__(self):
        self.native_calls = 0
        self._hadFirstGainFocus = False
        self.passThrough = False
        self.isReady = True
        self.rootNVDAObject = object()
        self.documentConstantIdentifier = "page-1"
        self._lastCachedDocumentConstantIdentifier = None
        self.selection = _Info()
        self.focus_events = 0

    def _iterNodesByType(self, item_type):
        return iter(())

    def event_gainFocus(self, focus, next_handler):
        self.focus_events += 1
        next_handler()

    def _getInitialCaretPos(self):
        return None


class _Plugin:
    def __init__(self, events, report=True):
        self.events = events
        self.report = report

    def _report_page_orientation_for_document(self, document):
        self.events.append("summary")
        return self.report

    def _debug_log(self, message):
        self.events.append("debug")


class PageOrientationTests(unittest.TestCase):
    def setUp(self):
        self.original_base = getattr(browseMode, "BrowseModeDocumentTreeInterceptor", None)
        self.original_report = getattr(browseMode, "reportPassThrough", None)
        self.original_braille_handler = getattr(braille, "handler", None)
        self.original_focus = api.getFocusObject
        self.original_say_handler = sayAll.SayAllHandler
        self.original_cursor = getattr(sayAll, "CURSOR", None)

        browseMode.BrowseModeDocumentTreeInterceptor = _BaseBrowseDocument
        self.mode_events = []
        browseMode.reportPassThrough = lambda document: self.mode_events.append("mode")
        braille.handler = types.SimpleNamespace(
            handleGainFocus=lambda document: self.mode_events.append("braille"),
        )
        config.conf["virtualBuffers"] = {"autoSayAllOnPageLoad": False}
        set_page_load_summary_mode(PAGE_LOAD_SUMMARY_MODE_NATIVE)
        self.routes = []

    def tearDown(self):
        for plugin, routes in reversed(self.routes):
            page_orientation.restore(plugin, routes)
        if self.original_base is None:
            delattr(browseMode, "BrowseModeDocumentTreeInterceptor")
        else:
            browseMode.BrowseModeDocumentTreeInterceptor = self.original_base
        if self.original_report is None:
            delattr(browseMode, "reportPassThrough")
        else:
            browseMode.reportPassThrough = self.original_report
        braille.handler = self.original_braille_handler
        api.getFocusObject = self.original_focus
        sayAll.SayAllHandler = self.original_say_handler
        if self.original_cursor is None:
            if hasattr(sayAll, "CURSOR"):
                delattr(sayAll, "CURSOR")
        else:
            sayAll.CURSOR = self.original_cursor

    def _install(self, events):
        plugin = _Plugin(events)
        routes = page_orientation.install(plugin)
        self.routes.append((plugin, routes))
        return plugin, routes

    def _focus(self, document):
        api.getFocusObject = lambda: types.SimpleNamespace(
            treeInterceptor=document,
            event_gainFocus=lambda: None,
        )

    def test_disabled_mode_calls_exact_native_method(self):
        events = []
        plugin, routes = self._install(events)
        document = _Document()
        self._focus(document)

        document.event_treeInterceptor_gainFocus()

        self.assertEqual(document.native_calls, 1)
        self.assertEqual(events, [])
        self.assertEqual(self.mode_events, [])
        self.assertEqual(len(routes), 1)

    def test_orientation_summary_only_preserves_setup_and_final_updates(self):
        events = []
        self._install(events)
        set_page_load_summary_mode(PAGE_LOAD_SUMMARY_MODE_ORIENTATION)
        document = _Document()
        self._focus(document)

        document.event_treeInterceptor_gainFocus()

        self.assertEqual(events, ["summary"])
        self.assertEqual(document.native_calls, 0)
        self.assertTrue(document._hadFirstGainFocus)
        self.assertEqual(document._lastCachedDocumentConstantIdentifier, "page-1")
        self.assertEqual(self.mode_events, ["mode", "mode", "braille"])

    def test_orientation_summary_precedes_native_say_all(self):
        events = []
        self._install(events)
        set_page_load_summary_mode(PAGE_LOAD_SUMMARY_MODE_ORIENTATION)
        config.conf["virtualBuffers"]["autoSayAllOnPageLoad"] = True
        sayAll.CURSOR = types.SimpleNamespace(CARET="caret")
        sayAll.SayAllHandler = types.SimpleNamespace(
            readText=lambda cursor: events.append(("sayAll", cursor)),
        )
        document = _Document()
        self._focus(document)

        document.event_treeInterceptor_gainFocus()

        self.assertEqual(events, ["summary", ("sayAll", "caret")])

    def test_restore_returns_the_exact_original_method(self):
        events = []
        original = _BaseBrowseDocument.event_treeInterceptor_gainFocus
        plugin, routes = self._install(events)
        self.assertIsNot(_BaseBrowseDocument.event_treeInterceptor_gainFocus, original)

        page_orientation.restore(plugin, routes)
        self.routes.pop()

        self.assertIs(_BaseBrowseDocument.event_treeInterceptor_gainFocus, original)


if __name__ == "__main__":
    unittest.main()
