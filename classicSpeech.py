# classicSpeech.py

import api
import config
import controlTypes
import globalPluginHandler
import globalCommands
import gui
import logHandler
import queueHandler
import scriptHandler
import speech.extensions
import ui
import speech
from speech import shortcutKeys as nvdaShortcutKeys
import braille
import wx
import functools
import inputCore

from speech.commands import BreakCommand

from ._speech_core.dialog_helpers import (
    find_default_button,
    focused_button_default_status,
    get_default_button_name,
    get_object_name,
)
from ._speech_core.menu_hints import MenuHintHelper, is_structural_menubar_sequence
from ._speech_core.prosody_routing import (
    is_keyboard_entry_profile_routing_active,
    is_mouse_pointer_profile_routing_active,
    is_system_notification_profile_routing_active,
    keyboard_entry_profile_routing,
    mouse_pointer_profile_routing,
    system_notification_profile_routing,
    wrap_keyboard_entry_sequence,
    wrap_review_literal_sequence,
    wrap_system_notification_sequence,
)
from ._speech_core.key_labels import get_key_label_runtime
from ._speech_core.processors.core_ui import CoreUISpeechProcessor
from ._speech_core.settings import (
    ClassicSpeechDialog,
    get_announce_speech_hook_loaded_enabled,
    get_debug_logging_enabled,
    get_query_object_source,
    get_object_navigation_processing_enabled,
    get_speech_hook_enabled,
    get_speech_hook_loaded_message,
    QUERY_OBJECT_SOURCE_NATIVE,
    QUERY_OBJECT_SOURCE_NAVIGATOR,
)
from ._speech_core.settings.web_settings_dialog import WebBrowseSettingsDialog
from ._speech_core.settings.voice_profiles_dialog import VoiceProfilesDialog
from ._speech_core.history import SpeechHistoryBuffer, consume_history_native_passthrough
from ._speech_core.history_viewer import show_history_dialog, is_history_list_focus
from ._speech_core.interrupt_control import SpeechInterruptController
from ._speech_core.web_summary import build_summary, format_summary_with_document_title
from .page_orientation_runtime import install as install_page_orientation, restore as restore_page_orientation
from ._speech_core.settings.web_summary_config import (
    get_automatic_reporting_enabled,
    get_included_element_types,
    get_include_document_title,
    get_page_entry_summary_delay_seconds,
    get_page_orientation_enabled,
    get_notify_when_page_ready,
    get_page_ready_message,
)

log = logHandler.log


from ._speech_core.plugin_config import (
    _CLASSIC_SPEECH_SPEC,
    _getClassicSpeechSection,
    _initClassicSpeechConfig,
)


