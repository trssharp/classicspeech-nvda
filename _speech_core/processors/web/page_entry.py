"""Opt-in browser page-entry presentation replacement for ClassicSpeech.

This runtime intentionally patches the shared Browse Mode entry class after NVDA
has selected a backend-specific virtual buffer. It keeps NVDA's initial
focus/caret setup and braille handling, while replacing the explicit
root-document/initial-line presentation with a callback owned by ClassicSpeech.
All compatibility uncertainty fails closed to NVDA's native implementation.
"""
from __future__ import annotations

import functools
import inspect

import api
import braille
import config
import controlTypes
import speech
import textInfos
from speech import sayAll

from ...settings.web.summary_config import get_page_orientation_enabled

_METHOD = "event_treeInterceptor_gainFocus"
_MARKER = "_classicSpeechPageOrientationRoute"


def _is_supported_initial_handler(method) -> bool:
    """Accept only the current no-argument bound virtual-buffer entry shape."""
    try:
        parameters = tuple(inspect.signature(method).parameters)
    except (TypeError, ValueError):
        return False
    return parameters == ("self",)


def _get_target_classes():
    """Return NVDA's shared post-backend Browse Mode entry class."""
    try:
        import browseMode

        target = browseMode.BrowseModeDocumentTreeInterceptor
    except Exception:
        return ()
    return (target,)


def _is_current_ready_browse_document(document) -> bool:
    try:
        return (
            getattr(api.getFocusObject(), "treeInterceptor", None) is document
            and getattr(document, "isReady", False) is True
            and callable(getattr(document, "_iterNodesByType", None))
        )
    except Exception:
        return False


def _emit_native_initial_presentation(document, had_first_gain_focus, do_say_all):
    """Mirror only NVDA's current explicit presentation branch.

    This helper is called after the original setup sequence has been preserved
    by the browser-class wrapper. It must stay limited to the speech calls from
    the inspected NVDA handler; it does not own caret, focus, braille, or mode
    handling.
    """
    if do_say_all:
        speech.speakObjectProperties(
            document.rootNVDAObject,
            name=True,
            states=True,
            reason=controlTypes.OutputReason.FOCUS,
        )
        sayAll.SayAllHandler.readText(sayAll.CURSOR.CARET)
        return
    if not had_first_gain_focus:
        speech.speakObject(document.rootNVDAObject, reason=controlTypes.OutputReason.FOCUS)
    else:
        ancestors = api.getFocusAncestors()
        focus_difference_level = api.getFocusDifferenceLevel()
        try:
            root_level = ancestors.index(document.rootNVDAObject)
        except ValueError:
            root_level = len(ancestors)
        if focus_difference_level <= root_level:
            speech.speakObject(document.rootNVDAObject, reason=controlTypes.OutputReason.FOCUS)
    info = document.selection
    if not info.isCollapsed:
        speech.speakPreselectedText(info.text)
    else:
        info.expand(textInfos.UNIT_LINE)
        speech.speakTextInfo(info, reason=controlTypes.OutputReason.CARET, unit=textInfos.UNIT_LINE)


def _install_target(plugin, target):
    existing = getattr(target, _MARKER, None)
    if existing:
        owner, original, wrapper = existing
        if owner is plugin:
            return None
        if getattr(target, _METHOD, None) is wrapper:
            return None

    original = getattr(target, _METHOD, None)
    if not callable(original) or not _is_supported_initial_handler(original):
        return None

    @functools.wraps(original)
    def wrapped(document):
        # Disabled, re-entry, focus mode, non-ready, or non-current documents
        # retain the exact native method. Only a first ready browser entry is
        # eligible for the presentation replacement.
        if (
            not get_page_orientation_enabled()
            or getattr(document, "_hadFirstGainFocus", False)
            or getattr(document, "passThrough", False)
            or not _is_current_ready_browse_document(document)
        ):
            return original(document)

        try:
            import browseMode

            had_first_gain_focus = document._hadFirstGainFocus
            focus = api.getFocusObject()
            document.event_gainFocus(focus, lambda: focus.event_gainFocus())
            if document.passThrough:
                # Native setup has switched modes. It produces no Browse Mode
                # orientation, but its final mode and braille handling remain.
                browseMode.reportPassThrough(document)
                braille.handler.handleGainFocus(document)
                return
            document._lastCachedDocumentConstantIdentifier = document.documentConstantIdentifier
            initial_pos = document._getInitialCaretPos()
            if initial_pos:
                document.selection = document.makeTextInfo(initial_pos)
            browseMode.reportPassThrough(document)
            do_say_all = config.conf["virtualBuffers"]["autoSayAllOnPageLoad"]
            document._hadFirstGainFocus = True

            continuation = (
                (lambda: sayAll.SayAllHandler.readText(sayAll.CURSOR.CARET))
                if do_say_all else None
            )
            fallback = lambda: _emit_native_initial_presentation(
                document, had_first_gain_focus, do_say_all
            )
            reported = plugin._report_page_orientation_for_document(
                document, continuation, fallback
            )
            if not reported:
                _emit_native_initial_presentation(document, had_first_gain_focus, do_say_all)

            browseMode.reportPassThrough(document)
            braille.handler.handleGainFocus(document)
        except Exception:
            # State may have changed after the early eligibility check. Do not
            # attempt to run the original method after partial native setup; log
            # the failure and preserve the already-completed setup instead.
            plugin._debug_log("Page Orientation presentation failed after native setup")

    setattr(target, _METHOD, wrapped)
    setattr(target, _MARKER, (plugin, original, wrapped))
    return (target, original, wrapped)


def install(plugin):
    """Install the shared ready Browse Mode wrapper and return its records."""
    records = []
    for target in _get_target_classes():
        record = _install_target(plugin, target)
        if record is not None:
            records.append(record)
    return records


def restore(plugin, records):
    """Restore only wrappers still owned by this plugin instance."""
    for target, original, wrapper in reversed(records or ()):
        try:
            marker = getattr(target, _MARKER, None)
            if marker and marker[0] is plugin:
                if getattr(target, _METHOD, None) is wrapper:
                    setattr(target, _METHOD, original)
                delattr(target, _MARKER)
        except Exception:
            plugin._debug_log("Page Orientation wrapper restoration failed")
