"""Narrow Microsoft Edge UIA notification policy for ClassicSpeech.

Only exact activity IDs registered by the permanent ClassicSpeech Edge settings
panel are owned here. Other UIA notifications retain NVDA's native handling.
"""
from __future__ import annotations

from collections.abc import Mapping

import appModuleHandler
import ui

from globalPlugins._speech_core.settings import edge_notifications_config
from globalPlugins._speech_core.settings.web_summary_config import get_notify_when_page_ready


_PAGE_LOADING_ACTIVITY_ID = "PageLoading"
_PAGE_LOADING_START_TEXT = "Loading page"
_PAGE_LOADING_COMPLETE_TEXT = "Loading complete"


class AppModule(appModuleHandler.AppModule):
    def event_UIA_notification(
        self,
        obj,
        nextHandler,
        notificationKind=None,
        notificationProcessing=None,
        displayString=None,
        activityId=None,
        **kwargs,
    ):
        """Apply the current per-activity Edge notification preference.

        Config is deliberately read per event so settings changes take effect
        immediately. Broken config access fails open to native NVDA handling.
        No download foreground heuristic is included: this module has no safe,
        tested UIA focus/tree predicate for such a policy.
        """
        if not isinstance(activityId, str) or activityId not in edge_notifications_config.ACTIVITY_IDS:
            nextHandler()
            return

        try:
            enabled_ids = edge_notifications_config.get_enabled_activity_ids()
            custom_messages = edge_notifications_config.get_custom_messages()
            config_is_valid = (
                isinstance(enabled_ids, (tuple, list, set, frozenset))
                and all(
                    isinstance(enabled_id, str)
                    and enabled_id in edge_notifications_config.ACTIVITY_IDS
                    for enabled_id in enabled_ids
                )
                and isinstance(custom_messages, Mapping)
            )
            if not config_is_valid:
                nextHandler()
                return
            if activityId not in enabled_ids:
                return
            custom_message = custom_messages.get(activityId)
        except Exception:
            nextHandler()
            return

        if activityId == _PAGE_LOADING_ACTIVITY_ID:
            normalized_display_string = displayString.strip() if isinstance(displayString, str) else None
            page_loading_phase = {
                _PAGE_LOADING_START_TEXT: "start",
                _PAGE_LOADING_COMPLETE_TEXT: "complete",
            }.get(normalized_display_string)
            if page_loading_phase == "complete":
                try:
                    if get_notify_when_page_ready():
                        return
                except Exception:
                    # A broken Page Ready getter must preserve native Edge behavior.
                    nextHandler()
                    return
                # Completion is owned by the shared Page Ready setting, never by
                # the PageLoading custom start-message setting.
                nextHandler()
                return
            # The exact start event and future PageLoading text keep the
            # established PageLoading policy below.

        if isinstance(custom_message, str):
            custom_message = custom_message.strip()
            if custom_message:
                ui.message(custom_message)
                return
        nextHandler()