class GlobalPlugin(globalPluginHandler.GlobalPlugin):

    # ``documentLoadComplete`` can precede a usable virtual buffer, notably for
    # early Chromium focus. These retries are wake-ups only: readiness remains
    # the sole authorization to speak.
    _AUTOMATIC_PAGE_SUMMARY_RETRY_DELAY_MS = 50
    _AUTOMATIC_PAGE_SUMMARY_MAX_RETRIES = 8

    __gestures = {
        "kb:NVDA+Shift+C": "openClassicSpeechSettings",
        "kb:NVDA+Tab": "queryCurrentObject",
        "kb:NVDA+E": "announceDefaultButton",
        "kb:Shift+F11": "previousSpeechHistory",
        "kb:Shift+F12": "nextSpeechHistory",
        "kb:Control+Shift+F11": "bottomSpeechHistory",
        "kb:Control+Shift+F12": "topSpeechHistory",
        "kb:F12": "copySpeechHistory",
        "kb:NVDA+Shift+H": "openSpeechHistory",
        "kb:NVDA+Shift+U": "pageSummary",
    }

    _OBJECT_NAVIGATION_SCRIPTS = {
        "script_navigatorObject_current",
        "script_navigatorObject_currentDimensions",
        "script_navigatorObject_toFocus",
        "script_navigatorObject_parent",
        "script_navigatorObject_next",
        "script_navigatorObject_previous",
        "script_navigatorObject_firstChild",
        "script_navigatorObject_nextInFlow",
        "script_navigatorObject_previousInFlow",
        "script_navigatorObject_moveFocus",
        "script_navigatorObject_devInfo",
    }

    _REVIEW_CURSOR_LITERAL_SCRIPTS = {
        "script_review_top",
        "script_review_previousLine",
        "script_review_currentLine",
        "script_review_nextLine",
        "script_review_previousPage",
        "script_review_nextPage",
        "script_review_bottom",
        "script_review_previousWord",
        "script_review_currentWord",
        "script_review_nextWord",
        "script_review_startOfLine",
        "script_review_previousCharacter",
        "script_review_currentCharacter",
        "script_review_nextCharacter",
        "script_review_endOfLine",
        "script_review_startOfSelection",
        "script_review_endOfSelection",
    }

    _REVIEW_CURSOR_STATUS_SCRIPTS = {
        "script_reviewMode_next",
        "script_reviewMode_previous",
        "script_reportReviewCursorLocation",
        "script_reportCurrentNavigatorObjectLocation",
        "script_review_activate",
        "script_review_currentSymbol",
        "script_review_markStartForCopy",
        "script_review_moveToStartMarkedForCopy",
        "script_review_copy",
        "script_reviewCursorToStatusLine",
        # NVDA+Shift+F and its direct Review helper report only
        # api.getReviewPosition(). Caret-formatting scripts stay native.
        "script_reportFormatting",
        "script_reportFormattingAtReview",
        "script_toggleSimpleReviewMode",
        "script_toggleCaretMovesReviewCursor",
        "script_toggleFocusMovesNavigatorObject",
        "script_moveMouseToNavigatorObject",
        "script_moveNavigatorObjectToMouse",
    }
    def _is_object_navigation_script_active(self):
        try:
            currentScript = scriptHandler.getCurrentScript()
        except Exception:
            return False
        if currentScript is None:
            return False
        scriptName = getattr(currentScript, "__name__", "")
        if scriptName in self._OBJECT_NAVIGATION_SCRIPTS:
            return True
        # Bound methods can occasionally expose the underlying function via
        # __func__; this keeps the guard robust across NVDA/Python variations.
        scriptFunc = getattr(currentScript, "__func__", None)
        scriptName = getattr(scriptFunc, "__name__", "")
        return scriptName in self._OBJECT_NAVIGATION_SCRIPTS

    def _current_speech_script_name(self):
        """Return the active NVDA script name, including bound script methods."""
        try:
            currentScript = scriptHandler.getCurrentScript()
        except Exception:
            return "<script lookup failed>"
        if currentScript is None:
            return "<no current script>"
        scriptName = getattr(currentScript, "__name__", "")
        if scriptName:
            return scriptName
        scriptFunc = getattr(currentScript, "__func__", None)
        return getattr(scriptFunc, "__name__", "<unnamed script>")

    def _is_review_cursor_literal_script_active(self):
        """Return true only for NVDA Review Cursor reading scripts.

        Copy, activation, formatting, and Review Say All intentionally remain
        outside this one-sequence route.
        """
        try:
            currentScript = scriptHandler.getCurrentScript()
        except Exception:
            return False
        if currentScript is None:
            return False
        scriptName = getattr(currentScript, "__name__", "")
        if scriptName in self._REVIEW_CURSOR_LITERAL_SCRIPTS:
            return True
        scriptFunc = getattr(currentScript, "__func__", None)
        scriptName = getattr(scriptFunc, "__name__", "")
        return scriptName in self._REVIEW_CURSOR_LITERAL_SCRIPTS

    _REVIEW_MOVEMENT_BOUNDARY_MESSAGES = {"Top", "Bottom", "Left", "Right"}

    def _is_review_movement_boundary_sequence(self, sequence):
        """Return true only for a boundary status emitted before Review text.

        NVDA's Review movement scripts call ``ui.reviewMessage`` for a boundary
        and immediately follow it with ``speakTextInfo`` in the same script.
        Holding this one status lets the filter make both fragments one
        queue-bound Review transaction, without retaining Review state past the
        command.
        """
        if not self._is_review_cursor_literal_script_active():
            return False
        text = [item for item in sequence if isinstance(item, str) and item]
        return len(sequence) == 1 and len(text) == 1 and text[0] in self._REVIEW_MOVEMENT_BOUNDARY_MESSAGES

    def _is_review_cursor_status_script_active(self):
        """Return true only for short Review-Cursor status/result scripts."""
        try:
            currentScript = scriptHandler.getCurrentScript()
        except Exception:
            return False
        if currentScript is None:
            return False
        scriptName = getattr(currentScript, "__name__", "")
        if scriptName in self._REVIEW_CURSOR_STATUS_SCRIPTS:
            return True
        scriptFunc = getattr(currentScript, "__func__", None)
        return getattr(scriptFunc, "__name__", "") in self._REVIEW_CURSOR_STATUS_SCRIPTS

    def _install_shortcut_speaker_bypass(self):
        """Bypass ClassicSpeech for NVDA's native shortcut speaker.

        NVDA's reportFocusObjectAccelerator script calls
        speech.shortcutKeys.speakKeyboardShortcuts(). Wrapping that helper is more
        reliable than replacing the script method after gesture registration, and
        it works for desktop layout, laptop layout, and user remaps.
        """
        try:
            if getattr(nvdaShortcutKeys, "_classicSpeechBypassInstalled", False):
                owner = getattr(nvdaShortcutKeys, "_classicSpeechBypassOwner", None)
                if owner is self:
                    return
                original = getattr(nvdaShortcutKeys, "_classicSpeechOriginalSpeakKeyboardShortcuts", None)
                if original is not None:
                    nvdaShortcutKeys.speakKeyboardShortcuts = original
                nvdaShortcutKeys._classicSpeechBypassInstalled = False
                nvdaShortcutKeys._classicSpeechBypassOwner = None
            original = nvdaShortcutKeys.speakKeyboardShortcuts
            self._originalSpeakKeyboardShortcuts = original
            nvdaShortcutKeys._classicSpeechOriginalSpeakKeyboardShortcuts = original
            plugin = self

            @functools.wraps(original)
            def wrapped_speakKeyboardShortcuts(*args, **kwargs):
                try:
                    if getattr(plugin, "_speechHookRegistered", False):
                        plugin.processor._bypass_next_sequence = True
                except Exception:
                    log.debug("ClassicSpeech: failed to arm native shortcut speaker bypass", exc_info=True)
                return original(*args, **kwargs)

            nvdaShortcutKeys.speakKeyboardShortcuts = wrapped_speakKeyboardShortcuts
            nvdaShortcutKeys._classicSpeechBypassInstalled = True
            nvdaShortcutKeys._classicSpeechBypassOwner = self
            log.debug("ClassicSpeech: installed native shortcut speaker bypass")
        except Exception:
            log.exception("ClassicSpeech: failed to install native shortcut speaker bypass")

    def _restore_shortcut_speaker_bypass(self):
        try:
            original = getattr(self, "_originalSpeakKeyboardShortcuts", None)
            if original is not None:
                owner = getattr(nvdaShortcutKeys, "_classicSpeechBypassOwner", None)
                if owner is self or owner is None:
                    nvdaShortcutKeys.speakKeyboardShortcuts = original
            if getattr(nvdaShortcutKeys, "_classicSpeechBypassOwner", None) is self:
                nvdaShortcutKeys._classicSpeechBypassOwner = None
            if getattr(nvdaShortcutKeys, "_classicSpeechBypassInstalled", False) and getattr(nvdaShortcutKeys, "_classicSpeechBypassOwner", None) is None:
                nvdaShortcutKeys._classicSpeechBypassInstalled = False
            log.debug("ClassicSpeech: restored native shortcut speaker")
        except Exception:
            log.debug("ClassicSpeech: failed to restore native shortcut speaker", exc_info=True)

    def _install_keyboard_entry_profile_route(self):
        """Scope only NVDA typed character/word echo to the Keyboard profile."""
        try:
            if getattr(speech, "_classicSpeechKeyboardEntryRouteInstalled", False):
                owner = getattr(speech, "_classicSpeechKeyboardEntryRouteOwner", None)
                if owner is self:
                    return
                original = getattr(speech, "_classicSpeechOriginalSpeakTypedCharacters", None)
                if original is not None:
                    speech.speakTypedCharacters = original
                speech._classicSpeechKeyboardEntryRouteInstalled = False
                speech._classicSpeechKeyboardEntryRouteOwner = None
            original = speech.speakTypedCharacters
            self._originalSpeakTypedCharacters = original
            speech._classicSpeechOriginalSpeakTypedCharacters = original
            plugin = self

            @functools.wraps(original)
            def wrapped_speakTypedCharacters(*args, **kwargs):
                # This public NVDA entry point emits both typed characters and
                # completed typed words. It excludes command/help/shortcut paths.
                with keyboard_entry_profile_routing():
                    return original(*args, **kwargs)

            speech.speakTypedCharacters = wrapped_speakTypedCharacters
            speech._classicSpeechKeyboardEntryRouteInstalled = True
            speech._classicSpeechKeyboardEntryRouteOwner = plugin
            log.debug("ClassicSpeech: installed Keyboard entry profile route")
        except Exception:
            log.exception("ClassicSpeech: failed to install Keyboard entry profile route")

    def _restore_keyboard_entry_profile_route(self):
        try:
            original = getattr(self, "_originalSpeakTypedCharacters", None)
            if original is not None:
                owner = getattr(speech, "_classicSpeechKeyboardEntryRouteOwner", None)
                if owner is self or owner is None:
                    speech.speakTypedCharacters = original
            if getattr(speech, "_classicSpeechKeyboardEntryRouteOwner", None) is self:
                speech._classicSpeechKeyboardEntryRouteOwner = None
            if (
                getattr(speech, "_classicSpeechKeyboardEntryRouteInstalled", False)
                and getattr(speech, "_classicSpeechKeyboardEntryRouteOwner", None) is None
            ):
                speech._classicSpeechKeyboardEntryRouteInstalled = False
            log.debug("ClassicSpeech: restored Keyboard entry route")
        except Exception:
            log.debug("ClassicSpeech: failed to restore Keyboard entry route", exc_info=True)

    def _install_mouse_pointer_profile_route(self):
        try:
            import eventHandler
            original = eventHandler.executeEvent
            self._mouseEventHandler = eventHandler
            self._originalExecuteEvent = original
            @functools.wraps(original)
            def wrapped(eventName, *args, **kwargs):
                if eventName == "mouseMove":
                    with mouse_pointer_profile_routing():
                        return original(eventName, *args, **kwargs)
                return original(eventName, *args, **kwargs)
            eventHandler.executeEvent = wrapped
        except Exception:
            log.debug("ClassicSpeech: mouse profile route unavailable", exc_info=True)

    def _restore_mouse_pointer_profile_route(self):
        handler = getattr(self, "_mouseEventHandler", None)
        original = getattr(self, "_originalExecuteEvent", None)
        if handler is not None and original is not None:
            handler.executeEvent = original

    def _install_windows_toast_system_route(self):
        """Route only NVDA's dedicated transient Windows-toast overlay events.

        Generic UIA notification events are intentionally excluded: applications
        use them for their own results and status messages. Notification Center
        navigation is also untouched because it is ordinary focus speech.
        """
        self._windowsToastRoutes = []
        try:
            import NVDAObjects.UIA as uia
            for class_name, event_name in (
                ("Toast_win8", "event_UIA_toolTipOpened"),
                ("Toast_win10", "event_UIA_window_windowOpen"),
                ("Toast_win10", "event_UIA_toolTipOpened"),
            ):
                toast_class = getattr(uia, class_name, None)
                original = getattr(toast_class, event_name, None)
                if toast_class is None or original is None:
                    continue
                marker = f"_classicSpeechToastRoute_{event_name}"
                prior_route = getattr(toast_class, marker, None)
                if prior_route:
                    prior_owner, prior_original, prior_wrapper = prior_route
                    if prior_owner is self:
                        continue
                    if getattr(toast_class, event_name, None) is prior_wrapper:
                        setattr(toast_class, event_name, prior_original)
                    original = prior_original

                @functools.wraps(original)
                def wrapped(*args, __original=original, **kwargs):
                    with system_notification_profile_routing():
                        return __original(*args, **kwargs)

                setattr(toast_class, event_name, wrapped)
                setattr(toast_class, marker, (self, original, wrapped))
                self._windowsToastRoutes.append((toast_class, event_name, marker, original, wrapped))
        except Exception:
            log.debug("ClassicSpeech: Windows toast System route unavailable", exc_info=True)

    def _restore_windows_toast_system_route(self):
        for toast_class, event_name, marker, original, wrapper in reversed(
            getattr(self, "_windowsToastRoutes", ())
        ):
            try:
                route = getattr(toast_class, marker, None)
                if route and route[0] is self:
                    if getattr(toast_class, event_name, None) is wrapper:
                        setattr(toast_class, event_name, original)
                    delattr(toast_class, marker)
            except Exception:
                log.debug("ClassicSpeech: failed to restore Windows toast System route", exc_info=True)

    def _install_system_notification_profile_routes(self):
        """Scope only selected OS-origin notification functions to System."""
        self._systemNotificationRoutes = []
        for module_name, function_name in (
            ("eventHandler", "handlePossibleDesktopNameChange"),
            ("winAPI.secureDesktop", "_handleSecureDesktopChange"),
            ("winAPI._displayTracking", "reportScreenOrientationChange"),
            ("winAPI._powerTracking", "_reportPowerStatus"),
        ):
            try:
                module = __import__(module_name, fromlist=[function_name])
                original = getattr(module, function_name)
                @functools.wraps(original)
                def wrapped(*args, __original=original, **kwargs):
                    with system_notification_profile_routing():
                        return __original(*args, **kwargs)
                setattr(module, function_name, wrapped)
                self._systemNotificationRoutes.append((module, function_name, original))
            except Exception:
                log.debug("ClassicSpeech: System notification origin unavailable: %s.%s", module_name, function_name, exc_info=True)

    def _restore_system_notification_profile_routes(self):
        for module, function_name, original in reversed(getattr(self, "_systemNotificationRoutes", ())):
            if getattr(module, function_name, None) is not original:
                setattr(module, function_name, original)

    def _install_configuration_save_revert_system_routes(self):
        """Route only queued save/revert confirmations, never factory reset."""
        self._configurationSaveRevertRoutes = []
        try:
            import gui
            main_frame = gui.mainFrame
            original_message = gui.ui.message
            for method_name in (
                "onSaveConfigurationCommand",
                "onRevertToSavedConfigurationCommand",
            ):
                original = getattr(main_frame, method_name)

                @functools.wraps(original)
                def wrapped(*args, __original=original, **kwargs):
                    @functools.wraps(original_message)
                    def routed_message(*message_args, **message_kwargs):
                        with system_notification_profile_routing():
                            return original_message(*message_args, **message_kwargs)

                    gui.ui.message = routed_message
                    try:
                        return __original(*args, **kwargs)
                    finally:
                        gui.ui.message = original_message

                setattr(main_frame, method_name, wrapped)
                self._configurationSaveRevertRoutes.append((main_frame, method_name, original))
        except Exception:
            log.debug("ClassicSpeech: configuration save/revert System routes unavailable", exc_info=True)

    def _restore_configuration_save_revert_system_routes(self):
        for main_frame, method_name, original in reversed(
            getattr(self, "_configurationSaveRevertRoutes", ())
        ):
            if getattr(main_frame, method_name, None) is not original:
                setattr(main_frame, method_name, original)

    def _is_system_voice_script_active(self):
        try:
            import scriptHandler
            script = scriptHandler.getCurrentScript()

            script_name = getattr(script, "__name__", "")
            if script_name.startswith("script_profile_"):
                return True
            return script_name in {
                "script_speechMode",
                "script_dateTime",
                "script_say_battery_status",
                "script_toggleScreenCurtain",
                "script_reportActiveConfigurationProfile",
                "script_toggleConfigProfileTriggers",
                "script_cycleAudioDuckingMode",
                "script_toggleCurrentAppSleepMode",
            }
        except Exception:
            return False


    def _get_query_object(self):
        try:
            if get_query_object_source() == QUERY_OBJECT_SOURCE_NAVIGATOR:
                return api.getNavigatorObject()
        except Exception:
            log.debug("ClassicSpeech: failed to fetch navigator object for query", exc_info=True)
        return api.getFocusObject()

    def _install_remote_speech_compatibility(self):
        """Keep local profile triggers out of NVDA Remote's JSON transport.

        Profile triggers are local config operations, not portable speech. Remote
        receives a copied sequence with only those commands removed; NVDA's local
        SpeechManager still receives the original sequence unchanged.
        """
        try:
            import _remoteClient.session as remote_session
            follower = remote_session.FollowerSession
            marker = "_classicSpeechRemoteSpeechCompatibility"
            existing = getattr(follower, marker, None)
            if existing:
                owner, original, wrapper = existing
                if owner is self:
                    return
                if getattr(follower, "sendSpeech", None) is wrapper:
                    follower.sendSpeech = original
            original = follower.sendSpeech
            plugin = self

            @functools.wraps(original)
            def wrapped(session, speechSequence, *args, **kwargs):
                remote_sequence = [
                    item for item in speechSequence
                    if type(item).__name__ != "ConfigProfileTriggerCommand"
                ]
                return original(session, remote_sequence, *args, **kwargs)

            follower.sendSpeech = wrapped
            setattr(follower, marker, (plugin, original, wrapped))
            self._remoteSpeechFollower = follower

            # Remote registers a bound sendSpeech callback at connection time.
            # Replacing the class method above does not modify callbacks already
            # registered before ClassicSpeech loads, so replace those explicitly.
            from speech.extensions import pre_speechQueued
            self._remoteSpeechCallbacks = []
            for handler in list(pre_speechQueued.handlers):
                if getattr(handler, "__self__", None) is None:
                    continue
                if not isinstance(getattr(handler, "__self__", None), follower):
                    continue
                if getattr(handler, "__func__", None) is not original:
                    continue

                @functools.wraps(handler)
                def queued_wrapped(speechSequence, priority=None, __original=handler):
                    remote_sequence = [
                        item for item in speechSequence
                        if type(item).__name__ != "ConfigProfileTriggerCommand"
                    ]
                    return __original(remote_sequence, priority)

                pre_speechQueued.unregister(handler)
                pre_speechQueued.register(queued_wrapped)
                self._remoteSpeechCallbacks.append((pre_speechQueued, handler, queued_wrapped))
            self._debug_log("installed NVDA Remote local-trigger compatibility")
        except ImportError:
            self._remoteSpeechFollower = None
        except Exception:
            self._remoteSpeechFollower = None
            log.debug("ClassicSpeech: NVDA Remote compatibility unavailable", exc_info=True)

    def _restore_remote_speech_compatibility(self):
        for action, original_handler, wrapper in reversed(
            getattr(self, "_remoteSpeechCallbacks", ())
        ):
            try:
                action.unregister(wrapper)
                action.register(original_handler)
            except Exception:
                log.debug("ClassicSpeech: failed to restore an NVDA Remote speech callback", exc_info=True)
        self._remoteSpeechCallbacks = []

        follower = getattr(self, "_remoteSpeechFollower", None)
        if follower is None:
            return
        marker = "_classicSpeechRemoteSpeechCompatibility"
        existing = getattr(follower, marker, None)
        if existing and existing[0] is self:
            _, original, wrapper = existing
            if getattr(follower, "sendSpeech", None) is wrapper:
                follower.sendSpeech = original
            delattr(follower, marker)
        self._remoteSpeechFollower = None

    def __init__(self):
        super().__init__()

        _initClassicSpeechConfig()

        section = _getClassicSpeechSection()
        defaultProfile = section.get("defaultProfile", "Beginner")

        self.processor = CoreUISpeechProcessor()
        self.processor.set_profile(defaultProfile)
        self.history = SpeechHistoryBuffer()
        self._settingsDialog = None
        self._webBrowseDialog = None
        self._voiceProfilesDialog = None
        self._classicSpeechMenu = None
        self._classicSpeechMenuItem = None
        self._classicSpeechPreferencesMenu = None
        self._classicSpeechMenuItems = []
        self._menuHints = MenuHintHelper()
        self._keyLabelRuntime = get_key_label_runtime()
        self._interruptController = SpeechInterruptController()
        self._install_shortcut_speaker_bypass()
        self._install_keyboard_entry_profile_route()
        self._install_mouse_pointer_profile_route()
        self._install_windows_toast_system_route()
        self._install_system_notification_profile_routes()
        self._install_configuration_save_revert_system_routes()
        self._install_remote_speech_compatibility()
        self._pendingContainerSequence = None
        self._pendingContainerFlush = None
        self._flushingPendingContainer = False
        self._speechHookRegistered = False
        self._automaticSummaryPending = None
        self._automaticSummaryReported = None
        self._automaticSummaryTerminated = False
        self._pageOrientationRoutes = install_page_orientation(self)

        self._installClassicSpeechMenu()
        self.set_speech_hook_enabled(get_speech_hook_enabled())

        log.info(f"ClassicSpeech loaded (profile: {defaultProfile}, hook: {self._speechHookRegistered})")

    def terminate(self):
        self._cancel_automatic_page_summaries()
        restore_page_orientation(self, getattr(self, "_pageOrientationRoutes", ()))
        self._pageOrientationRoutes = []
        self._unregister_speech_hook()
        self._restore_remote_speech_compatibility()
        self._restore_windows_toast_system_route()
        self._restore_system_notification_profile_routes()
        self._restore_configuration_save_revert_system_routes()
        self._restore_mouse_pointer_profile_route()
        try:
            self._restore_keyboard_entry_profile_route()
        except Exception:
            log.debug("ClassicSpeech: failed to restore Keyboard entry route", exc_info=True)
        try:
            self._restore_shortcut_speaker_bypass()
        except Exception:
            log.debug("ClassicSpeech: failed to restore native shortcut speaker bypass", exc_info=True)
        try:
            self._interruptController.uninstall()
        except Exception:
            log.debug("ClassicSpeech: failed to uninstall speech interrupt controller", exc_info=True)
        try:
            pendingFlush = getattr(self, "_pendingContainerFlush", None)
            if pendingFlush is not None:
                pendingFlush.Stop()
        except Exception:
            pass
        try:
            self._keyLabelRuntime.terminate()
        except Exception:
            log.debug("ClassicSpeech: failed to restore key labels", exc_info=True)
        self._removeClassicSpeechMenu()
        log.info("ClassicSpeech unloaded")


    def _debug_log(self, message):
        try:
            if get_debug_logging_enabled():
                log.info(f"ClassicSpeech debug: {message}")
        except Exception:
            pass


    def _announce_speech_hook_loaded(self):
        try:
            if not get_announce_speech_hook_loaded_enabled():
                return
            message = get_speech_hook_loaded_message()
            if message:
                ui.message(message)
        except Exception:
            log.debug("ClassicSpeech: failed to announce speech hook loaded", exc_info=True)


    def _register_speech_hook(self):
        if self._speechHookRegistered:
            return
        speech.extensions.filter_speechSequence.register(self._filterSpeechSequence)
        self._speechHookRegistered = True
        self._debug_log("registered filter_speechSequence hook")
        self._announce_speech_hook_loaded()


    def _unregister_speech_hook(self):
        if not getattr(self, "_speechHookRegistered", False):
            return
        try:
            speech.extensions.filter_speechSequence.unregister(self._filterSpeechSequence)
        except Exception:
            log.debug("ClassicSpeech: failed to unregister speech hook", exc_info=True)
        self._speechHookRegistered = False
        self._debug_log("unregistered filter_speechSequence hook")


    def set_speech_hook_enabled(self, enabled):
        if enabled:
            self._interruptController.install()
            self._keyLabelRuntime.install()
            self._register_speech_hook()
        else:
            self._unregister_speech_hook()
            self._interruptController.uninstall()
            self._keyLabelRuntime.terminate()
            self._clear_hotkey_carryover()
            try:
                self.processor._bypass_next_sequence = False
            except Exception:
                pass
            self._cancel_pending_container_flush()
            self._pendingContainerSequence = None


    def _string_tokens(self, sequence):
        return [item for item in sequence if isinstance(item, str) and item.strip()]

    def _norm_text(self, text):
        return str(text or "").strip().lower().rstrip(":.")

    def _looks_like_position_text(self, text):
        import re
        return bool(re.fullmatch(r"\d+\s+of\s+\d+", self._norm_text(text)))

    def _looks_like_container_role_text(self, text):
        normalized = self._norm_text(text).replace(" ", "")
        return normalized in {
            "list",
            "listview",
            "tree",
            "treeview",
            "table",
            "grid",
            "toolbar",
            "tabcontrol",
            "combobox",
        }

    def _is_categories_list_focus(self):
        try:
            focus = api.getFocusObject()
            if not focus:
                return False
            name = self._norm_text(getattr(focus, "name", ""))
            if name == "categories":
                return True
            parent = getattr(focus, "parent", None)
            parent_name = self._norm_text(getattr(parent, "name", "")) if parent else ""
            return parent_name == "categories"
        except Exception:
            return False

    def _normalize_categories_list_leak(self, sequence):
        strings = self._string_tokens(sequence)
        if len(strings) == 1 and self._looks_like_container_role_text(strings[0]) and self._is_categories_list_focus():
            return ["Categories", "list"]
        return sequence

    def _split_container_hotkey_tail(self, sequence):
        seq = list(sequence)
        # Keep accelerator/access-key fragments at the end of the merged event
        # so token order can place the hotkey after the focused item.
        for i, item in enumerate(seq):
            if isinstance(item, str) and self._norm_text(item) in {"alt+", "alt,", "control+", "ctrl+", "shift+", "windows+", "win+"}:
                return seq[:i], seq[i:]
        return seq, []

    def _is_mergeable_container_sequence(self, sequence):
        strings = self._string_tokens(sequence)
        if not strings:
            return False
        if any(self._looks_like_position_text(s) for s in strings):
            return False
        if not any(self._looks_like_container_role_text(s) for s in strings):
            return False
        # Only hold compact container focus fragments such as
        # ['Categories:', 'list', 'Alt+', CharacterModeCommand(True), 'c', ...].
        # Avoid holding verbose content or ordinary list-item navigation.
        return len(strings) <= 4

    def _focus_is_item_like(self):
        try:
            role_key = self.processor._get_focus_role_key()
        except Exception:
            role_key = None
        return role_key in {"listitem", "treeviewitem", "menuitem", "tablerow", "tablecell"}

    def _is_mergeable_item_followup(self, sequence):
        strings = self._string_tokens(sequence)
        if not strings:
            return False
        if self._focus_is_item_like():
            return True
        return any(self._looks_like_position_text(s) for s in strings)

    def _cancel_pending_container_flush(self):
        pendingFlush = getattr(self, "_pendingContainerFlush", None)
        if pendingFlush is not None:
            try:
                pendingFlush.Stop()
            except Exception:
                pass
        self._pendingContainerFlush = None

    def _flush_pending_container_sequence(self):
        pending = getattr(self, "_pendingContainerSequence", None)
        self._pendingContainerSequence = None
        self._pendingContainerFlush = None
        if not pending:
            return
        try:
            self._flushingPendingContainer = True
            raw = pending.get("raw") if isinstance(pending, dict) else pending
            speech.speak(list(raw or []))
        except Exception:
            log.debug("ClassicSpeech: failed to flush pending container sequence", exc_info=True)
        finally:
            self._flushingPendingContainer = False

    def _hold_container_sequence(self, sequence):
        self._cancel_pending_container_flush()
        core, hotkey = self._split_container_hotkey_tail(sequence)
        self._pendingContainerSequence = {"core": core, "hotkey": hotkey, "raw": list(sequence)}
        log.debug(f"ClassicSpeech: holding split container speech briefly: {sequence}")
        try:
            self._pendingContainerFlush = wx.CallLater(50, self._flush_pending_container_sequence)
        except Exception:
            self._pendingContainerFlush = None
        return []

    def _consume_pending_container_for(self, sequence):
        pending = getattr(self, "_pendingContainerSequence", None)
        if not pending:
            return None
        self._cancel_pending_container_flush()
        self._pendingContainerSequence = None
        if self._is_mergeable_item_followup(sequence):
            merged = list(pending.get("core") or pending.get("raw") or [])
            if merged and isinstance(merged[-1], str):
                merged.append(BreakCommand(time=80))
            merged.extend(list(sequence))
            if pending.get("hotkey"):
                merged.append(BreakCommand(time=80))
                merged.extend(list(pending.get("hotkey") or []))
            log.debug(f"ClassicSpeech: merged generic container/item sequence: {pending.get('raw')} -> {merged}")
            return merged
        # If the held sequence was a false positive, do not drop it. Speak it
        # immediately before the current sequence as one conservative utterance.
        merged = list(pending.get("raw") or [])
        if merged and isinstance(merged[-1], str):
            merged.append(BreakCommand(time=80))
        merged.extend(list(sequence))
        return merged

    def _merge_prefix_sequence(self, prefix, sequence):
        if not prefix:
            return list(sequence)
        seq = list(sequence)
        lead = []
        rest = list(seq)
        while rest and not isinstance(rest[0], str):
            lead.append(rest.pop(0))
        merged = lead + list(prefix)
        if rest and isinstance(merged[-1], str):
            merged.append(BreakCommand(time=80))
        merged.extend(rest)
        return merged

    def _hint_only_sequence(self, prefix):
        out = []
        for index, item in enumerate(prefix):
            out.append(item)
            if index < len(prefix) - 1:
                out.append(BreakCommand(time=80))
        return out

    def _record_history(self, sequence):
        try:
            self.history.append_sequence(sequence)
        except Exception:
            log.debug("ClassicSpeech: failed to append speech history", exc_info=True)


    def _sequence_is_character_navigation(self, sequence):
        try:
            for item in sequence:
                if item.__class__.__name__ == "CharacterModeCommand" and getattr(item, "state", False):
                    return True
        except Exception:
            return False
        return False

    def _apply_text_processing(self, speechSequence):
        """Apply text-only processors at the speech-hook boundary.

        Text processors operate on literal string data and must be independent
        from semantic role demotion / formatting bypasses. This lets editor,
        Say All, and command-wrapped text sequences use the same transformation
        path while still preserving non-string speech commands.
        """
        try:
            textProcessor = getattr(self.processor, "text_processor", None)
            if textProcessor is None:
                return speechSequence
            try:
                repeatedMode = textProcessor.get_repeated_character_mode()
            except Exception:
                repeatedMode = "unknown"
            allowNumberModes = not self._sequence_is_character_navigation(speechSequence)
            processed = textProcessor.process_literal_sequence(
                speechSequence,
                allow_number_modes=allowNumberModes,
            )
            if processed != list(speechSequence):
                speechSequence.clear()
                speechSequence.extend(processed)
                self._debug_log(f"text processed (repeated mode {repeatedMode}): {speechSequence}")
            else:
                self._debug_log(f"text unchanged (repeated mode {repeatedMode})")
        except Exception:
            log.exception("ClassicSpeech: text processing failed")
        return speechSequence

    def _sequence_has_text(self, sequence):
        try:
            return any(isinstance(item, str) and item.strip() for item in sequence)
        except Exception:
            return False

    def _clear_hotkey_carryover(self):
        """Clear only hotkey carryover state; leave container merge buffers alone."""
        try:
            self.processor._pending_hotkey = None
        except Exception:
            pass

    def _is_input_help_active(self):
        try:
            return bool(inputCore.manager.isInputHelpActive)
        except Exception:
            return False

    def _filterSpeechSequence(self, speechSequence):
        try:
            self._debug_log(f"filter input: {speechSequence}")
            # History replay/copy confirmations are already final flattened text.
            # Speak them natively so Shift+F11, Shift+F12, Ctrl+Shift+F11,
            # Ctrl+Shift+F12, and F12 cannot be reclassified into silence.
            # Do not record these here; SpeechHistoryBuffer suppresses its own
            # replay/copy speech so history does not recursively record itself.
            if consume_history_native_passthrough():
                return speechSequence

            # Input help is a native diagnostic mode. Do not tokenize it, do not
            # extract/apply hotkeys, and do not let a previously extracted hotkey
            # leak into the following input-help description.
            if self._is_input_help_active():
                self._clear_hotkey_carryover()
                self._record_history(speechSequence)
                self._debug_log("bypass: input help")
                return speechSequence

            # Explicit native pass-through paths should stay completely raw.
            # History is intentionally recorded before returning so the history
            # buffer acts like a recorder at the speech-hook boundary rather
            # than a feature hidden behind the formatter.
            if getattr(self.processor, "_bypass_next_sequence", False):
                self.processor._bypass_next_sequence = False
                self._clear_hotkey_carryover()
                self._record_history(speechSequence)
                self._debug_log("bypass: requested native pass-through")
                return speechSequence

            # ``speech.speakTypedCharacters`` is NVDA's shared typed-character
            # and typed-word echo entry point. Keep its text native; add only
            # Keyboard profile prosody and do not invoke hotkey/text processing.
            if is_keyboard_entry_profile_routing_active():
                self._clear_hotkey_carryover()
                output = wrap_keyboard_entry_sequence(speechSequence)
                self._record_history(output)
                self._debug_log("typed keyboard/braille entry uses Keyboard profile")
                return output

            if is_mouse_pointer_profile_routing_active():
                self._clear_hotkey_carryover()
                output = wrap_review_literal_sequence(speechSequence)
                self._record_history(output)
                self._debug_log("mouse pointer feedback uses Review profile")
                return output

            if is_system_notification_profile_routing_active() or self._is_system_voice_script_active():
                self._clear_hotkey_carryover()
                output = wrap_system_notification_sequence(speechSequence)
                self._record_history(output)
                self._debug_log("scoped System notification uses System profile")
                return output

            if self._is_review_cursor_status_script_active():
                self._clear_hotkey_carryover()
                output = wrap_review_literal_sequence(speechSequence)
                self._record_history(output)
                self._debug_log("review cursor status uses Review profile")
                return output

            self._apply_text_processing(speechSequence)

            isObjectNavigation = self._is_object_navigation_script_active()
            isReviewCursorLiteral = self._is_review_cursor_literal_script_active()
            if not isReviewCursorLiteral and getattr(self, "_pendingReviewMovementBoundary", None):
                self._pendingReviewMovementBoundary = None
                self._debug_log("discarded incomplete Review movement boundary")
            if self._is_review_movement_boundary_sequence(speechSequence):
                self._pendingReviewMovementBoundary = list(speechSequence)
                self._debug_log("held Review movement boundary for following Review text")
                return []
            if isReviewCursorLiteral:
                pendingBoundary = getattr(self, "_pendingReviewMovementBoundary", None)
                if pendingBoundary and self._sequence_has_text(speechSequence):
                    speechSequence = list(pendingBoundary) + list(speechSequence)
                    self._pendingReviewMovementBoundary = None
                    self._debug_log("merged Review movement boundary with following Review text")
                elif pendingBoundary:
                    self._debug_log("kept Review movement boundary across command-only fragment")
            # Disabling object-navigation processing disables ClassicSpeech's
            # semantic formatting, not the user-selected Review Voice. Preserve
            # NVDA's whole sequence but apply only Review prosody for explicit
            # navigator-object commands and their status messages.
            if (not get_object_navigation_processing_enabled()) and isObjectNavigation:
                self._clear_hotkey_carryover()
                output = wrap_review_literal_sequence(speechSequence)
                self._record_history(output)
                self._debug_log("object navigation native sequence uses Review profile")
                return output

            # A real Review Cursor reading script owns every one of its native
            # speech sequences, including spelling fragments with command
            # boundaries. Preserve the sequence intact and add only the Review
            # profile commands around its spoken text.
            if isReviewCursorLiteral:
                self._clear_hotkey_carryover()
                output = wrap_review_literal_sequence(speechSequence)
                self._record_history(output)
                self._debug_log("review cursor sequence uses Review profile")
                return output

            # Speech for actual history entries inside our own history dialog is
            # already final user-facing text. Bypass only list-item navigation;
            # let the list control and Copy/Clear/Close buttons use normal
            # ClassicSpeech verbosity processing. Record it so the recorder sees
            # native list navigation too, while replay suppression above prevents
            # recursive history entries.
            if is_history_list_focus(speechSequence):
                self._clear_hotkey_carryover()
                self._record_history(speechSequence)
                self._debug_log("bypass: speech history list focus")
                return speechSequence

            # Sequence merging is for focus-mode/app control chatter only.
            # Run this before the single-fragment literal-review guard: native
            # focus speech often arrives as a bare structural role first
            # ("list", "tree view", etc.) followed immediately by the real
            # focused item.  If literal review sees that first, it leaks the
            # unlabeled container role before the useful item speech.
            #
            # Browse/virtual-buffer speech still bypasses this so plain web text
            # such as "list" is not held and virtual navigation stays snappy.
            mergeAllowed = True
            try:
                mergeAllowed = self.processor.should_process(speechSequence)
            except Exception:
                mergeAllowed = True

            if mergeAllowed and not getattr(self, "_flushingPendingContainer", False):
                mergedSequence = self._consume_pending_container_for(speechSequence)
                if mergedSequence is not None:
                    speechSequence = mergedSequence
                elif self._is_mergeable_container_sequence(speechSequence):
                    return self._hold_container_sequence(speechSequence)

            # Literal review/caret text must be completely raw. Run this after
            # the compact split-container guard above so unlabeled container
            # fragments do not leak as standalone role speech.
            if self.processor.should_bypass_literal_review(speechSequence):
                self._clear_hotkey_carryover()
                output = (
                    wrap_review_literal_sequence(speechSequence)
                    if isReviewCursorLiteral
                    else speechSequence
                )
                self._record_history(output)
                self._debug_log(
                    "review cursor literal sequence uses Review profile"
                    if isReviewCursorLiteral
                    else (
                        "bypass: literal review/caret text after text processing "
                        f"(script={self._current_speech_script_name()}): {speechSequence}"
                    ),
                )
                return output

            prefix = self._menuHints.get_prefix_sequence(speechSequence)
            speechOrigin = "objectNavigation" if isObjectNavigation else "focus"
            processed = self.processor.process(speechSequence, speech_origin=speechOrigin)

            # Normalize anonymous structural menubar utterances such as
            # "Menu Bar, tool bar" to the explicit menubar hint only.
            # This prevents Firefox and similar apps from saying awkward
            # container speech like "menu active, menu bar, tool bar".
            if is_structural_menubar_sequence(speechSequence):
                # Suppress raw structural container speech such as
                # "Menu Bar, tool bar". MenuHintHelper queues the normalized
                # "menu bar" hint and attaches it to the next real item
                # sequence, preventing Firefox from cancelling the hint.
                self._debug_log("suppressed structural menubar sequence")
                return []

            if prefix:
                output = self._merge_prefix_sequence(prefix, processed)
            else:
                output = processed

            # Defensive failsafe: if processing accidentally turns a non-empty
            # native announcement into command-only speech, fall back to the
            # original sequence rather than speaking silence. This is especially
            # useful for flattened strings that contain position-like text.
            if self._sequence_has_text(speechSequence) and not self._sequence_has_text(output):
                try:
                    if any(not isinstance(item, str) for item in output):
                        log.debug("ClassicSpeech: command-only output detected; falling back to native speech")
                        self._record_history(speechSequence)
                        return speechSequence
                except Exception:
                    pass

            self._record_history(output)
            self._debug_log(f"filter output: {output}")
            return output
        except Exception as e:
            log.error(f"ClassicSpeech speech filter failure: {e}", exc_info=True)
            return speechSequence


    def _is_secure_context(self):
        try:
            globalVars = __import__("globalVars")
            return bool(getattr(getattr(globalVars, "appArgs", None), "secure", False))
        except Exception:
            return False

    def _installClassicSpeechMenu(self):
        """Add ClassicSpeech entry points under NVDA menu > Preferences."""
        if self._is_secure_context():
            return
        try:
            sysTrayIcon = gui.mainFrame.sysTrayIcon
            preferencesMenu = sysTrayIcon.preferencesMenu
            classicSpeechMenu = wx.Menu()
            generalItem = classicSpeechMenu.Append(wx.ID_ANY, "General Settings...")
            webItem = classicSpeechMenu.Append(wx.ID_ANY, "Web / Browse Mode Settings...")
            voiceProfilesItem = classicSpeechMenu.Append(wx.ID_ANY, "Voice Profiles...")
            submenuItem = preferencesMenu.AppendSubMenu(classicSpeechMenu, "ClassicSpeech")
            sysTrayIcon.Bind(wx.EVT_MENU, self.onClassicSpeechGeneralSettingsMenu, generalItem)
            sysTrayIcon.Bind(wx.EVT_MENU, self.onClassicSpeechWebBrowseSettingsMenu, webItem)
            sysTrayIcon.Bind(wx.EVT_MENU, self.onClassicSpeechVoiceProfilesMenu, voiceProfilesItem)
            self._classicSpeechPreferencesMenu = preferencesMenu
            self._classicSpeechMenu = classicSpeechMenu
            self._classicSpeechMenuItem = submenuItem
            self._classicSpeechMenuItems = [generalItem, webItem, voiceProfilesItem]
        except Exception:
            self._classicSpeechPreferencesMenu = None
            self._classicSpeechMenu = None
            self._classicSpeechMenuItem = None
            self._classicSpeechMenuItems = []
            log.debug("ClassicSpeech: failed to install Preferences submenu", exc_info=True)

    def _removeClassicSpeechMenu(self):
        """Remove and destroy the Preferences submenu during plugin reload.

        wx.Menu.Remove expects an item id in the same way NVDA's own dynamic
        Remote Access submenu is cleaned up.  Removing by the wrapper object
        can leave the old menu item attached after Control+Insert+F3, producing
        duplicate ClassicSpeech submenus on the next plugin initialization.
        """
        try:
            preferencesMenu = getattr(self, "_classicSpeechPreferencesMenu", None)
            if preferencesMenu is None:
                preferencesMenu = gui.mainFrame.sysTrayIcon.preferencesMenu

            menuItems = []
            knownItem = getattr(self, "_classicSpeechMenuItem", None)
            if knownItem is not None:
                menuItems.append(knownItem)

            # Clean up stale entries left by earlier reloads as well as the
            # current plugin's own submenu item.
            for item in list(preferencesMenu.GetMenuItems()):
                try:
                    label = item.GetItemLabelText()
                except Exception:
                    label = item.GetLabel()
                if str(label or "").replace("&", "").strip() == "ClassicSpeech" and item not in menuItems:
                    menuItems.append(item)

            for item in menuItems:
                try:
                    preferencesMenu.Remove(item.Id)
                except Exception:
                    log.debug("ClassicSpeech: failed to remove Preferences submenu item", exc_info=True)
                    continue
                try:
                    item.Destroy()
                except Exception:
                    log.debug("ClassicSpeech: failed to destroy Preferences submenu item", exc_info=True)

            menu = getattr(self, "_classicSpeechMenu", None)
            if menu is not None:
                try:
                    menu.Destroy()
                except Exception:
                    pass
        except Exception:
            log.debug("ClassicSpeech: failed to remove Preferences submenu", exc_info=True)
        finally:
            self._classicSpeechPreferencesMenu = None
            self._classicSpeechMenu = None
            self._classicSpeechMenuItem = None
            self._classicSpeechMenuItems = []

    def onClassicSpeechGeneralSettingsMenu(self, evt):
        queueHandler.queueFunction(queueHandler.eventQueue, self._openSettings)

    def onClassicSpeechWebBrowseSettingsMenu(self, evt):
        queueHandler.queueFunction(queueHandler.eventQueue, self._openWebBrowseSettings)

    def onClassicSpeechVoiceProfilesMenu(self, evt):
        queueHandler.queueFunction(queueHandler.eventQueue, self._openVoiceProfiles)

    @scriptHandler.script(
        description="Opens ClassicSpeech settings",
        category="ClassicSpeech",
    )
    def script_openClassicSpeechSettings(self, gesture):
        queueHandler.queueFunction(queueHandler.eventQueue, self._openSettings)


    def _report_page_summary_for_document(self, document):
        """Speak one Page Summary, optionally prefixed by the document name."""
        summary = build_summary(document, get_included_element_types())
        document_title = None
        if get_include_document_title():
            try:
                document_title = getattr(getattr(document, "rootNVDAObject", None), "name", None)
            except Exception:
                log.debugWarning("ClassicSpeech: unable to read Page Summary document title", exc_info=True)
        ui.message(format_summary_with_document_title(document_title, summary))

    def _report_page_orientation_for_document(self, document, on_summary=None, on_fallback=None):
        """Own the Page Orientation presentation, possibly after its delay."""
        try:
            if (
                not get_page_orientation_enabled()
                or self._automatic_summary_document_for_event(document) is not document
                or getattr(document, "isReady", False) is not True
            ):
                return False
            cycle_marker = self._automatic_summary_load_cycle_marker(document)
            if get_notify_when_page_ready() and getattr(self, "_automaticSummaryReported", None) != (document, cycle_marker):
                ui.message(get_page_ready_message())
            delay_ms = get_page_entry_summary_delay_seconds() * 1000
            if delay_ms:
                self._queue_page_orientation_summary(document, cycle_marker, delay_ms, on_summary, on_fallback)
                return True
            self._automaticSummaryReported = (document, cycle_marker)
            self._report_page_summary_for_document(document)
            if on_summary is not None:
                on_summary()
            return True
        except Exception:
            log.debug("ClassicSpeech: Page Orientation summary failed", exc_info=True)
            return False

    def _queue_page_orientation_summary(self, document, cycle_marker, delay_ms, on_summary, on_fallback):
        def callback():
            pending = getattr(self, "_pageOrientationSummaryPending", None)
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
            self._report_page_summary_for_document(document)
            if on_summary is not None:
                on_summary()
        later = wx.CallLater(delay_ms, callback)
        self._pageOrientationSummaryPending = (document, cycle_marker, later)

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
        """Return the NVDA virtual-buffer generation for one document load.

        A VirtualBuffer can keep its Python identity across a refresh, while
        ``loadBuffer`` replaces ``VBufHandle`` for the newly loaded buffer.
        NVDA also exposes ``isLoading`` while that replacement is in progress.
        Together these form the cycle boundary: repeated events for one ready
        handle dedupe, while a replacement handle (or an in-progress reload)
        remains eligible. The event object is only a fallback for lightweight
        non-VirtualBuffer test doubles without a handle.
        """
        try:
            handle = getattr(document, "VBufHandle", None)
            if handle is not None:
                return ("buffer", id(handle))
        except Exception:
            pass
        return ("event", id(event_obj)) if event_obj is not None else None

    def _stop_automatic_page_summary_pending(self):
        """Cancel deferred automatic reports before they can become stale."""
        pending = getattr(self, "_automaticSummaryPending", None)
        orientation_pending = getattr(self, "_pageOrientationSummaryPending", None)
        self._automaticSummaryPending = None
        self._pageOrientationSummaryPending = None
        for pending_item in (pending, orientation_pending):
            if pending_item is None:
                continue
            try:
                pending_item[2].Stop()
            except Exception:
                pass

    def _cancel_automatic_page_summaries(self):
        self._automaticSummaryTerminated = True
        self._stop_automatic_page_summary_pending()
        self._automaticSummaryReported = None

    def _cancel_automatic_page_summary_if_focus_changed(self, focus):
        """Discard deferred automatic work as soon as focus leaves its document."""
        pending = getattr(self, "_automaticSummaryPending", None) or getattr(self, "_pageOrientationSummaryPending", None)
        if pending is None:
            return
        try:
            focus_document = getattr(focus, "treeInterceptor", None)
        except Exception:
            focus_document = None
        if pending[0] is not focus_document:
            self._stop_automatic_page_summary_pending()

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
            log.debug("ClassicSpeech: failed to defer automatic page summary", exc_info=True)
            return
        self._automaticSummaryPending = (document, cycle_marker, later, attempt, settling)

    def _run_automatic_page_summary(self, document, cycle_marker, attempt, settling=False):
        pending = getattr(self, "_automaticSummaryPending", None)
        if (
            pending is None
            or pending[0] is not document
            or pending[1] != cycle_marker
            or pending[3] != attempt
            or pending[4] != settling
        ):
            return
        self._automaticSummaryPending = None

        if getattr(self, "_automaticSummaryTerminated", False):
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
            # A retry that began with an actual virtual-buffer handle belongs
            # only to that generation. If Firefox/another backend replaces it
            # before readiness, a later load-complete event owns the replacement
            # cycle and this stale callback must stay silent. By contrast, NVDA
            # can signal documentLoadComplete before any handle exists; its
            # event-fallback marker must be allowed to acquire the first handle.
            if cycle_marker[0] == "buffer" and ready_cycle_marker != cycle_marker:
                return
            if not settling and summary_enabled and get_page_entry_summary_delay_seconds() > 0:
                # The Page Ready notification remains tied to real readiness;
                # only the optional count summary waits for late page content.
                if ready_enabled:
                    ui.message(get_page_ready_message())
                self._queue_automatic_page_summary(document, ready_cycle_marker, settling=True)
                return
            if getattr(self, "_automaticSummaryReported", None) == (document, ready_cycle_marker):
                return
            self._automaticSummaryReported = (document, ready_cycle_marker)
            # Read configuration only after this document has become ready, so
            # a disabled notification cannot leak from an earlier schedule.
            # Keep the ready notification ahead of the existing automatic
            # summary for the same virtual-buffer generation.
            if ready_enabled and not settling:
                ui.message(get_page_ready_message())
            if summary_enabled:
                self._report_page_summary_for_document(document)
        except Exception:
            # Automatic failures are silent; the manual command remains explicit.
            log.debug("ClassicSpeech: automatic page summary failed", exc_info=True)

    def event_gainFocus(self, obj, nextHandler):
        """Cancel only stale deferred summaries after native focus processing."""
        nextHandler()
        self._cancel_automatic_page_summary_if_focus_changed(obj)

    def event_documentLoadComplete(self, obj, nextHandler):
        """Report only one ready current Browse Mode summary after NVDA handles loading."""
        nextHandler()
        try:
            if getattr(self, "_automaticSummaryTerminated", False):
                return
            document = self._automatic_summary_document_for_event(obj)
            if document is None:
                return
            cycle_marker = self._automatic_summary_load_cycle_marker(document, obj)
            pending = getattr(self, "_automaticSummaryPending", None)
            if pending is not None and (pending[0] is not document or pending[1] != cycle_marker):
                self._stop_automatic_page_summary_pending()
                pending = None
            summary_enabled = get_automatic_reporting_enabled()
            ready_enabled = get_notify_when_page_ready()
            if get_page_orientation_enabled():
                # Page Orientation owns the initial ready-page presentation,
                # including an enabled Page Ready message. Never queue the
                # deferred automatic-summary path for that same cycle.
                if pending is not None:
                    self._stop_automatic_page_summary_pending()
                return
            if not (summary_enabled or ready_enabled):
                if pending is not None:
                    self._stop_automatic_page_summary_pending()
                return
            if pending is not None:
                return
            if getattr(self, "_automaticSummaryReported", None) != (document, cycle_marker):
                self._automaticSummaryReported = None
            if getattr(self, "_automaticSummaryReported", None) == (document, cycle_marker) and not getattr(document, "isLoading", False):
                return
            self._queue_automatic_page_summary(document, cycle_marker)
        except Exception:
            log.debug("ClassicSpeech: automatic page summary event handling failed", exc_info=True)

    @scriptHandler.script(
        description="Reports selected Browse Mode element counts for the current page",
        category="ClassicSpeech",
    )
    def script_pageSummary(self, gesture):
        try:
            focus = api.getFocusObject()
            document = getattr(focus, "treeInterceptor", None)
            if document is None or not hasattr(document, "_iterNodesByType"):
                ui.message("Page summary is not available here.")
                return
            self._report_page_summary_for_document(document)
        except Exception:
            log.exception("ClassicSpeech page summary failed")
            ui.message("Page summary is not available here.")


    @scriptHandler.script(
        description="Speaks the current object. Press twice quickly to spell and copy it",
        category="ClassicSpeech",
    )
    def script_queryCurrentObject(self, gesture):
        try:
            if (not getattr(self, "_speechHookRegistered", False)) or (not get_speech_hook_enabled()):
                globalCommands.commands.script_reportCurrentFocus(gesture)
                return

            if get_query_object_source() == QUERY_OBJECT_SOURCE_NATIVE:
                try:
                    self.processor._bypass_next_sequence = True
                except Exception:
                    pass
                globalCommands.commands.script_reportCurrentFocus(gesture)
                return

            focus = self._get_query_object()
            if not focus:
                ui.message("No object")
                return

            repeatCount = scriptHandler.getLastScriptRepeatCount()
            if repeatCount == 0:
                self.processor.speak_query_object(focus)
                return

            text = self.processor.get_query_object_text(focus)
            if not text:
                ui.message("No object")
                return

            speech.speakSpelling(text)
            api.copyToClip(text, notify=False)
        except Exception as e:
            log.error(f"ClassicSpeech query object failed: {e}", exc_info=True)
            ui.message("No focus")
    @scriptHandler.script(
        description="Reviews the previous ClassicSpeech history item",
        category="ClassicSpeech",
    )
    def script_previousSpeechHistory(self, gesture):
        self.history.speak_previous()

    @scriptHandler.script(
        description="Reviews the next ClassicSpeech history item",
        category="ClassicSpeech",
    )
    def script_nextSpeechHistory(self, gesture):
        self.history.speak_next()

    @scriptHandler.script(
        description="Moves to the oldest ClassicSpeech history item",
        category="ClassicSpeech",
    )
    def script_bottomSpeechHistory(self, gesture):
        self.history.speak_bottom()

    @scriptHandler.script(
        description="Moves to the newest ClassicSpeech history item",
        category="ClassicSpeech",
    )
    def script_topSpeechHistory(self, gesture):
        self.history.speak_top()

    @scriptHandler.script(
        description="Copies the current ClassicSpeech history item to the clipboard",
        category="ClassicSpeech",
    )
    def script_copySpeechHistory(self, gesture):
        self.history.copy_current()

    @scriptHandler.script(
        description="Opens the ClassicSpeech history dialog",
        category="ClassicSpeech",
    )
    def script_openSpeechHistory(self, gesture):
        try:
            show_history_dialog(self.history)
        except Exception as e:
            log.error(f"Failed to open ClassicSpeech history: {e}", exc_info=True)
            ui.message("Could not open speech history")


    def _getWxDefaultButtonName(self):
        """Return the wx default button name for NVDA-owned dialogs, when available.

        Some wx dialogs keep Enter wired to the default button even when the
        accessibility tree does not expose an explicit default-button state.
        This is especially visible after a child modal, such as the token rename
        dialog, returns focus to the ClassicSpeech settings dialog.
        """
        try:
            focusWin = wx.Window.FindFocus()
            if not focusWin:
                return ""
            top = wx.GetTopLevelParent(focusWin)
            if not isinstance(top, wx.Dialog):
                return ""
            defaultItem = top.GetDefaultItem()
            if not defaultItem:
                return ""
            if not defaultItem.IsEnabled():
                return ""
            try:
                label = defaultItem.GetLabelText()
            except Exception:
                label = defaultItem.GetLabel()
            return str(label or "").replace("&", "").strip()
        except Exception:
            log.debugWarning("ClassicSpeech: wx default button lookup failed", exc_info=True)
            return ""

    def _getDefaultButtonName(self):
        return get_default_button_name(api.getFocusObject())

    def _getFocusedButtonDefaultStatus(self):
        focus = api.getFocusObject()
        return focus, focused_button_default_status(focus)

    @scriptHandler.script(
        description="Announces the default button in the current dialog",
        category="ClassicSpeech",
    )
    def script_announceDefaultButton(self, gesture):
        try:
            focus = api.getFocusObject()

            # Classic query behavior: if focus is on a button, report the
            # focused button as the queried default-button target.  This is
            # intentionally independent from the true dialog default check;
            # focus speech handles true default-token classification separately.
            try:
                if getattr(focus, "role", None) == controlTypes.Role.BUTTON:
                    name = get_object_name(focus) or "unknown"
                    ui.message(f"Default button {name}")
                    return
            except Exception:
                pass

            name = self._getDefaultButtonName()
            if not name:
                ui.message("No default button")
                return
            ui.message(f"Default button {name}")
        except Exception as e:
            log.error(f"Failed announcing default button: {e}", exc_info=True)
            ui.message("No default button")

    def _onWebBrowseDialogClosed(self, evt):
        try:
            evt.Skip()
        finally:
            self._webBrowseDialog = None
            try:
                gui.mainFrame.postPopup()
            except Exception:
                pass

    def _onVoiceProfilesDialogClosed(self, evt):
        try:
            evt.Skip()
        finally:
            self._voiceProfilesDialog = None
            try:
                gui.mainFrame.postPopup()
            except Exception:
                pass

    def _onDialogClosed(self, evt):
        try:
            evt.Skip()
        finally:
            self._settingsDialog = None
            try:
                gui.mainFrame.postPopup()
            except Exception:
                pass

    def _openSettings(self):
        try:
            if self._settingsDialog:
                try:
                    self._settingsDialog.Raise()
                    self._settingsDialog.SetFocus()
                    return
                except Exception:
                    self._settingsDialog = None

            gui.mainFrame.prePopup()
            dlg = ClassicSpeechDialog(gui.mainFrame)
            dlg._popupActive = True
            dlg.Bind(wx.EVT_CLOSE, self._onDialogClosed)
            self._settingsDialog = dlg
            dlg.Show()

        except Exception as e:
            log.error(f"Failed to open ClassicSpeech settings: {e}", exc_info=True)
            try:
                gui.mainFrame.postPopup()
            except Exception:
                pass

    def _openWebBrowseSettings(self):
        try:
            if self._webBrowseDialog:
                try:
                    self._webBrowseDialog.Raise()
                    self._webBrowseDialog.SetFocus()
                    return
                except Exception:
                    self._webBrowseDialog = None

            gui.mainFrame.prePopup()
            dlg = WebBrowseSettingsDialog(gui.mainFrame)
            dlg._popupActive = True
            dlg.Bind(wx.EVT_CLOSE, self._onWebBrowseDialogClosed)
            self._webBrowseDialog = dlg
            dlg.Show()

        except Exception as e:
            log.error(f"Failed to open ClassicSpeech web/browse settings: {e}", exc_info=True)
            try:
                gui.mainFrame.postPopup()
            except Exception:
                pass

    def _openVoiceProfiles(self):
        try:
            if self._voiceProfilesDialog:
                try:
                    self._voiceProfilesDialog.Raise()
                    self._voiceProfilesDialog.SetFocus()
                    return
                except Exception:
                    self._voiceProfilesDialog = None

            gui.mainFrame.prePopup()
            dlg = VoiceProfilesDialog(gui.mainFrame)
            dlg._popupActive = True
            dlg.Bind(wx.EVT_CLOSE, self._onVoiceProfilesDialogClosed)
            self._voiceProfilesDialog = dlg
            dlg.Show()

        except Exception as e:
            log.error(f"Failed to open ClassicSpeech Voice Profiles: {e}", exc_info=True)
            try:
                gui.mainFrame.postPopup()
            except Exception:
                pass
