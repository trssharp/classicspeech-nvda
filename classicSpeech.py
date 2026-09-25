from ._speech_core.localization import _

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
import speech
from speech import shortcutKeys as nvdaShortcutKeys
import braille
import wx
import functools
import os
import inputCore

from speech.commands import BreakCommand

from ._speech_core.dialog_helpers import (
    SOURCE_APPEARANCE,
    focused_button_default_status,
    query_default_button,
    remember_default_button_for_focus,
    reset_default_button_cache,
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
    wrap_mouse_sequence,
    wrap_review_literal_sequence,
    wrap_system_notification_sequence,
)
from ._speech_core import nvda_settings_backup
from ._speech_core import settings_file, compact_toasts
from ._speech_core.key_labels import apply_key_labels_live, get_key_label_config, get_key_label_runtime
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
from ._speech_core.settings.config_core import _forget_normalized_section
from ._speech_core.settings.profile_config import nvda_settings_set_by_saved_settings
from ._speech_core.settings.web import WebBrowseSettingsDialog
from ._speech_core.settings.voice_profiles_dialog import VoiceProfilesDialog
from ._speech_core.schemes import store as scheme_store
from ._speech_core.cancelable import strip_cancelable
from ._speech_core.history import SpeechHistoryBuffer, consume_history_native_passthrough
from ._speech_core.history_viewer import show_history_dialog, is_history_list_focus
from ._speech_core.interrupt_control import SpeechInterruptController
from ._speech_core import message_priority
from ._speech_core.message_priority import join_message_ends, speak_message, split_message_ends
from ._speech_core.update_check import UpdateChecker
from ._speech_core.user_guide import open_user_guide
from ._speech_core.processors.web.summary import build_summary, format_summary_with_document_title
from ._speech_core.processors.web.lifecycle import WebPageLifecycle
from ._speech_core.processors.web.page_entry import (
    install as install_page_orientation,
    restore as restore_page_orientation,
)
from ._speech_core.processors.web.heading_continuity import (
    install as install_heading_continuity,
)
from ._speech_core.processors.web.mode_indication import (
    install as install_mode_indication,
    restore as restore_mode_indication,
)
from ._speech_core.settings.web.mode_indication_config import (
    get_custom_browse_mode_message,
    get_custom_focus_mode_message,
)
from ._speech_core.settings.web.summary_config import (
    get_included_element_types,
    get_include_document_title,
)
from ._speech_core.schemes import runtime as scheme_runtime
from ._speech_core.schemes import nvda_sounds
from ._speech_core.schemes.markers import LabelMarker, has_markers, has_range_marks, strip_markers
from ._speech_core.schemes.tagging import SchemeTagger

log = logHandler.log


from ._speech_core.plugin_config import (
    _CLASSIC_SPEECH_SPEC,
    _getClassicSpeechSection,
    _initClassicSpeechConfig,
)


class GlobalPlugin(globalPluginHandler.GlobalPlugin):

    __gestures = {
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

        hadSettings = _initClassicSpeechConfig()

        section = _getClassicSpeechSection()
        defaultProfile = section.get("defaultProfile", "Beginner")

        self.processor = CoreUISpeechProcessor()
        self.processor.set_profile(defaultProfile)
        self._record_nvda_settings_changed_earlier(hadSettings)
        self._install_config_reset_handler()
        self.history = SpeechHistoryBuffer()
        self._settingsDialog = None
        self._webBrowseDialog = None
        self._voiceProfilesDialog = None
        self._schemesDialog = None
        self._classicSpeechMenu = None
        self._classicSpeechMenuItem = None
        self._classicSpeechPreferencesMenu = None
        self._classicSpeechMenuItems = []
        self._menuHints = MenuHintHelper()
        self._keyLabelRuntime = get_key_label_runtime()
        self._interruptController = SpeechInterruptController()
        # Before the speech hook: the interrupt controller wraps speech
        # cancellation around this one, as it did around NVDA's own.
        message_priority.install()
        self._install_shortcut_speaker_bypass()
        self._install_keyboard_entry_profile_route()
        self._install_mouse_pointer_profile_route()
        self._install_windows_toast_system_route()
        self._toastArrival = compact_toasts.ToastArrivalRuntime(
            lambda: bool(getattr(self, "_speechHookRegistered", False)), log
        )
        self._toastArrival.install()
        self._install_system_notification_profile_routes()
        self._install_configuration_save_revert_system_routes()
        self._install_remote_speech_compatibility()
        self._schemeTagger = SchemeTagger(
            is_active=lambda: bool(getattr(self, "_speechHookRegistered", False))
        )
        self._install_speech_schemes()
        self._install_nvda_sounds()
        self._pendingContainerSequence = None
        self._pendingContainerFlush = None
        self._flushingPendingContainer = False
        self._rawHistorySequenceOverride = None
        self._pendingReviewMovementBoundary = None
        self._pendingReviewMovementBoundaryRaw = None
        self._speechHookRegistered = False
        self._webPageLifecycle = WebPageLifecycle(
            self._report_page_summary_for_document, self._log_web_page_lifecycle
        )
        self._pageOrientationRoutes = install_page_orientation(self)
        self._headingContinuityRuntime = install_heading_continuity(log)
        self._modeIndicationRoute = install_mode_indication(
            self,
            get_browse_mode_message=get_custom_browse_mode_message,
            get_focus_mode_message=get_custom_focus_mode_message,
            speak_message=speak_message,
        )

        self._installClassicSpeechMenu()
        self.set_speech_hook_enabled(get_speech_hook_enabled())
        self._updateChecker = UpdateChecker()
        try:
            self._updateChecker.schedule_automatic_check()
        except Exception:
            log.debug("ClassicSpeech: could not schedule the automatic update check", exc_info=True)

        log.info(f"ClassicSpeech loaded (profile: {defaultProfile}, hook: {self._speechHookRegistered})")

    def terminate(self):
        self._remove_config_reset_handler()
        checker = getattr(self, "_updateChecker", None)
        if checker is not None:
            checker.stop()
        self._get_web_page_lifecycle().cancel()
        restore_page_orientation(self, getattr(self, "_pageOrientationRoutes", ()))
        self._pageOrientationRoutes = []
        restore_mode_indication(self, getattr(self, "_modeIndicationRoute", None))
        self._modeIndicationRoute = None
        headingContinuityRuntime = getattr(self, "_headingContinuityRuntime", None)
        if headingContinuityRuntime is not None:
            headingContinuityRuntime.restore()
        self._headingContinuityRuntime = None
        self._unregister_speech_hook()
        self._uninstall_speech_schemes()
        self._uninstall_nvda_sounds()
        self._restore_remote_speech_compatibility()
        if getattr(self, "_toastArrival", None) is not None:
            self._toastArrival.restore()
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
            message_priority.uninstall()
        except Exception:
            log.debug("ClassicSpeech: failed to remove message priority", exc_info=True)
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
        # Let go of the dialog objects the default-button lookup remembers.
        reset_default_button_cache()
        self._removeClassicSpeechMenu()
        log.info("ClassicSpeech unloaded")


    def _log_web_page_lifecycle(self, message):
        """Keep automatic lifecycle failures diagnostic without plugin coupling."""
        log.debug(f"ClassicSpeech: {message}", exc_info=True)

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
                speak_message(message)
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
            self._rawHistorySequenceOverride = None
            self._pendingReviewMovementBoundary = None
            self._pendingReviewMovementBoundaryRaw = None


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

    def _focus_signature(self):
        """Identify the focused object well enough to notice it has moved.

        NVDA can build a new object for the same control, so this describes what
        the object is rather than which instance it is, as NVDA's own
        ``FocusLossCancellableSpeechCommand`` does when it compares objects.
        """
        try:
            focus = api.getFocusObject()
        except Exception:
            return None
        if focus is None:
            return None
        try:
            role = getattr(focus, "role", None)
            return (
                getattr(focus, "windowHandle", None),
                getattr(focus, "processID", None),
                getattr(focus, "IAccessibleChildID", None),
                str(getattr(role, "name", role) or ""),
                self._norm_text(getattr(focus, "name", "")),
            )
        except Exception:
            return None

    def _sequence_is_focus_name(self, sequence):
        """Return True when the sequence is only the focused object's own name.

        A tree view item named "list" or "tree view" is an item, not the
        container that holds it. Holding it would delay the item a user just
        arrowed to, and merging it into the next announcement would move it onto
        another item. The Speech and Sound Schemes tree is full of such names.
        """
        strings = self._string_tokens(sequence)
        if len(strings) != 1:
            return False
        try:
            focus = api.getFocusObject()
            name = self._norm_text(getattr(focus, "name", "")) if focus else ""
        except Exception:
            return False
        return bool(name) and self._norm_text(strings[0]) == name

    def _is_mergeable_container_sequence(self, sequence):
        strings = self._string_tokens(sequence)
        if not strings:
            return False
        if any(self._looks_like_position_text(s) for s in strings):
            return False
        if not any(self._looks_like_container_role_text(s) for s in strings):
            return False
        if self._sequence_is_focus_name(sequence):
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
        if isinstance(pending, dict) and pending.get("focus") != self._focus_signature():
            # The focus moved on while the container was held, so this fragment
            # describes something the user has already left. Speaking it now
            # would talk over the new object, and NVDA would drop the whole
            # utterance - and everything queued before it - as expired focus
            # speech, silencing the announcement the user is waiting for.
            log.debug("ClassicSpeech: dropped a held container after the focus moved")
            return
        try:
            self._flushingPendingContainer = True
            raw = pending.get("raw") if isinstance(pending, dict) else pending
            if isinstance(pending, dict):
                self._rawHistorySequenceOverride = list(pending.get("historyRaw") or [])
            speech.speak(list(raw or []))
        except Exception:
            log.debug("ClassicSpeech: failed to flush pending container sequence", exc_info=True)
        finally:
            self._rawHistorySequenceOverride = None
            self._flushingPendingContainer = False

    def _hold_container_sequence(self, sequence, historyRaw):
        self._cancel_pending_container_flush()
        # NVDA's focus cancellation markers describe the utterance NVDA built.
        # This fragment is spoken again later, or inside another object's
        # announcement, so it travels without them.
        held = strip_cancelable(sequence)
        core, hotkey = self._split_container_hotkey_tail(held)
        self._pendingContainerSequence = {
            "core": core,
            "hotkey": hotkey,
            "raw": list(held),
            "historyRaw": list(historyRaw),
            "focus": self._focus_signature(),
        }
        log.debug(f"ClassicSpeech: holding split container speech briefly: {sequence}")
        try:
            self._pendingContainerFlush = wx.CallLater(50, self._flush_pending_container_sequence)
        except Exception:
            self._pendingContainerFlush = None
        return []

    def _consume_pending_container_for(self, sequence, historyRaw):
        pending = getattr(self, "_pendingContainerSequence", None)
        if not pending:
            return None
        if pending.get("focus") != self._focus_signature():
            # Held for a focus the user has already left; it is not this
            # object's container and must not be spoken with it.
            self._cancel_pending_container_flush()
            self._pendingContainerSequence = None
            log.debug("ClassicSpeech: discarded a held container from an earlier focus")
            return None
        if not self._is_mergeable_item_followup(sequence):
            # The held container was not followed by an item of that container
            # (for example Chrome's "tool bar" before the address bar edit
            # field). Speak it now as its own native utterance, queued ahead of
            # the current sequence. Merging the two would make the classifier
            # read the edit field's name, role and contents as values of the
            # tool bar and drop them.
            self._cancel_pending_container_flush()
            self._flush_pending_container_sequence()
            return None
        self._cancel_pending_container_flush()
        self._pendingContainerSequence = None
        mergedHistoryRaw = list(pending.get("historyRaw") or []) + list(historyRaw)
        merged = list(pending.get("core") or pending.get("raw") or [])
        if merged and isinstance(merged[-1], str):
            merged.append(BreakCommand(time=80))
        merged.extend(list(sequence))
        if pending.get("hotkey"):
            merged.append(BreakCommand(time=80))
            merged.extend(list(pending.get("hotkey") or []))
        log.debug(f"ClassicSpeech: merged generic container/item sequence: {pending.get('raw')} -> {merged}")
        return merged, mergedHistoryRaw

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

    def _record_history(self, sequence, emittedSequence=None):
        try:
            if emittedSequence is not None and not self._sequence_has_text(emittedSequence):
                return
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

    def _install_speech_schemes(self):
        """Mark scheme items in NVDA speech and reset say all state on cancel."""
        try:
            # Give every scheme its folder, moving schemes an earlier version kept in the config.
            scheme_store.prepare_scheme_folders()
        except Exception:
            log.exception("ClassicSpeech: failed to prepare the Speech and Sound Schemes folder")
        try:
            self._schemeTagger.install()
        except Exception:
            log.exception("ClassicSpeech: failed to install Speech and Sound Schemes")
        try:
            canceled = getattr(speech.extensions, "speechCanceled", None)
            if canceled is not None:
                canceled.register(scheme_runtime.reset_carried_state)
                self._schemeSpeechCanceled = canceled
        except Exception:
            log.debug("ClassicSpeech: speech cancel notification unavailable", exc_info=True)

    def _uninstall_speech_schemes(self):
        tagger = getattr(self, "_schemeTagger", None)
        if tagger is not None:
            try:
                tagger.uninstall()
            except Exception:
                log.debug("ClassicSpeech: failed to remove Speech and Sound Schemes", exc_info=True)
        canceled = getattr(self, "_schemeSpeechCanceled", None)
        if canceled is not None:
            try:
                canceled.unregister(scheme_runtime.reset_carried_state)
            except Exception:
                pass
            self._schemeSpeechCanceled = None
        scheme_runtime.reset_carried_state()

    def _install_nvda_sounds(self):
        """Play the active scheme's sounds instead of NVDA's own sounds."""
        try:
            nvda_sounds.install()
        except Exception:
            log.exception("ClassicSpeech: failed to install the scheme's NVDA sounds")
        try:
            nvda_sounds.handle_nvda_start()
        except Exception:
            log.exception("ClassicSpeech: failed to handle NVDA's start sound")
        self._windowsSessionApp = None
        try:
            app = wx.GetApp()
            app.Bind(wx.EVT_END_SESSION, self._onWindowsSessionEnd)
            self._windowsSessionApp = app
        except Exception:
            log.debug("ClassicSpeech: Windows session end is unavailable", exc_info=True)

    def _onWindowsSessionEnd(self, evt):
        try:
            nvda_sounds.handle_windows_session_end()
        except Exception:
            log.debug("ClassicSpeech: could not play the exit sound at sign-out", exc_info=True)
        finally:
            # NVDA's own handler saves its configuration.
            evt.Skip()

    def _nvda_is_exiting(self):
        try:
            import core

            return bool(getattr(core, "_hasShutdownBeenTriggered", False))
        except Exception:
            return False

    def _addon_is_leaving(self):
        """True when NVDA exits to disable or remove ClassicSpeech, not to update it."""
        try:
            import addonHandler

            addon = addonHandler.getCodeAddon()
        except Exception:
            return False
        if getattr(addon, "isPendingDisable", False):
            return True
        if getattr(addon, "isPendingRemove", False):
            # An update also removes the old copy; the new one keeps the sounds.
            try:
                pending = os.path.join(os.path.dirname(addon.path), addon.name + ".pendingInstall")
                return not os.path.isdir(pending)
            except Exception:
                return True
        return False

    def _uninstall_nvda_sounds(self):
        app = getattr(self, "_windowsSessionApp", None)
        if app is not None:
            try:
                app.Unbind(wx.EVT_END_SESSION, handler=self._onWindowsSessionEnd)
            except Exception:
                pass
        self._windowsSessionApp = None
        exiting = self._nvda_is_exiting()
        if exiting:
            try:
                nvda_sounds.handle_nvda_exit(addon_leaving=self._addon_is_leaving())
            except Exception:
                log.exception("ClassicSpeech: failed to handle NVDA's exit sound")
        try:
            nvda_sounds.uninstall(nvda_exiting=exiting)
        except Exception:
            log.debug("ClassicSpeech: failed to remove the scheme's NVDA sounds", exc_info=True)

    def _filterSpeechSequence(self, speechSequence):
        """ClassicSpeech speech filter, followed by Speech and Sound Schemes.

        Scheme markers added while NVDA generated the speech are always
        converted or removed here, so they never reach other filters or the
        synthesizer.

        A ClassicSpeech message given priority ends with a callback that
        tells ClassicSpeech it has been spoken. It is set aside while the
        message is processed, so the message is processed exactly as without
        priority, and put back right after the message's text.
        """
        speechSequence, messageEnds = split_message_ends(speechSequence)
        output = self._filterSpeechSequenceCore(speechSequence)
        try:
            output = scheme_runtime.apply_schemes(output)
        except Exception:
            log.exception("ClassicSpeech: Speech and Sound Schemes failed")
            try:
                output = strip_markers(output)
            except Exception:
                pass
        return join_message_ends(output, messageEnds)

    def _filterSpeechSequenceCore(self, speechSequence):
        try:
            self._debug_log(f"filter input: {speechSequence}")
            # History replay/copy confirmations are already final flattened text.
            # Speak them natively so Shift+F11, Shift+F12, Ctrl+Shift+F11,
            # Ctrl+Shift+F12, and F12 cannot be reclassified into silence.
            # Do not record these here; SpeechHistoryBuffer suppresses its own
            # replay/copy speech so history does not recursively record itself.
            if consume_history_native_passthrough():
                return speechSequence

            rawHistorySequence = getattr(self, "_rawHistorySequenceOverride", None)
            if rawHistorySequence is None:
                rawHistorySequence = list(speechSequence)
            else:
                rawHistorySequence = list(rawHistorySequence)
                self._rawHistorySequenceOverride = None

            # Input help is a native diagnostic mode. Do not tokenize it, do not
            # extract/apply hotkeys, and do not let a previously extracted hotkey
            # leak into the following input-help description.
            if self._is_input_help_active():
                self._clear_hotkey_carryover()
                self._record_history(rawHistorySequence, speechSequence)
                self._debug_log("bypass: input help")
                return speechSequence

            # Explicit native pass-through paths should stay completely raw.
            # History is intentionally recorded before returning so the history
            # buffer acts like a recorder at the speech-hook boundary rather
            # than a feature hidden behind the formatter.
            if getattr(self.processor, "_bypass_next_sequence", False):
                self.processor._bypass_next_sequence = False
                self._clear_hotkey_carryover()
                self._record_history(rawHistorySequence, speechSequence)
                self._debug_log("bypass: requested native pass-through")
                return speechSequence

            # ``speech.speakTypedCharacters`` is NVDA's shared typed-character
            # and typed-word echo entry point. Keep its text native; add only
            # Keyboard profile prosody and do not invoke hotkey/text processing.
            if is_keyboard_entry_profile_routing_active():
                self._clear_hotkey_carryover()
                output = wrap_keyboard_entry_sequence(speechSequence)
                self._record_history(rawHistorySequence, output)
                self._debug_log("typed keyboard/braille entry uses Keyboard profile")
                if get_debug_logging_enabled():
                    self._debug_log(f"filter output: {output}")
                return output

            if is_mouse_pointer_profile_routing_active():
                self._clear_hotkey_carryover()
                output = wrap_mouse_sequence(speechSequence)
                self._record_history(rawHistorySequence, output)
                self._debug_log("mouse pointer feedback uses Mouse profile")
                if get_debug_logging_enabled():
                    self._debug_log(f"filter output: {output}")
                return output

            if is_system_notification_profile_routing_active() or self._is_system_voice_script_active():
                self._clear_hotkey_carryover()
                # Text-only toast presentation; retain existing routing priority,
                # raw history, scheme processing and message completion commands.
                output = wrap_system_notification_sequence(compact_toasts.transform(speechSequence))
                self._record_history(rawHistorySequence, output)
                self._debug_log("scoped System notification uses System profile")
                if get_debug_logging_enabled():
                    self._debug_log(f"filter output: {output}")
                return output

            if self._is_review_cursor_status_script_active():
                self._clear_hotkey_carryover()
                output = wrap_review_literal_sequence(speechSequence)
                self._record_history(rawHistorySequence, output)
                self._debug_log("review cursor status uses Review profile")
                if get_debug_logging_enabled():
                    self._debug_log(f"filter output: {output}")
                return output

            self._apply_text_processing(speechSequence)

            isObjectNavigation = self._is_object_navigation_script_active()
            isReviewCursorLiteral = self._is_review_cursor_literal_script_active()
            if not isReviewCursorLiteral and getattr(self, "_pendingReviewMovementBoundary", None):
                self._pendingReviewMovementBoundary = None
                self._pendingReviewMovementBoundaryRaw = None
                self._debug_log("discarded incomplete Review movement boundary")
            if self._is_review_movement_boundary_sequence(speechSequence):
                self._pendingReviewMovementBoundary = list(speechSequence)
                self._pendingReviewMovementBoundaryRaw = list(rawHistorySequence)
                self._debug_log("held Review movement boundary for following Review text")
                return []
            if isReviewCursorLiteral:
                pendingBoundary = getattr(self, "_pendingReviewMovementBoundary", None)
                if pendingBoundary and self._sequence_has_text(speechSequence):
                    speechSequence = list(pendingBoundary) + list(speechSequence)
                    rawHistorySequence = list(
                        getattr(self, "_pendingReviewMovementBoundaryRaw", None) or []
                    ) + list(rawHistorySequence)
                    self._pendingReviewMovementBoundary = None
                    self._pendingReviewMovementBoundaryRaw = None
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
                self._record_history(rawHistorySequence, output)
                self._debug_log("object navigation native sequence uses Review profile")
                if get_debug_logging_enabled():
                    self._debug_log(f"filter output: {output}")
                return output

            # A real Review Cursor reading script owns every one of its native
            # speech sequences, including spelling fragments with command
            # boundaries. Preserve the sequence intact and add only the Review
            # profile commands around its spoken text.
            if isReviewCursorLiteral:
                self._clear_hotkey_carryover()
                output = wrap_review_literal_sequence(speechSequence)
                self._record_history(rawHistorySequence, output)
                self._debug_log("review cursor sequence uses Review profile")
                if get_debug_logging_enabled():
                    self._debug_log(f"filter output: {output}")
                return output

            # Speech for actual history entries inside our own history dialog is
            # already final user-facing text. Bypass only list-item navigation;
            # let the list control and Copy/Clear/Close buttons use normal
            # ClassicSpeech verbosity processing. Record it so the recorder sees
            # native list navigation too, while replay suppression above prevents
            # recursive history entries.
            if is_history_list_focus(speechSequence):
                self._clear_hotkey_carryover()
                self._record_history(rawHistorySequence, speechSequence)
                self._debug_log("bypass: speech history list focus")
                return speechSequence

            # A Speech and Sound Scheme item speaks a run of this document text:
            # NVDA marked where the formatting or the element begins and ends
            # while it built the sequence inside getTextInfoSpeech (caret,
            # review cursor, browse mode, quick navigation, Say All). Merging or
            # reordering the fragments would move the item's voice and sound
            # onto the wrong words, so keep NVDA's own text exactly as it is.
            # Sequences no scheme item speaks still take the paths below.
            if has_range_marks(speechSequence):
                self._clear_hotkey_carryover()
                output = (
                    wrap_review_literal_sequence(speechSequence)
                    if isReviewCursorLiteral
                    else speechSequence
                )
                self._record_history(rawHistorySequence, output)
                self._debug_log("bypass: NVDA text speech carrying scheme marks")
                if get_debug_logging_enabled():
                    self._debug_log(f"filter output: {output}")
                return output

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
                mergedResult = self._consume_pending_container_for(speechSequence, rawHistorySequence)
                if mergedResult is not None:
                    speechSequence, rawHistorySequence = mergedResult
                elif self._is_mergeable_container_sequence(speechSequence):
                    return self._hold_container_sequence(speechSequence, rawHistorySequence)

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
                self._record_history(rawHistorySequence, output)
                self._debug_log(
                    "review cursor literal sequence uses Review profile"
                    if isReviewCursorLiteral
                    else (
                        "bypass: literal review/caret text after text processing "
                        f"(script={self._current_speech_script_name()}): {speechSequence}"
                    ),
                )
                if get_debug_logging_enabled():
                    self._debug_log(f"filter output: {output}")
                return output

            # NVDA's own role/state label markers are dropped before semantic
            # processing: the token editor may reorder or rename those words.
            # The formatter marks the final role and state tokens again.
            if has_markers(speechSequence):
                speechSequence[:] = [item for item in speechSequence if not isinstance(item, LabelMarker)]

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
                        self._record_history(rawHistorySequence, speechSequence)
                        return speechSequence
                except Exception:
                    pass

            self._record_history(rawHistorySequence, output)
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
            generalItem = classicSpeechMenu.Append(wx.ID_ANY, _("General Settings..."))
            webItem = classicSpeechMenu.Append(wx.ID_ANY, _("Web / Browse Mode Settings..."))
            voiceProfilesItem = classicSpeechMenu.Append(wx.ID_ANY, _("Voice Profiles..."))
            schemesItem = classicSpeechMenu.Append(wx.ID_ANY, _("Speech and Sound Schemes..."))
            classicSpeechMenu.AppendSeparator()
            updateItem = classicSpeechMenu.Append(wx.ID_ANY, _("Check for Updates..."))
            resetItem = classicSpeechMenu.Append(wx.ID_ANY, _("Reset All ClassicSpeech Settings..."))
            submenuItem = preferencesMenu.AppendSubMenu(classicSpeechMenu, _("ClassicSpeech"))
            sysTrayIcon.Bind(wx.EVT_MENU, self.onClassicSpeechGeneralSettingsMenu, generalItem)
            sysTrayIcon.Bind(wx.EVT_MENU, self.onClassicSpeechWebBrowseSettingsMenu, webItem)
            sysTrayIcon.Bind(wx.EVT_MENU, self.onClassicSpeechVoiceProfilesMenu, voiceProfilesItem)
            sysTrayIcon.Bind(wx.EVT_MENU, self.onClassicSpeechSchemesMenu, schemesItem)
            sysTrayIcon.Bind(wx.EVT_MENU, self.onClassicSpeechUpdateMenu, updateItem)
            sysTrayIcon.Bind(wx.EVT_MENU, self.onClassicSpeechResetMenu, resetItem)
            self._classicSpeechPreferencesMenu = preferencesMenu
            self._classicSpeechMenu = classicSpeechMenu
            self._classicSpeechMenuItem = submenuItem
            self._classicSpeechMenuItems = [
                generalItem, webItem, voiceProfilesItem, schemesItem, updateItem, resetItem,
            ]
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

    def onClassicSpeechSchemesMenu(self, evt):
        queueHandler.queueFunction(queueHandler.eventQueue, self._openSpeechSchemes)

    def _outside_nvda_core(self, function):
        """Run ``function`` from wx's event loop, never inside NVDA's core queue.

        Scripts and ``queueHandler`` functions run inside NVDA's core pump. A
        modal dialog opened there, such as a Yes/No message box, stops the pump,
        so NVDA freezes and can't even speak the dialog. NVDA opens modal dialogs
        for scripts the same way (``gui.runScriptModalDialog`` used wx.CallAfter).
        """
        wx.CallAfter(function)

    def onClassicSpeechUpdateMenu(self, evt):
        self._outside_nvda_core(self._checkForUpdates)

    def onClassicSpeechResetMenu(self, evt):
        self._outside_nvda_core(self._confirmResetAllSettings)

    @scriptHandler.script(
        description=_("Opens ClassicSpeech settings"),
        category=_("ClassicSpeech"),
    )
    def script_openClassicSpeechSettings(self, gesture):
        queueHandler.queueFunction(queueHandler.eventQueue, self._openSettings)

    @scriptHandler.script(
        description=_("Opens ClassicSpeech Web / Browse Mode Settings"),
        category=_("ClassicSpeech"),
    )
    def script_openClassicSpeechWebBrowseSettings(self, gesture):
        queueHandler.queueFunction(queueHandler.eventQueue, self._openWebBrowseSettings)

    @scriptHandler.script(
        description=_("Opens ClassicSpeech Voice Profiles"),
        category=_("ClassicSpeech"),
    )
    def script_openClassicSpeechVoiceProfiles(self, gesture):
        queueHandler.queueFunction(queueHandler.eventQueue, self._openVoiceProfiles)

    @scriptHandler.script(
        description=_("Opens ClassicSpeech Speech and Sound Schemes"),
        category=_("ClassicSpeech"),
    )
    def script_openClassicSpeechSchemes(self, gesture):
        queueHandler.queueFunction(queueHandler.eventQueue, self._openSpeechSchemes)

    @scriptHandler.script(
        description=_("Opens the ClassicSpeech user guide"),
        category=_("ClassicSpeech"),
    )
    def script_openClassicSpeechUserGuide(self, gesture):
        try:
            open_user_guide()
        except Exception:
            log.exception("ClassicSpeech: opening the user guide failed")

    @scriptHandler.script(
        description=_("Resets all ClassicSpeech settings and restores the NVDA settings it changed"),
        category=_("ClassicSpeech"),
    )
    def script_resetAllClassicSpeechSettings(self, gesture):
        self._outside_nvda_core(self._confirmResetAllSettings)

    @scriptHandler.script(
        description=_("Checks for ClassicSpeech updates"),
        category=_("ClassicSpeech"),
    )
    def script_checkForClassicSpeechUpdates(self, gesture):
        self._outside_nvda_core(self._checkForUpdates)

    def _checkForUpdates(self):
        if self._is_secure_context():
            return
        checker = getattr(self, "_updateChecker", None)
        if checker is None:
            checker = self._updateChecker = UpdateChecker()
        try:
            checker.check(manual=True)
        except Exception:
            log.exception("ClassicSpeech: update check failed")

    @scriptHandler.script(
        description=_("Turns ClassicSpeech speech and sound schemes on or off"),
        category=_("ClassicSpeech"),
    )
    def script_toggleSpeechSchemes(self, gesture):
        try:
            enabled = not bool(scheme_store.runtime_data().data and scheme_store.runtime_data().data.get("enabled"))
            scheme_store.set_schemes_enabled(enabled)
            speak_message(_("Speech and sound schemes on") if enabled else _("Speech and sound schemes off"))
        except Exception:
            log.exception("ClassicSpeech: toggling speech and sound schemes failed")

    @scriptHandler.script(
        description=_("Switches to the next ClassicSpeech speech and sound scheme"),
        category=_("ClassicSpeech"),
    )
    def script_nextSpeechScheme(self, gesture):
        try:
            name = scheme_store.cycle_active_scheme()
            speak_message(_("Scheme {name}").format(name=name))
        except Exception:
            log.exception("ClassicSpeech: switching speech and sound schemes failed")


    def _report_page_summary_for_document(self, document):
        """Speak one Page Summary, optionally prefixed by the document name."""
        summary = build_summary(document, get_included_element_types())
        document_title = None
        if get_include_document_title():
            try:
                document_title = getattr(getattr(document, "rootNVDAObject", None), "name", None)
            except Exception:
                log.debugWarning("ClassicSpeech: unable to read Page Summary document title", exc_info=True)
        speak_message(format_summary_with_document_title(document_title, summary))

    def _get_web_page_lifecycle(self):
        """Return the automatic web lifecycle, including test-double fallback."""
        lifecycle = getattr(self, "_webPageLifecycle", None)
        if lifecycle is None:
            lifecycle = WebPageLifecycle(
                self._report_page_summary_for_document, self._log_web_page_lifecycle
            )
            self._webPageLifecycle = lifecycle
        return lifecycle


    @property
    def _automaticSummaryPending(self):
        return self._get_web_page_lifecycle().automatic_summary_pending

    @property
    def _automaticSummaryReported(self):
        return self._get_web_page_lifecycle().automatic_summary_reported

    def _report_page_orientation_for_document(self, document, on_summary=None, on_fallback=None):
        """Thin Page Entry facade; lifecycle owns presentation state and timing."""
        return self._get_web_page_lifecycle().report_page_orientation(
            document, on_summary, on_fallback
        )

    def event_gainFocus(self, obj, nextHandler):
        """Keep NVDA's native focus event first, exactly once."""
        nextHandler()
        self._get_web_page_lifecycle().handle_focus_change(obj)
        remember_default_button_for_focus(obj)

    def event_documentLoadComplete(self, obj, nextHandler):
        """Keep NVDA's native load event first, exactly once."""
        nextHandler()
        self._get_web_page_lifecycle().handle_document_load_complete(obj)

    @scriptHandler.script(
        description=_("Reports selected Browse Mode element counts for the current page"),
        category=_("ClassicSpeech"),
    )
    def script_pageSummary(self, gesture):
        try:
            focus = api.getFocusObject()
            document = getattr(focus, "treeInterceptor", None)
            if document is None or not hasattr(document, "_iterNodesByType"):
                speak_message(_("Page summary is not available here."))
                return
            self._report_page_summary_for_document(document)
        except Exception:
            log.exception("ClassicSpeech page summary failed")
            speak_message(_("Page summary is not available here."))


    @scriptHandler.script(
        description=_("Speaks the current object. Press twice quickly to spell and copy it"),
        category=_("ClassicSpeech"),
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
                speak_message(_("No object"))
                return

            repeatCount = scriptHandler.getLastScriptRepeatCount()
            if repeatCount == 0:
                self.processor.speak_query_object(focus)
                return

            text = self.processor.get_query_object_text(focus)
            if not text:
                speak_message(_("No object"))
                return

            speech.speakSpelling(text)
            api.copyToClip(text, notify=False)
        except Exception as e:
            log.error(f"ClassicSpeech query object failed: {e}", exc_info=True)
            speak_message(_("No focus"))
    @scriptHandler.script(
        description=_("Reviews the previous ClassicSpeech history item"),
        category=_("ClassicSpeech"),
    )
    def script_previousSpeechHistory(self, gesture):
        self.history.speak_previous()

    @scriptHandler.script(
        description=_("Reviews the next ClassicSpeech history item"),
        category=_("ClassicSpeech"),
    )
    def script_nextSpeechHistory(self, gesture):
        self.history.speak_next()

    @scriptHandler.script(
        description=_("Moves to the oldest ClassicSpeech history item"),
        category=_("ClassicSpeech"),
    )
    def script_bottomSpeechHistory(self, gesture):
        self.history.speak_bottom()

    @scriptHandler.script(
        description=_("Moves to the newest ClassicSpeech history item"),
        category=_("ClassicSpeech"),
    )
    def script_topSpeechHistory(self, gesture):
        self.history.speak_top()

    @scriptHandler.script(
        description=_("Copies the current ClassicSpeech history item to the clipboard"),
        category=_("ClassicSpeech"),
    )
    def script_copySpeechHistory(self, gesture):
        self.history.copy_current()

    @scriptHandler.script(
        description=_("Opens the ClassicSpeech history dialog"),
        category=_("ClassicSpeech"),
    )
    def script_openSpeechHistory(self, gesture):
        try:
            show_history_dialog(self.history)
        except Exception as e:
            log.error(f"Failed to open ClassicSpeech history: {e}", exc_info=True)
            speak_message(_("Could not open speech history"))


    def _getDefaultButton(self):
        # An explicit NVDA+E query always looks again; focus speech keeps using
        # the dialog cache, including a recent "no default button" result.
        return query_default_button(api.getFocusObject())

    def _getFocusedButtonDefaultStatus(self):
        focus = api.getFocusObject()
        return focus, focused_button_default_status(focus)

    @staticmethod
    def _defaultButtonMessage(query):
        button = query.button
        if button is None:
            if query.screenCurtainBlocked:
                # Translators: NVDA+E found no default button, and could not
                # look at the dialog's buttons while NVDA's Screen Curtain
                # hides the screen.
                return _(
                    "No default button found. Turn off Screen Curtain so ClassicSpeech can check how the buttons look."
                )
            return _("No default button")
        # A button can have no label, such as one that only shows a picture.
        name = button.name or _("unknown")
        if button.source == SOURCE_APPEARANCE:
            # Translators: NVDA+E names the dialog's default button, found by
            # how it looks on screen (its color or border), because the
            # application does not report it.
            return _("Default button {name}, by appearance").format(name=name)
        if not button.certain:
            return _("No default button")
        return _("Default button {name}").format(name=name)

    @scriptHandler.script(
        description=_("Announces the default button in the current dialog"),
        category=_("ClassicSpeech"),
    )
    def script_announceDefaultButton(self, gesture):
        try:
            # Prefer an eligible focused button; otherwise retain the dialog's
            # default detection, including the qualified appearance fallback.
            speak_message(self._defaultButtonMessage(self._getDefaultButton()))
        except Exception as e:
            log.error(f"Failed announcing default button: {e}", exc_info=True)
            speak_message(_("No default button"))

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

    # -- settings storage, reset and removal --------------------------------------

    def _record_nvda_settings_changed_earlier(self, hadSettings):
        """Record NVDA settings that an earlier ClassicSpeech changed, once.

        Those versions did not record NVDA's earlier values, so a reset puts
        NVDA's defaults back for the Object Presentation options they set.
        """
        try:
            if nvda_settings_backup.legacy_checked():
                return
            if hadSettings:
                recorded = nvda_settings_backup.record_legacy_changes(
                    nvda_settings_set_by_saved_settings(self.processor.verbosity)
                )
                if recorded:
                    log.info(f"ClassicSpeech: recorded NVDA settings set by an earlier version: {recorded}")
            else:
                nvda_settings_backup.mark_legacy_checked()
        except Exception:
            log.debug("ClassicSpeech: could not record NVDA settings set by an earlier version", exc_info=True)

    def _install_config_reset_handler(self):
        """Reload ClassicSpeech's settings file when NVDA reverts or resets its configuration."""
        self._configResetAction = None
        try:
            action = getattr(config, "post_configReset", None)
            if action is not None:
                action.register(self._onConfigReset)
                self._configResetAction = action
        except Exception:
            log.debug("ClassicSpeech: could not watch for configuration resets", exc_info=True)

    def _remove_config_reset_handler(self):
        action = getattr(self, "_configResetAction", None)
        if action is None:
            return
        try:
            action.unregister(self._onConfigReset)
        except Exception:
            pass
        self._configResetAction = None

    def _onConfigReset(self, factoryDefaults=False):
        try:
            settings_file.load_into_nvda(factory_defaults=bool(factoryDefaults))
            self._reload_settings()
        except Exception:
            log.exception("ClassicSpeech: could not reload its settings after NVDA's configuration was reset")

    def _reload_settings(self):
        """Use the ClassicSpeech settings now in NVDA's configuration, as at startup."""
        _forget_normalized_section()
        _initClassicSpeechConfig()
        section = _getClassicSpeechSection()
        verbosity = getattr(self.processor, "verbosity", None)
        if verbosity is not None and hasattr(verbosity, "load_from_config"):
            verbosity.load_from_config()
        self.processor.set_profile(section.get("defaultProfile", "Beginner"))
        try:
            apply_key_labels_live(get_key_label_config())
        except Exception:
            log.debug("ClassicSpeech: failed to reload key labels", exc_info=True)
        try:
            scheme_store.invalidate_runtime_cache()
            scheme_store.prepare_scheme_folders()
        except Exception:
            log.debug("ClassicSpeech: failed to reload Speech and Sound Schemes", exc_info=True)
        try:
            nvda_sounds.sync_start_and_exit_sounds()
        except Exception:
            log.debug("ClassicSpeech: failed to update NVDA's start and exit sounds", exc_info=True)
        self.set_speech_hook_enabled(get_speech_hook_enabled())

    def _open_settings_dialogs(self):
        dialogs = []
        for name in ("_settingsDialog", "_webBrowseDialog", "_voiceProfilesDialog", "_schemesDialog"):
            dialog = getattr(self, name, None)
            if dialog:
                dialogs.append(dialog)
        return dialogs

    def _show_message(self, message, title, style):
        """Show a message box from a command or the NVDA menu and return the answer.

        It waits for the user, so call it only through ``_outside_nvda_core``.
        """
        gui.mainFrame.prePopup()
        try:
            return wx.MessageBox(message, title, style, gui.mainFrame)
        finally:
            gui.mainFrame.postPopup()

    def _confirmResetAllSettings(self):
        if self._is_secure_context():
            return
        title = _("Reset ClassicSpeech")
        if self._open_settings_dialogs():
            self._show_message(
                _("Close the ClassicSpeech settings dialogs first, then choose Reset All ClassicSpeech Settings again."),
                title,
                wx.OK | wx.ICON_INFORMATION,
            )
            return
        answer = self._show_message(
            _(
                "Do you really want to reset all ClassicSpeech settings?\n\n"
                "This deletes every ClassicSpeech setting, voice profile and speech and sound scheme, "
                "including the sounds copied into your schemes, and puts back the NVDA settings "
                "ClassicSpeech changed. To keep your schemes or voice profiles, export them first. "
                "You can't undo a reset.\n\n"
                "NVDA saves its configuration after the reset."
            ),
            title,
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
        )
        if answer != wx.YES:
            return
        try:
            result = self.reset_all_settings()
        except Exception:
            log.exception("ClassicSpeech: reset failed")
            self._show_message(
                _("ClassicSpeech could not finish the reset. Details are in the NVDA log."),
                title,
                wx.OK | wx.ICON_ERROR,
            )
            return
        message = _(
            "ClassicSpeech settings were reset, and the NVDA settings it changed were put back. "
            "ClassicSpeech now uses its default settings. "
            "To remove ClassicSpeech, uninstall it from the Add-on Store."
        )
        if result.get("kept"):
            message += "\n\n" + _(
                "{count} NVDA settings were left as they are, because they were changed "
                "in NVDA's own settings after ClassicSpeech last changed them."
            ).format(count=len(result["kept"]))
        if result.get("notDeleted"):
            message += "\n\n" + _(
                "Some files could not be deleted. Delete this folder yourself: {folder}"
            ).format(folder=result["notDeleted"])
        self._show_message(message, title, wx.OK | wx.ICON_INFORMATION)

    def reset_all_settings(self):
        """Delete every ClassicSpeech setting and put back the NVDA settings it changed.

        ClassicSpeech keeps running from its default settings, and NVDA's
        configuration is saved, so the reset lasts even if NVDA doesn't save
        its configuration on exit.
        """
        result = nvda_settings_backup.reset_all(save=False)
        log.info(
            f"ClassicSpeech: reset all settings; restored {result['restored']}, kept {result['kept']}"
        )
        self._reload_settings()
        nvda_settings_backup.mark_legacy_checked()
        nvda_settings_backup.save_nvda_configuration()
        return result

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

    def _schemeFocusClassName(self):
        """Window class of the object in use before the dialog opened, if any."""
        for getter in (
            lambda: getattr(gui.mainFrame, "prevFocus", None),
            api.getNavigatorObject,
            api.getFocusObject,
        ):
            try:
                obj = getter()
                name = str(getattr(obj, "windowClassName", "") or "")
                if name:
                    return name
            except Exception:
                continue
        return ""

    def _onSchemesDialogDestroyed(self, evt):
        try:
            evt.Skip()
        finally:
            if evt.GetEventObject() is self._schemesDialog:
                self._schemesDialog = None
                try:
                    gui.mainFrame.postPopup()
                except Exception:
                    pass

    def _openSpeechSchemes(self):
        try:
            if self._schemesDialog:
                try:
                    self._schemesDialog.Raise()
                    self._schemesDialog.SetFocus()
                    return
                except Exception:
                    self._schemesDialog = None

            focusClassName = self._schemeFocusClassName()
            gui.mainFrame.prePopup()
            from ._speech_core.settings.schemes_dialog import SpeechSoundSchemesDialog

            dlg = SpeechSoundSchemesDialog(gui.mainFrame, focus_class_name=focusClassName)
            dlg._popupActive = True
            dlg.Bind(wx.EVT_WINDOW_DESTROY, self._onSchemesDialogDestroyed)
            self._schemesDialog = dlg
            dlg.Show()

        except Exception as e:
            log.error(f"Failed to open ClassicSpeech Speech and Sound Schemes: {e}", exc_info=True)
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
